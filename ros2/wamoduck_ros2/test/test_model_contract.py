"""Tests that the frozen policy contract, the URDF and the generated ROS URDF agree.

The point of these tests is to catch the failure mode where everything loads, everything
starts, and one joint is quietly driven the wrong way. So they check the *agreement* between
the three descriptions of the robot rather than each one in isolation:

* ``model_contract`` -- the frozen 14-joint order, the action permutation, the observation
  layout and the timing, copied from ``deploy/policy_contract.json`` v1;
* ``models/wmduck/wmduck.urdf`` -- the canonical URDF, which declares a *different* order;
* the generated ROS URDF in the package share directory -- which must differ from the
  canonical file only in its mesh URIs.

``ACTION_TO_JOINT`` is the identity as of the 2026-09-16 action-order adjudication (the policy
output is in joint-tree order, not actuator order); the test below pins it as an identity so
that the actuator-order permutation cannot come back by accident. See the ``model_contract``
module docstring for the four independent lines of evidence.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import pytest

from wamoduck_ros2 import model_contract as mc

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_TEST_DIR, os.pardir, os.pardir, os.pardir))
_SOURCE_URDF = os.path.join(_REPO_ROOT, "models", "wmduck", "wmduck.urdf")


def _installed_urdf() -> str | None:
    try:
        from ament_index_python.packages import get_package_share_directory
    except ImportError:
        return None
    try:
        share = get_package_share_directory("wamoduck_description")
    except Exception:
        return None
    candidate = os.path.join(share, "urdf", "wmduck.urdf")
    return candidate if os.path.isfile(candidate) else None


def _require_source_urdf() -> str:
    if not os.path.isfile(_SOURCE_URDF):
        pytest.skip(f"{_SOURCE_URDF} not available (only the ros2/ subtree was copied)")
    return _SOURCE_URDF


# ---------------------------------------------------------------------------
# Contract self-consistency
# ---------------------------------------------------------------------------


def test_contract_has_fourteen_joints_in_tree_order():
    assert len(mc.JOINT_ORDER) == 14
    assert len(set(mc.JOINT_ORDER)) == 14
    # Left leg first, then right leg: the observation block order. The URDF uses a different
    # order, so this assertion is what stops someone "tidying" it into URDF order.
    assert mc.JOINT_ORDER[:5] == (
        "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
    )
    assert mc.JOINT_ORDER[5:10] == (
        "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle",
    )
    assert "mouth" not in mc.JOINT_ORDER


def test_action_to_joint_is_the_identity_and_matches_the_contract():
    """The action output is in joint-tree order, so the permutation is the identity.

    This test used to assert the actuator-order permutation
    ``(0, 5, 1, 6, 2, 7, 3, 8, 4, 9, 10, 11, 12, 13)``. That reading was adjudicated wrong on
    2026-09-16 (source semantics + ONNX metadata + a one-hot MuJoCo probe + a 2x2 ablation);
    the assertions below are what stop it from coming back silently.
    """
    assert sorted(mc.ACTION_TO_JOINT) == list(range(14))
    assert mc.ACTION_TO_JOINT == tuple(range(14))
    # Spelled out, because this is the line that would silently mis-drive a joint: action
    # entry 1 is the LEFT hip roll, not the right hip yaw.
    joint_by_action = [mc.JOINT_ORDER[i] for i in mc.ACTION_TO_JOINT]
    assert joint_by_action == list(mc.JOINT_ORDER)
    # The reading this replaced, kept as a named constant so the difference is explicit and
    # so a future edit that reintroduces it fails here with a readable message.
    actuator_order_reading = (0, 5, 1, 6, 2, 7, 3, 8, 4, 9, 10, 11, 12, 13)
    assert mc.ACTION_TO_JOINT != actuator_order_reading
    # The MJCF actuator order really is L/R interleaved, i.e. the trap is real. If this ever
    # stops being true the two readings coincide and this whole module can be simplified.
    assert actuator_order_reading != tuple(range(14))


def test_observation_offsets_match_the_documented_layout():
    assert mc.observation_offsets() == {
        "base_ang_vel": (0, 3),
        "projected_gravity": (3, 3),
        "joint_pos": (6, 14),
        "joint_vel": (20, 14),
        "last_action": (34, 14),
        "command": (48, 3),
    }
    assert mc.OBS_DIM_WITH_COMMAND == 51
    assert mc.OBS_DIM_WITHOUT_COMMAND == 48


def test_timing_is_self_consistent():
    assert mc.CONTROL_HZ == 50.0
    assert mc.TIMESTEP_S == 0.005
    assert mc.DECIMATION == 4
    # 50 Hz and 0.005 * 4 s are the same statement; a mismatch here is a train/deploy bug.
    assert pytest.approx(mc.TIMESTEP_S * mc.DECIMATION) == 1.0 / mc.CONTROL_HZ


def test_default_joint_pos_and_action_scale_are_the_contract_values():
    assert mc.DEFAULT_JOINT_POS == (0.0,) * 14
    assert mc.ACTION_SCALE == 1.0


def test_command_ranges_are_the_trained_curriculum_values():
    assert mc.COMMAND_RANGES == {
        "lin_vel_x": (-0.6, 1.0),
        "lin_vel_y": (-0.3, 0.3),
        "ang_vel_z": (-0.8, 0.8),
    }
    assert mc.COMMAND_LAYOUT == ("vx_m_s", "vy_m_s", "wz_rad_s")


def test_safety_constants_match_the_protocol_module():
    from wamoduck_ros2 import frame_codec as fc

    assert mc.SAFETY["cmd_timeout_hold_ms"] == fc.CMD_TIMEOUT_HOLD_MS
    assert mc.SAFETY["cmd_timeout_off_ms"] == fc.CMD_TIMEOUT_OFF_MS
    assert mc.SAFETY["max_cmd_jump_rad"] == fc.MAX_CMD_JUMP_RAD


# ---------------------------------------------------------------------------
# Contract vs the canonical URDF
# ---------------------------------------------------------------------------


def test_canonical_urdf_declares_the_joints_the_contract_needs():
    path = _require_source_urdf()
    urdf_joints = mc.read_urdf_joint_names(path)
    assert len(urdf_joints) == 15
    assert len(set(urdf_joints)) == 15
    for name in mc.JOINT_ORDER:
        assert name in urdf_joints, f"contract joint {name!r} missing from the URDF"
    # The one movable joint the 14-joint contract does not use.
    assert sorted(set(urdf_joints) - set(mc.JOINT_ORDER)) == ["mouth"]


def test_urdf_document_order_differs_from_the_contract_order():
    """Documents the trap explicitly: the two orders are NOT the same.

    If a future edit makes them equal, this test fails on purpose -- it means either the URDF
    or the contract changed, and the permutation and the CSV mapping have to be rechecked
    rather than assumed still correct.
    """
    path = _require_source_urdf()
    urdf_joints = mc.read_urdf_joint_names(path)
    assert urdf_joints != list(mc.JOINT_ORDER)
    # URDF order interleaves left/right; the contract groups by leg.
    assert urdf_joints[:4] == [
        "left_hip_yaw", "right_hip_yaw", "left_hip_roll", "right_hip_roll",
    ]


def test_contract_check_report_is_ok():
    path = _require_source_urdf()
    report = mc.check_contract_against_urdf(path)
    assert report["ok"] is True, report
    assert report["contract_joints_missing_from_urdf"] == []
    assert report["urdf_joints_absent_from_contract"] == ["mouth"]
    assert report["action_to_joint_is_permutation"] is True
    assert report["urdf_joint_order_equals_contract"] is False


def test_link_and_joint_counts_match_the_published_validation_record():
    """Cross-check against models/wmduck/validation.json, which is the published record."""
    path = _require_source_urdf()
    import json

    validation_path = os.path.join(os.path.dirname(path), "validation.json")
    if not os.path.isfile(validation_path):
        pytest.skip("validation.json not available")
    with open(validation_path, "r", encoding="utf-8") as handle:
        validation = json.load(handle)

    assert len(mc.read_urdf_links(path)) == validation["urdf_links"] == 17
    assert len(mc.read_urdf_joint_names(path)) == validation["rotational_joints"] == 15
    root = mc.read_urdf_root(path)
    fixed = [j.get("name") for j in root.findall("joint") if j.get("type") == "fixed"]
    assert len(fixed) == validation["fixed_joints"] == 1
    assert root.get("name") == "wmduck"


# ---------------------------------------------------------------------------
# The installed (generated) ROS URDF
# ---------------------------------------------------------------------------


def test_installed_urdf_uses_only_package_uris_for_meshes():
    path = _installed_urdf()
    if path is None:
        pytest.skip("wamoduck_description is not built/installed in this environment")
    text = open(path, "r", encoding="utf-8").read()
    references = re.findall(r'<mesh\b[^>]*?\bfilename="([^"]*)"', text)
    assert references, "the installed URDF references no meshes at all"
    assert len(references) == 79, "the canonical URDF has 79 mesh references"
    for reference in references:
        assert reference.startswith("package://wamoduck_description/meshes/"), reference


def test_installed_urdf_differs_from_the_canonical_urdf_only_in_mesh_uris():
    installed = _installed_urdf()
    if installed is None:
        pytest.skip("wamoduck_description is not built/installed in this environment")
    source = _require_source_urdf()

    def strip_mesh_uris(text: str) -> str:
        return re.sub(
            r'(<mesh\b[^>]*?\bfilename=")[^"]*(")',
            r"\1MESH\2",
            text,
        ).replace("\r\n", "\n")

    a = strip_mesh_uris(open(source, "r", encoding="utf-8").read())
    b = strip_mesh_uris(open(installed, "r", encoding="utf-8").read())
    assert a == b, "the generated URDF differs from the canonical URDF beyond mesh URIs"

    # And the structural summary agrees, which is what the generator itself asserts.
    root_a = ET.fromstring(open(source, "r", encoding="utf-8").read())
    root_b = ET.fromstring(open(installed, "r", encoding="utf-8").read())
    assert [e.get("name") for e in root_a.findall("joint")] == [
        e.get("name") for e in root_b.findall("joint")
    ]
    assert [e.get("name") for e in root_a.findall("link")] == [
        e.get("name") for e in root_b.findall("link")
    ]
