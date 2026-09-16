# Wamoduck policies / 策略权重

[English simulation guide](../docs/simulation.md) · [中文仿真指南](../docs/simulation.zh-CN.md)

Five trained policies, exported from the training run that produced them. Each is an ONNX actor for one
task; run them with [`wamoduck_sim.py`](../wamoduck_sim.py) and the MJCF in
[`models/wmduck/mjcf/`](../models/wmduck/mjcf/). / 五个训练好的策略，均由产出它们的训练轮次导出。每个都是
某一任务的 ONNX actor；请配合 [`wamoduck_sim.py`](../wamoduck_sim.py) 与
[`models/wmduck/mjcf/`](../models/wmduck/mjcf/) 里的 MJCF 运行。

| File / 文件 | Bytes | SHA-256 | Source run / 来源轮次 | Checkpoint / 检查点 | Task / 任务 |
| --- | ---: | --- | --- | --- | --- |
| [wamoduck-stand-stand_v3.onnx](wamoduck-stand-stand_v3.onnx) | 766915 | `3ec3397ae9c17743ee4214234864da392562f7550ca7459ef1bd09dd2f44262f` | `2026-09-12_08-32-26_stand_v3` (SHIP) | `model_1499.pt` | stand / 站立抗扰 |
| [wamoduck-getup-getup_v18.onnx](wamoduck-getup-getup_v18.onnx) | 766915 | `804d2cee90881d6eb4756f9306d27bd3e19c8e9aa3f903bec65089787e323bf5` | `2026-09-15_17-37-06_getup_v18` | `model_3999.pt` | get up / 起身 |
| [wamoduck-sitstand-sit_stand_v2.onnx](wamoduck-sitstand-sit_stand_v2.onnx) | 768992 | `26e40f7a20f333c52816e53cb092b945f677c526d8f1685bf886d321c21a680d` | `2026-09-12_11-18-34_sit_stand_v2` (SHIP) | `model_2499.pt` | sit / stand |
| [wamoduck-walk-walk_v4r.onnx](wamoduck-walk-walk_v4r.onnx) | 773096 | `ff1379550b1c107ab1287dd85627466dae235580e96da8e4d1b77033305d393d` | `2026-09-16_12-01-21_walk_v4r` | `model_6000.pt` | walking / 平地行走 |
| [wamoduck-rough-rough_v2.onnx](wamoduck-rough-rough_v2.onnx) | 773096 | `811d79ea78a0ba3d349f5b7709fe6ffaf382c3929d61b13f47b43a0fac4a425b` | `2026-09-16_00-00-04_rough_v2` | `model_5999.pt` | 1 cm terrain / 1 cm 越障 |

The runs were resolved with the development repository's `tools/run_select.py`, not by picking a file by
hand. Each published file was then confirmed to be the export of exactly the checkpoint named above, by
rebuilding the actor from the `.pt` file and comparing it with the ONNX initializers. / 轮次是用研发仓库的
`tools/run_select.py` 解析出来的，不是手工挑的文件。随后每个公开文件都用 `.pt` 重建 actor 与 ONNX 权重逐项
比对，确认它确实就是上表写明的那个检查点导出的。

## Contract / 契约

| Item / 项目 | Value / 取值 |
| --- | --- |
| ONNX input / 输入 | `obs`, float32, `[1, N]` with N = 48 / 49 / 51 |
| ONNX output / 输出 | `actions`, float32, `[1, 14]` |
| Control rate / 控制频率 | 50 Hz (`decimation = 4` × `timestep = 0.005 s`) |
| Observation normalizer / 观测归一化 | **Inside the ONNX** — feed raw observations, never normalize again / **已含在 ONNX 内** —— 喂原始观测，绝不要再归一化 |
| Action → target / 动作换算 | `q_target = default_joint_pos + 1.0 × action`, `default_joint_pos` is 14 zeros / 为 14 个 0 |
| Action clipping / 动作截断 | none in the policy; MuJoCo clamps `ctrl` to `ctrlrange` / 策略侧无截断；MuJoCo 按 `ctrlrange` 截断 |
| Joint order / 关节顺序 | joint-tree order (left leg, then right leg, then neck/head) — **not** the MJCF actuator order / 关节树顺序，**不是** MJCF 执行器顺序 |

The full observation layout, offsets, and the evidence behind the joint-order and normalizer statements are
on the [simulation page](../docs/simulation.md) / [仿真页](../docs/simulation.zh-CN.md).

## Verify them yourself / 自己验一遍

```bash
python wamoduck_sim.py --check --policy stand      # also: getup, sitstand, walk, rough
```

This checks the ONNX input/output shape against the task contract, re-derives the observation blocks against
MuJoCo, and confirms the graph contains the normalizer.

## Scope / 范围

These files are the trained actors, published so the policies can be run and inspected. They are **not** a
hardware deployment package: motor calibration, encoder signs and zeroes, CAN IDs, timing, and safety limits
are not solved here, and no policy in this repository has been validated on a physical robot. / 这些文件是训练
出来的 actor，公开出来是为了让策略能被运行与检查。它们**不是**硬件部署包：电机标定、编码器方向与零位、CAN ID、
时序与安全限幅都没有在这里解决，本仓库里的任何策略都没有在实物机器人上验证过。
