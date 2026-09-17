# Run the trained policies in MuJoCo / 在 MuJoCo 里跑训练好的策略

[Home](../README.md) · English | [简体中文](simulation.zh-CN.md) · [Measured capabilities](capabilities.md)

This page is for the five Wamoduck policies published in [`policies/`](../policies/): standing, get-up,
sit/stand, flat-ground walking, and 1 cm rough terrain. Each one ships as an ONNX file, together with the
**training-time MJCF** it was trained on and a single-file runner, so you can run them on your own machine
with plain MuJoCo and no GPU.

**All five run in one demo.** The same viewer switches between them while it runs: walking, sitting down,
standing up, and the rough-terrain policy are all reachable without restarting the script — press `1`-`5`,
or `Tab`/`n` for the next one. The runner prints which policy is loaded, what it observes, and which command
it takes, both at startup and after every switch.

**Scope: simulation only (Sim2Sim).** Everything here runs in MuJoCo on the CPU against the same model the
policy was trained on. There are **no hardware results anywhere in this repository**, nothing here has been
tested on a physical robot, and "it stands in MuJoCo" is not a claim that it stands on hardware.

**Four limits worth knowing before you start.** Walking cannot turn in place, and a sideways command drags
the robot round. `getup` stands up, but it does not settle into the saved nominal pose. `sitstand` buzzes in
place while standing, and the pose it holds when you ask it to sit down is neither upright nor left/right
symmetric. And nothing on this page was measured on hardware. All four are written out in full, with numbers,
under [Known gaps, stated plainly](#known-gaps-stated-plainly).

## Quick start

```bash
pip install mujoco onnxruntime numpy

git clone <this repo>
cd Wamoduck

python wamoduck_sim.py --list                 # what is published
python wamoduck_sim.py                        # one window, all five policies
python wamoduck_sim.py --policy getup --spawn lie-back
python wamoduck_sim.py --policy walk --vx 0.3
python wamoduck_sim.py --policy stand --check # contract self-test, no viewer
python wamoduck_sim.py --cycle-test           # headless switching self-test
```

`--policy` names the policy the demo **starts** on (`stand` by default); keys `1`-`5` switch from there.
`wamoduck_sim.py` imports **only** `mujoco`, `onnxruntime`, and `numpy` — no mjlab, no torch, no rsl_rl,
no CUDA.

Controls are typed into the terminal that launched the script, not into the viewer window:

| Key | Action | Applies to |
| --- | --- | --- |
| `1` `2` `3` `4` `5` | switch policy: `stand` / `getup` / `sitstand` / `walk` / `rough` | every policy |
| `Tab` / `n` | switch to the next policy in that order | every policy |
| `↑` / `w`, `↓` / `s` | `vx` ± 0.1 m/s | `walk`, `rough` |
| `←` / `a`, `→` / `d` | `vy` ± 0.1 m/s | `walk`, `rough` |
| `e` / `z` | `wz` ± 0.1 rad/s | `walk`, `rough` |
| `space` | zero the twist command | `walk`, `rough` |
| `m` | sit / stand toggle (0.11241 m / 0.175 m) | `sitstand` |
| `r` | reset (re-spawn the current policy) | every policy |
| `k` | toggle the policy (hold the zero action instead) | every policy |
| `q` | reset with a random push | every policy |
| `h` / `?` | print the key table again | every policy |
| `x` | quit | every policy |

**The viewer window names the policy too, in plain words and in both languages.** Top-left it draws a panel with
four things: **what the policy does** (`[3/5] 坐下与站起 Sit down and stand up`), the **version handle** that ties
the running file to a checkpoint and a hash (`sitstand = sit_stand_v3 · obs 49-D · 平地 flat`), **the keys that
actually do something for this policy right now**, and **what to try**. Bottom-left the live command values
appear (`cmd vx +0.30 …`), and the two names differ only when a switch was refused — which is exactly when
seeing it matters.

The keys line is derived from the same table as the terminal key list, filtered by the running policy, so a key
that does nothing for it is never advertised. Move or resize the panel with `--overlay-corner {top-left,
top-right,bottom-left,bottom-right}`, `--overlay-width N`, and `--overlay-scale N` (0, the default, scales from
the window height). Print or export it without opening a window:

```bash
python wamoduck_sim.py --overlay-preview                 # the rows, for all five policies
python wamoduck_sim.py --overlay-preview --overlay-png ov.png   # the pixels it would blit
python wamoduck_sim.py --viewer-smoke                    # open a window and draw all five (needs a display)
```

Why the panel is an **image** rather than viewer text: MuJoCo's HUD font is bitmap ASCII, so Chinese comes out
as boxes, and `set_texts` draws entries that share a grid position *on top of each other* rather than wrapping.
The panel is rendered with Pillow using a system CJK font and blitted with `set_images`. That does **not** add a
dependency: the three imports above are still the only ones required, and without Pillow or a CJK font the
overlay falls back to English text placed in separate grid cells.

**No key is ignored in silence.** The twist keys only exist in the observation of `walk` and `rough`, and `m`
only exists for `sitstand`; pressing a key the current policy has no channel for prints what the key would
need and what the policy actually observes, and a key the runner does not bind at all says so too:

```text
[key] 'm' needs a body-height command, but the current policy 'walk' observes vx/vy/wz -- ignored (nothing changed)
```

### What a switch keeps, and what it has to reset

| Switch | MJCF | What happens to the robot |
| --- | --- | --- |
| `stand` ↔ `sitstand` ↔ `walk` ↔ `rough` | unchanged (`robot_walk.xml`) | **State kept.** Only the ONNX actor and the observation assembly (48 / 49 / 51 values) are swapped, so the pose, the velocity, the twist command, and the height command all survive. `last_action` is zeroed — that observation term is the new policy's own memory of its previous output. |
| into or out of `getup` | reloaded (`robot_groundcontact.xml` ↔ `robot_walk.xml`) | **State reset, and the runner says why.** `getup` is the only policy trained with the head chain colliding, so it needs a different physical model; a policy is a function of the model it was trained in, and there is no meaningful way to carry one model's state into another. Entering `getup` re-spawns the robot lying down (`lie-back`), leaving it re-spawns the nominal stance. |
| `walk` ↔ `rough` | unchanged | **State kept.** The 1 cm curbs are compiled into the model and moved: they are placed 0.3 m apart starting 0.3 m ahead of the robot's current `x`, and the unused ones are parked below the floor with their collision switched off. Nothing is reloaded. |

`--spawn` (when given) overrides the spawn of every policy, including the reset that follows a model reload;
by default each policy uses its own: `lie-back` for `getup`, `nominal` for the rest.

Headless self-test runs print the tilt angle, base height, joint deviation, and foot contact at the end:

```bash
python wamoduck_sim.py --policy stand --headless --steps 250   # 5.0 s at 50 Hz
python wamoduck_sim.py --policy getup --spawn lie-back --headless --steps 300   # 6.0 s
python wamoduck_sim.py --policy walk --vx 0.3 --headless --steps 250
```

## The policies

| Name | ONNX (`policies/`) | Source run | Checkpoint | MJCF (`models/wmduck/mjcf/`) | What it does |
| --- | --- | --- | --- | --- | --- |
| `stand` | `wamoduck-stand-stand_v3.onnx` | `2026-09-12_08-32-26_stand_v3` (marked SHIP) | `model_1499.pt` | `robot_walk.xml` | Hold the nominal stance; recover from a push |
| `getup` | `wamoduck-getup-getup_v20.onnx` | `2026-09-16_19-12-01_getup_v20` | `model_3999.pt` | `robot_groundcontact.xml` | Start lying on the ground and get back on its feet |
| `sitstand` | `wamoduck-sitstand-sit_stand_v3.onnx` | `2026-09-16_18-05-44_sit_stand_v3` | `model_2499.pt` | `robot_walk.xml` | Crouch to a commanded body height and stand back up |
| `walk` | `wamoduck-walk-walk_v4r.onnx` | `2026-09-16_12-01-21_walk_v4r` | `model_6749.pt` | `robot_walk.xml` | Walk on flat ground from a twist command |
| `rough` | `wamoduck-rough-rough_v2.onnx` | `2026-09-16_00-00-04_rough_v2` | `model_5999.pt` | `robot_walk.xml` | Walk over 1 cm curbs from a twist command |

The *Source run* and *Checkpoint* columns were resolved with the development repository's
`tools/run_select.py` rather than by picking a file by hand. `stand` is selected by its `SHIP` marker;
`sitstand`, `getup`, `walk`, and `rough` are selected by naming the run explicitly, which is the
highest-priority rule in that tool. Every published ONNX was then verified to be the export of exactly the
checkpoint named in the column by rebuilding the actor from the `.pt` file and comparing it with the ONNX
initializers — now as a tool,
`tools/verify_onnx_provenance.py --onnx <file> --run <run> --expect <checkpoint>`, which reports the exact
match over every `model_*.pt` in the run and exits non-zero otherwise (see
[What was verified](#what-was-verified-on-what-machine-and-what-was-not)).

## Observation and action contract

This is the part that silently breaks everything if it is wrong, so it is written out item by item.

**Control rate: 50 Hz.** One control step is `decimation = 4` physics steps of `timestep = 0.005 s`
(20 ms), the same as training. Both numbers are in the training configs and in the `<option>` element of
the MJCF.

### Observation vector — feed it **raw**

| # | Term | Offset | Size | Unit / definition |
| --- | --- | ---: | ---: | --- |
| 1 | `base_ang_vel` | 0 | 3 | rad/s, base frame — the MJCF `imu_gyro` sensor |
| 2 | `projected_gravity` | 3 | 3 | unit vector; `(0, 0, -1)` when upright; `Rᵀ·(0,0,-1)` |
| 3 | `joint_pos` | 6 | 14 | rad, relative to `default_joint_pos`; that default is **all zeros**, so these are absolute angles |
| 4 | `joint_vel` | 20 | 14 | rad/s, relative to the default joint velocity, which is zero |
| 5 | `last_action` | 34 | 14 | the **previous raw policy output**, before scale and offset |
| 6a | `command` (twist) | 48 | 3 | `vx` m/s, `vy` m/s, `wz` rad/s — `walk`, `rough` |
| 6b | `height_command` | 48 | 1 | target base height in m — `sitstand` |

Total: **48** for `stand` and `getup`, **49** for `sitstand`, **51** for `walk` and `rough`. The ONNX
input shape states the same number, and the runner refuses to pair a policy with the wrong task.

Trained command ranges (`CMD_RANGES` in the training config): `vx` ∈ [-0.4, 0.6], `vy` ∈ [-0.3, 0.3],
`wz` ∈ [-0.8, 0.8]. The runner clamps to these and says so when it does. The sit/stand height command range
is **[0.11241, 0.175] m** — it was [0.085, 0.175] m until 2026-09-16, when 0.085 m was measured to be
**geometrically unreachable** while the trunk stays upright: the torso collision box's lowest corner lies
**109 mm** below the base origin, so the base cannot go lower than 0.109 m without the torso entering the
floor. The old policy only appeared to reach 0.094 m by leaning 25.9° to lift that corner clear.

### Joint order — joint-tree order, and it is not the actuator order

The 14 values of `joint_pos`, the 14 of `joint_vel`, and the 14 action values are all in **joint-tree
order**, which is the order the joints appear in the MJCF and the order the ONNX metadata records:

| Index | Joint name |
| ---: | --- |
| 0 | `left_hip_yaw` |
| 1 | `left_hip_roll` |
| 2 | `left_hip_pitch` |
| 3 | `left_knee` |
| 4 | `left_ankle` |
| 5 | `right_hip_yaw` |
| 6 | `right_hip_roll` |
| 7 | `right_hip_pitch` |
| 8 | `right_knee` |
| 9 | `right_ankle` |
| 10 | `neck_pitch` |
| 11 | `head_pitch` |
| 12 | `head_yaw` |
| 13 | `head_roll` |

That is all 14 actuated joints, left leg first and then right leg, followed by the neck/head chain.

**This is not the order of the `<actuator>` block in the MJCF**, which alternates left/right
(`act_left_hip_yaw`, `act_right_hip_yaw`, `act_left_hip_roll`, …). The two orders differ, and using the
actuator order for the observations or the actions makes the robot collapse within a second. See
[what the ablation showed](#a-wrong-joint-order-makes-the-robot-collapse).

**This reading was adjudicated on 2026-09-16, and it is no longer only an assumption here.** It was
already the reading used on this page and in the runner, but
[`model_contract.py`](../ros2/wamoduck_ros2/wamoduck_ros2/model_contract.py) in the ROS 2 module read
the same 14 values in **actuator** order, so the repository contradicted itself for `action[1]` to
`action[8]`. The ROS 2 side was corrected. Two pieces of evidence pin the order **directly**, on top of
the behaviour ablation below:

- every published policy's ONNX metadata records `joint_names` in tree order;
- a **one-hot probe** — drive one action channel at a time through
  `q_target = default_joint_pos + action_scale × action` in MuJoCo and read which joint actually moves —
  returns the identity permutation: channel `i` moves tree joint `i` and nothing else, so each row and
  each column of the 14×14 response matrix has exactly one dominant entry, with a dominance of at least
  **140×**. The actuator-order reading moves a *different* joint for `action[1]` to `action[8]`, so the
  two readings are physically distinguishable rather than a matter of interpretation.

In the runner this is one line: `ctrl_ids = [0, 2, 4, 6, 8, 1, 3, 5, 7, 9, 10, 11, 12, 13]`, so action
element `i` is written to the actuator that drives tree joint `i`.

### Action → joint target

```
q_target[j] = default_joint_pos[j] + action_scale * action[j]      with action_scale = 1.0
```

- `default_joint_pos` is **14 zeros** (the ONNX metadata and the `stand` keyframe agree), so
  `q_target = action` for every joint.
- **No clipping is applied to the action.** The training runner config leaves `clip_actions = None`, and
  the action config sets no `clip` either. Each action value is used as-is.
- MuJoCo then clamps `ctrl` to each actuator's `ctrlrange` (every actuator in the model is
  `ctrllimited = true` via `autolimits="true"`), which is where the joint limits take effect.
- The servo is a soft position servo: `kp = 5.0`, `kv = 0.5`, `forcerange = ±1.5 N·m` on all 14 joints.
  These are simulation values, not hardware ratings.

### The ONNX already contains the observation normalizer

**Feed the ONNX raw observations. Do not normalize them yourself, and do not subtract a mean.**

All five published ONNX graphs begin with the normalizer: two nodes, `Sub` then `Div`, with initializers
`obs_normalizer._mean` and a divisor, followed by the three `Gemm` + `Elu` actor layers
(512 → 256 → 128 → 14). The export is the actor **with** its `EmpiricalNormalization` module, because the
actor config sets `obs_normalization = True`.

Concretely, the graph computes `(obs - mean) / (std + eps)` with `eps = 0.01` and then the MLP — so a
client that normalizes again is applying the normalization twice, which is the classic
"it runs but behaves nothing like training" failure. The divisor in the graph was verified to equal
`std + 0.01` element by element against the checkpoint's own `obs_normalizer._std`.

The five graphs, for the record:

| Policy | ONNX input | ONNX output | Normalizer in graph |
| --- | --- | --- | --- |
| `stand` | `obs` `[1, 48]` | `actions` `[1, 14]` | yes (`Sub`, `Div` + `obs_normalizer._mean`) |
| `getup` | `obs` `[1, 48]` | `actions` `[1, 14]` | yes |
| `sitstand` | `obs` `[1, 49]` | `actions` `[1, 14]` | yes |
| `walk` | `obs` `[1, 51]` | `actions` `[1, 14]` | yes |
| `rough` | `obs` `[1, 51]` | `actions` `[1, 14]` | yes |

## Why you must use the bundled MJCF, not the URDF

The [URDF in `models/wmduck/`](../models/wmduck/) and the [MJCF in `models/wmduck/mjcf/`](..) describe the
same robot, but only one of them is the model the policies were trained in. Use the MJCF.

- **The URDF has no actuators, no sensors, and no contact model.** It declares 15 revolute joints and 17
  links for inspection and exchange, with `effort` set to the rated 0.6 N·m and no actuator elements at
  all. A policy needs all three: the 14 position servos with their `kp`/`kv`/`forcerange`, the `imu_gyro`
  sensor the observations read, and the collision geometry the robot balances on.
- **The joint count is not the same.** The URDF's 15 joints include a `mouth` joint that is not actuated
  in the control model; the policy drives **14** joints, and its observations are 14-wide.
- **The training MJCF carries measured-mass updates.** The MJCF masses are the ones the policies were
  trained with; the published URDF carries motor-mass overrides that have not been reconciled with it.
  Inertias, contact geometry, and the collision variant all differ. A policy is a function of the model it
  was trained in, so a different model is a different task.

The two MJCF files published here are the training files verbatim, with **one attribute changed**:
`meshdir="."` became `meshdir=".."` so that the models load the 20 meshes that are already in this
repository at [`models/wmduck/meshes/`](../models/wmduck/meshes/) instead of a private copy. Nothing else differs — not
the inertias, the joints, the actuators, the sensors, the contact parameters, or the `<option>` block. The
20 mesh files are **byte-identical** to the training ones (all 20 SHA-256 values match).

The floor, the light, and the optional 1 cm curbs are added at load time by the runner, so the XML files
stay exactly as they were trained.

## What was verified, on what machine, and what was not

The three required checks were run on **CPU only** (no GPU) with plain MuJoCo 3.10, ONNX Runtime 1.30, and
NumPy 2.5, driving the published ONNX files through the published `wamoduck_sim.py` code path.

### 1. `stand` — 5 s from the nominal stance, does not fall

```
python wamoduck_sim.py --policy stand --headless --steps 250
```

```
[final] tilt=  0.54 deg  base_z=0.1770 m  max_joint_dev=  1.88 deg  both_soles=True  standing=True  nominal=True
[final] simulated 5.00 s (250 control steps)
[final] base_z 0.1776 -> 0.1770 m
[final] displacement dx=+0.001 m dy=-0.000 m |d|=0.001 m
```

Final tilt **0.54°**, base height **0.1770 m** (started at 0.1776), both soles on the ground, largest joint
deviation **1.88°**, and 1 mm of total drift over 5 s. This passes even the **strict** criterion used on the
[measured capability board](capabilities.md) (tilt < 8°, both soles, every joint within 20° of nominal,
base height > 0.15 m).

### 2. `getup` — 6 s from a lying start, stands up

```
python wamoduck_sim.py --policy getup --spawn lie-back --headless --steps 300
```

```
[start] tilt= 69.81 deg  base_z=0.0920 m  max_joint_dev=  9.34 deg  both_soles=True  standing=False  nominal=False
[final] tilt=  2.23 deg  base_z=0.1763 m  max_joint_dev= 11.01 deg  both_soles=True  standing=True  nominal=True
[final] base_z 0.0920 -> 0.1763 m
[final] lowest tilt seen: 0.90 deg
```

It gets up: from a lying start at 69.8° of tilt and 0.092 m it ends upright at **2.23°** and **0.1763 m**, with
both soles down, having passed through 0.90°, and a largest joint deviation of **11.01°** — so this run reaches
the **strict** nominal criterion, not just the loose one. That matches the internal
[capability board](capabilities.md), which now records **63/64 (98.4 %)** on that criterion for `getup_v20`.

**The same command run against the previous policy, for comparison**, is the measurement that found the gap
that was fixed on 2026-09-16:

```
python wamoduck_sim.py --policy getup --onnx policies/wamoduck-getup-getup_v18.onnx \
                       --spawn lie-back --headless --steps 300
# [final] tilt=  8.24 deg  base_z=0.1784 m  max_joint_dev= 52.08 deg  both_soles=True  standing=True  nominal=False
```

That one reached the **loose** "standing" criterion but **not** the strict nominal one, because the final joint
deviation was 52°. It is kept here rather than deleted, and `getup_v18` is still published so it can be
reproduced.

All five published lying spawns were tested for 6 s each: `lie-back`, `lie-front`, `lie-side`,
`lie-side-r`, and `inverted` all end standing.

### 3. `walk` — 5 s at vx = 0.3 m/s, moves forward

```
python wamoduck_sim.py --policy walk --vx 0.3 --headless --steps 250
```

```
[final] tilt=  4.92 deg  base_z=0.1864 m  max_joint_dev= 23.11 deg  both_soles=False  standing=True  nominal=False
[final] base_z 0.1776 -> 0.1864 m
[final] displacement dx=+1.482 m dy=-0.328 m |d|=1.518 m
[final] commanded vx=+0.30 m/s -> +1.500 m in 5.0 s
```

It covers **1.482 m** of the commanded 1.500 m, i.e. **99 %** of the commanded speed, with the tilt staying
below 5° the whole time and never falling. This is a pure CPU MuJoCo number and is **not** comparable with
the internal GPU measurements on the [capability board](capabilities.md), which use a different simulator
(MuJoCo Warp) and a different protocol.

### Also checked

```
python wamoduck_sim.py --policy sitstand --target-height 0.11241 --headless --steps 250
python wamoduck_sim.py --policy rough --terrain-level 3 --vx 0.3 --headless --steps 250
```

- `sitstand`: commanded **0.11241 m**, **held 0.1096 m** (2.9 mm low), both soles down, tilt **0.12°**, and
  the left and right legs agree. This is the replacement policy; the numbers the previous one produced on the
  old 0.085 m command are kept below as the baseline.
- `rough`: over 3 consecutive 1 cm curbs at vx = 0.3, it travelled **1.384 m** in 5 s and stayed standing
  (tilt 5.3°). The `--terrain-level N` option adds N curbs spaced 0.3 m apart, starting 0.3 m ahead.
  Since the demo gained policy switching, `rough` gets those 3 curbs **by default** and `walk` stays on the
  flat floor, so that switching between the two changes the terrain as well as the policy. `--terrain-level N`
  still overrides both, and then every policy runs on N curbs.

#### `sitstand` at length: the two issues a user reported

> **Both were fixed on 2026-09-16** by the replacement policy `sit_stand_v3`, which the runner now loads. The
> measurements below were taken on `sit_stand_v2` and are kept as the baseline they were judged against; the
> before/after pairs are jitter **0.699 → 0.000**, drift **+27.99 → +0.394 mm/s**, sitting tilt
> **10.05° → 0.225°** and left/right residual **146.09° → 0.473°**. Note too that the old **0.085 m** command
> is **geometrically unreachable** with an upright trunk (the torso box's lowest corner is 109 mm below the
> base origin), which is why the commanded seat is now **0.11241 m**.

A user playing the published demo reported that `sitstand` **buzzes in place while standing**, and that
sitting down does not give the pose the report described as "head and torso vertical to the ground, left and
right legs braced symmetrically". Both were measured afterwards with this same runner — CPU only, MuJoCo
**3.10.0**, ONNX Runtime **1.30.0**, NumPy **2.5.3**, 500 control steps (**10.0 s**), spawn `nominal`, flat
floor — by running the two commands beside the `stand` policy. To reproduce them, point the runner at the
previous policy explicitly, since the default is now the replacement:

```bash
# the baseline (sit_stand_v2), i.e. the measurement quoted below:
python wamoduck_sim.py --policy sitstand --onnx policies/wamoduck-sitstand-sit_stand_v2.onnx \
                       --target-height 0.175 --headless --steps 500
python wamoduck_sim.py --policy sitstand --onnx policies/wamoduck-sitstand-sit_stand_v2.onnx \
                       --target-height 0.085 --headless --steps 500
python wamoduck_sim.py --policy stand --headless --steps 500

# the current policy (sit_stand_v3), same protocol:
python wamoduck_sim.py --policy sitstand --target-height 0.175 --headless --steps 500
python wamoduck_sim.py --policy sitstand --target-height 0.11241 --headless --steps 500
```

The baseline run reproduces the two figures already on this page — **0.094 m** held against a 0.085 m command,
and a **~26°** lean — and adds two that were not recorded before.

- **At the standing command (0.175 m) the robot buzzes in place.** It is upright (final tilt **0.44°**, base
  height **0.1762 m**) and it never settles: action jitter, `mean abs(delta a)` per control step, is **0.229**
  over the whole 10 s, **0.235** after the first 1.0 s and **0.236** in the last 1.0 s, with a maximum single
  step of **1.313**. The `stand` policy, on the same metric and the same run length, gives **9.9e-5**,
  **2.9e-7** and **4.1e-8** on those same three windows — roughly six orders of magnitude quieter. Tilt std is **0.403°**
  (**0.396°** in the last 1.0 s, so it is a sustained limit cycle, not a settling transient), base-height std
  is **1.10 mm**, and mean absolute joint velocity is **1.69 rad/s** with a peak of **10.11 rad/s**. Both soles
  are down in only **92.2 %** of the steps after the first 1.0 s, the feet carry **45.46 N** on average against
  a **36.80 N** weight, and "in place" is approximate: it also travels **0.263 m** in the 10 s.
- **At the sitting command (0.085 m) the pose is neither upright nor symmetric.** Unlike the standing command,
  this one is **quiet** — it reaches a static pose inside about 1.0 s (`mean abs(delta a)` **4.4e-7** in the last
  1.0 s), so the buzz is a standing-height problem only. But the pose it settles into is a **25.89°** lean
  (roll **−15.99°**, pitch **+20.64°**), measured **0.0943 m** instead of 0.085 m (**+9.3 mm**), with the
  **head** — `head_roll_link` — **25.62°** off vertical and the neck **25.44°** off, because the head chain's own
  joints are all within **0.6°** of zero and simply inherit the trunk's lean. It rests on its **pelvis**:
  `base_link_body_collision` is in contact with the floor in **100 %** of the last 1.0 s, carrying **7.16 N**
  of the **36.83 N** total. And the two legs are not mirrors of each other — on `hip_pitch`, `hip_yaw` and
  `ankle` the left and right values sit on **opposite sides of zero** (left hip **+128.29°** against a right hip
  of **−45.26°**, left ankle **−93.97°** against **+48.36°**), while `hip_roll` and `knee` agree to within
  **0.6°**. `stand` keeps every one of those five pairs within **0.6°**, so the sign convention is being applied
  correctly and a symmetric pose is reachable in this model.

The full tables — the per-run jitter comparison, all 14 joint angles, the left/right residuals with the
mirror-sign convention stated, the contact census, and the user's expectation written as three testable
statements — are on the [measured capability page](capabilities.md#the-two-known-sitstand-issues-as-measured).
That page states the sign convention in full: the MJCF mirrors the ranges of the two `hip_yaw` and `hip_roll`
joints, and a probe confirms a positive `hip_roll` is outward on the left leg and inward on the right, so a
mirrored pose has those two pairs at **opposite signs** while `hip_pitch`, `knee` and `ankle` should be equal.
This repository **defines no target sitting pose**, so nothing here says what the sit pose should look like
beyond restating the user's expectation.

### The demo switching all five policies: `--cycle-test`

```
python wamoduck_sim.py --cycle-test
```

`--cycle-test` is the headless version of what a user does in the viewer: it presses `1`, `2`, `3`, `4`, `5`
through the same key handler the keyboard uses, so the state-keeping path and the model-reload path are both
exercised, and it checks each segment. 300 control steps (6.0 s) per policy, `vx = +0.30 m/s` on the two
walking policies, and `m` in the middle of the sit/stand segment:

| Segment | Switch into it | End tilt | End `base_z` | Travel | Heading change |
| --- | --- | ---: | ---: | ---: | ---: |
| `1 stand` | in place (same MJCF, from the starting policy) | 0.54° | 0.1770 m | 0.001 m | +1.0° |
| `2 getup` | **reload** (`robot_groundcontact.xml`, spawn `lie-back`) | 8.14° | 0.1782 m (from 0.0920) | 0.071 m | +33.8° |
| `3 sitstand` | **reload** back to `robot_walk.xml`, spawn `nominal` | 25.74° | 0.0945 m after `m` (from 0.1748) | 0.038 m | +26.2° |
| `4 walk` | in place (state kept from the crouch) | 4.49° | 0.1841 m | 1.730 m of 1.800 m commanded | **−112.2°** |
| `5 rough` | in place, curbs moved in front of the robot | 3.28° | 0.1904 m | 1.774 m of 1.800 m commanded | −64.4° |
| `6 walk` (forward check) | `4` then `r`: fresh nominal spawn, 5.0 s | 6.14° | 0.1770 m → 0.1864 m | dx **+1.482 m**, dy −0.328 m | −19.6° |

All seven checks pass, and the two that matter most for the demo are visible above: the model reload really
does reset the robot (`getup` starts lying at 0.0920 m and ends at 0.1782 m), and the in-place switches really
do keep it (`walk` starts its segment from the **0.1719 m** standing pose the sit/stand segment left behind).

**Read segment 4 with its heading column.** Because the sitstand → walk switch keeps the state by design, the
walk policy picks the robot up in whatever pose the sit/stand segment left, and it spends that segment
recovering: it turns **9.2°** before it settles into walking. That is the uncommanded-rotation weakness this
walking checkpoint is already documented with; the assertion is about travel, not about a heading. Segment 6
is the control for it — after all five switches (two of them MJCF reloads) the demo is pressed back to
`walk`, re-spawned with `r`, and it reproduces the single-policy run **exactly**:
`dx = +1.470 m, dy = −0.416 m` in 5.0 s.

**The seated → walking hand-over is a measured limitation, and the self-test now steps around it.** With the
sit/stand policy replaced by `sit_stand_v3` on 2026-09-16, switching to `walk` **while still seated**
collapses the robot — an earlier revision of the self-test did exactly that and measured tilt **134.9°** after
6 s with only **0.438 m** of travel, because the walking policy was trained from a nominal stance and has
never seen a seated one. The self-test therefore presses `m` to stand back up before the walk segment (and
asserts that stand-up itself: 0.1096 m → 0.1719 m, tilt 1.31°), which is what a user does anyway.

These numbers were measured on **MuJoCo 3.12.0, ONNX Runtime 1.28.0, NumPy 2.4.6**, the versions on our
machine when the switching test was added; the runs in the three sections above were measured on
MuJoCo 3.10, ONNX Runtime 1.30, NumPy 2.5, which is why a contact-rich number such as `getup`'s final height
differs in the last two digits. Both sets are CPU-only MuJoCo.

### `--check`: the contract self-test

`python wamoduck_sim.py --policy <name> --check` re-derives the wiring against MuJoCo itself rather than
trusting the code, and all five policies pass:

- `projected_gravity` equals `-R[2,:]` of MuJoCo's own base rotation matrix (checked at a rotated pose);
- the `imu` site frame equals the base frame, and `imu_gyro` equals the free joint's angular velocity, which
  MuJoCo keeps in the body-local frame (also checked at a rotated pose — an upright base would make this
  pass trivially and hide a wrong convention);
- the nominal pose `q = 0` is inside every joint range;
- every actuator is `ctrllimited`, and `kp = 5.0` / `kv = 0.5` for all 14;
- the ONNX graph contains the normalizer, so raw observations are required;
- the assembled observation and action vectors have the right dimensions and are finite.

### A wrong joint order makes the robot collapse

Because the action order is the single easiest thing to get wrong here, it was measured rather than assumed.
Four wirings were tried for each policy and each was run for 5 s (6 s for `getup`):

| Policy | Observation order | Action order | Result |
| --- | --- | --- | --- |
| `stand` | tree | **tree** | tilt **0.54°**, base_z 0.1770 — standing |
| `stand` | tree | actuator | tilt 135.5°, base_z 0.035 — collapsed |
| `stand` | actuator | tree | tilt 135.3° — collapsed |
| `stand` | actuator | actuator | tilt 134.0° — collapsed |
| `walk` | tree | **tree** | travelled **+1.482 m** at vx = 0.3 (commanded 1.500 m) |
| `walk` | tree | actuator | collapsed (tilt 135.3°) |
| `walk` | actuator | tree | collapsed |
| `walk` | actuator | actuator | collapsed |
| `sitstand` | tree | **tree** | crouched to 0.094 m, both soles, held |
| `sitstand` | any other of the three | | collapsed (tilt ≈ 135°) |
| `getup` | tree | **tree** | **5/5** lying spawns end standing, mean final tilt 8.2° |
| `getup` | tree | actuator | 1/5 end standing, mean final tilt 47.0° |
| `getup` | actuator | tree | 0/5 |
| `getup` | actuator | actuator | 0/5 |

Only "tree order for the observations **and** tree order for the actions" works, and it is the only wiring
that works for every policy. `getup` is the least sensitive of the five — from one lying pose it stands up
even with the wrong action order — but across all five spawns that advantage disappears
(1/5 versus 5/5).

## Known gaps, stated plainly

- **Walking is the weakest of the five, and it was retrained for this release.** `walk_v4r` is the newest
  walking run; it ran past the 6000 iterations this release first assumed was its end and stopped at
  **6749**, and the ONNX published here is the export of that run's **final checkpoint `model_6749.pt`**.
  (An earlier revision of this file was the export of `model_6000.pt`, copied while the run was still
  training; see the [changelog](../CHANGELOG.md).) The earlier internal measurement of walking reports two
  specific failures that this release does **not** fix: **in-place turning** — a 0.5 rad/s yaw command
  produced **+0.3°** of rotation in 10 s, and it has since been measured to be **out of reach for this
  mechanism** rather than undertrained (see [Why in-place turning cannot be trained
  away](capabilities.md#why-in-place-turning-cannot-be-trained-away)) — and **side-stepping is accompanied
  by large uncommanded rotation**, with a +0.30 m/s lateral command producing +0.218 m/s sideways *and*
  **+520.4°** of uncommanded yaw. Our own CPU run shows the same symptom in miniature: the 5 s forward run
  drifted **0.328 m** sideways while commanded to go straight. Treat forward walking and turning *while
  moving* as usable, and in-place turning and side-stepping as not.
- **The walking ONNX is not the checkpoint the capability board measured.** That board's walking row refers
  to `walk_r3`, which was trained under an older command range. `walk_v4r` has no private measurement, so
  this page quotes only our own CPU Sim2Sim displacement for it and claims nothing else.
- **`getup` used to not reach the strict nominal pose — fixed on 2026-09-16.** With the previous policy
  (`getup_v18`, still published) the final joint deviation was **52°** and the strict criterion was **0/64**;
  the replacement `getup_v20` measures **63/64** on that criterion with **10.4°** of joint deviation, and
  **5/5** on the end-to-end hand-over. This page's own CPU run reproduces it: **11.01°**, `nominal=True`.
  The stricter six-axis criterion is **45/64**, up from **0/64**.
- **`sitstand` used to hold 0.094 m when asked for 0.085 m and lean ~26° while crouched; both were fixed on
  2026-09-16.** Two issues were reported by a user in this demo and measured here, and the replacement policy
  `sit_stand_v3` fixes both (jitter **0.699 → 0.000**, drift **+27.99 → +0.394 mm/s**, sitting tilt
  **10.05° → 0.225°**, left/right residual **146.09° → 0.473°**). What follows is the **baseline**, measured on
  `sit_stand_v2`, which is still published so the numbers stay reproducible:
  - **It buzzed in place at the standing command.** At `--target-height 0.175`, action jitter
    (`mean abs(delta a)` per control step) was **0.235** after the first 1.0 s — the `stand` policy gives
    **2.9e-7** on the same metric — tilt std **0.403°**, mean absolute joint velocity **1.69 rad/s**, both
    soles down in only **92.2 %** of the steps, and the feet carrying **45.46 N** on average against a
    **36.80 N** weight. It did not decay: the last 1.0 s was as restless as the average.
  - **The sitting posture was neither upright nor left/right symmetric.** At `--target-height 0.085` it was
    quiet but wrong: base tilt **25.89°** with the head **25.62°** off vertical, base height **0.0943 m**
    against the commanded 0.085 m, `base_link_body_collision` (the pelvis) on the floor for **100 %** of the
    last 1.0 s carrying **19.4 %** of the weight, and on three of the five leg-joint pairs the left and right
    values sat on **opposite sides of zero** (residuals of **119°** to **174°**), where `stand` keeps every
    pair inside **0.6°**.
  - **And one limitation arrived with the fix**: the seated pose is not a stance the walking policy can start
    from — switching to `walk` while seated collapses it (tilt **134.9°** after 6 s).

  Numbers, commands, the mirror-sign convention and the user's expectation written as three testable statements
  are under [`sitstand` at length](#sitstand-at-length-the-two-issues-a-user-reported) and on the
  [measured capability page](capabilities.md#the-two-known-sitstand-issues-as-measured).
- **The policies were measured in one simulator, on one machine, on one day.** None of the internal
  measurement protocols are published, so nothing here can re-derive the internal rates.
- **`rough` was checked with 3 hand-placed curbs, not the training terrain generator.** The internal
  terrain generator is not published, so this is an approximation of the obstacle family, not a
  reproduction of the training terrain.

## Files

```text
Wamoduck/
├── wamoduck_sim.py                  # the runner: one demo, all five policies
│                                    #   (mujoco + onnxruntime + numpy only)
├── policies/
│   ├── wamoduck-stand-stand_v3.onnx
│   ├── wamoduck-getup-getup_v20.onnx         # current get-up policy
│   ├── wamoduck-getup-getup_v18.onnx         # kept: the baseline the get-up gap was measured on
│   ├── wamoduck-sitstand-sit_stand_v3.onnx   # current sit/stand policy
│   ├── wamoduck-sitstand-sit_stand_v2.onnx   # kept: the baseline the two measurements above were taken on
│   ├── wamoduck-walk-walk_v4r.onnx
│   ├── wamoduck-rough-rough_v2.onnx
│   └── README.md                    # hashes and provenance
└── models/wmduck/
    ├── mjcf/
    │   ├── robot_walk.xml           # stand, sitstand, walk, rough
    │   ├── robot_groundcontact.xml  # getup (33 collision geoms, so it can lie down)
    │   └── README.md
    └── meshes/                      # the 20 STLs the MJCF files load
```

## What this page does not claim

- **No hardware results.** Every number on this page is simulated. The repository contains no
  physical-robot measurement of any policy.
- **No training code.** The training configuration, the checkpoints, the scene generator, and the
  measurement tools are not published. What is published is enough to *run* the policies, not to reproduce
  the training or the internal measurements.
- **No claim that the ONNX files are deployment-ready for hardware.** They are what the training produced.
  Motor calibration, encoder signs and zeroes, CAN IDs, timing, and safety limits are a separate problem
  that this repository does not solve.

## See also

- [Measured capabilities](capabilities.md) / [实测能力清单](capabilities.zh-CN.md) — what the policies were
  measured at, by the internal tools, and which parts do not work.
- [Model guide](model.en.md) / [模型指南](model.zh-CN.md) — the URDF, its 15 joints, and its assumptions.
- [Roadmap](roadmap.md) — what is still missing from the public repository.
