"""The policy observation and action contract, as pure functions.

This module contains no ROS and no ONNX. It is the part of ``policy_node`` that can actually
be verified today: the observation layout, the action -> joint permutation, the command
clamp and the target computation. All four are unit-tested.

The contract, restated exactly
-----------------------------
**Observation vector, ONNX input order, 51 wide for the walk task**::

    offset  0  base_ang_vel        3   rad/s, IMU gyro, body frame
    offset  3  projected_gravity   3   unit vector; upright is (0, 0, -1)
    offset  6  joint_pos          14   rad, relative to default_joint_pos (default is all
                                       zeros, so this is the absolute angle)
    offset 20  joint_vel          14   rad/s
    offset 34  last_action        14   the previous raw policy output, BEFORE action_scale
    offset 48  command             3   (vx m/s, vy m/s, wz rad/s)
    ------------------------------------------------------------------------------
    total                         51

The stand policies were trained with **48** inputs: the same layout with the trailing
``command`` block absent. 48 and 51 are therefore not interchangeable, and a single script
cannot hot-swap between them without retraining -- that is a known open item on the training
side, not something the device can paper over.

**Normalisation lives inside the ONNX graph.** Every exported policy carries its own
normalizer as ``Sub``/``Div``/``Elu``/``Gemm`` nodes, so the host feeds **raw** observations.
Normalising again on the device would apply the transform twice and is the single easiest way
to make a policy that trains fine and stands badly.

**The action is in joint-tree order, the same order as the observation.** The policy output is
14 wide and entry ``i`` drives ``JOINT_ORDER[i]``. ``action_to_joint`` is still applied exactly
once, here, on the host -- it is simply the identity now (see the ``model_contract`` module
docstring for the 2026-09-16 adjudication and its four lines of evidence). It is kept as an
explicit permutation so the application site stays in one place and a future order change does
not have to be hunted down through the call graph.

**Target computation**::

    q_target[joint] = default_joint_pos[joint] + action_scale * action[action_index]

With ``default_joint_pos`` all zeros and ``action_scale`` 1.0, this reduces to
``q_target = action``. Both are still applied symbolically so that a future policy with a
non-zero default or a real scale does not need this code to change.

**Timing**: 50 Hz control loop, MuJoCo ``timestep = 0.005 s``, ``decimation = 4``, so
``0.005 * 4 = 0.02 s``. The control period and the physics period are consistent with each
other; a host that runs at 50 Hz against a policy trained at a different decimation is a
silent train/deploy mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .model_contract import (
    ACTION_SCALE,
    ACTION_TO_JOINT,
    COMMAND_RANGES,
    DEFAULT_JOINT_POS,
    JOINT_ORDER,
    N_JOINTS,
    OBS_DIM_WITH_COMMAND,
    OBS_DIM_WITHOUT_COMMAND,
    observation_offsets,
)

OFFSETS = observation_offsets()


def clamp_command(command: Sequence[float]) -> tuple[float, float, float]:
    """Clamp (vx, vy, wz) to the trained ranges.

    The ranges are the final curriculum values, and clamping to them is required: a command
    outside the training distribution is not "a bit faster", it is an instruction the policy
    has never seen, and its response is undefined rather than merely degraded.
    """
    if len(command) != 3:
        raise ValueError("command must be (vx, vy, wz)")
    (x_lo, x_hi) = COMMAND_RANGES["lin_vel_x"]
    (y_lo, y_hi) = COMMAND_RANGES["lin_vel_y"]
    (z_lo, z_hi) = COMMAND_RANGES["ang_vel_z"]
    return (
        min(max(float(command[0]), x_lo), x_hi),
        min(max(float(command[1]), y_lo), y_hi),
        min(max(float(command[2]), z_lo), z_hi),
    )


@dataclass
class ObservationState:
    """Everything the observation needs, in the units the link delivers."""

    base_ang_vel: tuple[float, float, float] = (0.0, 0.0, 0.0)
    projected_gravity: tuple[float, float, float] = (0.0, 0.0, -1.0)
    joint_pos: list[float] = field(default_factory=lambda: [0.0] * N_JOINTS)
    joint_vel: list[float] = field(default_factory=lambda: [0.0] * N_JOINTS)
    last_action: list[float] = field(default_factory=lambda: [0.0] * N_JOINTS)
    command: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def ready(self) -> tuple[bool, list[str]]:
        """Is every block present and the right width?"""
        problems: list[str] = []
        if len(self.joint_pos) != N_JOINTS:
            problems.append(f"joint_pos has {len(self.joint_pos)} entries, expected {N_JOINTS}")
        if len(self.joint_vel) != N_JOINTS:
            problems.append(f"joint_vel has {len(self.joint_vel)} entries, expected {N_JOINTS}")
        if len(self.last_action) != N_JOINTS:
            problems.append(f"last_action has {len(self.last_action)} entries, expected {N_JOINTS}")
        for name in ("base_ang_vel", "projected_gravity", "command"):
            if len(getattr(self, name)) != 3:
                problems.append(f"{name} must have 3 entries")
        return (not problems), problems


def assemble_observation(state: ObservationState, with_command: bool = True) -> list[float]:
    """Build the observation vector in ONNX input order.

    ``with_command=False`` produces the 48-wide layout used by the stand tasks. Nothing is
    normalised here, on purpose: see the module docstring.
    """
    ok, problems = state.ready()
    if not ok:
        raise ValueError("observation state is incomplete: " + "; ".join(problems))

    observation = (
        list(state.base_ang_vel)
        + list(state.projected_gravity)
        + list(state.joint_pos)
        + list(state.joint_vel)
        + list(state.last_action)
    )
    if with_command:
        observation += list(clamp_command(state.command))

    expected = OBS_DIM_WITH_COMMAND if with_command else OBS_DIM_WITHOUT_COMMAND
    if len(observation) != expected:
        raise AssertionError(
            f"assembled observation is {len(observation)} wide, expected {expected}"
        )
    return observation


def projected_gravity_from_quat(quat_wxyz: Sequence[float]) -> tuple[float, float, float]:
    """Gravity direction in the body frame, from a scalar-first unit quaternion.

    Upright gives ``(0, 0, -1)``. This is the same quantity ``docs/16`` uses as the IMU
    sanity check, and it is computed here rather than trusted from the module so that the
    frame convention is explicit and testable.
    """
    if len(quat_wxyz) != 4:
        raise ValueError("quaternion must be (w, x, y, z)")
    w, x, y, z = (float(v) for v in quat_wxyz)
    norm = (w * w + x * x + y * y + z * z) ** 0.5
    if norm <= 0.0:
        raise ValueError("quaternion has zero norm")
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    # Third row of the rotation matrix, negated: gravity in the body frame.
    return (
        -(2.0 * (x * z - w * y)),
        -(2.0 * (y * z + w * x)),
        -(1.0 - 2.0 * (x * x + y * y)),
    )


def action_to_joint_target(action: Sequence[float]) -> list[float]:
    """Turn a raw policy action into a joint-tree-order target.

    The action is already in ``JOINT_ORDER``; ``ACTION_TO_JOINT`` is the identity, so this is
    an element-wise ``default_joint_pos + action_scale * action``. It is written as a
    permutation anyway because that is the *one* place the two orders could disagree, and
    because the raw action must also be returned to the caller as the next ``last_action``
    block -- the observation stores the *unscaled* action, matching training.
    """
    if len(action) != N_JOINTS:
        raise ValueError(f"action must have {N_JOINTS} entries, got {len(action)}")
    target = [0.0] * N_JOINTS
    for action_index, joint in enumerate(ACTION_TO_JOINT):
        target[joint] = DEFAULT_JOINT_POS[joint] + ACTION_SCALE * float(action[action_index])
    return target


def joint_state_to_contract_order(
    joint_names: Sequence[str], positions: Sequence[float], velocities: Sequence[float] | None = None
) -> tuple[list[float], list[float]]:
    """Re-order a JointState message into the contract's ``JOINT_ORDER``.

    A ``sensor_msgs/JointState`` may list joints in any order, and robot_state_publisher
    matches by name. The policy, however, needs a fixed order, so this converts by lookup and
    raises if a contract joint is absent -- a missing joint would otherwise arrive as a silent
    zero, which is indistinguishable from a joint that is genuinely at zero.
    """
    position_by_name = dict(zip(joint_names, positions))
    missing = [name for name in JOINT_ORDER if name not in position_by_name]
    if missing:
        raise KeyError(f"JointState is missing contract joints: {', '.join(missing)}")

    ordered_pos = [float(position_by_name[name]) for name in JOINT_ORDER]

    if velocities is None:
        return ordered_pos, [0.0] * N_JOINTS
    velocity_by_name = dict(zip(joint_names, velocities))
    ordered_vel = [float(velocity_by_name.get(name, 0.0)) for name in JOINT_ORDER]
    return ordered_pos, ordered_vel
