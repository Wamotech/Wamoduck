"""Snapshot installed Bambu A1 mini presets; no user settings are accessed."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = Path(r"C:\Program Files\Bambu Studio\resources\profiles\BBL")
META = {"inherits", "include"}
sources = {}


def flatten(kind, name, stack=()):
    if name in stack:
        raise ValueError(f"Cyclic preset: {stack + (name,)}")
    path = PROFILES / kind / (name + ".json")
    raw = path.read_bytes()
    data = json.loads(raw)
    sources[str(path.relative_to(PROFILES))] = hashlib.sha256(raw).hexdigest()
    merged = {}
    if data.get("inherits"):
        merged.update(flatten(kind, data["inherits"], stack + (name,)))
    # Bundled A1 mini includes are individual G-code templates. Apply them
    # after inherited values, before the child, matching PresetBundle.cpp.
    for include in data.get("include", []):
        merged.update(flatten(kind, include, stack + (name,)))
    merged.update({key: value for key, value in data.items() if key not in META})
    return merged


def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


machine_name = "Bambu Lab A1 mini 0.4 nozzle"
process_base = "0.16mm High Quality @BBL A1M"
filament_name = "Generic PLA @BBL A1M"
machine = flatten("machine", machine_name)
machine["printer_settings_id"] = machine_name
assert len(machine["machine_start_gcode"]) > 1000
assert "A1 mini" in machine["machine_start_gcode"]
write("machine-a1mini-0.4.json", machine)

process = flatten("process", process_base)
overrides = {
    "name": "Wamoduck 0.16mm PLA A1 mini tree supports",
    "from": "user",
    "inherits": process_base,
    "layer_height": "0.16",
    "initial_layer_print_height": "0.2",
    "wall_loops": "3",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "enable_support": "1",
    "support_type": "tree(auto)",
    "support_style": "default",
    "support_on_build_plate_only": "0",
    "support_threshold_angle": "30",
    "support_top_z_distance": "0.2",
    "support_bottom_z_distance": "0.2",
    "support_interface_top_layers": "3",
    "support_interface_bottom_layers": "2",
    "support_object_xy_distance": "0.35",
    "support_filament": "0",
    "support_interface_filament": "0",
    "brim_type": "outer_only",
    "brim_width": "8",
    "brim_object_gap": "0.1",
    "initial_layer_speed": ["25"],
    "initial_layer_infill_speed": ["40"],
    "enable_prime_tower": "0",
    "timelapse_type": "0",
}
process.update(overrides)
process["print_settings_id"] = process["name"]
process.pop("setting_id", None)
write("process-0.16-tree.json", process)

filament = flatten("filament", filament_name)
filament["filament_settings_id"] = [filament_name]
write("filament-generic-pla.json", filament)

manifest = {
    "source": "Installed Bambu Studio bundled BBL profiles",
    "profile_bundle_version": json.loads((PROFILES.parent / "BBL.json").read_text(encoding="utf-8"))["version"],
    "machine": machine_name,
    "process_base": process_base,
    "filament": filament_name,
    "bed_type": "Textured PEI Plate",
    "overrides": overrides,
    "source_sha256": dict(sorted(sources.items())),
    "references": [
        "https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage",
        "https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PresetBundle.cpp",
    ],
}
write("profile-provenance.json", manifest)
print(json.dumps({"bundle_version": manifest["profile_bundle_version"], "resolved_source_files": len(sources), "machine_keys": len(machine), "process_keys": len(process), "filament_keys": len(filament)}, indent=2))
