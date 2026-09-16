#!/usr/bin/env python3
"""Run the trained Wamoduck policies in plain MuJoCo, on CPU.

This is a **Sim2Sim** tool: it loads one of the ONNX policies published in
``policies/`` together with the **training-time MJCF** in
``models/wmduck/mjcf/`` and runs the same observation/action contract the policy
was trained with, at the same 50 Hz control rate. It is not hardware code, and
nothing here has been validated on a physical robot.

Dependencies: ``mujoco``, ``onnxruntime``, ``numpy``. Nothing else -- no mjlab,
no torch, no rsl_rl, no GPU.

Quick start
-----------
    pip install mujoco onnxruntime numpy
    python wamoduck_sim.py --list
    python wamoduck_sim.py --policy stand
    python wamoduck_sim.py --policy getup --spawn lie-back
    python wamoduck_sim.py --policy walk --vx 0.3
    python wamoduck_sim.py --policy stand --check          # contract self-test
    python wamoduck_sim.py --policy stand --headless --steps 250

Controls (type into the terminal that launched the script, not the viewer window)
--------------------------------------------------------------------------------
    up / w      vx += 0.1 m/s          down / s    vx -= 0.1 m/s
    left / a    vy += 0.1 m/s          right / d   vy -= 0.1 m/s
    e           wz += 0.1 rad/s        z           wz -= 0.1 rad/s
    space       zero the twist command
    m           sit / stand toggle (only the ``sitstand`` policy)
    r           reset (re-spawn)
    k           toggle the policy (hold the zero action instead)
    q           reset with a random push
    x           quit

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
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

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
SIT_HEIGHT, TALL_HEIGHT = 0.085, 0.175

OBS_GROUPS = ["base_ang_vel", "projected_gravity", "joint_pos", "joint_vel", "last_action"]


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
    extra_obs: list[str] = field(default_factory=list)

    @property
    def terms(self) -> list[str]:
        return OBS_GROUPS + self.extra_obs


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
    ),
    "getup": PolicySpec(
        name="getup",
        onnx="wamoduck-getup-getup_v18.onnx",
        mjcf="robot_groundcontact.xml",
        obs_dim=48,
        command="none",
        default_spawn="lie-back",
        kind="groundcontact",
        summary="start lying down and get back on its feet",
    ),
    "sitstand": PolicySpec(
        name="sitstand",
        onnx="wamoduck-sitstand-sit_stand_v2.onnx",
        mjcf="robot_walk.xml",
        obs_dim=49,
        command="height",
        default_spawn="nominal",
        kind="walk",
        summary="crouch to a commanded body height and stand back up",
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
        extra_obs=["command"],
    ),
}

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

    def __init__(self, spec: PolicySpec, onnx_path: Path, terrain_level: int = 0) -> None:
        import mujoco
        import onnxruntime as ort

        self.mujoco = mujoco
        self.spec = spec
        self.terrain_level = int(terrain_level)

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
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self.in_name = self.session.get_inputs()[0].name
        self.out_name = self.session.get_outputs()[0].name
        shape = self.session.get_inputs()[0].shape
        dim = shape[-1] if isinstance(shape[-1], int) else None
        if dim is not None and dim != spec.obs_dim:
            raise SystemExit(
                f"{onnx_path.name} expects {dim} observation values but the "
                f"{spec.name!r} contract builds {spec.obs_dim}. Wrong pairing of "
                "policy and task."
            )
        self.onnx_path = onnx_path

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

    # ---- model -----------------------------------------------------------
    def _build_model(self, xml: Path):
        """Compile the training MJCF and add the scene it expects (floor, light).

        The published XML files are the training models with exactly one change:
        ``meshdir`` points at ``../meshes`` so they use the meshes already in this
        repository. The floor, the light and the optional curbs are added here, at
        load time, so the XML files stay byte-comparable with training.
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
        # `--terrain-level N`: N consecutive 1 cm curbs, the same obstacle family
        # the rough task was trained on (STEP_HEIGHT = 1 cm in the cfg). Level 0
        # is a flat floor.
        for i in range(max(0, self.terrain_level)):
            curb = spec.worldbody.add_geom()
            curb.name = f"curb_{i}"
            curb.type = mujoco.mjtGeom.mjGEOM_BOX
            curb.size = [0.15, 1.0, 0.005]
            curb.pos = [0.3 + 0.3 * i, 0.0, 0.005]
            curb.rgba = [0.45, 0.42, 0.38, 1.0]
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

    def max_joint_dev_deg(self) -> float:
        return float(np.degrees(np.abs(self.data.qpos[self.qadr] - self.default_q)).max())

    def feet_down(self) -> tuple[bool, bool]:
        """Which soles are touching the floor (or a curb)."""
        left = right = False
        ground = {self.floor_geom} | {
            self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, f"curb_{i}")
            for i in range(self.terrain_level)
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


def list_policies() -> int:
    print(f"Control rate: {CONTROL_HZ:.0f} Hz  (decimation {DECIMATION} x timestep {TIMESTEP})")
    print(f"{'name':10s} {'obs':>4s} {'MJCF':24s} {'ONNX':38s} present")
    for spec in POLICIES.values():
        p = POLICY_DIR / spec.onnx
        xml = MJCF_DIR / spec.mjcf
        present = "yes" if (p.is_file() and xml.is_file()) else "NO"
        print(f"{spec.name:10s} {spec.obs_dim:4d} {spec.mjcf:24s} {spec.onnx:38s} {present}")
        print(f"{'':10s} {'':4s} {spec.summary}")
    return 0


# ------------------------------------------------------------------- main -----
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the published Wamoduck ONNX policies in plain MuJoCo (CPU).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python wamoduck_sim.py --policy getup --spawn lie-back",
    )
    ap.add_argument("--policy", default="stand", help="one of: " + ", ".join(POLICIES))
    ap.add_argument("--onnx", default=None, help="override the bundled ONNX file")
    ap.add_argument("--spawn", default=None,
                    help="initial pose: " + ", ".join(sorted(SPAWNS)) + ", random")
    ap.add_argument("--seed", type=int, default=0, help="seed for --spawn random")
    ap.add_argument("--terrain-level", type=int, default=0,
                    help="0 = flat floor; N = N consecutive 1 cm curbs")
    ap.add_argument("--vx", type=float, default=None, help="initial forward command (m/s)")
    ap.add_argument("--vy", type=float, default=None, help="initial lateral command (m/s)")
    ap.add_argument("--wz", type=float, default=None, help="initial yaw-rate command (rad/s)")
    ap.add_argument("--target-height", type=float, default=None,
                    help=f"body-height command for --policy sitstand "
                         f"({SIT_HEIGHT} sit .. {TALL_HEIGHT} stand)")
    ap.add_argument("--headless", action="store_true", help="no viewer; run --steps control steps")
    ap.add_argument("--steps", type=int, default=250, help="control steps in --headless mode")
    ap.add_argument("--settle", type=int, default=40, help=argparse.SUPPRESS)
    ap.add_argument("--check", action="store_true", help="run the observation/action contract self-test")
    ap.add_argument("--list", action="store_true", help="list the published policies and exit")
    args = ap.parse_args()

    if args.list:
        return list_policies()
    if args.policy not in POLICIES:
        raise SystemExit(f"unknown --policy {args.policy!r}; choose from {', '.join(POLICIES)}")
    spec = POLICIES[args.policy]

    print(f"Wamoduck Sim2Sim runner -- policy {spec.name!r} ({spec.summary})")
    print("This is a MuJoCo simulation of a trained policy. It is NOT hardware, and "
          "nothing here is a physical-robot result.")

    onnx_path = Path(args.onnx) if args.onnx else POLICY_DIR / spec.onnx
    bot = Wamoduck(spec, onnx_path, terrain_level=args.terrain_level)
    bot.settle_steps = args.settle

    if args.check:
        return bot.self_check()

    rng = np.random.default_rng(args.seed)
    spawn = args.spawn or spec.default_spawn
    bot.reset(spawn=spawn, rng=rng)
    if spec.command == "twist":
        for k, v in (("vx", args.vx), ("vy", args.vy), ("wz", args.wz)):
            if v is not None:
                lo, hi = CMD_LIMITS[k]
                clamped = max(lo, min(hi, float(v)))
                if clamped != v:
                    print(f"[cmd] {k}={v} clamped to {clamped} (trained command range {lo}..{hi})")
                bot.command[{"vx": 0, "vy": 1, "wz": 2}[k]] = clamped
    if spec.command == "height":
        bot.height_command = max(SIT_HEIGHT, min(TALL_HEIGHT, args.target_height or TALL_HEIGHT))

    print(f"[setup] MJCF        : {spec.mjcf} (terrain level {args.terrain_level})")
    print(f"[setup] ONNX        : {onnx_path.name}  in {bot.session.get_inputs()[0].shape} "
          f"out {bot.session.get_outputs()[0].shape}")
    print(f"[setup] spawn       : {spawn}")
    print(f"[setup] control     : {CONTROL_HZ:.0f} Hz  obs {spec.obs_dim}-D  act {N_ACT}-D")
    if spec.command == "twist":
        print(f"[setup] command     : vx={bot.command[0]:+.2f} vy={bot.command[1]:+.2f} "
              f"wz={bot.command[2]:+.2f}")
    if spec.command == "height":
        print(f"[setup] height cmd  : {bot.height_command:.3f} m")
    print("[setup] " + format_status("start", bot.status()))

    if args.headless:
        start_xy = bot.data.qpos[0:2].copy()
        initial_z = bot.base_z()
        lowest_tilt = bot.status()["tilt_deg"]
        ever_standing = bot.status()["standing"]
        for i in range(args.steps):
            obs = bot.observe()
            bot.apply(bot.act(obs))
            bot.step()
            st = bot.status()
            lowest_tilt = min(lowest_tilt, st["tilt_deg"])
            ever_standing = ever_standing or st["standing"]
            if i % max(1, args.steps // 8) == 0:
                print(f"  t={i * DECIMATION * TIMESTEP:5.2f}s " + format_status("run", st))
        st = bot.status()
        moved = bot.data.qpos[0:2] - start_xy
        print(format_status("final", st))
        print(f"[final] simulated {args.steps * DECIMATION * TIMESTEP:.2f} s "
              f"({args.steps} control steps)")
        print(f"[final] base_z {initial_z:.4f} -> {st['base_z']:.4f} m")
        print(f"[final] displacement dx={moved[0]:+.3f} m dy={moved[1]:+.3f} m "
              f"|d|={float(np.linalg.norm(moved)):.3f} m")
        if spec.command == "twist" and abs(bot.command[0]) > 1e-9:
            expected = float(bot.command[0]) * args.steps * DECIMATION * TIMESTEP
            print(f"[final] commanded vx={bot.command[0]:+.2f} m/s -> {expected:+.3f} m "
                  f"in {args.steps * DECIMATION * TIMESTEP:.1f} s")
        print(f"[final] ever stood (tilt<{STAND_TILT_DEG:.0f} deg and base_z>{STAND_Z} m): "
              f"{ever_standing}")
        print(f"[final] lowest tilt seen: {lowest_tilt:.2f} deg")
        print(f"[final] VERDICT: {'standing' if st['standing'] else 'NOT standing'} / "
              f"{'nominal stance' if st['recovered_to_nominal'] else 'not the strict nominal stance'}")
        return 0

    term = TerminalInput()

    def handle(k: str) -> bool:
        """Returns True when the user asked to quit."""
        if k in ("up", "w") and spec.command == "twist":
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
            bot.height_command = SIT_HEIGHT if bot.height_command > (SIT_HEIGHT + TALL_HEIGHT) / 2 else TALL_HEIGHT
        elif k == "r":
            bot.reset(spawn=spawn, rng=rng)
            print("[key] reset")
        elif k == "k":
            bot.policy_on = not bot.policy_on
            print(f"[key] policy {'ON' if bot.policy_on else 'OFF'}")
        elif k == "q":
            ang = rng.uniform(0.0, 2.0 * math.pi)
            bot.data.qvel[0] = 0.3 * math.cos(ang)
            bot.data.qvel[1] = 0.3 * math.sin(ang)
            print("[key] push")
        elif k == "x":
            return True
        return False

    print("[keys] arrows/WASD = vx,vy   E/Z = yaw   space = stop   "
          + ("m = sit/stand   " if spec.command == "height" else "")
          + "r = reset   k = toggle policy   q = push   x = quit")

    control_dt = DECIMATION * TIMESTEP
    import mujoco.viewer

    with mujoco.viewer.launch_passive(bot.model, bot.data, show_left_ui=False,
                                      show_right_ui=False) as viewer:
        n = 0
        while viewer.is_running():
            t0 = time.perf_counter()
            for k in term.get_keys():
                if k and handle(k):
                    term.close()
                    return 0
            if bot.policy_on:
                bot.apply(bot.act(bot.observe()))
            bot.step()
            viewer.sync()
            n += 1
            if n % int(CONTROL_HZ * 5) == 0:
                st = bot.status()
                print(f"  t={n / CONTROL_HZ:6.1f}s " + format_status("run", st)
                      + (f"  cmd=({bot.command[0]:+.2f},{bot.command[1]:+.2f},{bot.command[2]:+.2f})"
                         if spec.command == "twist" else ""))
            sleep = control_dt - (time.perf_counter() - t0)
            if sleep > 0:
                time.sleep(sleep)
    term.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
