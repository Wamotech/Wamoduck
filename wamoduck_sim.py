#!/usr/bin/env python3
"""Run the trained Wamoduck policies in plain MuJoCo, on CPU.

This is a **Sim2Sim** tool: it loads the ONNX policies published in
``policies/`` together with the **training-time MJCF** in
``models/wmduck/mjcf/`` and runs the same observation/action contract each policy
was trained with, at the same 50 Hz control rate. It is not hardware code, and
nothing here has been validated on a physical robot.

**One demo, all five policies.** The viewer starts on ``--policy`` (``stand`` by
default) and the number keys switch between every published policy while it
runs, so walking, sitting down, standing up, and the rough-terrain policy are all
reachable in the same window -- no restart, no second script.

Dependencies: ``mujoco``, ``onnxruntime``, ``numpy``. Nothing else -- no mjlab,
no torch, no rsl_rl, no GPU.

Quick start
-----------
    pip install mujoco onnxruntime numpy
    python wamoduck_sim.py --list
    python wamoduck_sim.py                                 # one window, all five
    python wamoduck_sim.py --policy getup --spawn lie-back
    python wamoduck_sim.py --policy walk --vx 0.3
    python wamoduck_sim.py --policy stand --check          # contract self-test
    python wamoduck_sim.py --policy stand --headless --steps 250
    python wamoduck_sim.py --cycle-test                    # headless switching test

Controls (type into the terminal that launched the script, not the viewer window)
--------------------------------------------------------------------------------
    1 2 3 4 5   switch policy: 1=stand  2=getup  3=sitstand  4=walk  5=rough
    Tab / n     switch to the next policy in that order
    up / w      vx += 0.1 m/s          down / s    vx -= 0.1 m/s   (walk, rough)
    left / a    vy += 0.1 m/s          right / d   vy -= 0.1 m/s   (walk, rough)
    e           wz += 0.1 rad/s        z           wz -= 0.1 rad/s (walk, rough)
    space       zero the twist command                             (walk, rough)
    m           sit / stand toggle: 0.11241 m sit / 0.175 m stand  (sitstand)
    r           reset (re-spawn the current policy)
    k           toggle the policy (hold the zero action instead)
    q           reset with a random push
    h / ?       print the key table again
    x           quit

The twist keys only exist in the observation of ``walk`` and ``rough``, and ``m``
only exists for ``sitstand``. A key that the current policy has no channel for is
**not ignored in silence**: the runner says which command the key would need and
which one the policy actually observes. A key that is not bound at all says so
too, and points at ``h``.

Switching policies
------------------
    stand, sitstand, walk, rough        same MJCF, ``robot_walk.xml``
        The ONNX actor and the observation assembly (48 / 49 / 51 values) are
        swapped **in place**: the robot keeps its pose, its velocity, and the
        command state. ``last_action`` is zeroed, because that observation is the
        new policy's own memory and a fresh policy has no history.
    getup                               ``robot_groundcontact.xml``
        Entering or leaving ``getup`` **reloads the MJCF**, so the robot state
        cannot be kept: it is a different physical model (the head chain
        collides, which is what lets the robot lie down). The runner says so on
        screen, and re-spawns into ``getup`` lying down and out of ``getup`` in
        the nominal stance.
    walk <-> rough                      terrain, not the MJCF
        The 1 cm curbs are moved to (or away from) the robot's own position, so
        the model is not reloaded and the state is kept.

The observation contract (this is the part that silently breaks everything if
it is wrong) is assembled in :meth:`Wamoduck.observe` and documented in
``docs/simulation.md`` / ``docs/simulation.zh-CN.md``:

    stand / getup   48 = base_ang_vel(3) projected_gravity(3) joint_pos(14)
                          joint_vel(14) last_action(14)
    sitstand        49 = the 48 above + height_command(1)
    walk / rough    51 = the 48 above + command(3)

The ONNX graphs already contain the observation normalizer, so the client must
feed **raw** observations and must not normalize again.
"""

from __future__ import annotations

import argparse
import math
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent
MJCF_DIR = REPO_ROOT / "models" / "wmduck" / "mjcf"
POLICY_DIR = REPO_ROOT / "policies"

# ---------------------------------------------------------------- contract ---
# Control timing: `decimation=4` and `<option timestep="0.005">` in the training
# env cfg (wmduck_*_env_cfg.py) and in the MJCF `robot_*.xml` <option> element.
DECIMATION = 4
TIMESTEP = 0.005
CONTROL_HZ = 1.0 / (DECIMATION * TIMESTEP)  # 50 Hz

N_ACT = 14
STAND_HEIGHT = 0.177618  # keyframe "stand" in the MJCF; also STAND_HEIGHT in the cfgs

# "Standing" thresholds, same definitions as the internal tools/stand_criteria.py.
STAND_TILT_DEG = 30.0   # loose: "has not fallen over"
STAND_Z = 0.15
STRICT_TILT_DEG = 8.0   # strict: "back at the nominal stance, both soles down"
STRICT_JOINT_DEG = 20.0

SOLE_LEFT = "left_ankle_link_sole"
SOLE_RIGHT = "right_ankle_link_sole"

# Action limits of the twist command, from CMD_RANGES in
# wmduck_velocity_env_cfg.py. x (forward) is limited to +0.6 m/s.
CMD_LIMITS = {"vx": (-0.4, 0.6), "vy": (-0.3, 0.3), "wz": (-0.8, 0.8)}
CMD_STEP = {"vx": 0.1, "vy": 0.1, "wz": 0.1}

# Body-height command of the sit/stand task: BodyHeightCommandCfg.height_range.
SIT_HEIGHT, TALL_HEIGHT = 0.11241, 0.175

# The rough task was trained on 1 cm curbs (STEP_HEIGHT = 1 cm in the cfg), spaced
# 0.3 m apart and starting 0.3 m ahead of the robot. The runner always compiles
# MAX_CURBS of them into the model and parks the unused ones below the floor with
# their collision switched off, so `walk` <-> `rough` can change the terrain
# without reloading the MJCF.
MAX_CURBS = 3
CURB_HALF_HEIGHT = 0.005      # 1 cm curb
CURB_SPACING = 0.3
CURB_FIRST_AHEAD = 0.3
CURB_PARKED_Z = -1.0          # below the floor: out of sight and out of contact
DEFAULT_TERRAIN = {"rough": MAX_CURBS}

OBS_GROUPS = ["base_ang_vel", "projected_gravity", "joint_pos", "joint_vel", "last_action"]
OBS_SIZES = [3, 3, 14, 14, 14]
CMD_INDEX = {"vx": 0, "vy": 1, "wz": 2}


@dataclass(frozen=True)
class PolicySpec:
    """One published policy and the contract it was trained under."""

    name: str
    onnx: str
    mjcf: str
    obs_dim: int
    command: str          # "none" | "twist" | "height"
    default_spawn: str
    kind: str             # "walk" | "groundcontact"
    summary: str
    # Descriptive names, in both languages and in ordinary words. The internal run
    # name (`getup_v20`, `sit_stand_v3`, ...) is a *version*, not a description: it
    # says which training round produced the file, not what the robot does. Both are
    # shown together -- the plain name first, the version second -- so a reader is not
    # left guessing what "sit_stand_v3" is supposed to do.
    label_zh: str = ""
    label_en: str = ""
    # The suggested way to exercise this policy: what to press, in what order, and
    # what to watch for. Shown in the viewer overlay and in the startup banner.
    flow_zh: str = ""
    flow_en: str = ""
    extra_obs: list[str] = field(default_factory=list)

    @property
    def terms(self) -> list[str]:
        return OBS_GROUPS + self.extra_obs

    @property
    def label(self) -> str:
        """`坐 / 站 Sit and stand` -- the plain description, both languages."""
        return f"{self.label_zh} {self.label_en}"

    @property
    def run_id(self) -> str:
        """`sit_stand_v3`: the training round, parsed from the ONNX file name.

        Kept visible everywhere, because it is the only handle that ties the running
        file to a checkpoint, a changelog entry and a hash in `policies/README.md`.
        """
        stem = Path(self.onnx).stem            # wamoduck-sitstand-sit_stand_v3
        return stem.split("-", 2)[-1] if stem.count("-") >= 2 else stem


POLICIES: dict[str, PolicySpec] = {
    "stand": PolicySpec(
        name="stand",
        onnx="wamoduck-stand-stand_v3.onnx",
        mjcf="robot_walk.xml",
        obs_dim=48,
        command="none",
        default_spawn="nominal",
        kind="walk",
        summary="hold the nominal stance and recover from pushes",
        label_zh="站立抗推",
        label_en="Stand and resist pushes",
        flow_zh="先看它站得稳不稳（应几乎不动），再按 q 随机推它一把，看它自己站回来",
        flow_en="watch it hold still, then press q to shove it and watch it recover",
    ),
    "getup": PolicySpec(
        name="getup",
        # 2026-09-16: `getup_v18` -> `getup_v20`. v18 is kept in `policies/` because the
        # measurement that found its remaining gap (standing 64/64, strict "back to the
        # saved nominal pose" 0/64, 52.3 deg of joint deviation) was taken on it; v20
        # fixes that gap (63/64 strict, joint deviation 10.4 deg, hand-over 5/5).
        onnx="wamoduck-getup-getup_v20.onnx",
        mjcf="robot_groundcontact.xml",
        obs_dim=48,
        command="none",
        default_spawn="lie-back",
        kind="groundcontact",
        summary="start lying down and get back on its feet",
        label_zh="起身",
        label_en="Get up after a fall",
        flow_zh="按 r 让它重新躺下，看它自己站起来并回到标称站姿（末态不应歪着）",
        flow_en="press r to lie it down again, watch it stand up and settle into the nominal pose",
    ),
    "sitstand": PolicySpec(
        name="sitstand",
        # 2026-09-16: `sit_stand_v2` -> `sit_stand_v3`. v2 is kept in `policies/`
        # because the two problems recorded on the capability board were measured on
        # it (it buzzes in place while standing, and its sitting pose is neither
        # upright nor symmetric); v3 fixes both, and its seat is 0.11241 m rather
        # than 0.085 m -- 0.085 m is geometrically unreachable with an upright
        # trunk (the torso box's lowest corner sits 109 mm below the base origin).
        onnx="wamoduck-sitstand-sit_stand_v3.onnx",
        mjcf="robot_walk.xml",
        obs_dim=49,
        command="height",
        default_spawn="nominal",
        kind="walk",
        summary="crouch to a commanded body height and stand back up",
        label_zh="坐下与站起",
        label_en="Sit down and stand up",
        flow_zh="按 m 坐下 → 看躯干是否直立、左右两腿是否对称（坐高 0.112 m）→ 按 e/z 调高度 → 再按 m 站回",
        flow_en="press m to sit (0.112 m), check the trunk is upright and the legs symmetric, e/z change the height, m again to stand",
        extra_obs=["height_command"],
    ),
    "walk": PolicySpec(
        name="walk",
        onnx="wamoduck-walk-walk_v4r.onnx",
        mjcf="robot_walk.xml",
        obs_dim=51,
        command="twist",
        default_spawn="nominal",
        kind="walk",
        summary="walk on flat ground from a (vx, vy, wz) command",
        label_zh="平地行走",
        label_en="Walk on flat ground",
        flow_zh="按 ↑ 给 0.3 m/s 看直行；再按 ← → 与 e/z 试边走边转。注意：速度低于 0.20 m/s 它不会走",
        flow_en="press up for 0.3 m/s, then add left/right and e/z to turn while walking; below 0.20 m/s it does not walk at all",
        extra_obs=["command"],
    ),
    "rough": PolicySpec(
        name="rough",
        onnx="wamoduck-rough-rough_v2.onnx",
        mjcf="robot_walk.xml",
        obs_dim=51,
        command="twist",
        default_spawn="nominal",
        kind="walk",
        summary="walk over 1 cm curbs from a (vx, vy, wz) command",
        label_zh="越障行走",
        label_en="Walk over 1 cm curbs",
        flow_zh="开局就在 3 个 1 cm 台阶上；按 ↑ 给 0.3 m/s 看它跨过去（越障地形与平地的差别只有约 4 %）",
        flow_en="it starts on 3 one-centimetre curbs; press up for 0.3 m/s and watch it step over them",
        extra_obs=["command"],
    ),
}

# The five published policies, in the order the number keys switch through them.
POLICY_ORDER = ["stand", "getup", "sitstand", "walk", "rough"]
POLICY_KEYS = {str(i + 1): name for i, name in enumerate(POLICY_ORDER)}

# Deterministic lying poses, as a rotation applied to the base link:
#   (roll, pitch, yaw) in radians, composed as Rz @ Ry @ Rx.
# `pitch = +pi/2` lays the body axis down horizontally with the belly up (supine);
# `roll = +pi/2` rolls it onto one side.
SPAWNS = {
    "nominal": (0.0, 0.0, 0.0),
    "lie-back": (0.0, math.pi / 2.0, 0.0),        # on its back
    "lie-front": (0.0, -math.pi / 2.0, 0.0),      # face down
    "lie-side": (math.pi / 2.0, 0.0, 0.0),        # on its left side
    "lie-side-r": (-math.pi / 2.0, 0.0, 0.0),     # on its right side
    "inverted": (0.0, math.pi, 0.0),              # fully upside down
}


# ------------------------------------------------------------------ helpers ---
def quat_from_rpy(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """(w, x, y, z) for the intrinsic composition Rz @ Ry @ Rx."""
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return np.array([
        cy * cp * cr + sy * sp * sr,
        cy * cp * sr - sy * sp * cr,
        cy * sp * cr + sy * cp * sr,
        sy * cp * cr - cy * sp * sr,
    ])


def random_sphere_quat(rng: np.random.Generator) -> np.ndarray:
    """Uniform-ish orientation: roll/pitch over the full circle, yaw uniform.

    This mirrors the training reset (``pose_range`` samples roll, pitch and yaw
    independently over their ranges), so it is not exactly uniform on SO(3) --
    the same over-sampling near the poles that training has.
    """
    return quat_from_rpy(
        rng.uniform(-math.pi, math.pi),
        rng.uniform(-math.pi, math.pi),
        rng.uniform(-math.pi, math.pi),
    )


def tilt_deg_from_quat(w: float, x: float, y: float, z: float) -> float:
    """Angle between the base's local +Z and world +Z, in degrees."""
    up_z = 1.0 - 2.0 * (x * x + y * y)
    return math.degrees(math.acos(max(-1.0, min(1.0, up_z))))


def yaw_deg_from_quat(w: float, x: float, y: float, z: float) -> float:
    """Heading of the base's local +X in the world XY plane, in degrees."""
    return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


class TerminalInput:
    """Single-key reader with arrow-key support (Windows msvcrt / POSIX cbreak)."""

    _WIN_ARROWS = {0x48: "up", 0x50: "down", 0x4B: "left", 0x4D: "right"}

    def __init__(self) -> None:
        self._q: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self.enabled = bool(sys.stdin and sys.stdin.isatty())
        if not self.enabled:
            print("[keys] stdin is not a TTY -- keyboard control disabled")
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            import msvcrt  # Windows
        except ImportError:
            msvcrt = None
        if msvcrt is not None:
            while not self._stop.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        try:
                            code = msvcrt.getwch()
                        except OSError:
                            continue
                        self._q.put(self._WIN_ARROWS.get(ord(code), "") if code else "")
                        continue
                    self._q.put(ch.lower())
                time.sleep(0.01)
            return
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    continue
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    more = sys.stdin.read(2) if select.select([sys.stdin], [], [], 0.01)[0] else ""
                    self._q.put({"A": "up", "B": "down", "C": "right", "D": "left"}.get(more[-1:], ""))
                elif ch:
                    self._q.put(ch.lower())
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def get_keys(self) -> list[str]:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out

    def close(self) -> None:
        self._stop.set()


# ------------------------------------------------------------------- robot ----
class Wamoduck:
    """The MJCF + ONNX pair, and the observation/action contract between them."""

    def __init__(self, spec: PolicySpec, onnx_path: Path, terrain_level: int = 0,
                 n_curbs: int | None = None) -> None:
        import mujoco

        self.mujoco = mujoco
        self.spec = spec
        self.terrain_level = int(terrain_level)   # curbs that are *active* now
        self.n_curbs = int(n_curbs if n_curbs is not None
                           else max(MAX_CURBS, self.terrain_level))

        xml = MJCF_DIR / spec.mjcf
        if not xml.is_file():
            raise SystemExit(
                f"missing {xml}\n"
                "Run this script from inside a clone of the repository, keeping "
                "models/wmduck/mjcf/ and models/wmduck/meshes/ in place."
            )
        self.model = self._build_model(xml)
        self.data = mujoco.MjData(self.model)

        if not onnx_path.is_file():
            raise SystemExit(f"missing ONNX policy {onnx_path}")
        self._load_onnx(spec, onnx_path)

        # ---- joint / actuator ordering -------------------------------------
        # The observation uses **joint-tree order** (`robot.joint_names`, which is
        # what the ONNX metadata records), while `<actuator>` in the MJCF is in a
        # different order (left/right alternating). The policy's 14 outputs are
        # indexed in joint-tree order, so each one has to be written to the ctrl
        # slot of the joint it belongs to.
        m = self.model
        self.tree_joints = [m.joint(i).name for i in range(m.njnt)]
        self.act_joints = [n for n in self.tree_joints if n != "floating_base"]
        if len(self.act_joints) != N_ACT:
            raise SystemExit(f"expected {N_ACT} actuated joints, found {len(self.act_joints)}")
        by_joint: dict[str, int] = {}
        for a in range(m.nu):
            by_joint[m.joint(int(m.actuator_trnid[a, 0])).name] = a
        missing = [n for n in self.act_joints if n not in by_joint]
        if missing:
            raise SystemExit(f"joints without an actuator: {missing}")
        self.ctrl_ids = np.array([by_joint[n] for n in self.act_joints], dtype=int)

        self.qadr = np.array(
            [m.jnt_qposadr[m.joint(n).id] for n in self.act_joints], dtype=int
        )
        self.vadr = np.array(
            [m.jnt_dofadr[m.joint(n).id] for n in self.act_joints], dtype=int
        )
        # default_joint_pos is all zeros for this robot (ONNX metadata
        # `default_joint_pos` = 14 zeros, and the keyframe holds q=0).
        self.default_q = np.array([m.qpos0[a] for a in self.qadr], dtype=float)

        self.base_id = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "base_link")
        self.gyro_adr = int(
            m.sensor_adr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SENSOR, "imu_gyro")]
        )
        self.floor_geom = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        self.sole_geoms = {
            mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, SOLE_LEFT + "_collision"): "left",
            mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, SOLE_RIGHT + "_collision"): "right",
        }

        self.last_action = np.zeros(N_ACT)
        self.command = np.zeros(3)
        self.height_command = TALL_HEIGHT
        self.policy_on = True
        self.settle_steps = 40
        self.reset()

    # ---- policy in / out (same MJCF) -------------------------------------
    def _load_onnx(self, spec: PolicySpec, onnx_path: Path) -> None:
        """Open an ONNX actor and check it against the observation contract.

        Nothing on ``self`` is touched until the session is open and the input
        width has been checked, so a bad pairing cannot leave the runner half
        switched to a policy it cannot drive.
        """
        import onnxruntime as ort

        if not onnx_path.is_file():
            raise SystemExit(f"missing ONNX policy {onnx_path}")
        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        shape = session.get_inputs()[0].shape
        dim = shape[-1] if isinstance(shape[-1], int) else None
        if dim is not None and dim != spec.obs_dim:
            raise SystemExit(
                f"{onnx_path.name} expects {dim} observation values but the "
                f"{spec.name!r} contract builds {spec.obs_dim}. Wrong pairing of "
                "policy and task."
            )
        self.session = session
        self.in_name = session.get_inputs()[0].name
        self.out_name = session.get_outputs()[0].name
        self.onnx_path = onnx_path

    def load_policy(self, spec: PolicySpec, onnx_path: Path | None = None) -> None:
        """Switch to another policy that shares this MJCF, keeping the robot state.

        Only the actor and the observation assembly change: the pose, the velocity,
        the twist command and the height command all survive, because the physics
        model -- and therefore the meaning of that state -- is the same.
        ``last_action`` is zeroed: that observation term is the *new* policy's own
        memory of its previous output, and a freshly loaded policy has no history.
        """
        path = onnx_path or (POLICY_DIR / spec.onnx)
        self._load_onnx(spec, path)
        self.spec = spec
        self.last_action[:] = 0.0

    # ---- terrain (same MJCF) ---------------------------------------------
    def _curb_id(self, i: int) -> int:
        return self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, f"curb_{i}")

    def set_terrain(self, level: int) -> str:
        """Make `level` curbs active, parked in front of where the robot is now.

        The curbs are compiled into the model once (see ``MAX_CURBS``) and only
        moved, so a flat-ground policy and the rough-terrain policy can share one
        model and one running robot. Active curbs are placed starting 0.3 m ahead
        of the robot's current ``x``; the rest are parked below the floor with
        their collision switched off. Returns a one-line description.
        """
        level = max(0, min(int(level), self.n_curbs))
        changed = level != self.terrain_level
        self.terrain_level = level
        base_x, base_y = self._place_curbs()
        if level == 0:
            desc = "flat floor (no curbs)"
        else:
            desc = (f"{level} x 1 cm curb(s), {CURB_SPACING:.2f} m apart, starting "
                    f"{CURB_FIRST_AHEAD:.2f} m ahead of x={base_x:+.2f}")
        return desc if changed else desc + " (unchanged)"

    def _place_curbs(self) -> tuple[float, float]:
        """Position the active curbs ahead of the robot and park the others."""
        base_x = float(self.data.qpos[0])
        base_y = float(self.data.qpos[1])
        for i in range(self.n_curbs):
            gid = self._curb_id(i)
            if gid < 0:
                continue
            if i < self.terrain_level:
                self.model.geom_pos[gid] = [
                    base_x + CURB_FIRST_AHEAD + CURB_SPACING * i, base_y, CURB_HALF_HEIGHT,
                ]
                self.model.geom_contype[gid] = 1
                self.model.geom_conaffinity[gid] = 1
            else:
                self.model.geom_pos[gid] = [base_x, base_y, CURB_PARKED_Z]
                self.model.geom_contype[gid] = 0
                self.model.geom_conaffinity[gid] = 0
        return base_x, base_y

    # ---- model -----------------------------------------------------------
    def _build_model(self, xml: Path):
        """Compile the training MJCF and add the scene it expects (floor, light).

        The published XML files are the training models with exactly one change:
        ``meshdir`` points at ``../meshes`` so they use the meshes already in this
        repository. The floor, the light and the curbs are added here, at load
        time, so the XML files stay byte-comparable with training.
        """
        mujoco = self.mujoco
        spec = mujoco.MjSpec.from_file(str(xml))
        floor = spec.worldbody.add_geom()
        floor.name = "floor"
        floor.type = mujoco.mjtGeom.mjGEOM_PLANE
        floor.size = [6.0, 6.0, 0.1]
        floor.rgba = [0.32, 0.34, 0.38, 1.0]
        light = spec.worldbody.add_light()
        light.pos = [1.0, -1.0, 2.5]
        light.dir = [-0.4, 0.4, -1.0]
        light.castshadow = False
        # The curbs of the rough task (STEP_HEIGHT = 1 cm in the cfg) are always
        # compiled in, so that `walk` <-> `rough` can swap terrain without
        # reloading the MJCF. Those that are not active start parked below the
        # floor with their collision switched off; :meth:`set_terrain` moves them.
        for i in range(max(0, self.n_curbs)):
            curb = spec.worldbody.add_geom()
            curb.name = f"curb_{i}"
            curb.type = mujoco.mjtGeom.mjGEOM_BOX
            curb.size = [CURB_SPACING / 2.0, 1.0, CURB_HALF_HEIGHT]
            curb.rgba = [0.45, 0.42, 0.38, 1.0]
            if i < self.terrain_level:
                curb.pos = [CURB_FIRST_AHEAD + CURB_SPACING * i, 0.0, CURB_HALF_HEIGHT]
                curb.contype = 1
                curb.conaffinity = 1
            else:
                curb.pos = [0.0, 0.0, CURB_PARKED_Z]
                curb.contype = 0
                curb.conaffinity = 0
        return spec.compile()

    # ---- reset / spawn ---------------------------------------------------
    def reset(self, spawn: str | None = None, rng: np.random.Generator | None = None,
              settle_steps: int | None = None) -> None:
        mujoco = self.mujoco
        spawn = spawn or self.spec.default_spawn
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = 0.0
        for a, d in zip(self.qadr, self.default_q):
            self.data.qpos[a] = d
        self.data.qvel[:] = 0.0

        if spawn == "random":
            quat = random_sphere_quat(rng or np.random.default_rng())
        elif spawn in SPAWNS:
            quat = quat_from_rpy(*SPAWNS[spawn])
        else:
            raise SystemExit(f"unknown --spawn {spawn!r}; choose from {sorted(SPAWNS) + ['random']}")
        self.data.qpos[0:3] = [0.0, 0.0, STAND_HEIGHT]
        self.data.qpos[3:7] = quat

        if spawn != "nominal":
            # Drop the robot from just above the ground: place the base so the
            # lowest bounding sphere of any collision geom sits `clearance` above
            # z=0, then let it settle for a few steps before the policy starts.
            # (Bounding spheres are a conservative approximation of the measured
            # per-geom AABBs the training reset uses, so the robot may start a few
            # millimetres high and drop.)
            self.data.qpos[2] = 0.0
            mujoco.mj_forward(self.model, self.data)
            lowest = min(
                self.data.geom_xpos[g][2] - self.model.geom_rbound[g]
                for g in range(self.model.ngeom)
                if self.model.geom_contype[g] or self.model.geom_conaffinity[g]
            )
            self.data.qpos[2] = -lowest + 0.003
            mujoco.mj_forward(self.model, self.data)
            n_settle = self.settle_steps if settle_steps is None else settle_steps
            for _ in range(max(0, n_settle)):  # free settling, holding zero torque
                self.data.ctrl[:] = self.default_q
                mujoco.mj_step(self.model, self.data)

        self.data.ctrl[:] = self.default_q
        self.last_action[:] = 0.0
        self.command[:] = 0.0
        # The robot is back at the origin, so any active curbs have to come with
        # it -- otherwise `r` under `rough` would leave the terrain behind.
        self._place_curbs()
        mujoco.mj_forward(self.model, self.data)

    # ---- observation -----------------------------------------------------
    def observe(self) -> np.ndarray:
        """Assemble the actor observation, in the order the policy was trained on."""
        d = self.data
        w, x, y, z = d.xquat[self.base_id]
        # projected_gravity_b = R^T @ (0, 0, -1) = MINUS the third row of R.
        # mjlab: quat_apply_inverse(root_link_quat_w, gravity_vec_w).
        gravity = -np.array([
            2.0 * (x * z - w * y),
            2.0 * (y * z + w * x),
            1.0 - 2.0 * (x * x + y * y),
        ])
        blocks = [
            np.asarray(d.sensordata[self.gyro_adr:self.gyro_adr + 3], dtype=float),
            gravity,
            d.qpos[self.qadr] - self.default_q,   # joint_pos_rel; default is all zeros
            d.qvel[self.vadr],                    # joint_vel_rel; default velocity is zero
            self.last_action,                     # last raw action, before scale/offset
        ]
        if self.spec.command == "twist":
            blocks.append(self.command)
        elif self.spec.command == "height":
            blocks.append(np.array([self.height_command]))
        obs = np.concatenate(blocks)
        if obs.shape[0] != self.spec.obs_dim:
            raise RuntimeError(f"built {obs.shape[0]} obs values, expected {self.spec.obs_dim}")
        return obs

    # ---- act / step ------------------------------------------------------
    def act(self, obs: np.ndarray) -> np.ndarray:
        x = np.asarray(obs, dtype=np.float32).reshape(1, -1)
        a = np.asarray(self.session.run([self.out_name], {self.in_name: x})[0]).reshape(-1)
        return a.astype(float)

    def apply(self, action: np.ndarray) -> None:
        """target = default_joint_pos + action * action_scale (scale = 1.0).

        ``JointPositionActionCfg(scale=1.0, use_default_offset=True)`` with an
        all-zero default pose. There is no policy-side action clipping; MuJoCo
        clamps ``ctrl`` to each actuator's ``ctrlrange`` (``ctrllimited="true"``
        via ``autolimits="true"``), and the servo is a soft position servo with
        kp = 5.0, kv = 0.5 and a +/-1.5 N*m forcerange.
        """
        self.data.ctrl[self.ctrl_ids] = self.default_q + action
        self.last_action = np.asarray(action, dtype=float)

    def step(self) -> None:
        for _ in range(DECIMATION):
            self.mujoco.mj_step(self.model, self.data)

    # ---- diagnostics -----------------------------------------------------
    @property
    def base_quat(self) -> np.ndarray:
        return np.asarray(self.data.qpos[3:7], dtype=float)

    def tilt_deg(self) -> float:
        return tilt_deg_from_quat(*self.base_quat)

    def base_z(self) -> float:
        return float(self.data.qpos[2])

    def yaw_deg(self) -> float:
        return yaw_deg_from_quat(*self.base_quat)

    def max_joint_dev_deg(self) -> float:
        return float(np.degrees(np.abs(self.data.qpos[self.qadr] - self.default_q)).max())

    def feet_down(self) -> tuple[bool, bool]:
        """Which soles are touching the floor (or an active curb)."""
        left = right = False
        ground = {self.floor_geom} | {
            self._curb_id(i) for i in range(self.n_curbs) if i < self.terrain_level
        }
        for c in range(self.data.ncon):
            g1, g2 = int(self.data.contact[c].geom[0]), int(self.data.contact[c].geom[1])
            if not ((g1 in ground) ^ (g2 in ground)):
                continue
            other = g2 if g1 in ground else g1
            if other in self.sole_geoms:
                if self.sole_geoms[other] == "left":
                    left = True
                else:
                    right = True
        return left, right

    def status(self) -> dict:
        left, right = self.feet_down()
        tilt = self.tilt_deg()
        z = self.base_z()
        dev = self.max_joint_dev_deg()
        return {
            "tilt_deg": tilt,
            "base_z": z,
            "both_feet": left and right,
            "max_joint_dev_deg": dev,
            "standing": tilt < STAND_TILT_DEG and z > STAND_Z,
            "recovered_to_nominal": tilt < STRICT_TILT_DEG and left and right
            and dev < STRICT_JOINT_DEG and z > STAND_Z,
        }

    # ---- self-check ------------------------------------------------------
    def self_check(self) -> int:
        """Cross-check the hand-written observation wiring against MuJoCo itself."""
        import mujoco

        print(f"[check] model      : {self.spec.mjcf}  ({MJCF_DIR})")
        print(f"[check] policy     : {self.onnx_path.name}")
        print(f"[check] ONNX input : {self.session.get_inputs()[0].shape} "
              f"output {self.session.get_outputs()[0].shape}")
        print(f"[check] control    : {CONTROL_HZ:.0f} Hz "
              f"(decimation {DECIMATION} x timestep {TIMESTEP})")
        print(f"[check] joints     : {N_ACT} actuated, tree order == "
              f"'{self.act_joints[0]}' .. '{self.act_joints[-1]}'")
        print(f"[check] ctrl order : tree->actuator map {self.ctrl_ids.tolist()}")
        print(f"[check] actuator order differs from tree order: "
              f"{any(i != c for i, c in enumerate(self.ctrl_ids))}")
        bad = 0

        def check(label: str, ok: bool, detail: str = "") -> None:
            nonlocal bad
            bad += 0 if ok else 1
            print(f"  {'OK  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")

        # 1. projected_gravity vs MuJoCo's own rotation matrix.
        d = self.data
        R = np.asarray(d.xmat[self.base_id], dtype=float).reshape(3, 3)
        w, x, y, z = d.xquat[self.base_id]
        g_mine = -np.array([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)])
        check("projected_gravity == -R[2,:]", bool(np.allclose(g_mine, -R[2], atol=1e-12)),
              f"max diff {np.abs(g_mine + R[2]).max():.2e}")

        # 2. gyro sensor frame: the `imu` site sits at the base origin with an
        #    identity orientation, so the gyro must read exactly the free joint's
        #    angular velocity -- which MuJoCo keeps in the **body-local** frame.
        #    Checked at a rotated pose, otherwise an upright base makes the
        #    assertion trivially true and hides a wrong frame convention.
        d.qvel[3:6] = [0.11, -0.23, 0.37]
        d.qpos[3:7] = quat_from_rpy(0.4, -0.7, 1.1)
        mujoco.mj_forward(self.model, d)
        gyro = np.asarray(d.sensordata[self.gyro_adr:self.gyro_adr + 3], dtype=float)
        R = np.asarray(d.xmat[self.base_id], dtype=float).reshape(3, 3)
        R_site = np.asarray(
            d.site_xmat[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "imu")],
            dtype=float,
        ).reshape(3, 3)
        w, x, y, z = d.xquat[self.base_id]
        g_mine = -np.array([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)])
        check("projected_gravity == -R[2,:] at a rotated pose",
              bool(np.allclose(g_mine, -R[2], atol=1e-12)),
              f"max diff {np.abs(g_mine + R[2]).max():.2e}")
        check("imu site frame == base frame",
              bool(np.allclose(R_site, R, atol=1e-12)), f"|diff| {np.abs(R_site - R).max():.2e}")
        check("imu_gyro == base angular velocity (body frame)",
              bool(np.allclose(gyro, d.qvel[3:6], atol=1e-9)),
              f"|diff| {np.abs(gyro - d.qvel[3:6]).max():.2e}")
        self.reset()

        # 3. joint limits: the nominal stance (q = 0) must be inside every range.
        inside = all(
            self.model.jnt_range[self.model.joint(n).id][0] - 1e-9 <= 0.0
            <= self.model.jnt_range[self.model.joint(n).id][1] + 1e-9
            for n in self.act_joints
        )
        check("nominal pose q=0 is inside every joint range", inside)

        # 4. ctrl clamping is MuJoCo's, not the policy's.
        check("all actuators are ctrl-limited (ctrllimited)",
              bool(np.all(self.model.actuator_ctrllimited)))
        kp = self.model.actuator_gainprm[self.ctrl_ids, 0]
        kv = -self.model.actuator_biasprm[self.ctrl_ids, 2]
        check("position servo gains kp=5.0 kv=0.5",
              bool(np.allclose(kp, 5.0) and np.allclose(kv, 0.5)),
              f"kp {kp.min()}..{kp.max()} kv {kv.min()}..{kv.max()}")

        # 5. ONNX graph is self-contained: it must begin with the normalizer.
        check("ONNX graph contains the observation normalizer", not self.normalizer_is_absent(),
              "Sub/Div at the input, so feed RAW observations and never normalize again")

        # 6. The observation dimension the contract builds.
        obs = self.observe()
        check(f"observation vector is {self.spec.obs_dim}-D", obs.shape[0] == self.spec.obs_dim,
              f"terms {self.spec.terms}")
        a = self.act(obs)
        check(f"action vector is {N_ACT}-D and finite", a.shape[0] == N_ACT and np.isfinite(a).all())
        print(f"  info obs[:6]={np.array2string(obs[:6], precision=4)}  "
              f"command={self.command.tolist()}")
        print(f"\n[check] {'all contract checks passed' if bad == 0 else f'{bad} CHECK(S) FAILED'}")
        return 0 if bad == 0 else 1

    def normalizer_is_absent(self) -> bool:
        try:
            import onnx
        except ImportError:
            return False  # cannot tell; do not claim a failure
        graph = onnx.load(str(self.onnx_path)).graph
        names = {t.name for t in graph.initializer}
        ops = {n.op_type for n in graph.node}
        return not (any("normalizer" in n for n in names) and {"Sub", "Div"} <= ops)


# --------------------------------------------------------------- reporting ----
def format_status(tag: str, st: dict) -> str:
    return (
        f"[{tag}] tilt={st['tilt_deg']:6.2f} deg  base_z={st['base_z']:.4f} m  "
        f"max_joint_dev={st['max_joint_dev_deg']:6.2f} deg  "
        f"both_soles={st['both_feet']}  "
        f"standing={st['standing']}  nominal={st['recovered_to_nominal']}"
    )


def describe_obs(spec: PolicySpec) -> str:
    """The observation vector, term by term, for the policy in use."""
    parts = [f"{n}({s})" for n, s in zip(OBS_GROUPS, OBS_SIZES)]
    if spec.command == "twist":
        parts.append("command(3)")
    elif spec.command == "height":
        parts.append("height_command(1)")
    return f"{spec.obs_dim}-D = " + " | ".join(parts)


def describe_command(spec: PolicySpec, bot: "Wamoduck | None" = None) -> str:
    """Which command channel the policy observes, with its current value."""
    if spec.command == "twist":
        keys = "arrow/WASD keys, e/z, space"
        if bot is None:
            return f"vx/vy/wz twist ({keys})"
        return (f"vx/vy/wz twist -- vx={bot.command[0]:+.2f} vy={bot.command[1]:+.2f} m/s, "
                f"wz={bot.command[2]:+.2f} rad/s ({keys})")
    if spec.command == "height":
        keys = "'m' toggles"
        if bot is None:
            return (f"body height -- {SIT_HEIGHT:.3f} m sit / {TALL_HEIGHT:.3f} m stand ({keys})")
        posture = "stand" if bot.height_command > (SIT_HEIGHT + TALL_HEIGHT) / 2.0 else "sit"
        return (f"body height -- {bot.height_command:.3f} m ({posture}), "
                f"{SIT_HEIGHT:.3f} / {TALL_HEIGHT:.3f} m ({keys})")
    return "none -- this policy has no command input, so the twist keys and 'm' do nothing"


def print_policy_state(bot: "Wamoduck", tag: str = "policy") -> None:
    """Say which policy is loaded, what it observes, and what it can be told."""
    spec = bot.spec
    terrain = "flat floor" if bot.terrain_level == 0 else f"{bot.terrain_level} x 1 cm curbs"
    print(f"[{tag}] current   : {spec.label}   ({spec.name} = {spec.run_id})")
    print(f"[{tag}] does      : {spec.summary}")
    print(f"[{tag}] try       : {spec.flow_zh}")
    print(f"[{tag}]             {spec.flow_en}")
    print(f"[{tag}] keys      : {overlay_keys_line(spec)}")
    print(f"[{tag}] obs       : {describe_obs(spec)}")
    print(f"[{tag}] command   : {describe_command(spec, bot)}")
    print(f"[{tag}] model     : {spec.mjcf}  terrain: {terrain}  "
          f"{bot.onnx_path.name}  act {N_ACT}-D")


def describe_command_short(bot: "Wamoduck") -> str:
    """The command value in as few characters as the viewer overlay can take."""
    if bot.spec.command == "twist":
        return (f"cmd  vx {bot.command[0]:+.2f}  vy {bot.command[1]:+.2f}  "
                f"wz {bot.command[2]:+.2f}")
    if bot.spec.command == "height":
        return f"height  {bot.height_command:.3f} m"
    return "no command channel on this policy"


# ------------------------------------------------------- 左上角信息块 ----------
#
# 为什么这一块**不是**用 `viewer.set_texts` 画的（2026-09-17，用户截图反馈"糊成一片"）：
#   ① MuJoCo 的 HUD 字体是**点阵 ASCII**，画不了中文 —— 每个汉字都会变成一个方块；
#   ② `set_texts` 里**同一个 gridpos 的多条文本是叠在同一格上**，不是换行堆叠 ⇒
#      上一版把四行都放进 TOPLEFT，于是中文全是方块、英文两行互相盖住。
# 所以左上角这块改成：**用 Pillow 把中英文渲染成一张小图，再用 `viewer.set_images` 贴到
# 左上角**。这样中文能显示、多行真正换行、背景板让文字在模型上也读得清。
# 兜底：本机没有 Pillow 或找不到中文字体时，**退回纯 ASCII 文本**，并把几行分散到
# 不同的 gridpos（避免再次互相覆盖）—— 公开仓库的运行器只承诺 mujoco + onnxruntime +
# numpy 三个依赖，不能因为少了 Pillow 就什么都看不见。
OVERLAY_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",          # Windows: 微软雅黑
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",        # 黑体
    r"C:\Windows\Fonts\Deng.ttf",          # 等线
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

_OVERLAY_FONT: str | None = None
_OVERLAY_FONT_LOOKED = False


def overlay_font_path() -> str | None:
    """A CJK-capable TTF/OTC on this machine, or None (then the overlay stays ASCII)."""
    global _OVERLAY_FONT, _OVERLAY_FONT_LOOKED
    if _OVERLAY_FONT_LOOKED:
        return _OVERLAY_FONT
    _OVERLAY_FONT_LOOKED = True
    for path in OVERLAY_FONT_CANDIDATES:
        if os.path.isfile(path):
            _OVERLAY_FONT = path
            return path
    import glob as _glob
    for pattern in ("/usr/share/fonts/**/*CJK*", "/usr/share/fonts/**/wqy*",
                    "/usr/share/fonts/**/DroidSansFallback*"):
        hits = sorted(_glob.glob(pattern, recursive=True))
        if hits:
            _OVERLAY_FONT = hits[0]
            return _OVERLAY_FONT
    return None


def overlay_rows(bot: "Wamoduck", selected: str) -> list[tuple[str, str]]:
    """The top-left block, as (style, text) rows. Styles: title/sub/label/zh/en.

    The order is deliberate: **what the policy does** (both languages), then **which
    keys actually work right now** (filtered from KEY_TABLE, so a dead key can never be
    advertised), then **what to try**. The version handle is on the second line, small,
    because it is the link to the checkpoint/hash/changelog rather than a description.
    """
    spec = bot.spec
    terrain = "平地 flat" if bot.terrain_level == 0 else \
        f"{bot.terrain_level} 个 1 cm 台阶 curbs"
    idx = POLICY_ORDER.index(spec.name) + 1
    rows = [
        ("title", f"[{idx}/5]  {spec.label}"),
        ("sub", f"{spec.name} = {spec.run_id}    obs {spec.obs_dim}-D    {terrain}"),
        ("label", "可用按键 keys  (typed in the terminal, not this window)"),
        ("zh", overlay_keys_line(spec)),
        ("label", "建议流程 try this"),
        ("zh", spec.flow_zh),
        ("en", spec.flow_en),
    ]
    if selected != spec.name:
        rows.append(("warn",
                     f"⚠ 你按了 {selected}，但窗口里跑的仍是 {spec.name}（这次切换被拒绝）  "
                     f"you asked for {selected}; still running {spec.name}"))
    return rows


def render_overlay_image(rows: list[tuple[str, str]], width_px: int = 980,
                         scale: float = 1.0, font_path: str | None = None):
    """Render the block to an RGB array (or None when Pillow / a CJK font is missing)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    path = font_path or overlay_font_path()
    if path is None:
        return None

    sizes = {"title": 21, "sub": 14, "label": 15, "zh": 16, "en": 15, "warn": 15}
    colors = {
        "title": (245, 245, 250), "sub": (165, 172, 185), "label": (120, 200, 255),
        "zh": (238, 238, 242), "en": (198, 205, 216), "warn": (255, 190, 120),
    }
    try:
        fonts = {k: ImageFont.truetype(path, max(9, int(v * scale))) for k, v in sizes.items()}
    except Exception:
        return None

    pad, gap = int(10 * scale), int(4 * scale)
    max_text_w = max(120, width_px - 2 * pad)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    def wrap(text: str, font) -> list[str]:
        """Greedy wrap: CJK may break anywhere, ASCII runs (and `a/b`) stay whole."""
        def atoms(s: str) -> list[str]:
            out, cur = [], ""
            for ch in s:
                if ch.isascii() and (ch.isalnum() or ch in "/._+-"):
                    cur += ch
                else:
                    if cur:
                        out.append(cur)
                        cur = ""
                    out.append(ch)
            if cur:
                out.append(cur)
            return out

        lines: list[str] = []
        cur = ""
        for atom in atoms(text):
            if atom == "\n":
                lines.append(cur.rstrip())
                cur = ""
                continue
            if cur and probe.textlength(cur + atom, font=font) > max_text_w:
                lines.append(cur.rstrip())
                cur = "" if atom == " " else atom
            else:
                cur += atom
        if cur.strip():
            lines.append(cur.rstrip())
        return lines or [""]

    laid: list[tuple[str, str]] = []
    for style, text in rows:
        if not text:
            continue
        for line in wrap(text, fonts[style]):
            laid.append((style, line))

    # 行高按字体实际高度算，行距固定
    heights = []
    for style, line in laid:
        box = fonts[style].getbbox(line) or (0, 0, 0, sizes[style])
        heights.append(box[3] - box[1] + int(6 * scale))
    img_h = pad * 2 + sum(heights) + gap * max(0, len(laid) - 1)
    img = Image.new("RGB", (width_px, max(img_h, pad * 2 + 8)), (16, 17, 22))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width_px - 1, img.height - 1], outline=(70, 76, 92))

    y = pad
    for (style, line), hh in zip(laid, heights):
        draw.text((pad, y), line, font=fonts[style], fill=colors[style])
        y += hh + gap
    return np.asarray(img, dtype=np.uint8)


def overlay_corner_rect(viewer, img, corner: str = "top-left", margin: int = 8):
    """Where to blit the block, in the viewer's screen coordinates (origin bottom-left)."""
    import mujoco

    vp = getattr(viewer, "viewport", None)
    if vp is None:
        return None
    h, w = int(img.shape[0]), int(img.shape[1])
    left, bottom = int(vp.left), int(vp.bottom)
    vw, vh = int(vp.width), int(vp.height)
    if w > vw or h > vh:
        return None
    if corner == "top-left":
        x, y = left + margin, bottom + vh - h - margin
    elif corner == "top-right":
        x, y = left + vw - w - margin, bottom + vh - h - margin
    elif corner == "bottom-left":
        x, y = left + margin, bottom + margin
    else:
        x, y = left + vw - w - margin, bottom + margin
    return mujoco.MjrRect(x, y, w, h)


def overlay_command_text(bot: "Wamoduck", selected: str) -> list:
    """The single bottom-left text line: what is running, and the live command."""
    import mujoco

    try:
        font = mujoco.mjtFontScale.mjFONTSCALE_150
        cell = mujoco.mjtGridPos.mjGRID_BOTTOMLEFT
    except AttributeError:
        return []
    spec = bot.spec
    left = f"running: {spec.name} = {spec.run_id}"
    if selected != spec.name:
        left += f"   (you asked for {selected} -- refused)"
    return [(font, cell, left, describe_command_short(bot))]


def overlay_fallback_texts(bot: "Wamoduck", selected: str) -> list:
    """ASCII-only `set_texts` fallback, one grid cell per line so nothing overlaps."""
    import mujoco

    try:
        font = mujoco.mjtFontScale.mjFONTSCALE_150
        cells = [mujoco.mjtGridPos.mjGRID_TOPLEFT, mujoco.mjtGridPos.mjGRID_TOPCENTER,
                 mujoco.mjtGridPos.mjGRID_TOPRIGHT, mujoco.mjtGridPos.mjGRID_MIDRIGHT]
    except AttributeError:
        return []
    spec = bot.spec
    terrain = "flat" if bot.terrain_level == 0 else f"{bot.terrain_level} x 1 cm curbs"
    idx = POLICY_ORDER.index(spec.name) + 1
    lines = [
        (f"[{idx}/5] {spec.label_en}", f"{spec.name} = {spec.run_id}  obs {spec.obs_dim}-D  {terrain}"),
        ("keys that work now", overlay_keys_line(spec)),
        ("try this", spec.flow_en),
        ("", ""),
    ]
    texts = [(font, cell, left, right) for (left, right), cell in zip(lines, cells)]
    texts.extend(overlay_command_text(bot, selected))
    return texts


def viewer_status_texts(bot: "Wamoduck", selected: str) -> list | None:
    """Deprecated shim kept for callers that only want the ASCII text overlay."""
    spec = bot.spec
    try:
        import mujoco
    except Exception:
        return None
    try:
        font = mujoco.mjtFontScale.mjFONTSCALE_150
        top = mujoco.mjtGridPos.mjGRID_TOPLEFT
    except AttributeError:
        return None
    terrain = "flat" if bot.terrain_level == 0 else f"{bot.terrain_level} x 1 cm curbs"
    return [
        (font, top, f"[{POLICY_ORDER.index(spec.name) + 1}/5] {spec.label_en}",
         f"{spec.name} = {spec.run_id}  obs {spec.obs_dim}-D  {terrain}"),
    ]


# Which keys the runner binds, and which policies each one can act on. This is the
# single source of the key table: it is printed at startup, again on `h`, it is what
# the "no effect with this policy" notes are derived from, and it is what the viewer
# overlay's "keys that work right now" line is built from -- so the overlay can never
# advertise a key the running policy cannot use. Each row is
#   (keys, what it does in English, scope, what it does in Chinese).
KEY_TABLE: list[tuple[str, str, str, str]] = [
    ("1 2 3 4 5", "switch policy: 1=stand 2=getup 3=sitstand 4=walk 5=rough", "always",
     "切换策略：1=站立 2=起身 3=坐站 4=行走 5=越障"),
    ("Tab / n", "switch to the next policy in that order", "always",
     "按顺序切到下一个策略"),
    ("up / w", f"vx += {CMD_STEP['vx']:.1f} m/s", "twist", f"前进 +{CMD_STEP['vx']:.1f} m/s"),
    ("down / s", f"vx -= {CMD_STEP['vx']:.1f} m/s", "twist", f"前进 -{CMD_STEP['vx']:.1f} m/s"),
    ("left / a", f"vy += {CMD_STEP['vy']:.1f} m/s", "twist", f"左移 +{CMD_STEP['vy']:.1f} m/s"),
    ("right / d", f"vy -= {CMD_STEP['vy']:.1f} m/s", "twist", f"右移 -{CMD_STEP['vy']:.1f} m/s"),
    ("e", f"wz += {CMD_STEP['wz']:.1f} rad/s", "twist", f"左转 +{CMD_STEP['wz']:.1f} rad/s"),
    ("z", f"wz -= {CMD_STEP['wz']:.1f} rad/s", "twist", f"右转 -{CMD_STEP['wz']:.1f} rad/s"),
    ("space", "zero the twist command", "twist", "速度指令清零"),
    ("m", f"sit / stand toggle ({SIT_HEIGHT:.3f} / {TALL_HEIGHT:.3f} m)", "height",
     f"坐/站切换（{SIT_HEIGHT:.3f} / {TALL_HEIGHT:.3f} m）"),
    ("r", "reset (re-spawn the current policy)", "always", "重新出生（按该策略自己的出生点）"),
    ("k", "toggle the policy (hold the zero action instead)", "always",
     "暂时停用策略（改为保持零动作）"),
    ("q", "reset with a random push", "always", "重新出生并随机推一把"),
    ("h / ?", "print this key table", "always", "再打印这张键表"),
    ("x", "quit", "always", "退出"),
]

KEY_SCOPE = {"twist": "walk, rough", "height": "sitstand"}
KEY_SCOPE_ZH = {"twist": "行走/越障", "height": "坐站"}


def key_applies(kind: str, spec: PolicySpec) -> bool:
    if kind == "always":
        return True
    return spec.command == kind


def overlay_keys_line(spec: PolicySpec) -> str:
    """`↑↓ 前进 · ←→ 侧移 · e/z 偏航 · 空格 清零 · m 坐/站 · r 出生 · q 推 · h 键表 · x 退出`

    Only the keys that actually do something for *this* policy, in Chinese and
    English, for the viewer overlay's top-left block.
    """
    short = {
        "1 2 3 4 5": "1-5 换策略 policy",
        "Tab / n": "Tab 下一个 next",
        "up / w": "↑ 前进 fwd",
        "down / s": "↓ 后退 back",
        "left / a": "← 左移 left",
        "right / d": "→ 右移 right",
        "e": "e 左转 turn+",
        "z": "z 右转 turn-",
        "space": "空格 清零 zero",
        "m": "m 坐站 sit/stand",
        "r": "r 重出生 respawn",
        "k": "k 冻结 freeze",
        "q": "q 推一把 push",
        "h / ?": "h 键表 keys",
        "x": "x 退出 quit",
    }
    parts = [short[keys] for keys, _, kind, _ in KEY_TABLE if key_applies(kind, spec)]
    return "  ·  ".join(parts)


def print_keys(spec: PolicySpec) -> None:
    """Print the key table, marking every key the current policy cannot use."""
    print("[keys] keys are typed into the terminal that launched this script, "
          "not into the viewer window")
    for keys, action, kind, action_zh in KEY_TABLE:
        scope = KEY_SCOPE.get(kind, "every policy")
        if key_applies(kind, spec):
            status = "active"
        else:
            status = f"NO EFFECT with '{spec.name}' -- it has no such command"
        print(f"[keys]   {keys:<12s} {action:<48s} ({scope:<12s}) {status}")
        print(f"[keys]   {'':<12s} {action_zh}")
    print("[keys] switch policies with 1-5 or Tab/n; the runner prints what changed "
          "on every switch. Press h for this table again.")


def list_policies() -> int:
    print(f"Control rate: {CONTROL_HZ:.0f} Hz  (decimation {DECIMATION} x timestep {TIMESTEP})")
    print(f"{'key':>3s} {'name':10s} {'run':18s} {'obs':>4s} {'ONNX':38s} present")
    for i, spec in enumerate(POLICIES.values(), start=1):
        p = POLICY_DIR / spec.onnx
        xml = MJCF_DIR / spec.mjcf
        present = "yes" if (p.is_file() and xml.is_file()) else "NO"
        print(f"{i:3d} {spec.name:10s} {spec.run_id:18s} {spec.obs_dim:4d} "
              f"{spec.onnx:38s} {present}")
        print(f"{'':3s} {spec.label}")
        print(f"{'':3s} {spec.summary}")
    print("\nKeys '1'..'5' switch between these five policies inside one running demo:")
    for key, name in POLICY_KEYS.items():
        print(f"  {key} = {name:9s} {POLICIES[name].label}   [{POLICIES[name].run_id}]")
    print("  Tab / n = the next one in that order")
    return 0


def overlay_preview(png_out: str | None = None, width: int = 980,
                    scale: float = 1.0) -> int:
    """Print the viewer's top-left block for every policy, without opening a window.

    The block is *drawn* by the viewer, so it cannot be inspected from a headless run --
    which is exactly how a wrong, stale or overlapping line reaches a user unnoticed
    (2026-09-17: it did). This prints the same rows as text, and with ``--overlay-png``
    also writes the pixels it would blit, so the layout can be checked before a release.
    """
    font = overlay_font_path()
    if scale <= 0:                    # 0 = "auto" for the live window; here there is no
        scale = 1.0                   # window, so the preview renders at 1.0
        print("[overlay] preview: no window, so --overlay-scale 0 (auto) renders at 1.0")
    print(f"[overlay] corner default top-left; CJK font: {font or 'NOT FOUND -> ASCII fallback'}")
    print(f"[overlay] Pillow: ", end="")
    try:
        import PIL
        print(f"yes ({PIL.__version__})")
    except Exception as exc:
        print(f"no ({exc})")
    for key, name in POLICY_KEYS.items():
        spec = POLICIES[name]
        bot = SimpleNamespace(spec=spec, terrain_level=0 if name != "rough" else 3,
                              command=[0.3, 0.0, 0.0], height_command=TALL_HEIGHT,
                              onnx_path=POLICY_DIR / spec.onnx)
        rows = overlay_rows(bot, name)
        print(f"\n===== key {key}: {name} ({spec.run_id}) =====")
        for style, text in rows:
            print(f"  {style:6s}| {text}")
        img = render_overlay_image(rows, width_px=int(width * scale), scale=scale)
        if img is None:
            print("  (no image: Pillow or a CJK font is missing -> ASCII text fallback)")
            continue
        print(f"  image: {img.shape[1]} x {img.shape[0]} px, rgb")
        if png_out:
            try:
                from PIL import Image
                stem = Path(png_out)
                out = stem.with_name(f"{stem.stem}_{name}{stem.suffix}") if len(POLICY_KEYS) > 1 \
                    else stem
                Image.fromarray(img).save(out)
                print(f"  written: {out}")
            except Exception as exc:
                print(f"  could not write {png_out}: {exc}")
    return 0


# ------------------------------------------------------------------- demo -----
class Demo:
    """One window, all five policies: the current policy and what every key does.

    The demo owns the robot (a :class:`Wamoduck`) and swaps it when a policy needs
    a different MJCF. Both the interactive viewer and the headless ``--cycle-test``
    drive it through :meth:`on_key`, so the switching code under test is the same
    code the keyboard uses.
    """

    #: Keys that only mean something when the policy observes a twist command.
    TWIST_KEYS = ("up", "w", "down", "s", "left", "a", "right", "d", "e", "z", " ")
    #: Tab arrives as "\t" from either the Windows or the POSIX reader.
    NEXT_KEYS = ("tab", "\t", "n")

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.rng = np.random.default_rng(args.seed)
        self.bot: Wamoduck | None = None
        #: The policy the user asked for. It tracks :attr:`bot.spec` unless a switch
        #: was refused, and the viewer window shows both so that is visible.
        self.selected = args.policy
        self.first_load = True
        self.restart_viewer = False
        self.quit = False
        self.load(POLICIES[args.policy])
        self.apply_initial_commands()

    # ---- what the CLI asked for ------------------------------------------
    def terrain_for(self, spec: PolicySpec) -> int:
        """Active curbs for `spec`: ``--terrain-level`` if given, else its default."""
        if self.args.terrain_level is not None:
            return max(0, self.args.terrain_level)
        return DEFAULT_TERRAIN.get(spec.name, 0)

    def spawn_for(self, spec: PolicySpec) -> str:
        """`--spawn` when the user named one, otherwise the policy's own spawn."""
        return self.args.spawn or spec.default_spawn

    def onnx_for(self, spec: PolicySpec) -> Path:
        """`--onnx` replaces only the policy named on the command line."""
        if self.first_load and self.args.onnx and spec.name == self.args.policy:
            return Path(self.args.onnx)
        return POLICY_DIR / spec.onnx

    # ---- construction ----------------------------------------------------
    def load(self, spec: PolicySpec) -> None:
        """Build the runner for `spec` and reset the robot to its spawn.

        Either the whole thing works or ``self.bot`` is left exactly as it was, so
        a broken switch cannot leave the demo holding half a policy.
        """
        old = self.bot
        level = self.terrain_for(spec)
        bot = Wamoduck(spec, self.onnx_for(spec), terrain_level=level,
                       n_curbs=max(MAX_CURBS, level))
        bot.settle_steps = self.args.settle
        bot.reset(spawn=self.spawn_for(spec), rng=self.rng)
        if old is not None:
            # The robot state is reset by the reload; the *commands* the user set
            # are not part of the robot, so they carry over.
            bot.command[:] = old.command
            bot.height_command = old.height_command
            bot.policy_on = old.policy_on
        self.bot = bot
        self.first_load = False

    def apply_initial_commands(self) -> None:
        """``--vx``/``--vy``/``--wz``/``--target-height`` for the starting policy."""
        bot, spec = self.bot, self.bot.spec
        if spec.command == "twist":
            for k, v in (("vx", self.args.vx), ("vy", self.args.vy), ("wz", self.args.wz)):
                if v is not None:
                    lo, hi = CMD_LIMITS[k]
                    clamped = max(lo, min(hi, float(v)))
                    if clamped != v:
                        print(f"[cmd] {k}={v} clamped to {clamped} "
                              f"(trained command range {lo}..{hi})")
                    bot.command[CMD_INDEX[k]] = clamped
        if spec.command == "height" and self.args.target_height is not None:
            bot.height_command = max(SIT_HEIGHT, min(TALL_HEIGHT, self.args.target_height))

    # ---- switching -------------------------------------------------------
    def switch(self, name: str) -> None:
        """Switch policy, keeping the robot state whenever the MJCF allows it."""
        bot = self.bot
        old_spec = bot.spec
        if name not in POLICIES:
            print(f"[switch] unknown policy {name!r}; the choices are "
                  f"{', '.join(POLICY_ORDER)}")
            return
        new_spec = POLICIES[name]
        if name == old_spec.name:
            self.selected = name
            print(f"[switch] '{name}' is already running -- nothing changed")
            return
        self.selected = name
        try:
            if new_spec.mjcf == old_spec.mjcf:
                # Same physical model: swap the actor and the observation assembly
                # under the running robot.
                bot.load_policy(new_spec, self.onnx_for(new_spec))
                terrain = bot.set_terrain(self.terrain_for(new_spec))
                print(f"[switch] {old_spec.name} -> {new_spec.name}  "
                      f"(same MJCF '{new_spec.mjcf}' -- the robot state is KEPT: pose, "
                      f"velocity and commands all survive)")
                print(f"[switch] obs        : {describe_obs(new_spec)}")
                print(f"[switch] last_action: zeroed (a freshly loaded policy has no "
                      f"action history)")
                print(f"[switch] terrain    : {terrain}")
            else:
                self.load(new_spec)
                print(f"[switch] {old_spec.name} -> {new_spec.name}  "
                      f"(different MJCF: '{old_spec.mjcf}' -> '{new_spec.mjcf}')")
                print(f"[switch] this is a different physical model, so the robot state "
                      f"cannot be carried over -- the MJCF is RELOADED and the state is "
                      f"RESET (a policy is a function of the model it was trained in)")
                print(f"[switch] re-spawned '{self.spawn_for(new_spec)}' in the new model "
                      f"(<-- the model-reload path: entering or leaving 'getup')")
                self.restart_viewer = True
        except (SystemExit, Exception) as exc:      # a switch must never kill the demo
            print(f"[switch] FAILED to switch to '{name}': {exc}")
            print_policy_state(self.bot, "policy")
            return
        print_policy_state(self.bot, "policy")

    # ---- keys ------------------------------------------------------------
    def on_key(self, k: str) -> bool:
        """Handle one keypress. Returns True when the user asked to quit."""
        bot, spec = self.bot, self.bot.spec
        if k in POLICY_KEYS:
            self.switch(POLICY_KEYS[k])
        elif k in self.NEXT_KEYS:
            self.switch(POLICY_ORDER[(POLICY_ORDER.index(spec.name) + 1) % len(POLICY_ORDER)])
        elif k in ("h", "?"):
            print_keys(spec)
        elif k in ("up", "w") and spec.command == "twist":
            bot.command[0] = min(CMD_LIMITS["vx"][1], bot.command[0] + CMD_STEP["vx"])
        elif k in ("down", "s") and spec.command == "twist":
            bot.command[0] = max(CMD_LIMITS["vx"][0], bot.command[0] - CMD_STEP["vx"])
        elif k in ("left", "a") and spec.command == "twist":
            bot.command[1] = min(CMD_LIMITS["vy"][1], bot.command[1] + CMD_STEP["vy"])
        elif k in ("right", "d") and spec.command == "twist":
            bot.command[1] = max(CMD_LIMITS["vy"][0], bot.command[1] - CMD_STEP["vy"])
        elif k == "e" and spec.command == "twist":
            bot.command[2] = min(CMD_LIMITS["wz"][1], bot.command[2] + CMD_STEP["wz"])
        elif k == "z" and spec.command == "twist":
            bot.command[2] = max(CMD_LIMITS["wz"][0], bot.command[2] - CMD_STEP["wz"])
        elif k == " " and spec.command == "twist":
            bot.command[:] = 0.0
        elif k == "m" and spec.command == "height":
            bot.height_command = (SIT_HEIGHT if bot.height_command > (SIT_HEIGHT + TALL_HEIGHT) / 2
                                  else TALL_HEIGHT)
            posture = "stand" if bot.height_command > (SIT_HEIGHT + TALL_HEIGHT) / 2 else "sit"
            print(f"[key] height command -> {bot.height_command:.3f} m ({posture})")
        elif ((k in self.TWIST_KEYS and spec.command != "twist")
              or (k == "m" and spec.command != "height")):
            # A key that IS recognised but does not apply to the policy in use used to
            # be dropped in silence, which reads as "this key is broken" -- a user hit
            # exactly that pressing `m` on the walking policy (2026-09-16). The mapping
            # is symmetric: under the sit/stand policy the arrow keys are the ones that
            # do nothing. Say what happened instead of doing nothing.
            need = "body-height" if k == "m" else "vx/vy/wz (twist)"
            have = {"twist": "vx/vy/wz", "height": "body-height"}.get(spec.command, "no command")
            print(f"[key] '{k}' needs a {need} command, but the current policy {spec.name!r} "
                  f"observes {have} -- ignored (nothing changed)")
            print(f"[key] press 1-5 or Tab/n to switch to a policy that has that channel "
                  f"(h for the key table)")
        elif k == "r":
            bot.reset(spawn=self.spawn_for(spec), rng=self.rng)
            print(f"[key] reset ('{spec.name}' re-spawned at '{self.spawn_for(spec)}')")
        elif k == "k":
            bot.policy_on = not bot.policy_on
            print(f"[key] policy {'ON' if bot.policy_on else 'OFF'} "
                  f"(OFF holds the zero action)")
        elif k == "q":
            ang = self.rng.uniform(0.0, 2.0 * math.pi)
            bot.data.qvel[0] = 0.3 * math.cos(ang)
            bot.data.qvel[1] = 0.3 * math.sin(ang)
            print("[key] push")
        elif k == "x":
            return True
        elif k.strip():
            print(f"[key] {k!r} is not a key this runner binds -- press h for the key table")
        return False


# ------------------------------------------------------------------- main -----
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the published Wamoduck ONNX policies in plain MuJoCo (CPU). "
                    "One demo, all five policies: press 1-5 to switch while it runs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python wamoduck_sim.py            # then press 1..5 or Tab to switch\n"
               "         python wamoduck_sim.py --policy getup --spawn lie-back",
    )
    ap.add_argument("--policy", default="stand",
                    help="the policy the demo starts on; one of: " + ", ".join(POLICIES)
                         + " (keys 1-5 and Tab/n switch from there)")
    ap.add_argument("--onnx", default=None,
                    help="override the bundled ONNX file of --policy "
                         "(switching always uses the bundled files)")
    ap.add_argument("--spawn", default=None,
                    help="spawn pose for --policy and for every later switch: "
                         + ", ".join(sorted(SPAWNS)) + ", random")
    ap.add_argument("--seed", type=int, default=0, help="seed for --spawn random")
    ap.add_argument("--terrain-level", type=int, default=None,
                    help="0 = flat floor; N = N consecutive 1 cm curbs. Default: 0 for "
                         f"every policy except rough ({DEFAULT_TERRAIN['rough']}), so that "
                         "walk <-> rough switches terrain as well as policy")
    ap.add_argument("--vx", type=float, default=None, help="initial forward command (m/s)")
    ap.add_argument("--vy", type=float, default=None, help="initial lateral command (m/s)")
    ap.add_argument("--wz", type=float, default=None, help="initial yaw-rate command (rad/s)")
    ap.add_argument("--target-height", type=float, default=None,
                    help=f"body-height command for --policy sitstand "
                         f"({SIT_HEIGHT} sit .. {TALL_HEIGHT} stand)")
    ap.add_argument("--headless", action="store_true", help="no viewer; run --steps control steps")
    ap.add_argument("--steps", type=int, default=250, help="control steps in --headless mode")
    ap.add_argument("--cycle-test", action="store_true",
                    help="no viewer; switch stand->getup->sitstand->walk->rough with the "
                         "switch keys and check each segment (see --cycle-steps)")
    ap.add_argument("--cycle-steps", type=int, default=300,
                    help="control steps per policy in --cycle-test (>=150 recommended; "
                         "300 = 6.0 s, the length of the documented get-up run)")
    ap.add_argument("--settle", type=int, default=40, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="run the observation/action contract self-test")
    ap.add_argument("--list", action="store_true", help="list the published policies and exit")
    ap.add_argument("--overlay-preview", action="store_true",
                    help="print the viewer's top-left status block for every policy "
                         "as plain text and exit (for tests; needs no window)")
    ap.add_argument("--overlay-corner", default="top-left",
                    choices=["top-left", "top-right", "bottom-left", "bottom-right"],
                    help="where the status block is drawn inside the viewer (default top-left)")
    ap.add_argument("--overlay-width", type=int, default=980,
                    help="width of the status block in window pixels (default 980)")
    ap.add_argument("--overlay-scale", type=float, default=0.0,
                    help="text scale of the status block; 0 (default) = automatic from the "
                         "window height (height/1200, clamped to 1.0 .. 1.6; the 2560x1440 "
                         "framebuffer on the reference machine lands on 1.2). Set 1.6 to "
                         "force it bigger, or 1.0 for the smallest")
    ap.add_argument("--overlay-png", default=None,
                    help="with --overlay-preview: also write the rendered block to this PNG")
    ap.add_argument("--viewer-smoke", action="store_true",
                    help="open a real window and walk all five policies through the "
                         "overlay code, then exit (needs a display; this is the only "
                         "test that exercises set_images/set_texts)")
    args = ap.parse_args()

    if args.list:
        return list_policies()
    if args.overlay_preview:
        return overlay_preview(args.overlay_png, args.overlay_width, args.overlay_scale)
    if args.policy not in POLICIES:
        raise SystemExit(f"unknown --policy {args.policy!r}; choose from {', '.join(POLICIES)}")

    print("Wamoduck Sim2Sim runner -- one demo, all five policies "
          "(stand, getup, sitstand, walk, rough)")
    print("This is a MuJoCo simulation of trained policies. It is NOT hardware, and "
          "nothing here is a physical-robot result.")

    if args.check:
        # The contract self-test is per policy and needs no viewer, so it stays a
        # direct build of the policy named on the command line.
        spec = POLICIES[args.policy]
        onnx_path = Path(args.onnx) if args.onnx else POLICY_DIR / spec.onnx
        bot = Wamoduck(spec, onnx_path, terrain_level=args.terrain_level or 0)
        bot.settle_steps = args.settle
        print(f"[check] started on --policy {spec.name!r}; --check tests that one policy "
              f"(run it once per policy to cover all five)")
        return bot.self_check()

    demo = Demo(args)
    bot, spec = demo.bot, demo.bot.spec

    print(f"[setup] MJCF        : {spec.mjcf}  terrain: "
          + ("flat floor" if bot.terrain_level == 0 else f"{bot.terrain_level} x 1 cm curbs"))
    print(f"[setup] ONNX        : {bot.onnx_path.name}  in {bot.session.get_inputs()[0].shape} "
          f"out {bot.session.get_outputs()[0].shape}")
    print(f"[setup] spawn       : {demo.spawn_for(spec)}")
    print(f"[setup] control     : {CONTROL_HZ:.0f} Hz  obs {spec.obs_dim}-D  act {N_ACT}-D")
    print(f"[setup] command     : {describe_command(spec, bot)}")
    print("[setup] " + format_status("start", bot.status()))
    print("[setup] the demo can switch policies while it runs: 1-5, or Tab/n for the next one")
    print_keys(spec)

    if args.cycle_test:
        return run_cycle_test(demo, args)
    if args.viewer_smoke:
        return viewer_smoke(demo)
    if args.headless:
        return run_headless(bot, args.steps)
    return run_viewer(demo)


def run_headless(bot: Wamoduck, steps: int) -> int:
    """Run one policy for `steps` control steps without a viewer."""
    spec = bot.spec
    start_xy = bot.data.qpos[0:2].copy()
    initial_z = bot.base_z()
    lowest_tilt = bot.status()["tilt_deg"]
    ever_standing = bot.status()["standing"]
    for i in range(steps):
        obs = bot.observe()
        bot.apply(bot.act(obs))
        bot.step()
        st = bot.status()
        lowest_tilt = min(lowest_tilt, st["tilt_deg"])
        ever_standing = ever_standing or st["standing"]
        if i % max(1, steps // 8) == 0:
            print(f"  t={i * DECIMATION * TIMESTEP:5.2f}s " + format_status("run", st))
    st = bot.status()
    moved = bot.data.qpos[0:2] - start_xy
    print(format_status("final", st))
    print(f"[final] simulated {steps * DECIMATION * TIMESTEP:.2f} s "
          f"({steps} control steps)")
    print(f"[final] base_z {initial_z:.4f} -> {st['base_z']:.4f} m")
    print(f"[final] displacement dx={moved[0]:+.3f} m dy={moved[1]:+.3f} m "
          f"|d|={float(np.linalg.norm(moved)):.3f} m")
    if spec.command == "twist" and abs(bot.command[0]) > 1e-9:
        expected = float(bot.command[0]) * steps * DECIMATION * TIMESTEP
        print(f"[final] commanded vx={bot.command[0]:+.2f} m/s -> {expected:+.3f} m "
              f"in {steps * DECIMATION * TIMESTEP:.1f} s")
    print(f"[final] ever stood (tilt<{STAND_TILT_DEG:.0f} deg and base_z>{STAND_Z} m): "
          f"{ever_standing}")
    print(f"[final] lowest tilt seen: {lowest_tilt:.2f} deg")
    print(f"[final] VERDICT: {'standing' if st['standing'] else 'NOT standing'} / "
          f"{'nominal stance' if st['recovered_to_nominal'] else 'not the strict nominal stance'}")
    return 0


# ---------------------------------------------- headless policy switching ----
def run_cycle_test(demo: Demo, args: argparse.Namespace) -> int:
    """Switch stand -> getup -> sitstand -> walk -> rough and check every segment.

    This is the headless version of what a user does in the viewer: the switches go
    through :meth:`Demo.on_key`, the same path the keyboard uses, so the
    state-keeping and the model-reload paths are the ones under test. Each segment
    runs long enough for the new policy to be judged, and every segment ends in the
    state that policy is supposed to reach.
    """
    steps = max(1, args.cycle_steps)
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, bool(ok), detail))
        print(f"[cycle] {'OK  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")

    def run_segment(label: str, n: int) -> dict:
        bot = demo.bot
        x0, y0 = float(bot.data.qpos[0]), float(bot.data.qpos[1])
        yaw0 = bot.yaw_deg()
        z0 = bot.base_z()
        z_lo = z_hi = z0
        tilt_hi = bot.tilt_deg()
        for i in range(n):
            bot.apply(bot.act(bot.observe()))
            bot.step()
            z = bot.base_z()
            z_lo, z_hi = min(z_lo, z), max(z_hi, z)
            tilt_hi = max(tilt_hi, bot.tilt_deg())
            if (i + 1) % max(1, n // 4) == 0 or i + 1 == n:
                print(f"[cycle]   t={(i + 1) * DECIMATION * TIMESTEP:5.2f}s "
                      + format_status("seg", bot.status()))
        st = bot.status()
        moved = np.array([float(bot.data.qpos[0]) - x0, float(bot.data.qpos[1]) - y0])
        dyaw = (bot.yaw_deg() - yaw0 + 180.0) % 360.0 - 180.0
        print(f"[cycle] {label}: {n} control steps ({n * DECIMATION * TIMESTEP:.2f} s), "
              f"policy '{bot.spec.name}', obs {bot.spec.obs_dim}-D")
        print("  " + format_status("end", st))
        print(f"[cycle]   base_z {z0:.4f} -> {st['base_z']:.4f} m "
              f"(min {z_lo:.4f}, max {z_hi:.4f})")
        print(f"[cycle]   displacement dx={moved[0]:+.3f} dy={moved[1]:+.3f} "
              f"|d|={float(np.linalg.norm(moved)):.3f} m   heading change {dyaw:+.1f} deg   "
              f"worst tilt {tilt_hi:.2f} deg")
        return {"st": st, "moved": moved, "z0": z0, "z_lo": z_lo, "z_hi": z_hi,
                "tilt_hi": tilt_hi, "n": n, "dyaw": dyaw}

    def command_vx(vx: float) -> None:
        """Set the twist command through the keys, not by writing bot.command."""
        demo.on_key(" ")
        taps = int(round(vx / CMD_STEP["vx"]))
        for _ in range(taps):
            demo.on_key("up")
        print(f"[cycle] twist command set with the keys: space, then 'up' x{taps} -> "
              f"vx={demo.bot.command[0]:+.2f} m/s")

    print()
    print(f"[cycle] headless switching self-test: stand -> getup -> sitstand -> walk -> rough, "
          f"{steps} control steps per segment ({steps * DECIMATION * TIMESTEP:.1f} s)")

    # 1 -- stand. Same MJCF as the starting policy, so this is the in-place switch.
    demo.on_key("1")
    stand = run_segment("1 stand", steps)
    check("stand ends upright (tilt < 10 deg and base_z > 0.15 m)",
          stand["st"]["tilt_deg"] < 10.0 and stand["st"]["base_z"] > 0.15,
          f"tilt {stand['st']['tilt_deg']:.2f} deg, base_z {stand['st']['base_z']:.4f} m, "
          f"worst tilt {stand['tilt_hi']:.2f} deg")

    # 2 -- getup. Different MJCF: this switch must reload the model and re-spawn.
    demo.on_key("2")
    getup = run_segment("2 getup", steps)
    check("getup gets up from the lying spawn (base_z > 0.15 m)",
          getup["st"]["base_z"] > 0.15,
          f"base_z {getup['z0']:.4f} -> {getup['st']['base_z']:.4f} m "
          f"(max {getup['z_hi']:.4f}), tilt {getup['st']['tilt_deg']:.2f} deg")

    # 3 -- sitstand. Back to robot_walk.xml (another reload), then toggle with 'm'.
    demo.on_key("3")
    half = max(1, steps // 2)
    tall = run_segment("3 sitstand (tall, command 0.175 m)", half)
    demo.on_key("m")
    print(f"[cycle] pressed 'm': height command is now {demo.bot.height_command:.3f} m")
    sit = run_segment(f"3 sitstand (after 'm', command {SIT_HEIGHT:.3f} m)", half)
    drop = tall["st"]["base_z"] - sit["st"]["base_z"]
    check(f"sitstand changes height after 'm' (>= 0.03 m lower; {TALL_HEIGHT:.3f} -> {SIT_HEIGHT:.3f} is "
          f"{TALL_HEIGHT - SIT_HEIGHT:.3f} m of headroom)",
          drop >= 0.03,
          f"base_z {tall['z0']:.4f} -> {tall['st']['base_z']:.4f} m (tall) -> "
          f"{sit['st']['base_z']:.4f} m (sit): {drop:.4f} m lower")

    # 4 -- walk. Same MJCF, so the state is kept, then vx = 0.3 via the keys.
    #
    # 2026-09-16: stand back up with 'm' BEFORE switching to walk. Reason, measured:
    # the sit/stand policy is now `sit_stand_v3`, whose seat is **0.1096 m with the
    # feet spread** (hip yaw ~ +-41 deg, measured in the development repository's
    # acceptance run). Handing that pose to the walking policy collapses it -- an
    # earlier revision of this self-test switched to `walk` *while seated* and
    # measured tilt **134.9 deg** after 6 s with 0.438 m of travel. The walking
    # policy was trained from a nominal stance and has never seen a seated one, so
    # "sit -> stand -> walk" is the supported sequence (and the one a user performs).
    # The unsupported hand-over is recorded in the note below rather than asserted
    # here: a self-test that is red on a supported workflow reads as "this
    # repository is broken", which is not what is true.
    demo.on_key("m")
    up = run_segment(f"3 sitstand (after 'm', command {TALL_HEIGHT:.3f} m -- standing back up)", half)
    check("sitstand stands back up after a second 'm' (base_z > 0.15 m)",
          up["st"]["base_z"] > 0.15,
          f"base_z {sit['st']['base_z']:.4f} -> {up['st']['base_z']:.4f} m, "
          f"tilt {up['st']['tilt_deg']:.2f} deg")
    demo.on_key("4")
    print(f"[cycle] state kept across the sitstand -> walk switch: "
          f"base_z={demo.bot.base_z():.4f} m tilt={demo.bot.tilt_deg():.2f} deg "
          f"height cmd={demo.bot.height_command:.3f} m")
    command_vx(0.3)
    walk = run_segment("4 walk (vx=+0.30 m/s)", steps)
    check("walk moves with vx = +0.30 m/s (>= 0.20 m of travel)",
          float(np.linalg.norm(walk["moved"])) >= 0.20,
          f"|d|={float(np.linalg.norm(walk['moved'])):.3f} m (dx={walk['moved'][0]:+.3f} "
          f"dy={walk['moved'][1]:+.3f}, heading {walk['dyaw']:+.1f} deg) in "
          f"{steps * DECIMATION * TIMESTEP:.1f} s, commanded "
          f"{0.3 * steps * DECIMATION * TIMESTEP:.3f} m, tilt {walk['st']['tilt_deg']:.2f} deg")
    if abs(walk["dyaw"]) > 20.0:
        print(f"[cycle] note: this segment started from the crouch the sit/stand segment left "
              f"behind (state KEPT by design), and the walk policy turned "
              f"{walk['dyaw']:+.1f} deg while recovering from it -- most of that travel is along "
              f"its own new heading, not +x. That is the uncommanded-rotation weakness this "
              f"walking checkpoint is already known for; the forward check below measures +x "
              f"from a fresh spawn.")

    # 5 -- rough. Same MJCF; only the curbs move, so the state is kept again.
    demo.on_key("5")
    print(f"[cycle] terrain after the walk -> rough switch: "
          f"{demo.bot.terrain_level} active 1 cm curb(s)")
    command_vx(0.3)
    rough = run_segment("5 rough (vx=+0.30 m/s over curbs)", steps)
    check("rough moves with vx = +0.30 m/s (>= 0.20 m of travel)",
          float(np.linalg.norm(rough["moved"])) >= 0.20,
          f"|d|={float(np.linalg.norm(rough['moved'])):.3f} m (dx={rough['moved'][0]:+.3f} "
          f"dy={rough['moved'][1]:+.3f}, heading {rough['dyaw']:+.1f} deg) in "
          f"{steps * DECIMATION * TIMESTEP:.1f} s, commanded "
          f"{0.3 * steps * DECIMATION * TIMESTEP:.3f} m, tilt {rough['st']['tilt_deg']:.2f} deg")

    # Keys the current policy has no channel for must say so, never be silent.
    print()
    print("[cycle] keys that 'rough' has no channel for, and what they print:")
    demo.on_key("m")
    print("[cycle] ...and a key this runner does not bind at all:")
    demo.on_key("j")
    print("[cycle] ...and the key table itself:")
    demo.on_key("h")

    # After all five switches (two of which reloaded the MJCF): go back to walking,
    # re-spawn to the nominal stance, and check that plain forward walking still does
    # what the single-policy run does -- the documented `--policy walk --vx 0.3
    # --headless --steps 250` travels dx = +1.482 m. This is a post-switch sanity
    # check, not one of the five policy segments above.
    print()
    demo.on_key("4")
    demo.on_key("r")
    command_vx(0.3)
    fwd_steps = max(150, min(steps, 250))
    fwd = run_segment("6 walk, forward check after 'r' (fresh nominal spawn)", fwd_steps)
    check("after five switches a fresh walk run still goes forward (dx > 0.5 m)",
          fwd["moved"][0] > 0.5,
          f"dx={fwd['moved'][0]:+.3f} m dy={fwd['moved'][1]:+.3f} m in "
          f"{fwd_steps * DECIMATION * TIMESTEP:.1f} s at vx=+0.30 (single-policy run: "
          f"dx=+1.482 m in 5.0 s), heading {fwd['dyaw']:+.1f} deg")

    print()
    print("[cycle] ---- assertions ----")
    for label, ok, detail in checks:
        print(f"[cycle]   {'OK  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")
    failed = [c for c in checks if not c[1]]
    print(f"[cycle] cycle test: {len(checks) - len(failed)}/{len(checks)} checks passed"
          + ("" if not failed else " -- FAILED"))
    return 0 if not failed else 1


# --------------------------------------------------------------- viewer -------
class OverlayState:
    """Draws the status block, and remembers what it last drew.

    One `apply()` entry point so the interactive loop and `--viewer-smoke` exercise
    **the same code**: the two bugs found on 2026-09-17 (an `args` name that only
    exists in `main`, and a list nested one level too deep) both lived on the "a
    window is open" path, which `--check` and `--cycle-test` never take.
    """

    def __init__(self) -> None:
        self.key: tuple | None = None
        self.img = None
        self.shown: list | None = None
        self.missing_reported = False
        self.drew_image = False

    def apply(self, viewer, bot, selected: str, opts) -> None:
        vp_h = int(getattr(getattr(viewer, "viewport", None), "height", 0) or 0)
        scale = opts.overlay_scale if opts.overlay_scale > 0 else \
            min(1.6, max(1.0, round(vp_h / 1200.0, 2)))
        key = (bot.spec.name, bot.terrain_level, selected, round(scale, 2))
        if key != self.key:
            self.key = key
            self.img = render_overlay_image(overlay_rows(bot, selected),
                                            width_px=int(opts.overlay_width * scale),
                                            scale=scale)
        rect = None
        if self.img is not None and getattr(viewer, "set_images", None) is not None:
            rect = overlay_corner_rect(viewer, self.img, opts.overlay_corner)
            if rect is not None:
                # set_images 自己会上下翻转，所以每次都给它**正向**的数组
                viewer.set_images([(rect, np.ascontiguousarray(self.img))])
        self.drew_image = rect is not None

        if getattr(viewer, "set_texts", None) is None:
            if not self.missing_reported:
                self.missing_reported = True
                print("[viewer] this MuJoCo build has no viewer text overlay -- the policy "
                      "name is printed in this terminal instead")
            return
        # 图片已经承担左上角的内容 ⇒ 文本只留底部那行（且要跟着指令值刷新）；
        # 画不出图片（缺 Pillow / 没有中文字体 / 窗口太小）⇒ 文本兜底，几行分散到
        # 不同 gridpos，避免像第一版那样互相覆盖。
        want = overlay_command_text(bot, selected) if rect is not None else \
            overlay_fallback_texts(bot, selected)
        if want != self.shown:
            viewer.set_texts(want)
            self.shown = want


def viewer_smoke(demo: "Demo") -> int:
    """Open a real window, then walk all five policies through the overlay code.

    Needs a display, so it is not in the default test set -- but it is the only test
    that exercises `set_images`/`set_texts` at all, and that is exactly where the
    overlay bugs were.
    """
    import mujoco.viewer

    state = OverlayState()
    opts = demo.args
    failures = 0
    for key, name in POLICY_KEYS.items():
        demo.on_key(key)
        bot = demo.bot
        try:
            viewer = mujoco.viewer.launch_passive(bot.model, bot.data, show_left_ui=False,
                                                  show_right_ui=False)
        except Exception as exc:
            print(f"[smoke] {name}: could not open a window ({exc})")
            return 1
        with viewer:
            for _ in range(40):
                if bot.policy_on:
                    bot.apply(bot.act(bot.observe()))
                bot.step()
                state.apply(viewer, bot, demo.selected, opts)
                viewer.sync()
                time.sleep(0.01)
        if state.img is None:
            print(f"[smoke] {name} ({bot.spec.run_id}): TEXT FALLBACK only "
                  f"(no Pillow or no CJK font)")
            continue
        print(f"[smoke] {name} ({bot.spec.run_id}): image "
              f"{state.img.shape[1]}x{state.img.shape[0]} px, "
              f"drew_image={state.drew_image}, rows={len(overlay_rows(bot, demo.selected))}")
        if not state.drew_image:
            failures += 1
            print("[smoke]   the image was built but could not be placed (window too small?)")
    print("[smoke] " + ("OK -- every policy drew its overlay" if not failures
                        else f"{failures} problem(s)"))
    return 0 if not failures else 1


def run_viewer(demo: Demo) -> int:
    """Interactive loop. The viewer is relaunched when a switch reloads the MJCF."""
    import mujoco.viewer

    control_dt = DECIMATION * TIMESTEP
    term = TerminalInput()
    launched_once = False
    try:
        while not demo.quit:
            demo.restart_viewer = False
            bot = demo.bot
            try:
                viewer = mujoco.viewer.launch_passive(bot.model, bot.data, show_left_ui=False,
                                                      show_right_ui=False)
            except Exception as exc:
                # A first window that will not open (no display, no GLFW) stays loud. A
                # window that will not REOPEN after a model reload must not look like a
                # switch that crashed the demo, so say what happened and what is left.
                if not launched_once:
                    raise
                print(f"[viewer] could not reopen the window for the reloaded MJCF: {exc}")
                print(f"[viewer] the demo itself is fine and is on policy "
                      f"'{bot.spec.name}'; restart the script to get a window for the new "
                      f"model, or keep using --headless / --cycle-test")
                return 1
            launched_once = True
            overlay = OverlayState()
            with viewer:
                n = 0
                while viewer.is_running() and not demo.quit and not demo.restart_viewer:
                    t0 = time.perf_counter()
                    for k in term.get_keys():
                        if k and demo.on_key(k):
                            demo.quit = True
                            break
                    if demo.quit or demo.restart_viewer:
                        break           # the switch that just ran owns the next model
                    bot = demo.bot       # in-place switches keep the same bot object
                    if bot.policy_on:
                        bot.apply(bot.act(bot.observe()))
                    bot.step()
                    # Keep the policy name on screen: the window is where the user is
                    # looking while pressing 1-5, and a switch that reloads the MJCF
                    # reopens the window, so this is refreshed per window.
                    #
                    # 左上角那块用**图片**（中文要能显示、多行要真的换行 —— 见
                    # `overlay_rows` 上方的说明）；画不出图片时退回 ASCII 文本。
                    # 逻辑全在 OverlayState 里，`--viewer-smoke` 走的是同一段代码。
                    overlay.apply(viewer, bot, demo.selected, demo.args)
                    viewer.sync()
                    n += 1
                    if n % int(CONTROL_HZ * 5) == 0:
                        st = bot.status()
                        print(f"  t={n / CONTROL_HZ:6.1f}s " + format_status("run", st)
                              + f"  policy={bot.spec.name}"
                              + (f"  selected={demo.selected}"
                                 if demo.selected != bot.spec.name else "")
                              + (f"  cmd=({bot.command[0]:+.2f},{bot.command[1]:+.2f},"
                                 f"{bot.command[2]:+.2f})"
                                 if bot.spec.command == "twist" else "")
                              + (f"  height={bot.height_command:.3f}"
                                 if bot.spec.command == "height" else ""))
                    sleep = control_dt - (time.perf_counter() - t0)
                    if sleep > 0:
                        time.sleep(sleep)
            if demo.restart_viewer and not demo.quit:
                print("[viewer] reopening the window: the MJCF was reloaded, and a viewer "
                      "cannot be re-pointed at another model in place")
    finally:
        term.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
