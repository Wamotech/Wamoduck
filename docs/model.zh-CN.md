# Wamoduck 模型指南

[首页](../README.zh-CN.md) · [English](model.en.md) | 简体中文

[Wamoduck URDF](../models/wmduck/wmduck.urdf) 是从 SolidWorks 2025 中保存的 `Full_wmduck.SLDASM` 总装导出的 15 自由度机器人描述，提供几何、运动学、估计惯量和初始关节限位，供查看与仿真开发使用。行走控制器和完整的强化学习环境仍待后续开发。

![Wamoduck 的 CAD 保存姿态](../assets/wamoduck-model.png)

这是统一灰色外观的模型渲染图，并非实物照片，也未还原全部 CAD 配色。

## 模型包文件

复制模型时，请保持 [models/wmduck/](../models/wmduck/) 目录完整。

| 文件 | 用途 |
| --- | --- |
| [wmduck.urdf](../models/wmduck/wmduck.urdf) | 机器人描述，包含惯性与关节数据 |
| [meshes/](../models/wmduck/meshes/) | 20 个二进制 STL，供 40 个零件实例复用 |
| [joint_parameters.json](../models/wmduck/joint_parameters.json) | 关节角度范围（rad）、力矩（N·m）与速度（rad/s） |
| [joint_limits.csv](../models/wmduck/joint_limits.csv) | 角度与弧度限位、碰撞零件对、边界括区和例外 |
| [motor_parameters.json](../models/wmduck/motor_parameters.json) | 转录的电机规格与惯量估计方法 |
| [component_mass_audit.csv](../models/wmduck/component_mass_audit.csv) | 零件材料、密度与质量 |
| [validation.json](../models/wmduck/validation.json) | 当前模型包结构与 MuJoCo 导入检查 |

JSON 文件用于描述当前导出结果。**只修改 JSON 不会重新生成或改变 URDF。** 调整数值时，需要同步修改 URDF 和相应参数记录。CAD 提取快照与生成脚本不在本公开包中。

## 坐标系、单位与零位

- `base_link` 与总装的 `Body_sys` IMU 参考坐标系重合：+X 向前、+Y 向左、+Z 向上。
- `imu_link` 是固定在 `base_link` 上、平移和旋转均为零的无质量参考坐标系。它不代表实物 IMU 已完成安装标定，也不会添加仿真传感器。
- **所有关节 q=0 对应 CAD 保存姿态**，包括弯曲的腿和倾斜的颈部。编码器零位、电机方向与直腿参考姿态需另行标定。
- 关节原点来自同心配合轴线与对应重合配合平面的交点。零位时各 link 坐标轴与 `Body_sys` 平行；未将子装配平移值直接作为关节位置。
- yaw 绕 +Z，roll 绕 +X，pitch、knee、ankle 和 mouth 绕 +Y。左右两侧正转均遵循右手定则。
- 单位为米、千克、kg·m² 和弧度。**STL 坐标已经是米，所有网格缩放均为 `1 1 1`，不要再乘 0.001。**

模型有 17 个 link：16 个机械刚体加 `imu_link`，由 15 个转动关节与 1 个固定关节连接。子装配内部零件作为刚体组运动，电机转子运动不单列自由度。

下图名称表示各运动链中的关节：

```text
base_link (Body_sys)
├─ left_hip_yaw → left_hip_roll → left_hip_pitch → left_knee → left_ankle
├─ right_hip_yaw → right_hip_roll → right_hip_pitch → right_knee → right_ankle
├─ neck_pitch → head_pitch → head_yaw → head_roll → mouth
└─ imu_link (fixed)
```

## 初始几何关节限位

下表角度单位为度，均相对于保存姿态。这些数值是带条件的几何估计，并非实测机械挡位或编码器限位。SolidWorks 角度配合用于定位保存姿态，未被当作真实运动范围。

| 关节 | 下限（°） | 上限（°） | 依据 / 例外 |
| --- | ---: | ---: | --- |
| `left_hip_yaw` | -99.0 | 30.5 | CAD 干涉边界，向内余量 ≥2° |
| `right_hip_yaw` | -30.5 | 99.0 | CAD 干涉边界，向内余量 ≥2° |
| `left_hip_roll` | -63.9 | 24.7 | CAD 干涉边界，向内余量 ≥2° |
| `right_hip_roll` | -24.7 | 63.9 | CAD 干涉边界，向内余量 ≥2° |
| `left_hip_pitch` | -64.8 | 160.7 | CAD 干涉边界，向内余量 ≥2° |
| `right_hip_pitch` | -64.8 | 160.7 | CAD 干涉边界，向内余量 ≥2° |
| `left_knee` | -32.9 | 178.0 | 下限余量 ≥2°；上限为软件范围 |
| `right_knee` | -32.9 | 178.0 | 下限余量 ≥2°；上限为软件范围 |
| `left_ankle` | -101.1 | 56.4 | CAD 干涉边界，向内余量 ≥2° |
| `right_ankle` | -101.1 | 56.4 | CAD 干涉边界，向内余量 ≥2° |
| `neck_pitch` | -35.1 | 128.5 | CAD 干涉边界，向内余量 ≥2° |
| `head_pitch` | -64.6 | 69.2 | CAD 干涉边界，向内余量 ≥2° |
| `head_yaw` | -178.0 | 178.0 | 双向均为软件范围 |
| `head_roll` | -71.9 | 75.7 | CAD 干涉边界，向内余量 ≥2° |
| `mouth` | 0.0 | 102.5 | 下限保留闭嘴位；上限余量 ≥2° |

源模型导出时的分析逐一移动每个关节的整条下游子树，其余关节保持零位，检查也包含相邻 link。先以 5° 粗扫，将碰撞边界细化至 ≤0.1°，再按 1° 间隔及区间端点复核，合计完成 2,538 个单关节离散姿态的实体交集检查。

在 ±180° 搜索窗口内，`head_yaw` 双向及膝关节正向未找到碰撞，因此这些方向暂取 178° 软件范围，不能据此认定机械挡位或线束允许转角。嘴部负向约 −0.9° 开始干涉，仍保留 0° 闭嘴位；其约 0.86° 的余量是 2° 规则的明确例外。

两处颈部轴承配合在零位已有约 0.117 mm³ 嵌入。分析以每对零件的初始交集体积再加 0.1 mm³ 为阈值，而非整对豁免。线束、未建模零件、制造偏差以及仅有曲面的 IMU 不在这些实体检查的覆盖范围内。

**独立限位不能保证多关节组合运动无碰撞。** 源分析抽样的 58 个组合姿态中，有 33 个出现超阈值干涉。因此，规划或控制仍需自碰撞检查，以及随整体姿态变化的约束。这里汇总的是源模型导出时的分析，当前模型包检查未重新执行该分析。

## 电机数据、质量与惯量

HTDW3532 参数转录自提供的产品参数图，未经台架实测。15 个电机均采用每台 150 g、额定输出扭矩 0.6 N·m、额定输出速度 60 rpm = 6.283185 rad/s。这些输出端参数已包含 32:1 减速器作用。单独记录的 3.7 N·m 堵转扭矩和 300 rpm 空载速度不作为连续 URDF 限值，资料也未给出允许堵转时长。

导出总质量为 **3.886339783 kg**，属于估计值。原 CAD 总质量为 3.348577287 kg，将每台电机约 114.149 g 的 CAD 质量替换为 150 g 后得到当前总质量。电机质心保持不变，惯量张量按质量比（约 1.314070037）缩放。随后对惯量张量旋转并使用平行轴定理重新合成各 link，且已将 SolidWorks 惯性积符号转换为 URDF 约定。

| 零件 | 当前假设 | 质量 |
| --- | --- | ---: |
| 15 台电机中的每台 | 产品标注质量；CAD 质量分布按比例均匀缩放 | 150.000 g |
| `Head` | CAD 材料为 6061 铝合金 | 773.444 g |
| `Battery_6s18650_24V` | CAD 材料为未充填环氧树脂 | 230.900 g |
| `IMU_YB-MRA02` | 只有曲面，无实体体积 | 0 g |

头部和电池的材料设置需按预期实物修正。IMU 的 CAD 零质量不代表其真实重量。其他零件保留 CAD 材料质量；整机重量和电机惯量分布尚未实测，这些假设限制了动力学预测的准确性。

## 在 MuJoCo 中打开

在仓库根目录运行以下命令，使用安装 MuJoCo 3.12.0 的 Python 环境：

```sh
python -m pip install "mujoco==3.12.0"
python -m mujoco.viewer --mjcf=models/wmduck/wmduck.urdf
```

查看器会立即开始仿真。查看 CAD 保存姿态时，请先按**空格键**暂停，再按 **Backspace** 重置；调整 **Joint（关节）**滑块时保持暂停。恢复仿真后，未配置执行器的模型会发生运动。参见[查看器快捷键](https://mujoco.readthedocs.io/en/stable/programming/samples.html#shortcuts)。

Python 包自带命令行查看器，其模型文件参数名为 `--mjcf`。参见官方 [Python 查看器文档](https://mujoco.readthedocs.io/en/stable/python.html#standalone-app)。

固定基座的最小导入示例，同样从仓库根目录运行：

```python
from pathlib import Path
import mujoco

path = Path("models/wmduck/wmduck.urdf").resolve()
model = mujoco.MjModel.from_xml_path(str(path))
print(model.nq, model.nv, model.nu)  # 15 15 0
```

如需浮动基座，可通过 [MuJoCo 模型编辑接口](https://mujoco.readthedocs.io/en/stable/python.html#model-editing)在导入时添加自由关节：

```python
from pathlib import Path
import mujoco

path = Path("models/wmduck/wmduck.urdf").resolve()
spec = mujoco.MjSpec.from_file(str(path))
spec.body("base_link").add_freejoint(name="floating_base")
model = spec.compile()
print(model.nq, model.nv, model.nu)  # 22 21 0
```

常规导入会固定 `base_link`。自由关节增加 7 个位置坐标（平移与四元数）和 6 个速度坐标。两种导入均为 `nu=0`：URDF 的力矩和速度元数据不会创建执行器或控制器。URDF 保留 visual，关闭静态 link 融合与惯量自动平衡。

## 碰撞与验证范围

除仅有曲面的 IMU 外，碰撞元素复用 CAD 网格。MuJoCo 常规网格碰撞采用[凸包](https://mujoco.readthedocs.io/en/stable/XMLreference.html#asset-mesh)，因此支架凹槽和外壳开孔不会形成精确的凹形碰撞体。仿真还需要适当简化或分解碰撞几何，并配置接触过滤。

[validation.json](../models/wmduck/validation.json) 记录对当前模型包及其固定/浮动基座 MuJoCo 导入新执行的检查，不是重新运行 CAD 干涉分析，也不能证明实物运动效果。本包尚未提供执行器、控制器、地面、调校后的接触参数或训练任务；模型可作为添加这些功能的起点。
