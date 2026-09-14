# Mechanical files

English | [简体中文](mechanical.zh-CN.md) · [Home](../README.md)

This package contains simplified geometry selected for sharing. It supports inspecting the design and using it as a starting point for changes. Manufacturing specifications and a verified assembly procedure have not yet been supplied.

## Choose a format

| Format | Location | Contents | Intended use |
| --- | --- | --- | --- |
| STEP `.stp` | [hardware/step](../hardware/step/) | 20 individual part models | Exchange geometry across CAD tools |
| SolidWorks `.SLDPRT` / `.SLDASM` | [hardware/solidworks](../hardware/solidworks/) | 20 parts + 11 assemblies | Inspect the native assembly and mates |
| URDF + STL | [models/wmduck](../models/wmduck/) | Robot description + 20 meshes | View the assembled robot and explore joint motion |
| Zero-fixture STEP / STL / 3MF | [hardware/fixtures/standing-zero](../hardware/fixtures/standing-zero/) | 4 editable STEP + 4 print STL + a two-plate H2D project | Print the standing-zero calibration fixture |

The public native set uses the main saved assembly. Alternate motion assemblies, the older-version archive, application lock files, and intermediate exports are not included. File names are preserved so they can be matched to the source model.

## STEP parts

1. Download the repository and open a file in `hardware/step/` using a CAD application that reads STEP.
2. The exports declare millimeters. Preserve the declared units and check the import scale before taking measurements.
3. These are individual parts, not a whole-robot STEP assembly. To inspect the assembled pose, use the native assembly or URDF.
4. Compare the file name with the [component inventory](components.md). Motor, battery, bearing, IMU, and control-board models provide component geometry; their presence does not provide electronics or supplier manufacturing drawings.

The STEP set is copied without changing its geometry. The IMU is represented by sheet geometry, so a successful import need not yield a solid for every file. This preparation checked file structure and declared units, but did not reopen every STEP in a CAD application.

The [structure classification](../hardware/robot-structure.csv) separates the 20 STEP geometries into 15 robot-structure classes and 5 purchased/reference classes. The assembly uses 40 modeled instances, but an assembly instance count is not a printable-part split or a manufacturing quantity. One STEP may also contain more than one body; `Body_Frame`, in particular, should be inspected as a multi-body candidate after import. CAD material assignments record source-model metadata and are not approved materials or manufacturing requirements.

## SolidWorks assembly

1. Keep all files in `hardware/solidworks/` together.
2. Open [`Full_wmduck.SLDASM`](../hardware/solidworks/Full_wmduck.SLDASM). The source export record identifies SolidWorks 2025; use that version as the initial compatibility target.
3. If SolidWorks requests referenced parts or subassemblies, resolve them from the same folder. If an imported STEP reference is requested, inspect `hardware/step/`.
4. Inspect the saved pose and component tree before changing mates. Save modifications as a separate working copy.

The native files are copied byte-for-byte. The source extraction lists 20 parts and 10 subassemblies, all included alongside the root assembly; the current root assembly and part hashes match that extraction. Their portability has **not** been verified by opening the package in a clean SolidWorks session with the original source unavailable. Embedded references and native binary metadata were not fully decoded. Imported bodies may not contain a complete parametric feature history.

Two source spellings are intentionally preserved: `Control_Borad_AT32` and `Rightt_hip_pitch`. Renaming only one file can break references. Treat any future naming cleanup as a coordinated CAD-and-documentation change.

## Printing and manufacturing

The STL files under `models/wmduck/meshes/` use **meters** and include purchased-component geometry. They are not slicer-ready manufacturing exports. A slicer that assumes millimeters would import them at the wrong scale.

To make a trial print of a robot structural STEP, choose a `robot_structure` entry in [robot-structure.csv](../hardware/robot-structure.csv), import its `.stp` into a STEP-capable slicer such as Bambu Studio, and preserve millimeters at 100% scale. Inspect the body count before arranging the plate: one file can contain several bodies. Choose orientation and supports for the selected part, then check mating holes and contact faces on the trial print. The CSV's modeled instance count is a reference for assembly, not an approved print quantity or process.

The [standing-zero fixture](../hardware/fixtures/standing-zero/README.md) is the current downloadable manufacturing package. It provides four editable STEP files and four millimetre-scale STL files, one of each printed part. The user-supplied Bambu H2D 3MF arranges those four parts across two plates. Assembly uses six M3 screws. Its documented CAD and mesh checks do not establish that a physical print or repeatability test has been completed.

The robot itself does not yet have a verified functional print list. A future robot-print release should identify only the parts to be fabricated, specify the actual print split rather than copying assembly instance counts, use explicit manufacturing units, and record material, orientation, supports, tolerances, hardware and finishing operations. Confirm those requirements against the physical design before generating print files. The CAD material labels in the [inventory](components.md) are model data, not approved manufacturing instructions.

## Traceability

[`asset-manifest.json`](../asset-manifest.json) lists the selected assets, byte sizes, hashes, and export provenance. Public file paths are relative to this repository; the fixture has its own detailed manifest and validation record. The [roadmap](roadmap.md) separates this geometry package from the documentation needed to reproduce a working robot.
