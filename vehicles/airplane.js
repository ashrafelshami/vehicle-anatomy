// Airplane design. Nose is +x, up is +y, wings extend along z.
// part(geometry, x, y, z, [rotX, rotY, rotZ], kind)  kind: 'shell' (blue, default), 'int' (interior), 'mech' (mechanics), 'acc' (glass, lights)
VEHICLES.airplane = {
    zone: { x: [-7, 7], y: [-0.5, 0.6], z: 0.8 },  // box where ECUs are placed automatically
    s: 0.8,             // base ECU size
    cam: [22, 9, 22],   // starting camera position
    gy: -3,             // grid height
    build({ THREE, part, B, C, H }) {

        // ---------- helpers ----------
        // Swept wing/stabilizer planform: pts are [x, z] on the +z side, mirrored by s (+1 / -1). Thickness along y.
        const swept = (pts, t, s) => {
            const sh = new THREE.Shape();
            pts.forEach(([x, z], i) => (i ? sh.lineTo(x, -z * s) : sh.moveTo(x, -z * s)));
            const g = new THREE.ExtrudeGeometry(sh, { depth: t, bevelEnabled: false });
            g.rotateX(-H);
            g.translate(0, -t / 2, 0);
            return g;
        };
        // Vertical fin / winglet profile in the x-y plane, thickness along z.
        const fin = (pts, t) => {
            const sh = new THREE.Shape();
            pts.forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y)));
            const g = new THREE.ExtrudeGeometry(sh, { depth: t, bevelEnabled: false });
            g.translate(0, 0, -t / 2);
            return g;
        };
        const DIH = 0.06;        // wing dihedral
        const wingY = z => -0.8 + DIH * z;   // wing centre height at span z

        // ---------- fuselage ----------
        part(new THREE.CapsuleGeometry(1.4, 14, 8, 24), 0, 0, 0, [0, 0, H]);                 // main barrel + nose
        part(new THREE.ConeGeometry(1.38, 4.5, 28), -9.5, 0, 0, [0, 0, H]);                  // tapered tail cone
        part(new THREE.SphereGeometry(1, 24, 12).scale(3.4, 0.5, 1.5), 1, -1.25, 0);         // wing-root belly fairing

        // livery stripes
        for (const x of [-6.2, 5.2]) part(new THREE.TorusGeometry(1.41, 0.035, 8, 48), x, 0, 0, [0, H, 0], 'int');

        // ---------- cockpit & windows ----------
        for (const s of [-1, 1]) {
            part(B(0.12, 0.42, 0.72), 8.03, 0.64, 0.52 * s, [0, -0.46 * s, 0.5], 'acc');       // windshield
            part(B(0.5, 0.36, 0.06), 6.6, 0.62, 1.34 * s, [0, 0, 0], 'acc');                  // cockpit side window
            for (let x = -5.5; x <= 5.5; x += 1) part(B(0.4, 0.34, 0.08), x, 0.42, 1.36 * s, [0, 0, 0], 'acc'); // cabin windows
        }

        // ---------- cockpit interior ----------
        part(B(0.3, 0.4, 1.6), 7.3, -0.1, 0, [0, 0, 0], 'int');                              // dashboard
        for (const s of [-1, 1]) {
            part(B(0.5, 0.18, 0.5), 6.5, -0.55, 0.55 * s, [0, 0, 0], 'int');                  // seat
            part(B(0.12, 0.7, 0.5), 6.25, -0.2, 0.55 * s, [0, 0, -0.15], 'int');              // seat back
        }
        part(B(13, 0.08, 2.2), 0, -0.98, 0, [0, 0, 0], 'int');                                // cabin floor

        // ---------- wings ----------
        const wingPts = [[2.4, 0.6], [-1.4, 9], [-2.4, 9], [-2.6, 0.6]];
        const aileronZ = 6.4, flapZ = 2.35;
        part(B(0.4, 0.25, 16), 1.2, -0.95, 0, [0, 0, 0], 'mech');                             // main spar through fuselage
        for (const s of [-1, 1]) {
            part(swept(wingPts, 0.14, s), 1, -0.8, 0, [-DIH * s, 0, 0]);                      // wing
            // control surfaces (panel lines)
            part(B(0.6, 0.04, 3.2), -0.2, wingY(aileronZ) + 0.08, aileronZ * s, [-DIH * s, 0, 0], 'int');   // aileron
            part(B(0.8, 0.04, 2.1), -0.1, wingY(flapZ) + 0.08, flapZ * s, [-DIH * s, 0, 0], 'int');         // flap
            // winglet
            part(fin([[0.5, 0], [-0.5, 0], [-0.9, 1.0], [-0.3, 1.0]], 0.07), -0.9, wingY(9) - 0.05, 9.0 * s, [0, 0, 0]);
            // navigation light (red left / green right)
            part(new THREE.SphereGeometry(0.1, 12, 12), -0.9, wingY(9), 9.15 * s, [0, 0, 0], 'acc');
        }

        // ---------- tail ----------
        part(fin([[1.6, 0], [-1.8, 0], [-3.0, 3.4], [-1.6, 3.4]], 0.12), -8.4, 0.45, 0);      // vertical fin
        part(B(0.5, 0.05, 0.14), -10.0, 3.2, 0, [0, 0, 0], 'int');                           // rudder trim
        const stabPts = [[1.4, 0.3], [-0.6, 3.6], [-1.4, 3.6], [-1.5, 0.3]];
        for (const s of [-1, 1]) part(swept(stabPts, 0.09, s), -9.6, 0.0, 0, [-0.03 * s, 0, 0]); // horizontal stabilizers
        part(new THREE.SphereGeometry(0.09, 12, 12), -11.6, 0, 0, [0, 0, 0], 'acc');         // tail beacon

        // ---------- engines ----------
        for (const s of [-1, 1]) {
            const ez = 3.8 * s, ey = -1.45, ex = 3.0;
            part(B(1.8, 0.6, 0.22), ex - 0.3, -0.9, ez, [0, 0, 0]);                           // pylon
            part(new THREE.CylinderGeometry(0.62, 0.55, 3.2, 28), ex, ey, ez, [0, 0, -H]);    // nacelle
            part(new THREE.TorusGeometry(0.6, 0.07, 12, 36), ex + 1.6, ey, ez, [0, H, 0]);    // intake lip
            part(new THREE.CircleGeometry(0.54, 28), ex + 1.4, ey, ez, [0, H, 0], 'mech');    // fan face
            part(new THREE.ConeGeometry(0.18, 0.5, 16), ex + 1.55, ey, ez, [0, 0, -H], 'mech'); // spinner
            part(new THREE.ConeGeometry(0.4, 0.9, 20), ex - 2.05, ey, ez, [0, 0, H], 'mech'); // exhaust cone
        }

        // ---------- landing gear ----------
        for (const s of [-1, 1]) {                                                            // main gear
            part(new THREE.CylinderGeometry(0.07, 0.07, 1.6, 12), 0.8, -1.8, 1.0 * s, [0, 0, 0], 'mech');
            for (const dz of [-0.28, 0.28])
                part(new THREE.CylinderGeometry(0.45, 0.45, 0.3, 24), 0.8, -2.55, 1.0 * s + dz, [H, 0, 0], 'mech');
        }
        part(new THREE.CylinderGeometry(0.06, 0.06, 1.1, 12), 6, -1.95, 0, [0, 0, 0], 'mech'); // nose gear strut
        for (const dz of [-0.2, 0.2])
            part(new THREE.CylinderGeometry(0.4, 0.4, 0.22, 24), 6, -2.6, dz, [H, 0, 0], 'mech');
    }
};