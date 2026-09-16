"""Reader for the reference gait CSVs under ``tools/matlab/data/``.

File shape
----------
The first line is a ``#`` comment carrying the provenance and the plan parameters. The
second line is the header, and the data starts on the third. Columns are::

    t_s
    q_<joint> ...      15 columns, radians, one per movable URDF joint
    tau_<joint> ...    15 columns, N.m, the plan's feed-forward torque
    base_x, base_y, base_z, base_roll_rad

The joint column names are ``q_<urdf joint name>``, so they are matched **by name** against
the URDF. Nothing in this module assumes a column position, and nothing assumes the URDF
document order or the policy contract order.

What these files are not
------------------------
They are quasi-static kinematic inverse-kinematics plans, not hardware logs and not the
output of a trained policy. ``step_len = 0.01 m`` and ``speed = 0.01 m/s`` for both files.
They are used here to prove that the description animates and that a JointState stream at a
known rate is well formed. A gait that *looks* right in RViz says nothing about whether it
would balance on hardware, because RViz integrates no dynamics at all.
"""

from __future__ import annotations

import csv
import statistics
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

_ARRAY_FIELDS = ("base_x", "base_y", "base_z", "base_roll_rad")


@dataclass(frozen=True)
class GaitTrack:
    """One parsed gait CSV."""

    path: str
    comment: str
    times_s: tuple[float, ...]
    """Timestamps made relative to the first sample, so playback always starts at 0."""
    joint_positions: dict[str, tuple[float, ...]] = field(default_factory=dict)
    joint_efforts: dict[str, tuple[float, ...]] = field(default_factory=dict)
    base: dict[str, tuple[float, ...]] = field(default_factory=dict)

    @property
    def samples(self) -> int:
        return len(self.times_s)

    @property
    def duration_s(self) -> float:
        return self.times_s[-1] - self.times_s[0] if self.times_s else 0.0

    @property
    def nominal_hz(self) -> float:
        """Median sample rate. Median, not mean, so one timestamp glitch cannot skew it."""
        if len(self.times_s) < 2:
            return 0.0
        deltas = [b - a for a, b in zip(self.times_s, self.times_s[1:])]
        median = statistics.median(deltas)
        return 1.0 / median if median > 0 else 0.0

    @property
    def uniform(self) -> bool:
        """True when every step is within 1 % of the median step."""
        if len(self.times_s) < 3:
            return True
        deltas = [b - a for a, b in zip(self.times_s, self.times_s[1:])]
        median = statistics.median(deltas)
        if median <= 0:
            return False
        return all(abs(d - median) <= 0.01 * median for d in deltas)

    def index_at(self, t_rel: float) -> int:
        """Index of the newest sample at or before ``t_rel`` (clamped to the track)."""
        if not self.times_s:
            raise ValueError("empty track")
        return max(0, min(self.samples - 1, bisect_right(self.times_s, t_rel) - 1))

    def joint_names(self) -> list[str]:
        return list(self.joint_positions)


def load_gait_csv(path: str | Path) -> GaitTrack:
    """Parse a gait CSV. Raises ``ValueError`` with a readable message on a malformed file."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"gait CSV not found: {csv_path}")

    comments: list[str] = []
    header: list[str] | None = None
    rows: list[list[str]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                if header is None:
                    comments.append(line.lstrip()[1:].strip())
                continue
            if header is None:
                header = [cell.strip() for cell in next(csv.reader([line]))]
                continue
            rows.append(next(csv.reader([line])))

    if header is None:
        raise ValueError(f"{csv_path}: no header line found")
    if not rows:
        raise ValueError(f"{csv_path}: header found but no data rows")
    if "t_s" not in header:
        raise ValueError(f"{csv_path}: header has no 't_s' column (found {header[:6]}...)")

    columns: dict[str, list[float]] = {name: [] for name in header}
    for line_no, row in enumerate(rows, start=1):
        if len(row) != len(header):
            raise ValueError(
                f"{csv_path}: data row {line_no} has {len(row)} fields, header has {len(header)}"
            )
        for name, cell in zip(header, row):
            try:
                columns[name].append(float(cell))
            except ValueError as exc:
                raise ValueError(
                    f"{csv_path}: data row {line_no}, column '{name}': {cell!r} is not a number"
                ) from exc

    raw_times = columns["t_s"]
    if any(b < a for a, b in zip(raw_times, raw_times[1:])):
        raise ValueError(f"{csv_path}: t_s is not monotonically non-decreasing")
    t0 = raw_times[0]
    times = tuple(t - t0 for t in raw_times)

    joint_positions: dict[str, tuple[float, ...]] = {}
    joint_efforts: dict[str, tuple[float, ...]] = {}
    for name in header:
        if name.startswith("q_"):
            joint_positions[name[2:]] = tuple(columns[name])
        elif name.startswith("tau_"):
            joint_efforts[name[4:]] = tuple(columns[name])

    if not joint_positions:
        raise ValueError(f"{csv_path}: no 'q_<joint>' columns found")

    base = {name: tuple(columns[name]) for name in _ARRAY_FIELDS if name in columns}

    return GaitTrack(
        path=str(csv_path),
        comment=" ".join(comments),
        times_s=times,
        joint_positions=joint_positions,
        joint_efforts=joint_efforts,
        base=base,
    )


def map_track_to_urdf_joints(
    track: GaitTrack, urdf_joint_names: list[str]
) -> tuple[dict[str, tuple[float, ...]], list[str], list[str]]:
    """Select and order the track's columns for the joints a URDF actually declares.

    Returns ``(ordered_positions, matched_names, warnings)`` where ``ordered_positions`` is
    keyed in ``urdf_joint_names`` order. Every URDF joint without a column, and every column
    without a URDF joint, is reported as a warning rather than silently dropped -- a typo in
    one of the two files would otherwise look like a joint that simply does not move.
    """
    warnings: list[str] = []
    ordered: dict[str, tuple[float, ...]] = {}
    matched: list[str] = []

    for name in urdf_joint_names:
        if name in track.joint_positions:
            ordered[name] = track.joint_positions[name]
            matched.append(name)
        else:
            warnings.append(
                f"URDF joint '{name}' has no 'q_{name}' column in {Path(track.path).name}; "
                "it will be published at 0.0"
            )

    for name in track.joint_positions:
        if name not in urdf_joint_names:
            warnings.append(
                f"column 'q_{name}' in {Path(track.path).name} matches no movable URDF joint; ignored"
            )

    if not matched:
        raise ValueError(
            f"{Path(track.path).name}: none of its q_* columns match a movable URDF joint "
            f"(columns: {sorted(track.joint_positions)}; URDF: {urdf_joint_names})"
        )
    return ordered, matched, warnings


def finite_difference(values: tuple[float, ...], times: tuple[float, ...]) -> tuple[float, ...]:
    """Numerical derivative, central inside and one-sided at the ends.

    The CSVs carry no velocity column, and a JointState with empty ``velocity`` is legal but
    makes RViz's and ``rqt``'s displays less useful. This is a display aid only; it is not
    the velocity that a controller should consume, which comes from the encoder over the link.
    """
    n = len(values)
    if n == 0:
        return ()
    if n == 1:
        return (0.0,)
    out: list[float] = [0.0] * n
    for i in range(n):
        if i == 0:
            dt = times[1] - times[0]
            out[i] = (values[1] - values[0]) / dt if dt else 0.0
        elif i == n - 1:
            dt = times[n - 1] - times[n - 2]
            out[i] = (values[n - 1] - values[n - 2]) / dt if dt else 0.0
        else:
            dt = times[i + 1] - times[i - 1]
            out[i] = (values[i + 1] - values[i - 1]) / dt if dt else 0.0
    return tuple(out)
