"""Round-trip and framing tests for the wmduck binary link protocol (v1).

These are the tests that matter for the link: they pin the CRC variant by a known-answer
vector, pin the exact byte layout by hand-built byte strings, and check that the parser
resynchronises instead of losing the frames queued behind a corrupted one.

Nothing here touches hardware, a serial port or a ROS graph.
"""

from __future__ import annotations

import struct

import pytest

from wamoduck_ros2 import frame_codec as fc

Q_EXAMPLE = tuple(0.001 * i for i in range(fc.N_JOINTS))


# ---------------------------------------------------------------------------
# CRC
# ---------------------------------------------------------------------------


def test_crc16_known_answer_vector():
    """CRC16-CCITT-FALSE("123456789") == 0x29B1.

    A wrong CRC variant (CCITT-TRUE, ARC, or reflected input) still produces plausible-looking
    checksums, fails only on the wire, and looks exactly like a noisy cable. Pinning the
    variant to a published vector is cheaper than debugging that.
    """
    assert fc.crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_empty_and_single_byte():
    assert fc.crc16_ccitt(b"") == 0xFFFF
    assert fc.crc16_ccitt(b"\x00") == 0xE1F0


# ---------------------------------------------------------------------------
# Frame geometry
# ---------------------------------------------------------------------------


def test_frame_lengths_match_the_documented_table():
    assert fc.CMD_PAYLOAD_LEN == 40
    assert fc.CMD_FRAME_LEN == 46
    assert fc.STATE_Q_PAYLOAD_LEN == 32
    assert fc.STATE_Q_FRAME_LEN == 38
    assert fc.STATE_DQ_FRAME_LEN == 38
    assert fc.STATE_IMU_PAYLOAD_LEN == 24
    assert fc.STATE_IMU_FRAME_LEN == 30
    assert fc.EVENT_FRAME_LEN == 10
    assert fc.ESTOP_FRAME_LEN == 6


def test_every_payload_fits_a_single_can_fd_frame():
    """The whole point of the "one frame per CAN-FD message" claim in docs/16 section 4.1."""
    for length in (
        fc.CMD_PAYLOAD_LEN,
        fc.STATE_Q_PAYLOAD_LEN,
        fc.STATE_DQ_PAYLOAD_LEN,
        fc.STATE_IMU_PAYLOAD_LEN,
        fc.EVENT_PAYLOAD_LEN,
    ):
        assert length <= 64


def test_uplink_round_bandwidth_matches_the_documented_106_bytes():
    per_round = fc.STATE_Q_FRAME_LEN + fc.STATE_DQ_FRAME_LEN + fc.STATE_IMU_FRAME_LEN
    assert per_round == 106
    # 200 Hz -> 21.2 kB/s, which is 23 % of 921600 8N1 (92160 B/s).
    assert per_round * 200 == 21200
    assert pytest.approx(21200 / (921600 / 10), abs=0.005) == 0.23


# ---------------------------------------------------------------------------
# CMD: layout pinned against a hand-built byte string
# ---------------------------------------------------------------------------


def test_cmd_frame_bytes_are_exactly_as_specified():
    """Pin endianness, field order and scales against bytes assembled by hand.

    The head is written as literal bytes and the two int16 arrays use a format string spelled
    out here rather than the module's own struct, so a change to the wire layout has to be
    made in two places -- which is the point of a pin.
    """
    q = tuple(float(i) for i in range(fc.N_JOINTS))          # q[i] = i rad -> i*1000 mrad
    payload = fc.pack_cmd(q, mode=fc.MODE_POLICY, twist=(1.0, -1.0, 0.5), t_ms=1000, flags=0)

    head = bytes([
        0x02,                    # mode = MODE_POLICY
        0x00,                    # flags
        0xE8, 0x03, 0x00, 0x00,  # t_ms = 1000, little-endian u32
    ])
    q_bytes = struct.pack('<14h', *(i * 1000 for i in range(fc.N_JOINTS)))
    twist_bytes = struct.pack('<3h', 1000, -1000, 500)       # mm/s, mm/s, mrad/s
    body = head + q_bytes + twist_bytes
    assert len(body) == fc.CMD_PAYLOAD_LEN
    assert payload == body
    # Spot-check the first two quantised joints: 0 rad -> 0x0000, 1 rad -> 1000 -> 0x03E8 LE.
    assert payload[6:10] == bytes([0x00, 0x00, 0xE8, 0x03])

    frame = fc.pack_frame(fc.TYPE_CMD, payload, seq=3)
    expected = (
        bytes([fc.SOF, fc.TYPE_CMD, fc.CMD_PAYLOAD_LEN, 3])
        + body
        + fc.crc16_ccitt(bytes([fc.TYPE_CMD, fc.CMD_PAYLOAD_LEN, 3]) + body).to_bytes(2, "little")
    )
    assert frame == expected
    assert len(frame) == 46


def test_cmd_round_trip_within_one_milliradian():
    payload = fc.pack_cmd(Q_EXAMPLE, mode=fc.MODE_POLICY, twist=(0.3, -0.1, 0.2), t_ms=1234)
    frames = list(fc.FrameParser().feed(fc.pack_frame(fc.TYPE_CMD, payload, seq=7)))
    assert len(frames) == 1
    decoded = fc.unpack_cmd(frames[0].payload)
    assert frames[0].seq == 7
    assert frames[0].type_name == "CMD"
    assert decoded["mode"] == fc.MODE_POLICY
    assert decoded["mode_name"] == "POLICY"
    assert decoded["t_ms"] == 1234
    # int16 mrad: quantisation error is bounded by half a milliradian.
    assert max(abs(a - b) for a, b in zip(decoded["q_target"], Q_EXAMPLE)) <= 5e-4
    assert decoded["twist"] == pytest.approx((0.3, -0.1, 0.2), abs=5e-4)


def test_cmd_saturation_clamps_and_never_wraps():
    """+99 rad must arrive as +32.767 rad, not as -12 rad."""
    decoded = fc.unpack_cmd(fc.pack_cmd([99.0] * fc.N_JOINTS))
    assert decoded["q_target"][0] == pytest.approx(32.767, abs=1e-3)
    negative = fc.unpack_cmd(fc.pack_cmd([-99.0] * fc.N_JOINTS))
    assert negative["q_target"][0] == pytest.approx(-32.768, abs=1e-3)


def test_quantise_reports_which_entries_saturated():
    ints, saturated = fc.quantise_i16([0.0, 100.0, -100.0, 1.0], fc.Q_SCALE)
    assert saturated == [1, 2]
    assert ints == [0, 32767, -32768, 1000]
    assert fc.quantise_i16([0.0], fc.Q_SCALE)[1] == []


def test_wrong_joint_count_is_rejected_rather_than_padded():
    with pytest.raises(ValueError, match="14 entries"):
        fc.pack_cmd([0.0] * 13)
    with pytest.raises(ValueError, match="twist"):
        fc.pack_cmd([0.0] * fc.N_JOINTS, twist=(0.0, 0.0))


# ---------------------------------------------------------------------------
# Parser: rejection, resynchronisation, counters
# ---------------------------------------------------------------------------


def test_corrupted_frame_is_rejected_and_does_not_eat_the_next_frame():
    good = fc.pack_frame(fc.TYPE_CMD, fc.pack_cmd(Q_EXAMPLE), seq=1)
    bad = bytearray(good)
    bad[10] ^= 0x40
    parser = fc.FrameParser()
    frames = list(parser.feed(bytes(bad) + good))
    assert len(frames) == 1
    assert frames[0].seq == 1
    assert parser.bad_crc == 1
    # Exactly one byte of the bad frame is dropped before SOF realigns, so the good frame
    # behind it survives. (>= 1 rather than == 1: if the corrupted body happens to contain a
    # 0xA5 the parser skips a few more bytes on the way, which is still correct behaviour.)
    assert parser.resync_bytes >= 1


def test_partial_frame_is_buffered_until_it_completes():
    frame = fc.pack_frame(fc.TYPE_CMD, fc.pack_cmd(Q_EXAMPLE), seq=0)
    parser = fc.FrameParser()
    assert list(parser.feed(frame[:9])) == []
    assert parser.buffered_bytes == 9
    frames = list(parser.feed(frame[9:]))
    assert len(frames) == 1
    assert parser.buffered_bytes == 0


def test_leading_noise_is_counted_and_recovered_from():
    frame = fc.pack_frame(fc.TYPE_CMD, fc.pack_cmd(Q_EXAMPLE), seq=0)
    parser = fc.FrameParser()
    frames = list(parser.feed(b"\x00\x13\x99" + frame))
    assert len(frames) == 1
    assert parser.resync_bytes == 3


def test_pipelined_frames_are_all_decoded():
    frame = fc.pack_frame(fc.TYPE_CMD, fc.pack_cmd(Q_EXAMPLE), seq=0)
    parser = fc.FrameParser()
    frames = list(parser.feed(frame * 3))
    assert [f.seq for f in frames] == [0, 0, 0]
    assert len(frames) == 3


def test_pure_noise_produces_no_frames_and_no_exception():
    # Noise deliberately free of SOF, so the outcome is deterministic rather than a
    # one-in-65536 CRC collision.
    noise = bytes(byte for byte in range(1, 256) if byte != fc.SOF) * 4
    parser = fc.FrameParser()
    frames = list(parser.feed(noise))
    assert frames == []
    assert parser.resync_bytes == len(noise)


# ---------------------------------------------------------------------------
# Uplink frames
# ---------------------------------------------------------------------------


def test_state_q_round_trip():
    parser = fc.FrameParser()
    frame = fc.pack_frame(
        fc.TYPE_STATE_Q,
        fc.pack_state_q([0.1] * fc.N_JOINTS, age_ms=37, status=fc.ST_ENABLED | fc.ST_POLICY_MODE),
    )
    frames = list(parser.feed(frame))
    assert len(frames) == 1
    state = fc.unpack_state_q(frames[0].payload)
    assert state["age_ms"] == 37
    assert state["status"] == fc.ST_ENABLED | fc.ST_POLICY_MODE
    assert state["q"][0] == pytest.approx(0.1, abs=1e-3)
    assert len(state["q"]) == fc.N_JOINTS


def test_state_dq_round_trip():
    frame = fc.pack_frame(
        fc.TYPE_STATE_DQ, fc.pack_state_dq([-1.5] * fc.N_JOINTS, age_ms=3, status=fc.ST_FALLEN)
    )
    state = fc.unpack_state_dq(list(fc.FrameParser().feed(frame))[0].payload)
    assert state["age_ms"] == 3
    assert state["status"] == fc.ST_FALLEN
    assert state["dq"][0] == pytest.approx(-1.5, abs=0.01)


def test_state_imu_round_trip():
    frame = fc.pack_frame(
        fc.TYPE_STATE_IMU,
        fc.pack_state_imu(
            (0.0, 0.0, 1.5), (0.0, 0.0, 9.81), (1.0, 0.0, 0.0, 0.0), age_ms=5, status=0
        ),
    )
    state = fc.unpack_state_imu(list(fc.FrameParser().feed(frame))[0].payload)
    assert state["age_ms"] == 5
    assert state["gyro"][2] == pytest.approx(1.5, abs=0.01)
    assert state["acc"][2] == pytest.approx(9.81, abs=0.01)
    assert state["quat_wxyz"][0] == pytest.approx(1.0, abs=1e-4)


def test_state_imu_rejects_short_input():
    with pytest.raises(ValueError, match="gyro"):
        fc.pack_state_imu((0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), age_ms=0)


def test_event_round_trip():
    frame = fc.pack_frame(fc.TYPE_EVENT, fc.pack_event(1, arg=250))
    assert len(frame) == fc.EVENT_FRAME_LEN
    event = fc.unpack_event(list(fc.FrameParser().feed(frame))[0].payload)
    assert event == {"code": 1, "name": "watchdog_hold", "arg": 250}


def test_estop_frame_is_six_bytes_with_an_empty_payload():
    frame = fc.pack_estop()
    assert len(frame) == fc.ESTOP_FRAME_LEN
    # SOF | TYPE_ESTOP | LEN=0 | SEQ=0, then the CRC over TYPE..SEQ (which is not zero: the
    # CRC of a 3-byte body is whatever CCITT-FALSE says it is, and treating it as padding
    # would be the bug this assertion exists to catch).
    assert frame[:4] == bytes([fc.SOF, fc.TYPE_ESTOP, 0x00, 0x00])
    assert frame[4:] == fc.crc16_ccitt(frame[1:4]).to_bytes(2, 'little')
    parsed = list(fc.FrameParser().feed(frame))
    assert len(parsed) == 1
    assert parsed[0].payload == b""
    # The ESTOP frame has to have a different CRC from an all-zero tail, or the field would
    # not be doing anything.
    assert frame[4:] != b"\x00\x00"


def test_payload_decoders_reject_the_wrong_length():
    with pytest.raises(ValueError):
        fc.unpack_state_q(b"\x00" * 30)
    with pytest.raises(ValueError):
        fc.unpack_state_dq(b"\x00" * 30)
    with pytest.raises(ValueError):
        fc.unpack_state_imu(b"\x00" * 30)
    with pytest.raises(ValueError):
        fc.unpack_event(b"\x00" * 3)
    with pytest.raises(ValueError):
        fc.unpack_cmd(b"\x00" * 39)


def test_oversized_payload_cannot_be_framed():
    with pytest.raises(ValueError, match="too long"):
        fc.pack_frame(fc.TYPE_CMD, b"\x00" * 256)


def test_status_flags_decode():
    status = fc.ST_ENABLED | fc.ST_WATCHDOG | fc.ST_ESTOP
    assert fc.status_flags(status) == ["ENABLED", "WATCHDOG", "ESTOP"]
    assert fc.status_flags(0) == []


def test_mode_names_cover_the_protocol():
    assert fc.MODE_NAMES == {0: "OFF", 1: "HOLD", 2: "POLICY", 3: "CALIB"}


def test_protection_constants_are_the_contract_values():
    """These are contract values, not tunables: the firmware implements the same numbers."""
    assert fc.CMD_TIMEOUT_HOLD_MS == 200
    assert fc.CMD_TIMEOUT_OFF_MS == 1000
    assert fc.CMD_TIMEOUT_OFF_MS > fc.CMD_TIMEOUT_HOLD_MS
    assert fc.MAX_CMD_JUMP_RAD == 0.35
