# Wamoduck

**Wamotech 的 15 自由度鸭子机器人。**

[English](README.md) | 简体中文

![Wamoduck 在 CAD 保存姿态下的机器人模型](assets/wamoduck-model.png)

*图片来自 Wamoduck URDF 模型渲染，并非实物照片。*

Wamoduck 是一个鸭子外形的双足机器人项目，用于探索机械设计、关节运动与机器人建模。全身包含 15 个转动自由度：左右腿各 5 个，颈部、头部和嘴部运动链共 5 个。

本次初版资料提供简化机械设计和机器人描述模型，方便查看、研究与进一步开发。完整搭建教程、电子系统、固件和行走控制器仍待整理或发布。

## 从这里开始

| 你想做什么 | 对应入口 |
| --- | --- |
| 查看或修改单个机械零件 | [20 个 STEP 模型](hardware/step/) · [机械文件指南](docs/mechanical.zh-CN.md) |
| 查看原生装配关系 | [SolidWorks 文件](hardware/solidworks/) · [打开方法](docs/mechanical.zh-CN.md#solidworks-装配体) |
| 查看整机和关节运动 | [URDF 与网格](models/wmduck/) · [模型指南](docs/model.zh-CN.md) |
| 了解模型中包含的部件 | [组件清单](docs/components.md) |
| 参与改进项目 | [贡献指南](CONTRIBUTING.md) · [路线图](docs/roadmap.md) |

打开装配体或 URDF 前，请下载或克隆整个仓库；这些文件需要配套的零件或网格文件。

## 模型概览

| 项目 | 当前模型 |
| --- | --- |
| 转动关节 | 15 个：左腿 5 + 右腿 5 + 颈部／头部／嘴部 5 |
| 机器人描述 | URDF；16 个机械刚体 link + 1 个固定 IMU 参考 link |
| 几何文件 | 20 个简化 STEP 零件模型；20 个 URDF 用 STL 网格 |
| 保存姿态下的模型近似包络 | 181.5 × 221.2 × 390.8 mm（X × Y × Z） |
| 模型估算质量 | 3.886 kg；基于 CAD 并修正电机质量，并非整机实测重量 |
| 模型单位 | m、kg、rad；STEP 文件声明的长度单位为 mm |

质量和包络描述的是所附模型，并非经过实物验证的规格。使用惯量、电机参数或关节范围前，请先阅读[模型假设](docs/model.zh-CN.md)。

## 本次包含什么

```text
Wamoduck/
├── hardware/
│   ├── step/             # 独立的简化零件，毫米单位
│   └── solidworks/       # 简化原生零件与装配体
├── models/wmduck/        # URDF、网格、关节数据与导入检查
├── assets/              # 模型预览图
├── docs/                # 中英文机械和模型指南
├── CONTRIBUTING.md
└── LICENSE
```

STEP 用于跨软件交换几何。STL 用于机器人显示与初步碰撞建模，**不是一套经过验证的可打印零件**。关节限位来自单关节几何检查，不能保证多个关节同时运动时不发生碰撞。

要完成实物复现，还需补齐经过核对的采购 BOM、制造要求、装配步骤、接线、标定及控制软件。[路线图](docs/roadmap.md)列出了这些待完善内容。

## 参考项目与许可证

文档组织参考了 [Open Duck Mini](https://github.com/apirrone/Open_Duck_Mini) 和 [Pollen Robotics Microduck](https://github.com/pollen-robotics/microduck)：提供清晰的设计文件入口、说明模型假设，并分别组织搭建、运行和训练资料。具体来源与区别见[参考说明](docs/references.md)。

仓库保留现有 [MIT 许可证](LICENSE)，版权归属 © 2026 Wamotech。参考项目与第三方部件保留各自的许可证及相关权利；不应假定它们的尺寸、控制器或搭建教程可直接用于 Wamoduck。
