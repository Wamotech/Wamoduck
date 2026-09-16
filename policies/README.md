# Wamoduck policies / 策略权重

[English simulation guide](../docs/simulation.md) · [中文仿真指南](../docs/simulation.zh-CN.md)

Five trained tasks, and six ONNX actors: the sit/stand row carries **two** files, because the 2026-09-16
replacement is published next to the file whose measured problems it fixes. Each is an ONNX actor for one
task; run them with [`wamoduck_sim.py`](../wamoduck_sim.py) and the MJCF in
[`models/wmduck/mjcf/`](../models/wmduck/mjcf/). / 五个训练任务、**六个** ONNX actor：坐／站那一行有**两份**
文件 —— 2026-09-16 的替换版本与"被它修掉的那两个实测问题所属的旧版"一起保留。每个都是某一任务的
ONNX actor；请配合 [`wamoduck_sim.py`](../wamoduck_sim.py) 与
[`models/wmduck/mjcf/`](../models/wmduck/mjcf/) 里的 MJCF 运行。

| File / 文件 | Bytes | SHA-256 | Source run / 来源轮次 | Checkpoint / 检查点 | Task / 任务 |
| --- | ---: | --- | --- | --- | --- |
| [wamoduck-stand-stand_v3.onnx](wamoduck-stand-stand_v3.onnx) | 766915 | `3ec3397ae9c17743ee4214234864da392562f7550ca7459ef1bd09dd2f44262f` | `2026-09-12_08-32-26_stand_v3` (SHIP) | `model_1499.pt` | stand / 站立抗扰 |
| [wamoduck-getup-getup_v18.onnx](wamoduck-getup-getup_v18.onnx) | 766915 | `804d2cee90881d6eb4756f9306d27bd3e19c8e9aa3f903bec65089787e323bf5` | `2026-09-15_17-37-06_getup_v18` | `model_3999.pt` | get up — **superseded, kept for the measurements below** / 起身 —— **已被取代**，保留用于复现那些测量 |
| [wamoduck-getup-getup_v20.onnx](wamoduck-getup-getup_v20.onnx) | 766915 | `29bbebd0d6597a1f425305c90fc29a1b71c79e066a26ae44c20e1fab3a3fbed6` | `2026-09-16_19-12-01_getup_v20` | `model_3999.pt` | get up — **current**; returns to the nominal stance / 起身 —— **当前版**；能站回标称姿态 |
| [wamoduck-sitstand-sit_stand_v2.onnx](wamoduck-sitstand-sit_stand_v2.onnx) | 768992 | `26e40f7a20f333c52816e53cb092b945f677c526d8f1685bf886d321c21a680d` | `2026-09-12_11-18-34_sit_stand_v2` (SHIP) | `model_2499.pt` | sit / stand — **superseded, kept for the measurements below** |
| [wamoduck-sitstand-sit_stand_v3.onnx](wamoduck-sitstand-sit_stand_v3.onnx) | 768992 | `c75139732aa2890964f56a5df78b8c8c351d2fea88533ac5b1fb78aba6574163` | `2026-09-16_18-05-44_sit_stand_v3` | `model_2499.pt` | sit / stand — **current**; fixes both problems measured on v2 |
| [wamoduck-walk-walk_v4r.onnx](wamoduck-walk-walk_v4r.onnx) | 773096 | `8ec4fd347a22d69937550681e58e6d2cd511748b067677bcef345fdae5546ea2` | `2026-09-16_12-01-21_walk_v4r` | `model_6749.pt` | walking / 平地行走 |
| [wamoduck-rough-rough_v2.onnx](wamoduck-rough-rough_v2.onnx) | 773096 | `811d79ea78a0ba3d349f5b7709fe6ffaf382c3929d61b13f47b43a0fac4a425b` | `2026-09-16_00-00-04_rough_v2` | `model_5999.pt` | 1 cm terrain / 1 cm 越障 |

The runs were resolved with the development repository's `tools/run_select.py`, not by picking a file by
hand. Each published file was then confirmed to be the export of exactly the checkpoint named above, by
rebuilding the actor from the `.pt` file and comparing it with the ONNX initializers. That comparison is a
tool, not a one-off: `tools/verify_onnx_provenance.py --onnx <file> --run <run> --expect <checkpoint>`
reports the exact match over every `model_*.pt` in the run and exits non-zero otherwise (its `--selftest`
proves the criterion accepts the right checkpoint and rejects a perturbed one). For a byte-identical
export the element-wise difference is exactly zero, which is what all five rows above report. / 轮次是用研发
仓库的 `tools/run_select.py` 解析出来的，不是手工挑的文件。随后每个公开文件都用 `.pt` 重建 actor 与 ONNX 权重逐项
比对，确认它确实就是上表写明的那个检查点导出的。这个比对已经做成了工具（见上），它对轮次目录里的每个
`model_*.pt` 报出精确匹配、否则以非零码退出；导出是纯拷贝，所以逐元素差**恰好为 0** —— 上表五行都满足。

> **A note on the walking row / 关于行走那一行**：this file was first published as `model_6000.pt`, taken
> from the run directory while training was **still running** — mjlab rewrites that directory's ONNX on
> every checkpoint save, so the copy captured a mid-run save and the run's final save (`model_6749.pt`,
> written 28 minutes later) never reached this repository. It has been replaced with the run's final
> checkpoint; both revisions are valid exports of the same run, and the file now matches the checkpoint
> this table names. Lesson recorded because it is a repeatable trap: **do not publish from a directory
> whose training is still in progress**, and verify provenance instead of trusting the file name. / 这个文件
> 最初是以 `model_6000.pt` 发布的：当时训练**还在跑**，而 mjlab 在每次保存检查点时都会重写轮次目录里的那份
> ONNX，所以拷走的是中途某一次保存，训练结束时（28 分钟后写入的 `model_6749.pt`）从未进过本仓库。现在已换成
> 该轮次的最终检查点；两版都是同一轮次的合法导出，只是现在这个文件与上表写明的检查点一致。把教训写在这里，
> 因为它是可复现的坑：**不要在训练还在进行时发布**，并且要核验来源，不要相信文件名。

> **A note on the sit/stand row / 关于坐／站那一行**：`sit_stand_v3` replaces `sit_stand_v2` and fixes both
> problems that the capability board measured on it. Standing jitter `mean|Δa|` **0.699 → 0.000** and net
> drift **+27.99 → +0.394 mm/s**; the sitting pose goes from a **10.05°** lean at 0.112 m (and **25.91°** at
> the old 0.085 m command) with left/right residuals of **146.09°** / **173.56°**, to a **0.225°** lean with
> a **0.473°** residual between the two legs. The seat is now **0.11241 m**, not 0.085 m: 0.085 m is
> **geometrically unreachable** while the trunk is upright, because the torso collision box's lowest corner
> sits **109 mm** below the base origin — the old policy only "reached" 0.094 m by leaning 25.9° to lift that
> corner clear of the floor. One measured limitation comes with the new pose: **switching to `walk` while
> seated collapses the robot** (tilt 134.9° after 6 s), because the walking policy has never seen a seated
> stance — press `m` first, which is what the bundled runner's self-test now does. / **`sit_stand_v3` 取代
> `sit_stand_v2`，修掉能力清单在旧版上实测到的两个问题**：站立抖动 `mean\|Δa\|` **0.699 → 0.000**、净漂移
> **+27.99 → +0.394 mm/s**；坐姿从"指令 0.112 m 时倾 **10.05°**（旧指令 0.085 m 时 **25.91°**）、左右腿残差
> **146.09°／173.56°**"变成"倾 **0.225°**、左右残差 **0.473°**"。坐高改为 **0.11241 m** 而不是 0.085 m：
> 躯干直立时 0.085 m **几何不可达** —— 躯干碰撞盒最低角点在基座原点下方 **109 mm**，旧策略能凑到 0.094 m
> 是靠歪 25.9° 把那个角抬离地面。新坐姿带来一条实测限制：**坐着直接切到 `walk` 会让机器人瘫倒**
> （6 s 后倾角 **134.9°**），因为行走策略从未见过坐姿 —— 先按 `m` 站起来，随仓库的运行器自检现在就是这么做的。

> **A note on the get-up row / 关于起身那一行**：`getup_v20` replaces `getup_v18` and closes the gap the
> capability board measured on it. Recovering from a random lying pose: standing at the end **64/64**,
> time to first standing **0.48 s** median, final tilt **2.5°**; the strict criterion "back to the saved
> nominal pose" goes **0/64 → 63/64 (98.4 %)** with the largest joint deviation **52.3° → 10.4°**, and the
> end-to-end hand-over (shoved over → gets up → back to nominal) is **5/5** with **5/5** "did not fall again"
> (v18 was 4/5 on that last row). The only change was in the reward: the head-chain posture penalty was
> **ungated** and its weight went **−0.5 → −1.0**; the previous round had gated it by body tilt, and the
> policy escaped through the gate by staying tilted — see the [changelog](../CHANGELOG.md). The stricter
> six-axis criterion (which also requires the head to stay off the ground and the soles to be flat, sustained
> over the last second) is **45/64**, up from **0/64**, with per-axis rates of 56/64, 52/64, 58/64, 61/64,
> 61/64 and 46/64 — where the "both feet" axis is itself read through a contact path this project has flagged
> as unreliable (60/64 there against 64/64 from the contact sensors), so it under-counts. v18 is kept so the
> measurements above stay reproducible. / **`getup_v20` 取代 `getup_v18`，
> 补上了能力清单在旧版上实测到的那条差距**：随机躺姿起身 —— 末态站住 **64/64**、首次站起时间中位
> **0.48 s**、末态倾角 **2.5°**；严格口径"回到保存的标称姿态" **0/64 → 63/64（98.4 %）**，最大关节偏差
> **52.3° → 10.4°**；端到端接力（推倒→起身→站回标称）**5/5**，其中"起身后没有再次摔倒"**5/5**（v18 在这一行
> 是 4/5）。唯一的改动在奖励侧：头链姿态惩罚**不加门控**、权重由 **−0.5 改到 −1.0** —— 上一轮给它加了"按
> 身体倾角生效"的门，结果策略靠**一直歪着**从门里逃了出去（见[更新记录](../CHANGELOG.md)）。更严的六轴
> 口径（还要求头不压地、脚掌平贴，并要求在最后一秒内持续成立）从 **0/64** 升到 **45/64**，逐轴为
> 56/64、52/64、58/64、61/64、61/64、46/64。v18 保留，好让上面的测量可复现。

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
