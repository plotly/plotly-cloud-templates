import aerosandbox as asb
import aerosandbox.numpy as np

e216 = asb.Airfoil("e216")
naca0008 = asb.Airfoil("naca0008")

# Lateral boom position for each boom count, as a fraction of the half-span
BOOM_LOCATIONS = {1: [0], 2: [-0.40, 0.40], 3: [-0.57, 0, 0.57]}


def make_airplane(n_booms, wing_span):
    # Wing
    wing_root_chord = 2.316
    wing_x_quarter_chord = -0.1

    # Horizontal stabilizer
    hstab_span = 2.867
    hstab_chord = 1.085
    hstab_twist = -3

    # Vertical stabilizer
    vstab_span = 2.397
    vstab_chord = 1.134

    # Fuselage
    boom_length = 6.181
    nose_length = 1.5
    fuse_diameter = 0.6
    boom_diameter = 0.2

    wing = asb.Wing(
        name="Main Wing",
        symmetric=True,
        xsecs=[
            asb.WingXSec(  # Root
                xyz_le=[wing_x_quarter_chord - wing_root_chord / 4, 0, 0],
                chord=wing_root_chord,
                airfoil=e216,
            ),
            asb.WingXSec(  # Tip
                xyz_le=[wing_x_quarter_chord - wing_root_chord * 0.5 / 4, wing_span / 2, 0],
                chord=wing_root_chord * 0.5,
                airfoil=e216,
            ),
        ],
    )

    hstab_x_le = boom_length - vstab_chord * 0.75 - hstab_chord
    hstab = asb.Wing(
        name="Horizontal Stabilizer",
        symmetric=True,
        xsecs=[
            asb.WingXSec(
                xyz_le=[hstab_x_le, 0, 0.1],
                chord=hstab_chord,
                twist=hstab_twist,
                airfoil=naca0008,
            ),
            asb.WingXSec(
                xyz_le=[hstab_x_le, hstab_span / 2, 0.1],
                chord=hstab_chord,
                twist=hstab_twist,
                airfoil=naca0008,
            ),
        ],
    )

    vstab_x_le = boom_length - vstab_chord * 0.75
    vstab_z_le = -vstab_span / 2 + vstab_span * 0.15
    vstab = asb.Wing(
        name="Vertical Stabilizer",
        symmetric=False,
        xsecs=[
            asb.WingXSec(
                xyz_le=[vstab_x_le, 0, vstab_z_le],
                chord=vstab_chord,
                airfoil=naca0008,
            ),
            asb.WingXSec(
                xyz_le=[vstab_x_le, 0, vstab_z_le + vstab_span],
                chord=vstab_chord,
                airfoil=naca0008,
            ),
        ],
    )

    # Fuselage: rounded nose, taper down to the boom diameter, then a straight boom
    def blend(x):
        return (1 - np.cos(np.pi * x)) / 2

    resolution = 10
    theta = np.linspace(0, np.pi / 2, resolution)
    taper = np.linspace(0, 1, resolution)
    straight = np.linspace(0, 1, 4)[1:]

    fuse_x = np.concatenate(
        [
            (wing_x_quarter_chord - wing_root_chord / 4) - nose_length * np.cos(theta),
            0.6 * boom_length * taper,
            0.6 * boom_length + 0.4 * boom_length * straight,
        ]
    )
    fuse_z = np.concatenate(
        [
            np.full(resolution, -fuse_diameter / 2),
            -fuse_diameter / 2 * blend(1 - taper) - boom_diameter / 2 * blend(taper),
            np.full(len(straight), -boom_diameter / 2),
        ]
    )
    fuse_r = np.concatenate(
        [
            fuse_diameter / 2 * np.sin(theta),
            fuse_diameter / 2 * blend(1 - taper) + boom_diameter / 2 * blend(taper),
            np.full(len(straight), boom_diameter / 2),
        ]
    )

    if n_booms not in BOOM_LOCATIONS:
        raise ValueError("n_booms must be 1, 2 or 3")

    fuselages, hstabs, vstabs = [], [], []
    for fraction in BOOM_LOCATIONS[n_booms]:
        dy = wing_span / 2 * fraction
        fuselages.append(
            asb.Fuselage(
                name="Fuselage",
                xsecs=[
                    asb.FuselageXSec(xyz_c=[x, dy, z], radius=r)
                    for x, z, r in zip(fuse_x, fuse_z, fuse_r)
                ],
            )
        )
        hstabs.append(hstab.translate([0, dy, 0]))
        vstabs.append(vstab.translate([0, dy, 0]))

    return asb.Airplane(
        name="Solar1",
        xyz_ref=[0, 0, 0],
        wings=[wing] + hstabs + vstabs,
        fuselages=fuselages,
    )
