# Wamoduck

**A 15-DOF duck robot by Wamotech.**

English | [简体中文](README.zh-CN.md)

![Wamoduck robot model in its saved CAD pose](assets/wamoduck-model.png)

*Model rendering from the Wamoduck URDF; this is not a photograph.*

Wamoduck is a duck-shaped biped robot project for exploring mechanical design, articulated motion, and robot modeling. Its 15 rotational degrees of freedom cover two five-joint legs and a five-joint neck, head, and beak chain.

This initial package shares simplified mechanical designs and a robot description for inspection and further development. A complete build guide, electronics, firmware, and walking controller are still to be documented or released.

## Start here

| I want to… | Open |
| --- | --- |
| Inspect or adapt individual mechanical parts | [20 STEP models](hardware/step/) · [Mechanical guide](docs/mechanical.en.md) |
| Explore the native assembly | [SolidWorks files](hardware/solidworks/) · [Opening instructions](docs/mechanical.en.md#solidworks-assembly) |
| View the robot and inspect its joints | [URDF and meshes](models/wmduck/) · [Model guide](docs/model.en.md) |
| Understand the modeled components | [Component inventory](docs/components.md) |
| Help improve the project | [Contributing](CONTRIBUTING.md) · [Roadmap](docs/roadmap.md) |

Download or clone the complete repository before opening an assembly or URDF. Those files need the parts or meshes supplied alongside them.

## At a glance

| Item | Current model |
| --- | --- |
| Rotational joints | 15: left leg 5 + right leg 5 + neck/head/beak 5 |
| Robot description | URDF; 16 mechanical links + 1 fixed IMU reference link |
| Geometry | 20 simplified STEP part models; 20 STL meshes for the URDF |
| Approximate model envelope at the saved pose | 181.5 × 221.2 × 390.8 mm (X × Y × Z) |
| Estimated model mass | 3.886 kg; CAD values with motor mass overrides, not a measured robot weight |
| Model units | m, kg, rad; STEP files declare mm |

The mass and envelope describe the supplied model, not certified hardware specifications. See the [model assumptions](docs/model.en.md) before using its inertias, motor values, or joint ranges.

## What is included

```text
Wamoduck/
├── hardware/
│   ├── step/             # Individual simplified parts, millimeters
│   └── solidworks/       # Simplified native parts and assemblies
├── models/wmduck/        # URDF, meshes, joint data, and import checks
├── assets/              # Model preview
├── docs/                # Bilingual mechanical and model guides
├── CONTRIBUTING.md
└── LICENSE
```

The STEP files support geometry exchange. The STL files are robot visualization and initial collision meshes, **not a validated set of printable parts**. Joint limits are estimates from single-joint geometry checks and do not guarantee collision-free combined motion.

For physical reproduction, the project still needs a verified procurement BOM, manufacturing specifications, assembly instructions, wiring, calibration, and control software. The [roadmap](docs/roadmap.md) tracks these gaps explicitly.

## References and license

The documentation structure draws on [Open Duck Mini](https://github.com/apirrone/Open_Duck_Mini) and [Pollen Robotics Microduck](https://github.com/pollen-robotics/microduck): accessible design files, clear model assumptions, and separate build/runtime/training instructions. See [references and scope](docs/references.md) for the exact sources and distinctions.

This repository retains its existing [MIT license](LICENSE), copyright © 2026 Wamotech. Referenced projects and third-party components retain their own licenses and rights. Their dimensions, controllers, and build instructions should not be assumed compatible with Wamoduck.
