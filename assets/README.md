# Visual assets / 图像与动图

[English home](../README.md) · [中文首页](../README.zh-CN.md)

| Asset / 文件 | Contents / 内容 |
| --- | --- |
| [Brand logo](branding/wamotech-symbol-black.png) · [White version](branding/wamotech-symbol-white.png) | Maintainer-supplied Wamotech symbol, copied unchanged / 维护者提供的望默科技图形标志，原样复制 |
| [Wordmark](branding/wamotech-wordmark-black.png) · [White version](branding/wamotech-wordmark-white.png) | WAMOTECH wordmark paired with the symbol in both README headers / 与图形标志配套展示在中英文首页的 WAMOTECH 字标 |
| [wamoduck-motion.gif](wamoduck-motion.gif) | Animated joint-motion preview rendered from the public URDF / 由公开 URDF 渲染的关节运动演示 |
| [wamoduck-gait-preview.gif](wamoduck-gait-preview.gif) | Reference walking gait, two cycles, rendered from the public URDF / 参考行走步态（两个周期），由公开 URDF 渲染 |
| [wamoduck-gait-walk.mp4](wamoduck-gait-walk.mp4) | The same gait, 20 s of continuous walking with the body position shown / 同一步态，连续行走 20 s 并标出机体位置 |
| [wamoduck-gait-still.png](wamoduck-gait-still.png) | Single frame of the reference gait / 参考步态的单帧静图 |
| [wamoduck-matlab-player.png](wamoduck-matlab-player.png) | Screenshot of the bundled MATLAB player / 随仓库附带的 MATLAB 回放器截图 |
| [wamoduck-dof-overview.png](wamoduck-dof-overview.png) | Four-view joint-origin overview from the finalized URDF export / 最终 URDF 导出的四视图关节原点总览 |
| [wamoduck-model.png](wamoduck-model.png) | Original static model rendering at the saved pose / 原有保存姿态下的静态模型渲染 |
| [media-manifest.json](media-manifest.json) | Provenance, hashes, and animation properties for the added media / 新增图像的来源、哈希与动图属性 |

## Motion preview / 运动演示

The animation uses the geometry and joint definitions in [wmduck.urdf](../models/wmduck/wmduck.urdf). Preset joint angles are applied and rendered with MuJoCo forward kinematics. It demonstrates the articulated model, including both legs and the neck/head/beak chain; the movements are not produced by a trained ONNX policy or a physical robot. / 动图使用 [wmduck.urdf](../models/wmduck/wmduck.urdf) 的几何与关节定义，设置预定关节角并通过 MuJoCo 前向运动学渲染，展示双腿以及颈部、头部、嘴部的结构运动；动作并非由训练后的 ONNX 策略或实物机器人产生。

All animated joint values remain within the supplied URDF ranges. This is a visualization check, not a dynamic balance or collision-clearance test. Presentation changes such as lighting and camera settings do not change the published CAD or URDF. / 动画关节值保持在所附 URDF 范围内；这属于可视化检查，不是动态平衡或碰撞间隙验证。灯光、相机等展示设置不改变公开 CAD 或 URDF。

## Reference gait / 参考步态

[wamoduck-gait-preview.gif](wamoduck-gait-preview.gif) and [wamoduck-gait-walk.mp4](wamoduck-gait-walk.mp4) replay the **reference quasi-static gait** supplied in [tools/matlab/data/](../tools/matlab/data/): the same URDF, the same method as the joint-motion preview — prescribed joint angles plus MuJoCo forward kinematics, with the body pose from the data file. The GIF covers two whole cycles (the ground tick spacing equals one cycle's 2 cm of travel, so the loop is seamless). / [wamoduck-gait-preview.gif](wamoduck-gait-preview.gif) 与 [wamoduck-gait-walk.mp4](wamoduck-gait-walk.mp4) 回放的是 [tools/matlab/data/](../tools/matlab/data/) 里的**参考准静态步态**：同一个 URDF、与关节运动演示相同的方法（给定关节角 + MuJoCo 前向运动学），机体位姿取自数据文件。GIF 覆盖两个整周期（地面刻度间距等于一个周期的 2 cm 前进量，因此循环无缝）。

The gait is an inverse-kinematics plan with a static-stability check: 1 cm per step, 1 cm/s, 4.5 mm foot lift, peak inverse-dynamics torque 2.53 N·m. It is **not** a trained policy, **not** hardware footage, and **not** a dynamic-balance result; the scripted-motion note above applies in full. / 该步态是带静态稳定性检查的逆运动学规划：每步 1 cm、1 cm/s、抬脚 4.5 mm、逆动力学峰值力矩 2.53 N·m。它**不是**训练策略、**不是**实物拍摄、**也**不是动态平衡结果；上面关于"预定动作"的说明完全适用。

[wamoduck-matlab-player.png](wamoduck-matlab-player.png) is a screenshot of [tools/matlab/wamoduck_play.m](../tools/matlab/wamoduck_play.m) playing the same data set. See the [gait guide](../docs/matlab.en.md) / [步态指南](../docs/matlab.zh-CN.md) for the measured numbers and the known limits. / [wamoduck-matlab-player.png](wamoduck-matlab-player.png) 是 [tools/matlab/wamoduck_play.m](../tools/matlab/wamoduck_play.m) 回放同一份数据的截图。实测数据与已知限制见[步态指南](../docs/matlab.zh-CN.md)。

## DOF overview / 自由度总览

The overview is copied unchanged from the finalized model's `coordinate_frames/00_overview.png`. It shows front, right, top, and isometric orthographic views at the saved CAD pose (`q=0`). Labels 01–15 are diagram indices, not motor IDs. / 总览图原样取自最终模型的 `coordinate_frames/00_overview.png`，包含 CAD 保存姿态（`q=0`）下的正视、右侧视、俯视与等轴正投影视图。01–15 是图册索引，不是电机 ID。

The 15 joint definitions in the public URDF match the finalized export. Current joint ranges were retained; their confirmation does not imply a new measurement of physical stops or encoder offsets. See the [English model guide](../docs/model.en.md) / [中文模型指南](../docs/model.zh-CN.md). / 公开 URDF 的 15 个转动关节定义与最终导出一致，沿用已确认的关节范围；确认模型参数不代表重新实测了机械挡位或编码器零偏，详见模型指南。
