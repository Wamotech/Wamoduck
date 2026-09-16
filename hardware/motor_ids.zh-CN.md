# CAN-FD 总线上的电机 ID

[中文首页](../README.zh-CN.md) · [English](motor_ids.md) | 简体中文 · [模型指南](../docs/model.zh-CN.md) · [仿真指南](../docs/simulation.zh-CN.md)

![Wamoduck 上各电机 ID 的位置，两个 CAD 视图](../assets/wamoduck-motor-ids.png)

*同一台机器人的两个 CAD 视图，每个电机旁边标着它的总线 ID，腿部下方写着 `Left` / `Right`。*

本页是**硬件与接口信息**，仅此而已。它记录哪个总线 ID 对应哪个关节、那个电机挂在哪一条 CAN-FD 总线上，以及策略输出的 14 个值如何对应到这些 ID 上。它不涉及策略能否站起来或走起来：本仓库里的所有结果都是仿真结果，也没有任何一个策略在实物机器人上测过。

## 本目录包含什么

| 文件 | 内容 |
| --- | --- |
| [motor_ids.csv](motor_ids.csv) | 映射表，每个电机一行 |
| [motor_ids.json](motor_ids.json) | 同样内容，机器可读 |
| [../assets/wamoduck-motor-ids.png](../assets/wamoduck-motor-ids.png) | 上面那张位置图 |

源工作簿 `List_MotorID_CANFD.xlsx` 与源幻灯片 `Motor_ID_location.pptx` **不随本仓库分发**。这里只公开派生出来的表格与导出的位置图。

## 三路 CAN-FD 总线

- **AT32** 主控板走**三路物理 CAN-FD 总线**，每路都用 **XT30(2+2)** 端子。该端子把电源与 CAN-FD 一起承载。
- 三路分别是**左下肢**一路、**右下肢**一路、**脖子及头部**一路。
- 每路挂 **5** 个电机，即 **3 × 5 = 15**，恰好等于源表的 **15** 行。总线划分与源表完全吻合。
- **三路总线共用一套 ID 空间，而单条总线上的 ID 不是连号。** 左下肢总线上的 ID 是 **1、3、5、7、9**；右下肢是 **2、4、6、8、10**；脖子及头部是 **11、12、13、14、15**。也就是说，左下肢总线**不**用 1、2、3、4、5。这一点很反直觉，接线时最先要弄对的就是它。
- 该 ID 分配由维护者于 **2026-09-16** 确认，它也正是源表把左右两侧交替编号的原因。

## 映射表

| 总线 | 总线 ID | 关节 | 中文名称 | 侧 | 在策略动作向量里 |
| --- | ---: | --- | --- | --- | --- |
| left_leg | 1 | `left_hip_yaw` | 左髋偏航 | left | 是 |
| left_leg | 3 | `left_hip_roll` | 左髋侧摆 | left | 是 |
| left_leg | 5 | `left_hip_pitch` | 左髋俯仰 | left | 是 |
| left_leg | 7 | `left_knee` | 左膝关节 | left | 是 |
| left_leg | 9 | `left_ankle` | 左踝关节 | left | 是 |
| right_leg | 2 | `right_hip_yaw` | 右髋偏航 | right | 是 |
| right_leg | 4 | `right_hip_roll` | 右髋侧摆 | right | 是 |
| right_leg | 6 | `right_hip_pitch` | 右髋俯仰 | right | 是 |
| right_leg | 8 | `right_knee` | 右膝关节 | right | 是 |
| right_leg | 10 | `right_ankle` | 右踝关节 | right | 是 |
| neck_head | 11 | `neck_pitch` | 颈俯仰 | center | 是 |
| neck_head | 12 | `head_pitch` | 头俯仰 | center | 是 |
| neck_head | 13 | `head_yaw` | 头偏航 | center | 是 |
| neck_head | 14 | `head_roll` | 头侧倾 | center | 是 |
| neck_head | 15 | `mouth` | 嘴开合 | center | **否** |

- 关节名取自 [wmduck.urdf](../models/wmduck/wmduck.urdf)。这 15 个名字已逐个与 URDF 核对过。
- **对源表的一处更正。** 源表把总线 2 上的关节拼成 `Rightt_hip_yaw`。那是拼写笔误：URDF 与 MJCF 都拼作 `right_hip_yaw`，这里用的也是这个拼法。[motor_ids.csv](motor_ids.csv) 的 `note` 字段记录了源表的原始拼写。
- **总线 ID 15 不由策略驱动。** 公开策略输出的是 **14** 个值而不是 15 个：它们没有嘴部这一轴。`mouth` 在 URDF 里是真实的转动关节、在脖子及头部总线上也是真实的电机，但它不在动作向量里，因此它的 `driven_by_policy` 为 `false`、`action_index` 为空。策略驱动的是总线 ID 1 到 14。总线 ID 15 作为一个备用自由度留给交互功能，这些功能**计划中、未实现** —— 计划内容以及模型今天的实际状况见[路线图](../docs/roadmap.md)。

## 两种顺序，以及它们之间的置换

本项目里有两种顺序，而且它们**并不相同**：

| 顺序 | 具体是什么，按序展开 |
| --- | --- |
| 总线 ID 顺序 | 1、2、3 …… 15 —— 左右交错（左髋偏航、右髋偏航、左髋侧摆……） |
| 关节树顺序 | 左腿 5 个、再右腿 5 个、再颈头 4 个 —— 策略实际驱动的 14 个关节 |

总线 ID 顺序就是 [robot_walk.xml](../models/wmduck/mjcf/robot_walk.xml) 里 `<actuator>` 块的顺序 —— 也就是这些公开策略训练时所用的 MJCF：`act_left_hip_yaw`、`act_right_hip_yaw`、`act_left_hip_roll`，依此类推。

但 14 维动作向量是按**关节树顺序**解读的：第 0 个元素是左髋偏航，第 4 个是左踝，第 5 个是右髋偏航，第 10 到 13 个是颈与头。这正是[仿真指南](../docs/simulation.zh-CN.md)写明的读法。

**因此固件与任何上位机程序都必须做一次置换**，从动作下标换到总线 ID：

```text
bus_id(action_index) = [1, 3, 5, 7, 9, 2, 4, 6, 8, 10, 11, 12, 13, 14]     # action index 0..13
```

读法是：`action[0]` 是左髋偏航，发往总线 ID 1；`action[1]` 是左髋侧摆，发往总线 ID 3；`action[2]` 是左髋俯仰，发往总线 ID 5；`action[3]` 是左膝，发往总线 ID 7；`action[4]` 是左踝，发往总线 ID 9；`action[5]` 是右髋偏航，发往总线 ID 2；依此类推。`action[10]` 到 `action[13]` 分别是颈俯仰、头俯仰、头偏航、头侧倾，原样发往总线 ID 11、12、13、14。

> ### ⚠️ 不要仅凭这个置换就给舵机上电
>
> **上面这个置换尚未在实机上验证过。** 在有独立证据之前，不要据此给舵机上电。关节顺序一旦接错就会错误驱动关节，而在本项目自己的仿真里，顺序接错会让机器人在一秒内瘫倒。
>
> 而且这件事**尚未裁决**。我们内部有一处部署契约文件把 14 维动作向量按**执行器顺序**而不是关节树顺序解读，本仓库的 ROS 2 模块 [`model_contract.py`](../ros2/wamoduck_ros2/wamoduck_ros2/model_contract.py) 也是同样的读法。按那种读法，`action[1]` 的目标是总线 ID 2，而本页把它发往总线 ID 3，因此对 `action[1]` 到 `action[8]` 这两种读法互相冲突。目前还没有人对这个分歧做出裁决。请把该置换当作一个有待与实机核对的假设，而不是接线指令。
>
> 三路总线的拓扑同样未在实机上验证：每一路的**方向与极性**、**终端电阻**、以及**舵机里实际烧录的 ID 分配**，都还没有在机器上核对过。

## 位置图的来源

- 来源是维护者的幻灯片 `Motor_ID_location.pptx`，全套共 1 页，本图是其中的第 1 页。
- 该幻灯片里只有**两张**内嵌 PNG 渲染图，没有别的图；这两张 CAD 视图本身并不带总线 ID。
- 1 到 15 的数字与 `Left` / `Right` 标签是叠在图片之上的独立文本框，因此"把这一页导出"才是标注的唯一忠实形式。该导出由 Microsoft PowerPoint 生成，尺寸为 **2400 × 1350** 像素，原样公开、未作修改。
- 这张图**不是**实物照片，也不能作为"这些电机已经接好线或被驱动过"的证据。

## 本页没有声称的东西

- 它没有声称机器人能用，也没有声称任何策略能站能走。它只是一张总线 ID 表。
- 它没有声称这些 ID 已经在实物线束上核对过。写这一页时没有开过任何 CAN 总线。
- 总线 ID、总线拓扑、关节名与顺序都是接口事实。请把它们与行为结果分开看 —— 后者在[实测能力清单](../docs/capabilities.zh-CN.md)上。

## 相关页面

- [模型指南](../docs/model.zh-CN.md) —— 关节名、轴向与限位。
- [仿真指南](../docs/simulation.zh-CN.md) —— 观测布局、关节树顺序与动作映射。
- [机械设计](README.md) —— STEP 与 SolidWorks 文件。
