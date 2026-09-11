# Wamoduck robot description / 机器人描述

[English model guide](../../docs/model.en.md) · [中文模型指南](../../docs/model.zh-CN.md)

Open [`wmduck.urdf`](wmduck.urdf) with its [`meshes/`](meshes/) folder present. This package has 15 revolute joints, 1 fixed joint, and 20 meter-scale STL files. / 打开 [`wmduck.urdf`](wmduck.urdf) 时请保留配套 [`meshes/`](meshes/) 文件夹；本包包含 15 个转动关节、1 个固定关节和 20 个米制 STL。

| File / 文件 | Purpose / 用途 |
| --- | --- |
| [wmduck.urdf](wmduck.urdf) | Main model / 主模型 |
| [joint_parameters.json](joint_parameters.json) | Joint assumptions; editing this file alone does not update the URDF / 关节参数记录，单独修改不会更新 URDF |
| [joint_limits.csv](joint_limits.csv) | Geometric range estimates and their basis / 几何限位估计与依据 |
| [motor_parameters.json](motor_parameters.json) | Transcribed motor assumptions / 电机参数记录 |
| [component_mass_audit.csv](component_mass_audit.csv) | Modeled instance masses and sources / 模型实例质量与来源 |
| [validation.json](validation.json) | Current package structural and import checks / 当前资料包结构与导入检查 |

This is a model for inspection and development. It does not include a controller, actuators, a ground scene, or training code. / 这是用于查看与开发的模型，不含控制器、执行器定义、地面场景或训练代码。
