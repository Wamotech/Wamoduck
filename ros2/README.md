# Wamoduck on ROS 2 (Jazzy)

A ROS 2 chain for the Wamoduck (`wmduck`) 15-DoF biped, aimed at people who are **not**
fluent in MuJoCo: install, build, launch, and see the robot move — without touching the
physics stack.

**Scope of this directory: the first two stages only.**

| Stage | Contents | State |
| --- | --- | --- |
| **1. Description + nodes** | `wamoduck_msgs`, `wamoduck_description`, `wamoduck_ros2` | done, built and verified (see [Verification status](#verification-status)) |
| **2. RViz visualisation** | `display.launch.py`, `gait_display.launch.py`, two `.rviz` configs | done, screenshot evidence in [`verification/`](verification/) |
| 3. Gazebo | `ros-jazzy-ros-gz`, physics, controllers | **not started — nothing here runs Gazebo** |
| 4. MoveIt | motion planning | **not started** |

Nothing in this directory claims Gazebo or MoveIt works. Nothing here claims anything about
real hardware, and `ros-jazzy-ros-gz` is deliberately not a dependency.

> **Stage 2 has no physics.** RViz integrates nothing, collides nothing and applies no
> gravity. A gait that looks plausible on screen has proven that the description loads, that
> the joint frames are where the URDF says they are, and that a `JointState` stream is well
> formed. It has proven nothing about dynamics or balance. MuJoCo remains the physics
> reference for this project.

---

## Packages

```
ros2/
├── wamoduck_msgs/          interface package (ament_cmake)
│   └── msg/JointTarget.msg       ROS-side image of the 46 B CMD frame payload
│   └── msg/LinkStatus.msg        link counters + cerebellum status word
├── wamoduck_description/   URDF + meshes + RViz (ament_cmake)
│   ├── scripts/generate_ros_urdf.py   rewrites mesh paths at build time
│   ├── urdf/README.md                 why no URDF is checked in here
│   ├── launch/display.launch.py       robot_state_publisher + joint_state_publisher + RViz
│   └── rviz/wamoduck.rviz, wamoduck_world.rviz
├── wamoduck_ros2/          nodes (ament_python)
│   ├── wamoduck_ros2/frame_codec.py       byte protocol, ROS-free, fully unit-tested
│   ├── wamoduck_ros2/model_contract.py    frozen policy contract + URDF joint reader
│   ├── wamoduck_ros2/gait_csv.py          reader for tools/matlab/data/gait_*.csv
│   ├── wamoduck_ros2/policy_interface.py  observation assembly, action permutation
│   ├── wamoduck_ros2/policy_runner.py     ONNX boundary (skeleton, never executed)
│   ├── wamoduck_ros2/gait_player.py       CSV -> sensor_msgs/JointState
│   ├── wamoduck_ros2/policy_node.py       50 Hz policy loop (skeleton)
│   ├── wamoduck_ros2/bridge_stub.py       byte transport <-> topics (skeleton + codec)
│   └── launch/gait_display.launch.py      gait_player + RViz, one command
├── tools/verify_description.py   independent geometric verification of the description
└── verification/                 evidence produced by the runs described below
```

The node split follows `docs/16_真机部署方案.md` §6.5: **ROS lives only on the Linux side**
(no micro-ROS on the AT32, whose 96+12 KB SRAM cannot comfortably hold a DDS session), the
wire protocol is the deterministic 46-byte frame format, and the bridge is the only
component that parses bytes. Plain `rclpy`, no real-time kernel. Name mapping:

| `docs/16` §6.5 | this package |
| --- | --- |
| `wmduck_bridge` | `bridge_stub` |
| `wmduck_policy` | `policy_node` |
| `wmduck_safety` | **not written** (a later stage) |
| `wmduck_msgs/JointTarget` | `wamoduck_msgs/JointTarget` |

### Assets are never stored twice

`models/wmduck/` stays the single source of truth. This directory contains **no meshes and no
URDF**, and `tools/matlab/data/` stays the single source of truth for the gait CSVs.

* `wamoduck_description` rewrites the canonical URDF's mesh references from the
  file-relative `meshes/Head.stl` to `package://wamoduck_description/meshes/Head.stl` at
  build time, and installs the meshes straight out of `models/wmduck/meshes`.
* `wamoduck_ros2` installs `tools/matlab/data/gait_*.csv` into `share/wamoduck_ros2/data`.

Both are build-time copies, so the ~11 MB of STL exists exactly once inside Git. See
[`wamoduck_description/urdf/README.md`](wamoduck_description/urdf/README.md) for why
symlinks were rejected.

The rewrite is not cosmetic. `robot_state_publisher` + RViz resolve meshes through
`resource_retriever`, which understands `package://`, `file://` and paths relative to the
**current working directory** — never a URDF-relative path. Launch RViz from anywhere else
and the robot silently renders empty. `tools/verify_description.py` measures exactly this: run
against the canonical URDF it reports all 79 references as working-directory dependent, and
against the generated URDF it reports zero.

---

## Install

ROS 2 **Jazzy** (Ubuntu 24.04's matching distribution). Do not use Humble: that is the 22.04
release.

### Option A — everything, including RViz (a workstation)

```bash
sudo apt update
sudo apt install ros-jazzy-desktop
```

`ros-jazzy-desktop` is the simple choice and is what the verification below used
(`0.11.0-1noble`, RViz 14.1.23). It is roughly 1–2 GB.

### Option B — minimal (the RDK X5, or a machine with no display)

```bash
sudo apt install ros-jazzy-ros-base \
                 ros-jazzy-robot-state-publisher \
                 ros-jazzy-joint-state-publisher
# only if you want RViz on that machine too:
sudo apt install ros-jazzy-rviz2
```

`ros-jazzy-ros-base` is enough for the nodes. `wamoduck_description` needs
`robot_state_publisher` only if something consumes its TF; RViz needs the `rviz2` package plus
the `rviz_default_plugins` that come with it.

### Build and test tooling

```bash
sudo apt install python3-colcon-common-extensions python3-pytest
# optional, used by the verification notes in this directory:
sudo apt install liburdfdom-tools ros-jazzy-tf2-tools
```

`liburdfdom-tools` provides the standalone `/usr/bin/check_urdf`. The `check_urdf` on your
`PATH` after sourcing ROS 2 is the one from `ros-jazzy-urdf`; both work.

---

## Build

The packages live in a plain `ros2/` directory, not in a workspace `src/`. Two ways to build:

### Symlink the packages into a workspace (recommended)

Keeps one source of truth and avoids building on `/mnt/e` or any other slow/shared filesystem:

```bash
mkdir -p ~/ws_wamoduck/src
cd ~/ws_wamoduck
for p in wamoduck_msgs wamoduck_description wamoduck_ros2; do
  ln -sfn /path/to/Wamoduck/ros2/$p src/$p
done

source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

`wamoduck_description/CMakeLists.txt` resolves symlinks before walking up to `models/wmduck`,
so this layout works with the same default it uses in-place.

### Build in place

```bash
cd /path/to/Wamoduck/ros2
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

### If only `ros2/` was copied to this machine

`wamoduck_description` deliberately carries no URDF, so it needs the model directory. Either
copy `models/wmduck/` alongside, or point the build at it:

```bash
colcon build --packages-select wamoduck_description \
  --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
```

The build fails loudly, with that instruction, if `wmduck.urdf` or the mesh directory is
missing — rather than installing a description that renders an empty robot.

### Expected build result

```
Starting >>> wamoduck_description
Starting >>> wamoduck_msgs
Starting >>> wamoduck_ros2
...
Summary: 3 packages finished [21.6s]
```

If `colcon list` shows `wamoduck_ros2 (python)` instead of `(ros.ament_python)`, **stop**:
that means `package.xml` is not being parsed as a ROS manifest and no ROS environment is
generated for the package, so `ros2 launch` will never find it. The usual cause is an
unescaped `<` in an XML text field. `wamoduck_ros2/test/test_package_manifests.py` exists to
catch that, because `colcon build` succeeds either way.

---

## Run

### 1. Just look at the robot

```bash
ros2 launch wamoduck_description display.launch.py
```

`robot_state_publisher` + `joint_state_publisher` + RViz. All movable joints sit at 0, which
is the CAD standing pose, because the contract's `default_joint_pos` is all zeros.

Useful arguments:

| Argument | Default | Effect |
| --- | --- | --- |
| `rviz` | `true` | set `false` for a headless bring-up |
| `use_gui` | `false` | drag joint sliders with `joint_state_publisher_gui` |
| `use_joint_state_publisher` | `true` | set `false` when something else owns `/joint_states` |
| `rviz_config` | `<share>/rviz/wamoduck.rviz` | Fixed Frame `base_link` |
| `urdf_file` | generated URDF | publish a different description |

### 2. Watch it walk the reference gait

```bash
ros2 launch wamoduck_ros2 gait_display.launch.py
```

That is the whole one-click path: `gait_player` reads
`share/wamoduck_ros2/data/gait_cycle_2s_50Hz.csv` and publishes it as `sensor_msgs/JointState`
while `robot_state_publisher` turns it into TF and RViz draws it. The base trajectory from the
CSV's `base_x` / `base_y` / `base_z` / `base_roll_rad` is broadcast as `world -> base_link`,
so `gait_display.launch.py` selects `wamoduck_world.rviz` (Fixed Frame `world`) for you.

| Argument | Default | Effect |
| --- | --- | --- |
| `csv_path` | installed `gait_cycle_2s_50Hz.csv` | any other track, e.g. `gait_walk_1m_10Hz.csv` |
| `loop` | `true` | repeat forever |
| `time_scale` | `1.0` | playback rate multiplier |
| `start_delay_s` | `1.0` | let RViz load meshes before the first sample |
| `publish_base_tf` | `true` | `false` also switches RViz to Fixed Frame `base_link` |
| `rviz` | `true` | `false` runs the player headless |

The two reference tracks are quasi-static **kinematic IK plans**, not hardware logs and not
the output of a trained policy: `step_len = 0.01 m`, `speed = 0.01 m/s` for both. The player's
own log line reports its achieved rate so the timing can be checked rather than trusted.

### 3. The nodes on their own

```bash
# gait replay without a display
ros2 run wamoduck_ros2 gait_player --ros-args -p csv_path:=/abs/path.csv

# the same, with the convenience flag; --loop is not a ROS argument, it is stripped
ros2 run wamoduck_ros2 gait_player --loop

# protocol bridge, loopback transport, no hardware required
ros2 run wamoduck_ros2 bridge_stub

# policy loop (skeleton: assembles observations, never infers)
ros2 run wamoduck_ros2 policy_node
```

### 4. Inspect what is flowing

```bash
ros2 topic echo /joint_states --once
ros2 topic hz /joint_states
ros2 topic echo /tf --once
ros2 run tf2_tools view_frames          # needs graphviz
```

---

## The 46-byte link, in one page

`wamoduck_ros2/frame_codec.py` implements deployment protocol v1. It is wire-compatible with
the reference implementation in the internal engineering tree, and it is deliberately ROS-free
so it can be tested without a graph or hardware.

```
SOF(0xA5) | TYPE | LEN | SEQ | PAYLOAD | CRC16(TYPE..PAYLOAD)
   1 B      1 B    1 B   1 B     LEN B          2 B
```

CRC is **CRC16-CCITT-FALSE** (poly `0x1021`, init `0xFFFF`, no reflection, no final xor);
`CRC16-CCITT-FALSE(b"123456789") == 0x29B1` is asserted by the test suite, because a wrong CRC
variant fails only on the wire and looks exactly like a noisy cable. All integers are
little-endian.

| Direction | TYPE | Name | Payload | Frame | Rate |
| --- | --- | --- | ---: | ---: | --- |
| host → cerebellum | `0x01` | `CMD` | 40 B: `mode, flags, t_ms, q[14] i16, twist[3] i16` | **46 B** | 50 Hz |
| host → cerebellum | `0x02` | `ESTOP` | empty | 6 B | event |
| cerebellum → host | `0x81` | `STATE_Q` | 32 B: `age_ms, q[14], status` | 38 B | 200 Hz |
| cerebellum → host | `0x82` | `STATE_DQ` | 32 B: `age_ms, dq[14], status` | 38 B | 200 Hz |
| cerebellum → host | `0x83` | `STATE_IMU` | 24 B: `age_ms, gyro[3], acc[3], quat[4] wxyz, status` | 30 B | 200 Hz (optional) |
| cerebellum → host | `0x84` | `EVENT` | 4 B: `code, arg` | 10 B | event |

Uplink is 106 B/round, i.e. 21.2 kB/s at 200 Hz, 23 % of a 921600 8N1 UART. Every payload is
≤ 64 B, so the same framing fits one CAN-FD message per frame with no change above the
transport.

Fixed-point scales: `q` rad→mrad ×1000, `dq` rad/s→0.01 ×100, `gyro` ×100, `acc` ×100,
`quat` ×30000, `twist` m/s→mm/s ×1000 and rad/s→mrad/s ×1000. Out-of-range values
**saturate**; they never wrap.

**Array order.** `q` and `dq` are always in *joint-tree order* — the 14-joint order in
`model_contract.JOINT_ORDER` — which is also the order of `joint_pos` / `joint_vel` inside the
policy observation, **and the order of the policy's own 14-wide output**. The permutation
between action and joint is therefore the identity, and it is still applied once, on the host,
in `policy_interface.action_to_joint_target()`.

Three different joint orders exist in this project and mixing them up is a known bug class.
The code keeps them apart, and `test_model_contract.py` asserts that the URDF's document order
**differs** from the contract order (so a future "tidy-up" fails the tests instead of silently
re-wiring a joint):

| Order | Where | Contents |
| --- | --- | --- |
| joint-tree order | `JOINT_ORDER`, 14 names | `left_hip_yaw, left_hip_roll, …, left_ankle, right_hip_yaw, …, head_roll` |
| actuator order | MJCF `<actuator>`, 14 | L/R interleaved per joint kind; **not** the action order — `action_to_joint` is the identity |
| URDF document order | `models/wmduck/wmduck.urdf`, 15 joints | L/R interleaved, plus `mouth` |

The action order was **adjudicated on 2026-09-16** in favour of joint-tree order. This module
previously read the action vector in actuator order; four independent lines of evidence settled
it: mjlab's own resolver on the training MJCF returns `target_ids = [0 … 13]`; every published
policy's ONNX metadata records `joint_names` in tree order; a one-hot MuJoCo probe driving one
action channel at a time moves `JOINT_ORDER[i]` and nothing else; and a 2×2 ablation over
observation × action order leaves only tree/tree standing, walking, crouching and getting up.
See the [`model_contract`](wamoduck_ros2/wamoduck_ros2/model_contract.py) module docstring.

`gait_player` reads the joint list **out of the URDF** and matches the CSV columns to it **by
name**; it hard-codes no order at all. It publishes all 15 movable joints, including `mouth`,
which the 14-joint policy contract does not use — that is the honest visualisation of the
description and does not change what the policies observe.

---

## The policy contract

`wamoduck_ros2/policy_node.py` is a **skeleton**: it assembles observations and publishes
nothing, because `onnxruntime` is not installed and no policy has been loaded on any machine
in this tree. What *is* implemented and unit-tested is the contract.

Observation, ONNX input order, **51** wide for the walk tasks:

```
offset  0  base_ang_vel        3   rad/s, IMU gyro, body frame
offset  3  projected_gravity   3   unit vector; upright is (0, 0, -1)
offset  6  joint_pos          14   rad, relative to default_joint_pos (which is all zeros)
offset 20  joint_vel          14   rad/s
offset 34  last_action        14   the previous raw policy output, before action_scale
offset 48  command             3   (vx, vy, wz), clamped to x[-0.6,1.0] y[-0.3,0.3] wz[-0.8,0.8]
------------------------------------------------------------------------------
total                         51
```

The **stand** policies were trained with **48** inputs: the same layout with the trailing
`command` block absent. 48 and 51 are not interchangeable.

* **The normalizer is inside the ONNX graph** (`normalizer_inside_onnx: true`), so the host
  feeds **raw** observations. Normalising again on the device applies the transform twice —
  the classic way to get a policy that trains well and stands badly.
* The action is 14 wide in **joint-tree order**, the same order as the observation;
  `action_to_joint` is applied once, on the host, and is the identity.
* `q_target[joint] = default_joint_pos[joint] + action_scale * action[joint]`, with
  `default_joint_pos` all zeros and `action_scale` 1.0, so in practice `q_target = action`.
* Timing: **50 Hz**, MuJoCo `timestep = 0.005 s`, `decimation = 4` ⇒ `0.005 × 4 = 0.02 s`.
* State topics use **BEST_EFFORT + KEEP_LAST(1)**. With RELIABLE and a deeper queue, one slow
  callback leaves stale observations queued and the policy reasons about tens-of-milliseconds-old
  state; the symptom is "sluggish and oscillating", and it is hard to find afterwards.
* Start-up order: bridge and safety first, policy last. A policy that is not ready leaves the
  cerebellum on its watchdog (HOLD at 200 ms, OFF at 1000 ms). That is the intended default.

---

## Verification status

Everything below was run inside **WSL2 Ubuntu 24.04 (x86_64)** with ROS 2 **Jazzy**.
Artifacts are in [`verification/`](verification/); see
[`verification/README.md`](verification/README.md) for the exact commands.

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | `colcon build` | **PASS** — 3 packages, 0 failures, `Summary: 3 packages finished [21.6s]` | `verification/colcon_build_log.txt` |
| 2 | `robot_state_publisher` + `gait_player`, `ros2 topic echo /joint_states --once` | **PASS** — 49.998–50.001 Hz, 15 named joints in URDF document order, non-zero and finite | `verification/runtime_verification_log.txt` |
| 3 | RViz renders the description | **PASS** — headless Xvfb + llvmpipe screenshot, and also under WSLg | `verification/rviz_gait_xvfb.png`, `verification/rviz_gait_wslg.png` |
| 4 | URDF parses and the geometry is right | **PASS** — `check_urdf` on both files, plus FK at q=0 vs the published `validation.json` (agreement to 3.1e-9 m) | `verification/description_check.json` |
| 5 | 46-byte frame codec round-trip, CRC vector, resync, saturation | **PASS** — 87 tests via `colcon test` and via direct `pytest` | `verification/static_verification_log.txt` |
| 6 | `policy_node` ONNX inference | **NOT RUN** — skeleton, `onnxruntime` not installed | `policy_runner.py` docstring |

The two screenshots show the same robot in different gait phases, taken about a minute apart
with `loop:=true` running, which is itself evidence that the track is being replayed.

### Explicitly not verified

* **ARM64 / RDK X5.** Every result here is from **x86_64 Ubuntu 24.04 in WSL2**. Nothing has
  been built or run on the X5's ARM64 userspace, and availability there is **unverified**.
  The packages are pure Python plus one `message` interface, so the port is expected to be
  uneventful, but "expected" is not "verified".
* **Hardware.** No serial port, no CAN bus, no AT32, no IMU, no motors. `bridge_stub`'s
  `serial` transport has never been opened, and its `can` transport is not written (it raises
  rather than starting a bridge that does nothing).
* **`policy_node` end to end.** No ONNX was loaded, no inference ran, no output was compared
  against a MuJoCo rollout.
* **`wmduck_safety`** (watchdog, e-stop aggregation, `/diagnostics`) is not written. The
  cerebellum-side protection layer (200 ms HOLD, 1000 ms OFF, 0.35 rad per frame, limit
  clamping) is specified in the protocol and lives in the firmware; the host deliberately does
  not duplicate it, because two watchdogs with different timeouts are worse than one.
* **Dynamics of any kind.** Stage 2 has no physics. The reference gait is a kinematic IK plan.
* **Gazebo and MoveIt.** Not started.
* **RViz on WSLg.** RViz starts under WSLg, but WSLg's window contents cannot be read back
  with `import`/`xwd`, so the screenshot evidence is the headless Xvfb render. See
  `verification/README.md`.

---

## Deploying to the RDK X5

Target: Ubuntu 22.04/24.04 ARM64 on the X5, with the robot's Linux side talking to the AT32
cerebellum over `/dev/ttyS1` or CAN-FD.

1. **Install ROS 2 on the X5.** Match the distro to the X5's Ubuntu release. The packages
   here are built and tested with Jazzy on 24.04.

   ```bash
   sudo apt install ros-jazzy-ros-base ros-jazzy-robot-state-publisher
   ```

   `ros-jazzy-rviz2` only if the X5 drives a display.

2. **Copy the sources and the model.** Either clone the repository, or copy `ros2/` plus
   `models/wmduck/`:

   ```bash
   rsync -a ros2/ x5:/opt/wamoduck/ros2/
   rsync -a models/wmduck/ x5:/opt/wamoduck/models/wmduck/
   rsync -a tools/matlab/data/ x5:/opt/wamoduck/tools/matlab/data/
   ```

   The third line matters: `wamoduck_ros2` installs the gait CSVs from there. Without it the
   package still builds (with a warning) and `gait_player` needs an explicit `csv_path`.

3. **Build on the X5.** Native ARM64 build; `colcon build` is enough, the packages are tiny.

   ```bash
   mkdir -p ~/ws/src && cd ~/ws
   ln -sfn /opt/wamoduck/ros2/wamoduck_msgs src/
   ln -sfn /opt/wamoduck/ros2/wamoduck_description src/
   ln -sfn /opt/wamoduck/ros2/wamoduck_ros2 src/
   source /opt/ros/jazzy/setup.bash
   colcon build --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
   source install/setup.bash
   ```

   Omitting `-DWAMODUCK_MODELS_DIR` also works if the tree layout is preserved and the
   workspace `src/` entries are symlinks, because the description package resolves symlinks
   before walking up to `models/wmduck`.

4. **Start-up order** (`docs/16` §6.5 point 4): bridge and safety first, policy last.

   ```bash
   ros2 run wamoduck_ros2 bridge_stub --ros-args -p transport:=serial -p port:=/dev/ttyS1
   # ... then, once the state stream is healthy:
   ros2 run wamoduck_ros2 policy_node --ros-args -p onnx_path:=/opt/wamoduck/policies/....onnx
   ```

   For the 50 Hz joint loop, `docs/16` §6.5 recommends running policy and bridge in one process
   with intra-process communication (or in one node) to avoid the DDS round trip. The two are
   separate executables here, so this is an integration step still to be done.

5. **Before any of this drives a joint**, complete the calibration checklist in `docs/16` §5:
   zero offsets and sign per joint, measured limits, IMU axis mapping, and the five-parameter
   gain calibration. `policy_contract.json`'s `calibration` block is a placeholder with zeros,
   and `q = 0` is the CAD pose, **not** an encoder zero.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `package 'wamoduck_ros2' not found` although `colcon build` succeeded | `package.xml` is not valid XML, so colcon classified it as plain `python`. Check `colcon list`: it must say `(ros.ament_python)`. |
| Robot renders empty in RViz | Mesh references are not `package://`. Run `tools/verify_description.py` — it checks this against an arbitrary working directory. |
| `colcon build` fails with "canonical URDF not found" | Only `ros2/` was copied. Pass `-DWAMODUCK_MODELS_DIR=...`. |
| `colcon build` fails with "'data_files' must be relative" | colcon asserts relative `data_files` sources; `setup.py` converts the gait CSV paths with `os.path.relpath` for this reason. |
| RViz shows a tiny speck | The `Views` block in the `.rviz` file sets the orbit distance to 0.85–1.0 m; the RViz default of 10 m is far too wide for a 0.39 m robot. |
| An `.rviz` edit seems to have no effect | The configs are copied into `share/` at install time, so a rebuild is needed. Use `colcon build --symlink-install` to avoid this. |
| `gait_player` warns a URDF joint has no column | The CSV and the URDF disagree; the warning names the joint. It is published at 0.0 rather than silently dropped. |

## License

MIT, copyright © 2026 Wamotech — the same as the rest of this repository. See [`../LICENSE`](../LICENSE).
