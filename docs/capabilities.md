# Measured capabilities / 实测能力清单

[Home](../README.md) · English | [简体中文](capabilities.zh-CN.md) · [Simulation guide](simulation.md) · [Roadmap](roadmap.md)

This page is one honest board of what the trained policies actually do. Every figure was measured in simulation on **2026-09-16**, and copied from a measurement log with the tool that produced it named beside it. Nothing here is extrapolated, estimated, or carried over from a different run without saying so. The parts that do not work are listed with the same weight as the parts that do.

**The short version:**

- **What works:** standing still while something shoves it, getting up after a knock-down, walking forwards, and walking over 1 cm curbs.
- **What does not work:** turning in place, and side-stepping — which also drags the robot round. And `getup` stands the robot up without returning it to the saved nominal pose. In-place turning is **not** a policy that was trained badly: it has since been measured to be **out of reach for this mechanism** — see [Why in-place turning cannot be trained away](#why-in-place-turning-cannot-be-trained-away).
- **What none of this is:** hardware. Every figure on this page came out of a simulator.
- Sit/stand gives interactive height control. It **had** two reported issues, both measured on CPU with the previous policy — it **buzzed in place while standing**, and its **sitting posture was neither upright nor left/right symmetric** — and both were **fixed on 2026-09-16** by `sit_stand_v3`, which is now the published sit/stand policy. See [section 6](#6-sit--stand).

**Scope: simulation only.** The policies run in a MuJoCo / mjlab environment on one laptop GPU, normally **64 parallel environments** per measurement (32 for the walking table), with the round named in each row. There are no hardware measurements on this page. The training code, the scene generator, the checkpoints, and the measurement tools live in the private development repository and are **not** published here — so this page reports measurements rather than offering a reproduction recipe. Re-measure before quoting it.

**Five of these policies are now published** as ONNX files, with the MJCF model they were trained on and a CPU runner — so their behaviour can be re-run, though **not** the measurement protocols behind the numbers below. See [Run the trained policies in MuJoCo](simulation.md) / [在 MuJoCo 里跑训练好的策略](simulation.zh-CN.md) for the observation and action contract, the joint ordering, our own CPU check results, and the parts that still do not work.

## Summary

| # | Capability | Policy | Headline result |
| --- | --- | --- | --- |
| 1 | Standing against a push | `stand_v3` (`model_1499.pt`, shipped) | Push threshold **40.5 N**; steady-state drift **0.00 mm/s** over 40 s |
| 2 | Knocked down → get up → back to nominal | `stand_v3` + `getup_v20` (`model_3999.pt`) | **5/5** trials end in the strict nominal stance, and **5/5** "did not fall again after standing up" (the previous get-up policy was 5/5 and 4/5) |
| 3 | Get-up from a random lying pose | `getup_v20` (`model_3999.pt`) | Standing at the end **64/64**; strict nominal criterion **63/64 (98.4 %)**, up from **0/64**, largest joint deviation **52.3° → 10.4°** |
| 4 | Flat-ground walking | `walk_r3` (`model_5999.pt`, shipped) | Forward tracking 106 % / 103 %; **side-stepping is broken**, and **in-place turning is out of reach for this mechanism** (not a training gap — see [§4](#why-in-place-turning-cannot-be-trained-away)) |
| 5 | 1 cm rough terrain | `rough_v2` (`model_5999.pt`) | Survival **51/64 (79.7 %)**; mean speed **61 %** of the command |
| 6 | Sit / stand | `sit_stand_v3` (`model_2499.pt`, shipped) | Interactive height control. The two issues measured on the previous policy are **fixed**: standing jitter **0.699 → 0.000** and drift **+27.99 → +0.394 mm/s**; the sitting pose goes from **10.05°** of lean with **146.09°** of left/right asymmetry to **0.225°** and **0.473°**. The seat is **0.11241 m** (0.085 m is geometrically unreachable) |

A policy marked *shipped* is the checkpoint the interactive demos load by default in the development repository. As of this release, five of the six rows also have a published ONNX file you can run yourself: `stand_v3`, `getup_v18`, `sit_stand_v2`, and `rough_v2` are the exact checkpoints on this page, while the published walking policy is `walk_v4r` rather than the `walk_r3` this page measured — see [row 4](#4-flat-ground-walking) and the [simulation guide](simulation.md).

## 1. Standing against a push

| Field | Value |
| --- | --- |
| Policy | `stand_v3`, `model_1499.pt` (shipped) |
| Measured | Drag the robot with the mouse and it finds its balance again. Over a 40 s quiet stand: base drift **0.00 mm/s**, path length **0.00 mm/s**, action jitter **mean abs(delta a) = 0.00000** |
| Push protocol | One horizontal shove of 0.2 s, fixed amplitude, random azimuth per environment, applied 0.05 m above the centre of mass with the moment arm included; the policy stays in the loop throughout; a fall means tilt > 60 deg or base height < 0.10 m |
| Measured threshold | 0 to 24 N: **0/64** fall. 32 N: 1.6 %. 40 N: **45.3 %**. 48 N: 89.1 %. 56 N: 96.9 %. Critical force (first amplitude with a fall rate >= 50 %) = **40.5 N** |
| Tools | `diagnose_stand_play.py` (steady state, 40 s) and `measure_push_threshold.py` (64 environments) |

![An ordinary push while standing; the robot stays on its feet](../assets/wamoduck-push-normal.gif)

*An ordinary push — it stays on its feet. Simulation screen recording, not hardware footage: it shows the standing policy `stand_v3` in MuJoCo, one selected take, not a test.*

Two disciplines are worth copying from this measurement. First, the training-side disturbance and the measuring-side shove are the same physical quantity — horizontal, fixed amplitude, azimuth random, moment arm included — because an earlier version compared two different quantities and produced a threshold that only looked measured. Second, every sweep starts with a **0 N control row**: if the robot cannot stand without a push, the run is declared invalid instead of reporting a threshold. That control row is what caught the first version of this tool, which stepped the simulator with zero actions and concluded that 8 N knocked the robot over 100 % of the time.

## 2. Knocked down, get up, back to nominal

| Field | Value |
| --- | --- |
| Policy | `stand_v3` + `getup_v20` (`model_3999.pt`), switched automatically by a small state machine. The previous get-up policy, `getup_v18`, is still in [`policies/`](../policies/README.md) because the gap recorded under section 3 was measured on it |
| Sequence | Shove it over → the get-up policy takes over → it stands up → the standing policy takes over and settles into the saved nominal pose |
| Measured (5 trials) | End-to-end, ending in the strict nominal stance: **5/5**. Final tilt **0.5 deg**, `neck_pitch` **0.3 deg**, largest joint deviation **1.9 deg**, both feet on the ground, base height **0.177 m** — the same five numbers in all five trials |
| Not as good | "Did not fall again after standing up": **5/5** with `getup_v20`. It was **4/5** with `getup_v18`: in one of those trials the hand-over dropped the robot five times before the final state passed |
| Tool | `probe_recovery_handover.py --trials 5` |

![Pushed over, then it stands back up and settles into the nominal stance](../assets/wamoduck-pushed-down-recover.gif)

*Pushed over, then recovers to the nominal stance. Simulation screen recording, not hardware footage: it shows `stand_v3` and `getup_v18` handing over inside MuJoCo, one selected take — the 5/5 and 5/5 above come from the 5-trial probe, not from this clip, and the clip predates the 2026-09-16 replacement of the get-up policy.*

![The hardest case: repeated attempts, finally getting up](../assets/wamoduck-getup-struggle.gif)

*The hardest case: repeated attempts, finally gets up. Simulation screen recording, not hardware footage: it shows `getup_v18` inside MuJoCo, the policy published before 2026-09-16. It is published precisely because it is not a clean take — the first attempts fail before it gets up, which matches that policy's "did not fall again after standing up 4/5".*

The full-length recording of this session — pushes, knock-downs, get-up attempts, and the hand-over, 1:49.37, 1280 × 716, no audio — is [wamoduck-force-test-demo.mp4](../assets/wamoduck-force-test-demo.mp4). It is one session, not a test campaign; the rates on this page come from the tools named in each row.

This is the requirement that matters most, because it is the only row that tests the two policies **together**: a nominal final pose that cannot survive the hand-over would not be a usable robot behaviour.

## 3. Get-up from a random lying pose

| Field | Value |
| --- | --- |
| Policy | `getup_v20`, `model_3999.pt` (current). The previous policy `getup_v18` measured **0/64** on the strict criterion below and is still published so that number stays reproducible |
| Setup | Spawned lying on the ground with random roll and pitch, 64 environments, 300 steps (6 s) |
| Measured | Reached standing at some point **64/64**; standing at the end **64/64** (loose criterion: tilt < 30 deg and base height > 0.15 m); median time to first standing **0.48 s**, p90 **0.79 s**; mean final tilt **2.5 deg** |
| Measured (strict) | Returning to the **nominal** stance (tilt < 8 deg, both feet on the ground, every joint within 20 deg of nominal): **63/64 (98.4 %)** — up from **0/64**. Mean largest joint deviation **10.4 deg** (max 11.8 deg), against **52.3 deg** for `getup_v18`; both feet 63/64 |
| 900-step acceptance | The get-up delivery criterion runs 900 steps and requires the criterion to hold rather than to happen once, and it adds two axes: the head must not press on the ground and the soles must be flat. At **256 environments**: all six together **206/256 (80.5 %)**, per axis tilt **239/256**, both feet **221/256**, joint deviation **237/256**, base height **255/256**, head off the ground **253/256**, flat soles **209/256** — up from **0/64** for `getup_v18` on the same criterion. At the **64**-environment setting used for the numbers above, the all-six figure reads **45/64 (70.3 %)** with the same per-axis shape (56/52/58/61/61/46): the per-axis rates are the stable part, and the all-six conjunction is sample-limited, so the larger run is the better estimate. `getup_v18` failed this one on `head_pitch` at **46 deg**, the second link of the head chain. **One caveat on the "both feet" axis**: it is read through `stand_criteria`, whose foot-contact path this project has flagged as unreliable (it infers contact counts from `nacon[0]`, a per-world array). Both runs cross-check it against the sensor path — **245/256** there against **256/256** from the contact sensors, **60/64** against **64/64** at 64 environments — so that axis under-counts; the two new axes do not use that path |
| Head chain on the ground | **0/64**, i.e. the head does not carry the robot. The round before that was 63/64 with **17.5 N** of ground reaction on the head, about 106 % of the head's own weight |
| Tools | `eval_getup.py --envs 64 --run getup_v20`, `check_getup_delivery.py --policy getup_v20 --envs 64 --steps 900`, `probe_recovery_handover.py --trials 5 --getup-run getup_v20` |

Read the two blocks together: the robot reliably gets up, reliably ends up standing, and — since 2026-09-16 — reliably ends up in the **saved nominal pose** as well. The fix was one reward term, not a new mechanism: the head-chain posture penalty is **ungated** and weighs **−1.0** (it was `−0.5` ungated before, and the round in between gated it by body tilt, which the policy escaped by staying tilted — that round measured **0/5** on the hand-over).

## 4. Flat-ground walking

Read this row with more care than the others, because **the numbers and the policy are not from the same round**.

| Field | Value |
| --- | --- |
| Shipped policy | `walk_r3`, `model_5999.pt`, trained 2026-09-12 under an older command range |
| Newest same-protocol table | `walk_v3`, `model_5999.pt` (2026-09-15/16, **not published**), body-frame commands, 32 environments, 500 steps (10 s) |
| Forward tracking | 0.3 m/s command → **106 %**; 0.5 m/s command → **103 %** |
| Side-stepping | Command +0.30 m/s → measured **+0.218 m/s** body-frame, but with **+520.4 deg** of uncommanded yaw and a forward drift of **-0.003 m** over the same 10 s. The sideways magnitude survived (the previous round measured +0.240 m/s) while the axis discipline collapsed, so this mode is **not usable** |
| Turn in place | Command 0.5 rad/s → **0.1 %** of the commanded yaw, i.e. **+0.3 deg** in 10 s. The robot does not turn on the spot — and this is a property of the mechanism, not of the training: see [Why in-place turning cannot be trained away](#why-in-place-turning-cannot-be-trained-away) |
| Walk and turn together | 0.4 m/s plus 0.5 rad/s → forward **109 %**, yaw **7 %** |
| Tool | `measure_twist_tracking.py --run walk_v3` |

Two warnings, both about honesty rather than capability:

- The shipped `walk_r3` checkpoint was trained under a different command range from the one the current configuration uses, so measurements of it under the current range are **not directly comparable** with the fresh table. Its behaviour is best judged by driving the interactive keyboard demo, not by quoting either table. Walking has since been retrained: `walk_v4r` reached its iteration limit of 6000 on 2026-09-16 and **its final checkpoint `model_6000.pt` is the walking policy published in this repository** — that ONNX is not the checkpoint this table measured.
- The ruler itself was replaced for this round. The old criterion used the net world-frame displacement, which cannot tell "cannot walk" from "walked in a circle"; the numbers above are body-frame integrals of the same quantity the training reward uses, and the tool validates itself against analytic trajectories before measuring anything.

What our own CPU check of the published `walk_v4r` policy shows, through the published
[simulation runner](simulation.md), is consistent with the two failures above: at a +0.30 m/s forward command it
travelled **1.482 m** of the commanded 1.500 m in 5 s and never fell, but drifted **0.328 m** sideways while
being commanded to go straight. That is a Sim2Sim check on plain CPU MuJoCo, not a re-measurement of this
table, and the two are not comparable.

### Why in-place turning cannot be trained away

The `Turn in place` row is not "a policy that did not learn". Before scheduling another training round for it, it was checked on **plain CPU MuJoCo**, on the unmodified MJCF the policies were trained in, with both feet planted. Three hard constraints bind, each with an analytic bound **and** a measured number from that same scene:

| Constraint | Why it binds | Analytic bound | Measured |
| --- | --- | --- | --- |
| Hip-yaw travel | With both feet planted and not sliding, equal and opposite yaw on the two legs is an **internal torque pair** — the net moment on the robot is zero — so it can only twist the torso **relative to the feet**, and only as far as one joint range allows | torso vs ground ≤ **0.532 rad = 30.5°** | foot slip **8.0°** plus torso **22.5°** = **30.5°** |
| Unloading one foot | A single-support turn needs the CoM ground projection inside one footprint (stance width **171.4 mm**, foot width **51.1 mm**) | CoM shift ≥ **59.8–60.2 mm** | the CoP equals the CoM projection to **0.000 mm**, so this requirement is exact |
| Shifting the CoM sideways | There is **no ankle roll**, so keeping the soles flat locks the roll of foot and shin; the only lever left is the torso rotating about the hip-roll axes | symmetric upper bound **35.3 mm**; one leg forced to its limit **76.0 mm** | symmetric **16.5 mm**; one side **38.5 mm**, but the robot is then tilted **28.5°** with hip roll saturated for **110 of 125** steps — the fall line is **30°** |

**No planted-foot driver accumulates.** Eleven drive patterns were run for 10 s each (triangle waves, sine scrubbing, scissoring, a four-phase ratchet, slow ramps into both end stops): the seven that stayed upright for the full 10 s reoriented the **feet in the world** by only **−12° to +8°** against a **286°** command, and every pattern that rotated further was on the ground within **0.96–1.22 s** (post-fall tumbling excluded). Lifting one foot does reach **0.000 N** of load, but only at the joint limits, at **28.47°** of tilt, for **0.8 %** of the time — that is falling onto one foot, not a controlled single support.

**Positive control, same ruler.** Through the published runner, at a yaw command with zero forward speed the second-half yaw rate is **0.00 deg/s** for all four walking checkpoints measured — not "small", zero. The yaw command only does anything once forward speed is commanded (**vx ≥ 0.20 m/s**).

**So the deliverable is restated.** Turning happens **while moving**. Measured with the published policy through the published runner (10 s runs, yaw command 0.5 rad/s = **28.6 deg/s**): at **0.10 and 0.15 m/s the robot does not walk at all** — **0.012–0.018 m** of travel in 10 s, with or without the yaw command — so at those speeds the question of tracking the yaw command does not arise. From **0.20 m/s** it does turn while walking: it tracked **62 % / 69 % / 75 %** of the command at 0.20 / 0.30 / 0.40 m/s, on arcs of **measured** radius **0.72 / 0.93 / 1.11 m** — larger than the **commanded** ratio vx / \|wz\| of 0.40 / 0.60 / 0.80 m, because the yaw command is under-tracked by exactly that factor. So the tightest arc we have **measured** is **R ≈ 0.7 m**, reached at **vx ≥ 0.20 m/s**. Standing still, the torso can be re-oriented **once** by up to **±30.5°** relative to the ground — enough to aim the head or a camera, but it does not accumulate. Making true in-place rotation real is a **hardware** change: an ankle-roll (or equivalent coronal-plane) degree of freedom so the legs can lean and the CoM can move ≥ 60 mm, or a waist yaw joint.

Reproducibility and self-check: plain MuJoCo on CPU, training MJCF unmodified, two independent runs producing **byte-identical** JSON, and the tool calibrates its own ruler before measuring anything (a box the size of the real sole, hinged about z, starts turning at **0.635 N·m**, giving an effective lever of **34.5 mm** inside the analytic bracket of 25.5–47.7 mm; it also checks that the CoP equals the CoM projection). The turning figures above come from the published runner on CPU, with a `wz = 0` straight-line control at every speed so that "did not turn" cannot be confused with "did not move", and with the yaw angle integrated step by step rather than read off the endpoints.

## 5. 1 cm rough terrain

| Field | Value |
| --- | --- |
| Policy | `rough_v2`, `model_5999.pt` |
| Setup | Generated terrain with 1 cm curbs and 1 cm step-downs, difficulty rows 0 to 5; 64 environments, 600 steps (12 s), forward command +0.30 m/s; curricula disabled so the difficulty row cannot change mid-measurement |
| Measured | Survived to the end **51/64 (79.7 %)**; mean forward speed **+0.183 m/s = 61 %** of the command; moved forward by more than 0.1 m in **53/64**; median / p90 max tilt **7.7 / 8.3 deg** |
| Hard rows only | On difficulty rows 3 and above (n = 33): survived **24/33**, mean speed **+0.157 m/s** |
| Tool | `eval_rough.py --envs 64` (round `rough_v2`) |

The 61 % is a real loss of speed, and it is measured against the commanded speed, not against the policy's flat-ground speed. **No flat-ground control run was made in the same batch**, so this page does not attribute the loss to the terrain alone.

**Our own CPU control, added 2026-09-16, separates two things that this row had left together.** Running the published policy in the bundled runner — CPU MuJoCo, 600 control steps (12 s), `vx = +0.30 m/s`, commanded **3.600 m** — on a flat floor and over 3 consecutive 1 cm curbs:

| Setup | Forward travel | Of the command |
| --- | --- | --- |
| Flat floor (`--terrain-level 0`) | **+3.458 m** | **96.1 %** |
| 3 consecutive 1 cm curbs (`--terrain-level 3`) | **+3.316 m** | **92.1 %** |

So in this runner's own setup the curbs cost about **4 percentage points**, not 39. That does **not** overturn the 61 % above: that number comes from the development repository's **generated** terrain at difficulty rows 0–5 (denser, with step-downs), which is harder than three hand-placed curbs, and it was measured in a different simulator with a different protocol. What it does show is that the loss is **specific to the harder terrain**, rather than the policy being unable to hold speed whenever the ground is uneven. The two runs are ours, on CPU, and are not a re-measurement of the internal batch.

## 6. Sit / stand

| Field | Value |
| --- | --- |
| Policy | `sit_stand_v3`, `model_2499.pt` (shipped). The previous policy, `sit_stand_v2`, is still in [`policies/`](../policies/README.md) because the two problems below were measured on it |
| Control | One key toggles between sitting and standing; two more keys raise and lower the target height |
| Setup | The delivery criterion is **seven axes** with thresholds fixed before the measurement: jitter `mean\|Δa\|` ≤ 0.05 rad, net drift ≤ 1.0 mm/s, path length rate ≤ 5.0 mm/s, height std ≤ 2.0 mm, tilt std ≤ 1.0°, final tilt ≤ 8.0° standing, and (sitting) final tilt ≤ 8.0°, height error ≤ 10 mm, left/right mirror residual ≤ 5.0°, both feet down with the CoM inside the support polygon for ≥ 90 % of the last second, and the commanded height must be geometrically reachable. Every run carries a 0 N control group and a static reference group whose jitter must read exactly 0 |
| Measured, standing (0.175 m) | Final height **0.1725 m** (error 2.5 mm), tilt **1.10°**, jitter **0.000**, net drift **+0.394 mm/s**, path **0.394 mm/s**, height std **0.021 mm**, tilt std **0.042°** — **J1–J5 pass** |
| Measured, sitting (0.11241 m) | Final height **0.1095 m** (error 2.9 mm), tilt **0.225°**, left/right residual **0.473°** (largest pair: the knees at 0.47°), both feet down with the CoM inside the support polygon **100 %** of the last second — **S1–S5 pass** |
| Measured, the old 0.085 m command | The policy fails all five sitting axes, and that is the point: **0.085 m is geometrically unreachable** while the trunk is upright — the torso collision box's lowest corner is **109 mm** below the base origin, so the base cannot go below 0.109 m without the torso entering the floor. The axis that reports this is separate from the four that judge the policy, so "the command is impossible" and "the policy cannot do it" are not confused |
| Tools | `check_sit_stand.py --policy sit_stand_v3 --heights 0.175,0.11241,0.085 --render` (CPU only, no GPU) |
| **Fixed on 2026-09-16** | A user playing the published demo reported that `sitstand` **buzzed in place while standing**, and that sitting down did not produce the pose the report described as "head and torso vertical to the ground, left and right legs braced symmetrically". Both were measured; both are now **fixed**. The measurements that found them are kept below as the baseline, and the before/after pairs are jitter **0.699 → 0.000**, drift **+27.99 → +0.394 mm/s**, sitting tilt **10.05° → 0.225°**, left/right residual **146.09° → 0.473°** |
| **One new limitation** | The **seated pose is not a stance the walking policy can start from**: switching to `walk` while seated collapses the robot — tilt **134.9°** after 6 s with **0.438 m** of travel. Stand up with `m` first. The bundled runner's `--cycle-test` now performs that sequence, and asserts the stand-up itself (0.1096 → 0.1719 m, tilt 1.31°) |

### The two known sit/stand issues, as measured

> **Status update (2026-09-16): both are fixed by `sit_stand_v3`** — see the before/after pairs in the table
> above. Everything on this page below this point describes the **previous** policy, `sit_stand_v2`, which is
> still published so these measurements stay reproducible. It is the baseline the replacement was judged
> against, not the current behaviour.

The report is quoted as the user gave it; every number below is our own measurement, taken after that
report, with the published single-file runner. **CPU only** — MuJoCo **3.10.0**, ONNX Runtime **1.30.0**,
NumPy **2.5.3** — 500 control steps (**10.0 s**) per run, spawn `nominal`, flat floor, on the same code path as

```bash
python wamoduck_sim.py --policy sitstand --target-height 0.175 --headless --steps 500
python wamoduck_sim.py --policy sitstand --target-height 0.085 --headless --steps 500
python wamoduck_sim.py --policy stand                      --headless --steps 500
```

**These are Sim2Sim numbers from our CPU runner, not internal-board numbers.** The internal round behind
this row recorded no acceptance figures at all, and it recorded no `sitstand` jitter figure, so nothing
below reproduces a private measurement. Two figures that were already on this page do come back out of
this run: **0.094 m** held against a 0.085 m command, and a lean of **~26°**. What is new here is the
jitter and the left/right symmetry.

**1. The standing posture buzzes in place** (height command **0.175 m**). The robot is upright — final tilt
**0.44°**, base height **0.1762 m** — and it does not settle: the action stream in the last 1.0 s is just
as restless as the average over the whole run, so this is a sustained limit cycle, not a decaying transient.

| Quantity | `sitstand` @0.175 m | `stand` (same run length) |
| --- | --- | --- |
| Action jitter, mean abs(delta a) per control step, whole 10 s | **0.229** | 9.9e-5 |
| Action jitter, mean abs(delta a), after the first 1.0 s | **0.235** | 2.9e-7 |
| Action jitter, mean abs(delta a), last 1.0 s | **0.236** | 4.1e-8 |
| max abs(delta a), after the first 1.0 s | **1.313** | 2.5e-5 |
| base height std, after the first 1.0 s | **1.10 mm** | 1.8e-7 m |
| base height std, last 1.0 s | **0.99 mm** | 8.7e-11 m |
| tilt std, after the first 1.0 s | **0.403°** | 6.6e-4° |
| tilt std, last 1.0 s | **0.396°** | 2.5e-7° |
| mean abs(joint velocity), after the first 1.0 s | **1.68 rad/s** | 7.2e-6 rad/s |
| mean abs(joint velocity), last 1.0 s | **1.69 rad/s** | 3.4e-8 rad/s |
| max abs(joint velocity), last 1.0 s | **10.11 rad/s** | 2.0e-7 rad/s |
| steps with both soles down, after the first 1.0 s | **92.2 %** | 100 % |
| mean total ground reaction, after the first 1.0 s | **45.46 N** | 36.80 N |
| displacement over the 10 s | **0.263 m** | 0.001 m |

Read the first row against the figure in row 1 of this page: the `stand` policy's internal 40 s quiet stand
records the same metric as **0.00000**, and our `stand` run reproduces that to **2.9e-7**. The `sitstand`
policy is about **six orders of magnitude** above it — `mean abs(delta a)` of **0.235** per 0.02 s control
step is the joint targets moving at roughly **11.7 rad/s**. The robot's weight is **36.80 N**; the feet
carry **45.46 N** on average at that height, which is the buzz pushing the ground. And "in place" is
approximate: it also travels **0.263 m** over the 10 s.

**2. The sitting posture is neither upright nor left/right symmetric** (height command **0.085 m**). Where
the standing posture buzzes, this one is **quiet** — it reaches a static pose within about 1.0 s and stays
there (`mean abs(delta a)` **4.4e-7** in the last 1.0 s, base height std **1.9e-7 m**, tilt std
**1.3e-4°**). Pressing `m` mid-run instead of starting at 0.085 m lands on the same pose (`mean abs(delta a)`
**3.0e-5**, base height **0.0943 m**, tilt **25.84°**). So the jitter is a standing-height problem only.

What that quiet pose is:

| Quantity | Measured | The user's expectation |
| --- | --- | --- |
| base height, commanded **0.085 m** | **0.0943 m** (**+9.3 mm**, **+10.9 %**) | the commanded height |
| base tilt, last 1.0 s | **25.89°** (roll **−15.99°**, pitch **+20.64°**) | upright, i.e. near **0°** |
| `neck_pitch_link` up-axis vs world up | **25.44°** | near **0°** |
| `head_roll_link` (the head) up-axis vs world up | **25.62°** | near **0°** |
| `base_link_body_collision` against the floor, after the first 1.0 s | in contact **100 %** of steps, **7.16 N** of **36.83 N** = **19.4 %** of the weight | the two feet carrying the robot |
| left sole | **3** contact points, **16.69 N**, flat | both feet planted |
| right sole | **1** contact point, **12.98 N**, sole geometry **22 mm** above its contact | both feet planted |
| lateral distance between the soles | **0.216 m** (nominal spawn **0.169 m**) | legs braced outward |
| base drift from the spawn | dy **+0.041 m**, dx **−0.012 m**, yaw **+7.42°** | — |

The head chain's own joints are all within **0.6°** of zero (`neck_pitch` **−0.55°**, `head_pitch`
**+0.015°`, `head_yaw` **−0.20°**, `head_roll` **−0.28°**), so the trunk's lean is inherited whole by the
head: **the head and the torso are 25.4° to 25.9° off vertical**, which is what "not head and torso vertical
to the ground" looks like as a number. And the robot is **not** standing on two feet — its pelvis is on the
floor for every step of the last 1.0 s, carrying a fifth of its weight, with the right foot rolled onto a
single edge contact.

The 14 joint angles at the end (last 1.0 s mean, degrees), beside the same policy's standing-height run and
the `stand` policy as references:

| Joint | `sitstand` @0.085 m | `sitstand` @0.175 m | `stand` |
| --- | --- | --- | --- |
| `left_hip_yaw` | **−95.55** | +16.00 | −1.88 |
| `left_hip_roll` | +19.84 | −7.45 | +0.46 |
| `left_hip_pitch` | **+128.29** | +32.17 | −0.22 |
| `left_knee` | −17.77 | −11.19 | +0.38 |
| `left_ankle` | **−93.97** | −23.22 | −0.88 |
| `right_hip_yaw` | −23.77 | −14.25 | −0.44 |
| `right_hip_roll` | −20.39 | +2.84 | −0.26 |
| `right_hip_pitch` | **−45.26** | −43.97 | +0.014 |
| `right_knee` | −17.25 | +16.21 | −0.051 |
| `right_ankle` | **+48.36** | +32.96 | −0.29 |
| `neck_pitch` | −0.55 | +0.14 | +0.31 |
| `head_pitch` | +0.015 | −0.094 | −0.16 |
| `head_yaw` | −0.20 | −0.65 | +0.041 |
| `head_roll` | −0.28 | −0.19 | −0.12 |

**The left/right symmetry, and the sign convention it needs.** Two independent checks fix the convention
before any asymmetry is claimed, because the same joint on the two sides does **not** share a sign:

1. **The MJCF itself mirrors the rolls and yaws.** `left_hip_yaw` is **−1.7279 to +0.5323 rad** while
   `right_hip_yaw` is **−0.5323 to +1.7279 rad**, and `left_hip_roll` is **−1.1153 to +0.4311 rad** against
   `right_hip_roll` **−0.4311 to +1.1153 rad**. `hip_pitch`, `knee` and `ankle` have **identical** ranges on
   both sides.
2. **A direct probe agrees.** With everything else at the nominal pose, `left_hip_roll = +0.3 rad` moves the
   left sole from y = **+0.0846 m** to **+0.1116 m** — outward — while `right_hip_roll = +0.3 rad` moves the
   right sole from y = **−0.0846 m** to **−0.0523 m** — inward. A positive roll is outward on the left and
   inward on the right. (The same probe on `hip_yaw` is inconclusive on its own: ±0.3 rad moved the left
   sole's y by under **2 mm** and non-monotonically, because yaw twists the leg about the vertical axis. The
   mirrored ranges are the evidence there, not the probe.)

So a mirror-symmetric pose has `hip_yaw` and `hip_roll` at **opposite signs** — their residual is
`left + right` — while `hip_pitch`, `knee` and `ankle` should be **equal** — residual `left − right`. The
residual is also given as a percentage of the pair's own mean magnitude, which saturates at **200 %** when
the two values sit on opposite sides of zero, i.e. the worst disagreement possible.

| Pair | Convention | `sitstand` @0.085 m: left / right | Residual | % |
| --- | --- | --- | --- | --- |
| `hip_yaw` | mirrored (opposite signs) | −95.55° / −23.77° | **−119.32°** | **200 %** |
| `hip_roll` | mirrored (opposite signs) | +19.84° / −20.39° | −0.55° | 2.7 % |
| `hip_pitch` | same sign | +128.29° / −45.26° | **+173.54°** | **200 %** |
| `knee` | same sign | −17.77° / −17.25° | −0.52° | 3.0 % |
| `ankle` | same sign | −93.97° / +48.36° | **−142.33°** | **200 %** |

At the sitting height, `hip_roll` and `knee` match to within **0.6°**, and the other three do not match at
all: on `hip_yaw`, `hip_pitch` and `ankle` the two legs are on **opposite sides of zero** — the left hip is
flexed **+128.29°** while the right hip is extended **−45.26°**, and the left ankle is **−93.97°** against a
right ankle of **+48.36°**. That is a twisted pose, not a mirrored one, and the residual being **200 %** means
it is the largest disagreement the pairing can express.

The same measurement at the standing height shows the buzz also ends in a staggered stance — one leg forward,
one leg back — and the `stand` policy is the control that shows the convention is being applied correctly:

| Pair | `sitstand` @0.175 m: residual | `sitstand` @0.085 m: residual | `stand`: residual |
| --- | --- | --- | --- |
| `hip_yaw` | +1.74° (11.5 %) | −119.32° (200 %) | −2.32° |
| `hip_roll` | −4.61° (89.6 %) | −0.55° (2.7 %) | +0.20° |
| `hip_pitch` | +76.14° (200 %) | +173.54° (200 %) | −0.23° |
| `knee` | −27.40° (200 %) | −0.52° (3.0 %) | +0.43° |
| `ankle` | −56.18° (200 %) | −142.33° (200 %) | −0.59° |

The `stand` policy keeps every pair within **0.6°** in absolute terms, so the convention is right and a
symmetric pose is achievable in this model. **Read the absolute degrees, not the percentage, whenever both
values are near zero** — three of the five `stand` pairs also print **200 %**, on values of a fifth of a
degree, because a percentage of nothing is not a measurement.

**The user's expectation, written so it can be tested.** This repository has **no** definition of a target
sitting pose, so the three statements below are the report's expectation restated as assertions, not a
measured target and not a threshold we are proposing to train against. Where a tolerance is quoted it is one
this repository already uses, and the tolerance for the third statement is not decided here.

1. **At a 0.085 m height command, the trunk and the head are vertical:** base tilt and the `head_roll_link`
   up-axis are near **0°** — the strict-standing row on this page already calls tilt below **8°** "upright",
   and the current values are **25.89°** and **25.62°**, i.e. **3.2×** outside it. (The full strict-standing
   criterion does not apply to a sitting pose: it also requires a base height above 0.15 m, which a 0.085 m
   sit command can never satisfy.)
2. **The pose is mirror-symmetric:** for `hip_pitch`, `knee` and `ankle` the left and right values agree, and
   for `hip_roll` and `hip_yaw` they agree after the mirror-sign correction above. The current residuals are
   **173.54°**, **−0.52°**, **−142.33°**, **−0.55°** and **−119.32°** — so two of the five pairs pass and
   three fail by more than **100°**.
3. **Both legs support the robot and brace outward:** both soles flat on the ground, the weight carried by
   the feet, and the hips abducted away from the midline. The current pose has the pelvis on the ground for
   **100 %** of the last 1.0 s carrying **19.4 %** of the weight and a right foot on a single edge contact.
   No tolerance is quoted for this one; it was not measured as a bracing force, only as the contacts above.
   This repository already has precedent for checks of that shape — the strict-standing criterion asks for
   both soles rather than being propped up on a knee, shoulder or head, and the get-up delivery criterion
   fails a pose whose head chain presses the ground with more than **2 N** — but neither of those thresholds
   is stated for the pelvis, so none is applied here.

**Status: both fixed on 2026-09-16.** The two issues above were measured on `sit_stand_v2` and are recorded
here as the baseline; the replacement policy `sit_stand_v3` passes all eleven axes that apply to it, with the
before/after pairs in the section table. The one thing that did **not** change is the geometry: a 0.085 m seat
is still unreachable with an upright trunk, so the command range moved to **0.11241–0.175 m** rather than the
policy learning to do something the mechanism cannot.

## How standing is judged

The four thresholds, all of which must hold for "recovered to the nominal stance":

1. tilt < **8 deg** — upright, not merely "has not fallen";
2. **both soles touching the ground** — standing, not propped up on a knee, shoulder, or head;
3. every joint within **20 deg** of nominal (nominal = all zeros);
4. base height > **0.15 m** — not crouching.

On top of the four thresholds there is a **duration rule**: the criterion must hold for at least **90 % of the sampled instants in the last 1.0 s** (50 control steps at 50 Hz). It is deliberately neither "every frame" nor "the final frame".

Why 90 %: a robot that is standing is continuously making small corrections, the way a person keeps balancing on a moving bus. Demanding a flawless run of 50 steps asks it to stand like a statue — on the same final states, the both-feet condition at every one of those steps gives **20/64** while the final frame alone gives **63 to 64/64**. The 90 % rule sits between those two: it still refuses a single lucky frame, and it no longer rejects a robot that is actively balancing.

The loose pair used to describe "standing" at all (tilt < 30 deg, base height > 0.15 m) is kept deliberately separate. Conflating the two once let a policy that parked itself in a 19 deg lean be reported as recovered.

The get-up delivery criterion extends the same four axes with two more, because the four alone can pass a pose that keeps the head on the ground and the feet on an edge: **the head chain must not press the ground** (vertical ground reaction below 2 N, the same threshold the training penalty uses) and **the soles must be flat** (within 5 deg). One shared definition lives in `stand_criteria.py` and is imported by the evaluation tool, the get-up demo, and the recovery probe, so there is exactly one set of thresholds rather than one per script.

## Two structural facts behind these results

**The head is 44 % of the robot.** The head chain — `neck_pitch_link`, `head_pitch_link`, `head_yaw_link`, `head_roll_link`, `mouth_link` — carries **1.654 kg** of the model's **3.751 kg**, i.e. **44.1 %**. Both figures can be read straight out of the published [URDF](../models/wmduck/wmduck.urdf) and its [mass audit](../models/wmduck/component_mass_audit.csv).

**The head is a two-way lever.** The maximum static gravity torque about the `neck_pitch` axis is **1.61 N·m** in the training model (closed-form solution), while the saved nominal pose needs only about **0.05 N·m** — the nominal pose says almost nothing about the worst angle. If the actuator limit is smaller than that maximum, there is always a band of angles where gravity can fold the head down but the joint cannot lift it back — a one-way ratchet. With the 1.5 N·m limit used for every other joint, that dead band is about **139 deg** wide, which is why the training model raises this **one joint to 2.2 N·m** (1.37 times the maximum gravity torque, 59 % of the recorded stall torque), in the collision-enabled variant only. A get-up rollout peaks at **1.613 N·m** against that 2.2 N·m limit — 27 % margin, and 0 % of the steps sit on the limit.

Two things that statement does not mean. It is not a hardware rating: 2.2 N·m is 3.7 times the motor's rated continuous output and 59 % of its recorded stall torque, and it is allowed only for short head-retraction motions. And it is not a claim about the published model: the [URDF](../models/wmduck/wmduck.urdf) effort column keeps the rated 0.6 N·m for all 15 joints and declares no actuators at all, so nothing in this repository states a 2.2 N·m limit. Recomputing the same closed form on the **published** URDF — summing each head-chain link's weight times its moment arm about the axis, maximized over the joint's rotation — gives **1.574 N·m**, because the training model carries measured-mass updates that have not been published yet.

## What this page does not claim

- **No hardware results.** Every number is simulated. The physical robot's mass, friction, compliance, and sensor chain are not in these numbers.
- **Not reproducible from this repository.** The scene, the measurement protocols, and the measuring tools are private. Five of the policies are now published as ONNX files with a CPU runner ([simulation guide](simulation.md)), so you can re-run the *behaviour* — but this page is a measurement report, and the numbers above come from a different simulator and a protocol that is not published. The one exception is [the sit/stand section](#the-two-known-sitstand-issues-as-measured), which is explicitly marked as our own CPU Sim2Sim measurement and is reproducible with the commands given there.
- **No perception, thermal, or endurance results.** Nothing here covers the camera, the runtime software, duty cycles, or long-duration reliability.
- **The get-up strict criterion is now met** — **63/64** and **5/5** end-to-end since 2026-09-16, against **0/64** before; the stricter six-axis version is **45/64**. **Walking side-stepping does not work.** Those remaining items are not rounding errors. **In-place turning is a different kind of entry**: it is measured to be out of reach for this mechanism ([§4](#why-in-place-turning-cannot-be-trained-away)), so it is listed as a limit of the design rather than as an unfinished item.
- **Sit/stand has two measured, unfixed issues** — it buzzes in place while standing, and its sitting posture is neither upright nor left/right symmetric. The numbers are in [section 6](#6-sit--stand), and no fix is claimed for either.
- **The training model is not the published model.** The results describe the simulation model used for training, which currently differs from the published URDF in measured-mass updates.

The areas where documentation is deliberately still thin are tracked in the [roadmap](roadmap.md).
