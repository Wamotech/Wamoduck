# Wamoduck MJCF / 训练用的 MuJoCo 模型

[English simulation guide](../../../docs/simulation.md) · [中文仿真指南](../../../docs/simulation.zh-CN.md) · [URDF package](../README.md)

These are the MuJoCo models the published policies were **trained in**, not exports or reconstructions. Load
them with the meshes that already ship in this repository at [`../meshes/`](../meshes/). / 这两个是公开策略**训练时
真正使用的** MuJoCo 模型，不是导出件或重建件。加载时使用本仓库已有的 [`../meshes/`](../meshes/) 网格。

| File / 文件 | Used by / 用于 | Notes / 说明 |
| --- | --- | --- |
| [robot_walk.xml](robot_walk.xml) | `stand`, `sitstand`, `walk`, `rough` | 45 geoms; a walkable collision set / 45 个 geom，可正常行走的碰撞集 |
| [robot_groundcontact.xml](robot_groundcontact.xml) | `getup` | 73 geoms; the head chain has collision geometry, so the robot can lie down and get up / 73 个 geom，头链带碰撞体，因此能躺下起身 |

## What was changed, exactly / 到底改了什么

One attribute, in each file, and nothing else: `meshdir="."` became `meshdir=".."`, so that the models load
the 20 STL files in [`../meshes/`](../meshes/) instead of a private copy of the same meshes. / 每个文件只改了一个
属性，别的都没动：`meshdir="."` 改成 `meshdir=".."`，好让模型加载 [`../meshes/`](../meshes/) 里那 20 个 STL，
而不是同一批网格的私有副本。

Everything else — the inertias, the joint definitions and ranges, the 14 position servos with their gains and
limits, the IMU and joint sensors, the contact parameters, the `<option>` solver settings, and the `stand`
keyframe — is byte-for-byte the training file. The 20 mesh files are **byte-identical** to the training ones;
all 20 SHA-256 digests match. / 其他部分 —— 惯量、关节定义与限位、14 个位置伺服及其增益与限位、IMU 与关节传感器、
接触参数、`<option>` 求解器设置、以及 `stand` 关键帧 —— 都与训练文件逐字节相同。20 个网格文件与训练用的
**逐字节相同**，20 个 SHA-256 全部一致。

The floor, the light, and the optional 1 cm curbs are **not** in these files. The runner adds them at load
time, so the XML stays exactly what training used. / 地面、灯光以及可选的 1 cm 台阶**不在**这两个文件里，由运行器
在加载时添加，因此 XML 保持训练时的原样。

## Running them / 怎么跑起来

```bash
python ../../../wamoduck_sim.py --policy stand --check
```

Do not load these files with the [URDF](../wmduck.urdf) meshes or settings: the URDF describes the same robot
but has no actuators, no sensors, and a different joint set, so a policy will not behave the same in it. See
the [simulation guide](../../../docs/simulation.md#why-you-must-use-the-bundled-mjcf-not-the-urdf) for why. /
不要用 [URDF](../wmduck.urdf) 的网格或设置来加载这两个文件：URDF 描述的是同一个机器人，但没有执行器、没有传感器，
关节集合也不同，策略在其中行为不会一致；原因见[仿真指南](../../../docs/simulation.zh-CN.md)。

## Licence and scope / 许可与范围

Same MIT licence as the rest of the repository. These are **simulation** models: they are not a
manufacturing specification, they declare simulation servo gains rather than hardware ratings, and nothing
here has been validated on a physical robot. / 沿用本仓库其余部分的 MIT 许可。它们是**仿真**模型：不是制造规格，其中
的伺服增益是仿真值而非硬件额定值，也没有在实物机器人上验证过任何内容。
