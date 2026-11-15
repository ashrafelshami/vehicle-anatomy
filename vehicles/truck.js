VEHICLES.truck = {
    zone: { x: [-3.6, 3.0], y: [1.0, 2.5], z: 0.8 },
    s: 0.65,
    cam: [10, 5, 10],
    gy: 0,

    build({ THREE, part, B, C, H }) {

        const IN = 'int';
        const ME = 'mech';
        const AC = 'acc';

        // =========================================
        // MAIN CAB - VOLVO FH AERODYNAMIC DESIGN
        // =========================================

        const prof = new THREE.Shape([
            [-.25, 1.25],
            [3.05, 1.25],
            [3.22, 1.65],
            [3.22, 2.65],
            [3.08, 3.12],
            [2.65, 3.58],
            [2.35, 3.72],
            [.25, 3.72],
            [-.2, 3.58],
            [-.25, 3.2]
        ].map(([x, y]) => new THREE.Vector2(x, y)));

        const cab = new THREE.ExtrudeGeometry(prof, {
            depth: 2.45,
            bevelEnabled: true,
            bevelThickness: .09,
            bevelSize: .07,
            bevelSegments: 3,
            curveSegments: 4
        });

        cab.translate(0, 0, -1.225);
        part(cab);

        // Lower front cab panel
        part(B(.12, 1.05, 2.25), 3.15, 1.85, 0);

        // Front bumper
        part(B(.32, .32, 2.5), 3.25, .98, 0, null, ME);

        // Lower bumper lip
        part(B(.38, .09, 2.48), 3.35, .79, 0, null, ME);

        // =========================================
        // WINDSCREEN AND ROOF
        // =========================================

        // Large front windscreen
        part(
            B(.055, 1.05, 2.12),
            3.05, 2.85, 0,
            [0, 0, .22],
            AC
        );

        // Windscreen lower border
        part(B(.07, .08, 2.15), 3.17, 2.30, 0, null, ME);

        // Windscreen upper border
        part(B(.08, .09, 2.15), 2.82, 3.38, 0, null, ME);

        // Wipers
        for (const z of [-.48, .48]) {
            part(B(.035, .025, .78), 3.16, 2.25, z, [0, 0, -.12], ME);
        }

        // Roof cap
        part(B(2.05, .12, 2.28), 1.28, 3.70, 0, null, ME);

        // Sun visor
        part(B(.48, .09, 2.45), 3.02, 3.48, 0, [0, 0, -.15], ME);

        // Roof marker lights
        for (const z of [-.85, -.42, 0, .42, .85]) {
            part(C(.055, .06, 12), 3.08, 3.57, z, [H, 0, 0], AC);
        }

        // =========================================
        // VOLVO-STYLE FRONT GRILLE
        // =========================================

        // Main grille frame
        part(B(.09, .95, 1.48), 3.24, 1.72, 0, null, ME);

        // Grille opening
        part(B(.10, .78, 1.27), 3.30, 1.73, 0, null, AC);

        // Horizontal grille bars
        for (let i = 0; i < 6; i++) {
            part(B(.035, .035, 1.23), 3.37, 1.40 + i * .12, 0, null, ME);
        }

        // Volvo-inspired diagonal grille bar
        part(
            B(.045, 1.05, .075),
            3.40, 1.73, 0,
            [0, 0, .75],
            AC
        );

        // Circular central emblem
        part(C(.16, .035, 28), 3.42, 1.80, 0, [0, 0, H], AC);

        // =========================================
        // MODERN V-SHAPED HEADLIGHTS
        // =========================================

        for (const z of [-.94, .94]) {

            // Headlight housing
            part(B(.13, .35, .48), 3.19, 2.10, z, null, ME);

            // LED upper strip
            part(B(.07, .055, .43), 3.28, 2.23, z, null, AC);

            // LED vertical section
            part(B(.07, .28, .055), 3.29, 2.08, z, null, AC);

            // Lower fog lamps
            part(C(.09, .045, 16), 3.39, .96, z * .88, [0, 0, H], AC);

            // Front corner indicators
            part(B(.06, .12, .13), 3.28, 1.85, z * 1.08, null, AC);
        }

        // =========================================
        // SIDE WINDOWS AND DOORS
        // =========================================

        for (const z of [-1.245, 1.245]) {

            // Main side window
            part(B(1.15, .78, .035), 1.88, 3.03, z, null, AC);

            // Lower door window
            part(B(.65, .58, .035), .53, 2.98, z, null, AC);

            // Window pillars
            part(B(.08, .95, .07), 1.20, 3.00, z, null, ME);

            // Door panel
            part(B(1.25, 1.52, .06), 1.15, 2.05, z, null, ME);

            // Door handle
            part(B(.25, .055, .055), .75, 2.50, z * 1.03, null, AC);

            // Door seam
            part(B(.025, 1.4, .035), .25, 2.05, z * 1.03, null, ME);

            // Lower side step
            part(B(.80, .12, .40), 2.05, .76, z * 1.12, null, ME);

            // Upper step
            part(B(.80, .10, .36), 2.05, 1.00, z * 1.12, null, ME);

            // Step grip lines
            for (let i = 0; i < 4; i++) {
                part(B(.58, .018, .025), 2.05, .84 + i * .045, z * 1.19, null, AC);
            }

            // Side mirrors - upper arm
            part(B(.12, .13, .35), 2.85, 3.00, z * 1.27, null, ME);

            // Main mirror
            part(B(.20, .58, .30), 2.88, 2.73, z * 1.34, null, ME);

            // Mirror glass
            part(B(.035, .42, .23), 2.99, 2.75, z * 1.35, null, AC);

            // Lower wide-angle mirror
            part(B(.16, .22, .28), 2.88, 2.25, z * 1.32, null, ME);

            // Mirror indicator
            part(B(.035, .06, .16), 3.00, 2.54, z * 1.35, null, AC);

            // Side marker lights
            part(B(.06, .12, .12), 2.65, 1.15, z * 1.12, null, AC);

            // Wheel arch trim
            part(B(.12, .10, .85), 2.58, .73, z * 1.08, null, ME);
        }

        // =========================================
        // INTERIOR - DRIVER AND SLEEPER
        // =========================================

        // Floor
        part(B(3.0, .06, 2.25), 1.45, 1.35, 0, null, IN);

        // Dashboard
        part(B(.65, .42, 2.10), 2.75, 2.05, 0, null, IN);

        // Instrument cluster
        part(B(.10, .30, .55), 2.91, 2.38, -.52, null, AC);

        // Central infotainment screen
        part(B(.09, .34, .43), 2.93, 2.37, 0, null, AC);

        // Steering column
        part(B(.15, .35, .15), 2.45, 1.92, -.58, [0, 0, -.3], IN);

        // Steering wheel
        part(
            new THREE.TorusGeometry(.22, .035, 10, 24),
            2.35, 2.20, -.58,
            [0, H, 0],
            IN
        );

        // Driver seat
        part(B(.42, .45, .45), 1.65, 1.55, -.58, null, IN);
        part(B(.20, .85, .48), 1.40, 2.12, -.58, [0, 0, .10], IN);
        part(B(.28, .20, .48), 1.30, 2.67, -.58, null, IN);

        // Passenger seat
        part(B(.42, .45, .45), 1.65, 1.55, .58, null, IN);
        part(B(.20, .85, .48), 1.40, 2.12, .58, [0, 0, .10], IN);
        part(B(.28, .20, .48), 1.30, 2.67, .58, null, IN);

        // Gear selector
        part(B(.08, .32, .08), 2.15, 1.65, -.15, null, IN);
        part(C(.07, .08, 12), 2.15, 1.83, -.15, [H, 0, 0], IN);

        // Sleeper bunk
        part(B(1.20, .18, 1.95), .15, 2.0, 0, null, IN);
        part(B(1.05, .13, 1.85), .15, 2.12, 0, null, IN);

        // Storage compartments
        part(B(.90, .35, 1.95), .10, 3.05, 0, null, IN);

        // =========================================
        // LONG EUROPEAN TRUCK CHASSIS
        // =========================================

        // Two main frame rails
        for (const z of [-.58, .58]) {
            part(B(7.8, .20, .14), -.60, .95, z, null, ME);
        }

        // Cross members
        for (const x of [-4.0, -3.0, -1.8, -.5, .8, 2.0, 2.8]) {
            part(B(.14, .17, 1.25), x, .95, 0, null, ME);
        }

        // Engine block
        part(B(1.40, .65, 1.10), 2.25, 1.05, 0, null, ME);

        // Engine top
        part(B(1.0, .18, .85), 2.25, 1.48, 0, null, ME);

        // Transmission
        part(B(.75, .45, .72), .85, .80, 0, null, ME);

        // Driveshaft
        part(C(.075, 2.5, 12), -.75, .95, 0, [0, 0, H], ME);

        // Rear differential housings
        for (const x of [-2.5, -3.7]) {
            part(C(.28, .75, 16), x, .90, 0, [H, 0, 0], ME);
        }

        // =========================================
        // FUEL TANKS AND EXHAUST
        // =========================================

        for (const z of [-1.0, 1.0]) {

            // Aluminum fuel tanks
            part(C(.38, 1.25, 24), .20, .90, z, [H, 0, 0], ME);

            // Tank mounting bands
            for (const x of [-.25, .25]) {
                part(B(.08, .80, .48), x, .90, z, null, ME);
            }
        }

        // Exhaust stack
        part(C(.10, 2.6, 16), -.50, 2.10, 1.35, null, ME);

        // Exhaust outlet
        part(C(.13, .22, 16), -.50, 3.42, 1.35, null, ME);

        // Battery box
        part(B(.75, .55, .65), -1.30, .85, 1.0, null, ME);

        // AdBlue tank
        part(B(.60, .65, .55), -1.90, .85, 1.0, null, ME);

        // Air tanks
        for (const x of [-2.8, -3.5]) {
            part(C(.18, .90, 16), x, .85, .72, [H, 0, 0], ME);
        }

        // =========================================
        // FIFTH WHEEL
        // =========================================

        part(B(1.05, .14, 1.25), -2.90, 1.15, 0, null, ME);
        part(C(.55, .12, 24), -2.90, 1.25, 0, null, ME);

        // =========================================
        // AXLES AND REALISTIC WHEELS
        // =========================================

        const axles = [
            [2.60, [-1.15, 1.15]],
            [-2.50, [-1.30, -.95, .95, 1.30]],
            [-3.70, [-1.30, -.95, .95, 1.30]]
        ];

        for (const [x, zs] of axles) {

            // Axle
            part(C(.09, 2.9, 16), x, .55, 0, [H, 0, 0], ME);

            for (const z of zs) {

                // Tire
                part(C(.53, .34, 32), x, .55, z, [H, 0, 0]);

                // Rim
                part(C(.32, .36, 24), x, .55, z * 1.06, [H, 0, 0], ME);

                // Central hub
                part(C(.15, .39, 20), x, .55, z * 1.15, [H, 0, 0], AC);

                // Hub cap
                part(C(.09, .40, 16), x, .55, z * 1.18, [H, 0, 0], ME);

                // Wheel nuts
                for (let i = 0; i < 8; i++) {
                    const a = i * Math.PI * 2 / 8;

                    part(
                        C(.035, .045, 8),
                        x + Math.sin(a) * .23,
                        .55 + Math.cos(a) * .23,
                        z * 1.19,
                        [H, 0, 0],
                        AC
                    );
                }

            }
        }

        // =========================================
        // REAR LIGHTS AND MUDGUARDS
        // =========================================

        for (const z of [-1.15, 1.15]) {

            // Mudguards
            part(B(1.0, .12, .70), -3.10, 1.10, z, null, ME);
            part(B(1.0, .12, .70), -4.0, 1.10, z, null, ME);

            // Rear lamps
            part(B(.12, .40, .18), -4.05, 1.0, z, null, AC);
        }

        // Rear frame crossbar
        part(B(.15, .22, 2.3), -4.25, .85, 0, null, ME);

        // Rear underrun protection
        part(B(.15, .16, 2.45), -4.30, .55, 0, null, ME);

    }
};