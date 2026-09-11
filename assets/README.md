# Visual assets / 图像与动图

[English home](../README.md) · [中文首页](../README.zh-CN.md)

| Asset / 文件 | Contents / 内容 |
| --- | --- |
| [wamoduck-motion.gif](wamoduck-motion.gif) | Animated joint-motion preview rendered from the public URDF / 由公开 URDF 渲染的关节运动演示 |
| [wamoduck-dof-overview.png](wamoduck-dof-overview.png) | Four-view joint-origin overview from the finalized URDF export / 最终 URDF 导出的四视图关节原点总览 |
| [wamoduck-model.png](wamoduck-model.png) | Original static model rendering at the saved pose / 原有保存姿态下的静态模型渲染 |
| [media-manifest.json](media-manifest.json) | Provenance, hashes, and animation properties for the added media / 新增图像的来源、哈希与动图属性 |

## Motion preview / 运动演示

The animation uses the geometry and joint definitions in [wmduck.urdf](../models/wmduck/wmduck.urdf). Preset joint angles are applied and rendered with MuJoCo forward kinematics. It demonstrates the articulated model, including both legs and the neck/head/beak chain; the movements are not produced by a trained ONNX policy or a physical robot. / 动图使用 [wmduck.urdf](../models/wmduck/wmduck.urdf) 的几何与关节定义，设置预定关节角并通过 MuJoCo 前向运动学渲染，展示双腿以及颈部、头部、嘴部的结构运动；动作并非由训练后的 ONNX 策略或实物机器人产生。

All animated joint values remain within the supplied URDF ranges. This is a visualization check, not a dynamic balance or collision-clearance test. Presentation changes such as lighting and camera settings do not change the published CAD or URDF. / 动画关节值保持在所附 URDF 范围内；这属于可视化检查，不是动态平衡或碰撞间隙验证。灯光、相机等展示设置不改变公开 CAD 或 URDF。

## DOF overview / 自由度总览

The overview is copied unchanged from the finalized model's `coordinate_frames/00_overview.png`. It shows front, right, top, and isometric orthographic views at the saved CAD pose (`q=0`). Labels 01–15 are diagram indices, not motor IDs. / 总览图原样取自最终模型的 `coordinate_frames/00_overview.png`，包含 CAD 保存姿态（`q=0`）下的正视、右侧视、俯视与等轴正投影视图。01–15 是图册索引，不是电机 ID。

The 15 joint definitions in the public URDF match the finalized export. Current joint ranges were retained; their confirmation does not imply a new measurement of physical stops or encoder offsets. See the [English model guide](../docs/model.en.md) / [中文模型指南](../docs/model.zh-CN.md). / 公开 URDF 的 15 个转动关节定义与最终导出一致，沿用已确认的关节范围；确认模型参数不代表重新实测了机械挡位或编码器零偏，详见模型指南。
