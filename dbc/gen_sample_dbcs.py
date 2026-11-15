#!/usr/bin/env python3
"""Generate sample DBC files with hundreds of signals for vehicle_anatomy.py.

Usage:
    python gen_sample_dbcs.py [output_dir] [--seed N]

Writes one .dbc per bus. Gateway and shared ECUs (GW_CENTRAL, VCU, EPS, ADAS_DOM)
appear in several files, so they link the buses together in the 3D view.
File names carry the bus type (..._canfd, ..._can, ..._eth), which the viewer uses
to guess the type and to draw ETH wires thicker.
"""
import random
import sys
from pathlib import Path

# kind -> (bit length, factor, offset, unit)
KINDS = {
    "flag": (1, 1, 0, ""), "state": (4, 1, 0, ""), "cnt": (8, 1, 0, ""),
    "pct": (8, 0.4, 0, "%"), "temp": (8, 1, -40, "degC"), "speed": (16, 0.01, 0, "km/h"),
    "rpm": (16, 0.25, 0, "rpm"), "volt": (16, 0.01, 0, "V"), "amp": (16, 0.1, -1000, "A"),
    "torque": (16, 0.5, -500, "Nm"), "pres": (16, 0.1, 0, "kPa"), "angle": (16, 0.1, -1000, "deg"),
    "dist": (16, 0.01, 0, "m"), "accel": (12, 0.05, -100, "m/s2"), "time": (16, 0.1, 0, "s"),
    "freq": (16, 0.1, 0, "Hz"), "energy": (16, 0.1, 0, "kWh"),
}
NUMERIC_QUALIFIERS = ["", "_Max", "_Min", "_Avg", "_Raw"]


def seq(prefix, kind, n):
    return [(f"{prefix}{i}", kind) for i in range(1, n + 1)]


def obj_pool(n):
    out = []
    for i in range(1, n + 1):
        out += [(f"Obj{i}Dist", "dist"), (f"Obj{i}Speed", "speed"), (f"Obj{i}Angle", "angle"), (f"Obj{i}Conf", "pct")]
    return out


def door(side):
    return [("DoorOpen", "flag"), ("DoorLocked", "flag"), ("WindowPos", "pct"), ("WindowMotorCurrent", "amp"),
            ("MirrorFoldCmd", "flag"), ("MirrorPosH", "angle"), ("MirrorPosV", "angle"), ("DoorHandleTouch", "flag"),
            ("WindowPinch", "flag"), ("MirrorHeat", "flag"), ("LatchState", "state"), ("CourtesyLight", "flag")]


POOLS = {
    "ECM": [("EngineSpeed", "rpm"), ("EngineTorque", "torque"), ("ThrottlePos", "pct"), ("FuelRate", "pct"),
            ("CoolantTemp", "temp"), ("OilTemp", "temp"), ("OilPressure", "pres"), ("IntakeTemp", "temp"),
            ("ManifoldPressure", "pres"), ("Lambda", "pct"), ("KnockLevel", "pct"), ("EngineRunning", "flag"),
            ("EngineState", "state"), ("StartStopReq", "flag"), ("FuelLevel", "pct"), ("ExhaustTemp", "temp"),
            ("TurboSpeed", "rpm"), ("BoostPressure", "pres")],
    "TCM": [("GearActual", "state"), ("GearTarget", "state"), ("ClutchPressure", "pres"), ("TransOilTemp", "temp"),
            ("OutputShaftSpeed", "rpm"), ("InputShaftSpeed", "rpm"), ("ShiftInProgress", "flag"),
            ("TorqueConverterLock", "flag"), ("DriveMode", "state"), ("LaunchControl", "flag"), ("TransFault", "flag"),
            ("PumpPressure", "pres")],
    "BMS": [("PackVoltage", "volt"), ("PackCurrent", "amp"), ("SOC", "pct"), ("SOH", "pct"), ("CellVoltage", "volt"),
            ("CellTemp", "temp"), ("ContactorState", "state"), ("IsolationFault", "flag"), ("ChargeState", "state"),
            ("PreChargeActive", "flag"), ("CoolantPumpCmd", "pct"), ("CellBalanceActive", "flag"), ("PackPower", "energy"),
            ("ChargePowerLimit", "energy"), ("DischargePowerLimit", "energy")],
    "INV": [("MotorSpeed", "rpm"), ("MotorTorque", "torque"), ("MotorTemp", "temp"), ("InverterTemp", "temp"),
            ("DCLinkVoltage", "volt"), ("PhaseCurrentU", "amp"), ("PhaseCurrentV", "amp"), ("PhaseCurrentW", "amp"),
            ("InverterState", "state"), ("TorqueLimit", "torque"), ("RegenLevel", "pct"), ("DerateActive", "flag")],
    "VCU": [("VehicleSpeed", "speed"), ("TorqueRequest", "torque"), ("DriveState", "state"), ("PedalPos", "pct"),
            ("BrakePedalPos", "pct"), ("ReadyToDrive", "flag"), ("PowerLimit", "energy"), ("EcoMode", "flag"),
            ("SportMode", "flag"), ("ThermalReq", "pct"), ("KeyState", "state"), ("CruiseSet", "speed"),
            ("CruiseActive", "flag"), ("TorqueSplit", "pct")],
    "GW_CENTRAL": [("GatewayState", "state"), ("BusLoad", "pct"), ("SleepRequest", "flag"), ("WakeSource", "state"),
                   ("TimeSync", "time"), ("DiagSessionActive", "flag"), ("NetworkMgmtState", "state"),
                   ("OTAActive", "flag"), ("ErrorCounter", "cnt"), ("RoutedFrameCount", "cnt"), ("GatewayTemp", "temp"),
                   ("VoltageSupply", "volt")],
    "ABS": [("WheelSpeedFL", "speed"), ("WheelSpeedFR", "speed"), ("WheelSpeedRL", "speed"), ("WheelSpeedRR", "speed"),
            ("ABSActive", "flag"), ("BrakePressure", "pres"), ("VehicleSpeedEst", "speed"), ("YawRate", "angle"),
            ("LongAccel", "accel"), ("LatAccel", "accel"), ("BrakeLightReq", "flag"), ("ABSFault", "flag"),
            ("WheelPulseFL", "cnt"), ("WheelPulseFR", "cnt")],
    "ESC": [("ESCActive", "flag"), ("TractionControl", "flag"), ("SteeringAngle", "angle"), ("YawRateRef", "angle"),
            ("SlipAngle", "angle"), ("StabilityState", "state"), ("HillHoldActive", "flag"), ("TorqueIntervention", "torque"),
            ("BrakeIntervention", "pct"), ("RollRate", "angle"), ("ESCFault", "flag")],
    "EPS": [("SteerTorque", "torque"), ("SteerAngleAct", "angle"), ("SteerAngleReq", "angle"), ("AssistLevel", "pct"),
            ("MotorTemp", "temp"), ("MotorCurrent", "amp"), ("EPSState", "state"), ("LKAActive", "flag"),
            ("SteerFault", "flag"), ("ColumnTorque", "torque")],
    "SUSP": [("RideHeightFL", "dist"), ("RideHeightFR", "dist"), ("RideHeightRL", "dist"), ("RideHeightRR", "dist"),
             ("DamperMode", "state"), ("AirPressure", "pres"), ("CompressorOn", "flag"), ("SuspState", "state"),
             ("BodyAccelZ", "accel"), ("LevelRequest", "pct")],
    "BCM": [("IgnitionState", "state"), ("DoorLockCmd", "flag"), ("WiperState", "state"), ("WiperSpeed", "state"),
            ("TurnSignalL", "flag"), ("TurnSignalR", "flag"), ("HazardActive", "flag"), ("HornCmd", "flag"),
            ("InteriorLight", "pct"), ("BatteryVoltage", "volt"), ("AlarmState", "state"), ("RainSensor", "pct"),
            ("LightSensor", "pct"), ("KeyFobBattery", "pct"), ("TrunkOpen", "flag"), ("HoodOpen", "flag")],
    "DOOR_FL": door("FL"), "DOOR_FR": door("FR"), "DOOR_RL": door("RL"), "DOOR_RR": door("RR"),
    "SEAT_DRV": [("SeatPosFwd", "dist"), ("SeatPosHeight", "dist"), ("BackrestAngle", "angle"), ("LumbarPct", "pct"),
                 ("SeatHeatLevel", "state"), ("SeatVentLevel", "state"), ("SeatBeltBuckled", "flag"),
                 ("OccupantPresent", "flag"), ("MemorySlot", "state"), ("SeatMotorCurrent", "amp")],
    "HVAC": [("CabinTemp", "temp"), ("SetTempL", "temp"), ("SetTempR", "temp"), ("BlowerSpeed", "pct"),
             ("CompressorSpeed", "rpm"), ("RefrigPressure", "pres"), ("AirRecirc", "flag"), ("DefrostActive", "flag"),
             ("ACActive", "flag"), ("VentMode", "state"), ("AmbientTemp", "temp"), ("EvapTemp", "temp"),
             ("HeaterPower", "pct"), ("SunLoad", "pct")],
    "LIGHT_F": [("LowBeam", "flag"), ("HighBeam", "flag"), ("DRL", "flag"), ("FogLamp", "flag"),
                ("AdaptiveAngle", "angle"), ("LevelingPos", "angle"), ("LampFault", "flag"), ("HeadlampTemp", "temp"),
                ("CornerLight", "flag"), ("MatrixSegment", "state")],
    "LIGHT_R": [("TailLight", "flag"), ("BrakeLight", "flag"), ("ReverseLight", "flag"), ("FogRear", "flag"),
                ("TurnRearL", "flag"), ("TurnRearR", "flag"), ("LampFaultRear", "flag"), ("PlateLight", "flag"),
                ("TailLampTemp", "temp")],
    "ADAS_DOM": [("ADASState", "state"), ("ACCActive", "flag"), ("ACCSetSpeed", "speed"), ("TargetDistance", "dist"),
                 ("TargetSpeedRel", "speed"), ("LKAReq", "flag"), ("AEBReq", "flag"), ("AEBDecel", "accel"),
                 ("SteerCmd", "angle"), ("DriverAttention", "pct"), ("HandsOnWheel", "flag"), ("LaneChangeAssist", "state"),
                 ("TrafficSign", "state"), ("SpeedLimit", "speed"), ("ObjectCount", "cnt"), ("FusionConfidence", "pct"),
                 ("EgoLanePos", "dist")],
    "RADAR_F": obj_pool(5) + [("RadarState", "state"), ("RadarTemp", "temp"), ("Blind", "flag"), ("ObjCount", "cnt")],
    "RADAR_RL": obj_pool(3) + [("RadarState", "state"), ("RadarTemp", "temp"), ("BlindSpot", "flag"), ("ObjCount", "cnt")],
    "RADAR_RR": obj_pool(3) + [("RadarState", "state"), ("RadarTemp", "temp"), ("BlindSpot", "flag"), ("ObjCount", "cnt")],
    "CAM_F": [("LaneLeftOffset", "dist"), ("LaneRightOffset", "dist"), ("LaneCurvature", "angle"), ("LaneConfidence", "pct"),
              ("SignClass", "state"), ("TrafficLight", "state"), ("PedestrianDetected", "flag"), ("VehicleCount", "cnt"),
              ("HighBeamAssist", "flag"), ("CamTemp", "temp"), ("Blockage", "flag"), ("ExposureLevel", "pct")],
    "LIDAR": [("PointCount", "cnt"), ("FreeSpaceFront", "dist"), ("FreeSpaceLeft", "dist"), ("FreeSpaceRight", "dist"),
              ("ScanRate", "freq"), ("LidarTemp", "temp"), ("LidarMotorSpeed", "rpm"), ("LidarBlockage", "flag")],
    "PARK_ASSIST": seq("Ultrasonic", "dist", 8) + [("ParkState", "state"), ("AutoParkActive", "flag"), ("SteerReq", "angle"),
                                                    ("ParkSpeedLimit", "speed")],
    "HEAD_UNIT": [("Volume", "pct"), ("Source", "state"), ("NavActive", "flag"), ("PhoneConnected", "flag"),
                  ("Brightness", "pct"), ("ScreenTemp", "temp"), ("VoiceActive", "flag"), ("ClimateTouchReq", "state"),
                  ("CameraView", "state"), ("MediaPos", "time")],
    "CLUSTER": [("DisplayMode", "state"), ("ClusterBrightness", "pct"), ("TripDist", "dist"), ("RangeEst", "dist"),
                ("UnitsMetric", "flag"), ("WarningLampBrake", "flag"), ("WarningLampABS", "flag"), ("WarningLampEng", "flag"),
                ("WarningLampBatt", "flag"), ("WarningLampAirbag", "flag"), ("ThemeId", "state"), ("GaugeNeedle", "angle")],
    "TCU": [("SignalStrength", "pct"), ("CellularState", "state"), ("GNSSFix", "state"), ("Latitude", "angle"),
            ("Longitude", "angle"), ("GNSSSpeed", "speed"), ("EcallState", "state"), ("OTAProgress", "pct"),
            ("WifiState", "state"), ("DataRate", "freq")],
    "AMP": [("AmpTemp", "temp"), ("OutputPower", "pct"), ("Mute", "flag"), ("EQPreset", "state"),
            ("SpeakerFault", "flag"), ("ChannelLevel", "pct"), ("BassLevel", "pct"), ("TrebleLevel", "pct")],
    "NAV": [("RouteActive", "flag"), ("DistToTurn", "dist"), ("NextManeuver", "state"), ("SpeedLimitMap", "speed"),
            ("RoadClass", "state"), ("ETA", "time"), ("GPSAccuracy", "dist"), ("CurvatureAhead", "angle"),
            ("SlopeAhead", "angle")],
}

# file name (= bus name), BusType attribute (None = let the viewer guess from the name), frame size, ECUs on the bus
BUSES = [
    ("powertrain_canfd", "CAN FD", 64, ["ECM", "TCM", "BMS", "INV", "VCU", "GW_CENTRAL"]),
    ("chassis_can", "CAN", 8, ["ABS", "ESC", "EPS", "SUSP", "VCU", "GW_CENTRAL"]),
    ("body_can", "CAN", 8, ["BCM", "DOOR_FL", "DOOR_FR", "DOOR_RL", "DOOR_RR", "SEAT_DRV", "HVAC", "LIGHT_F", "LIGHT_R",
                           "GW_CENTRAL"]),
    ("adas_canfd", "CAN FD", 64, ["ADAS_DOM", "RADAR_F", "RADAR_RL", "RADAR_RR", "CAM_F", "LIDAR", "PARK_ASSIST", "EPS",
                                  "GW_CENTRAL"]),
    ("infotainment_eth", None, 64, ["HEAD_UNIT", "CLUSTER", "TCU", "AMP", "NAV", "ADAS_DOM", "GW_CENTRAL"]),
]
TOPICS = ["Status", "Data", "Cmd", "Info", "Limits", "Monitor", "Req", "Diag"]


def pool_names(ecu):
    out = []
    for stem, kind in POOLS[ecu]:
        for q in (NUMERIC_QUALIFIERS if kind not in ("flag", "state", "cnt") else [""]):
            out.append((stem + q, kind))
    return out


def fmt(x):
    return f"{x:.6g}"


def build_bus(rng, name, btype, dlc, ecus):
    lines = ['VERSION ""', "", "NS_ :", "", "BS_:", "", "BU_: " + " ".join(ecus), ""]
    base = 0x1000 if name.endswith("_eth") else 0x100
    next_id = base
    n_sig = n_frames = 0
    for ecu in ecus:
        names = pool_names(ecu)
        rng.shuffle(names)
        pos = 0
        others = [e for e in ecus if e != ecu]
        for fi in range(rng.randint(3, 5)):
            topic = TOPICS[fi % len(TOPICS)]
            next_id += rng.randint(1, 8)
            mname = f"{ecu}_{topic}{fi + 1}"
            lines.append(f"BO_ {next_id} {mname}: {dlc} {ecu}")
            n_frames += 1
            main_rx = [r for r in others if r == "GW_CENTRAL" and rng.random() < .5]
            main_rx += rng.sample([r for r in others if r != "GW_CENTRAL"] or others, min(len(others), rng.randint(1, 3)))
            bit, used = 0, set()
            body = []
            budget = dlc * 8 - 12  # leave room for the alive counter and CRC
            while pos < len(names) and len(body) < rng.randint(6, 11):
                sname, kind = names[pos]
                length = KINDS[kind][0]
                if bit + length > budget:
                    break
                pos += 1
                if sname in used:
                    continue
                used.add(sname)
                rx = list(dict.fromkeys(rng.sample(others, rng.randint(1, min(3, len(others)))) + main_rx[:1]))
                body.append((sname, kind, bit, rx))
                bit += length
            body.append(("AliveCnt", "state", bit, main_rx))
            body.append(("Crc8", "cnt", bit + 4, main_rx))
            for sname, kind, start, rx in body:
                length, factor, offset, unit = KINDS[kind]
                lo, hi = offset, offset + factor * (2 ** length - 1)
                lines.append(f' SG_ {sname} : {start}|{length}@1+ ({fmt(factor)},{fmt(offset)}) '
                             f'[{fmt(lo)}|{fmt(hi)}] "{unit}" {",".join(rx)}')
                n_sig += 1
            lines.append("")
    if btype:
        lines.append(f'BA_ "BusType" "{btype}";')
    return "\n".join(lines) + "\n", n_frames, n_sig


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1
    if "--seed" in sys.argv:
        args = [a for a in args if a != str(seed)]
    out = Path(args[0] if args else "sample_dbcs")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    total = 0
    for name, btype, dlc, ecus in BUSES:
        text, nf, ns = build_bus(rng, name, btype, dlc, ecus)
        (out / f"{name}.dbc").write_text(text, encoding="latin-1")
        print(f"{name}.dbc: {len(ecus)} ECUs, {nf} frames, {ns} signals")
        total += ns
    print(f"total signals: {total}  ->  {out}/")


if __name__ == "__main__":
    main()
