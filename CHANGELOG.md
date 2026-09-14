# Changelog / 更新记录

## Unreleased / 尚未发布

### 2026-09-14 — Motor mass updated to a measurement / 电机质量改用实测值

- The 15 motor instances now use the maintainer-measured **141 g** instead of the 150 g transcribed from the vendor parameter image. Model total mass **3.886339783 → 3.751339783 kg**. / 15 个电机实例改用维护者实测的 **141 g**（原为厂家参数图转录的 150 g），模型总质量 **3.886339783 → 3.751339783 kg**。
- Because motor centers of mass are retained and motor inertias are rescaled by mass ratio, every link that carries a motor changed slightly in mass, center of mass, and inertia. Link geometry, joint definitions, and the zero-pose envelope are unchanged, and the package checks were recomputed from the updated URDF. / 由于电机质心保持不变、惯量按质量比缩放，**每个带电机的 link** 在质量、质心与惯量上都有小幅变化；link 几何、关节定义与零位姿态包络未变，资料包校验项已按更新后的 URDF 重算。
- `motor_parameters.json` now records the basis and date of the mass value, lists the 3.6 N·m peak alongside the 3.7 N·m stall figure, and records a bench observation that the motor held **3.5 N·m for more than 30 s** — labelled as one observation, not a duty-cycle or thermal rating, and with the rated 0.6 N·m left unchanged. / `motor_parameters.json` 现在记录了质量数值的来源与日期、把 3.6 N·m 峰值与 3.7 N·m 堵转并列，并记录了一条台架观测：电机**持续输出 3.5 N·m 超过 30 s**；该条明确标注为单次观测、不是占空比或热额定值，额定 0.6 N·m 不变。
- `component_mass_audit.csv` and `validation.json` were regenerated; the audit's mass column sums to the URDF model mass to within 1e-9 kg, and both manifests carry the new hashes. / 重新生成了 `component_mass_audit.csv` 与 `validation.json`；台账质量列合计与 URDF 模型质量相差 1e-9 kg 以内，两份清单已更新为新哈希。

### 2026-09-14 — Reference gait, MATLAB player, and gait media / 参考步态、MATLAB 回放器与步态媒体

- Added a walking reference trajectory for the published URDF: one steady-state gait cycle (2.0 s, 100 frames at 50 Hz) and the full 1 m walk (104 s at 10 Hz), with joint angles in radians, inverse-dynamics torque estimates, and the body pose. / 新增针对公开 URDF 的行走参考轨迹：一个稳态步态周期（2.0 s，50 Hz 共 100 帧）与整段 1 m 行走（104 s，10 Hz），含弧度制关节角、逆动力学力矩估计与机体位姿。
- Added `tools/matlab/wamoduck_play.m`: an interactive MATLAB player with a per-joint angle/torque table, a torque plot against the motor's rated and peak values, two data sets, and a self-test that checks units, joint limits, and ground contact. / 新增 `tools/matlab/wamoduck_play.m`：交互回放器，含逐关节角度／力矩表、与电机额定／峰值对照的力矩曲线、两份数据，以及检查单位、关节限位与脚底贴地的自检。
- Added gait media rendered from the public URDF: a seamless two-cycle GIF, a 20 s walk video, a still frame, and a screenshot of the MATLAB player. / 新增由公开 URDF 渲染的步态媒体：无缝两周期 GIF、20 s 行走视频、单帧静图，以及 MATLAB 回放器截图。
- Added the [gait guide](docs/matlab.en.md) / [步态指南](docs/matlab.zh-CN.md) in both languages, covering the data format, the scope of the plan, and the measured limits of this leg design: there is no ankle-roll joint, and a single-support step would need at least 57 mm of lateral centre-of-mass travel. / 新增中英文[步态指南](docs/matlab.zh-CN.md)，说明数据格式、规划口径，以及这条腿**实测**出来的限制：没有踝侧摆关节，单脚支撑至少需要 57 mm 的重心横移。
- The gait is a kinematic inverse-kinematics plan with a static-stability check. It is not a trained policy, not hardware data, and not a dynamic-balance result; the media manifest records this scope per asset. / 该步态是带静态稳定性检查的逆运动学规划，不是训练策略、不是实物数据、也不是动态平衡结果；媒体清单按条目记录了该口径。

### 2026-09-12 — Project overview and motion preview / 项目介绍与运动演示

- Highlighted servo closed-loop control, the MCU/Arm architecture, local vision, and mechanical extensibility in both READMEs. / 中英文首页突出伺服闭环、MCU／Arm 架构、本地视觉和结构扩展性。
- Updated project progress: mechanical prototyping, hardware/software integration, completed MuJoCo simulation, the ONNX deployment approach, and experiments with wearable robots. / 更新结构打样、软硬件联调、已完成 MuJoCo 仿真、ONNX 部署方式及穿戴机器人实验应用等进展。
- Added an actual URDF joint-motion GIF and the finalized export's 15-DOF overview. / 新增由实际 URDF 生成的关节运动 GIF，以及最终导出的 15 自由度总览。
- Distinguished project development progress from code and models already published in this repository. / 区分项目研发进展与本仓库已经公开的代码、模型范围。

### 2026-09-12 — Initial mechanical package / 首次机械资料整理

- Added English and Chinese project introductions, mechanical/model guides, a component inventory, and a roadmap. / 新增中英文项目介绍、机械／模型指南、组件清单与路线图。
- Selected 20 STEP models and 31 native SolidWorks files from the simplified design set. / 从简化设计中选入 20 个 STEP 与 31 个 SolidWorks 原生文件。
- Included the 15-DOF URDF, 20 meshes, and model parameter records. / 纳入 15 自由度 URDF、20 个网格与模型参数记录。
- Added asset hashes and package validation evidence. / 补充资产哈希与资料包验证记录。

This entry describes local preparation; no GitHub release is implied. / 本条记录描述本地整理，不表示已在 GitHub 发布版本。
