# Component inventory / 组件清单

[English home](../README.md) · [中文首页](../README.zh-CN.md)

This is a count of instances in the simplified model, **not a procurement or manufacturing BOM**. There are 40 modeled instances using 20 unique part geometries. Fasteners, cables, connectors, inserts, and unmodeled parts must be inventoried separately. / 这是简化模型中的实例数量，**不是采购或制造 BOM**：共 40 个实例、20 种零件几何。紧固件、线束、连接器、嵌件及未建模零件仍需单独盘点。

Counts are derived from [component_mass_audit.csv](../models/wmduck/component_mass_audit.csv). The linked STEP files and identically named native part files describe the same named components; this does not establish manufacturing readiness. / 数量来自 [component_mass_audit.csv](../models/wmduck/component_mass_audit.csv)。下表 STEP 与同名原生零件对应同一命名组件，不代表已经具备制造条件。

The machine-readable [STEP classification](../hardware/robot-structure.csv) identifies 15 robot-structure geometry classes and 5 purchased/reference classes (`Motor_HTDW3532`, `Bearing_20_27_4`, `Battery_6s18650_24V`, `Control_Borad_AT32`, and `IMU_YB-MRA02`). This classification describes the role of each model, not its manufacturing process. Modeled instances are not printable-part splits: a single model such as `Body_Frame` may contain multiple bodies, while several assembly instances may reuse one geometry. CAD material labels are source-model metadata, not manufacturing requirements. / 机器可读的 [STEP 分类表](../hardware/robot-structure.csv)标出 15 类机器人结构几何与 5 类外购／参考几何（`Motor_HTDW3532`、`Bearing_20_27_4`、`Battery_6s18650_24V`、`Control_Borad_AT32`、`IMU_YB-MRA02`）。该分类描述模型用途，不代表制造工艺。建模实例数不等于打印分体数：`Body_Frame` 这类单个模型可能包含多个实体，而装配中的多个实例也可能复用同一几何。CAD 材料标签属于源模型元数据，不是制造要求。

| STEP file / STEP 文件 | Description / 说明 | Instances / 实例数 | Modeled link(s) / 所属模型刚体 |
| --- | --- | ---: | --- |
| [Battery_6s18650_24V.stp](../hardware/step/Battery_6s18650_24V.stp) | Battery envelope / 电池包外形 | 1 | `base_link` |
| [Bearing_20_27_4.stp](../hardware/step/Bearing_20_27_4.stp) | Bearing geometry / 轴承几何 | 2 | `neck_pitch_link` |
| [Body_Frame.stp](../hardware/step/Body_Frame.stp) | Body frame / 躯干框架 | 1 | `base_link` |
| [Control_Borad_AT32.stp](../hardware/step/Control_Borad_AT32.stp) | Control-board envelope / 控制板外形 | 1 | `base_link` |
| [Head.stp](../hardware/step/Head.stp) | Head / 头部 | 1 | `head_roll_link` |
| [Head_pitch.stp](../hardware/step/Head_pitch.stp) | Head pitch part / 头部俯仰构件 | 1 | `head_pitch_link` |
| [IMU_YB-MRA02.stp](../hardware/step/IMU_YB-MRA02.stp) | IMU envelope / IMU 外形 | 1 | `base_link` |
| [Left_feet.stp](../hardware/step/Left_feet.stp) | Left foot / 左脚 | 1 | `left_ankle_link` |
| [Left_hip_roll.stp](../hardware/step/Left_hip_roll.stp) | Left hip roll part / 左髋侧摆构件 | 1 | `left_hip_roll_link` |
| [Left_knee.stp](../hardware/step/Left_knee.stp) | Left knee part / 左膝构件 | 1 | `left_knee_link` |
| [Motor_HTDW3532.stp](../hardware/step/Motor_HTDW3532.stp) | Motor envelope / 电机外形 | 15 | Distributed across the robot / 分布于整机 |
| [Mouth.stp](../hardware/step/Mouth.stp) | Beak / 嘴部 | 1 | `mouth_link` |
| [Right_feet.stp](../hardware/step/Right_feet.stp) | Right foot / 右脚 | 1 | `right_ankle_link` |
| [Right_hip_roll.stp](../hardware/step/Right_hip_roll.stp) | Right hip roll part / 右髋侧摆构件 | 1 | `right_hip_roll_link` |
| [Right_knee.stp](../hardware/step/Right_knee.stp) | Right knee part / 右膝构件 | 1 | `right_knee_link` |
| [WMD1005.stp](../hardware/step/WMD1005.stp) | Numbered structural part / 编号结构件 | 3 | `head_yaw_link`, `left_hip_yaw_link`, `right_hip_yaw_link` |
| [WMD1007.stp](../hardware/step/WMD1007.stp) | Numbered structural part / 编号结构件 | 3 | `left_hip_pitch_link`, `neck_pitch_link`, `right_hip_pitch_link` |
| [WMD1008.stp](../hardware/step/WMD1008.stp) | Numbered structural part / 编号结构件 | 2 | `left_hip_pitch_link`, `right_hip_pitch_link` |
| [WMD1012.stp](../hardware/step/WMD1012.stp) | Numbered structural part / 编号结构件 | 1 | `neck_pitch_link` |
| [WMD1018.stp](../hardware/step/WMD1018.stp) | Numbered structural part / 编号结构件 | 1 | `head_roll_link` |

**Total / 合计：40 instances / 个实例。**

A part assigned to a link moves rigidly with that link. The table does not identify motor IDs, encoder wiring, or procurement quantities for a complete robot. / 某零件归属于一个 link，表示它与该刚体一起运动；此表不定义电机 ID、编码器接线，也不代表完整机器人的采购数量。

## Printable calibration fixture / 可打印标定工装

The [standing-zero fixture](../hardware/fixtures/standing-zero/README.md) is a separate manufacturing package and is not part of the 40 robot-model instances above. Print one each of its four millimetre-scale STL files: main frame, head cradle, combined head keeper/mouth stop, and Body bridge. Four matching STEP files provide editable exchange geometry. The user-supplied Bambu H2D 3MF places the four parts on two plates, and assembly uses six M3 screws. The package does not claim a completed physical print or measured repeatability. / [站姿零点工装](../hardware/fixtures/standing-zero/README.zh-CN.md)是独立制造包，不属于上面的 40 个机器人模型实例。其 4 个毫米单位 STL——主框架、头托、头部前挡／嘴托组合件和 Body 横梁——每种打印 1 件；另有 4 个对应 STEP 用于编辑交换。用户提供的 Bambu H2D 3MF 将四件排在两个打印盘上，装配使用 6 颗 M3 螺钉。本包不宣称已经完成实物打印或实测重复定位验证。

## Before making a purchasing BOM / 转为采购 BOM 前

- Confirm exact supplier part numbers and mechanical/electrical compatibility. File names are identifiers, not purchasing specifications. / 确认供应商完整型号及机械／电气兼容性；文件名是标识，不是采购规格。
- Add omitted hardware and record quantities, material/finish, alternatives, and revision. / 补齐未建模配件，记录数量、材料／表面处理、替代项及版本。
- Separate purchased components from parts to fabricate, then verify dimensions and assembly fits. / 区分外购部件与需要加工的零件，再核对尺寸与装配配合。
- Reconcile CAD masses with measured values. The head is currently assigned aluminum, the battery resin, and the IMU zero mass. / 用实测值核对 CAD 质量；当前头部使用铝合金材料、电池使用树脂材料，IMU 质量为零。

See the [English model guide](model.en.md) / [中文模型指南](model.zh-CN.md) for the mass assumptions and [roadmap](roadmap.md) for build documentation work. / 质量假设见模型指南，搭建资料的后续工作见路线图。
