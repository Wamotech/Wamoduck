# Roadmap / 路线图

[English home](../README.md) · [中文首页](../README.zh-CN.md)

Status as of 2026-09-14. The project is in mechanical prototyping and hardware/software integration. The repository now includes reference-gait CSV data and a MATLAB player, plus a four-part standing calibration fixture with an H2D PLA project. The project's full MuJoCo environment and ONNX deployment software remain outside this repository. / 截至 2026-09-14，项目处于结构打样和软硬件联合调试阶段；仓库已包含参考步态 CSV 与 MATLAB 回放器，并整理了四件式站姿标定工装及 H2D PLA 工程。项目完整 MuJoCo 环境和 ONNX 部署软件尚未包含在本仓库。

The table below tracks **public repository deliverables**, not all development work. Simulation code, policy files, and integration evidence will be added as the project progresses. These are deliverables and acceptance criteria, not promised release dates. / 下表跟踪的是**公开仓库交付内容**，不代表项目全部研发工作的状态。仿真代码、策略文件及联调记录将随着项目进展逐步补充，以下目标与验收条件不代表发布日期承诺。

| Area / 方向 | Current state / 当前状态 | Next deliverable / 下一步交付 |
| --- | --- | --- |
| Mechanical sharing / 机械分享 | Included: simplified STEP and native SolidWorks files / 已包含简化 STEP 与原生 SolidWorks 文件 | Open on a separate machine, resolve all references, and record CAD version / 在独立机器打开、确认引用完整并记录 CAD 版本 |
| Robot description / 机器人描述 | Included: URDF, meshes, joint data, structural/import checks / 已包含 URDF、网格、关节数据与结构／导入检查 | Compare joint directions, zero offsets, masses, and inertias with measured hardware / 对照实物核对关节方向、零偏、质量和惯量 |
| Component list / 组件清单 | Included: counts of modeled instances / 已包含模型实例数量 | Verified purchasing BOM with specifications, quantities, alternatives, and source dates / 完整核对的采购 BOM，含规格、数量、替代项与来源日期 |
| Manufacturing / 加工制造 | [Standing fixture](../hardware/fixtures/standing-zero/README.md): 4 STEP, 4 STL, H2D PLA project; robot STEP roles classified / [站姿工装](../hardware/fixtures/standing-zero/README.zh-CN.md)含四份 STEP、四份 STL 与 H2D PLA 工程；机器人 STEP 已分类 | First-print fixture fit and repeatability; confirmed robot fabrication materials, tolerances, and tested processes / 工装首件配合与重复定位实测；机器人制造材料、公差与工艺核对 |
| Assembly / 装配 | Fixture sequence and six M3 screws documented / 已说明工装装配顺序及六颗 M3 螺钉 | Complete robot subassembly steps, fasteners, tools, and inspection points / 整机子装配图文步骤、紧固件、工具和检查点 |
| Electronics / 电子系统 | Component geometry only / 仅提供部件几何 | Wiring diagrams, connector pinouts, power design, and confirmed board revisions / 接线图、接口定义、电源设计及确定的板卡版本 |
| Firmware and calibration / 固件与标定 | Manual standing-fixture method included; firmware not included / 已提供站姿工装手动标定方法，尚无固件 | Firmware, motor-ID/sign mapping, offset storage procedure, and measured calibration repeatability / 固件、电机 ID／转向映射、零偏保存流程及重复标定实测 |
| Simulation / 仿真 | Public package includes URDF import checks and a scripted joint-motion GIF; the project's full simulation environment is not yet published / 公开包包含 URDF 导入检查与预设关节动作 GIF，项目完整仿真环境尚未公开 | Publish the simulation environment, collision setup, actuators, scene, and reproducible validation / 公开仿真环境、碰撞配置、执行器、场景与可复现验证 |
| Walking and training / 行走与训练 | Reference CSV trajectory and MATLAB playback/self-test included / 已包含参考轨迹 CSV 与 MATLAB 回放、自检 | Publish the trajectory generator and controller/training configuration with validation evidence / 公开轨迹生成器及控制器／训练配置和验证记录 |

## Suggested milestones / 建议阶段

1. **Mechanical reference package / 机械参考资料包** — this package, followed by independent CAD opening checks. / 当前资料包，随后完成独立 CAD 打开检查。
2. **Reproducible physical build / 可复现的实物搭建** — complete the BOM, manufacturing, assembly, and electrical documentation together. / 配套补齐 BOM、制造、装配及电气文档。
3. **Measured robot model and reproducible simulation / 经实测修正的模型与可复现仿真** — reconcile the model with hardware measurements and publish the simulation environment and validation. / 用实测数据校准模型，公开仿真环境及验证记录。
4. **Reproducible motion / 可复现的运动控制** — publish control or training software with hardware versions and test conditions. / 发布控制或训练软件，并记录硬件版本与测试条件。

Document new claims together with their evidence. A successful model import establishes that the file can be compiled; it does not establish walking performance or hardware reproducibility. / 新增结论应附带对应证据。模型成功导入只证明文件可编译，不代表行走性能或实物复现已经验证。
