# 参考步态与 MATLAB 回放 / Reference gait and MATLAB player

[中文首页](../README.zh-CN.md) · [English home](../README.md) · [English version](matlab.en.md) · [回放器说明](../tools/matlab/README.md)

本页说明随仓库附带的参考步态：数据从哪来、是什么又不是什么、怎么播放，以及这条腿**实测**出来的限制。

```matlab
cd <repo>                      % 含 models/ 与 tools/ 的那一层目录
addpath('tools/matlab')
wamoduck_play                  % 交互回放
wamoduck_play('mesh')          % 以真实网格视图启动
wamoduck_play(true)            % 无界面自检：单位、限位、脚底贴地
```

![Wamoduck 参考步态与 MATLAB 回放器](../assets/wamoduck-matlab-player.png)

## 包含什么

| 项目 | 内容 |
| --- | --- |
| [`tools/matlab/wamoduck_play.m`](../tools/matlab/wamoduck_play.m) | 交互回放器：播放暂停、推进步长、两份数据、骨架或网格显示、力矩曲线、逐关节数值表 |
| [`tools/matlab/data/gait_cycle_2s_50Hz.csv`](../tools/matlab/data/gait_cycle_2s_50Hz.csv) | 一个**稳态**步态周期：50 Hz 共 100 帧（2.0 s，前进 2 cm），可无缝循环 |
| [`tools/matlab/data/gait_walk_1m_10Hz.csv`](../tools/matlab/data/gait_walk_1m_10Hz.csv) | 整段 1 m 行走，抽稀到 10 Hz（104 s） |
| [`assets/wamoduck-gait-preview.gif`](../assets/wamoduck-gait-preview.gif) | 两个周期，由公开 URDF + 给定关节角渲染 |
| [`assets/wamoduck-gait-walk.mp4`](../assets/wamoduck-gait-walk.mp4) | 连续行走 20 s，画面上标出机体位置 |

## 数据是什么

列与单位见[回放器说明](../tools/matlab/README.md#data-format--数据格式)。一句话：15 个关节角用**弧度**、15 个逆动力学力矩估计用 **N·m**、机体（`base_link`）位姿用米。

这是一条**准静态步态**：每步 1 cm、每步 1 s，所以机体以 1 cm/s 前进；每个周期机体前进 2 cm，两脚交替；抬脚高度 4.5 mm。

角度用弧度，是因为"发放—回放"这条路径上**不应该出现任何单位换算**。（内部早先的一版查看器把角度换算错了，每个关节被放大 57 倍；这类 bug 很容易藏起来、也很难当场发现，所以公开数据干脆不做换算。）

## 这条步态能做什么、不能做什么

在规划所用的模型上，整段 1 m 的实测结果：

| 量 | 数值 | 怎么得到的 |
| --- | ---: | --- |
| 逆运动学位置误差 | 中位 0.015 mm、最大 0.020 mm | 逐采样点 IK 残差 |
| 脚掌接触 | 相对地面 +0.04 / −0.12 mm 以内 | 逐帧取脚掌最低角点（MuJoCo 模型） |
| 静态稳定余量 | 100 % 的采样点为正（最小 +34.2 mm） | 重心相对支撑多边形 |
| 逆动力学峰值力矩 | 2.53 N·m（`right_knee`），占峰值 3.6 N·m 的 70 % | 逐关节逆动力学 |
| 摆动时的抬脚高度 | 4.5 mm，离地 >1 mm 的时间占 21 % | 脚掌最低角点 |
| 两脚都不动的时间 | 54 % | 脚掌最低角点 |

这条步态是**双脚支撑的准静态蹭步**：大部分时间里两个脚掌都停在离地几毫米以内。它不是动态行走，附带的数据也不声称是。

两条限制都是**实测**出来的，不是假设：

- **真正的单脚支撑走不了。** 抬脚超过约 5 mm，支撑就只剩一只脚，重心必须移到那只脚上方；站姿 165 mm、脚掌宽 51 mm ⇒ 需要**至少 57 mm 的横移**。而这条腿**没有踝侧摆关节**，膝关节在标称姿态之外也只有约 15 mm 行程，这个横移在运动学上拿不到。硬加横移会让逆运动学把脚**侧翻到棱上**——试验变体实测脚掌侧倾 42°、穿地 6.3 mm、接触力 112 N（整机重量才 37 N）。
- **脚掌只能放平前后方向，放不平左右方向。** 前后倾由髋俯仰／膝／踝这条链决定，可以解平，也确实解平了（残差 0.01°）；左右倾由髋侧摆和机体侧倾决定，没有独立的踝侧摆去抵消，所以会残留几度侧倾。

这也解释了这条规划的形状：**4.5 mm 抬脚 + 30 % 摆动窗口**能让两个脚掌始终基本贴着地面，静态余量因此全程为正。

## 怎么播放

| 控件 | 含义 |
| --- | --- |
| ▶ / ⏸ | 播放 / 暂停 |
| 推进 step | 每显示一帧推进几帧数据；越小越连贯。这里 MATLAB 画一帧大约只能 1–5 fps，**靠小步长才看起来连续** |
| 轨迹 data | 在"单个周期"与"整段 1 m"之间切换 |
| 显示 view | **骨架**（快，用来看运动）或**网格**（真实 STL 几何，用来看姿态） |
| 滑块 | 拖到任意一帧 |
| 力矩曲线 | 15 个关节，附 [`motor_parameters.json`](../models/wmduck/motor_parameters.json) 里的额定 0.6 N·m 与峰值 3.6 N·m 参考线 |

`wamoduck_play(true)` 不打开窗口就能检查数据：关节角是否在 URDF 限位内、两个脚掌是否贴在地面上。

## 来源与口径

关节角与机体位姿来自用**本仓库 URDF** 做的准静态参考步态规划（规划由另一个仿真项目完成，这里以弧度制导出）。GIF、MP4 与静帧都是用公开 URDF **给定关节角 + 前向运动学**渲染的，与 [`assets/README.md`](../assets/README.md) 里关节运动演示所用的方法一致。**不含物理积分、不含控制器、不是训练策略、不是实物。**

力矩是用本仓库的建模质量与惯量做的**逆动力学估计**，不是实测值。它用的是 [`motor_parameters.json`](../models/wmduck/motor_parameters.json) 里维护者实测的 **141 g** 电机质量那一版模型，所以**随附数据与随附 URDF 描述的是同一台机器人**。请把它当作"给定电机能力下的需求估计"，而不是台架结果。
