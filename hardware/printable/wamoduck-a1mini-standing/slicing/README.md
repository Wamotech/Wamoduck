# Offline A1 mini slicing

`slice_model.py` slices an upright STL and exports a project containing one plate's G-code. It does not open the GUI, install presets, contact a printer, or start a print.

```powershell
py -3.11 .\slicing\slice_model.py .\Wamoduck_Standing_160mm.stl --output .\slicing\output-new
```

Run from the `wamoduck-a1mini-standing` folder. The output directory must be new: the wrapper refuses a stale archive or result file. It records the exact executable argument list in `command.json`, Bambu's slicer result in `result.json`, and archive/settings validation in `validation.json`. The generated `.gcode.3mf` contains the model, settings, and sliced G-code; `plate_1.gcode` is also available separately.

The installed slicer is Bambu Studio `02.08.02.60` (confirmed in generated G-code), with BBL profile bundle `02.08.00.04`: A1 mini, 0.4 mm nozzle, Generic PLA, Textured PEI Plate, and the 0.16 mm High Quality process base. Changes are three walls, 15% gyroid, automatic tree supports with three top interface layers, 0.20 mm support contact distances, an 8 mm outer brim with 0.10 mm gap, and 25 mm/s initial-layer perimeter speed. Support and interface use the same filament. Model orientation is preserved; arrangement translates/rotates on the plate without laying the figurine down. The initial layer is 0.20 mm. The Generic PLA profile supplies its normal nozzle and bed temperatures, cooling and flow limits.

`prepare_profiles.py` resolves inherited presets and the A1 mini's five included G-code templates from the installation's bundled profiles. The checked-in JSON snapshots are sufficient for slicing; regeneration is only needed intentionally after changing Bambu versions. `profile-provenance.json` records every source file's SHA-256 and the process overrides. These snapshots contain no personal profiles or account data.

The underlying CLI invocation is equivalent to:

```powershell
& 'C:\Program Files\Bambu Studio\bambu-studio.exe' `
  --debug 2 --arrange 1 --curr-bed-type 'Textured PEI Plate' `
  --load-settings 'ABSOLUTE\machine-a1mini-0.4.json;ABSOLUTE\process-0.16-tree.json' `
  --load-filaments 'ABSOLUTE\filament-generic-pla.json' `
  --slice 0 --outputdir 'ABSOLUTE\output' `
  --export-3mf 'wamoduck.gcode.3mf' 'ABSOLUTE\wamoduck.stl'
```

Use the Python wrapper to wait for completion reliably on Windows. Console output may be empty. `--export-3mf` must be a **filename only** when `--outputdir` is supplied because Bambu prepends the output directory unconditionally. `--orient` is deliberately omitted to retain the standing pose.

Final figurine result: `../Wamoduck_A1mini_PLA_160mm.3mf` is the validated project, copied from the successful final slicing run. Bambu returned exit 0 and `return_code: 0`, with an empty warning message. The estimate is **11 h 56 m 37 s and 150.26 g of PLA**, including supports; 1,000 layers and zero filament changes. The model remains 73.86 × 97.58 × 160 mm, standing at Z=0. The complete first-layer footprint, including brim/support, is 96.47 × 116.92 mm and stays at least 31.54 mm inside the bed edges. Its G-code contains 1,409 support segments and 464 interface segments. Printing has not been physically tested.

The public [slicing validation record](../slicing_validation.json) records the final STL SHA-256 (`ccbf810cbc7d7c1af2d7d276e885d178368bc43d92b9d1be36b6b8ca2b4acd96`), config hashes, output archive hash, XML/ZIP checks, embedded settings, footprint, and slicer statistics. The final archive SHA-256 is `acbbe804ae284d35d9c03e39cd7c4f2b18f8198dfad1ff3182e833362d386023`.

Directories matching `output*` or `probe*` are local intermediate and diagnostic outputs and are intentionally ignored by the public package. They may be retained in a working tree for investigation, but reproducibility claims should cite `../slicing_validation.json`, the checked-in profiles and scripts, and the top-level validated 3MF rather than those folders.

Sources: [official CLI usage](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage), [Bambu CLI implementation](https://github.com/bambulab/BambuStudio/blob/master/src/BambuStudio.cpp), and [preset resolution implementation](https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PresetBundle.cpp). The bundled profile snapshots derive from Bambu Studio's distributed profiles.
