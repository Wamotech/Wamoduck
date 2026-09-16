#!/usr/bin/env python3
"""Bridge between a byte transport (/dev/ttyS1 or CAN) and ROS topics. **Skeleton + codec.**

    ros2 run wamoduck_ros2 bridge_stub                       # loopback, no hardware needed
    ros2 run wamoduck_ros2 bridge_stub --ros-args -p transport:=serial -p port:=/dev/ttyS1

Division of labour (``docs/16_真机部署方案.md`` §6.5)
----------------------------------------------------
This node is the *only* place that knows the wire format. Everything above it speaks
``wamoduck_msgs/JointTarget`` downwards and ``sensor_msgs/JointState`` / ``sensor_msgs/Imu``
upwards, so swapping UART for CAN-FD changes this node's transport and nothing else. That
separation is the reason the frame codec lives in its own ROS-free module and is the one part
of this package with real unit tests.

Signal flow::

    JointTarget  -> pack CMD (46 B)          -> transport -> cerebellum
    JointState   <- unpack STATE_Q, STATE_DQ <- transport <- cerebellum
    Imu          <- unpack STATE_IMU         <- transport <- cerebellum
    LinkStatus   <- parser counters + status word

What is implemented and verified
--------------------------------
* the complete frame codec: encode/decode for every frame type, CRC16-CCITT-FALSE with its
  known-answer vector, frame-size assertions, int16 saturation, and a resynchronising parser
  with separate resync / bad-length / bad-CRC counters. Covered by
  ``test/test_frame_codec.py``.
* the topic plumbing for the loopback transport, which needs no hardware.

What is NOT implemented and NOT verified
----------------------------------------
* **no hardware has been touched.** The ``serial`` transport opens a pyserial port but has
  never been run against an AT32; the ``can`` transport is not written at all.
* the cerebellum-side protection layer (200 ms HOLD / 1000 ms OFF / 0.35 rad per-frame rate
  limit / limit clamping) is *specified* in the protocol and is **not** reimplemented here:
  per the design it lives in the firmware, and the host must not duplicate it, because two
  watchdogs with different timeouts is worse than one. Only the host-side ESTOP latch and the
  status-word relay exist.
* no watchdog, no diagnostics aggregation, no ``wmduck_safety`` node yet. ``docs/16`` §6.5
  lists it as a separate node and it is a later stage.
"""

from __future__ import annotations

import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, JointState
from std_msgs.msg import Bool

from wamoduck_msgs.msg import JointTarget, LinkStatus

from . import frame_codec as fc
from . import model_contract

# State topics: best effort, depth 1. A queued stale state is worse than a dropped one.
STATE_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)

COMMAND_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
)


class LoopbackTransport:
    """In-process transport: whatever is written comes straight back on the next read.

    Exists so that the topic plumbing, the watchdog bookkeeping and the counters can be
    exercised end to end without an AT32 on the bench. It is not a simulator: it does not
    apply gains, gravity or limits, and it echoes the commanded joints back as if the servos
    tracked perfectly. Never read dynamics into what it shows.
    """

    def __init__(self) -> None:
        self._pending = bytearray()
        self._last_cmd = None
        self.open = True
        self.description = 'loopback (echoes CMD back as STATE_Q; not a simulator)'

    def write(self, data: bytes) -> None:
        frames = list(fc.FrameParser().feed(bytes(data)))
        for frame in frames:
            if frame.type == fc.TYPE_CMD:
                self._last_cmd = fc.unpack_cmd(frame.payload)
            elif frame.type == fc.TYPE_ESTOP:
                self._last_cmd = None
            else:
                continue
        if self._last_cmd is not None and frames:
            payload = fc.pack_state_q(
                self._last_cmd['q_target'],
                age_ms=1,
                status=fc.ST_ENABLED | fc.ST_POLICY_MODE,
            )
            self._pending.extend(fc.pack_frame(fc.TYPE_STATE_Q, payload, seq=frames[-1].seq))

    def read(self) -> bytes:
        data = bytes(self._pending)
        self._pending.clear()
        return data

    def close(self) -> None:
        self.open = False


class SerialTransport:
    """UART transport over pyserial.

    Untested against hardware: pyserial is an optional dependency and the AT32 side does not
    exist in this repository. 921600 8N1 is the documented line rate, at which the 106 B
    uplink round is 23 % of the available bandwidth at 200 Hz.
    """

    def __init__(self, port: str, baudrate: int = 921600) -> None:
        try:
            import serial  # noqa: PLC0415 -- optional, only needed on the real link
        except ImportError as exc:
            raise RuntimeError(
                'transport:=serial needs pyserial: pip install pyserial'
            ) from exc
        self._serial = serial.Serial(
            port, baudrate=baudrate, timeout=0.0, bytesize=8, parity='N', stopbits=1
        )
        self._serial.reset_input_buffer()
        self.open = True
        self.description = f'serial {port} @ {baudrate} 8N1 (never exercised against hardware)'

    def write(self, data: bytes) -> None:
        self._serial.write(data)

    def read(self) -> bytes:
        waiting = self._serial.in_waiting
        return self._serial.read(waiting) if waiting else b''

    def close(self) -> None:
        self._serial.close()
        self.open = False


class CanTransport:
    """CAN-FD transport. Not implemented.

    Every frame payload is <= 64 B, so the identical framing fits one frame per CAN message
    with no upper-layer change; only this class would need writing. Left as an explicit gap
    rather than a silently-empty stub, because a bridge that accepts ``transport:=can`` and
    then never moves is worse than one that refuses to start.
    """

    def __init__(self, channel: str = 'can0', bitrate: int = 1_000_000) -> None:
        raise NotImplementedError(
            'the CAN-FD transport is not implemented yet. Payloads are all <= 64 B, so the '
            'framing already fits one CAN-FD message per frame; implement CanTransport '
            '(python-can) and nothing above it changes.'
        )


def make_transport(kind: str, port: str) -> object:
    if kind == 'loopback':
        return LoopbackTransport()
    if kind == 'serial':
        return SerialTransport(port)
    if kind == 'can':
        return CanTransport(port)
    raise ValueError(f'unknown transport {kind!r}; expected loopback, serial or can')


class BridgeStub(Node):
    """Encode JointTarget to frames, decode frames back into JointState/Imu/LinkStatus."""

    def __init__(self) -> None:
        super().__init__('bridge_stub')

        self.declare_parameter('transport', 'loopback')
        self.declare_parameter('port', '/dev/ttyS1')
        self.declare_parameter('target_topic', '/wmduck/joint_target')
        self.declare_parameter('joint_state_topic', '/joint_states')
        self.declare_parameter('imu_topic', '/imu/data')
        self.declare_parameter('status_topic', '/wmduck/link_status')
        self.declare_parameter('estop_topic', '/wmduck/estop')
        self.declare_parameter('read_period_s', 0.002)
        # JointState.header.frame_id. Convention is the base frame the angles are measured
        # against, not the world.
        self.declare_parameter('base_frame', 'base_link')

        kind = str(self.get_parameter('transport').value)
        port = str(self.get_parameter('port').value)
        try:
            self._transport = make_transport(kind, port)
        except (NotImplementedError, RuntimeError, ValueError) as exc:
            # Refuse to start rather than run a bridge that silently moves nothing.
            raise RuntimeError(f'bridge_stub: {exc}') from exc

        self._parser = fc.FrameParser()
        self._seq = 0
        self._rx_frames = 0
        self._tx_frames = 0
        self._latest_status = 0
        self._latest_age_ms = 0
        self._estop_latched = False

        # The cerebellum reports angles and velocities in *separate* frames (STATE_Q at
        # 200 Hz, STATE_DQ at 200 Hz) so that each fits one CAN-FD message and each can be
        # rate-reduced independently. JointState, on the other hand, is consumed position by
        # position by robot_state_publisher, so the latest of each is cached here and
        # republished together rather than emitting half-filled messages.
        self._latest_q: list[float] | None = None
        self._latest_dq: list[float] | None = None

        # The link array order is the contract's joint-tree order, not the URDF document
        # order: this is what makes "action (actuator order) -> joint" a single permutation.
        self._joint_names = list(model_contract.JOINT_ORDER)

        self.create_subscription(
            JointTarget,
            str(self.get_parameter('target_topic').value),
            self._on_target,
            COMMAND_QOS,
        )
        self.create_subscription(
            Bool, str(self.get_parameter('estop_topic').value), self._on_estop, COMMAND_QOS
        )
        self._joint_publisher = self.create_publisher(
            JointState, str(self.get_parameter('joint_state_topic').value), STATE_QOS
        )
        self._imu_publisher = self.create_publisher(
            Imu, str(self.get_parameter('imu_topic').value), STATE_QOS
        )
        self._status_publisher = self.create_publisher(
            LinkStatus, str(self.get_parameter('status_topic').value), STATE_QOS
        )

        period = max(0.0005, float(self.get_parameter('read_period_s').value))
        self.create_timer(period, self._pump_rx)
        self.create_timer(1.0, self._publish_status)

        self.get_logger().info(f'transport       : {self._transport.description}')
        self.get_logger().info(
            f'CMD frame is {fc.CMD_FRAME_LEN} B '
            f'({fc.CMD_PAYLOAD_LEN} B payload + {fc.FRAME_OVERHEAD} B framing); '
            f'q in joint-tree order, int16 mrad (scale {fc.Q_SCALE:g})'
        )
        self.get_logger().info(
            'cerebellum protection (200 ms HOLD / 1000 ms OFF / 0.35 rad per frame) lives in '
            'the firmware and is deliberately NOT duplicated here'
        )
        self.get_logger().warn(
            'SKELETON: no hardware in the loop, no safety node, no CAN transport. '
            'See the module docstring for exactly what is and is not implemented.'
        )

    # -- downlink -----------------------------------------------------------

    def _on_target(self, message: JointTarget) -> None:
        if self._estop_latched:
            self.get_logger().warn('ESTOP latched; dropping targets', throttle_duration_sec=5.0)
            return

        if len(message.q_target_rad) != fc.N_JOINTS:
            self.get_logger().error(
                f'JointTarget has {len(message.q_target_rad)} joints, expected {fc.N_JOINTS}'
            )
            return

        q_ints, saturated = fc.quantise_i16(message.q_target_rad, fc.Q_SCALE)
        if saturated:
            joints = ', '.join(self._joint_names[i] for i in saturated)
            self.get_logger().warn(
                f'q_target saturated at int16 mrad for: {joints} '
                f'(limit {32767 / fc.Q_SCALE:.3f} rad). Saturation clamps; it never wraps.'
            )

        twist = tuple(message.twist) if len(message.twist) == 3 else (0.0, 0.0, 0.0)
        payload = fc.pack_cmd(
            message.q_target_rad,
            mode=message.mode if message.mode else fc.MODE_POLICY,
            twist=twist,
            t_ms=message.t_ms,
            flags=message.flags,
        )
        frame = fc.pack_frame(fc.TYPE_CMD, payload, seq=self._seq)
        self._seq = (self._seq + 1) & 0xFF
        try:
            self._transport.write(frame)
        except Exception as exc:  # pragma: no cover - transport-level failure
            self.get_logger().error(f'transport write failed: {exc}')
            return
        self._tx_frames += 1

    def _on_estop(self, message: Bool) -> None:
        if not message.data:
            self._estop_latched = False
            self.get_logger().warn('ESTOP cleared')
            return
        self._estop_latched = True
        try:
            self._transport.write(fc.pack_estop())
        except Exception as exc:  # pragma: no cover
            self.get_logger().error(f'failed to send ESTOP frame: {exc}')
            return
        self.get_logger().error('ESTOP sent: 6 B empty-payload frame, immediate unload')

    # -- uplink -------------------------------------------------------------

    def _pump_rx(self) -> None:
        try:
            data = self._transport.read()
        except Exception as exc:  # pragma: no cover - transport-level failure
            self.get_logger().error(f'transport read failed: {exc}')
            return
        if not data:
            return
        for frame in self._parser.feed(data):
            self._rx_frames += 1
            if frame.type == fc.TYPE_STATE_Q:
                self._handle_state_q(frame.payload)
            elif frame.type == fc.TYPE_STATE_DQ:
                self._handle_state_dq(frame.payload)
            elif frame.type == fc.TYPE_STATE_IMU:
                self._handle_state_imu(frame.payload)
            elif frame.type == fc.TYPE_EVENT:
                event = fc.unpack_event(frame.payload)
                self.get_logger().warn(f'cerebellum event: {event["name"]} arg={event["arg"]}')
            else:
                self.get_logger().warn(f'unknown frame type 0x{frame.type:02X}')

    def _handle_state_q(self, payload: bytes) -> None:
        """STATE_Q carries the joint angles, which is the frame that drives everything else."""
        state = fc.unpack_state_q(payload)
        self._latest_status = state['status']
        self._latest_age_ms = state['age_ms']
        self._latest_q = list(state['q'])
        self._publish_joint_state()

    def _handle_state_dq(self, payload: bytes) -> None:
        """STATE_DQ carries the joint velocities and does not republish on its own.

        It only refreshes the cached velocity, so the JointState stream keeps one message per
        angle frame instead of doubling the rate with half-populated messages.
        """
        state = fc.unpack_state_dq(payload)
        self._latest_status = state['status']
        self._latest_age_ms = state['age_ms']
        self._latest_dq = list(state['dq'])

    def _publish_joint_state(self) -> None:
        """Publish a complete JointState from the newest cached angle and velocity frames.

        ``velocity`` is only included once a STATE_DQ has actually arrived. A velocity array
        initialised to zero would be indistinguishable from fourteen joints that are genuinely
        stationary, and that difference matters to anything that integrates it.
        """
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = str(self.get_parameter('base_frame').value)
        message.name = list(self._joint_names)
        message.position = list(self._latest_q) if self._latest_q is not None else []
        if self._latest_dq is not None:
            message.velocity = list(self._latest_dq)
        self._joint_publisher.publish(message)

    def _handle_state_imu(self, payload: bytes) -> None:
        state = fc.unpack_state_imu(payload)
        self._latest_status = state['status']
        self._latest_age_ms = state['age_ms']
        message = Imu()
        message.header.stamp = self.get_clock().now().to_msg()
        message.angular_velocity.x, message.angular_velocity.y, message.angular_velocity.z = state['gyro']
        message.linear_acceleration.x, message.linear_acceleration.y, message.linear_acceleration.z = state['acc']
        w, x, y, z = state['quat_wxyz']
        message.orientation.w, message.orientation.x = w, x
        message.orientation.y, message.orientation.z = y, z
        self._imu_publisher.publish(message)

    def _publish_status(self) -> None:
        message = LinkStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status = self._latest_status & 0xFFFF
        message.age_ms = self._latest_age_ms & 0xFFFF
        message.rx_frames = self._rx_frames
        message.tx_frames = self._tx_frames
        message.resync_bytes = self._parser.resync_bytes
        message.bad_len = self._parser.bad_len
        message.bad_crc = self._parser.bad_crc
        message.transport_open = bool(getattr(self._transport, 'open', False))
        message.estop = self._estop_latched
        self._status_publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    try:
        node = BridgeStub()
    except RuntimeError as exc:
        # Surface the reason on stderr and exit non-zero: a bridge that starts and does
        # nothing is harder to diagnose than one that refuses to start.
        print(f'bridge_stub: {exc}', file=sys.stderr)
        rclpy.shutdown()
        raise SystemExit(2) from exc
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        transport = getattr(node, '_transport', None)
        if transport is not None:
            try:
                transport.close()
            except Exception:  # pragma: no cover
                pass
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
