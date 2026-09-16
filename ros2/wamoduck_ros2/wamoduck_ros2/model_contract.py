"""The frozen policy contract, plus the URDF-derived joint list that must agree with it.

Two different "joint orders" exist in this project and confusing them is a known, previously
hit bug class. This module keeps them apart explicitly:

``JOINT_ORDER`` (14 names)
    **Joint-tree order.** The order of ``joint_pos`` / ``joint_vel`` inside the policy
    observation, the order of ``q`` / ``dq`` in every link frame, and -- since the
    adjudication below -- **also the order of the policy's 14-wide action output**.
    Taken from ``deploy/policy_contract.json``.

``ACTION_TO_JOINT`` (14 indices)
    The permutation from the policy's output order to joint-tree order. ``action_to_joint[i]``
    is the joint index that action entry ``i`` drives. It is applied exactly once, on the
    host. It is the **identity**, because the policy output is in joint-tree order; it is
    kept as an explicit permutation, rather than deleted, so the single application site in
    ``policy_interface.action_to_joint_target()`` stays exactly where it is and a future
    order change has one place to land.

``read_urdf_joints()``
    The movable joints **as they appear in the URDF file**, in document order. This is a
    third order and it is *not* either of the above: the canonical URDF lists the legs
    interleaved (``left_hip_yaw, right_hip_yaw, left_hip_roll, right_hip_roll, ...``) while
    the contract lists them left-leg-then-right-leg.

Action order was adjudicated on 2026-09-16: it is joint-tree order
----------------------------------------------------------------
This module used to read the 14-wide action output in **actuator order** (MJCF ``<actuator>``
order), which contradicted ``wamoduck_sim.py`` and ``docs/simulation.md``. That contradiction
is settled, in favour of joint-tree order, on four independent lines of evidence:

1. **Source semantics.** mjlab's ``Entity.find_joints_by_actuator_names`` builds
   ``actuated_in_natural_order`` as a *filter of* ``joint_names`` (joint-tree order) and then
   calls ``resolve_matching_names(..., preserve_order=False)``, which returns matches in the
   order of that target list; the actuator-name keys are only a filter. ``BaseAction.
   _find_targets`` does not even forward ``preserve_order`` for joint transmissions. Running
   the real mjlab resolver against the training MJCF returns ``target_ids = [0 .. 13]``.
2. **ONNX metadata.** Every published policy in ``policies/`` records ``joint_names`` as
   ``left_hip_yaw, left_hip_roll, ..., head_roll`` -- joint-tree order.
3. **One-hot probe (direct observation).** Driving one action channel at a time through
   ``q_target = default_joint_pos + action_scale * action`` and reading which joint actually
   moves yields the identity permutation: channel ``i`` moves ``JOINT_ORDER[i]`` and nothing
   else (every row and column exactly one dominant entry, dominance at least 140x). The
   actuator-order reading moves a *different* joint for channels 1 to 8, so the two readings
   are physically distinguishable.
4. **Behaviour.** A 2x2 ablation over observation order x action order shows that only
   tree/tree stands, walks, crouches and gets up, for all five published policies; every
   wiring with either half swapped collapses within a second.

The practical consequence for a host: the permutation to apply is the identity. The remaining
real trap is the URDF-document-order one, which is what the rest of this module is about.

Nothing here re-derives the contract from the URDF, and nothing re-derives the URDF from the
contract. They are checked against each other by ``test_model_contract.py``, and any
disagreement fails the test suite instead of silently mis-driving a joint.

Facts pinned here and where they come from:

===================================  ====================================================
control rate                         50 Hz (``CONTROL_HZ``)
MuJoCo timestep                      0.005 s (``TIMESTEP_S``)
decimation                           4 (``DECIMATION``) -> 0.005 * 4 = 0.02 s = 50 Hz
observation dimension                51 for the walk tasks, 48 for the stand tasks
policy output dimension              14, **joint-tree order** (was documented as
                                     actuator order until the 2026-09-16 adjudication)
``default_joint_pos``                all zeros, so an absolute joint angle and a
                                     joint angle relative to default are the same number
``action_scale``                     ``[1.0]`` (single element -> broadcast)
normalisation                        **inside the ONNX graph**; the host must feed raw
                                     observations and must not normalise again
===================================  ====================================================
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Frozen contract values (deploy/policy_contract.json, contract_version 1)
# ---------------------------------------------------------------------------

JOINT_ORDER: tuple[str, ...] = (
    "left_hip_yaw",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee",
    "left_ankle",
    "right_hip_yaw",
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee",
    "right_ankle",
    "neck_pitch",
    "head_pitch",
    "head_yaw",
    "head_roll",
)

JOINT_INDEX: dict[str, int] = {name: i for i, name in enumerate(JOINT_ORDER)}

# action index -> joint index. Both the policy output and the observation are in joint-tree
# order, so this is the identity. It is spelled out rather than written as ``range(14)``
# because it is the one line to change if the order is ever re-adjudicated, and because a
# reader must be able to see at a glance that it is the identity and not the actuator-order
# permutation ``(0, 5, 1, 6, 2, 7, 3, 8, 4, 9, 10, 11, 12, 13)`` that used to be here.
ACTION_TO_JOINT: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)

N_JOINTS = len(JOINT_ORDER)

CONTROL_HZ = 50.0
TIMESTEP_S = 0.005
DECIMATION = 4

DEFAULT_JOINT_POS: tuple[float, ...] = (0.0,) * N_JOINTS
ACTION_SCALE: float = 1.0

# Observation blocks in ONNX input order. Offsets are cumulative.
OBSERVATION_BLOCKS: tuple[tuple[str, int], ...] = (
    ("base_ang_vel", 3),
    ("projected_gravity", 3),
    ("joint_pos", N_JOINTS),
    ("joint_vel", N_JOINTS),
    ("last_action", N_JOINTS),
    ("command", 3),
)
OBS_DIM_WITH_COMMAND = sum(size for _, size in OBSERVATION_BLOCKS)  # 51
OBS_DIM_WITHOUT_COMMAND = OBS_DIM_WITH_COMMAND - 3                  # 48

# Trained command ranges (final curriculum values). The device side must clamp to these.
COMMAND_RANGES: dict[str, tuple[float, float]] = {
    "lin_vel_x": (-0.6, 1.0),
    "lin_vel_y": (-0.3, 0.3),
    "ang_vel_z": (-0.8, 0.8),
}
COMMAND_LAYOUT = ("vx_m_s", "vy_m_s", "wz_rad_s")

# Safety limits that the link contract requires both sides to honour.
SAFETY = {
    "cmd_timeout_hold_ms": 200,
    "cmd_timeout_off_ms": 1000,
    "max_cmd_jump_rad": 0.35,
}

# The trained-policy contract has no `mouth` axis; the URDF models one anyway.
NON_CONTRACT_URDF_JOINTS = ("mouth",)

MOVABLE_JOINT_TYPES = ("revolute", "continuous", "prismatic", "planar", "floating")


def observation_offsets() -> dict[str, tuple[int, int]]:
    """``{block name: (offset, size)}`` for the observation vector."""
    offsets: dict[str, tuple[int, int]] = {}
    cursor = 0
    for name, size in OBSERVATION_BLOCKS:
        offsets[name] = (cursor, size)
        cursor += size
    return offsets


# ---------------------------------------------------------------------------
# URDF side
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UrdfJoint:
    """One movable joint, as declared in the URDF."""

    name: str
    type: str
    index: int


def read_urdf_root(urdf_path: str | Path) -> ET.Element:
    """Parse a URDF file and return the ``<robot>`` element."""
    path = Path(urdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"URDF not found: {path}")
    try:
        return ET.fromstring(path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:  # pragma: no cover - only on a corrupt file
        raise ValueError(f"{path} is not well-formed XML: {exc}") from exc


def read_urdf_joints(urdf_path: str | Path) -> list[UrdfJoint]:
    """Movable joints in **URDF document order**.

    This is what a node must use to drive a JointState message: it maps by *name*, so the
    order only affects the message layout, but reading it from the file means no order is
    ever invented or hard-coded in a node.
    """
    root = read_urdf_root(urdf_path)
    joints: list[UrdfJoint] = []
    for element in root.findall("joint"):
        jtype = element.get("type", "")
        if jtype in MOVABLE_JOINT_TYPES:
            joints.append(UrdfJoint(name=element.get("name", ""), type=jtype, index=len(joints)))
    return joints


def read_urdf_joint_names(urdf_path: str | Path) -> list[str]:
    """Movable joint names in URDF document order."""
    return [joint.name for joint in read_urdf_joints(urdf_path)]


def read_urdf_links(urdf_path: str | Path) -> list[str]:
    return [element.get("name", "") for element in read_urdf_root(urdf_path).findall("link")]


def check_contract_against_urdf(urdf_path: str | Path) -> dict:
    """Cross-check the frozen contract against a URDF and return a findings report.

    The report never raises; ``test_model_contract.py`` asserts ``ok``, and the same report
    is a useful thing to log at node start-up so that a mismatched description is visible
    immediately instead of after a robot misbehaves.
    """
    urdf_joint_names = read_urdf_joint_names(urdf_path)
    urdf_set = set(urdf_joint_names)
    contract_set = set(JOINT_ORDER)

    findings: dict[str, object] = {
        "urdf_path": str(urdf_path),
        "urdf_movable_joints_in_document_order": urdf_joint_names,
        "contract_joint_order": list(JOINT_ORDER),
        "urdf_joint_order_equals_contract": urdf_joint_names == list(JOINT_ORDER),
        "contract_joints_missing_from_urdf": sorted(contract_set - urdf_set),
        "urdf_joints_absent_from_contract": sorted(urdf_set - contract_set),
        "action_to_joint_is_permutation": sorted(ACTION_TO_JOINT) == list(range(N_JOINTS)),
        "obs_dim_with_command": OBS_DIM_WITH_COMMAND,
        "obs_dim_without_command": OBS_DIM_WITHOUT_COMMAND,
    }
    findings["ok"] = (
        not findings["contract_joints_missing_from_urdf"]
        and findings["action_to_joint_is_permutation"]
        and OBS_DIM_WITH_COMMAND == 51
        and OBS_DIM_WITHOUT_COMMAND == 48
        and urdf_set - contract_set == set(NON_CONTRACT_URDF_JOINTS)
    )
    return findings
