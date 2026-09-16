#!/usr/bin/env python3
"""Replay a reference gait CSV as ``sensor_msgs/JointState``.

    ros2 run wamoduck_ros2 gait_player --ros-args -p csv_path:=/path/to/gait.csv
    ros2 run wamoduck_ros2 gait_player --loop

What it does
------------
Loads a gait CSV from ``tools/matlab/data/``, reads the movable joint names **out of the
URDF**, matches the CSV's ``q_<joint>`` columns to them by name, and publishes one
``JointState`` per sample at the file's own sample rate. ``robot_state_publisher`` turns that
into TF and RViz draws it.

What it is not
--------------
There is no physics here. This node does not simulate the robot, does not balance it, does
not check foot contact and does not claim the gait is dynamically valid. It is a replay of a
quasi-static kinematic plan, and its only promise is "the description animates at a
verifiable rate". See ``ros2/README.md``.

Joint names and ordering
------------------------
The joint list is read from the URDF at start-up. Nothing is hard-coded and no order is
invented:

* ``JointState.name`` is filled in **URDF document order**, and
  ``robot_state_publisher`` matches joints by name, so the message order is not
  load-bearing here.
* The CSV is matched to the URDF **by name**. If a URDF joint has no ``q_`` column it is
  published at 0.0 and a warning names it; if a ``q_`` column matches no URDF joint it is
  reported and ignored. Both cases are warnings rather than failures because either file may
  legitimately evolve, but neither is silent.
* The trained-policy contract's 14-joint order is a *third* order and is not used here. The
  URDF declares 15 movable joints (the contract omits ``mouth``) and the CSV carries a
  ``q_mouth`` column, so all 15 are animated. That is the honest visualisation of the
  description; it does not change what the policies observe.
"""

from __future__ import annotations

import math
import os
import sys
import time

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster

from . import model_contract
from .gait_csv import finite_difference, load_gait_csv, map_track_to_urdf_joints

DEFAULT_CSV_NAME = 'gait_cycle_2s_50Hz.csv'


def _default_csv_path() -> str:
    try:
        share = get_package_share_directory('wamoduck_ros2')
    except Exception:  # pragma: no cover - only outside a sourced workspace
        return ''
    candidate = os.path.join(share, 'data', DEFAULT_CSV_NAME)
    return candidate if os.path.isfile(candidate) else ''


def _default_urdf_path() -> str:
    try:
        share = get_package_share_directory('wamoduck_description')
    except Exception:  # pragma: no cover
        return ''
    candidate = os.path.join(share, 'urdf', 'wmduck.urdf')
    return candidate if os.path.isfile(candidate) else ''


class GaitPlayer(Node):
    """Publish a JointState stream from a gait CSV, paced by the wall clock."""

    def __init__(self) -> None:
        super().__init__('gait_player')

        self.declare_parameter('csv_path', _default_csv_path())
        self.declare_parameter('urdf_path', _default_urdf_path())
        self.declare_parameter('loop', False)
        self.declare_parameter('time_scale', 1.0)
        self.declare_parameter('start_delay_s', 0.5)
        self.declare_parameter('timer_hz', 0.0)
        self.declare_parameter('publish_base_tf', True)
        self.declare_parameter('world_frame', 'world')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('joint_state_topic', '/joint_states')

        # An empty value means "use the installed default". The launch files forward
        # `urdf_file:=` and `csv_path:=` straight through, and both default to '' there, so
        # treating '' as a hard error would make the documented one-command path fail.
        csv_path = str(self.get_parameter('csv_path').value) or _default_csv_path()
        urdf_path = str(self.get_parameter('urdf_path').value) or _default_urdf_path()
        if not csv_path:
            raise RuntimeError(
                'gait_player: no gait CSV. Pass -p csv_path:=<file>, or build the package so '
                'tools/matlab/data/gait_*.csv is installed into share/wamoduck_ros2/data/.'
            )
        if not urdf_path:
            raise RuntimeError(
                'gait_player: no URDF. Pass -p urdf_path:=<file>, or build '
                'wamoduck_description, which generates it.'
            )

        self._track = load_gait_csv(csv_path)
        self._urdf_joint_names = model_contract.read_urdf_joint_names(urdf_path)
        positions, matched, warnings = map_track_to_urdf_joints(
            self._track, self._urdf_joint_names
        )
        for warning in warnings:
            self.get_logger().warn(warning)

        # JointState.name is filled in URDF document order (see the module docstring). A joint
        # with no CSV column is published at 0.0 -- the URDF's CAD standing pose.
        self._names: list[str] = list(self._urdf_joint_names)
        self._positions: dict[str, tuple[float, ...]] = positions
        self._velocities: dict[str, tuple[float, ...]] = {
            name: finite_difference(values, self._track.times_s)
            for name, values in positions.items()
        }
        self._efforts: dict[str, tuple[float, ...]] = {
            name: self._track.joint_efforts[name]
            for name in positions
            if name in self._track.joint_efforts
        }

        self._times = self._track.times_s
        self._duration = self._track.duration_s
        self._publish_effort = bool(self._efforts)

        native_hz = self._track.nominal_hz or 50.0
        timer_hz = float(self.get_parameter('timer_hz').value) or native_hz
        timer_hz = max(1.0, timer_hz)

        qos = QoSProfile(
            depth=1,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._publisher = self.create_publisher(
            JointState, str(self.get_parameter('joint_state_topic').value), qos
        )
        self._publish_base_tf = bool(self.get_parameter('publish_base_tf').value)
        self._tf_broadcaster = TransformBroadcaster(self) if self._publish_base_tf else None
        self._world_frame = str(self.get_parameter('world_frame').value)
        self._base_frame = str(self.get_parameter('base_frame').value)

        self._t0: float | None = None
        self._finished = False
        self._published = 0
        self._first_sample_wall: float | None = None
        self._last_sample_wall: float | None = None

        self.create_timer(1.0 / timer_hz, self._on_timer)
        self.create_timer(5.0, self._report)

        self._log_startup(csv_path, urdf_path, native_hz, timer_hz, matched)

    # -- start-up reporting -------------------------------------------------

    def _log_startup(
        self, csv_path: str, urdf_path: str, native_hz: float, timer_hz: float, matched: list[str]
    ) -> None:
        log = self.get_logger()
        log.info(f'CSV            : {csv_path}')
        log.info(
            f'                 {self._track.samples} samples, {self._duration:.3f} s, '
            f'{native_hz:.3f} Hz nominal, uniform_dt={self._track.uniform}'
        )
        log.info(f'URDF           : {urdf_path}')
        log.info(
            f'                 {len(self._urdf_joint_names)} movable joints in URDF document order: '
            f'{", ".join(self._urdf_joint_names)}'
        )
        log.info(
            f'publishing     : {len(matched)} CSV-driven joints in URDF order, timer {timer_hz:.1f} Hz'
        )
        log.info(
            f'base TF        : '
            + (
                f'{self._world_frame} -> {self._base_frame} from base_x/y/z + base_roll_rad'
                if self._publish_base_tf
                else 'disabled (set publish_base_tf:=true and use Fixed Frame world in RViz)'
            )
        )
        # Printed, not just logged, because the contract's joint order is a different order
        # from the URDF's and readers of this output are usually checking exactly that.
        log.info(
            'contract check : URDF document order == contract joint_order ? '
            f'{self._urdf_joint_names == list(model_contract.JOINT_ORDER)} '
            '(false is expected and fine; see model_contract.py)'
        )

    # -- playback -----------------------------------------------------------

    def _on_timer(self) -> None:
        now = time.monotonic()

        if self._t0 is None:
            self._t0 = now + max(0.0, float(self.get_parameter('start_delay_s').value))

        time_scale = float(self.get_parameter('time_scale').value) or 1.0
        looping = bool(self.get_parameter('loop').value)

        t_rel = (now - self._t0) * time_scale
        if t_rel < 0.0:
            return

        if t_rel > self._duration + 1e-9:
            if looping:
                self._t0 = now
                t_rel = 0.0
                self.get_logger().info(
                    f'restarting the {self._duration:.3f} s track (loop enabled)'
                )
            else:
                if not self._finished:
                    self._finished = True
                    self._publish(self._track.samples - 1)
                    self.get_logger().info(
                        f'track finished after {self._published} messages of '
                        f'{self._duration:.3f} s; still publishing the last sample, '
                        'pass --loop to repeat'
                    )
                return

        self._publish(self._track.index_at(t_rel))

    def _publish(self, index: int) -> None:
        stamp = self.get_clock().now().to_msg()

        message = JointState()
        message.header.stamp = stamp
        message.header.frame_id = self._base_frame
        message.name = list(self._names)
        message.position = [
            float(self._positions[name][index]) if name in self._positions else 0.0
            for name in self._names
        ]
        message.velocity = [
            float(self._velocities[name][index]) if name in self._velocities else 0.0
            for name in self._names
        ]
        if self._publish_effort:
            message.effort = [
                float(self._efforts[name][index]) if name in self._efforts else 0.0
                for name in self._names
            ]
        self._publisher.publish(message)

        if self._tf_broadcaster is not None and self._track.base:
            transform = TransformStamped()
            transform.header.stamp = stamp
            transform.header.frame_id = self._world_frame
            transform.child_frame_id = self._base_frame
            transform.transform.translation.x = self._base_value('base_x', index)
            transform.transform.translation.y = self._base_value('base_y', index)
            transform.transform.translation.z = self._base_value('base_z', index)
            # The CSV carries base_roll_rad only: no pitch and no yaw. Anything else would
            # be invented. For a flat, straight-line reference gait that is the whole
            # orientation, and it is why the base moves but does not turn.
            roll = self._base_value('base_roll_rad', index)
            half = roll * 0.5
            transform.transform.rotation.x = math.sin(half)
            transform.transform.rotation.y = 0.0
            transform.transform.rotation.z = 0.0
            transform.transform.rotation.w = math.cos(half)
            self._tf_broadcaster.sendTransform(transform)

        self._published += 1
        if self._first_sample_wall is None:
            self._first_sample_wall = time.monotonic()
        self._last_sample_wall = time.monotonic()

    def _base_value(self, key: str, index: int) -> float:
        series = self._track.base.get(key)
        return float(series[index]) if series else 0.0

    def _report(self) -> None:
        """Periodic proof of the achieved rate, which is the thing a viewer cannot judge."""
        if self._published < 2 or self._first_sample_wall is None or self._last_sample_wall is None:
            return
        span = self._last_sample_wall - self._first_sample_wall
        if span <= 0.0:
            return
        achieved = (self._published - 1) / span
        self.get_logger().info(
            f'published {self._published} messages, achieved {achieved:.2f} Hz '
            f'(target {self._track.nominal_hz:.2f} Hz)'
        )


def main(args=None) -> None:
    """Entry point. Accepts a bare ``--loop`` / ``--no-loop`` for convenience.

    ``--loop`` is not a ROS argument, so it is stripped before ``rclpy.init`` and applied as
    the ``loop`` parameter. ``--ros-args -p loop:=true`` works identically; this only saves
    people who are not yet fluent in ROS 2 from having to remember that.
    """
    import rclpy

    argv = list(sys.argv if args is None else args)
    loop_override: bool | None = None
    cleaned: list[str] = []
    for argument in argv:
        if argument == '--loop':
            loop_override = True
        elif argument == '--no-loop':
            loop_override = False
        else:
            cleaned.append(argument)

    rclpy.init(args=cleaned)
    node = GaitPlayer()
    if loop_override is not None:
        node.set_parameters([Parameter('loop', value=loop_override)])
        node.get_logger().info(f'loop set to {loop_override} from the command line')

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
