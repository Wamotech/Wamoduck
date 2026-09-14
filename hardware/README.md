# Mechanical design / 机械设计

[English guide](../docs/mechanical.en.md) · [中文指南](../docs/mechanical.zh-CN.md)

[Static display prints / 固定展示打印模型](printable/README.md): a separate 160 mm A1 mini figurine, with fused joints and an integral base. / 独立的 160 mm A1 mini 摆件，关节固定并带一体底座。

- [step/](step/): 20 simplified millimetre STEP geometries: 15 robot-structure classes and 5 purchased/reference classes. See [robot-structure.csv](robot-structure.csv). / 20 类毫米单位 STEP 简化几何：15 类机器人结构几何与 5 类外购／参考几何，分类见 [robot-structure.csv](robot-structure.csv)。
- [solidworks/](solidworks/): 20 parts and 11 assemblies; start with `Full_wmduck.SLDASM`. / 20 个零件与 11 个装配体，入口为 `Full_wmduck.SLDASM`。
- [fixtures/standing-zero/](fixtures/standing-zero/): downloadable standing-zero calibration fixture with [English](fixtures/standing-zero/README.md) and [中文](fixtures/standing-zero/README.zh-CN.md) instructions. It contains four editable STEP files, four millimetre-scale print STL files, and a user-supplied Bambu H2D 3MF arranged on two plates. Print one of each part; assembly uses six M3 screws. / [站姿零点标定工装](fixtures/standing-zero/)提供[英文](fixtures/standing-zero/README.md)与[中文](fixtures/standing-zero/README.zh-CN.md)说明，包含 4 个可编辑 STEP、4 个毫米单位打印 STL，以及用户提供的双盘 Bambu H2D 3MF。每种零件打印 1 件，共使用 6 颗 M3 螺钉。

The 20 robot STEP/native files provide geometry and assembly references; their assembly instance counts do not define printable part splits. `Body_Frame` may import as multiple bodies, and CAD material labels are model metadata rather than manufacturing requirements. Manufacturing and clean-session native dependency validation for the robot are still pending. The zero fixture has passed the documented CAD/STL checks, but no physical print or repeatability test is claimed. / 这 20 类机器人 STEP／原生文件用于几何和装配参考；装配实例数量不等于打印分体数量。`Body_Frame` 导入后可能包含多个实体，CAD 材料标签属于模型元数据，不是制造要求。机器人制造要求及原生装配在独立会话中的依赖验证仍待补齐。零点工装已通过文档所列 CAD／STL 检查，但不宣称已经完成实物打印或重复定位测试。
