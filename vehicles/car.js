VEHICLES.car = {
  zone: {x: [-1.7, 1.7], y: [0.55, 1.1], z: 0.55},
  s: 0.45,
  cam: [6, 3.5, 6],
  gy: 0,

  build({THREE, part, B, C, H}) {

    // =================================
    // MAIN AERODYNAMIC BODY
    // =================================

    part(B(4.65, .42, 1.95), 0, .62, 0);
    part(B(4.35, .13, 2.0), 0, .88, 0);

    // Front aerodynamic hood
    part(B(1.55, .12, 1.85), 1.42, .91, 0);
    part(B(1.0, .08, 1.7), 1.75, .96, 0);

    // Rear body
    part(B(1.25, .17, 1.9), -1.65, .88, 0);

    // Front splitter
    part(B(.25, .07, 2.05), 2.28, .37, 0, [0, 0, 0], 'mech');

    // Rear diffuser
    part(B(.35, .12, 1.75), -2.22, .36, 0, [0, 0, 0], 'mech');

    // =================================
    // FUTURISTIC CABIN
    // =================================

    part(B(2.35, .55, 1.57), -.25, 1.25, 0);

    // Panoramic glass roof
    part(B(1.55, .09, 1.53), -.30, 1.56, 0, [0, 0, 0], 'acc');

    // Front windshield
    part(B(.08, .43, 1.50), .90, 1.34, 0, [0, 0, -.24], 'acc');

    // Rear windshield
    part(B(.08, .40, 1.48), -1.42, 1.32, 0, [0, 0, .24], 'acc');

    // Side windows
    for (const z of [-.80, .80]) {
      part(B(1.65, .31, .035), -.27, 1.34, z, [0, 0, 0], 'acc');

      // Window pillars
      part(B(.06, .42, .07), -.27, 1.36, z, [0, 0, 0], 'mech');
    }

    // =================================
    // FRONT LIGHTING
    // =================================

    // Slim futuristic headlights
    for (const z of [-.68, .68]) {

      part(B(.10, .09, .48), 2.27, .79, z, [0, 0, 0], 'acc');

      // LED strips
      part(B(.11, .025, .38), 2.32, .82, z, [0, 0, 0], 'acc');
    }

    // Front air intake
    part(B(.08, .20, 1.0), 2.29, .55, 0, [0, 0, 0], 'acc');

    // Lower grille
    part(B(.10, .09, 1.25), 2.34, .43, 0, [0, 0, 0], 'mech');

    // Hood detailing
    for (const z of [-.48, .48]) {
      part(B(1.0, .025, .035), 1.45, .99, z, [0, 0, 0], 'mech');
    }

    // =================================
    // SIDE BODY DETAILS
    // =================================

    for (const z of [-.99, .99]) {

      // Side skirts
      part(B(2.65, .11, .12), 0, .38, z, [0, 0, 0], 'mech');

      // Door sculpting
      part(B(1.35, .025, .035), -.30, .70, z, [0, 0, 0], 'mech');

      // Flush door handles
      part(B(.24, .035, .035), -.65, .99, z, [0, 0, 0], 'mech');

      // Side air vents
      part(B(.42, .12, .035), -1.12, .65, z, [0, 0, 0], 'mech');

      // Aerodynamic mirrors
      part(B(.22, .08, .15), .72, 1.27, z, [0, 0, 0], 'mech');
      part(B(.18, .11, .18), .77, 1.31, z, [0, 0, 0], 'acc');

    }

    // =================================
    // MODERN REAR LIGHT BAR
    // =================================

    // Full-width rear LED
    part(B(.10, .10, 1.55), -2.30, .83, 0, [0, 0, 0], 'acc');

    // Rear corner lights
    for (const z of [-.78, .78]) {
      part(B(.10, .14, .30), -2.30, .83, z, [0, 0, 0], 'acc');
    }

    // Rear bumper
    part(B(.18, .16, 1.95), -2.27, .40, 0, [0, 0, 0], 'mech');

    // Rear diffuser fins
    for (const z of [-.55, -.27, 0, .27, .55]) {
      part(B(.38, .15, .045), -2.12, .32, z, [0, 0, 0], 'mech');
    }

    // =================================
    // SPORT SPOILER
    // =================================

    for (const z of [-.57, .57]) {
      part(B(.12, .22, .12), -1.92, 1.05, z, [0, 0, 0], 'mech');
    }

    part(B(.30, .07, 1.55), -1.95, 1.18, 0, [0, 0, 0], 'mech');

    // =================================
    // PREMIUM ALLOY WHEELS
    // =================================

    for (const x of [-1.43, 1.43]) {
      for (const z of [-1.0, 1.0]) {

        // Tires
        part(C(.40, .28), x, .38, z, [H, 0, 0], 'mech');

        // Alloy rims
        part(C(.28, .30), x, .38, z * 1.06, [H, 0, 0], 'acc');

        // Center hub
        part(C(.10, .32), x, .38, z * 1.12, [H, 0, 0], 'mech');

        // Five-spoke wheel detailing
        for (let i = 0; i < 5; i++) {

          const a = i * Math.PI * 2 / 5;

          part(
            B(.20, .035, .045),
            x + Math.cos(a) * .13,
            .38 + Math.sin(a) * .13,
            z * 1.13,
            [0, 0, a],
            'mech'
          );
        }

        // Brake disc
        part(C(.20, .025), x, .38, z * 1.04, [H, 0, 0], 'mech');

      }
    }

    // =================================
    // LUXURY INTERIOR
    // =================================

    for (const z of [-.42, .42]) {

      // Sport seats
      part(B(.40, .40, .38), -.15, 1.03, z, [0, 0, 0], 'int');

      // Seat backs
      part(B(.18, .42, .38), -.30, 1.29, z, [0, 0, 0], 'int');

    }

    // Dashboard
    part(B(.25, .16, 1.38), .67, 1.03, 0, [0, 0, 0], 'int');

    // Center console
    part(B(.72, .10, .27), -.02, .99, 0, [0, 0, 0], 'int');

    // Steering wheel
    part(C(.13, .035), .52, 1.14, -.40, [H, 0, 0], 'int');

    // =================================
    // EXHAUST / REAR DETAILS
    // =================================

    for (const z of [-.60, .60]) {
      part(C(.10, .16), -2.36, .43, z, [H, 0, 0], 'mech');
    }

  }
};
