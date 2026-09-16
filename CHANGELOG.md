# Changelog / 更新记录

## Unreleased / 尚未发布

### 2026-09-16 — Measured capability summary and the standing criterion / 实测能力清单与站位判定口径

- Added [measured capabilities](docs/capabilities.md) / [实测能力清单](docs/capabilities.zh-CN.md): one honest board of the six trained policies (standing against pushes, knock-down recovery, get-up, walking, 1 cm rough terrain, sit/stand), each with its policy, its measured numbers, and the internal tool that produced them. Every figure is copied from a 2026-09-16 measurement log; no figure is extrapolated. / 新增[实测能力清单](docs/capabilities.zh-CN.md)与[英文版](docs/capabilities.md)：把六项训练能力（站立抗扰、推倒恢复、起身、行走、1 cm 越障、坐／站）逐项列出策略、实测数字与产出它的内部工具。所有数字逐条抄自 2026-09-16 的测量日志，没有外推。
- Recorded the measured results: push threshold **40.5 N** (40 N topples 45.3 %, 0 to 24 N topples nothing) and 40 s steady-state drift **0.00 mm/s**; knock-down → get-up → nominal stance **5/5** end-to-end, with "did not fall again after standing up" **4/5**; get-up standing at the end **64/64** while the strict nominal criterion remains **0/64**; 1 cm terrain survival **51/64 (79.7 %)** at **61 %** of the commanded speed. / 记录实测结果：抗推临界 **40.5 N**（40 N 时倒 45.3 %，0–24 N 全不倒）与 40 s 稳态漂移 **0.00 mm/s**；推倒→起身→标称站姿端到端 **5/5**，"起身后没有再次摔倒" **4/5**；起身末态站住 **64/64**，而严格标称口径仍是 **0/64**；1 cm 地形存活 **51/64（79.7 %）**，平均速度是指令的 **61 %**。
- Documented the negative results with the same weight as the positive ones: side-stepping answers a +0.30 m/s command with +0.218 m/s plus **+520.4 deg** of uncommanded yaw, in-place turning produces **+0.3 deg** in 10 s, and the shipped walking checkpoint was trained under a command range that makes it incomparable with the newest table. / 负面结果与正面结果同等写入：侧移对 +0.30 m/s 的指令只回 **+0.218 m/s** 并伴随 **+520.4°** 的未指令自转，原地转 10 s 只转 **+0.3°**，且已 SHIP 的行走检查点训练时用的命令范围与最新一张表不可比。
- Documented how "standing" is judged: tilt below 8 degrees, both soles in contact, every joint within 20 degrees of nominal, base height above 0.15 m, plus a duration rule that the criterion hold for at least **90 % of the last 1.0 s**. On the same final states, demanding all 50 steps gives 20/64 where the final frame alone gives 63 to 64/64. The get-up delivery criterion adds two axes: the head chain must not press the ground (below 2 N) and the soles must be flat (within 5 degrees). / 写明"站稳"的判定口径：倾角 < 8°、双脚着地、每关节偏差 < 20°、基座高度 > 0.15 m，外加"末 1.0 s 里至少 **90 %** 的时刻成立"的持续规则。同一批末态下，要求 50 步全部合格给 20/64，只看末帧给 63–64/64。起身交付口径另加两条：头链不压地（低于 2 N）与双脚平贴（偏差 < 5°）。
- Recorded two structural facts with their evidence: the head chain is **1.654 kg = 44.1 %** of the published model's 3.751 kg, and the maximum static gravity torque about `neck_pitch` is **1.61 N·m** in the training model (**1.574 N·m** recomputed on the published URDF). The published URDF is unaffected — its effort column keeps the rated 0.6 N·m and declares no actuators. / 记录两条带证据的结构性事实：头链占公开模型 3.751 kg 中的 **1.654 kg = 44.1 %**；绕 `neck_pitch` 轴的最大静态重力矩在训练模型上是 **1.61 N·m**（在公开 URDF 上重算为 **1.574 N·m**）。公开 URDF 不受影响：其 effort 列仍保留额定的 0.6 N·m 且不声明任何执行器。
- Updated both READMEs (Development progress and At a glance, each linking the new page), the [roadmap](docs/roadmap.md) with a measured known-gaps section, and this changelog. / 更新中英文首页（开发进度与模型概览两节，并链接新页面）、[路线图](docs/roadmap.md)（新增"已知不足（已实测）"一节）与本更新记录。

### 2026-09-14 — Printable standing fixture and reproduction index / 站姿打印工装与复现入口

- Curated the maintainer's updated P01 and matching H2D project into [standing-zero](hardware/fixtures/standing-zero/README.md): four STEP solids, four millimeter STL files, and a two-plate PLA 3MF with each part required once. / 将维护者优化后的 P01 与匹配 H2D 工程整理到[站姿工装目录](hardware/fixtures/standing-zero/README.zh-CN.md)：四个 STEP 实体、四个毫米 STL、各件一份的双盘 PLA 3MF。
- Added part quantities, six M3 screw specifications, 0.4 mm total fit clearance, assembly/calibration instructions, current CAD/mesh checks, and hashes. Preserved the user's slicer settings and local native master files. Physical fit and repeatability remain unmeasured. / 补充数量表、六颗 M3 螺钉规格、0.4 mm 总配合间隙、装配标定方法及新版 CAD／网格检查和哈希；保留用户切片设置与本地原生工作文件，实物配合及重复定位精度待测。
- Classified 20 robot STEP models into 15 structural types and five purchased-component reference types. Distinguished print geometry from meter-based URDF visualization meshes. / 将 20 个机器人 STEP 模型分为 15 类结构几何与五类采购件参考，区分打印几何与米制 URDF 显示网格。
- Integrated the separate task's [160 mm static A1 mini model](hardware/printable/README.md), print project, generation scripts, and portable slicing report into the print index. / 将另一任务完成的 [160 mm A1 mini 固定展示模型](hardware/printable/README.md)、打印工程、生成脚本和可移植切片报告纳入打印入口。
- Retained the existing MATLAB implementation and trajectory data; clarified its smoke-test scope and distinguished CSV-computed values from unpublished planner reports and physical measurements. / 保留原 MATLAB 实现与轨迹数据，说明快速自检的范围，并区分 CSV 可复核数值、未公开规划器报告与实物测量。

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
