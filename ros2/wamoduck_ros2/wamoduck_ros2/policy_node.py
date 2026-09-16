#!/usr/bin/env python3
"""50 Hz policy node: observation -> ONNX -> joint target. **Skeleton this stage.**

    ros2 run wamoduck_ros2 policy_node --ros-args -p onnx_path:=<policy.onnx>

STATUS -- read before relying on anything this node prints
----------------------------------------------------------
This node is an interface skeleton, as agreed for this stage of the ROS 2 work. What is
implemented and unit-tested is the *contract*: the observation layout, the command clamp,
the actuator -> joint permutation and the target computation
(``wamoduck_ros2/policy_interface.py``). What is **not** done and not verified:

* no ONNX policy has been loaded or executed on any machine in this ROS 2 tree;
  ``onnxruntime`` is not installed and ``policy_runner.py`` raises a clear error if reached;
* the node therefore never publishes a real ``JointTarget``;
* it has not been run against the real link, the real IMU or real hardware.

Everything below is written against ``deploy/policy_contract.json`` v1 and
``docs/16_真机部署方案.md`` §6.5. The numbers are quoted from those files, not measured here.

THE OBSERVATION / ACTION CONTRACT (frozen, changed only by regenerating the contract)
------------------------------------------------------------------------------------
**51-dimensional observation for the walk tasks**, in ONNX input order::

    base_ang_vel(3) | projected_gravity(3) | joint_pos(14) | joint_vel(14) | last_action(14) | command(3)

with offsets::

    0  base_ang_vel        3   rad/s, IMU gyro, body frame
    3  projected_gravity   3   unit vector, gravity in the body frame; upright is (0, 0, -1)
    6  joint_pos          14   rad; relative to default_joint_pos, which is all zeros, so
                               this is the absolute joint angle
    20 joint_vel          14   rad/s
    34 last_action        14   the previous raw policy output, BEFORE action_scale is applied
    48 command             3   (vx m/s, vy m/s, wz rad/s), clamped to the trained ranges
                               x[-0.6, 1.0]  y[-0.3, 0.3]  wz[-0.8, 0.8]

Total 51. The **stand** policies were trained with **48** inputs: the same layout with the
trailing ``command`` block absent. 48 and 51 are not interchangeable.

**The ONNX graph contains its own normalizer** (``Sub``/``Div``/``Elu``/``Gemm``; the
contract records ``normalizer_inside_onnx: true``). The host therefore feeds **raw**
observations. Normalising again on this side would apply the transform twice -- the classic
way to get a policy that trains well and stands badly.

**The action is 14 wide and in actuator order** (MJCF ``<actuator>`` order), which is *not*
the joint-tree order of the observation. ``action_to_joint`` in
``deploy/policy_contract.json``, mirrored as ``model_contract.ACTION_TO_JOINT``, is applied
exactly once, here, on the host. The firmware only needs to map its own CAN IDs onto the 14
array slots.

**Target computation**::

    q_target[joint] = default_joint_pos[joint] + action_scale * action[actuator]

with ``default_joint_pos`` = all zeros and ``action_scale`` = 1.0 for the current policies,
so in practice ``q_target = action``. It is still written symbolically so a future policy
with a non-zero default does not require editing logic.

**Timing**: control rate **50 Hz**; MuJoCo ``timestep`` = **0.005 s**; ``decimation`` = **4**,
so the policy acts every ``0.005 * 4 = 0.02 s``. 50 Hz and 0.02 s are the same statement and
must stay consistent.

Engineering rules this node must follow (``docs/16`` §6.5)
----------------------------------------------------------
1. **State topics use BEST_EFFORT + KEEP_LAST(1).** With RELIABLE and a queue deeper than
   one, a single slow callback leaves stale observations queued and the policy then reasons
   about tens-of-milliseconds-old state. The symptom is "sluggish and oscillating", and it
   is very hard to find after the fact. Command topics are the opposite: reliable, and
   ``JointTarget`` is published at a fixed 50 Hz so a drop is visible as a sequence gap.
2. **The 50 Hz callback does exactly three things**: take the newest state, infer, publish
   the target. No logging to disk, no parameter service calls, no TF lookups. Logging runs on
   its own timer.
3. **Start-up order matters**: the bridge and the safety side come up first, the policy last.
   A policy that is not ready leaves the cerebellum on its watchdog (HOLD at 200 ms, OFF at
   1000 ms). That is the intended failure mode, not a bug to be designed around.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, JointState

from wamoduck_msgs.msg import JointTarget

from . import model_contract
from .policy_interface import (
    ObservationState,
    action_to_joint_target,
    assemble_observation,
    joint_state_to_contract_order,
    projected_gravity_from_quat,
)
from .policy_runner import PolicyRunner, PolicyRunnerUnavailable

# State inputs: best effort, depth 1. See rule 1 in the module docstring.
STATE_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)

# Command outputs: reliable, depth 1 -- the newest target supersedes the previous one, and a
# gap in the 50 Hz stream is information the other end needs.
COMMAND_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
)


class PolicyNode(Node):
    """Assemble the observation, run the policy, publish a joint target."""

    def __init__(self) -> None:
        super().__init__('policy_node')

        self.declare_parameter('onnx_path', '')
        self.declare_parameter('control_hz', model_contract.CONTROL_HZ)
        self.declare_parameter('joint_state_topic', '/joint_states')
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('target_topic', '/wmduck/joint_target')
        self.declare_parameter('command_vx', 0.0)
        self.declare_parameter('command_vy', 0.0)
        self.declare_parameter('command_wz', 0.0)
        self.declare_parameter('dry_run', True)
        self.declare_parameter('state_timeout_s', 0.2)

        self._state = ObservationState()
        self._last_state_wall = None
        self._runner: PolicyRunner | None = None
        self._targets_published = 0
        self._ticks = 0

        self.create_subscription(
            JointState,
            str(self.get_parameter('joint_state_topic').value),
            self._on_joint_state,
            STATE_QOS,
        )
        self.create_subscription(
            Imu, str(self.get_parameter('imu_topic').value), self._on_imu, STATE_QOS
        )
        self._target_publisher = self.create_publisher(
            JointTarget, str(self.get_parameter('target_topic').value), COMMAND_QOS
        )

        control_hz = float(self.get_parameter('control_hz').value) or model_contract.CONTROL_HZ
        if abs(control_hz - model_contract.CONTROL_HZ) > 1e-9:
            self.get_logger().warn(
                f'control_hz is {control_hz} Hz but the policies were trained at '
                f'{model_contract.CONTROL_HZ} Hz (timestep {model_contract.TIMESTEP_S} s x '
                f'decimation {model_contract.DECIMATION}). A different rate is a train/deploy '
                'mismatch, not a tuning knob.'
            )
        self.create_timer(1.0 / control_hz, self._on_control_tick)
        self.create_timer(5.0, self._report)

        self._log_contract(control_hz)
        self._maybe_load_policy()

    # -- contract reporting -------------------------------------------------

    def _log_contract(self, control_hz: float) -> None:
        log = self.get_logger()
        offsets = model_contract.observation_offsets()
        layout = ' | '.join(
            f'{name}({size})@{offset}' for name, (offset, size) in offsets.items()
        )
        log.info(f'observation layout : {layout}  = {model_contract.OBS_DIM_WITH_COMMAND}')
        log.info(
            f'observation dims   : {model_contract.OBS_DIM_WITH_COMMAND} (walk, command block '
            f'present) / {model_contract.OBS_DIM_WITHOUT_COMMAND} (stand, command block absent)'
        )
        log.info(
            'normalisation      : inside the ONNX graph -> this node feeds RAW observations'
        )
        log.info(
            'joint order        : observation and link are joint-tree order; the action is '
            'actuator order and is permuted once via action_to_joint'
        )
        log.info(
            f'timing             : {control_hz} Hz control, timestep '
            f'{model_contract.TIMESTEP_S} s x decimation {model_contract.DECIMATION}'
        )
        ok, problems = self._state.ready()
        log.info(f'observation state  : ready={ok} {problems if problems else ""}')

    def _maybe_load_policy(self) -> None:
        onnx_path = str(self.get_parameter('onnx_path').value)
        if not onnx_path:
            self.get_logger().warn(
                'no onnx_path given; running as a skeleton that assembles observations but '
                'never infers. See the module docstring for what is and is not implemented.'
            )
            return
        self._runner = PolicyRunner(onnx_path)
        try:
            self._runner.load()
        except PolicyRunnerUnavailable as exc:
            self.get_logger().error(str(exc))
            self._runner = None
            return
        self.get_logger().info(
            f'loaded policy {onnx_path}: obs_dim={self._runner.obs_dim}, '
            f'action_dim={self._runner.action_dim}, uses_command={self._runner.uses_command}'
        )

    # -- subscriptions ------------------------------------------------------

    def _on_joint_state(self, message: JointState) -> None:
        try:
            positions, velocities = joint_state_to_contract_order(
                message.name, message.position, message.velocity
            )
        except KeyError as exc:
            self.get_logger().error(f'{exc}', throttle_duration_sec=5.0)
            return
        self._state.joint_pos = positions
        self._state.joint_vel = velocities
        self._last_state_wall = self.get_clock().now().nanoseconds * 1e-9

    def _on_imu(self, message: Imu) -> None:
        self._state.base_ang_vel = (
            message.angular_velocity.x,
            message.angular_velocity.y,
            message.angular_velocity.z,
        )
        orientation = message.orientation
        if any((orientation.x, orientation.y, orientation.z, orientation.w)):
            try:
                self._state.projected_gravity = projected_gravity_from_quat(
                    (orientation.w, orientation.x, orientation.y, orientation.z)
                )
            except ValueError as exc:
                self.get_logger().error(f'bad IMU orientation: {exc}', throttle_duration_sec=5.0)

    # -- control loop -------------------------------------------------------

    def _on_control_tick(self) -> None:
        """Rule 2: take the newest state, infer, publish. Nothing else belongs here."""
        self._ticks += 1

        timeout = float(self.get_parameter('state_timeout_s').value)
        if self._last_state_wall is None:
            self.get_logger().warn(
                'no JointState received yet; not publishing a target', throttle_duration_sec=5.0
            )
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        age = now - self._last_state_wall
        if age > timeout:
            self.get_logger().warn(
                f'newest JointState is {age * 1e3:.0f} ms old (> {timeout * 1e3:.0f} ms); '
                'not publishing a target. The cerebellum watchdog handles a silent host.',
                throttle_duration_sec=5.0,
            )
            return

        if self._runner is None:
            # Skeleton path: prove the observation assembles, then stop. This is the boundary
            # between "implemented" and "not implemented" for this stage.
            try:
                assemble_observation(self._state, with_command=True)
            except ValueError as exc:
                self.get_logger().error(f'observation incomplete: {exc}', throttle_duration_sec=5.0)
            return

        observation = assemble_observation(self._state, with_command=self._runner.uses_command)
        action = self._runner.infer(observation)
        self._state.last_action = list(action)
        target = action_to_joint_target(action)
        self._publish_target(target)

    def _publish_target(self, target_rad: list[float]) -> None:
        message = JointTarget()
        message.header.stamp = self.get_clock().now().to_msg()
        message.mode = JointTarget.MODE_POLICY
        message.flags = 0
        message.t_ms = int(self.get_clock().now().nanoseconds // 1_000_000) & 0xFFFFFFFF
        message.q_target_rad = [float(value) for value in target_rad]
        message.twist = [
            float(self.get_parameter('command_vx').value),
            float(self.get_parameter('command_vy').value),
            float(self.get_parameter('command_wz').value),
        ]
        self._target_publisher.publish(message)
        self._targets_published += 1

    def _report(self) -> None:
        self.get_logger().info(
            f'ticks={self._ticks}, targets published={self._targets_published}, '
            f'policy={"loaded" if self._runner else "not loaded (skeleton)"}'
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PolicyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
