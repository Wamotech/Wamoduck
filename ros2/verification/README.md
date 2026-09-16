# Verification evidence

Everything in this directory was produced by the commands listed below, on the machine and
versions stated. Nothing here is a description of intent: each file is the captured output of
a run, and the claims in [`../README.md`](../README.md) point back to these files.

If you want to re-run it, the scripts are the only thing you need — see
[Reproducing this](#reproducing-this).

## Environment actually used

| Item | Value |
| --- | --- |
| Host | Windows 11, WSL2 |
| Guest | Ubuntu 24.04 LTS (noble), `x86_64`, kernel `6.18.33.2-microsoft-standard-WSL2` |
| CPU / RAM | 20 cores / 19 GB |
| ROS 2 | **Jazzy**, `/opt/ros/jazzy`, `ros-jazzy-desktop 0.11.0-1noble.20260616.084553` |
| RViz | `ros-jazzy-rviz2 14.1.23-1noble.20260905.070259` |
| robot_state_publisher | `3.3.4-1noble.20260903.022201` |
| colcon | `python3-colcon-common-extensions 0.3.0-100` (colcon-core `0.21.2`) |
| pytest | `7.4.4-1` |
| liburdfdom-tools | `4.0.0-0ubuntu1` |
| Renderer | Mesa **llvmpipe** (`LLVM 20.1.2, 256 bits`), OpenGL 4.5 — **software, no GPU** |
| Build tree | `~/ws_wamoduck` (WSL-native), packages symlinked from `ros2/*` |

**This is x86_64 Ubuntu in WSL2. It is not the RDK X5, and it is not ARM64.** See
[Not covered](#not-covered).

## Files

| File | What it is | What it proves |
| --- | --- | --- |
| `colcon_build_log.txt` | full `colcon build` output | all three packages configure, build and install; the generated URDF manifest is printed |
| `static_verification_log.txt` | `check_urdf` on both URDFs, the geometric verifier, `colcon test`, and `pytest` | the description parses, its geometry matches the published record, and the 87 unit tests pass |
| `runtime_verification_log.txt` | nodes, topic echoes, rate measurement, RViz log, screenshot analysis | `robot_state_publisher` + `gait_player` publish a legal `JointState` stream at 50 Hz and RViz renders it |
| `description_check.json` | machine-readable report from `tools/verify_description.py` | per-check pass/fail, computed bounds, deviations, mesh triangle counts |
| `description_check_canonical_urdf.json` | the same report for `models/wmduck/wmduck.urdf` | the canonical URDF fails **exactly one** check — the working-directory one — which is why the build rewrites mesh paths, and proves the rewrite changes nothing else |
| `rviz_gait_xvfb.png` | RViz screenshot, headless Xvfb + llvmpipe | the description renders: 1400×900, 2346 distinct colours, meshes shaded, grid and TF visible |
| `rviz_gait_wslg.png` | RViz screenshot, WSLg (`:0`) | the same under WSLg — see the note on capture below |

## Key observed results

### Build

```
wamoduck_description  src/wamoduck_description  (ros.ament_cmake)
wamoduck_msgs         src/wamoduck_msgs         (ros.ament_cmake)
wamoduck_ros2         src/wamoduck_ros2         (ros.ament_python)
...
Summary: 3 packages finished [21.6s]
colcon build exit code: 0
```

`(ros.ament_python)` is load-bearing. When it reads `(python)` instead, `colcon build` still
succeeds but no ROS environment is generated for the prefix, so `ros2 launch` can never find
the package. That happened during development (an unescaped `<` in `package.xml`) and is now
covered by `test_package_manifests.py`.

The generated URDF manifest cross-checks the source model:

```
source_urdf_sha256            fd39cb49985354e76bc1e15745bf58e5824461246d492f439db77d5e2c1dd5d1
mesh_references_rewritten     79
unique_meshes_referenced      20
links                         17
movable_joints                15   (URDF document order, including `mouth`)
fixed_joints                  1    (imu_fixed)
structural_equality_vs_source true
```

That source SHA-256 is **identical to `urdf_sha256` in `models/wmduck/validation.json`**, so
the description installed here was built from exactly the URDF the published validation record
covers.

### URDF parsing and geometry

`check_urdf` succeeds on both the canonical and the generated URDF, reporting the same tree:
root `base_link` with children `imu_link`, `left_hip_yaw_link`, `neck_pitch_link`,
`right_hip_yaw_link`, and 16 joints total.

`tools/verify_description.py` then goes past parsing:

```
[PASS] tree_has_exactly_one_root                  roots=['base_link']
[PASS] every_link_is_connected                    16 child links for 17 links
[PASS] no_structural_problems
[PASS] forward_kinematics_reaches_every_link      0 links unreachable
[PASS] mesh_references_were_found_at_all          79 mesh tags under <visual>/<collision>
[PASS] all_mesh_references_resolve                0 unresolved
[PASS] no_mesh_reference_needs_the_rviz_cwd       0 references depend on the working directory
[PASS] every_referenced_mesh_parses_as_binary_stl 20 distinct mesh files
[PASS] zero_pose_bounds_match_the_published_record best variant 'all', deviation 3.140e-09 m
[PASS] triangle_count_matches_the_published_record 237802 triangles, published 237802
[PASS] link_and_joint_counts_match_the_published_record 17 links / 16 joints
[PASS] root_link_matches_the_published_record     ['base_link'] vs base_link
[PASS] left_right_link_frames_are_mirror_symmetric worst deviation 0.000e+00 m over 5 pairs
RESULT: ALL CHECKS PASSED
```

The bounds check is the one that matters for "no obvious misalignment". Forward kinematics is
computed from the URDF alone, every mesh vertex is transformed, and the resulting axis-aligned
box is compared against the published record:

```
published : [-0.08340850082323419, -0.1106025029906681, -0.17761809544517723]
            [-0.08340850082323419 ...]
          .. [0.09809900589255854, 0.11060250303302659, 0.21321191008871637]
computed  : [-0.08340850082323417, -0.11060250211000443, -0.17761809473751067]
          .. [0.09809900275250455, 0.11060250211000443, 0.21321190877487214]
size        published [0.18150750671579274, 0.2212050060236947, 0.3908300055338936]
            computed  [0.18150750357573872, 0.22120500422000886, 0.39083000351238284]
```

The residual is **3.14e-9 m (3.1 nanometres)**. It is float32 rounding, not geometry
disagreement: the STL vertex coordinates are float32, whose epsilon for coordinates of order
0.2 m is ~2.4e-8 m, so an independent double-precision reader cannot reproduce the published
figures bit-for-bit. The tolerance is set to 1e-6 m — three orders of magnitude above that
residual and at least three below any real error (a wrong joint origin, a wrong `rpy`, a wrong
mesh or a wrong scale all move this box by millimetres at minimum). The exact residual is
always recorded in the JSON, so the number can be judged rather than trusted.

Running the same verifier on the **canonical** URDF produces identical geometry results and
fails exactly one check:

```
[FAIL] no_mesh_reference_needs_the_rviz_cwd
       79 references would resolve only from a lucky working directory (RViz launched from /)
RESULT: FAILED  (only this check)
```

That is the defect the build-time rewrite fixes, demonstrated rather than asserted.

### Unit tests

```
build/wamoduck_ros2/pytest.xml: 78 tests, 0 errors, 0 failures, 0 skipped
```

plus the 9 tests in `test_package_manifests.py`, for **87 tests** total, passing both through `colcon test`
and through `python3 -m pytest` directly. What they cover:

* **CRC16-CCITT-FALSE pinned to a published vector** (`"123456789"` → `0x29B1`). A wrong CRC
  variant fails only on the wire and is indistinguishable from a noisy cable.
* **The exact CMD byte layout**, against a byte string assembled by hand in the test (the head
  as literal bytes, the arrays via a format string spelled out in the test rather than reused
  from the module), so a wire-format change must be made in two places.
* Frame sizes: 46 / 38 / 38 / 30 / 10 / 6 bytes; every payload ≤ 64 B for CAN-FD; the 106 B
  uplink round and its 23 % share of a 921600 8N1 UART.
* Round trips with quantisation bounds; **int16 saturation clamps and never wraps**
  (`+99 rad → +32.767`, not `-12`); rejected bad lengths; corrupted frames counted and the
  following good frame preserved; partial frames buffered; noise resynchronised.
* Observation layout position by position; the 48-wide stand layout equal to the 51-wide walk
  layout truncated; **the observation is not normalised**; command clamping to the trained
  ranges.
* `action_to_joint` pinned as the identity, and spelled out by joint name, so a swapped leg
  fails loudly. The action-order adjudication of 2026-09-16 settled that the policy output is
  in joint-tree order, not MJCF `<actuator>` order; the test also names the actuator-order
  permutation it replaced, so reintroducing it fails with a readable message.
* The URDF is read for movable joints, and the test asserts the URDF's document order
  **differs** from the contract order — if someone "tidies" one into the other, the suite fails
  instead of silently re-wiring a joint.
* The gait CSV reader: rebasing, non-uniform timestamps via the median, ragged rows, missing
  columns, and name-based matching with warnings rather than silent drops.
* Both real reference tracks (`100 samples @ 50 Hz`, `1040 samples @ 10 Hz`, 15 joints each).

### Runtime

`robot_state_publisher` + `gait_player`, started through the real launch file:

```
[gait_player]: CSV            : .../share/wamoduck_ros2/data/gait_cycle_2s_50Hz.csv
[gait_player]:                  100 samples, 1.980 s, 50.000 Hz nominal, uniform_dt=True
[gait_player]: URDF           : .../share/wamoduck_description/urdf/wmduck.urdf
[gait_player]:                  15 movable joints in URDF document order: left_hip_yaw,
                 right_hip_yaw, left_hip_roll, right_hip_roll, left_hip_pitch,
                 right_hip_pitch, left_knee, right_knee, left_ankle, right_ankle, neck_pitch,
                 head_pitch, head_yaw, head_roll, mouth
[gait_player]: publishing     : 15 CSV-driven joints in URDF order, timer 50.0 Hz
[gait_player]: base TF        : world -> base_link from base_x/y/z + base_roll_rad
[gait_player]: contract check : URDF document order == contract joint_order ? False
```

`ros2 topic echo /joint_states --once` produces a complete, legal message: 15 names, 15
positions, 15 velocities and 15 efforts, with the names in URDF document order and the values
non-zero (so something is genuinely animating) and finite:

```
name: [left_hip_yaw, right_hip_yaw, left_hip_roll, right_hip_roll, left_hip_pitch,
       right_hip_pitch, left_knee, right_knee, left_ankle, right_ankle, neck_pitch,
       head_pitch, head_yaw, head_roll, mouth]
position: [-0.045697, -0.279275, -0.017825, -0.006765, 0.126214, 0.279829, -0.324853,
           -0.300574, 0.197759, 0.018573, 0.0, 0.0, 0.0, 0.0, 0.0]
```

The head and mouth joints are exactly `0.0` because those columns are zero throughout the
reference CSVs — not because they failed to publish.

`ros2 topic echo /tf --once` shows the base trajectory:

```
frame_id: world
child_frame_id: base_link
translation: {x: 0.039, y: 0.0, z: 0.169618}
rotation:    {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
```

Those come from the CSV's `base_x` / `base_y` / `base_z` / `base_roll_rad`; the CSV carries no
pitch and no yaw, so none is invented.

Rate, measured three independent ways:

| Method | Result |
| --- | --- |
| `ros2 topic hz /joint_states` | `average rate: 49.998` / `49.999`, `min: 0.018s max: 0.022s std dev: 0.00026s` |
| `gait_player` self-report | `published 2199 messages, achieved 50.00 Hz (target 50.00 Hz)` |
| independent subscriber | `observed rate : 50.001 Hz` over 202 received samples |

The subscriber also confirms `names == URDF document order : True`, widths 15/15/15,
`all positions zero : False`, `all positions finite : True`, `all samples stamped : True`.

Read the subscriber row carefully: it reports **202** samples in a 6-second window, which is
not `50 x 6`. That is the intended behaviour, not a shortfall. The subscription uses
`KEEP_LAST(1)` on purpose (`docs/16` §6.5 point 1): a consumer slower than the publisher must
drop stale samples rather than queue them, because a queued stale observation is what makes a
policy appear "sluggish and oscillating". The Python subscriber below only drains when it is
scheduled, so it deliberately sees a subset — and the subset it does see arrives at 50.001 Hz,
measured between its own first and last received message. `ros2 topic hz`, which is written in
C++, is the better rate measurement of the two.

### RViz

RViz was started twice from the same launch file.

**Headless (Xvfb `:99` + llvmpipe software GL, `QT_QPA_PLATFORM=xcb`).** This is the primary
screenshot evidence, and it is reproducible without a GPU or a display:

```
Xvfb :99 -> OpenGL renderer string: llvmpipe (LLVM 20.1.2, 256 bits)
            OpenGL version string: 4.5 (Compatibility Profile) Mesa 25.2.8
RViz window present after ~5 s
0x200106 ".../rviz/wamoduck_world.rviz - RViz": ("rviz2" "rviz2")  1400x900+0+0
```

The window title confirms RViz loaded the config the launch file selected. The PNG is
1400×900 with 2346 distinct colours: background `#303030` (the configured
`Background Color: 48;48;48`), a large band of shaded grey mesh surfaces, and the grid. A blank
or failed render would be a single colour.

The image shows the assembled biped standing on the 1 m grid, mid-gait: legs posed by the
reference track, the two feet staggered, the head and body above. The joint frames are
where the URDF puts them, which is the visual counterpart of the bounds check above.

**WSLg (`DISPLAY=:0`).** RViz starts and creates its window under WSLg (`Weston WM` present,
`fatal-pattern lines: 0`), and a 1400×900 capture of the RViz client window succeeds
(`unique_colours=2460`).

> **Capture caveat.** Reading back WSLg's **root** window with `import`/`xwd` fails
> (`Resource temporarily unavailable`) — WSLg's root window is not a capturable X pixmap. The
> WSLg image is therefore taken from the RViz **client window id** (resolved from
> `xwininfo -root -tree`). It is a screenshot of the same render, but it is captured by a
> different mechanism than the Xvfb one, so the Xvfb image is the one to rely on if the two
> ever disagree.

## Not covered

Stated plainly, because these are the places where "verified" could be overstated:

* **ARM64 / RDK X5 — not verified at all.** Every number above is x86_64 Ubuntu 24.04 under
  WSL2. Nothing was built or run on the X5's ARM64 userspace. The packages are pure Python
  plus one message interface, so the port is *expected* to be uneventful; that is a
  prediction, not a result.
* **Hardware — never touched.** No serial port, no CAN bus, no AT32, no IMU, no motors.
  `bridge_stub`'s `serial` transport has never been opened. Its `can` transport is not
  implemented and raises rather than starting a bridge that silently moves nothing.
* **`policy_node` — skeleton.** No ONNX was loaded, no inference ran, no output was compared
  against a MuJoCo rollout. `onnxruntime` is not installed. The observation assembly, the
  command clamp and the action permutation *are* implemented and unit-tested.
* **No dynamics anywhere.** Stage 2 renders a kinematic tree. RViz integrates nothing,
  collides nothing and applies no gravity. The reference gait is a quasi-static IK plan, not
  hardware data and not a trained policy. **A gait that looks right on screen proves nothing
  about balance.**
* **Gazebo and MoveIt — not started.** `ros-jazzy-ros-gz` is not a dependency of anything here.
* **`wmduck_safety` is not written.** The cerebellum-side protection layer (200 ms HOLD,
  1000 ms OFF, 0.35 rad per frame, limit clamping) is specified in the protocol and lives in
  the firmware. The host deliberately does not duplicate it: two watchdogs with different
  timeouts are worse than one.
* **Foot clearance during the gait was not computed.** Two raw numbers that invite a wrong
  conclusion, so they are given with their scope: the URDF's zero-pose lowest point is
  0.17762 m below `base_link` (`validation.json`), the 2 s cycle's `base_z` is ≈0.16962 m and
  the walk track's is ≈0.17759 m. Read at the *CAD standing pose* that would put the soles
  ~8 mm below `z = 0` for the cycle and ~0 for the walk track. Whether the actual gait poses
  keep the feet above the floor was **not** evaluated; that would require FK over the track,
  and it is a kinematic statement about the plan either way, not a contact or dynamics result.

### Benign warnings you will see

* `[kdl_parser]: The root link base_link has an inertia specified in the URDF, but KDL does not
  support a root link with an inertia.` — `base_link` carries an inertia because the model has
  a real mass distribution. KDL ignores it for TF purposes. It does not affect the rendered
  link frames.
* `RViz: Stereo is NOT SUPPORTED` — expected under llvmpipe and on any non-stereo display.

## Reproducing this

The run scripts live outside the repository, in the WSL guest. To reproduce, from a full clone:

```bash
# 1. workspace
mkdir -p ~/ws_wamoduck/src && cd ~/ws_wamoduck
for p in wamoduck_msgs wamoduck_description wamoduck_ros2; do
  ln -sfn /path/to/Wamoduck/ros2/$p src/$p
done
source /opt/ros/jazzy/setup.bash

# 2. build
colcon build 2>&1 | tee colcon_build_log.txt

# 3. static: parse, geometry, unit tests
check_urdf /path/to/Wamoduck/models/wmduck/wmduck.urdf
check_urdf install/wamoduck_description/share/wamoduck_description/urdf/wmduck.urdf
source install/setup.bash
python3 /path/to/Wamoduck/ros2/tools/verify_description.py \
  --urdf install/wamoduck_description/share/wamoduck_description/urdf/wmduck.urdf \
  --meshes install/wamoduck_description/share/wamoduck_description/meshes \
  --validation /path/to/Wamoduck/models/wmduck/validation.json \
  --rviz-cwd / \
  --report description_check.json
colcon test && colcon test-result --all --verbose
python3 -m pytest /path/to/Wamoduck/ros2/wamoduck_ros2/test -q

# 4. runtime (no display needed for the first part)
ros2 launch wamoduck_ros2 gait_display.launch.py rviz:=false loop:=true &
ros2 topic echo /joint_states --once
ros2 topic echo /tf --once
timeout 12 ros2 topic hz /joint_states

# 5. RViz screenshot, headless, no GPU
Xvfb :99 -screen 0 1400x900x24 &
DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe QT_QPA_PLATFORM=xcb \
  ros2 launch wamoduck_ros2 gait_display.launch.py loop:=true &
sleep 35
DISPLAY=:99 import -window root rviz_gait_xvfb.png
identify -format '%wx%h unique_colours=%k\n' rviz_gait_xvfb.png
```

Notes worth knowing before you re-run it:

* `verify_description.py` needs `numpy` (it ships with ROS 2) and no display.
* Editing an `.rviz` file requires a **rebuild** for the change to reach `share/`, because the
  configs are copied at install time. This bit during development: the first screenshots used
  the old camera because the install tree still held the previous file. Use
  `colcon build --symlink-install` to avoid it.
* `--loop` and `--no-loop` are stripped from `argv` before `rclpy.init`, so they are not ROS
  arguments; `--ros-args -p loop:=true` is equivalent.
* Do not pipe a long `colcon build` into `Select-Object -First N` (PowerShell) or anything that
  closes the pipe early — it terminates the build mid-install and leaves a half-populated
  `install/`. Redirect to a file and read the file instead.
