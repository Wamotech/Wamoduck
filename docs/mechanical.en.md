# Mechanical files

English | [简体中文](mechanical.zh-CN.md) · [Home](../README.md)

This package contains simplified geometry selected for sharing. It supports inspecting the design and using it as a starting point for changes. Manufacturing specifications and a verified assembly procedure have not yet been supplied.

## Choose a format

| Format | Location | Contents | Intended use |
| --- | --- | --- | --- |
| STEP `.stp` | [hardware/step](../hardware/step/) | 20 individual part models | Exchange geometry across CAD tools |
| SolidWorks `.SLDPRT` / `.SLDASM` | [hardware/solidworks](../hardware/solidworks/) | 20 parts + 11 assemblies | Inspect the native assembly and mates |
| URDF + STL | [models/wmduck](../models/wmduck/) | Robot description + 20 meshes | View the assembled robot and explore joint motion |

The public native set uses the main saved assembly. Alternate motion assemblies, the older-version archive, application lock files, and intermediate exports are not included. File names are preserved so they can be matched to the source model.

## STEP parts

1. Download the repository and open a file in `hardware/step/` using a CAD application that reads STEP.
2. The exports declare millimeters. Preserve the declared units and check the import scale before taking measurements.
3. These are individual parts, not a whole-robot STEP assembly. To inspect the assembled pose, use the native assembly or URDF.
4. Compare the file name with the [component inventory](components.md). Motor, battery, bearing, IMU, and control-board models provide component geometry; their presence does not provide electronics or supplier manufacturing drawings.

The STEP set is copied without changing its geometry. The IMU is represented by sheet geometry, so a successful import need not yield a solid for every file. This preparation checked file structure and declared units, but did not reopen every STEP in a CAD application.

## SolidWorks assembly

1. Keep all files in `hardware/solidworks/` together.
2. Open [`Full_wmduck.SLDASM`](../hardware/solidworks/Full_wmduck.SLDASM). The source export record identifies SolidWorks 2025; use that version as the initial compatibility target.
3. If SolidWorks requests referenced parts or subassemblies, resolve them from the same folder. If an imported STEP reference is requested, inspect `hardware/step/`.
4. Inspect the saved pose and component tree before changing mates. Save modifications as a separate working copy.

The native files are copied byte-for-byte. The source extraction lists 20 parts and 10 subassemblies, all included alongside the root assembly; the current root assembly and part hashes match that extraction. Their portability has **not** been verified by opening the package in a clean SolidWorks session with the original source unavailable. Embedded references and native binary metadata were not fully decoded. Imported bodies may not contain a complete parametric feature history.

Two source spellings are intentionally preserved: `Control_Borad_AT32` and `Rightt_hip_pitch`. Renaming only one file can break references. Treat any future naming cleanup as a coordinated CAD-and-documentation change.

## Printing and manufacturing

The STL files under `models/wmduck/meshes/` use **meters** and include purchased-component geometry. They are not slicer-ready manufacturing exports. A slicer that assumes millimeters would import them at the wrong scale.

A future printable release should identify only the parts to be fabricated, use an explicit manufacturing unit, and specify quantities, material, orientation, supports, tolerances, and any inserts or finishing operations. Confirm those requirements against the physical design before generating print files. The CAD material labels in the [inventory](components.md) are model data, not approved manufacturing instructions.

## Traceability

[`asset-manifest.json`](../asset-manifest.json) lists the supplied source assets, byte sizes, hashes, and any text-only adjustments. Public file paths are relative to this repository. The [roadmap](roadmap.md) separates this geometry package from the documentation needed to reproduce a working robot.
