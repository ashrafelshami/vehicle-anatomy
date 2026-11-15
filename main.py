#!/usr/bin/env python3
"""Vehicle Anatomy: view DBC files as ECUs and wires inside a transparent 3D vehicle.

Usage:
    python vehicle_anatomy.py sample.dbc
    python vehicle_anatomy.py ./dbc_folder
    python vehicle_anatomy.py powertrain.dbc body.dbc --vehicle truck --port 8000

ECU positions: drag the ECUs, then press "Save ECU positions". They are written to
positions/<vehicle>.json and read again when you open that vehicle.

Each DBC file is treated as one bus (named after the file). Gateway ECUs that
appear in several files link the buses together.
"""

import argparse
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Default display settings. Change them here, or with the gear icon in the page
# (the gear saves only the values you changed to settings.json next to this script).
# Sizes are multiples of a base size that is auto-fitted to the vehicle and the
# number of ECUs, so they stay in proportion for a car, a truck or an airplane.
# ---------------------------------------------------------------------------
ECU_SIZE = (0.3, 0.05, 0.3)  # ECU plate width, height, depth (thin, no text on it)
ECU_SCALE = 0.5  # multiplier for the whole ECU plate (0.5 = half size)
ECU_LEADER = 0.35  # length of the line from the plate up to the name
ECU_NAME_WIDTH = 0.8  # width of the ECU name text above the line
WIRE_RADIUS = 0.001  # wire thickness
ETH_WIRE_FACTOR = 1  # ETH wires are this many times thicker
WIRE_LABEL_SIZE = 0.4  # width of the bus label on each wire
WIRE_LABEL_SELECTED_ZOOM = 1.7  # how much a label grows on a selected wire
PARTICLE_SIZE = 0.005  # size of the moving dots on a selected wire
VEHICLE_OPACITY_MIN = 1  # transparency slider, left end (0 = vehicle invisible)
VEHICLE_OPACITY_MAX = 100  # transparency slider, right end (25 is the original look, 100 is much more solid)
VEHICLE_OPACITY_DEFAULT = 10  # slider start value
VEHICLE_OPACITY_REMEMBER = False  # True: the browser remembers the last slider value and it replaces the default next time
ORBIT_ROTATE_SPEED = 0.5  # mouse rotation speed (1 = fast, 0.3 = slow)
ORBIT_DAMPING = 0.2  # how fast the rotation stops after you let go (0.05 = glides a long time, 1 = stops at once)

SETTINGS = {
    "ecu_size": list(ECU_SIZE),
    "ecu_scale": ECU_SCALE,
    "ecu_leader": ECU_LEADER,
    "ecu_name_width": ECU_NAME_WIDTH,
    "wire_radius": WIRE_RADIUS,
    "eth_wire_factor": ETH_WIRE_FACTOR,
    "wire_label_size": WIRE_LABEL_SIZE,
    "wire_label_selected_zoom": WIRE_LABEL_SELECTED_ZOOM,
    "particle_size": PARTICLE_SIZE,
    "opacity_min": VEHICLE_OPACITY_MIN,
    "opacity_max": VEHICLE_OPACITY_MAX,
    "opacity_default": VEHICLE_OPACITY_DEFAULT,
    "opacity_remember": VEHICLE_OPACITY_REMEMBER,
    "orbit_rotate_speed": ORBIT_ROTATE_SPEED,
    "orbit_damping": ORBIT_DAMPING,
}

BU_RE = re.compile(r"^BU_:\s*(.*)$")
BO_RE = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)")
SG_RE = re.compile(
    r"^\s*SG_\s+(\w+)(?:\s+(?:M|m\d+M?))?\s*:\s*(\d+)\|(\d+)@([01])([+-])"
    r"\s*\(([^,]+),([^)]+)\)\s*\[([^|]*)\|([^\]]*)\]\s*\"([^\"]*)\"\s*(.*)$"
)
BA_RE = re.compile(r'^BA_\s+"BusType"\s+"([^"]*)"')
NONE_NODE = "Vector__XXX"
BUS_GUESS = [
    (r"can[_ -]?fd", "CAN FD"),
    (r"(?<![a-z])eth(ernet)?(?![a-z])", "ETH"),
    (r"flex", "FlexRay"),
    (r"(?<![a-z])lin(?![a-z])", "LIN"),
]


def guess_bus_type(name):
    for pat, kind in BUS_GUESS:
        if re.search(pat, name.lower()):
            return kind
    return "CAN"


def parse_dbc(path, bus):
    ecus, frames, cur, btype = [], [], None, None
    text = Path(path).read_text(encoding="latin-1")
    for line in text.splitlines():
        m = BA_RE.match(line)
        if m:
            btype = m.group(1)
            continue
        m = BU_RE.match(line)
        if m:
            ecus += [n for n in m.group(1).split() if n != NONE_NODE]
            continue
        m = BO_RE.match(line)
        if m:
            sender = "" if m.group(4) == NONE_NODE else m.group(4)
            cur = {
                "id": hex(int(m.group(1)) & 0x1FFFFFFF),
                "name": m.group(2),
                "dlc": int(m.group(3)),
                "sender": sender,
                "bus": bus,
                "signals": [],
            }
            frames.append(cur)
            continue
        m = SG_RE.match(line)
        if m and cur is not None:
            rx = [
                r.strip()
                for r in m.group(11).split(",")
                if r.strip() and r.strip() != NONE_NODE
            ]
            cur["signals"].append(
                {
                    "name": m.group(1),
                    "start": int(m.group(2)),
                    "length": int(m.group(3)),
                    "unit": m.group(10),
                    "receivers": rx,
                }
            )
    return ecus, frames, btype


VEHICLE_DIR = (
    Path(__file__).resolve().parent / "vehicles"
)  # one .js design file per vehicle
SETTINGS_FILE = (
    Path(__file__).resolve().parent / "settings.json"
)  # values changed with the gear icon in the page
POSITIONS_DIR = (
    Path(__file__).resolve().parent / "positions"
)  # one <vehicle>.json file of ECU positions per vehicle


def vehicle_names():
    return [f.stem for f in sorted(VEHICLE_DIR.glob("*.js"))]


def load_vehicles():
    """Read the design files on every page load, so edits show up after a browser reload."""
    files = sorted(VEHICLE_DIR.glob("*.js"))
    return "\n".join(f.read_text(encoding="utf-8") for f in files), [
        f.stem for f in files
    ]


def collect_dbcs(paths):
    """Expand files and directories (searched recursively) into a list of .dbc files."""
    found = []
    for p in map(Path, paths):
        if p.is_dir():
            found += sorted(
                f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".dbc"
            )
        elif p.is_file():
            found.append(p)
        else:
            raise SystemExit(f"Not found: {p}")
    found = list(dict.fromkeys(found))
    if not found:
        raise SystemExit("No .dbc files found.")
    return found


def build_model(files, vehicle, overrides=None, channels=None):
    """Bus type comes from --bus-type, else the DBC's BusType attribute, else the file name."""
    overrides, channels = overrides or {}, channels or {}
    ecus, frames, buses = [], [], []
    for f in files:
        bus = Path(f).stem
        e, fr, btype = parse_dbc(f, bus)
        buses.append(
            {"name": bus, "type": overrides.get(bus) or btype or guess_bus_type(bus)}
        )
        ecus += e
        frames += fr
    count = (
        {}
    )  # channel names: CAN 1, CAN 2, LIN 1, ETH 1 ... in file order, unless set with --channel
    for b in buses:
        count[b["type"]] = count.get(b["type"], 0) + 1
        b["channel"] = channels.get(b["name"]) or f'{b["type"]} {count[b["type"]]}'
    for fr in frames:  # nodes only mentioned in messages/signals
        ecus.append(fr["sender"])
        for s in fr["signals"]:
            ecus += s["receivers"]
    ecus = list(dict.fromkeys(e for e in ecus if e))
    return {"vehicle": vehicle, "buses": buses, "ecus": ecus, "frames": frames}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def changed_settings(data):
    """Keep only valid values that differ from the defaults above."""
    out = {}
    if not isinstance(data, dict):
        return out
    for key, dv in SETTINGS.items():
        v = data.get(key)
        if isinstance(dv, bool):
            ok = isinstance(v, bool)
        elif isinstance(dv, list):
            ok = isinstance(v, list) and len(v) == len(dv) and all(_num(x) for x in v)
        else:
            ok = _num(v)
        if ok and v != dv:
            out[key] = v
    return out


def read_settings():
    try:
        return changed_settings(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def save_settings(data):
    out = changed_settings(data)
    if out:
        SETTINGS_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    elif SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()


def make_handler(get_page, save_layout):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = get_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # the page saves ECU positions here
            try:
                req = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                )
                if self.path == "/layout":
                    save_layout(req["vehicle"], req["positions"])
                elif self.path == "/settings":
                    save_settings(req)
                else:
                    raise ValueError
                self.send_response(204)
            except Exception as exc:
                body = (str(exc) or type(exc).__name__).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.end_headers()

        def log_message(self, *a):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "dbc", nargs="+", help="directories and/or .dbc files (one bus per file)"
    )
    ap.add_argument(
        "--vehicle",
        default=None,
        help="design from the vehicles/ folder (default: car)",
    )
    ap.add_argument(
        "--bus-type",
        action="append",
        default=[],
        metavar="NAME=TYPE",
        help="set a bus type, e.g. --bus-type backbone=ETH (NAME is the file name without .dbc)",
    )
    ap.add_argument(
        "--channel",
        action="append",
        default=[],
        metavar="NAME=CHANNEL",
        help='set a channel name, e.g. --channel body="CAN 3" (default: numbered per type in file order)',
    )
    ap.add_argument(
        "--positions",
        default=str(POSITIONS_DIR),
        help="directory with one <vehicle>.json file of ECU positions per vehicle (default: positions/ next to this script)",
    )
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    names = vehicle_names()
    if args.vehicle is None:  # no --vehicle given: use truck, or the first design found
        args.vehicle = "truck" if "truck" in names else (names[0] if names else "")
    if args.vehicle not in names:
        raise SystemExit(
            f"Unknown vehicle '{args.vehicle}'. Available: {', '.join(vehicle_names()) or 'none'} (folder: {VEHICLE_DIR})"
        )

    files = collect_dbcs(args.dbc)
    print("DBC files: " + ", ".join(f.name for f in files))
    overrides = dict(x.split("=", 1) for x in args.bus_type if "=" in x)
    chans = dict(x.split("=", 1) for x in args.channel if "=" in x)
    model = build_model(files, args.vehicle, overrides, chans)
    print(
        "Channels: "
        + ", ".join(f"{b['channel']} = {b['name']}" for b in model["buses"])
    )
    pos_dir = Path(args.positions)
    print(f"ECU positions folder: {pos_dir}")

    def read_layout():
        """Read every <vehicle>.json again on each page load, so a saved position shows after a reload."""
        out = {}
        for f in sorted(pos_dir.glob("*.json")):
            try:
                out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        return out

    def save_layout(vehicle, positions):
        if vehicle not in vehicle_names():
            raise ValueError("unknown vehicle")
        clean = {
            str(n): [float(v) for v in xyz]
            for n, xyz in positions.items()
            if len(xyz) == 3
        }
        pos_dir.mkdir(parents=True, exist_ok=True)
        (pos_dir / f"{vehicle}.json").write_text(
            json.dumps(clean, indent=1), encoding="utf-8"
        )

    def get_page():
        js, names = load_vehicles()
        data = json.dumps(
            {**model, "layout": read_layout(), "vehicles": names, "defaults": SETTINGS}
        ).replace("</", "<\\/")
        settings = json.dumps({**SETTINGS, **read_settings()})
        return (
            HTML.replace("__VEHICLES__", js)
            .replace("__SETTINGS__", settings)
            .replace("__DATA__", data)
        )

    url = f"http://localhost:{args.port}/"
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), make_handler(get_page, save_layout)
    )
    print(
        f"{len(model['ecus'])} ECUs, {len(model['frames'])} frames on {len(model['buses'])} bus(es)"
    )
    print(f"Serving {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vehicle Anatomy</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>
:root{--bg:#0a111d;--panel:#0f1a2b;--line:#1f3250;--ink:#dce8fa;--dim:#7f95b5;--src:#3ddc97;--dst:#ff9f43;--sig:#ffe07a}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 "IBM Plex Sans",system-ui,sans-serif}
#app{display:grid;grid-template-columns:var(--sidew,350px) 1fr;height:100%}
#side{position:relative;background:var(--panel);border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
#head{padding:14px 14px 10px;border-bottom:1px solid var(--line)}
#head h1{font-size:17px;margin:0 0 8px;font-weight:600}
#head .row{display:flex;gap:8px}
input,select{background:#0a1424;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:7px 9px;font:inherit}
input{flex:1;min-width:0}
input:focus,select:focus,button:focus-visible{outline:2px solid var(--sig);outline-offset:1px}
#tree{overflow:auto;flex:1;padding:6px 0}
.ecu>button.eh{all:unset;display:flex;width:100%;box-sizing:border-box;padding:8px 14px;cursor:pointer;gap:8px;align-items:center}
.ecu>button.eh:hover{background:#14233a}
.ecu.sel>button.eh{background:#17304f}
.eh .nm{font-weight:600;flex:1}
.eh .ct{color:var(--dim);font:12px "IBM Plex Mono",monospace}
.ecu .body{display:none;padding:0 0 6px 14px;border-left:2px solid var(--line);margin-left:18px}
.ecu.open .body{display:block}
.grp{color:var(--dim);font-size:12px;margin:8px 0 2px 8px}
.fr{margin:2px 0}
.fr>button.fh{all:unset;display:block;padding:3px 8px;cursor:pointer;font:12.5px "IBM Plex Mono",monospace;color:#b8cdee;width:100%;box-sizing:border-box}
.fr>button.fh:hover{background:#14233a}
.fr.sel>button.fh{background:#17304f}
.fr{position:relative}
.tg{all:unset;position:absolute;right:8px;top:2px;cursor:pointer;color:var(--dim);padding:0 6px;font-size:12px}
.tg::before{content:"\25BE"}.fr.closed .tg::before{content:"\25B8"}.tg:hover{color:var(--ink)}
.fr.closed>.sg{display:none}
#head .row button{flex:1;background:#0a1424;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font:inherit;font-size:13px;cursor:pointer}
#head .row button:hover{background:#17304f}
.sg{all:unset;display:block;box-sizing:border-box;width:calc(100% - 16px);margin-left:16px;padding:2px 8px;cursor:pointer;font:12px "IBM Plex Mono",monospace;color:var(--dim)}
.sg:hover{background:#14233a;color:var(--ink)}
.sg.sel{background:#3a3417;color:var(--sig)}
#legend{padding:8px 14px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--dim)}
#legend i{display:inline-block;width:18px;height:3px;margin-right:5px;vertical-align:middle;border-radius:2px}
#rz{position:absolute;top:0;bottom:0;right:-4px;width:8px;cursor:col-resize;z-index:5;touch-action:none}
#rz::after{content:"";position:absolute;top:0;bottom:0;left:3px;width:2px;background:transparent;transition:background .15s}
#rz:hover::after,#rz.on::after,#rz:focus-visible::after{background:var(--sig)}
#stage{position:relative;min-width:0}
#view{position:absolute;inset:0}
#info{position:absolute;left:16px;right:16px;bottom:14px;background:#0f1a2bdd;border:1px solid var(--line);border-radius:8px;padding:10px 14px;font-size:13px;pointer-events:none}
#info b{font-weight:600}
.s{color:var(--src)}.d{color:var(--dst)}
#topbar{position:absolute;top:14px;left:16px;right:16px;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-start;pointer-events:none;z-index:3}
#topbar>*{pointer-events:auto}
#savebar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#right{display:flex;gap:8px;align-items:flex-start;justify-content:flex-end;flex:1 1 420px;min-width:0}
#savebar button{background:#0f1a2bdd;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:7px 11px;font:inherit;cursor:pointer}
#savebar button:hover{background:#17304f}#savebar button.dirty{border-color:var(--sig);color:var(--sig)}
#savebar #load{display:flex;gap:6px;align-items:center}
#savemsg{font-size:12px;color:var(--dim)}
#gear{flex:none;background:#0f1a2bdd;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:7px 9px;cursor:pointer;display:flex}
#gear:hover,#gear[aria-expanded=true]{background:#17304f}
#settings{position:absolute;top:58px;right:16px;width:330px;max-width:calc(100% - 32px);max-height:calc(100% - 150px);overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 14px 12px;font-size:13px}
#settings[hidden]{display:none}
#settings h3{font-size:12px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;margin:12px 0 6px}
#settings .set{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:5px 0}
#settings .set span{flex:1}
#settings .set input[type=number]{flex:none;width:76px;padding:4px 6px;font:12px "IBM Plex Mono",monospace}
#settings .set.vec input[type=number]{width:56px}
#settings .set input[type=checkbox]{flex:none;width:16px;height:16px}
#settings .btns{display:flex;gap:8px;align-items:center;margin-top:14px}
#settings .btns button{background:#0a1424;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font:inherit;cursor:pointer}
#settings .btns button:hover{background:#17304f}
#setmsg{display:block;margin-top:8px;font-size:12px;color:var(--dim)}
#setmsg:empty{display:none}
#tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;min-width:0}
#tools button,#tools label{background:#0f1a2bdd;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:7px 11px;font:inherit}
#tools button{cursor:pointer}#tools button:hover{background:#17304f}#tools button:disabled{opacity:.4;cursor:not-allowed}
#tools label{display:flex;gap:8px;align-items:center;font-size:13px;padding:5px 10px}
#tools input[type=range]{width:90px;flex:none;padding:0}
#tools output{min-width:2.4em;font:12px "IBM Plex Mono",monospace;color:var(--dim)}
@media(max-width:760px){
  #rz{display:none}
  #app{grid-template-columns:1fr;grid-template-rows:42% 58%}
  #side{order:2;border-right:0;border-top:1px solid var(--line)}
  #topbar button,#tools label{padding:5px 8px;font-size:12px}
  #tools input[type=range]{width:64px}
}
</style></head>
<body><div id="app">
<aside id="side">
 <div id="head"><h1>Vehicle Anatomy</h1>
  <div class="row"><input id="q" type="search" placeholder="Find ECU, frame or signal" aria-label="Search">
  <select id="veh" aria-label="Vehicle"></select></div>
  <div class="row" style="margin-top:8px"><button id="expand">Expand all</button><button id="collapse">Collapse all</button></div></div>
 <div id="tree"></div><div id="legend"></div>
 <div id="rz" role="separator" aria-orientation="vertical" aria-label="Resize side panel (drag, double-click to reset)" tabindex="0"></div>
</aside>
<main id="stage"><div id="view"></div>
<div id="topbar"><div id="savebar"><button id="save">Save ECU positions</button><button id="load" title="Load ECU positions from a JSON file" aria-label="Load ECU positions"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:block"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1"/><path d="M3 10h19l-2 8a2 2 0 0 1-2 1.5H5A2 2 0 0 1 3 18z"/></svg>Load positions</button><input id="loadfile" type="file" accept=".json,application/json" hidden><span id="savemsg" role="status"></span></div>
<div id="right"><div id="tools"><label title="Vehicle transparency"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.7s7 7.2 7 12a7 7 0 0 1-14 0c0-4.8 7-12 7-12z"/></svg><input id="opa" type="range" min="0" max="100" value="25" aria-label="Vehicle opacity"><output id="opaout" for="opa">25%</output></label><button id="center" disabled>Center on ECU</button><button id="reset">Reset view</button><button id="hide">Hide vehicle</button><button id="hideecu">Hide ECUs</button><button id="hidewire">Hide wiring</button>
<button id="lock">Lock ECUs</button><button id="relayout">Reset ECU positions</button></div>
<button id="gear" title="Settings" aria-label="Settings" aria-expanded="false"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></button>
</div></div><div id="settings" hidden></div>
<div id="info">Select an ECU, frame or signal to follow the data. Drag the background to orbit, scroll to zoom, right-drag to pan. Drag an ECU box to move it, Shift+drag to lift it, or drag one of its X/Y/Z arrows to move it along that axis.</div></main>
</div>
<script>window.VEHICLES = {};
__VEHICLES__
</script>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.1/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const D = __DATA__, ST = __SETTINGS__;
const Vq = new URLSearchParams(location.search).get('vehicle') || D.vehicle, V = VEHICLES[Vq] ? Vq : D.vehicles[0];
const $ = id => document.getElementById(id);
const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
const BUSCOL = [0x4cc9f0, 0xf72585, 0xb5e48c, 0xffd166, 0xb892ff, 0xff8fab];
const busNames = D.buses.map(b => b.name), busType = Object.fromEntries(D.buses.map(b => [b.name, b.type])), busChan = Object.fromEntries(D.buses.map(b => [b.name, b.channel]));
const busColor = b => BUSCOL[Math.max(0, busNames.indexOf(b)) % BUSCOL.length];

/* ---------- scene ---------- */
const host = $('view');
const renderer = new THREE.WebGLRenderer({antialias: true});
renderer.setPixelRatio(devicePixelRatio);
host.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0a111d);
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500);
const controls = new OrbitControls(camera, renderer.domElement);
controls.rotateSpeed = ST.orbit_rotate_speed; controls.dampingFactor = ST.orbit_damping; controls.enableDamping = ST.orbit_damping < 1;
/* three axis arrows (X red, Y green, Z blue) on the selected ECU: drag one to move the ECU along that axis */
const gizmo = new THREE.Group(); gizmo.visible = false; scene.add(gizmo);
const arrowPick = [];
[[0xff5555, new THREE.Vector3(1, 0, 0)], [0x55e07a, new THREE.Vector3(0, 1, 0)], [0x5599ff, new THREE.Vector3(0, 0, 1)]].forEach(([col, dir]) => {
  const g = new THREE.Group(); g.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
  const mat = new THREE.MeshBasicMaterial({color: col, depthTest: false, transparent: true});
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(.012, .012, .72, 8), mat); shaft.position.y = .46;
  const cone = new THREE.Mesh(new THREE.ConeGeometry(.055, .18, 16), mat); cone.position.y = .91;
  const pick = new THREE.Mesh(new THREE.CylinderGeometry(.07, .07, .9, 8), new THREE.MeshBasicMaterial({visible: false})); pick.position.y = .55; pick.userData.axis = dir;
  shaft.renderOrder = cone.renderOrder = 20; g.add(shaft, cone, pick); gizmo.add(g); arrowPick.push(pick);
});
scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 1.4));
const dl = new THREE.DirectionalLight(0xffffff, 1.2); dl.position.set(6, 10, 8); scene.add(dl);
const grid = new THREE.GridHelper(60, 60, 0x1f3250, 0x14233a); scene.add(grid);
const vehicleGroup = new THREE.Group(); scene.add(vehicleGroup);

const CFG = VEHICLES[V];  // design from vehicles/<name>.js: zone, s, cam, gy, build()
grid.position.y = CFG.gy;
const ghost = new THREE.MeshPhysicalMaterial({color: 0x7fb2ff, transparent: true, opacity: 0.1, roughness: 0.2, side: THREE.DoubleSide, depthWrite: false});
const edge = new THREE.LineBasicMaterial({color: 0x4d7fc4, transparent: true, opacity: 0.55});
const look = (color, op, edgeColor, edgeOp) => [
  new THREE.MeshPhysicalMaterial({color, transparent: true, opacity: op, roughness: .3, side: THREE.DoubleSide, depthWrite: false}),
  new THREE.LineBasicMaterial({color: edgeColor, transparent: true, opacity: edgeOp})];
const KINDS = {shell: [ghost, edge], int: look(0xffcf8a, .2, 0xe0a85f, .85), mech: look(0x9fd0b4, .16, 0x6fb08e, .75), acc: look(0x7fe0ff, .28, 0x55d3ff, .95)};
const VMATS = Object.values(KINDS).flatMap(([m, l]) => [[m, m.opacity], [l, l.opacity]]);  // vehicle materials and their base opacity
function setVehicleOpacity(v) { VMATS.forEach(([m, o]) => { m.opacity = Math.min(1, o * v / 25); }); }  // 25 = the original look
function part(geo, x = 0, y = 0, z = 0, rot, kind = 'shell') {
  const [mat, ln] = KINDS[kind];
  const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); if (rot) m.rotation.set(...rot);
  m.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 20), ln)); vehicleGroup.add(m);
}
const B = (x, y, z) => new THREE.BoxGeometry(x, y, z), C = (r, h, n = 24) => new THREE.CylinderGeometry(r, r, h, n);
const H = Math.PI / 2;
CFG.build({THREE, part, B, C, H});
camera.position.set(...CFG.cam); controls.target.set(0, (CFG.zone.y[0] + CFG.zone.y[1]) / 2, 0);

/* ---------- ECU boxes ---------- */
function nameTex(name) {  // transparent tag: just the ECU name
  const w = 512, h = 128, c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'); g.textAlign = 'center'; g.textBaseline = 'middle';
  let fs = 80; g.font = `600 ${fs}px sans-serif`;
  while (g.measureText(name).width > w * .95 && fs > 14) { fs -= 2; g.font = `600 ${fs}px sans-serif`; }
  g.lineWidth = 10; g.strokeStyle = '#0a111d'; g.strokeText(name, w / 2, h / 2);  // dark outline for readability
  g.fillStyle = '#e8f1ff'; g.fillText(name, w / 2, h / 2);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const rows = 3, n = Math.max(1, D.ecus.length), cols = Math.ceil(n / rows);
const [x0, x1] = CFG.zone.x, [y0, y1] = CFG.zone.y;
const stepX = cols > 1 ? (x1 - x0) / (cols - 1) : 0;
const S = stepX ? Math.min(CFG.s, stepX / 1.5) : CFG.s;
const ecuObj = {}, SAVED = (D.layout || {})[V] || {};
D.ecus.forEach((name, i) => {
  const c = Math.floor(i / rows), r = i % rows;
  const mats = [new THREE.MeshStandardMaterial({color: 0x3d7bd6, roughness: .5})];
  const mesh = new THREE.Mesh(B(...ST.ecu_size.map(v => S * v * ST.ecu_scale)), mats[0]);
  const L = S * ST.ecu_leader, tw = S * ST.ecu_name_width;
  const lineMat = new THREE.LineBasicMaterial({color: 0x5aa9ff});
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, L, 0)]), lineMat); mesh.add(line);
  const tag = new THREE.Sprite(new THREE.SpriteMaterial({map: nameTex(name), transparent: true, depthTest: false}));
  tag.scale.set(tw, tw / 4, 1); tag.position.set(0, L + tw / 8, 0); tag.renderOrder = 11; mesh.add(tag);
  const auto = new THREE.Vector3(cols > 1 ? x0 + stepX * c : (x0 + x1) / 2, y0 + (r % 2) * (y1 - y0), (r - 1) * CFG.zone.z);
  mesh.position.copy(SAVED[name] ? new THREE.Vector3(...SAVED[name]) : auto);
  mesh.userData.ecu = name; scene.add(mesh); ecuObj[name] = {mesh, mats, auto, lineMat, tag, line};
});
function glow(name, hex) { const o = ecuObj[name]; o.mats.forEach(m => m.emissive.setHex(hex)); o.lineMat.color.setHex(hex ? 0xffe07a : 0x5aa9ff); }

/* ---------- wires ---------- */
const pairs = new Map();
const pk = (a, b, bus) => (a < b ? a + '|' + b : b + '|' + a) + '|' + bus;
D.frames.forEach(f => f.signals.forEach(s => s.receivers.forEach(r => {
  if (f.sender && r !== f.sender && ecuObj[f.sender] && ecuObj[r]) {
    const k = pk(f.sender, r, f.bus); if (!pairs.has(k)) pairs.set(k, {a: [f.sender, r].sort()[0], b: [f.sender, r].sort()[1], bus: f.bus});
  }
})));
function setLabel(w, k) { w.label.scale.set(S * ST.wire_label_size * k, S * ST.wire_label_size / 4 * k, 1); }
function wireTex(text) {  // same look as the ECU name: plain text with a dark outline, no box
  const c = document.createElement('canvas'); c.width = 512; c.height = 128;
  const g = c.getContext('2d'); g.textAlign = 'center'; g.textBaseline = 'middle';
  let fs = 64; g.font = `600 ${fs}px sans-serif`;
  while (g.measureText(text).width > 488 && fs > 14) { fs -= 2; g.font = `600 ${fs}px sans-serif`; }
  g.lineWidth = 10; g.strokeStyle = '#0a111d'; g.strokeText(text, 256, 64);
  g.fillStyle = '#e8f1ff'; g.fillText(text, 256, 64);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const wires = new Map(); let wi = 0;
function layoutWire(w) {  // recompute a wire after an ECU moved
  const pa = ecuObj[w.a].mesh.position, pb = ecuObj[w.b].mesh.position, c = w.curve;
  c.v0.copy(pa); c.v2.copy(pb);
  c.v1.copy(pa).add(pb).multiplyScalar(.5); c.v1.y += .25 + pa.distanceTo(pb) * .12 + w.lift; c.v1.z += w.zoff;
  w.mesh.geometry.dispose(); w.mesh.geometry = new THREE.TubeGeometry(c, 40, w.rad, 6);
  w.base.copy(c.getPoint(.5)); w.label.position.copy(w.base);
}
for (const [k, p] of pairs) {
  const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3());
  const col = busColor(p.bus), type = busType[p.bus];
  const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({color: col, transparent: true, opacity: .35})); scene.add(mesh);
  const label = new THREE.Sprite(new THREE.SpriteMaterial({map: wireTex(`${busChan[p.bus]} · ${p.bus}`), transparent: true, depthTest: false, opacity: .75}));
  label.scale.set(S * ST.wire_label_size, S * ST.wire_label_size / 4, 1); label.renderOrder = 10; scene.add(label);
  const w = {...p, curve, mesh, label, col, base: new THREE.Vector3(), rad: S * ST.wire_radius * (type === 'ETH' ? ST.eth_wire_factor : 1), lift: (wi % 4) * .12, zoff: ((wi % 3) - 1) * .15};
  wi++; wires.set(k, w); layoutWire(w);
}

/* ---------- selection & animation ---------- */
let pGeo = new THREE.SphereGeometry(S * ST.particle_size, 10, 10); const pMat = new THREE.MeshBasicMaterial({color: 0xffe07a});
let moving = [];
let selEcu = null;
function syncGizmo() { gizmo.visible = !!(selEcu && !locked && showEcus); }
function setSel(n) { selEcu = n && ecuObj[n] ? n : null; $('center').disabled = !selEcu; syncGizmo(); }
function clearSel() {
  setSel(null);
  wires.forEach(w => { w.mesh.material.opacity = .35; w.mesh.material.color.setHex(w.col); w.label.material.opacity = .6; setLabel(w, 1); });
  moving.forEach(m => scene.remove(m.mesh)); moving = [];
  for (const e in ecuObj) glow(e, 0);
  document.querySelectorAll('.sel').forEach(e => e.classList.remove('sel'));
}
function follow(directed) {
  wires.forEach(w => { w.mesh.material.opacity = .07; w.label.material.opacity = .12; setLabel(w, 1); });
  const srcs = new Set(), dsts = new Set(), seen = new Set();
  directed.forEach(([s, d, bus]) => {
    const w = wires.get(pk(s, d, bus)); if (!w) return;
    srcs.add(s); dsts.add(d);
    if (seen.has(s + '>' + d + '>' + bus)) return; seen.add(s + '>' + d + '>' + bus);
    w.label.material.opacity = 1; setLabel(w, ST.wire_label_selected_zoom); w.mesh.material.opacity = .95; w.mesh.material.color.setHex(0xffe07a);
    for (let i = 0; i < 5; i++) {
      const m = new THREE.Mesh(pGeo, pMat); m.visible = showWires; scene.add(m);
      moving.push({mesh: m, curve: w.curve, dir: w.a === s ? 1 : -1, t0: i / 5});
    }
  });
  dsts.forEach(e => glow(e, 0x8a4300)); srcs.forEach(e => glow(e, 0x13804f));
  return [[...srcs], [...dsts]];
}
const fmt = (a, c) => a.length ? a.map(x => `<b class="${c}">${x}</b>`).join(', ') : '<i>none</i>';
function say(title, [s, d]) { $('info').innerHTML = `${title}<br>Source ${fmt(s, 's')} &rarr; destination ${fmt(d, 'd')}`; }

const txOf = e => D.frames.filter(f => f.sender === e);
const rxOf = e => D.frames.filter(f => f.signals.some(s => s.receivers.includes(e)));
function pickSignal(f, s, btn) {
  clearSel(); setSel(f.sender); if (btn) btn.classList.add('sel');
  say(`Signal <b>${s.name}</b> in frame ${f.name} (${f.id}) on <b>${busChan[f.bus]}</b> (${f.bus})`, follow(s.receivers.map(r => [f.sender, r, f.bus])));
}
function pickFrame(f, box) {
  clearSel(); setSel(f.sender); if (box) box.classList.add('sel');
  say(`Frame <b>${f.name}</b> (${f.id}) on <b>${busChan[f.bus]}</b> (${f.bus})`, follow(f.signals.flatMap(s => s.receivers.map(r => [f.sender, r, f.bus]))));
}
function pickEcu(e, box) {
  clearSel(); setSel(e); if (box) box.classList.add('sel');
  const out = txOf(e).flatMap(f => f.signals.flatMap(s => s.receivers.map(r => [e, r, f.bus])));
  const inn = rxOf(e).map(f => [f.sender, e, f.bus]).filter(p => p[0]);
  const [s, d] = follow([...out, ...inn]);
  $('info').innerHTML = `ECU <b>${e}</b>: sends to ${fmt([...new Set(out.map(p => p[1]))], 'd')}; receives from ${fmt([...new Set(inn.map(p => p[0]))], 's')}`;
  if (!s.includes(e) && !d.includes(e)) glow(e, 0x13804f); else glow(e, 0x2a6fdb);
}

/* ---------- side panel ---------- */
const tree = $('tree'), boxes = {}, frameRow = new Map(), sigBtn = new Map();  // rows of the sending ECU, for search
D.ecus.forEach(e => {
  const box = el('div', 'ecu'), tx = txOf(e), rx = rxOf(e);
  const h = el('button', 'eh'); h.append(el('span', 'nm', e), el('span', 'ct', `TX ${tx.length} · RX ${rx.length}`));
  const body = el('div', 'body');
  const frame = (f, sigs, tag) => {
    const fr = el('div', 'fr'); const fh = el('button', 'fh', `${f.name}  ${f.id}  ${busChan[f.bus]}${tag}`);
    fh.onclick = () => pickFrame(f, fr); fr.append(fh); if (!tag) frameRow.set(f, fr);
    sigs.forEach(s => { const b = el('button', 'sg', s.name + (s.unit ? ` [${s.unit}]` : '')); b.onclick = () => pickSignal(f, s, b); fr.append(b); if (!tag) sigBtn.set(s, b); });
    if (sigs.length) { const tg = el('button', 'tg'); tg.title = 'Collapse / expand signals'; tg.setAttribute('aria-label', 'Collapse or expand signals'); tg.onclick = ev => { ev.stopPropagation(); fr.classList.toggle('closed'); }; fr.append(tg); }
    body.append(fr);
  };
  if (tx.length) body.append(el('div', 'grp', 'Sends'));
  tx.forEach(f => frame(f, f.signals, ''));
  if (rx.length) body.append(el('div', 'grp', 'Receives'));
  rx.forEach(f => frame(f, f.signals.filter(s => s.receivers.includes(e)), `  from ${f.sender || '?'}`));
  h.onclick = () => { box.classList.toggle('open'); pickEcu(e, box); };
  box.dataset.text = (e + ' ' + [...tx, ...rx].map(f => f.name + ' ' + f.signals.map(s => s.name).join(' ')).join(' ')).toLowerCase();
  box.append(h, body); tree.append(box); boxes[e] = box;
});
$('q').oninput = ev => {
  const q = ev.target.value.trim().toLowerCase();
  Object.values(boxes).forEach(b => { b.style.display = !q || b.dataset.text.includes(q) ? '' : 'none'; b.classList.toggle('open', !!q && b.dataset.text.includes(q)); });
  if (!q) return;
  const ex = D.ecus.find(e => e.toLowerCase() === q);  // an ECU name typed in full selects that ECU
  if (ex) { boxes[ex].style.display = ''; boxes[ex].classList.add('open'); pickEcu(ex, boxes[ex]); return; }
  /* a frame or signal matched: select the ECU that sends it (exact name first, then prefix, then contains) */
  const hits = [];
  D.frames.forEach(f => {
    if (!f.sender || !ecuObj[f.sender]) return;
    const names = [f.name, ...f.signals.map(s => s.name)].map(n => n.toLowerCase());
    const rank = names.some(n => n === q) ? 0 : names.some(n => n.startsWith(q)) ? 1 : names.some(n => n.includes(q)) ? 2 : 9;
    if (rank < 9) hits.push([rank, f.sender]);
  });
  if (!hits.length) return;
  const src = hits.sort((a, b) => a[0] - b[0])[0][1];
  boxes[src].style.display = ''; boxes[src].classList.add('open');
  pickEcu(src, boxes[src]); boxes[src].scrollIntoView({block: 'nearest'});
};
function reveal(elm, sender) {
  const b = boxes[sender]; if (b) { b.style.display = ''; b.classList.add('open'); }
  const fr = elm.closest('.fr'); if (fr) fr.classList.remove('closed');
  elm.scrollIntoView({block: 'nearest'});
}
$('q').onkeydown = ev => {  // Enter: select the best match (ECU, frame or signal) in the view
  if (ev.key !== 'Enter') return;
  const q = ev.target.value.trim().toLowerCase(); if (!q) return;
  const sc = n => { n = n.toLowerCase(); return n === q ? 0 : n.startsWith(q) ? 1 : n.includes(q) ? 2 : 9; };
  let best = null;
  const cand = (score, type, pick) => { if (score < 9 && (!best || score < best.score || (score === best.score && type < best.type))) best = {score, type, pick}; };
  D.ecus.forEach(e => cand(sc(e), 0, () => { pickEcu(e, boxes[e]); reveal(boxes[e], e); }));
  D.frames.forEach(f => {
    const row = frameRow.get(f);
    cand(sc(f.name), 1, () => { pickFrame(f, row); if (row) reveal(row, f.sender); });
    f.signals.forEach(s => { const b = sigBtn.get(s); cand(sc(s.name), 2, () => { pickSignal(f, s, b); if (b) reveal(b, f.sender); }); });
  });
  if (best) { ev.preventDefault(); best.pick(); }
};
D.buses.forEach(b => { const s = el('span'); const i = el('i'); i.style.background = '#' + busColor(b.name).toString(16).padStart(6, '0'); s.append(i, `${b.channel} · ${b.name}`); $('legend').append(s); });
D.vehicles.forEach(n => $('veh').append(new Option(n))); $('veh').value = V; $('veh').onchange = e => { location.search = '?vehicle=' + e.target.value; };

/* drag an ECU to move it (Shift = up/down); a click selects it */
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2(), cv = renderer.domElement;
const ecuMeshes = Object.values(ecuObj).map(o => o.mesh);
let drag = null;
const INFO0 = $('info').innerHTML;
function deselect() { clearSel(); $('info').innerHTML = INFO0; }
function aim(e) { const r = cv.getBoundingClientRect(); mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(mouse, camera); }
const _w = new THREE.Vector3();
function hitArrow(e) { aim(e); return ray.intersectObjects(arrowPick, false)[0]; }
function axisParam(o, d) {  // position along the axis line (through o, direction d) that is closest to the mouse ray
  const b = ray.ray.direction, w0 = _w.copy(o).sub(ray.ray.origin), bb = d.dot(b), den = 1 - bb * bb;
  return den < 1e-4 ? null : (bb * b.dot(w0) - d.dot(w0)) / den;
}
function hitEcu(e) { aim(e); return ray.intersectObjects(ecuMeshes.filter(m => m.visible), false)[0]; }
let dirty = false;
function setDirty(v, msg) { dirty = v; $('save').classList.toggle('dirty', v); $('savemsg').textContent = msg || (v ? 'Unsaved changes' : ''); }
async function savePositions() {
  try {
    const r = await fetch('/layout', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({vehicle: V, positions: allPos()})});
    if (!r.ok) throw 0;
    setDirty(false, `Saved to positions/${V}.json`);
  } catch (_) { setDirty(true, 'Save failed'); }
}
$('save').onclick = savePositions;
$('load').onclick = () => $('loadfile').click();
$('loadfile').onchange = async ev => {  // replace every ECU position in the view with the ones from the chosen file
  const f = ev.target.files[0]; ev.target.value = ''; if (!f) return;
  try {
    let pos = JSON.parse(await f.text());
    const ok = o => o && typeof o === 'object' && Object.values(o).every(v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite));
    if (!ok(pos) && pos && ok(pos[V])) pos = pos[V];
    if (!ok(pos)) throw 0;
    D.ecus.forEach(n => ecuObj[n].mesh.position.copy(pos[n] ? new THREE.Vector3(...pos[n]) : ecuObj[n].auto));
    wires.forEach(layoutWire); setDirty(true, `Loaded ${f.name} - not saved yet`);
  } catch (_) { $('savemsg').textContent = 'Could not read that positions file'; }
};
addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
const allPos = () => Object.fromEntries(D.ecus.map(n => [n, ecuObj[n].mesh.position.toArray().map(v => +v.toFixed(3))]));
cv.addEventListener('pointerdown', e => {
  const ah = gizmo.visible ? hitArrow(e) : null;
  if (ah) {  // start dragging along one axis arrow
    e.stopImmediatePropagation();
    const axis = ah.object.userData.axis.clone(), m = ecuObj[selEcu].mesh, t0 = axisParam(m.position, axis);
    drag = {x: e.clientX, y: e.clientY, moved: false, hit: null, arrow: {axis, start: m.position.clone(), t0: t0 || 0, m}};
    cv.setPointerCapture(e.pointerId); return;
  }
  const hit = hitEcu(e); drag = {x: e.clientX, y: e.clientY, moved: false, hit};
  if (!hit || locked) return;  // locked: no drag, orbit controls and click-to-select still work
  e.stopImmediatePropagation();  // keep the orbit controls out of an ECU drag
  const m = hit.object, plane = new THREE.Plane(), pt = new THREE.Vector3(), n = new THREE.Vector3(0, 1, 0);
  if (e.shiftKey) { camera.getWorldDirection(n); n.y = 0; n.normalize(); }
  plane.setFromNormalAndCoplanarPoint(n, m.position); ray.ray.intersectPlane(plane, pt);
  Object.assign(drag, {m, plane, off: m.position.clone().sub(pt), vertical: e.shiftKey});
  cv.setPointerCapture(e.pointerId);
}, true);
cv.addEventListener('pointermove', e => {
  if (drag && drag.arrow) {
    if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 2) drag.moved = true;
    aim(e); const a = drag.arrow, t = axisParam(a.start, a.axis); if (t === null) return;
    a.m.position.copy(a.start).addScaledVector(a.axis, t - a.t0);
    const n = a.m.userData.ecu; wires.forEach(w => { if (w.a === n || w.b === n) layoutWire(w); });
    return;
  }
  if (!drag || !drag.m) { cv.style.cursor = gizmo.visible && hitArrow(e) ? 'pointer' : hitEcu(e) ? (locked ? 'pointer' : 'grab') : ''; return; }
  if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 4) drag.moved = true;
  if (!drag.moved) return;
  aim(e); const pt = new THREE.Vector3(); if (!ray.ray.intersectPlane(drag.plane, pt)) return;
  pt.add(drag.off); const p = drag.m.position;
  if (drag.vertical) p.y = pt.y; else { p.x = pt.x; p.z = pt.z; }
  const n = drag.m.userData.ecu; wires.forEach(w => { if (w.a === n || w.b === n) layoutWire(w); });
  cv.style.cursor = 'grabbing';
});
cv.addEventListener('pointerup', e => {
  if (!drag) return; const d = drag; drag = null; cv.style.cursor = '';
  if (d.arrow) { try { cv.releasePointerCapture(e.pointerId); } catch (_) {} if (d.moved) setDirty(true); return; }
  if (d.m) { try { cv.releasePointerCapture(e.pointerId); } catch (_) {} }
  if (d.m && d.moved) setDirty(true);
  else if (d.hit && Math.hypot(e.clientX - d.x, e.clientY - d.y) <= 4) {
    const n = d.hit.object.userData.ecu; boxes[n].classList.add('open'); pickEcu(n, boxes[n]); boxes[n].scrollIntoView({block: 'nearest'});
  } else if (!d.hit && Math.hypot(e.clientX - d.x, e.clientY - d.y) <= 4) deselect();  // click on empty space
});
addEventListener('keydown', e => { if (e.key === 'Escape') deselect(); });

/* ---------- resizable side panel ---------- */
{
  const app = $('app'), rz = $('rz'); let w = 350;
  try { const x = parseInt(localStorage.getItem('va-sidew'), 10); if (x >= 200) w = x; } catch (_) {}
  const set = v => { w = Math.round(Math.min(Math.max(200, v), innerWidth * .7)); app.style.setProperty('--sidew', w + 'px'); };
  const save = () => { try { localStorage.setItem('va-sidew', w); } catch (_) {} };
  set(w);
  rz.onpointerdown = e => { rz.setPointerCapture(e.pointerId); rz.classList.add('on'); e.preventDefault(); };
  rz.onpointermove = e => { if (rz.hasPointerCapture(e.pointerId)) set(e.clientX - app.getBoundingClientRect().left); };
  rz.onpointerup = () => { rz.classList.remove('on'); save(); };
  rz.ondblclick = () => { set(350); save(); };
  rz.onkeydown = e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { set(w + (e.key === 'ArrowRight' ? 20 : -20)); save(); e.preventDefault(); } };
}

/* ---------- toolbar ---------- */
let opaV = ST.opacity_default;
function opaApply() {
  const lo = ST.opacity_min, hi = Math.max(lo + 1, ST.opacity_max);
  $('opa').min = lo; $('opa').max = hi; opaV = Math.min(hi, Math.max(lo, opaV));
  $('opa').value = opaV; $('opaout').textContent = opaV + '%'; setVehicleOpacity(opaV);
}
if (ST.opacity_remember) try { const x = parseInt(localStorage.getItem('va-opacity'), 10); if (Number.isFinite(x)) opaV = x; } catch (_) {}
opaApply();
$('opa').oninput = e => { opaV = +e.target.value; opaApply(); if (ST.opacity_remember) try { localStorage.setItem('va-opacity', opaV); } catch (_) {} };

/* ---------- settings panel (gear icon) ---------- */
function applySettings() {  // push the values in ST into the scene
  controls.rotateSpeed = ST.orbit_rotate_speed; controls.dampingFactor = ST.orbit_damping; controls.enableDamping = ST.orbit_damping < 1;
  const L = S * ST.ecu_leader, tw = S * ST.ecu_name_width;
  Object.values(ecuObj).forEach(o => {
    o.mesh.geometry.dispose(); o.mesh.geometry = B(...ST.ecu_size.map(v => S * v * ST.ecu_scale));
    o.line.geometry.dispose(); o.line.geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, L, 0)]);
    o.tag.scale.set(tw, tw / 4, 1); o.tag.position.set(0, L + tw / 8, 0);
  });
  wires.forEach(w => { w.rad = S * ST.wire_radius * (busType[w.bus] === 'ETH' ? ST.eth_wire_factor : 1); layoutWire(w); setLabel(w, w.label.material.opacity === 1 ? ST.wire_label_selected_zoom : 1); });
  pGeo.dispose(); pGeo = new THREE.SphereGeometry(S * ST.particle_size, 10, 10); moving.forEach(m => { m.mesh.geometry = pGeo; });
  opaApply();
}
const SPEC = [
  ['Vehicle transparency', [['opacity_min', 'Slider min', 'num', 1], ['opacity_max', 'Slider max', 'num', 1], ['opacity_default', 'Start value', 'num', 1], ['opacity_remember', 'Remember last value', 'bool']]],
  ['ECU', [['ecu_size', 'Plate width / height / depth', 'vec', .01], ['ecu_scale', 'Plate scale', 'num', .05], ['ecu_leader', 'Line length', 'num', .05], ['ecu_name_width', 'Name text width', 'num', .05]]],
  ['Wires', [['wire_radius', 'Wire thickness', 'num', .0005], ['eth_wire_factor', 'ETH wire factor', 'num', .1], ['wire_label_size', 'Bus label width', 'num', .05], ['wire_label_selected_zoom', 'Selected label zoom', 'num', .1], ['particle_size', 'Moving dot size', 'num', .001]]],
  ['Mouse', [['orbit_rotate_speed', 'Rotation speed', 'num', .05], ['orbit_damping', 'Rotation damping (1 = stop at once)', 'num', .01]]],
];
const panel = $('settings'), setIn = {};
const setMsg = el('span'); setMsg.id = 'setmsg'; setMsg.setAttribute('role', 'status');
function fillInputs() {
  for (const [, items] of SPEC) for (const [k, , kind] of items) {
    if (kind === 'bool') setIn[k][0].checked = !!ST[k];
    else if (kind === 'vec') setIn[k].forEach((i, n) => { i.value = ST[k][n]; });
    else setIn[k][0].value = ST[k];
  }
}
SPEC.forEach(([title, items]) => {
  panel.append(el('h3', '', title));
  items.forEach(([k, label, kind, step]) => {
    const row = el('label', kind === 'vec' ? 'set vec' : 'set'); row.append(el('span', '', label));
    const mk = n => { const i = el('input'); i.type = kind === 'bool' ? 'checkbox' : 'number'; if (step) i.step = step; if (kind !== 'bool') i.min = 0; i.setAttribute('aria-label', label); return i; };
    const ins = setIn[k] = kind === 'vec' ? [mk(), mk(), mk()] : [mk()];
    const commit = () => {
      if (kind === 'bool') ST[k] = ins[0].checked;
      else if (kind === 'vec') { const v = ins.map(i => parseFloat(i.value)); if (v.some(x => !Number.isFinite(x))) return; ST[k] = v; }
      else { const v = parseFloat(ins[0].value); if (!Number.isFinite(v)) return; ST[k] = v; }
      if (k === 'opacity_default') opaV = ST[k];
      setMsg.textContent = ''; applySettings();
    };
    ins.forEach(i => { i.oninput = commit; row.append(i); });
    panel.append(row);
  });
});
const btns = el('div', 'btns'), bSave = el('button', '', 'Save settings'), bReset = el('button', '', 'Reset to defaults');
btns.append(bSave, bReset); panel.append(btns, setMsg);
bSave.onclick = async () => {
  try { const r = await fetch('/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(ST)}); if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`); setMsg.textContent = 'Saved to settings.json'; }
  catch (error) { setMsg.textContent = `Save failed: ${error.message}`; }
};
bReset.onclick = () => { Object.assign(ST, JSON.parse(JSON.stringify(D.defaults))); opaV = ST.opacity_default; fillInputs(); applySettings(); setMsg.textContent = 'Defaults restored (press Save to keep)'; };
function placeSettings() {
  const t = $('topbar').offsetHeight + 22;
  panel.style.top = t + 'px'; panel.style.maxHeight = `calc(100% - ${t + 90}px)`;
}
$('gear').onclick = () => { placeSettings(); panel.hidden = !panel.hidden; $('gear').setAttribute('aria-expanded', String(!panel.hidden)); };
new ResizeObserver(placeSettings).observe($('topbar'));
fillInputs();
$('expand').onclick = () => Object.values(boxes).forEach(b => { b.classList.add('open'); b.querySelectorAll('.fr').forEach(f => f.classList.remove('closed')); });
$('collapse').onclick = () => Object.values(boxes).forEach(b => { b.classList.remove('open'); b.querySelectorAll('.fr').forEach(f => f.classList.add('closed')); });
let centerGoal = null;
$('center').onclick = () => { if (selEcu) centerGoal = ecuObj[selEcu].mesh.position.clone(); };
$('reset').onclick = () => { camera.position.set(...CFG.cam); controls.target.set(0, (CFG.zone.y[0] + CFG.zone.y[1]) / 2, 0); controls.update(); };
$('hide').onclick = e => { vehicleGroup.visible = !vehicleGroup.visible; e.target.textContent = vehicleGroup.visible ? 'Hide vehicle' : 'Show vehicle'; };
$('relayout').onclick = () => { D.ecus.forEach(n => ecuObj[n].mesh.position.copy(ecuObj[n].auto)); wires.forEach(layoutWire); setDirty(true); };
let showEcus = true, showWires = true, locked = false;
try { locked = localStorage.getItem('va-locked') === '1'; } catch (_) {}
const syncWires = () => { wires.forEach(w => { w.mesh.visible = w.label.visible = showWires; }); moving.forEach(m => { m.mesh.visible = showWires; }); };
$('hideecu').onclick = e => { showEcus = !showEcus; Object.values(ecuObj).forEach(o => { o.mesh.visible = showEcus; }); e.target.textContent = showEcus ? 'Hide ECUs' : 'Show ECUs'; syncGizmo(); };
$('hidewire').onclick = e => { showWires = !showWires; syncWires(); e.target.textContent = showWires ? 'Hide wiring' : 'Show wiring'; };
function syncLock() {
  $('lock').textContent = locked ? 'Unlock ECUs' : 'Lock ECUs'; $('relayout').disabled = $('load').disabled = locked; syncGizmo();
  try { localStorage.setItem('va-locked', locked ? '1' : '0'); } catch (_) {}
}
$('lock').onclick = () => { locked = !locked; syncLock(); }; syncLock();

/* ---------- loop ---------- */
function resize() { const w = host.clientWidth, h = host.clientHeight; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }
addEventListener('resize', resize); new ResizeObserver(resize).observe(host); resize();
/* keep text from overlapping: place ECU names first, then wire labels, nudging each label up/down on screen until it is clear */
const camUp = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();
function declutter() {
  const W = host.clientWidth, Hh = host.clientHeight; if (!W || !Hh) return;
  const k = 2 * Math.tan(camera.fov * Math.PI / 360) / Hh;  // world units per pixel = k * distance
  camUp.set(0, 1, 0).applyQuaternion(camera.quaternion);
  const placed = [];
  const rect = (pos, sp) => {
    tmp.copy(pos).project(camera); if (tmp.z > 1) return null;
    const u = k * camera.position.distanceTo(pos);
    return {x: (tmp.x + 1) / 2 * W, y: (1 - tmp.y) / 2 * Hh, w: sp.scale.x / u * .75, h: sp.scale.y / u * .5, u};
  };
  const hit = (r, q) => Math.abs(r.x - q.x) < (r.w + q.w) / 2 && Math.abs(r.y - q.y) < (r.h + q.h) / 2;
  if (showEcus) Object.values(ecuObj).forEach(o => {
    const r = rect(tmp2.copy(o.mesh.position).add(o.tag.position), o.tag); if (r) placed.push(r);
  });
  const order = [...wires.values()].filter(w => w.label.visible).sort((a, b) => b.label.material.opacity - a.label.material.opacity);
  order.forEach(w => {
    let r = rect(w.base, w.label); if (!r) { w.label.position.copy(w.base); return; }
    let best = 0;
    for (let i = 0; i < 17; i++) {
      const step = i % 2 ? (i + 1) / 2 : -i / 2;  // 0, 1, -1, 2, -2 ...
      const c = {...r, y: r.y - step * r.h * 1.1};
      if (!placed.some(q => hit(c, q))) { best = step; break; }
    }
    w.label.position.copy(w.base).addScaledVector(camUp, best * r.h * 1.1 * r.u);
    placed.push({...r, y: r.y - best * r.h * 1.1});
  });
}
const clock = new THREE.Clock();
(function loop() {
  requestAnimationFrame(loop);
  const t = clock.getElapsedTime() * .45;
  moving.forEach(m => { let u = (t + m.t0) % 1; if (m.dir < 0) u = 1 - u; m.mesh.position.copy(m.curve.getPoint(u)); });
  if (centerGoal) {  // glide the view so the selected ECU is in the middle, keeping the zoom and angle
    const d = tmp.copy(centerGoal).sub(controls.target);
    if (d.length() < .002) centerGoal = null; else { d.multiplyScalar(.15); controls.target.add(d); camera.position.add(d); }
  }
  if (gizmo.visible && selEcu) { const p = ecuObj[selEcu].mesh.position; gizmo.position.copy(p); gizmo.scale.setScalar(camera.position.distanceTo(p) * .12); }
  controls.update(); declutter(); renderer.render(scene, camera);
})();
</script></body></html>
"""

if __name__ == "__main__":
    main()
