"""Offline Bambu Studio slicing and archive checks. Never sends to a printer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("model", type=Path, help="Upright STL in millimetres")
parser.add_argument("--output", type=Path, default=HERE / "output")
parser.add_argument("--exe", type=Path, default=Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe"))
args = parser.parse_args()
model = args.model.resolve(strict=True)
model_sha256 = hashlib.sha256(model.read_bytes()).hexdigest()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
archive = out / (model.stem + ".gcode.3mf")
if archive.exists() or (out / "result.json").exists():
    raise SystemExit("Use a new output directory so stale output cannot pass validation.")
command = [
    str(args.exe), "--debug", "2", "--arrange", "1",
    "--curr-bed-type", "Textured PEI Plate",
    "--load-settings", f"{HERE / 'machine-a1mini-0.4.json'};{HERE / 'process-0.16-tree.json'}",
    "--load-filaments", str(HERE / "filament-generic-pla.json"),
    "--slice", "0", "--outputdir", str(out),
    # Bambu prefixes --outputdir unconditionally, so this must be a basename.
    "--export-3mf", archive.name, str(model),
]
(out / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
print(subprocess.list2cmdline(command), flush=True)
started = time.monotonic()
with (out / "stdout.txt").open("w", encoding="utf-8") as stdout, (out / "stderr.txt").open("w", encoding="utf-8") as stderr:
    result = subprocess.run(command, cwd=out, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
print(f"Bambu Studio exit={result.returncode}; elapsed={time.monotonic() - started:.1f}s", flush=True)
report = {"exit_code": result.returncode, "elapsed_seconds": round(time.monotonic() - started, 2),
          "input_model": str(model), "input_model_sha256": model_sha256,
          "config_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (
              HERE / "machine-a1mini-0.4.json", HERE / "process-0.16-tree.json", HERE / "filament-generic-pla.json")}}
assert hashlib.sha256(model.read_bytes()).hexdigest() == model_sha256, "Input model changed while slicing"
result_path = out / "result.json"
if result_path.exists():
    slicing_result = json.loads(result_path.read_text(encoding="utf-8"))
    report["slicing_result"] = slicing_result
    if slicing_result.get("return_code") != 0:
        raise SystemExit(json.dumps(slicing_result, indent=2))
if result.returncode != 0 or not archive.exists():
    raise SystemExit(f"Slicing did not produce an archive. Check {out}")
with zipfile.ZipFile(archive) as zf:
    assert zf.testzip() is None, "Corrupt ZIP entry"
    names = zf.namelist()
    gcode_names = [name for name in names if name.endswith(".gcode")]
    assert len(gcode_names) == 1, f"Expected exactly one plate G-code, got {gcode_names}"
    for name in names:
        if name.endswith((".model", ".xml", ".rels")) or name in ("Metadata/model_settings.config", "Metadata/slice_info.config"):
            ET.fromstring(zf.read(name))
    settings = json.loads(zf.read("Metadata/project_settings.config"))
    expected = {
        "printer_model": "Bambu Lab A1 mini", "layer_height": "0.16",
        "wall_loops": "3", "sparse_infill_density": "15%", "sparse_infill_pattern": "gyroid",
        "enable_support": "1", "support_type": "tree(auto)", "brim_width": "8",
        "brim_type": "outer_only", "brim_object_gap": "0.1",
        "support_top_z_distance": "0.2", "support_bottom_z_distance": "0.2",
        "support_filament": "0", "support_interface_filament": "0",
        "curr_bed_type": "Textured PEI Plate",
    }
    for key, value in expected.items():
        assert settings.get(key) == value, (key, settings.get(key), value)
    assert settings.get("nozzle_diameter") == ["0.4"], settings.get("nozzle_diameter")
    assert len(settings.get("filament_type", [])) == 1, settings.get("filament_type")
    gcode = zf.read(gcode_names[0])
    assert len(gcode) > 5000, "G-code unexpectedly short"
    report.update({"archive": str(archive), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                   "archive_members": names, "gcode_bytes": len(gcode), "verified_settings": expected})
    report["support_segments"] = gcode.count(b"; FEATURE: Support\n") + gcode.count(b"; FEATURE: Support\r\n")
    report["support_interface_segments"] = gcode.count(b"; FEATURE: Support interface\n") + gcode.count(b"; FEATURE: Support interface\r\n")
    report["gcode_header"] = gcode.split(b"; HEADER_BLOCK_END", 1)[0].decode("utf-8")
    plate_metadata = json.loads(zf.read("Metadata/plate_1.json"))
    report["plate_metadata"] = plate_metadata
    xmin, ymin, xmax, ymax = plate_metadata["bbox_all"]
    assert 0 <= xmin < xmax <= 180 and 0 <= ymin < ymax <= 180, "First-layer toolpaths exceed A1 mini bed"
    for name in ("Metadata/plate_1.png", "Metadata/top_1.png"):
        if name in names:
            (out / Path(name).name).write_bytes(zf.read(name))
    # --outputdir already causes Bambu to write plate_1.gcode. Do not rewrite
    # that file; the authoritative G-code bytes above come from the archive.
(out / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"archive": str(archive), "validation": str(out / "validation.json"), "gcode_bytes": len(gcode)}, indent=2))
