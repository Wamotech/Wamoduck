# Standing zero fixture

English | [简体中文](README.zh-CN.md)

A four-part PLA fixture for placing an assembled Wamoduck in its saved standing pose and recording the output-side encoder offsets of its 15 servos. The fixture locates the feet, the confirmed lower hip-motor housing faces, Body, head, and closed mouth. Screws join the fixture parts; no screws attach it to the robot.

![Current fixture and robot in the reference pose](images/assembly.png)

This package includes the maintainer's **2026-09-14 P01 revision** and their matching H2D project. The source SolidWorks parts were opened read-only for the new STEP exports and CAD checks.

## Download and print

1. Download the repository, then open [H2D_PLA_standing_zero.3mf](bambu/H2D_PLA_standing_zero.3mf) **as a project** in Bambu Studio. It contains both plates, all four parts, orientations, and saved settings. Bambu Studio 02.08.02.60 authored this project.
2. Confirm H2D, 0.4 mm nozzle, PLA, and the installed plate. The saved plate is SuperTack and all parts use filament slot 1, Bambu PLA Basic. Select your actual consumable/plate profile if different.
3. Slice both plates and inspect support contact and the tall mast before printing. This 3MF contains no G-code; it must be sliced. Print plate 1 once and plate 2 once. Do not add a second copy of the separately supplied STL files to the project.

| Part | Quantity | H2D plate | Print envelope, mm | Function |
| --- | ---: | ---: | --- | --- |
| [P01_Main_frame](stl/P01_Main_frame.stl) | 1 | 1 | 200 × 260 × 315.83 | Base, foot pockets, V saddles, front braces, rear mast and ribs |
| [P02_Head_cradle](stl/P02_Head_cradle.stl) | 1 | 2 | 220.5 × 130.4 × 38.8 | Head cradle and rear/side stops |
| [P03_Head_keeper_mouth](stl/P03_Head_keeper_mouth.stl) | 1 | 2 | 130.4 × 54.112 × 47 | Front head keeper and mouth support |
| [P04_Body_bridge](stl/P04_Body_bridge.stl) | 1 | 2 | 28.249 × 52 × 64 | Body front restraint with integral contact faces |

**Total: four printed pieces and six screws.** The machine-readable list is [print-parts.csv](print-parts.csv).

The saved process uses 0.20 mm layers, **2 walls, 20% honeycomb infill, automatic 5 mm brim, normal automatic support, and no raft**, printing by layer. These are the maintainer's project settings, preserved as supplied; earlier local recommendations of 6 walls and 35–45% infill are not the settings in this download. No physical print or load-test results are included yet.

For manual slicing, the STL files already have their intended print orientations: P01 upright on its base, P02 bottom down, P03 on its outer flat face, and P04 on its side. P01 fits the checked H2D envelope of 325 × 320 × 325 mm, with about 9.17 mm of height remaining before slicer additions. Verify the complete sliced envelope, including adhesion/support structures. Keep support interfaces off the locating surfaces where practical, and remove support residue before fitting.

## Files, units, and revisions

| Folder/file | Purpose |
| --- | --- |
| [step/](step/) | Four neutral CAD solids for geometry editing, in millimeters and the common assembly coordinate system |
| [stl/](stl/) | Four printable meshes in millimeters, oriented for printing |
| [bambu/](bambu/) | Two-plate H2D PLA project with embedded meshes and settings |
| [validation.json](validation.json) | Version-specific digital geometry and package checks |
| [manifest.json](manifest.json) | File sizes, SHA-256 checksums, and export provenance |

STEP and STL provide geometry; a slicer turns either supported format into printer paths. The 3MF project additionally stores placement and printing settings. Bambu Studio's STEP/STL/3MF import is described in the [H2D user manual](https://csm.bblcdn.com/hub/4668d0ca43994ff3bff4b37f1a65c2e7.pdf).

STEP positions reproduce the fixture assembly; STL positions reproduce printing orientations. Their origins therefore differ. P01's public STL is only translated to a zero-based print bounding box; its shape and topology are unchanged from the maintainer's updated STL. P02–P04 are copied unchanged. The public 3MF removes an account identifier from metadata; meshes, layout, and process settings are unchanged. Native working files and obsolete local check reports are kept outside this public package.

## Fits and screws

Nominal dimensions: **M3×0.5 tap pilot Ø2.5 mm; clearance Ø3.3 mm; cup-head counterbore Ø6.5 × 3.2 mm deep; total mating clearance 0.4 mm**. The total clearance is not 0.4 mm on each side. It accommodates the specified PLA printing tolerance of ±0.2 mm as a design allowance; first-print fit still needs checking.

| Connection | Screws |
| --- | --- |
| P01 to P02 | 2 × M3×25 socket-head screws |
| P02 to P03 | 2 × M3×16 socket-head screws |
| P01 to P04 | 2 × M3×16 socket-head screws |

Deburr and remove elephant foot, then hand-tap the Ø2.5 holes M3×0.5. Check screw seating and blind-hole depth before installing the robot. Tighten each pair evenly by hand. No threaded inserts are required. Cup heads bear on the flat counterbore shoulder; do not apply C2 to the narrow bearing ring between Ø6.5 and Ø3.3. The mouth entry has its own C2 lead-in.

P02 rear-stop and outer side-post roots have R3 fillets. P03 has R4 at the mouth-arm inner root and R3 at the upper hanger root. These features are included in STEP, STL, and the 3MF.

[View the head-stop and mouth-support root details](images/roots.png).

## Assembly and calibration

The robot must be articulated into the integral saddles; the rigid standing assembly cannot simply be lowered vertically into the completed fixture.

1. Disable motor drive and confirm that the joints can be moved slowly by hand. Encoder/controller power may remain on for reading. Place P01 on a flat, stable surface.
2. Move the legs by hand and seat both feet in their pockets. Then move the relevant joints until the lower motor housing faces settle onto the two V saddles. Keep the wire exits clear.
3. Fit P02 to the mast key with two M3×25 screws and place the head lightly against its supports.
4. Slide P03 horizontally in from the robot front through its open locating channels, then secure it with two M3×16 screws. The mouth support is 0.2 mm below the modeled closed mouth: use the mechanism's closed state to establish mouth zero, rather than forcing it onto this face.
5. Fit P04 and slide the whole bridge along its fore/aft slots until its integral faces lightly touch Body. Secure it with two M3×16 screws. The bridge works with the lower/rear supports to restrain Body pitching forward; it has no independently adjustable contact pads.
6. With each required datum lightly seated and the drive disabled, record the corresponding output encoder readings/offsets. Avoid distorting the printed frame or pulling a joint into position with screws. Repeat placement to assess consistency before accepting calibration.

The encoders are internal to the motors and remain untouched. Record the robot's actual motor-ID mapping and sign convention separately. URDF `q=0` denotes the saved model pose, not a motor's factory encoder zero: the recorded offsets relate real encoder readings to that reference. The [MATLAB player](../../../tools/matlab/README.md) replays model joint coordinates and does not write calibration to hardware.

## Checked scope

The updated native CAD has one solid per part, no reported feature errors, and zero detected static overlaps involving the fixture at the saved robot pose. All four final STL meshes passed the recorded watertightness, degeneracy, and print-envelope checks. All four 3MF meshes match the corresponding source STL within numerical precision.

These checks cover the supplied digital files. First-print fit, structural loading, repeated placement accuracy, and a complete hardware calibration have not been measured in this package. This is a positioning fixture for manual calibration, not a powered motion-test stand.
