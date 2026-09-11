# Roadmap / 路线图

[English home](../README.md) · [中文首页](../README.zh-CN.md)

Status of this package, 2026-09-12. These are deliverables and acceptance criteria, not promised release dates. / 本资料包状态，2026-09-12。以下是交付目标与验收条件，不代表发布日期承诺。

| Area / 方向 | Current state / 当前状态 | Next deliverable / 下一步交付 |
| --- | --- | --- |
| Mechanical sharing / 机械分享 | Included: simplified STEP and native SolidWorks files / 已包含简化 STEP 与原生 SolidWorks 文件 | Open on a separate machine, resolve all references, and record CAD version / 在独立机器打开、确认引用完整并记录 CAD 版本 |
| Robot description / 机器人描述 | Included: URDF, meshes, joint data, structural/import checks / 已包含 URDF、网格、关节数据与结构／导入检查 | Compare joint directions, zero offsets, masses, and inertias with measured hardware / 对照实物核对关节方向、零偏、质量和惯量 |
| Component list / 组件清单 | Included: counts of modeled instances / 已包含模型实例数量 | Verified purchasing BOM with specifications, quantities, alternatives, and source dates / 完整核对的采购 BOM，含规格、数量、替代项与来源日期 |
| Manufacturing / 加工制造 | Not included / 尚未提供 | Fabricated-part list, manufacturing exports, materials, tolerances, and tested print settings / 待加工零件清单、制造导出、材料、公差和实测打印设置 |
| Assembly / 装配 | Not included / 尚未提供 | Illustrated steps by subassembly, fasteners, inserts, tools, and inspection points / 按子装配编写图文步骤、紧固件、嵌件、工具和检查点 |
| Electronics / 电子系统 | Component geometry only / 仅提供部件几何 | Wiring diagrams, connector pinouts, power design, and confirmed board revisions / 接线图、接口定义、电源设计及确定的板卡版本 |
| Firmware and calibration / 固件与标定 | Not included / 尚未提供 | Firmware source, supported hardware, motor ID mapping, encoder offsets, and startup procedure / 固件源码、支持硬件、电机 ID 对照、编码器零偏与启动流程 |
| Simulation / 仿真 | Model import only; no locomotion environment / 仅模型导入，无行走环境 | Collision simplification, actuators, floating-base scene, contact settings, and reproducible checks / 简化碰撞体、执行器、浮动基座场景、接触参数与可复现检查 |
| Walking and training / 行走与训练 | Not included / 尚未提供 | Reproducible controller or training configuration with dated validation evidence / 可复现控制器或训练配置及带日期的验证记录 |

## Suggested milestones / 建议阶段

1. **Mechanical reference package / 机械参考资料包** — this package, followed by independent CAD opening checks. / 当前资料包，随后完成独立 CAD 打开检查。
2. **Reproducible physical build / 可复现的实物搭建** — complete the BOM, manufacturing, assembly, and electrical documentation together. / 配套补齐 BOM、制造、装配及电气文档。
3. **Measured robot model / 经实测修正的机器人模型** — calibrate geometry and dynamics, then validate the simulation scene. / 标定几何和动力学参数，再验证仿真场景。
4. **Reproducible motion / 可复现的运动控制** — publish control or training software with hardware versions and test conditions. / 发布控制或训练软件，并记录硬件版本与测试条件。

Document new claims together with their evidence. A successful model import establishes that the file can be compiled; it does not establish walking performance or hardware reproducibility. / 新增结论应附带对应证据。模型成功导入只证明文件可编译，不代表行走性能或实物复现已经验证。
