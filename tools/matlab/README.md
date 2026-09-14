# MATLAB reference-gait player / MATLAB 参考步态回放器

[English home](../../README.md) · [中文首页](../../README.zh-CN.md) · [Gait guide (EN)](../../docs/matlab.en.md) · [步态指南（中文）](../../docs/matlab.zh-CN.md)

| File / 文件 | Purpose / 用途 |
| --- | --- |
| [wamoduck_play.m](wamoduck_play.m) | Interactive player for the reference gait: play/pause, step size, two data sets, skeleton or mesh view, per-joint angle/torque table / 参考步态交互回放器：播放暂停、推进步长、两份数据、骨架或网格显示、逐关节角度与力矩表 |
| [data/gait_cycle_2s_50Hz.csv](data/gait_cycle_2s_50Hz.csv) | One full gait cycle, 100 frames at 50 Hz (2.0 s, 2 cm forward) / 一个完整步态周期，50 Hz 共 100 帧（2.0 s，前进 2 cm） |
| [data/gait_walk_1m_10Hz.csv](data/gait_walk_1m_10Hz.csv) | The full 1 m walk, decimated to 10 Hz (104 s; 10 cm/s of playback is not implied) / 整段 1 m 行走，抽稀到 10 Hz（104 s） |

```matlab
% MATLAB R2021b+ with Robotics System Toolbox / 需要 R2021b+ 与 Robotics System Toolbox
cd <repo>            % the folder that contains models/ and tools/ / 含 models 与 tools 的那层
addpath('tools/matlab')
wamoduck_play        % interactive / 交互
wamoduck_play(true)  % full-row headless self-test / 全行无界面自检
```

## Data format / 数据格式

One CSV per data set, with a single `#` provenance line first (**`readtable` needs `'CommentStyle','#'`** / 首行是 `#` 开头的说明，**`readtable` 必须加 `'CommentStyle','#'`**):

| Column / 列 | Unit / 单位 | Meaning / 含义 |
| --- | --- | --- |
| `t_s` | s | Sample time, 50 Hz or 10 Hz / 采样时刻 |
| `q_<joint>` × 15 | **rad** | Joint angle for all 15 revolute joints, including `mouth` / 15 个转动关节角（含 `mouth`） |
| `tau_<joint>` × 15 | **N·m** | Inverse-dynamics torque estimate / 逆动力学力矩估计 |
| `base_x`, `base_y`, `base_z` | m | Body (`base_link`) position / 机体位置 |
| `base_roll_rad` | rad | Body roll about X; pitch and yaw are zero in this plan / 机体绕 X 侧倾，本规划中俯仰与偏航为 0 |

Angles are given in **radians** so that they can be passed straight into `show()`/`homeConfiguration` with **no unit conversion anywhere**. / 角度用**弧度**给出，可直接送进 `show()`／`homeConfiguration`，**全程不做单位换算**。

The cycle file starts at a **steady-state** cycle (a transient first cycle was excluded) and its loop seam is one frame step (0.13°), so it can be played as a seamless loop. / 周期文件取的是**稳态**周期（已排除起步那一圈），循环接缝等于一帧步进（0.13°），可无缝循环。

## Scope / 口径

This is a **kinematic replay**: prescribed joint angles plus forward kinematics. There is no physics integration, no controller, no ONNX policy, and no hardware data. The unpublished trajectory generator produced the plan in a separate project; this player only replays the CSV and does not recompute IK or inverse dynamics. The torques are model-based estimates, not measurements. The bundled 10 Hz walk CSV has an actual peak of **2.50815 N·m**; the separately reported full-rate planning peak is 2.53 N·m. / 这是**运动学回放**：给定关节角 + 前向运动学，不含物理积分、不含控制器、不是 ONNX 策略、不是实物数据。未公开的轨迹生成器在独立项目中生成规划；本回放器只读取 CSV，不重算 IK 或逆动力学。力矩是模型估计值，不是实测。随附 10 Hz 全程 CSV 的实际峰值为 **2.50815 N·m**；另行报告的全采样率规划峰值为 2.53 N·m。

`wamoduck_play(true)` retains the existing quick smoke test: it samples the middle row of each CSV, checks joint limits and a coarse ±20 mm sole-height range, then saves a hidden-figure screenshot. It is not an all-frame contact or balance test. / `wamoduck_play(true)` 保留原有快速自检：抽查两份 CSV 各自的中间帧，检查关节限位与粗略的 ±20 mm 脚底高度范围，并保存隐藏图形截图；它不代表全帧接触检查或平衡验证。

The URDF `q=0` pose is not an actuator encoder zero. The [standing-zero fixture](../../hardware/fixtures/standing-zero/README.md) / [站姿零位工装](../../hardware/fixtures/standing-zero/README.zh-CN.md) can help measure encoder offsets, but this player neither applies those offsets nor sends commands to hardware. / URDF 的 `q=0` 姿态不是执行器编码器零位；工装可辅助测量偏置，本回放器既不应用偏置，也不向实机发送指令。

## Known limitations / 已知限制

- **MATLAB figure rendering is the bottleneck, not the data.** A bare `drawnow` on this machine costs ~0.17 s, so the mesh view runs at well under 1 fps and the skeleton view at a few fps. The default **skeleton view** exists for that reason; use it to watch motion and switch to the mesh view to inspect a pose. / **瓶颈是 MATLAB 的图形刷新，不是数据**：本机一次空 `drawnow` 约 0.17 s，所以网格视图不到 1 fps、骨架视图几 fps。默认用**骨架视图**看运动，切到网格视图看姿态。
- The locomotion is a **low-clearance quasi-static shuffle**, with one foot lifting about 4.5 mm while the other stays in contact; it is not a dynamic walk. See the [gait guide](../../docs/matlab.en.md#what-the-gait-does-and-does-not-do) for the model calculations. / 这是**低抬脚的准静态蹭步**：一只脚抬高约 4.5 mm 时另一只脚保持接地；它不是动态行走。模型计算口径见[步态指南](../../docs/matlab.zh-CN.md)。
- `wamoduck_play` is a **viewer**. It contains no balance controller and does not attempt to keep the robot upright. / `wamoduck_play` 只是**查看器**，不含平衡控制器。
