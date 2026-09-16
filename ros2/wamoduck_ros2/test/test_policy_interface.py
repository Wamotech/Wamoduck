"""Tests for the policy observation / action contract.

This is the part of ``policy_node`` that can be verified today: it is pure arithmetic, so it
is tested here rather than left to a claim in a docstring. What is *not* tested anywhere in
this package is ONNX inference -- see ``policy_runner.py``.
"""

from __future__ import annotations

import math

import pytest

from wamoduck_ros2 import model_contract as mc
from wamoduck_ros2.policy_interface import (
    ObservationState,
    action_to_joint_target,
    assemble_observation,
    clamp_command,
    joint_state_to_contract_order,
    projected_gravity_from_quat,
)


# ---------------------------------------------------------------------------
# Observation assembly
# ---------------------------------------------------------------------------


def test_observation_layout_is_pinned_position_by_position():
    state = ObservationState(
        base_ang_vel=(1.0, 2.0, 3.0),
        projected_gravity=(0.0, 0.0, -1.0),
        joint_pos=[10.0 + i for i in range(14)],
        joint_vel=[100.0 + i for i in range(14)],
        last_action=[200.0 + i for i in range(14)],
        command=(0.5, -0.1, 0.2),
    )
    observation = assemble_observation(state, with_command=True)

    assert len(observation) == 51
    assert observation[0:3] == [1.0, 2.0, 3.0]
    assert observation[3:6] == [0.0, 0.0, -1.0]
    assert observation[6:20] == [10.0 + i for i in range(14)]
    assert observation[20:34] == [100.0 + i for i in range(14)]
    assert observation[34:48] == [200.0 + i for i in range(14)]
    assert observation[48:51] == [0.5, -0.1, 0.2]


def test_stand_layout_is_the_same_without_the_command_block():
    state = ObservationState(
        base_ang_vel=(1.0, 2.0, 3.0),
        projected_gravity=(0.0, 0.0, -1.0),
        joint_pos=[10.0 + i for i in range(14)],
        joint_vel=[100.0 + i for i in range(14)],
        last_action=[200.0 + i for i in range(14)],
        command=(0.5, -0.1, 0.2),
    )
    with_command = assemble_observation(state, with_command=True)
    without_command = assemble_observation(state, with_command=False)
    assert len(without_command) == 48
    assert without_command == with_command[:48]


def test_observation_is_not_normalised():
    """The normalizer is inside the exported ONNX graph, so the host must not touch the data.

    A policy whose inputs are unit-magnitude would look "more correct" here if this module
    normalised; it must not. The values that go in are the values the link delivered.
    """
    state = ObservationState(
        base_ang_vel=(12.5, -3.25, 0.125),
        joint_pos=[1.5] * 14,
        joint_vel=[-7.75] * 14,
    )
    observation = assemble_observation(state, with_command=False)
    # Block boundaries, not just "some element is untouched": 0-2 base_ang_vel,
    # 3-5 projected_gravity, 6-19 joint_pos, 20-33 joint_vel.
    assert observation[0] == 12.5
    assert observation[3] == state.projected_gravity[0]
    assert observation[3:6] == list(state.projected_gravity)
    assert observation[6] == 1.5
    assert observation[6:20] == [1.5] * 14
    assert observation[20] == -7.75
    assert observation[20:34] == [-7.75] * 14


def test_command_is_clamped_inside_the_observation():
    state = ObservationState(command=(99.0, -99.0, 99.0))
    observation = assemble_observation(state, with_command=True)
    assert observation[48:51] == [1.0, -0.3, 0.8]


def test_incomplete_state_is_rejected_rather_than_zero_padded():
    state = ObservationState(joint_pos=[0.0] * 13)
    ok, problems = state.ready()
    assert not ok
    assert any("joint_pos" in problem for problem in problems)
    with pytest.raises(ValueError, match="joint_pos"):
        assemble_observation(state)


# ---------------------------------------------------------------------------
# Command clamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "given,expected",
    [
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((1.0, 0.3, 0.8), (1.0, 0.3, 0.8)),
        ((5.0, 5.0, 5.0), (1.0, 0.3, 0.8)),
        ((-5.0, -5.0, -5.0), (-0.6, -0.3, -0.8)),
        ((0.5, -0.1, 0.2), (0.5, -0.1, 0.2)),
    ],
)
def test_clamp_command_uses_the_trained_ranges(given, expected):
    assert clamp_command(given) == pytest.approx(expected)


def test_clamp_command_rejects_the_wrong_width():
    with pytest.raises(ValueError):
        clamp_command([0.0, 0.0])
    with pytest.raises(ValueError):
        clamp_command([0.0, 0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# Action -> joint target
# ---------------------------------------------------------------------------


def test_action_to_joint_target_applies_the_identity_permutation():
    """The action is in joint-tree order, so entry ``i`` targets ``JOINT_ORDER[i]``.

    The action-order adjudication of 2026-09-16 settled this: see ``model_contract``. The
    assertions below were rewritten from the actuator-order reading, which sent entry 1 to
    ``right_hip_yaw``; by name, so a swapped leg is impossible to miss either way.
    """
    action = list(range(14))  # joint-tree order: 0..13
    target = action_to_joint_target(action)
    assert len(target) == 14
    # Default joint positions are all zero and action_scale is 1.0, so the target equals the
    # action.
    by_name = dict(zip(mc.JOINT_ORDER, target))
    assert by_name["left_hip_yaw"] == 0
    assert by_name["left_hip_roll"] == 1
    assert by_name["left_hip_pitch"] == 2
    assert by_name["left_knee"] == 3
    assert by_name["left_ankle"] == 4
    assert by_name["right_hip_yaw"] == 5
    assert by_name["right_hip_roll"] == 6
    assert by_name["right_hip_pitch"] == 7
    assert by_name["right_knee"] == 8
    assert by_name["right_ankle"] == 9
    assert by_name["neck_pitch"] == 10
    assert by_name["head_pitch"] == 11
    assert by_name["head_yaw"] == 12
    assert by_name["head_roll"] == 13
    assert target == [float(i) for i in range(14)]


def test_action_to_joint_target_rejects_the_wrong_width():
    with pytest.raises(ValueError, match="14 entries"):
        action_to_joint_target([0.0] * 15)


def test_zero_action_gives_the_zero_target_which_is_the_cad_standing_pose():
    assert action_to_joint_target([0.0] * 14) == [0.0] * 14


# ---------------------------------------------------------------------------
# JointState -> contract order
# ---------------------------------------------------------------------------


def test_joint_state_is_reordered_into_the_contract_order():
    # Deliberately reversed and missing nothing: the message order carries no information.
    names = list(reversed(mc.JOINT_ORDER))
    positions = [float(i) for i in range(14)]
    velocities = [float(i) * 10 for i in range(14)]
    ordered_pos, ordered_vel = joint_state_to_contract_order(names, positions, velocities)

    assert ordered_pos == [float(13 - i) for i in range(14)]
    assert ordered_vel == [float((13 - i) * 10) for i in range(14)]
    assert ordered_pos[mc.JOINT_INDEX["left_hip_yaw"]] == 13.0
    assert ordered_pos[mc.JOINT_INDEX["head_roll"]] == 0.0


def test_a_missing_contract_joint_is_an_error_not_a_zero():
    names = [n for n in mc.JOINT_ORDER if n != "left_knee"]
    with pytest.raises(KeyError, match="left_knee"):
        joint_state_to_contract_order(names, [0.0] * 13)


def test_velocities_default_to_zero_when_absent():
    positions = [1.0] * 14
    ordered_pos, ordered_vel = joint_state_to_contract_order(list(mc.JOINT_ORDER), positions)
    assert ordered_pos == [1.0] * 14
    assert ordered_vel == [0.0] * 14


def test_extra_joints_in_the_message_are_ignored():
    names = list(mc.JOINT_ORDER) + ["mouth"]
    positions = [1.0] * 14 + [9.0]
    ordered_pos, _ = joint_state_to_contract_order(names, positions)
    assert ordered_pos == [1.0] * 14


# ---------------------------------------------------------------------------
# projected gravity
# ---------------------------------------------------------------------------


def test_upright_gives_minus_z():
    assert projected_gravity_from_quat((1.0, 0.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0, -1.0))


def test_gimbal_agnostic_and_returns_a_unit_vector():
    for angle in (0.0, math.pi / 6, math.pi / 3):
        half = angle / 2
        quat = (math.cos(half), math.sin(half), 0.0, 0.0)
        gravity = projected_gravity_from_quat(quat)
        assert math.sqrt(sum(component * component for component in gravity)) == pytest.approx(1.0)
        # Pure roll about +X leaves the body X axis pointing at gravity's null space, so the
        # gravity projection stays in the YZ plane.
        assert gravity[0] == pytest.approx(0.0)


def test_pitch_90_deg_points_gravity_along_plus_x():
    half = math.pi / 4  # 90 deg pitch
    quat = (math.cos(half), 0.0, math.sin(half), 0.0)
    gravity = projected_gravity_from_quat(quat)
    assert gravity == pytest.approx((1.0, 0.0, 0.0), abs=1e-9)


def test_projected_gravity_rejects_bad_quaternions():
    with pytest.raises(ValueError):
        projected_gravity_from_quat((1.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="zero norm"):
        projected_gravity_from_quat((0.0, 0.0, 0.0, 0.0))
