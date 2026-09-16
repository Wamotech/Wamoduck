"""Tests for the gait CSV reader and the URDF name matching around it.

The synthetic CSVs are written by the tests so that the reader's contract is pinned
independently of the real files, and the real files are checked separately for the shape the
reader assumes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from wamoduck_ros2.gait_csv import (
    finite_difference,
    load_gait_csv,
    map_track_to_urdf_joints,
)

HEADER = (
    "# synthetic track | units: q in rad, tau in N.m",
    "t_s,q_left_knee,q_mouth,tau_left_knee,tau_mouth,base_x,base_y,base_z,base_roll_rad",
)


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([*HEADER, *rows]) + "\n", encoding="utf-8", newline="\n")
    return path


def test_loads_a_well_formed_track(tmp_path):
    path = write_csv(
        tmp_path / "track.csv",
        [
            "10.0,0.0,0.0,0.0,0.0,0.0,0.0,0.17,0.0",
            "10.02,0.1,0.01,0.5,0.1,0.01,0.0,0.17,0.0",
            "10.04,0.2,0.02,1.0,0.2,0.02,0.0,0.17,0.0",
        ],
    )
    track = load_gait_csv(path)

    assert track.samples == 3
    # Timestamps are rebased to start at zero, so playback always begins at t = 0.
    assert track.times_s == pytest.approx((0.0, 0.02, 0.04))
    assert track.duration_s == pytest.approx(0.04)
    assert track.nominal_hz == pytest.approx(50.0)
    assert track.uniform
    assert set(track.joint_positions) == {"left_knee", "mouth"}
    assert set(track.joint_efforts) == {"left_knee", "mouth"}
    assert track.base["base_z"] == pytest.approx((0.17, 0.17, 0.17))
    assert track.comment.startswith("synthetic track")


def test_index_at_clamps_at_both_ends(tmp_path):
    path = write_csv(
        tmp_path / "track.csv",
        [
            "0.0,0.0,0.0,0.0,0.0,0,0,0,0",
            "0.5,1.0,0.0,0.0,0.0,0,0,0,0",
            "1.0,2.0,0.0,0.0,0.0,0,0,0,0",
        ],
    )
    track = load_gait_csv(path)
    assert track.index_at(-5.0) == 0
    assert track.index_at(0.24) == 0
    assert track.index_at(0.5) == 1
    assert track.index_at(0.99) == 1
    assert track.index_at(1.0) == 2
    assert track.index_at(99.0) == 2


def test_non_uniform_timestamps_are_reported_not_hidden(tmp_path):
    path = write_csv(
        tmp_path / "track.csv",
        [
            "0.0,0.0,0.0,0.0,0.0,0,0,0,0",
            "0.02,0.1,0.0,0.0,0.0,0,0,0,0",
            "0.10,0.2,0.0,0.0,0.0,0,0,0,0",
        ],
    )
    track = load_gait_csv(path)
    assert not track.uniform
    # median of (0.02, 0.08) is 0.05 -> 20 Hz, which is why the median is used rather than
    # the mean: a single long gap must not silently report a plausible-looking rate.
    assert track.nominal_hz == pytest.approx(20.0)


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_gait_csv(tmp_path / "nope.csv")


def test_header_without_t_s_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("q_left_knee\n0.0\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="t_s"):
        load_gait_csv(path)


def test_no_q_columns_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("t_s,base_z\n0.0,0.17\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="q_<joint>"):
        load_gait_csv(path)


def test_ragged_row_is_rejected_with_the_row_number(tmp_path):
    path = write_csv(tmp_path / "bad.csv", ["0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.17"])
    with pytest.raises(ValueError, match="row 1"):
        load_gait_csv(path)


def test_non_numeric_cell_is_rejected_with_the_column_name(tmp_path):
    path = write_csv(tmp_path / "bad.csv", ["0.0,abc,0.0,0.0,0.0,0.0,0.0,0.17,0.0"])
    with pytest.raises(ValueError, match="left_knee"):
        load_gait_csv(path)


def test_unsorted_timestamps_are_rejected(tmp_path):
    path = write_csv(
        tmp_path / "bad.csv",
        ["0.0,0.0,0.0,0.0,0.0,0,0,0,0", "0.5,0.0,0.0,0.0,0.0,0,0,0,0",
         "0.2,0.0,0.0,0.0,0.0,0,0,0,0"],
    )
    with pytest.raises(ValueError, match="monotonically"):
        load_gait_csv(path)


# ---------------------------------------------------------------------------
# URDF matching
# ---------------------------------------------------------------------------


def test_matching_orders_the_track_into_urdf_document_order(tmp_path):
    path = write_csv(
        tmp_path / "track.csv",
        ["0.0,0.0,0.0,0.0,0.0,0,0,0,0", "0.02,0.1,0.2,0.0,0.0,0,0,0,0"],
    )
    track = load_gait_csv(path)
    ordered, matched, warnings = map_track_to_urdf_joints(
        track, ["mouth", "left_knee", "left_ankle"]
    )
    # URDF document order is the message order, not the CSV column order.
    assert list(ordered) == ["mouth", "left_knee"]
    assert matched == ["mouth", "left_knee"]
    assert warnings == [
        "URDF joint 'left_ankle' has no 'q_left_ankle' column in track.csv; "
        "it will be published at 0.0"
    ]


def test_a_column_matching_no_joint_is_reported(tmp_path):
    path = write_csv(tmp_path / "track.csv", ["0.0,0.0,0.0,0.0,0.0,0,0,0,0"])
    track = load_gait_csv(path)
    _ordered, matched, warnings = map_track_to_urdf_joints(track, ["left_knee"])
    assert matched == ["left_knee"]
    assert any("matches no movable URDF joint" in w for w in warnings)


def test_no_match_at_all_is_an_error_not_an_empty_animation(tmp_path):
    path = write_csv(tmp_path / "track.csv", ["0.0,0.0,0.0,0.0,0.0,0,0,0,0"])
    track = load_gait_csv(path)
    with pytest.raises(ValueError, match="none of its q_\\* columns"):
        map_track_to_urdf_joints(track, ["some_other_joint"])


def test_finite_difference_endpoints_and_middle():
    # x = t^2 sampled at t = 0,1,2,3 -> exact derivative 2t is 0,2,4,6; the central
    # differences give 2 and 4 and the one-sided ends give 1 and 5, which is what pins the
    # "central inside, one-sided at the ends" behaviour.
    values = (0.0, 1.0, 4.0, 9.0)
    times = (0.0, 1.0, 2.0, 3.0)
    assert finite_difference(values, times) == pytest.approx((1.0, 2.0, 4.0, 5.0))


def test_finite_difference_handles_a_single_sample():
    assert finite_difference((5.0,), (0.0,)) == (0.0,)
    assert finite_difference((), ()) == ()


def test_finite_difference_survives_duplicate_timestamps():
    assert finite_difference((0.0, 1.0), (0.0, 0.0)) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# The real reference tracks
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
_REAL = {
    "gait_cycle_2s_50Hz.csv": (100, 50.0),
    "gait_walk_1m_10Hz.csv": (1040, 10.0),
}


@pytest.mark.parametrize("filename,expected", sorted(_REAL.items()))
def test_real_reference_tracks_have_the_documented_shape(filename, expected):
    path = os.path.join(_REPO_ROOT, "tools", "matlab", "data", filename)
    if not os.path.isfile(path):
        pytest.skip(f"{path} not available (only the ros2/ subtree was copied)")
    samples, hz = expected
    track = load_gait_csv(path)
    assert track.samples == samples
    assert track.nominal_hz == pytest.approx(hz, abs=1e-6)
    assert track.uniform
    # 15 movable joints per the URDF, including `mouth`, which the 14-joint policy contract
    # does not use. Both facts are asserted so that a change in either file is visible here.
    assert len(track.joint_positions) == 15
    assert "mouth" in track.joint_positions
    assert set(track.joint_efforts) == set(track.joint_positions)
    assert set(track.base) == {"base_x", "base_y", "base_z", "base_roll_rad"}
    assert "kinematic IK plan" in track.comment
