#!/usr/bin/env python3
"""Independent geometric verification of the Wamoduck ROS description.

Why this exists
---------------
"``check_urdf`` passes" and "the model looks right" are different claims. ``check_urdf``
verifies that the XML is a well-formed kinematic tree; it says nothing about whether a joint
origin is off by 100 mm, whether a mesh silently failed to load, or whether a link's visual
transform is wrong. This script checks the geometry itself, independently of RViz:

1. **Structure.** Every link, joint, parent/child edge, and the single rooted tree.
2. **Mesh resolution.** Every ``<mesh filename>`` resolves to a real file, in every
   reference form (``package://``, ``file://``, relative), using the same ament index rule
   RViz uses.
3. **STL integrity.** Each mesh parses as a binary STL and holds its own declared triangle
   count; the total is compared against the published record.
4. **Forward kinematics at q = 0.** The whole assembly is transformed into the root frame
   from the URDF alone, and the resulting axis-aligned bounding box is compared against
   ``models/wmduck/validation.json`` -> ``zero_pose_bounds_m``. A wrong joint origin, a wrong
   rpy, a missing mesh or a wrong mesh scale all move this box. This is the check that turns
   "it loaded" into "it is where the model says it is".
5. **Left/right symmetry.** Mirror-image link pairs are compared across the Y plane, which
   catches a sign error in one leg's origin.

Nothing here needs RViz, a GPU or a display, so it can run on the X5 too.

Usage
-----
    python3 verify_description.py --urdf <wmduck.urdf> --meshes <dir> \
                                  [--validation <validation.json>] [--report out.json]

Exit status is 0 only if every check that could run passed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print('verify_description: numpy is required (it ships with ROS 2)', file=sys.stderr)
    raise SystemExit(3)

# Bounds comparison tolerance, in metres.
#
# The published record (models/wmduck/validation.json) carries full double precision, but the
# STL vertex coordinates it was derived from are float32, so an independently written reader
# cannot reproduce it bit-for-bit. On this model the observed residual is ~3.1e-9 m: about
# 8e-9 relative, which is inside float32 rounding for coordinates of order 0.2 m (eps ~1.2e-7)
# and is therefore expected rather than suspicious.
#
# 1e-6 m (one micrometre) leaves three orders of magnitude of headroom above that residual,
# and is still three or more orders of magnitude below any error that would matter: a wrong
# joint origin, a wrong rpy, a wrong mesh or a wrong mesh scale all move this box by
# millimetres at the very least, and usually by centimetres. The exact residual is always
# reported, so a reader can judge it rather than trust the pass/fail.
BOUNDS_TOLERANCE_M = 1e-6
SYMMETRY_TOLERANCE_M = 1e-9


# ---------------------------------------------------------------------------
# URDF parsing helpers
# ---------------------------------------------------------------------------


def parse_origin(element: ET.Element | None) -> tuple[np.ndarray, np.ndarray]:
    """Return (translation, rotation matrix) from a <origin> element."""
    if element is None:
        return np.zeros(3), np.eye(3)
    origin = element.find('origin')
    if origin is None:
        return np.zeros(3), np.eye(3)
    xyz = [float(v) for v in (origin.get('xyz') or '0 0 0').split()]
    rpy = [float(v) for v in (origin.get('rpy') or '0 0 0').split()]
    return np.array(xyz, dtype=float), rpy_to_matrix(*rpy)


def rpy_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """URDF fixed-axis roll-pitch-yaw: R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=float)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=float)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=float)
    return rz @ ry @ rx


def read_stl_vertices(path: Path) -> np.ndarray:
    """Vertices of a binary STL as an (N, 3) float array.

    SolidWorks exports binary STL, which is what the model ships. An ASCII STL is rejected
    loudly rather than mis-parsed: the binary reader would happily read 'solid ...' as a
    header and then invent a triangle count from ASCII bytes.
    """
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f'{path.name}: too short to be a binary STL ({len(data)} B)')
    if data[:5].lower() == b'solid' and len(data) < 84 + 50:
        raise ValueError(f'{path.name}: looks like an ASCII STL; this reader is binary-only')
    count = struct.unpack_from('<I', data, 80)[0]
    expected = 84 + count * 50
    if len(data) != expected:
        raise ValueError(
            f'{path.name}: declares {count} triangles ({expected} B) but the file is {len(data)} B'
        )
    if count == 0:
        return np.zeros((0, 3), dtype=float)
    raw = np.frombuffer(data, dtype=np.uint8, count=count * 50, offset=84)
    records = raw.reshape(count, 50)
    # 12 little-endian float32 per facet: normal(3) + v1(3) + v2(3) + v3(3) + 2 attribute bytes.
    floats = records[:, :48].copy().view('<f4').reshape(count, 12)
    return floats[:, 3:12].reshape(count * 3, 3).astype(float)


def resolve_mesh(reference: str, urdf_dir: Path, meshes_dir: Path, package_name: str) -> Path | None:
    """Resolve a mesh reference the way resource_retriever does."""
    text = reference.strip().replace('\\', '/')
    basename = text.rstrip('/').split('/')[-1]
    candidates: list[Path] = []
    if text.startswith(f'package://{package_name}/'):
        candidates.append(meshes_dir / basename)
    elif text.startswith('package://'):
        rest = text[len('package://'):]
        candidates.append(urdf_dir / rest)
    elif text.startswith('file://'):
        candidates.append(Path(text[len('file://'):]))
    else:
        candidates.append(urdf_dir / text)
        candidates.append(Path.cwd() / text)
        candidates.append(meshes_dir / basename)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def is_unresolvable_in_rviz(reference: str, rviz_cwd: Path) -> bool:
    """Would resource_retriever fail on this reference when RViz runs from ``rviz_cwd``?

    This models the actual failure mode the generated URDF exists to avoid. RViz hands the
    string to resource_retriever, which understands ``package://`` and ``file://`` and
    otherwise treats the path as relative to the **current working directory** -- not to the
    URDF file. So a bare ``meshes/Head.stl`` is only safe by luck, and the luck runs out the
    moment RViz is launched from anywhere else.
    """
    text = reference.strip().replace('\\', '/')
    if text.startswith('package://') or text.startswith('file://'):
        return False
    return not (rviz_cwd / text).is_file()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(urdf_path: Path, meshes_dir: Path, validation_path: Path | None, package_name: str,
           rviz_cwd: Path) -> dict:
    report: dict = {
        'urdf': str(urdf_path),
        'meshes_dir': str(meshes_dir),
        'validation': str(validation_path) if validation_path else None,
        'checks': {},
        'failures': [],
        'notes': [],
    }
    checks = report['checks']
    failures = report['failures']

    def check(name: str, ok: bool, detail: str = '') -> bool:
        checks[name] = {'ok': bool(ok), 'detail': detail}
        if not ok:
            failures.append(f'{name}: {detail}')
        return ok

    urdf_dir = urdf_path.parent
    root = ET.fromstring(urdf_path.read_text(encoding='utf-8'))

    # ---- 1. structure ----------------------------------------------------
    links = {element.get('name'): element for element in root.findall('link')}
    joints: dict[str, ET.Element] = {element.get('name'): element for element in root.findall('joint')}
    child_of: dict[str, str] = {}
    parent_of: dict[str, str] = {}
    problems: list[str] = []
    for name, joint in joints.items():
        parent = joint.find('parent')
        child = joint.find('child')
        if parent is None or child is None:
            problems.append(f'joint {name} has no parent/child')
            continue
        p, c = parent.get('link'), child.get('link')
        if p not in links:
            problems.append(f'joint {name}: parent link {p!r} does not exist')
        if c not in links:
            problems.append(f'joint {name}: child link {c!r} does not exist')
        if c in child_of:
            problems.append(f'link {c} is the child of two joints')
        child_of[c] = name
        parent_of[c] = p

    roots = [name for name in links if name not in child_of]
    check('tree_has_exactly_one_root', len(roots) == 1, f'roots={roots}')
    check('every_link_is_connected', len(child_of) == len(links) - 1,
          f'{len(child_of)} child links for {len(links)} links')
    check('no_structural_problems', not problems, '; '.join(problems))
    checks['counts'] = {
        'links': len(links),
        'joints': len(joints),
        'movable_joints': sum(
            1 for j in joints.values() if j.get('type') != 'fixed'
        ),
        'fixed_joints': sum(1 for j in joints.values() if j.get('type') == 'fixed'),
        'root_links': roots,
    }

    # Zero-pose forward kinematics. A revolute joint at q = 0 contributes its origin only.
    world: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    link_pos, link_rot = np.zeros(3), np.eye(3)
    world[roots[0]] = (link_pos, link_rot)
    pending = list(joints.items())
    progressed = True
    while pending and progressed:
        progressed = False
        for name, joint in list(pending):
            child = joint.find('child').get('link')
            parent = joint.find('parent').get('link')
            if parent not in world:
                continue
            xyz, rot = parse_origin(joint)
            p_pos, p_rot = world[parent]
            world[child] = (p_pos + p_rot @ xyz, p_rot @ rot)
            pending.remove((name, joint))
            progressed = True
    check('forward_kinematics_reaches_every_link', not pending,
          f'{len(pending)} links unreachable: {[j[0] for j in pending]}')

    # ---- 2/3. meshes -----------------------------------------------------
    # The mesh lives at <visual|collision><geometry><mesh>, one level down from the
    # visual/collision element. Reading only the direct child silently finds nothing and
    # makes every downstream mesh check vacuously true, so the count is asserted first.
    references: list[tuple[str, str]] = []   # (kind, reference)
    for link_name, link in links.items():
        for kind in ('visual', 'collision'):
            for element in link.findall(kind):
                mesh = element.find('geometry/mesh')
                if mesh is not None:
                    references.append((kind, mesh.get('filename', '')))

    check('mesh_references_were_found_at_all', len(references) > 0,
          f'{len(references)} mesh tags under <visual>/<collision>; 0 would make the '
          'mesh checks below vacuous')

    unresolved = [
        reference for _kind, reference in references
        if resolve_mesh(reference, urdf_dir, meshes_dir, package_name) is None
    ]
    check('all_mesh_references_resolve', not unresolved,
          f'{len(unresolved)} unresolved: {sorted(set(unresolved))[:5]}')

    rviz_unsafe = [
        reference for _kind, reference in references
        if is_unresolvable_in_rviz(reference, rviz_cwd)
    ]
    check(
        'no_mesh_reference_needs_the_rviz_cwd',
        not rviz_unsafe,
        f'{len(rviz_unsafe)} references would resolve only from a lucky working directory '
        f'(RViz launched from {rviz_cwd}): {sorted(set(rviz_unsafe))[:5]}',
    )

    # ---- 4. STL integrity + zero-pose bounds ----------------------------
    cache: dict[Path, np.ndarray] = {}
    triangle_total = 0
    vertex_total = 0
    mesh_triangle_counts: dict[str, int] = {}
    for _kind, reference in references:
        path = resolve_mesh(reference, urdf_dir, meshes_dir, package_name)
        if path is None:
            continue
        if path not in cache:
            cache[path] = read_stl_vertices(path)
            mesh_triangle_counts[path.name] = len(cache[path]) // 3
    triangle_total = sum(mesh_triangle_counts.values())
    for vertices in cache.values():
        vertex_total += len(vertices)

    check('every_referenced_mesh_parses_as_binary_stl', len(cache) > 0,
          f'{len(cache)} distinct mesh files parsed')

    # Bounds for three plausible definitions, so that a mismatch is diagnosable instead of
    # just "the numbers differ".
    bounds: dict[str, dict] = {}
    for variant in ('all', 'visual', 'collision'):
        mins = np.array([np.inf] * 3)
        maxs = np.array([-np.inf] * 3)
        seen_any = False
        for link_name, link in links.items():
            if link_name not in world:
                continue
            base_pos, base_rot = world[link_name]
            for kind in ('visual', 'collision'):
                if variant != 'all' and kind != variant:
                    continue
                for element in link.findall(kind):
                    mesh = element.find('geometry/mesh')
                    if mesh is None:
                        continue
                    path = resolve_mesh(mesh.get('filename', ''), urdf_dir, meshes_dir, package_name)
                    if path is None:
                        continue
                    scale = np.array(
                        [float(v) for v in (mesh.get('scale') or '1 1 1').split()], dtype=float
                    )
                    oxyz, orot = parse_origin(element)
                    vertices = cache[path] * scale
                    if len(vertices) == 0:
                        continue
                    transform = base_rot @ orot
                    points = (vertices @ transform.T) + (base_pos + base_rot @ oxyz)
                    mins = np.minimum(mins, points.min(axis=0))
                    maxs = np.maximum(maxs, points.max(axis=0))
                    seen_any = True
        if seen_any:
            bounds[variant] = {
                'min': [float(v) for v in mins],
                'max': [float(v) for v in maxs],
                'size': [float(v) for v in (maxs - mins)],
            }
    report['zero_pose_bounds'] = bounds

    if validation_path and validation_path.is_file():
        published = json.loads(validation_path.read_text(encoding='utf-8'))
        published_min = np.array(published['zero_pose_bounds_m'][0], dtype=float)
        published_max = np.array(published['zero_pose_bounds_m'][1], dtype=float)

        best_variant = None
        best_deviation = float('inf')
        deviations: dict[str, float] = {}
        for variant, boxes in bounds.items():
            deviation = max(
                float(np.max(np.abs(np.array(boxes['min']) - published_min))),
                float(np.max(np.abs(np.array(boxes['max']) - published_max))),
            )
            deviations[variant] = deviation
            if deviation < best_deviation:
                best_variant, best_deviation = variant, deviation
        report['published_bounds_comparison'] = {
            'published_min': [float(v) for v in published_min],
            'published_max': [float(v) for v in published_max],
            'max_abs_deviation_per_variant_m': deviations,
            'best_matching_variant': best_variant,
            'best_max_abs_deviation_m': best_deviation,
            'tolerance_m': BOUNDS_TOLERANCE_M,
            'tolerance_rationale': (
                'STL vertices are float32, so an independent double-precision reader cannot '
                'reproduce the published record exactly; the observed residual is float32 '
                'rounding, not geometry disagreement'
            ),
            'computed_size_m': {
                variant: boxes['size'] for variant, boxes in bounds.items()
            },
            'published_size_m': published.get('zero_pose_size_xyz_m'),
        }
        check(
            'zero_pose_bounds_match_the_published_record',
            best_deviation <= BOUNDS_TOLERANCE_M,
            f'best variant {best_variant!r} deviates by {best_deviation:.3e} m '
            f'(tolerance {BOUNDS_TOLERANCE_M:.0e} m); per-variant {deviations}',
        )
        check(
            'triangle_count_matches_the_published_record',
            triangle_total == published.get('binary_stl_triangles'),
            f'URDF references {triangle_total} triangles across {len(cache)} unique meshes, '
            f'published record says {published.get("binary_stl_triangles")}',
        )
        check(
            'link_and_joint_counts_match_the_published_record',
            len(links) == published.get('urdf_links')
            and len(joints) == published.get('rotational_joints', 0) + published.get('fixed_joints', 0),
            f'{len(links)} links / {len(joints)} joints vs published '
            f'{published.get("urdf_links")} / '
            f'{published.get("rotational_joints")}+{published.get("fixed_joints")}',
        )
        check(
            'root_link_matches_the_published_record',
            roots == [published.get('root_link')],
            f'{roots} vs {published.get("root_link")}',
        )
    else:
        report['notes'].append('no validation.json supplied; bounds were computed but not compared')

    # ---- 5. left/right symmetry -----------------------------------------
    symmetry: dict[str, float] = {}
    for link_name in links:
        if not link_name.startswith('left_'):
            continue
        mirror_name = 'right_' + link_name[len('left_'):]
        if mirror_name not in world or link_name not in world:
            continue
        left_pos = world[link_name][0]
        right_pos = world[mirror_name][0]
        # Mirror across the Y plane: x and z must agree, y must be opposite.
        deviation = max(
            abs(left_pos[0] - right_pos[0]),
            abs(left_pos[1] + right_pos[1]),
            abs(left_pos[2] - right_pos[2]),
        )
        symmetry[f'{link_name} <-> {mirror_name}'] = float(deviation)
    report['left_right_frame_symmetry_m'] = symmetry
    if symmetry:
        worst = max(symmetry.values())
        check(
            'left_right_link_frames_are_mirror_symmetric',
            worst <= SYMMETRY_TOLERANCE_M,
            f'worst deviation {worst:.3e} m over {len(symmetry)} pairs',
        )

    report['mesh_references'] = len(references)
    report['unique_meshes'] = len(cache)
    report['mesh_triangle_counts'] = mesh_triangle_counts
    report['triangle_total'] = triangle_total
    # Summing over references instead of unique files counts a shared mesh once per instance;
    # the published record is a per-file figure, so it is the unique sum that is compared.
    report['triangle_total_over_references'] = sum(
        mesh_triangle_counts[path.name]
        for _kind, reference in references
        for path in [resolve_mesh(reference, urdf_dir, meshes_dir, package_name)]
        if path is not None and path.name in mesh_triangle_counts
    )
    report['mesh_vertices_total'] = vertex_total
    report['joint_frame_positions_m'] = {
        name: [float(v) for v in pos] for name, (pos, _rot) in world.items()
    }
    report['ok'] = not failures
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--urdf', required=True, type=Path)
    parser.add_argument('--meshes', required=True, type=Path)
    parser.add_argument('--validation', type=Path, default=None)
    parser.add_argument('--package-name', default='wamoduck_description')
    parser.add_argument('--rviz-cwd', type=Path, default=Path.cwd(),
                        help='Working directory RViz would be launched from, used to prove '
                             'the mesh references do not depend on it.')
    parser.add_argument('--report', type=Path, default=None)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    report = verify(args.urdf, args.meshes, args.validation, args.package_name, args.rviz_cwd)

    if not args.quiet:
        print('=' * 78)
        print(f'description verification: {report["urdf"]}')
        print('=' * 78)
        for name, entry in report['checks'].items():
            if isinstance(entry, dict) and 'ok' in entry:
                print(f'  [{"PASS" if entry["ok"] else "FAIL"}] {name}')
                if entry['detail']:
                    print(f'          {entry["detail"]}')
                if name == 'counts':
                    print(f'          {entry}')
        for note in report['notes']:
            print(f'  [note] {note}')
        if 'published_bounds_comparison' in report:
            comparison = report['published_bounds_comparison']
            print()
            print('  published zero-pose bounds : '
                  f'{comparison["published_min"]} .. {comparison["published_max"]}')
            print('  best matching variant      : '
                  f'{comparison["best_matching_variant"]} '
                  f'(deviation {comparison["best_max_abs_deviation_m"]:.3e} m)')
        if report['zero_pose_bounds']:
            print()
            for variant, box in report['zero_pose_bounds'].items():
                print(f'  computed bounds [{variant:<9}] : {box["min"]} .. {box["max"]}')
                print(f'  computed size   [{variant:<9}] : {box["size"]}')
        print()
        print(f'  mesh references {report["mesh_references"]}, '
              f'unique meshes {report["unique_meshes"]}, '
              f'triangles {report["triangle_total"]}, '
              f'vertices {report["mesh_vertices_total"]}')
        print()
        print(f'RESULT: {"ALL CHECKS PASSED" if report["ok"] else "FAILED"}')
        for failure in report['failures']:
            print(f'  - {failure}')

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n'
        )
        if not args.quiet:
            print(f'\nreport written to {args.report}')

    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
