# 在 MuJoCo 里跑训练好的策略 / Run the trained policies in MuJoCo

[首页](../README.zh-CN.md) · [English](simulation.md) | 简体中文 · [实测能力清单](capabilities.zh-CN.md)

本页面向 [`policies/`](../policies/) 里公开的五个 Wamoduck 策略：站立、起身、坐／站、平地行走、1 cm 越障。
每个策略都以 ONNX 文件发布，并随附它训练时用的 **MJCF 模型**与一个单文件运行器，因此你可以在自己的电脑上用
纯 MuJoCo、不需要 GPU 跑起来。

**五个策略都在同一个 demo 里。** 同一个窗口在运行中就能切换：走路、坐下、起身、越障都不必重启脚本 —— 按
`1`-`5`，或按 `Tab`／`n` 切到下一个。运行器会在启动时、以及**每次切换之后**打印当前策略、观测维度与它接受的
指令通道。

**范围：仅仿真（Sim2Sim）。** 本页所有内容都在 CPU 上用 MuJoCo 运行，模型就是策略训练时用的那个。
**本仓库没有任何实机结果**，没有在实物机器人上验证过任何内容，"在 MuJoCo 里能站住"不等于"在硬件上能站住"。

**上手前值得先知道的三条局限。** 行走不会原地转，给侧移指令还会把机器人带得打转；`getup` 能站起来，
但不会停进保存的标称姿态；本页没有任何一个数字来自硬件。这三条连同数字都在
[已知不足，直说](#已知不足直说)里写全了。

## 快速开始

```bash
pip install mujoco onnxruntime numpy

git clone <本仓库>
cd Wamoduck

python wamoduck_sim.py --list                 # 看发布了什么
python wamoduck_sim.py                        # 一个窗口，五个策略
python wamoduck_sim.py --policy getup --spawn lie-back
python wamoduck_sim.py --policy walk --vx 0.3
python wamoduck_sim.py --policy stand --check # 契约自检，不开窗口
python wamoduck_sim.py --cycle-test           # 无界面切换自检
```

`--policy` 指定 demo **启动时**用哪个策略（默认 `stand`）；之后用 `1`-`5` 切换。
`wamoduck_sim.py` **只**依赖 `mujoco`、`onnxruntime`、`numpy` —— 不含 mjlab、torch、rsl_rl，也不需要 CUDA。

按键要打在启动脚本的那个终端里，不是打在查看器窗口里：

| 按键 | 作用 | 对哪些策略有效 |
| --- | --- | --- |
| `1` `2` `3` `4` `5` | 切换策略：`stand`／`getup`／`sitstand`／`walk`／`rough` | 全部策略 |
| `Tab`／`n` | 按上面的顺序切到下一个策略 | 全部策略 |
| `↑`／`w`、`↓`／`s` | `vx` ± 0.1 m/s | `walk`、`rough` |
| `←`／`a`、`→`／`d` | `vy` ± 0.1 m/s | `walk`、`rough` |
| `e`／`z` | `wz` ± 0.1 rad/s | `walk`、`rough` |
| `space` | 速度指令清零 | `walk`、`rough` |
| `m` | 坐／站切换（0.085 m／0.175 m） | `sitstand` |
| `r` | 复位（按当前策略重新出生） | 全部策略 |
| `k` | 开关策略（关掉时保持零动作） | 全部策略 |
| `q` | 复位并随机推一把 | 全部策略 |
| `h`／`?` | 再打印一次键表 | 全部策略 |
| `x` | 退出 | 全部策略 |

**查看器窗口里也写着策略名。** 左上角是 `policy: walk`（**正在运行**的策略），左下角是 `selected: walk`
（最近一次**选中**的策略），旁边还有观测维度、MJCF 与地形、以及当前的指令值 —— 所以"它现在在跑什么"在画面上
就能看到，而不是只在终端里。两个名字只有在切换被拒绝时才会不同，而那正是需要看见它的时候。

**没有任何按键会被静默忽略。** 速度键只存在于 `walk` 与 `rough` 的观测里，`m` 只存在于 `sitstand` 里；
在当前策略没有对应通道时按键会打印"这个键需要哪种指令、当前策略实际观测哪种指令"，完全没绑定的键也会说明：

```text
[key] 'm' needs a body-height command, but the current policy 'walk' observes vx/vy/wz -- ignored (nothing changed)
```

### 切换时保留什么、什么时候必须重置

| 切换 | MJCF | 机器人状态会怎样 |
| --- | --- | --- |
| `stand` ↔ `sitstand` ↔ `walk` ↔ `rough` | 不变（`robot_walk.xml`） | **保留状态。** 只换 ONNX actor 与观测装配（48／49／51 维），因此姿态、速度、速度指令与高度指令都留下来了。`last_action` 归零 —— 那一项观测是**新策略**对自己上一步输出的记忆。 |
| 进入或离开 `getup` | 重新加载（`robot_groundcontact.xml` ↔ `robot_walk.xml`） | **状态被重置，而且运行器会说明原因。** `getup` 是唯一用"头链会碰撞"的模型训练出来的策略，因此它需要另一个物理模型；策略是"它所训练的模型"的函数，把一个模型的状态搬进另一个模型没有意义。进入 `getup` 时机器人以躺姿重出生（`lie-back`），离开时以标称站姿重出生。 |
| `walk` ↔ `rough` | 不变 | **保留状态。** 1 cm 台阶本来就编译在模型里，只做移动：从机器人当前 `x` 前方 0.3 m 起、间距 0.3 m 摆好，没用到的那些停在地面以下并关掉碰撞。不重新加载任何东西。 |

命令行给了 `--spawn` 时，它覆盖**每一个**策略的出生姿态，包括模型重载之后的那次重置；不给时每个策略用
自己的默认出生姿态：`getup` 用 `lie-back`，其余用 `nominal`。

无界面自检跑完会打印末态倾角、基座高度、关节偏差与脚底接触：

```bash
python wamoduck_sim.py --policy stand --headless --steps 250   # 50 Hz 下 5.0 s
python wamoduck_sim.py --policy getup --spawn lie-back --headless --steps 300   # 6.0 s
python wamoduck_sim.py --policy walk --vx 0.3 --headless --steps 250
```

## 策略清单

| 名称 | ONNX（`policies/`） | 来源轮次 | 检查点 | MJCF（`models/wmduck/mjcf/`） | 做什么 |
| --- | --- | --- | --- | --- | --- |
| `stand` | `wamoduck-stand-stand_v3.onnx` | `2026-09-12_08-32-26_stand_v3`（标了 SHIP） | `model_1499.pt` | `robot_walk.xml` | 保持标称站姿；被推后恢复 |
| `getup` | `wamoduck-getup-getup_v18.onnx` | `2026-09-15_17-37-06_getup_v18` | `model_3999.pt` | `robot_groundcontact.xml` | 从躺姿起身站回双脚 |
| `sitstand` | `wamoduck-sitstand-sit_stand_v2.onnx` | `2026-09-12_11-18-34_sit_stand_v2`（标了 SHIP） | `model_2499.pt` | `robot_walk.xml` | 按指令的基座高度蹲下／站起 |
| `walk` | `wamoduck-walk-walk_v4r.onnx` | `2026-09-16_12-01-21_walk_v4r` | `model_6000.pt` | `robot_walk.xml` | 按速度指令在平地行走 |
| `rough` | `wamoduck-rough-rough_v2.onnx` | `2026-09-16_00-00-04_rough_v2` | `model_5999.pt` | `robot_walk.xml` | 按速度指令越过 1 cm 台阶 |

"来源轮次"与"检查点"两列是用研发仓库的 `tools/run_select.py` 解析出来的，不是手工挑文件。`stand` 与
`sitstand` 由各自的 `SHIP` 标记选中；`getup`、`walk`、`rough` 由显式指定轮次名选中，那是该工具里优先级最高的
规则。随后每个公开 ONNX 都用 `.pt` 文件重建 actor 与 ONNX 的权重逐项比对，确认它确实就是该列写明的那个检查点
导出的（见[在什么机器上验证了什么](#在什么机器上验证了什么没验证什么)）。

## 观测与动作契约

这一段写错就会"看起来能跑但完全不对"，所以逐项写死。

**控制频率 50 Hz。** 一个控制步 = `decimation = 4` 个 `timestep = 0.005 s` 的物理步（20 ms），与训练一致。
两个数字都在训练配置里，也写在 MJCF 的 `<option>` 元素里。

### 观测向量 —— 喂**原始值**

| # | 观测项 | 偏移 | 维度 | 单位／定义 |
| --- | --- | ---: | ---: | --- |
| 1 | `base_ang_vel` | 0 | 3 | rad/s，机体系 —— 即 MJCF 的 `imu_gyro` 传感器 |
| 2 | `projected_gravity` | 3 | 3 | 单位向量；直立时 `(0, 0, -1)`；等于 `Rᵀ·(0,0,-1)` |
| 3 | `joint_pos` | 6 | 14 | rad，相对 `default_joint_pos`；该默认值**全为零**，所以就是绝对角 |
| 4 | `joint_vel` | 20 | 14 | rad/s，相对默认关节速度（为零） |
| 5 | `last_action` | 34 | 14 | **上一帧策略原始输出**，未乘 scale、未加 offset |
| 6a | `command`（twist） | 48 | 3 | `vx` m/s、`vy` m/s、`wz` rad/s —— 用于 `walk`、`rough` |
| 6b | `height_command` | 48 | 1 | 目标基座高度，m —— 用于 `sitstand` |

合计：`stand` 与 `getup` 为 **48**，`sitstand` 为 **49**，`walk` 与 `rough` 为 **51**。ONNX 的输入形状标注了
同一个数字，运行器拒绝把策略和不对应的任务配在一起。

训练用的指令范围（训练配置里的 `CMD_RANGES`）：`vx` ∈ [-0.4, 0.6]，`vy` ∈ [-0.3, 0.3]，
`wz` ∈ [-0.8, 0.8]。运行器按这个范围截断，并在截断时打印出来。坐／站的高度指令范围是 [0.085, 0.175] m。

### 关节顺序 —— 关节树顺序，不是执行器顺序

`joint_pos` 的 14 个值、`joint_vel` 的 14 个值、以及 14 个动作值，全部按**关节树顺序**排列，也就是关节在
MJCF 里出现的顺序，也是 ONNX 元数据记录的顺序：

| 下标 | 关节名 |
| ---: | --- |
| 0 | `left_hip_yaw` |
| 1 | `left_hip_roll` |
| 2 | `left_hip_pitch` |
| 3 | `left_knee` |
| 4 | `left_ankle` |
| 5 | `right_hip_yaw` |
| 6 | `right_hip_roll` |
| 7 | `right_hip_pitch` |
| 8 | `right_knee` |
| 9 | `right_ankle` |
| 10 | `neck_pitch` |
| 11 | `head_pitch` |
| 12 | `head_yaw` |
| 13 | `head_roll` |

这就是全部 14 个被驱动的关节：先左腿、再右腿，最后是颈／头链。

**它不是 MJCF 里 `<actuator>` 块的顺序。** 那一块是左右交替的（`act_left_hip_yaw`、`act_right_hip_yaw`、
`act_left_hip_roll`、……）。两种顺序并不相同，用执行器顺序去装观测或动作，机器人会在一秒内垮掉。见
[关节顺序写错会怎样](#关节顺序写错会怎样)。

在运行器里这就是一行：`ctrl_ids = [0, 2, 4, 6, 8, 1, 3, 5, 7, 9, 10, 11, 12, 13]`，于是动作第 `i` 项被写到
驱动树序第 `i` 个关节的那个执行器上。

### 动作 → 关节目标

```
q_target[j] = default_joint_pos[j] + action_scale * action[j]      其中 action_scale = 1.0
```

- `default_joint_pos` 是 **14 个零**（ONNX 元数据与 `stand` 关键帧一致），所以每个关节上
  `q_target = action`。
- **动作不做任何截断。** 训练的 runner 配置里 `clip_actions = None`，动作配置也没有设 `clip`。每个动作值
  都按原值使用。
- 接下来由 MuJoCo 把 `ctrl` 截到各执行器的 `ctrlrange`（模型里每个执行器都是
  `ctrllimited = true`，来自 `autolimits="true"`），关节限位是在这一步生效的。
- 伺服是软位置伺服：14 个关节全部 `kp = 5.0`、`kv = 0.5`、`forcerange = ±1.5 N·m`。这些是**仿真值，
  不是硬件额定值**。

### ONNX 里已经含观测归一化

**把原始观测直接喂给 ONNX。不要自己再归一化，也不要减均值。**

公开的五个 ONNX 图都以归一化开头：两个节点 `Sub`、`Div`，initializer 是 `obs_normalizer._mean` 与一个除数，
之后是三层 `Gemm` + `Elu` 的 actor（512 → 256 → 128 → 14）。导出的就是**带** `EmpiricalNormalization` 模块的
actor，因为 actor 配置里 `obs_normalization = True`。

具体说，图里算的是 `(obs - mean) / (std + eps)`，其中 `eps = 0.01`，然后进 MLP —— 所以如果客户端再归一化一次，
就是**归一化了两次**，这正是"跑起来了但行为和训练完全不一样"这类错误的经典成因。图里那个除数已逐元素验证
等于检查点自己的 `obs_normalizer._std` 加 0.01。

五个图的情况如下：

| 策略 | ONNX 输入 | ONNX 输出 | 图内是否含归一化 |
| --- | --- | --- | --- |
| `stand` | `obs` `[1, 48]` | `actions` `[1, 14]` | 含（`Sub`、`Div` + `obs_normalizer._mean`） |
| `getup` | `obs` `[1, 48]` | `actions` `[1, 14]` | 含 |
| `sitstand` | `obs` `[1, 49]` | `actions` `[1, 14]` | 含 |
| `walk` | `obs` `[1, 51]` | `actions` `[1, 14]` | 含 |
| `rough` | `obs` `[1, 51]` | `actions` `[1, 14]` | 含 |

## 为什么必须用随附的 MJCF，而不是 URDF

[`models/wmduck/` 里的 URDF](../models/wmduck/) 与 [`models/wmduck/mjcf/`](..) 里的 MJCF 描述的是同一个机器人，
但只有一个是**策略训练时用的模型**。请用 MJCF。

- **URDF 没有执行器、没有传感器、也没有接触模型。** 它声明 15 个转动关节与 17 个 link，供查看与交换使用，
  `effort` 用的是额定 0.6 N·m，且完全没有 actuator 元素。策略三样都需要：14 个带 `kp`／`kv`／`forcerange`
  的位置伺服、观测要读的 `imu_gyro` 传感器、以及机器人站在上面的碰撞几何。
- **关节数并不相同。** URDF 的 15 个关节里有一个 `mouth` 关节在控制模型里并不被驱动；策略驱动的是 **14** 个
  关节，观测也是 14 维。
- **训练 MJCF 带着实测质量更新。** 策略是按 MJCF 里的质量训练的；公开 URDF 带着尚未与之对齐的电机质量覆盖值。
  惯量、接触几何、碰撞变体都不一样。策略是"它所训练的那个模型"的函数，换模型就是换任务。

本仓库公开的两个 MJCF 就是训练文件原文，**只改了一个属性**：`meshdir="."` 改成 `meshdir=".."`，好让模型加载
本仓库已有的 [`models/wmduck/meshes/`](../models/wmduck/meshes/) 里那 20 个网格，而不是某个私有副本。除此之外没有任何不同 ——
惯量、关节、执行器、传感器、接触参数、`<option>` 块都没变。20 个网格文件与训练用的**逐字节相同**
（20 个 SHA-256 全部一致）。

地面、灯光、以及可选的 1 cm 台阶都由运行器在加载时添加，所以 XML 文件本身保持训练时的原样。

## 在什么机器上验证了什么、没验证什么

下面三项必需检查都在**纯 CPU**（不用 GPU）上跑，环境是 MuJoCo 3.10、ONNX Runtime 1.30、NumPy 2.5，并且走的
就是公开的 `wamoduck_sim.py` 代码路径与公开的 ONNX 文件。

### 1. `stand` —— 从标称站姿跑 5 s 不摔倒

```
python wamoduck_sim.py --policy stand --headless --steps 250
```

```
[final] tilt=  0.54 deg  base_z=0.1770 m  max_joint_dev=  1.88 deg  both_soles=True  standing=True  nominal=True
[final] simulated 5.00 s (250 control steps)
[final] base_z 0.1776 -> 0.1770 m
[final] displacement dx=+0.001 m dy=-0.000 m |d|=0.001 m
```

末态倾角 **0.54°**，基座高度 **0.1770 m**（起始 0.1776），双脚着地，最大关节偏差 **1.88°**，5 s 总漂移
1 mm。这一项**连严格口径都通过**（倾角 < 8°、双脚着地、每关节偏差 < 20°、基座高度 > 0.15 m），
即[实测能力清单](capabilities.zh-CN.md)用的那套判据。

### 2. `getup` —— 从躺姿跑 6 s 能站起来

```
python wamoduck_sim.py --policy getup --spawn lie-back --headless --steps 300
```

```
[start] tilt= 69.81 deg  base_z=0.0920 m  max_joint_dev=  9.34 deg  both_soles=True  standing=False  nominal=False
[final] tilt=  8.24 deg  base_z=0.1784 m  max_joint_dev= 52.08 deg  both_soles=True  standing=True  nominal=False
[final] base_z 0.0920 -> 0.1784 m
[final] lowest tilt seen: 2.41 deg
```

它确实站起来了：从倾角 69.8°、基座 0.092 m 的躺姿，最终到 8.24°、0.1784 m，双脚着地，中途最小倾角
2.41°。它达到的是**宽松**的"站住"，**没有**达到严格标称口径，因为末态关节偏差是 52° —— 这正是内部
[实测能力清单](capabilities.zh-CN.md)记录的"站住 64/64、严格标称 0/64"那个差距。这次 CPU 运行是**复现**了
那个已知不足，而不是把它藏起来。

公开的五个躺姿出生点各跑 6 s：`lie-back`、`lie-front`、`lie-side`、`lie-side-r`、`inverted` 末态都站住。

### 3. `walk` —— vx = 0.3 m/s 跑 5 s 能前进

```
python wamoduck_sim.py --policy walk --vx 0.3 --headless --steps 250
```

```
[final] tilt=  4.92 deg  base_z=0.1864 m  max_joint_dev= 23.11 deg  both_soles=False  standing=True  nominal=False
[final] base_z 0.1776 -> 0.1864 m
[final] displacement dx=+1.482 m dy=-0.328 m |d|=1.518 m
[final] commanded vx=+0.30 m/s -> +1.500 m in 5.0 s
```

指令 1.500 m，实际走了 **1.482 m**，即指令速度的 **99 %**，全程倾角保持在 5° 以内，没有摔倒。
这是纯 CPU MuJoCo 的数字，**不能**与[实测能力清单](capabilities.zh-CN.md)里的内部 GPU 实测相比 —— 那边用的
是另一个仿真器（MuJoCo Warp）和另一套协议。

### 另外也查了

```
python wamoduck_sim.py --policy sitstand --target-height 0.085 --headless --steps 250
python wamoduck_sim.py --policy rough --terrain-level 3 --vx 0.3 --headless --steps 250
```

- `sitstand`：指令 0.085 m，**实际维持 0.0942 m**（高 9 mm），双脚着地，倾角 25.9°。它能蹲下并保持住，
  但没有精确达到指令高度，而且蹲着的时候是歪的。
- `rough`：在 3 个连续的 1 cm 台阶上以 vx = 0.3 前进，5 s 走了 **1.384 m**，保持站立（倾角 5.3°）。
  `--terrain-level N` 会添加 N 个台阶，从前方 0.3 m 处开始、间距 0.3 m。
  自从 demo 支持切换策略之后，`rough` **默认**就带这 3 个台阶，而 `walk` 保持平地，这样在两者之间切换时
  地形与策略会一起变。`--terrain-level N` 仍然覆盖两者，此时每个策略都在 N 个台阶上跑。

### 一个 demo 切换全部五个策略：`--cycle-test`

```
python wamoduck_sim.py --cycle-test
```

`--cycle-test` 就是用户在窗口里那套操作的无界面版本：它通过**键盘用的同一个按键处理函数**依次按下
`1`、`2`、`3`、`4`、`5`，因此"保留状态"与"重载模型"两条路径都被走到，并对每一段做断言。每个策略 300 个控制步
（6.0 s），两个行走策略给 `vx = +0.30 m/s`，坐／站段中间按一次 `m`：

| 段 | 进入方式 | 末态倾角 | 末态 `base_z` | 位移 | 朝向变化 |
| --- | --- | ---: | ---: | ---: | ---: |
| `1 stand` | 原地切换（与起始策略同一 MJCF） | 0.54° | 0.1770 m | 0.001 m | +1.0° |
| `2 getup` | **重载**（`robot_groundcontact.xml`，出生点 `lie-back`） | 8.14° | 0.1782 m（起 0.0920） | 0.071 m | +33.8° |
| `3 sitstand` | **重载**回 `robot_walk.xml`，出生点 `nominal` | 25.74° | 按 `m` 后 0.0945 m（此前 0.1748） | 0.038 m | +26.2° |
| `4 walk` | 原地切换（保留蹲姿状态） | 4.49° | 0.1841 m | 指令 1.800 m 中走了 1.730 m | **−112.2°** |
| `5 rough` | 原地切换，台阶摆到机器人前方 | 3.28° | 0.1904 m | 指令 1.800 m 中走了 1.774 m | −64.4° |
| `6 walk`（前进复核） | 按 `4` 再按 `r`：从标称姿重新出生，5.0 s | 6.14° | 0.1770 m → 0.1864 m | dx **+1.482 m**、dy −0.328 m | −19.6° |

六条断言全部通过，而对 demo 最关键的两点在表里就能看出来：重载确实会重置机器人（`getup` 从躺着的
0.0920 m 起到 0.1782 m），原地切换确实会保留状态（`walk` 这一段就是从坐／站段留下的 0.0945 m 蹲姿开始的）。

**第 4 段要连着"朝向变化"一列一起看。** 因为 sitstand → walk 这次切换按设计**保留状态**，行走策略接手时机器人
是**蹲着的、倾角 25.7°，而且 0.085 m 的高度指令仍然生效**，所以这一段前半程实际上是在恢复：它先转了 **112°**
才进入正常行走，因此那 1.730 m 大部分是沿着它自己**转向后的前方**走的，而不是沿 `+x`。这正是这个行走检查点
已知的"未指令自转"弱点；该断言断言的是**有位移**，不是朝向。第 6 段就是它的对照：在五次切换（其中两次重载
MJCF）之后，把 demo 切回 `walk`、按 `r` 重新出生，它**完全复现**单策略运行的结果 —— 5.0 s 内
`dx = +1.482 m`、`dy = −0.328 m`，与上面 `walk` 一节里的数字一模一样。

这些数字测于 **MuJoCo 3.12.0、ONNX Runtime 1.28.0、NumPy 2.4.6**，也就是加这项切换自检时我们机器上的版本；
而前面三节里的运行测于 MuJoCo 3.10、ONNX Runtime 1.30、NumPy 2.5 —— 这正是像 `getup` 末态高度这种接触丰富的
数字会在最后两位上有差别的原因。两组都是纯 CPU 的 MuJoCo。

### `--check`：契约自检

`python wamoduck_sim.py --policy <名称> --check` 会拿观测装配合 MuJoCo 自身的量对着算，而不是相信代码，
五个策略全部通过：

- `projected_gravity` 等于 MuJoCo 自己算的基座旋转矩阵的 `-R[2,:]`（在一个旋转过的姿态上检查）；
- `imu` 的 site 坐标系等于基座坐标系，且 `imu_gyro` 等于自由关节的角速度 —— MuJoCo 把它存在**机体系**里
  （同样在旋转姿态上检查；直立姿态会让这一条平凡成立，从而掩盖错误的坐标系约定）；
- 标称姿态 `q = 0` 落在每个关节范围内；
- 每个执行器都是 `ctrllimited`，且 14 个的 `kp = 5.0`／`kv = 0.5`；
- ONNX 图内含归一化，因此必须喂原始观测；
- 装出来的观测向量与动作向量维度正确且数值有限。

### 关节顺序写错会怎样

正因为动作顺序是这里最容易写错的一处，它是**量出来的**，不是假设的。每个策略都试四种接法，每种跑 5 s
（`getup` 跑 6 s）：

| 策略 | 观测顺序 | 动作顺序 | 结果 |
| --- | --- | --- | --- |
| `stand` | 树序 | **树序** | 倾角 **0.54°**、base_z 0.1770 —— 站住 |
| `stand` | 树序 | 执行器序 | 倾角 135.5°、base_z 0.035 —— 垮掉 |
| `stand` | 执行器序 | 树序 | 倾角 135.3° —— 垮掉 |
| `stand` | 执行器序 | 执行器序 | 倾角 134.0° —— 垮掉 |
| `walk` | 树序 | **树序** | vx = 0.3 下走了 **+1.482 m**（指令 1.500 m） |
| `walk` | 树序 | 执行器序 | 垮掉（倾角 135.3°） |
| `walk` | 执行器序 | 树序 | 垮掉 |
| `walk` | 执行器序 | 执行器序 | 垮掉 |
| `sitstand` | 树序 | **树序** | 蹲到 0.094 m，双脚着地，保持住 |
| `sitstand` | 其余三种中任意一种 | | 垮掉（倾角约 135°） |
| `getup` | 树序 | **树序** | 五个躺姿出生点 **5/5** 末态站住，末态平均倾角 8.2° |
| `getup` | 树序 | 执行器序 | 1/5 末态站住，末态平均倾角 47.0° |
| `getup` | 执行器序 | 树序 | 0/5 |
| `getup` | 执行器序 | 执行器序 | 0/5 |

只有"观测用树序**且**动作用树序"这一种接法能用，而且它是唯一对每个策略都能用的接法。`getup` 是五个里最不
敏感的 —— 从某一个躺姿出发，即使动作顺序写错它也能站起来 —— 但在全部五个出生点上这个侥幸就消失了
（1/5 对 5/5）。

## 已知不足，直说

- **行走是五个里最弱的一项，本次发布用的是重训后的结果。** `walk_v4r` 是最新的行走轮次，它跑到迭代上限
  6000 后停止，本页公开的 ONNX 就是它最后一个检查点 `model_6000.pt` 导出的那一份。此前内部对行走的实测
  记录了两条本版本**并没有修好**的失败：
  **原地转不会** —— 0.5 rad/s 的偏航指令在 10 s 内只转出 **+0.3°**；**侧移伴随大量未指令自转** ——
  +0.30 m/s 的侧向指令给出 +0.218 m/s 的侧移，同时附带 **+520.4°** 的未指令偏航。我们自己的 CPU 运行也
  重现了这个症状的缩小版：5 s 直行过程中侧向漂了 **0.328 m**。请把"向前走"当作可用，把"转向／侧移"当作不可用。
- **行走的 ONNX 不是能力清单实测的那个检查点。** 那张表的行走行指的是 `walk_r3`，它是在更早的指令范围下
  训练的。`walk_v4r` 没有内部测量数据，所以本页只引用我们自己 CPU Sim2Sim 的位移，其他什么都不声称。
- **`getup` 没有回到严格标称姿态**（末态关节偏差 52°）。它能起身、能站住，但没有收敛到全零姿态。
- **`sitstand` 在要求 0.085 m 时维持 0.094 m**，蹲着时倾斜约 26°。
- **这些策略只在一个仿真器、一台机器、一天里测过。** 内部的测量协议没有公开，所以本仓库无法重新推出那些
  内部比例。
- **`rough` 是用手工放置的 3 个台阶检查的，不是训练用的地形生成器。** 地形生成器没有公开，所以这只是对
  障碍族的近似，不是训练地形的复现。

## 文件

```text
Wamoduck/
├── wamoduck_sim.py                  # 运行器：一个 demo 跑五个策略
│                                    #   （只依赖 mujoco + onnxruntime + numpy）
├── policies/
│   ├── wamoduck-stand-stand_v3.onnx
│   ├── wamoduck-getup-getup_v18.onnx
│   ├── wamoduck-sitstand-sit_stand_v2.onnx
│   ├── wamoduck-walk-walk_v4r.onnx
│   ├── wamoduck-rough-rough_v2.onnx
│   └── README.md                    # 哈希与来源
└── models/wmduck/
    ├── mjcf/
    │   ├── robot_walk.xml           # stand、sitstand、walk、rough
    │   ├── robot_groundcontact.xml  # getup（33 个碰撞体，所以能躺下）
    │   └── README.md
    └── meshes/                      # MJCF 加载的 20 个 STL
```

## 本页不声称什么

- **没有实机结果。** 本页每个数字都是仿真。仓库里没有任何对策略的实物测量。
- **没有训练代码。** 训练配置、检查点、场景生成器和测量工具都没有公开。公开出来的东西够你**运行**这些策略，
  不足以复现训练或内部测量。
- **不声称这些 ONNX 已经可以直接上硬件。** 它们就是训练产出的东西。电机标定、编码器方向与零位、CAN ID、
  时序与安全限幅是另一个问题，本仓库没有解决。

## 相关内容

- [实测能力清单](capabilities.zh-CN.md) / [英文版](capabilities.md) —— 策略被内部工具实测出来的数字，以及
  哪些部分还不行。
- [模型指南](model.zh-CN.md) / [英文版](model.en.md) —— URDF、它的 15 个关节与相关假设。
- [路线图](roadmap.md) —— 公开仓库还缺什么。
