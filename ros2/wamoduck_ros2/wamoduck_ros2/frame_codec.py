"""Byte-level codec for the wmduck host <-> cerebellum link (deployment protocol v1).

This module is deliberately **pure Python and ROS-free**: it can be imported, unit-tested
and reasoned about without a running ROS graph or any hardware, which is the whole point of
splitting protocol parsing away from control logic.

Wire format
-----------
::

    SOF(0xA5) | TYPE | LEN | SEQ | PAYLOAD | CRC16(TYPE..PAYLOAD)
       1 B      1 B    1 B   1 B     LEN B          2 B

* ``CRC16`` is CRC16-CCITT-FALSE: poly ``0x1021``, init ``0xFFFF``, no input reflection,
  no output reflection, no final XOR. The known-answer vector
  ``CRC16-CCITT-FALSE(b"123456789") == 0x29B1`` is asserted by the test suite; a wrong CRC
  variant fails quietly and looks like a noisy cable, so it is pinned by a test.
* Every multi-byte integer is **little-endian**, matching the ARM firmware and the reference
  implementation this file is wire-compatible with.
* ``LEN`` counts payload bytes only, so a full frame is ``4 + LEN + 2`` bytes.

Frames
------
Downlink (host -> cerebellum)::

    0x01 CMD      40 B payload -> 46 B frame    50 Hz   mode, flags, t_ms, q[14] i16, twist[3] i16
    0x02 ESTOP     0 B payload ->  6 B frame    event   immediate unload

Uplink (cerebellum -> host)::

    0x81 STATE_Q   32 B payload -> 38 B frame   200 Hz  age_ms, q[14] i16, status
    0x82 STATE_DQ  32 B payload -> 38 B frame   200 Hz  age_ms, dq[14] i16, status
    0x83 STATE_IMU 24 B payload -> 30 B frame   200 Hz  age_ms, gyro[3], acc[3], quat[4] wxyz, status
    0x84 EVENT      4 B payload -> 10 B frame   event   code, arg

Uplink bandwidth is 106 B per round for the three state frames, i.e. 21.2 kB/s at 200 Hz,
which is 23 % of a 921600 8N1 UART. Every payload is <= 64 B, so the same frames can be
carried one-per-message over CAN-FD without an upper layer change.

Fixed-point scales
------------------
Every float that crosses the link becomes an ``int16`` with a fixed scale. The scales and
the range each one can represent:

===========  ======================  =========  ==========================
quantity     unit                    scale      representable range
===========  ======================  =========  ==========================
q            rad  -> mrad            x1000      +/- 32.767 rad
dq           rad/s -> 0.01 rad/s     x100      +/- 327.67 rad/s
gyro         rad/s -> 0.01 rad/s     x100      +/- 327.67 rad/s
acc          m/s^2 -> 0.01 m/s^2     x100      +/- 327.67 m/s^2
quat         unit -> int16           x30000     -1.0 .. 1.0
twist linear m/s -> mm/s             x1000      +/- 32.767 m/s
twist yaw    rad/s -> mrad/s         x1000      +/- 32.767 rad/s
===========  ======================  =========  ==========================

Out-of-range values **saturate**; they never wrap. Wrapping would silently turn a +20 rad
target into -12 rad, which is the kind of bug that only shows up as a robot throwing itself
at the floor.

Array ordering
--------------
``q`` and ``dq`` are always in **joint-tree order**, the 14-joint order pinned by
``wamoduck_ros2.model_contract.JOINT_ORDER``, which is also the order of ``joint_pos`` and
``joint_vel`` inside the policy observation **and the order of the policy's own 14-wide
output**. The action -> joint permutation therefore resolves to the identity, and it is still
applied once, on the host, in ``policy_interface.action_to_joint_target()``. Keeping the link
order equal to the observation and action order is what makes that a single documented
statement instead of three orders to line up by hand.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOF = 0xA5

# Downlink (host -> cerebellum)
TYPE_CMD = 0x01
TYPE_ESTOP = 0x02
# Uplink (cerebellum -> host)
TYPE_STATE_Q = 0x81
TYPE_STATE_DQ = 0x82
TYPE_STATE_IMU = 0x83
TYPE_EVENT = 0x84

TYPE_NAMES = {
    TYPE_CMD: "CMD",
    TYPE_ESTOP: "ESTOP",
    TYPE_STATE_Q: "STATE_Q",
    TYPE_STATE_DQ: "STATE_DQ",
    TYPE_STATE_IMU: "STATE_IMU",
    TYPE_EVENT: "EVENT",
}

N_JOINTS = 14

Q_SCALE = 1000.0        # rad     -> mrad
DQ_SCALE = 100.0        # rad/s   -> 0.01 rad/s
GYRO_SCALE = 100.0      # rad/s   -> 0.01 rad/s
ACC_SCALE = 100.0       # m/s^2   -> 0.01 m/s^2
QUAT_SCALE = 30000.0    # unit quaternion -> int16
TWIST_LIN_SCALE = 1000.0  # m/s   -> mm/s
TWIST_YAW_SCALE = 1000.0  # rad/s -> mrad/s

# Downlink modes
MODE_OFF = 0      # unload: kp -> 0, the robot falls under gravity (controlled collapse)
MODE_HOLD = 1     # freeze at the previous target, gains unchanged (first timeout step)
MODE_POLICY = 2   # normal closed loop: track q_target
MODE_CALIB = 3    # bench-only slow single-joint excitation

MODE_NAMES = {
    MODE_OFF: "OFF",
    MODE_HOLD: "HOLD",
    MODE_POLICY: "POLICY",
    MODE_CALIB: "CALIB",
}

# Cerebellum status word bits (uplink `status` field)
ST_ENABLED = 1 << 0
ST_POLICY_MODE = 1 << 1
ST_WATCHDOG = 1 << 2
ST_FAULT_OVERCURRENT = 1 << 3
ST_FAULT_OVERTEMP = 1 << 4
ST_FAULT_ENCODER = 1 << 5
ST_LIMIT_CLAMPED = 1 << 6
ST_ESTOP = 1 << 7
ST_CAN_ERROR = 1 << 8
ST_FALLEN = 1 << 9

ST_NAMES = {
    ST_ENABLED: "ENABLED",
    ST_POLICY_MODE: "POLICY_MODE",
    ST_WATCHDOG: "WATCHDOG",
    ST_FAULT_OVERCURRENT: "FAULT_OVERCURRENT",
    ST_FAULT_OVERTEMP: "FAULT_OVERTEMP",
    ST_FAULT_ENCODER: "FAULT_ENCODER",
    ST_LIMIT_CLAMPED: "LIMIT_CLAMPED",
    ST_ESTOP: "ESTOP",
    ST_CAN_ERROR: "CAN_ERROR",
    ST_FALLEN: "FALLEN",
}

# Cerebellum protection layer. These are part of the contract, not tunables: the firmware is
# expected to implement exactly these defaults.
CMD_TIMEOUT_HOLD_MS = 200
CMD_TIMEOUT_OFF_MS = 1000
MAX_CMD_JUMP_RAD = 0.35    # per 20 ms frame; rate-limit, never drop the frame
CMD_LARGE_DELTA_RAD = 2.0  # above this only a diagnostic counter increments

EVENT_NAMES = {
    1: "watchdog_hold",
    2: "watchdog_off",
    3: "estop",
    4: "overcurrent",
    5: "overtemp",
    6: "encoder_fault",
    7: "can_bus_error",
    8: "limit_clamped",
    9: "self_check_failed",
}

# ---------------------------------------------------------------------------
# Frame packing / parsing
# ---------------------------------------------------------------------------

_HEADER = struct.Struct("<BBBB")            # SOF, TYPE, LEN, SEQ
_CRC = struct.Struct("<H")
_CMD = struct.Struct("<BB I 14h 3h")        # mode, flags, t_ms, q[14], twist[3]
_STATE_Q = struct.Struct("<H 14h H")        # age_ms, q[14], status
_STATE_DQ = struct.Struct("<H 14h H")       # age_ms, dq[14], status
_STATE_IMU = struct.Struct("<H 3h 3h 4h H")  # age_ms, gyro[3], acc[3], quat[4], status

CMD_PAYLOAD_LEN = _CMD.size                 # 40
STATE_Q_PAYLOAD_LEN = _STATE_Q.size         # 32
STATE_DQ_PAYLOAD_LEN = _STATE_DQ.size       # 32
STATE_IMU_PAYLOAD_LEN = _STATE_IMU.size     # 24
EVENT_PAYLOAD_LEN = 4

FRAME_OVERHEAD = 6                          # SOF + TYPE + LEN + SEQ + CRC16
CMD_FRAME_LEN = CMD_PAYLOAD_LEN + FRAME_OVERHEAD            # 46
ESTOP_FRAME_LEN = FRAME_OVERHEAD                            # 6
STATE_Q_FRAME_LEN = STATE_Q_PAYLOAD_LEN + FRAME_OVERHEAD    # 38
STATE_DQ_FRAME_LEN = STATE_DQ_PAYLOAD_LEN + FRAME_OVERHEAD  # 38
STATE_IMU_FRAME_LEN = STATE_IMU_PAYLOAD_LEN + FRAME_OVERHEAD  # 30
EVENT_FRAME_LEN = EVENT_PAYLOAD_LEN + FRAME_OVERHEAD        # 10


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """CRC16-CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no final XOR).

    Table-free bitwise implementation. A frame is at most 46 B and the downlink runs at
    50 Hz, so the cost is irrelevant and correctness-by-inspection is worth more than speed.
    """
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def pack_frame(frame_type: int, payload: bytes, seq: int = 0) -> bytes:
    """Build ``SOF | TYPE | LEN | SEQ | PAYLOAD | CRC16(TYPE..PAYLOAD)``."""
    if not 0 <= len(payload) <= 0xFF:
        raise ValueError(f"payload too long for the LEN byte: {len(payload)}")
    body = _HEADER.pack(SOF, frame_type & 0xFF, len(payload), seq & 0xFF) + bytes(payload)
    return body + _CRC.pack(crc16_ccitt(body[1:]))


@dataclass(frozen=True)
class Frame:
    """One decoded frame."""

    type: int
    seq: int
    payload: bytes

    @property
    def type_name(self) -> str:
        return TYPE_NAMES.get(self.type, f"UNKNOWN_0x{self.type:02X}")


class FrameParser:
    """Byte stream -> frames, dropping bad frames and counting why.

    Bad frames are discarded in place rather than raising, because a UART under electrical
    noise produces a continuous stream of them and the control loop must not care. The three
    counters are kept separate because they mean different things:

    ``resync_bytes``
        bytes skipped while hunting for ``SOF`` -- noise, or the tail of a half frame.
    ``bad_len``
        a plausible-looking header whose ``LEN`` byte cannot be satisfied. Almost always a
        real resync; worth watching because a run of them means the framing is drifting.
    ``bad_crc``
        a complete-length frame that failed CRC. Points at the physical layer.

    After a CRC failure only **one byte** is dropped, so a corrupted frame cannot swallow
    the good frames queued behind it.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.resync_bytes = 0
        self.bad_len = 0
        self.bad_crc = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._buf)

    def feed(self, data: bytes) -> Iterator[Frame]:
        """Consume bytes and yield every complete, CRC-valid frame."""
        self._buf.extend(data)
        while True:
            start = self._buf.find(SOF)
            if start < 0:
                if self._buf:
                    self.resync_bytes += len(self._buf)
                    self._buf.clear()
                return
            if start > 0:
                self.resync_bytes += start
                del self._buf[:start]
            if len(self._buf) < 4:
                return
            length = self._buf[2]
            total = 4 + length + 2
            if len(self._buf) < total:
                return
            body = bytes(self._buf[: 4 + length])
            crc_rx = _CRC.unpack(self._buf[4 + length:total])[0]
            if crc16_ccitt(body[1:]) != crc_rx:
                self.bad_crc += 1
                del self._buf[:1]
                continue
            yield Frame(type=body[1], seq=body[3], payload=body[4:])
            del self._buf[:total]


# ---------------------------------------------------------------------------
# Fixed-point helpers
# ---------------------------------------------------------------------------


def quantise_i16(values: Iterable[float], scale: float) -> tuple[list[int], list[int]]:
    """Scale floats to int16, saturating.

    Returns ``(ints, saturated_indices)``. The saturated indices are reported rather than
    logged here so that the caller decides: for a joint target it is worth a warning, for a
    quaternion it is always a bug.
    """
    ints: list[int] = []
    saturated: list[int] = []
    for index, value in enumerate(values):
        raw = int(round(float(value) * scale))
        if raw > 32767:
            ints.append(32767)
            saturated.append(index)
        elif raw < -32768:
            ints.append(-32768)
            saturated.append(index)
        else:
            ints.append(raw)
    return ints, saturated


def _pack_i16(values: Iterable[float], scale: float) -> bytes:
    ints, _ = quantise_i16(values, scale)
    return struct.pack(f"<{len(ints)}h", *ints)


def _unpack_i16(data: bytes, count: int, scale: float) -> list[float]:
    return [v / scale for v in struct.unpack_from(f"<{count}h", data, 0)]


# ---------------------------------------------------------------------------
# Downlink: CMD / ESTOP
# ---------------------------------------------------------------------------


def pack_cmd(
    q_target: Sequence[float],
    mode: int = MODE_POLICY,
    twist: Sequence[float] = (0.0, 0.0, 0.0),
    t_ms: int = 0,
    flags: int = 0,
) -> bytes:
    """Pack a CMD payload (40 B).

    ``q_target`` must be in joint-tree order -- see the module docstring. Length is checked
    rather than padded, because a silently short target array would leave joints commanded
    to whatever happened to be in the rest of the buffer.
    """
    if len(q_target) != N_JOINTS:
        raise ValueError(f"q_target must have {N_JOINTS} entries, got {len(q_target)}")
    if len(twist) != 3:
        raise ValueError("twist must be (vx, vy, wz)")
    q_ints, _ = quantise_i16(q_target, Q_SCALE)
    twist_ints, _ = quantise_i16(
        (twist[0] * TWIST_LIN_SCALE, twist[1] * TWIST_LIN_SCALE, twist[2] * TWIST_YAW_SCALE),
        1.0,
    )
    return _CMD.pack(mode & 0xFF, flags & 0xFF, t_ms & 0xFFFFFFFF, *q_ints, *twist_ints)


def unpack_cmd(payload: bytes) -> dict:
    """Unpack a CMD payload into radians and SI twist."""
    if len(payload) != CMD_PAYLOAD_LEN:
        raise ValueError(f"CMD payload must be {CMD_PAYLOAD_LEN} B, got {len(payload)}")
    mode, flags, t_ms, *rest = _CMD.unpack(payload)
    return {
        "mode": mode,
        "mode_name": MODE_NAMES.get(mode, f"UNKNOWN_{mode}"),
        "flags": flags,
        "t_ms": t_ms,
        "q_target": [v / Q_SCALE for v in rest[:N_JOINTS]],
        "twist": (
            rest[N_JOINTS] / TWIST_LIN_SCALE,
            rest[N_JOINTS + 1] / TWIST_LIN_SCALE,
            rest[N_JOINTS + 2] / TWIST_YAW_SCALE,
        ),
    }


def pack_estop() -> bytes:
    """Pack an ESTOP frame (6 B, empty payload)."""
    return pack_frame(TYPE_ESTOP, b"")


# ---------------------------------------------------------------------------
# Uplink: state frames
# ---------------------------------------------------------------------------


def pack_state_q(q: Sequence[float], age_ms: int, status: int = 0) -> bytes:
    if len(q) != N_JOINTS:
        raise ValueError(f"q must have {N_JOINTS} entries, got {len(q)}")
    return _STATE_Q.pack(min(int(age_ms), 0xFFFF),
                         *struct.unpack("<14h", _pack_i16(q, Q_SCALE)), status & 0xFFFF)


def pack_state_dq(dq: Sequence[float], age_ms: int, status: int = 0) -> bytes:
    if len(dq) != N_JOINTS:
        raise ValueError(f"dq must have {N_JOINTS} entries, got {len(dq)}")
    return _STATE_DQ.pack(min(int(age_ms), 0xFFFF),
                          *struct.unpack("<14h", _pack_i16(dq, DQ_SCALE)), status & 0xFFFF)


def pack_state_imu(
    gyro: Sequence[float],
    acc: Sequence[float],
    quat_wxyz: Sequence[float],
    age_ms: int,
    status: int = 0,
) -> bytes:
    """Pack STATE_IMU. ``quat_wxyz`` is scalar-first, as the IMU module reports it."""
    if len(gyro) != 3 or len(acc) != 3 or len(quat_wxyz) != 4:
        raise ValueError("STATE_IMU needs gyro[3], acc[3], quat_wxyz[4]")
    g = struct.unpack("<3h", _pack_i16(gyro, GYRO_SCALE))
    a = struct.unpack("<3h", _pack_i16(acc, ACC_SCALE))
    q = struct.unpack("<4h", _pack_i16(quat_wxyz, QUAT_SCALE))
    return _STATE_IMU.pack(min(int(age_ms), 0xFFFF), *g, *a, *q, status & 0xFFFF)


def unpack_state_q(payload: bytes) -> dict:
    if len(payload) != STATE_Q_PAYLOAD_LEN:
        raise ValueError(f"STATE_Q payload must be {STATE_Q_PAYLOAD_LEN} B, got {len(payload)}")
    age, *rest = _STATE_Q.unpack(payload)
    return {"age_ms": age, "q": [v / Q_SCALE for v in rest[:N_JOINTS]], "status": rest[N_JOINTS]}


def unpack_state_dq(payload: bytes) -> dict:
    if len(payload) != STATE_DQ_PAYLOAD_LEN:
        raise ValueError(f"STATE_DQ payload must be {STATE_DQ_PAYLOAD_LEN} B, got {len(payload)}")
    age, *rest = _STATE_DQ.unpack(payload)
    return {"age_ms": age, "dq": [v / DQ_SCALE for v in rest[:N_JOINTS]], "status": rest[N_JOINTS]}


def unpack_state_imu(payload: bytes) -> dict:
    if len(payload) != STATE_IMU_PAYLOAD_LEN:
        raise ValueError(f"STATE_IMU payload must be {STATE_IMU_PAYLOAD_LEN} B, got {len(payload)}")
    age, *rest = _STATE_IMU.unpack(payload)
    return {
        "age_ms": age,
        "gyro": [v / GYRO_SCALE for v in rest[:3]],
        "acc": [v / ACC_SCALE for v in rest[3:6]],
        "quat_wxyz": [v / QUAT_SCALE for v in rest[6:10]],
        "status": rest[10],
    }


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def pack_event(code: int, arg: int = 0) -> bytes:
    return struct.pack("<HH", code & 0xFFFF, arg & 0xFFFF)


def unpack_event(payload: bytes) -> dict:
    if len(payload) != EVENT_PAYLOAD_LEN:
        raise ValueError(f"EVENT payload must be {EVENT_PAYLOAD_LEN} B, got {len(payload)}")
    code, arg = struct.unpack("<HH", payload)
    return {"code": code, "name": EVENT_NAMES.get(code, f"unknown_{code}"), "arg": arg}


def status_flags(status: int) -> list[str]:
    """Decode a status word into the list of set bit names (for logs and diagnostics)."""
    return [name for bit, name in sorted(ST_NAMES.items()) if status & bit]
