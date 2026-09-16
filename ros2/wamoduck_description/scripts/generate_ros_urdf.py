#!/usr/bin/env python3
"""Rewrite the canonical model URDF into a ROS-installable, ``package://`` URDF.

Why this exists
---------------
``models/wmduck/wmduck.urdf`` is the single source of truth for the robot's geometry. It
references its meshes with paths relative to itself::

    <mesh filename="meshes/Head.stl" scale="1 1 1"/>

That form works for tooling that resolves relative to the URDF file, but it does **not**
work for ``robot_state_publisher`` + RViz. RViz hands the string to ``resource_retriever``,
which only understands ``package://``, ``file://`` and paths relative to the *current
working directory*. Launch RViz from any other directory and you get a silently empty
robot -- the classic "the URDF loads but nothing appears" failure.

So this script rewrites every mesh reference to
``package://<package_name>/meshes/<basename>`` and writes the result into the build tree.
The descriptor is otherwise byte-for-byte the canonical file: no link, joint, origin,
axis, limit, mass, inertia or visual/collision entry is added, removed or edited. That
equality is asserted by ``wamoduck_ros2/test/test_model_contract.py``, so the ROS
description and the MJCF used for training keep describing the same robot.

What it deliberately does NOT do
--------------------------------
It does not copy meshes. Copying 11 MB of STL into the package (or symlinking them inside
the Git tree, which Windows Git clients handle inconsistently) would create a second copy to
keep in sync. ``wamoduck_description/CMakeLists.txt`` installs them from
``models/wmduck/meshes`` at build time instead. See ``urdf/README.md``.

Usage
-----
    generate_ros_urdf.py --source-urdf <wmduck.urdf> --meshes-dir <meshes dir> \
                         --package-name wamoduck_description \
                         --output <out.urdf> --manifest <out.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Matches <mesh ... filename="..." ...> while leaving every other attribute alone.
_MESH_FILENAME_RE = re.compile(r'(<mesh\b[^>]*?\bfilename=")([^"]*)(")')

# Joint types that can move, i.e. that a JointState message can drive.
_MOVABLE_JOINT_TYPES = ("revolute", "continuous", "prismatic", "planar", "floating")


def mesh_basename(reference: str) -> str:
    """Reduce any mesh reference form to a bare file name.

    Handles ``meshes/X.stl``, ``./meshes/X.stl``, ``package://pkg/meshes/X.stl``,
    ``file:///abs/path/X.stl``, ``..\\meshes\\X.stl`` and a bare ``X.stl``.
    """
    text = reference.strip().replace("\\", "/")
    for scheme in ("package://", "file://"):
        if text.startswith(scheme):
            text = text[len(scheme):]
            break
    return text.rstrip("/").split("/")[-1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rewrite_mesh_references(text: str, package_name: str, meshes_dir: Path) -> tuple[str, list[str]]:
    """Return (rewritten URDF text, unique mesh basenames referenced)."""
    referenced: list[str] = []
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = mesh_basename(match.group(2))
        if name not in referenced:
            referenced.append(name)
        if not (meshes_dir / name).is_file() and name not in missing:
            missing.append(name)
        return f"{match.group(1)}package://{package_name}/meshes/{name}{match.group(3)}"

    rewritten = _MESH_FILENAME_RE.sub(replace, text)
    if missing:
        raise SystemExit(
            "generate_ros_urdf: the URDF references meshes that are not in "
            f"{meshes_dir}: {', '.join(sorted(missing))}"
        )
    return rewritten, referenced


def describe(root: ET.Element) -> dict:
    """Collect the structural facts that make the generated file auditable."""
    joints: list[dict] = []
    fixed: list[str] = []
    for joint in root.findall("joint"):
        name = joint.get("name", "")
        jtype = joint.get("type", "")
        if jtype == "fixed":
            fixed.append(name)
        elif jtype in _MOVABLE_JOINT_TYPES:
            joints.append({"name": name, "type": jtype})
    links = [link.get("name", "") for link in root.findall("link")]
    return {
        "robot_name": root.get("name", ""),
        "links": len(links),
        "link_names": links,
        "movable_joints_in_urdf_document_order": [j["name"] for j in joints],
        "movable_joint_types": {j["name"]: j["type"] for j in joints},
        "fixed_joints": fixed,
        "root_link": links[0] if links else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-urdf", required=True, type=Path)
    parser.add_argument("--meshes-dir", required=True, type=Path)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args(argv)

    source: Path = args.source_urdf
    meshes_dir: Path = args.meshes_dir
    if not source.is_file():
        raise SystemExit(f"generate_ros_urdf: source URDF not found: {source}")
    if not meshes_dir.is_dir():
        raise SystemExit(f"generate_ros_urdf: mesh directory not found: {meshes_dir}")

    original = source.read_text(encoding="utf-8")
    rewritten, referenced = rewrite_mesh_references(original, args.package_name, meshes_dir)

    # Parse both to prove the rewrite changed nothing structural.
    original_root = ET.fromstring(original)
    rewritten_root = ET.fromstring(rewritten)
    before = describe(original_root)
    after = describe(rewritten_root)
    for key in (
        "robot_name",
        "links",
        "movable_joints_in_urdf_document_order",
        "fixed_joints",
        "root_link",
    ):
        if before[key] != after[key]:
            raise SystemExit(
                f"generate_ros_urdf: rewrite changed '{key}' "
                f"({before[key]!r} -> {after[key]!r}); refusing to install a mutated description"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rewritten, encoding="utf-8", newline="\n")

    mesh_files = sorted(p.name for p in meshes_dir.glob("*.stl"))
    unused = [name for name in mesh_files if name not in referenced]

    manifest = {
        "generated_by": "ros2/wamoduck_description/scripts/generate_ros_urdf.py",
        "source_urdf": str(source),
        "source_urdf_sha256": sha256_file(source),
        "output_urdf": str(args.output),
        "output_urdf_sha256": sha256_file(args.output),
        "meshes_dir": str(meshes_dir),
        "package_name": args.package_name,
        "mesh_reference_form": f"package://{args.package_name}/meshes/<basename>",
        **after,
        "movable_joints": len(after["movable_joints_in_urdf_document_order"]),
        "mesh_references_rewritten": len(_MESH_FILENAME_RE.findall(original)),
        "unique_meshes_referenced": len(referenced),
        "meshes_available_on_disk": len(mesh_files),
        "meshes_present_but_not_referenced": unused,
        "structural_equality_vs_source": True,
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )

    print(
        f"generate_ros_urdf: {source.name} -> {args.output.name}: "
        f"{manifest['mesh_references_rewritten']} mesh references rewritten to "
        f"package://{args.package_name}/meshes/, "
        f"{manifest['links']} links, {manifest['movable_joints']} movable joints, "
        f"{len(manifest['fixed_joints'])} fixed joints"
    )
    if unused:
        print(f"generate_ros_urdf: note -- present but unreferenced meshes: {', '.join(unused)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
