# Wamoduck 的 ROS 2（Jazzy）链路

给**不熟悉 MuJoCo 的人**准备的一条 ROS 2 链路：装什么、怎么编译、怎么一键跑起来看到机器人动
——完全不碰物理引擎。

**本目录只做前两段。**

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| **1. 描述包 + 节点** | `wamoduck_msgs`、`wamoduck_description`、`wamoduck_ros2` | 已完成：编译、节点、话题均已验证（见[验证状态](#验证状态)） |
| **2. RViz 可视化** | `display.launch.py`、`gait_display.launch.py`、两个 `.rviz` 配置 | 已完成：截图证据在 [`verification/`](verification/) |
| 3. Gazebo | `ros-jazzy-ros-gz`、物理、控制器 | **未开工 —— 这里没有任何东西在跑 Gazebo** |
| 4. MoveIt | 运动规划 | **未开工** |

本目录**不声称** Gazebo 或 MoveIt 能用，也**不声称**任何实机效果；`ros-jazzy-ros-gz` 刻意不在依赖里。

> **第 2 段没有物理。** RViz 不积分动力学、不做碰撞、不加重力。屏幕上"看着像在走"只能证明：
> 描述包能加载、关节坐标系的位置和 URDF 说的**一致**、`JointState` 流是合法的。
> 它证明不了动力学或平衡。本项目的物理基准仍然是 MuJoCo。

---

## 包结构

```
ros2/
├── wamoduck_msgs/          接口包（ament_cmake）
│   └── msg/JointTarget.msg       46 B CMD 帧负载的 ROS 侧映像
│   └── msg/LinkStatus.msg        链路计数 + 小脑状态字
├── wamoduck_description/   URDF + 网格 + RViz（ament_cmake）
│   ├── scripts/generate_ros_urdf.py   编译期改写网格路径
│   ├── urdf/README.md                 为什么这里不存 URDF
│   ├── launch/display.launch.py       robot_state_publisher + joint_state_publisher + RViz
│   └── rviz/wamoduck.rviz, wamoduck_world.rviz
├── wamoduck_ros2/          节点（ament_python）
│   ├── wamoduck_ros2/frame_codec.py       二进制协议，不含 ROS，单元测试齐全
│   ├── wamoduck_ros2/model_contract.py    冻结的策略契约 + 从 URDF 读关节
│   ├── wamoduck_ros2/gait_csv.py          tools/matlab/data/gait_*.csv 的解析
│   ├── wamoduck_ros2/policy_interface.py  观测拼装、动作置换
│   ├── wamoduck_ros2/policy_runner.py     ONNX 边界（骨架，从未执行）
│   ├── wamoduck_ros2/gait_player.py       CSV → sensor_msgs/JointState
│   ├── wamoduck_ros2/policy_node.py       50 Hz 策略环（骨架）
│   ├── wamoduck_ros2/bridge_stub.py       字节传输 ↔ 话题（骨架 + 编解码器）
│   └── launch/gait_display.launch.py      gait_player + RViz，一条命令
├── tools/verify_description.py   与 RViz 无关的描述包几何校验
└── verification/                 下面那些验证跑出来的证据
```

节点划分遵循 `docs/16_真机部署方案.md` §6.5：**ROS 只留在 Linux 侧**（AT32 的 96+12 KB SRAM
跑 DDS 会话很紧，不跑 micro-ROS），线上协议是确定性的 46 B 帧格式，**只有 bridge 一个组件解析字节**。
全部是普通 `rclpy`，不需要实时内核。命名对应关系：

| `docs/16` §6.5 | 本包 |
| --- | --- |
| `wmduck_bridge` | `bridge_stub` |
| `wmduck_policy` | `policy_node` |
| `wmduck_safety` | **未编写**（后续阶段） |
| `wmduck_msgs/JointTarget` | `wamoduck_msgs/JointTarget` |

### 素材绝不存两份

`models/wmduck/` 始终是唯一出处。本目录**不含任何网格和 URDF**；步态 CSV 的唯一出处仍是
`tools/matlab/data/`。

* `wamoduck_description` 在编译期把规范 URDF 里的 `meshes/Head.stl` 改写成
  `package://wamoduck_description/meshes/Head.stl`，并直接从 `models/wmduck/meshes` 安装网格；
* `wamoduck_ros2` 把 `tools/matlab/data/gait_*.csv` 安装到 `share/wamoduck_ros2/data`。

两者都是**安装期拷贝**，所以 11 MB 的 STL 在 Git 仓库里只存在一份。为什么不用符号链接，见
[`wamoduck_description/urdf/README.md`](wamoduck_description/urdf/README.md)。

这个改写不是装饰性的：`robot_state_publisher` + RViz 通过 `resource_retriever` 解析网格，它只认
`package://`、`file://` 和**相对当前工作目录**的路径，**不认相对 URDF 的路径**。换个目录启动 RViz
机器人就会静默地画不出来。`tools/verify_description.py` 专门量化了这件事：对规范 URDF 它报告
79 处引用全部依赖工作目录，对生成后的 URDF 报告 0 处。

---

## 安装

ROS 2 **Jazzy**（Ubuntu 24.04 的配套版本）。**不要用 Humble**，那是 22.04 的。

### 方案 A —— 全装，含 RViz（工作站）

```bash
sudo apt update
sudo apt install ros-jazzy-desktop
```

省事，本文验证用的就是这个（`0.11.0-1noble`，RViz 14.1.23），大约 1–2 GB。

### 方案 B —— 最小（RDK X5，或无显示的机器）

```bash
sudo apt install ros-jazzy-ros-base \
                 ros-jazzy-robot-state-publisher \
                 ros-jazzy-joint-state-publisher
# 只有那台机器还要开 RViz 时才需要：
sudo apt install ros-jazzy-rviz2
```

跑节点 `ros-jazzy-ros-base` 就够。有东西要消费 `wamoduck_description` 的 TF 时才需要
`robot_state_publisher`；RViz 需要 `rviz2` 包以及随它来的 `rviz_default_plugins`。

### 编译与测试工具

```bash
sudo apt install python3-colcon-common-extensions python3-pytest
# 可选，本目录的验证脚本会用到：
sudo apt install liburdfdom-tools ros-jazzy-tf2-tools
```

`liburdfdom-tools` 提供独立的 `/usr/bin/check_urdf`。source 完 ROS 2 后 `PATH` 里的 `check_urdf`
来自 `ros-jazzy-urdf`，两个都能用。

---

## 编译

包放在普通的 `ros2/` 目录里，不在工作空间的 `src/` 下。两种编法：

### 软链接进工作空间（推荐）

保持单一出处，也避免在 `/mnt/e` 这类慢/共享文件系统上编译：

```bash
mkdir -p ~/ws_wamoduck/src
cd ~/ws_wamoduck
for p in wamoduck_msgs wamoduck_description wamoduck_ros2; do
  ln -sfn /path/to/Wamoduck/ros2/$p src/$p
done

source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

`wamoduck_description/CMakeLists.txt` 会**先解符号链接**再往上找 `models/wmduck`，所以软链接布局和
就地编译用的是同一个默认值。

### 就地编译

```bash
cd /path/to/Wamoduck/ros2
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash
```

### 只把 `ros2/` 拷到这台机器的情况

`wamoduck_description` 刻意不自带 URDF，所以它需要模型目录。要么把 `models/wmduck/` 一起拷过来，要么
指给编译：

```bash
colcon build --packages-select wamoduck_description \
  --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
```

`wmduck.urdf` 或网格目录缺失时，编译会带上这句提示**直接失败**，而不是装出一个"看着是空的机器人"的描述包。

### 编译成功的标志

```
Starting >>> wamoduck_description
Starting >>> wamoduck_msgs
Starting >>> wamoduck_ros2
...
Summary: 3 packages finished [21.6s]
```

**如果 `colcon list` 显示的是 `wamoduck_ros2 (python)` 而不是 `(ros.ament_python)`，请停下来查。**
那说明 `package.xml` 没有被当成 ROS 清单解析，colcon 不会为该前缀生成任何 ROS 环境，
`ros2 launch` 永远找不到这个包。最常见的原因就是 XML 文本里有个没转义的 `<`。
`wamoduck_ros2/test/test_package_manifests.py` 就是为了兜住这一类错误——因为**编译在这两种情况下都会成功**。

---

## 运行

### 1. 先看看机器人长什么样

```bash
ros2 launch wamoduck_description display.launch.py
```

`robot_state_publisher` + `joint_state_publisher` + RViz。所有可动关节都在 0 位，也就是 CAD 站姿
——因为契约里的 `default_joint_pos` 就是全 0。

常用参数：

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `rviz` | `true` | 设 `false` 就是纯无头启动 |
| `use_gui` | `false` | 用 `joint_state_publisher_gui` 拖关节滑块 |
| `use_joint_state_publisher` | `true` | 有别的节点占用 `/joint_states` 时设 `false` |
| `rviz_config` | `<share>/rviz/wamoduck.rviz` | Fixed Frame 是 `base_link` |
| `urdf_file` | 生成的 URDF | 换成别的描述 |

### 2. 看它按参考步态动

```bash
ros2 launch wamoduck_ros2 gait_display.launch.py
```

这一条命令就是全部：`gait_player` 读 `share/wamoduck_ros2/data/gait_cycle_2s_50Hz.csv` 并按文件
自己的采样率发 `sensor_msgs/JointState`，`robot_state_publisher` 把它变成 TF，RViz 画出来。CSV 里的
`base_x`/`base_y`/`base_z`/`base_roll_rad` 会作为 `world -> base_link` 广播出去，所以
`gait_display.launch.py` 会自动选 `wamoduck_world.rviz`（Fixed Frame 为 `world`）。

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `csv_path` | 已安装的 `gait_cycle_2s_50Hz.csv` | 换别的轨迹，例如 `gait_walk_1m_10Hz.csv` |
| `loop` | `true` | 循环播放 |
| `time_scale` | `1.0` | 播放速率倍数 |
| `start_delay_s` | `1.0` | 等 RViz 载完网格再出第一个采样 |
| `publish_base_tf` | `true` | 设 `false` 时 RViz 也会自动切回 Fixed Frame `base_link` |
| `rviz` | `true` | 设 `false` 只跑步态播放 |

两个参考轨迹都是**准静态运动学 IK 规划**，不是实机日志，也不是训练策略的输出：两者
`step_len = 0.01 m`、`speed = 0.01 m/s`。播放节点会自己打印实测频率，时序可以核对而不是靠相信。

### 3. 单独跑节点

```bash
# 无显示器的步态回放
ros2 run wamoduck_ros2 gait_player --ros-args -p csv_path:=/abs/path.csv

# 同样的事，方便写法；--loop 不是 ROS 参数，会被剥掉
ros2 run wamoduck_ros2 gait_player --loop

# 协议桥，loopback 传输，不需要任何硬件
ros2 run wamoduck_ros2 bridge_stub

# 策略环（骨架：只拼观测，不做推理）
ros2 run wamoduck_ros2 policy_node
```

### 4. 看看线上有什么

```bash
ros2 topic echo /joint_states --once
ros2 topic hz /joint_states
ros2 topic echo /tf --once
ros2 run tf2_tools view_frames          # 需要 graphviz
```

---

## 46 字节链路，一页说完

`wamoduck_ros2/frame_codec.py` 实现的是部署协议 v1，与内部工程树里的参考实现线级兼容；它刻意不含
ROS，所以不依赖 ROS 图或硬件就能测。

```
SOF(0xA5) | TYPE | LEN | SEQ | PAYLOAD | CRC16(TYPE..PAYLOAD)
   1 B      1 B    1 B   1 B     LEN B          2 B
```

CRC 是 **CRC16-CCITT-FALSE**（poly `0x1021`、init `0xFFFF`、不反转、不异或输出）；测试里钉死了
`CRC16-CCITT-FALSE(b"123456789") == 0x29B1`。因为 CRC 变体选错**只会在线上暴露**，而且看起来和
"线缆有噪声"一模一样。所有多字节整数都是小端。

| 方向 | TYPE | 名称 | 负载 | 帧长 | 频率 |
| --- | --- | --- | ---: | ---: | --- |
| 头 → 小脑 | `0x01` | `CMD` | 40 B：`mode, flags, t_ms, q[14] i16, twist[3] i16` | **46 B** | 50 Hz |
| 头 → 小脑 | `0x02` | `ESTOP` | 空 | 6 B | 事件 |
| 小脑 → 头 | `0x81` | `STATE_Q` | 32 B：`age_ms, q[14], status` | 38 B | 200 Hz |
| 小脑 → 头 | `0x82` | `STATE_DQ` | 32 B：`age_ms, dq[14], status` | 38 B | 200 Hz |
| 小脑 → 头 | `0x83` | `STATE_IMU` | 24 B：`age_ms, gyro[3], acc[3], quat[4] wxyz, status` | 30 B | 200 Hz（可选） |
| 小脑 → 头 | `0x84` | `EVENT` | 4 B：`code, arg` | 10 B | 事件 |

上行每轮 106 B，200 Hz 时 21.2 kB/s，是 921600 8N1 的 23%。每个负载都 ≤ 64 B，所以同一套帧格式
可以一帧一条直接改走 CAN-FD，传输层以上一行都不用改。

定点比例：`q` rad→mrad ×1000、`dq` rad/s→0.01 ×100、`gyro` ×100、`acc` ×100、`quat` ×30000、
`twist` m/s→mm/s ×1000 与 rad/s→mrad/s ×1000。超范围的值**饱和**，绝不回绕。

**数组顺序。** `q` 与 `dq` 永远是**关节树顺序**，也就是 `model_contract.JOINT_ORDER` 里的 14 关节顺序，
它同时是策略观测里 `joint_pos`/`joint_vel` 的顺序，**也是策略自己那 14 维输出的顺序**。因此
"动作 → 关节"的置换就是恒等置换，它仍然只在主机侧施加一次，位置是
`policy_interface.action_to_joint_target()`。

本项目里同时存在**三套关节顺序**，混淆它们是已知的坑。代码把它们分开，并且
`test_model_contract.py` 专门断言 URDF 的文档顺序**不同于**契约顺序——这样将来有人"整理"顺序时会
测试失败，而不是悄悄接错一根关节：

| 顺序 | 出处 | 内容 |
| --- | --- | --- |
| 关节树顺序 | `JOINT_ORDER`，14 个 | `left_hip_yaw, left_hip_roll, …, left_ankle, right_hip_yaw, …, head_roll` |
| 执行器顺序 | MJCF `<actuator>`，14 个 | 按关节种类左右交错；**不是**动作顺序——`action_to_joint` 是恒等置换 |
| URDF 文档顺序 | `models/wmduck/wmduck.urdf`，15 个 | 左右交错，且多一个 `mouth` |

动作顺序已于 **2026-09-16 裁决**为关节树顺序。本模块此前按执行器顺序解读动作向量；四条互相独立的
证据定了案：mjlab 自己的解析器在训练 MJCF 上返回 `target_ids = [0 … 13]`；每个已发布策略的 ONNX
元数据里 `joint_names` 都是树序；一次 one-hot 的 MuJoCo 探针逐个驱动动作通道时，动的正是
`JOINT_ORDER[i]` 且只有它；以及观测顺序 × 动作顺序的 2×2 消融里，只有树序／树序还能站、能走、
能蹲起、能起身。详见 [`model_contract`](wamoduck_ros2/wamoduck_ros2/model_contract.py) 的模块文档。

`gait_player` 的关节表是**从 URDF 里读的**，CSV 列是**按名字**匹配的，它自己一个顺序都不写死。它发布
全部 15 个可动关节（含 `mouth`，14 关节的策略契约不用它）——那是对描述包最诚实的可视化，不改变策略观测到什么。

---

## 策略契约

`wamoduck_ros2/policy_node.py` 是**骨架**：只拼观测，什么都不发，因为 `onnxruntime` 没装、这棵代码树里
任何机器都没加载过策略。真正实现并且有单元测试的是**契约**。

观测向量，按 ONNX 输入顺序，行走任务是 **51** 维：

```
offset  0  base_ang_vel        3   rad/s，IMU 陀螺，机体系
offset  3  projected_gravity   3   单位向量；直立时 = (0, 0, -1)
offset  6  joint_pos          14   rad，相对 default_joint_pos（而它全 0）
offset 20  joint_vel          14   rad/s
offset 34  last_action        14   上一帧策略原始输出，**未乘** action_scale
offset 48  command             3   (vx, vy, wz)，限幅到 x[-0.6,1.0] y[-0.3,0.3] wz[-0.8,0.8]
------------------------------------------------------------------------------
合计                          51
```

**站立**任务训练时是 **48** 维：同样的布局，去掉末尾的 `command` 块。48 和 51 不可互换。

* **归一化在 ONNX 图里面**（`normalizer_inside_onnx: true`），所以主机侧喂**原始**观测。设备侧再归一化
  一次等于把变换做了两遍——这是"训练挺好、站得挺差"最经典的成因。
* 动作是 14 维**关节树顺序**，与观测同一个顺序；`action_to_joint` 只在主机侧施加一次，且是恒等置换。
* `q_target[joint] = default_joint_pos[joint] + action_scale * action[joint]`，其中
  `default_joint_pos` 全 0、`action_scale` 为 1.0，所以实际就是 `q_target = action`。
* 时序：**50 Hz**，MuJoCo `timestep = 0.005 s`，`decimation = 4` ⇒ `0.005 × 4 = 0.02 s`。
* 状态类话题用 **BEST_EFFORT + KEEP_LAST(1)**。如果是 RELIABLE 且队列更深，某次回调慢一下就会在队列里
  积压旧状态，策略拿着滞后几十毫秒的观测推理；症状是"迟钝、振荡"，事后极难查。
* 启动顺序：bridge 与 safety 先起，policy 最后起。policy 没就绪时小脑靠看门狗停在 HOLD/OFF
  （200 ms → HOLD，1000 ms → OFF），**这是刻意的默认值**。

---

## 验证状态

以下全部跑在 **WSL2 Ubuntu 24.04（x86_64）** + ROS 2 **Jazzy**。证据文件在
[`verification/`](verification/)，具体命令见 [`verification/README.md`](verification/README.md)。

| # | 检查项 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | `colcon build` | **通过** —— 3 个包，0 失败，`Summary: 3 packages finished [21.6s]` | `verification/colcon_build_log.txt` |
| 2 | `robot_state_publisher` + `gait_player`，`ros2 topic echo /joint_states --once` | **通过** —— 49.998–50.001 Hz，15 个关节名且顺序等于 URDF 文档顺序，数值非零且有限 | `verification/runtime_verification_log.txt` |
| 3 | RViz 渲染描述包 | **通过** —— 无头 Xvfb + llvmpipe 截图，WSLg 下也拿到了截图 | `verification/rviz_gait_xvfb.png`、`verification/rviz_gait_wslg.png` |
| 4 | URDF 能解析，且几何位置正确 | **通过** —— 两个 URDF 都过 `check_urdf`，并在 q=0 做正运动学与已发布的 `validation.json` 对比（吻合到 3.1e-9 m） | `verification/description_check.json` |
| 5 | 46 B 帧编解码往返、CRC 已知向量、重同步、饱和 | **通过** —— `colcon test` 与直接 `pytest` 共 87 个测试全过 | `verification/static_verification_log.txt` |
| 6 | `policy_node` 的 ONNX 推理 | **未运行** —— 骨架，未装 `onnxruntime` | `policy_runner.py` 文档字符串 |

两张截图是同一台机器人在**不同步态相位**下的画面，中间隔了约一分钟、`loop:=true` 一直在跑，
这本身就是"轨迹在循环回放"的证据。

### 明确未验证的事

* **ARM64 / RDK X5。** 这里所有结果都来自 **WSL2 里的 x86_64 Ubuntu 24.04**。X5 的 ARM64 用户态上
  **没有编译过、也没有运行过**，**可用性属于未验证**。包本身是纯 Python 加一个消息接口，移植预计不会
  有波折，但"预计"不是"已验证"。
* **硬件。** 没有串口、没有 CAN、没有 AT32、没有 IMU、没有电机。`bridge_stub` 的 `serial` 传输从未
  打开过，`can` 传输根本没写（它会直接报错，而不是起一个什么都不做的桥）。
* **`policy_node` 端到端。** 没加载过 ONNX、没跑过推理、没和 MuJoCo rollout 比对过输出。
* **`wmduck_safety`**（看门狗、急停汇聚、`/diagnostics`）未编写。小脑侧保护层（200 ms HOLD、
  1000 ms OFF、单帧 0.35 rad、限位夹取）写在协议规范里、实现在固件侧；主机侧**刻意不重复实现**
  ——两个超时不同的看门狗比一个好不了，只会更糟。
* **任何动力学。** 第 2 段没有物理。参考步态是运动学 IK 规划。
* **Gazebo 与 MoveIt。** 未开工。
* **WSLg 下的 RViz。** RViz 在 WSLg 下能起来，但 WSLg 的窗口内容无法用 `import`/`xwd` 回读（根窗口）；
  本次改为按窗口 id 截取客户端窗口并成功拿到 1400×900 的渲染图。截图证据见 `verification/README.md`。

---

## 部署到 RDK X5

目标：X5 上的 Ubuntu 22.04/24.04 ARM64，Linux 侧通过 `/dev/ttyS1` 或 CAN-FD 与 AT32 小脑通信。

1. **在 X5 上装 ROS 2。** 发行版要和 X5 的 Ubuntu 版本对上。本目录是用 24.04 + Jazzy 编译验证的。

   ```bash
   sudo apt install ros-jazzy-ros-base ros-jazzy-robot-state-publisher
   ```

   只有 X5 要接显示器时才需要 `ros-jazzy-rviz2`。

2. **拷源码和模型。** 要么整库 clone，要么把 `ros2/` 连同 `models/wmduck/` 一起拷：

   ```bash
   rsync -a ros2/ x5:/opt/wamoduck/ros2/
   rsync -a models/wmduck/ x5:/opt/wamoduck/models/wmduck/
   rsync -a tools/matlab/data/ x5:/opt/wamoduck/tools/matlab/data/
   ```

   第三行不能省：`wamoduck_ros2` 是从那里安装步态 CSV 的。省了也不会编译失败（只会警告），
   但 `gait_player` 就必须显式给 `csv_path`。

3. **在 X5 上本机编译。** 原生 ARM64 编译，`colcon build` 够了，包很小。

   ```bash
   mkdir -p ~/ws/src && cd ~/ws
   ln -sfn /opt/wamoduck/ros2/wamoduck_msgs src/
   ln -sfn /opt/wamoduck/ros2/wamoduck_description src/
   ln -sfn /opt/wamoduck/ros2/wamoduck_ros2 src/
   source /opt/ros/jazzy/setup.bash
   colcon build --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
   source install/setup.bash
   ```

   目录结构保持一致、且 `src/` 下是软链接时，不加 `-DWAMODUCK_MODELS_DIR` 也行——描述包会先解符号
   链接再往上找 `models/wmduck`。

4. **启动顺序**（`docs/16` §6.5 第 4 点）：bridge 与 safety 先起，policy 最后起。

   ```bash
   ros2 run wamoduck_ros2 bridge_stub --ros-args -p transport:=serial -p port:=/dev/ttyS1
   # …… 等状态流健康之后：
   ros2 run wamoduck_ros2 policy_node --ros-args -p onnx_path:=/opt/wamoduck/policies/....onnx
   ```

   50 Hz 关节环上，`docs/16` §6.5 建议 policy 与 bridge 走同一进程 + 进程内通信（或者干脆写在一个
   节点里），省掉 DDS 往返。这里两者是两个可执行文件，所以这一步集成**还没做**。

5. **在让它驱动任何关节之前**，先把 `docs/16` §5 的标定清单做完：逐关节零偏与方向、实测限位、IMU 轴系
   映射、五参数增益标定。`policy_contract.json` 里的 `calibration` 块是占位全 0，并且
   `q = 0` 是 CAD 姿态，**不是**编码器零位。

---

## 排错

| 现象 | 原因 |
| --- | --- |
| `colcon build` 成功，但 `package 'wamoduck_ros2' not found` | `package.xml` 不是合法 XML，colcon 把它归类成了普通 `python`。看 `colcon list`，必须是 `(ros.ament_python)`。 |
| RViz 里机器人是空的 | 网格引用不是 `package://`。跑 `tools/verify_description.py`，它会用任意工作目录去检验这件事。 |
| 编译报 "canonical URDF not found" | 只拷了 `ros2/`。加 `-DWAMODUCK_MODELS_DIR=...`。 |
| 编译报 "'data_files' must be relative" | colcon 断言 `data_files` 的源必须是相对路径；`setup.py` 因此用 `os.path.relpath` 转换步态 CSV 路径。 |
| RViz 里机器人只有一个小点 | `.rviz` 里的 `Views` 块把轨道距离设成了 0.85–1.0 m；RViz 默认的 10 m 对 0.39 m 的机器人太远。 |
| 改了 `.rviz` 好像没生效 | 配置是安装期拷到 `share/` 的，必须重编译。用 `colcon build --symlink-install` 可以免掉这一步。 |
| `gait_player` 警告某个 URDF 关节没有对应列 | CSV 与 URDF 不一致，警告里点名了关节。它按 0.0 发布，而不是悄悄丢掉。 |

## 许可

MIT，版权 © 2026 Wamotech —— 与仓库其余部分一致。见 [`../LICENSE`](../LICENSE)。
