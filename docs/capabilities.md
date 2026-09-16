# Measured capabilities / 实测能力清单

[Home](../README.md) · English | [简体中文](capabilities.zh-CN.md) · [Roadmap](roadmap.md)

This page is one honest board of what the trained policies actually do. Every figure was measured in simulation on **2026-09-16** and copied from a measurement log, with the tool that produced it named beside it. Nothing here is extrapolated, estimated, or carried over from a different run without saying so, and the parts that do not work are listed with the same weight as the parts that do.

**Scope: simulation only.** The policies run in a MuJoCo / mjlab environment on one laptop GPU, normally **64 parallel environments** per measurement (32 for the walking table), with the round named in each row. There are no hardware measurements on this page. The training code, the scene generator, the checkpoints, and the measurement tools live in the private development repository and are **not** published here — so this page reports measurements rather than offering a reproduction recipe. Re-measure before quoting it.

## Summary

| # | Capability | Policy | Headline result |
| --- | --- | --- | --- |
| 1 | Standing against a push | `stand_v3` (`model_1499.pt`, shipped) | Push threshold **40.5 N**; steady-state drift **0.00 mm/s** over 40 s |
| 2 | Knocked down → get up → back to nominal | `stand_v3` + `getup_v18` (`model_3999.pt`) | **5/5** trials end in the strict nominal stance |
| 3 | Get-up from a random lying pose | `getup_v18` (`model_3999.pt`) | Standing at the end **64/64**; strict nominal criterion still **0/64** |
| 4 | Flat-ground walking | `walk_r3` (`model_5999.pt`, shipped) | Forward tracking 106 % / 103 %, but **side-stepping and in-place turning are broken** |
| 5 | 1 cm rough terrain | `rough_v2` (`model_5999.pt`) | Survival **51/64 (79.7 %)**; mean speed **61 %** of the command |
| 6 | Sit / stand | `sit_stand_v2` (`model_2499.pt`, shipped) | Interactive height control; no acceptance numbers in this batch |

A policy marked *shipped* is the checkpoint the interactive demos load by default in the development repository; it is not in this repository.

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
| Policy | `stand_v3` + `getup_v18` (`model_3999.pt`), switched automatically by a small state machine |
| Sequence | Shove it over → the get-up policy takes over → it stands up → the standing policy takes over and settles into the saved nominal pose |
| Measured (5 trials) | End-to-end, ending in the strict nominal stance: **5/5**. Final tilt **0.5 deg**, `neck_pitch` **0.3 deg**, largest joint deviation **1.9 deg**, both feet on the ground, base height **0.177 m** — the same five numbers in all five trials |
| Not as good | "Did not fall again after standing up": **4/5**. In one trial the hand-over dropped the robot five times before the final state passed, so the interlock is not yet repeatable in the strong sense |
| Tool | `probe_recovery_handover.py --trials 5` |

![Pushed over, then it stands back up and settles into the nominal stance](../assets/wamoduck-pushed-down-recover.gif)

*Pushed over, then recovers to the nominal stance. Simulation screen recording, not hardware footage: it shows `stand_v3` and `getup_v18` handing over inside MuJoCo, one selected take — the 5/5 and 4/5 above come from the 5-trial probe, not from this clip.*

![The hardest case: repeated attempts, finally getting up](../assets/wamoduck-getup-struggle.gif)

*The hardest case: repeated attempts, finally gets up. Simulation screen recording, not hardware footage: it shows `getup_v18` inside MuJoCo. It is published precisely because it is not a clean take — the first attempts fail before it gets up, which matches the "did not fall again after standing up 4/5" row above.*

The full-length recording of this session — pushes, knock-downs, get-up attempts, and the hand-over, 1:49.37, 1280 × 716, no audio — is [wamoduck-force-test-demo.mp4](../assets/wamoduck-force-test-demo.mp4). It is one session, not a test campaign; the rates on this page come from the tools named in each row.

This is the requirement that matters most, because it is the only row that tests the two policies **together**: a nominal final pose that cannot survive the hand-over would not be a usable robot behaviour.

## 3. Get-up from a random lying pose

| Field | Value |
| --- | --- |
| Policy | `getup_v18`, `model_3999.pt` |
| Setup | Spawned lying on the ground with random roll and pitch, 64 environments, 300 steps (6 s) |
| Measured | Reached standing at some point **64/64**; standing at the end **64/64** (loose criterion: tilt < 30 deg and base height > 0.15 m); median time to first standing **0.50 s**, p90 **0.81 s**; mean final tilt **7.8 deg** |
| Measured (strict) | Returning to the **nominal** stance (tilt < 8 deg, both feet on the ground, every joint within 20 deg of nominal): **0/64**. Mean largest joint deviation 52.3 deg, both feet 63/64 |
| 900-step acceptance | The get-up delivery criterion runs 900 steps and requires the criterion to hold rather than to happen once. Still **0/64**. The failing joint is now `head_pitch` at **46 deg** — the second link of the head chain, which never touches the ground |
| Head chain on the ground | **0/64**, i.e. the head no longer carries the robot. The previous round was 63/64 with **17.5 N** of ground reaction on the head, about 106 % of the head's own weight |
| Tools | `eval_getup.py --envs 64`, `check_getup_delivery.py --envs 64`, `probe_getup_support.py` |

Read the two blocks together: the robot reliably gets up and reliably ends up standing, and it still does not reliably end up in the **saved nominal pose**. The gap is concentrated in one joint of the head chain rather than spread over the legs, and a training-side fix for it is in progress.

## 4. Flat-ground walking

Read this row with more care than the others, because **the numbers and the policy are not from the same round**.

| Field | Value |
| --- | --- |
| Shipped policy | `walk_r3`, `model_5999.pt`, trained 2026-09-12 under an older command range |
| Newest same-protocol table | `walk_v3`, `model_5999.pt` (2026-09-15/16, **not published**), body-frame commands, 32 environments, 500 steps (10 s) |
| Forward tracking | 0.3 m/s command → **106 %**; 0.5 m/s command → **103 %** |
| Side-stepping | Command +0.30 m/s → measured **+0.218 m/s** body-frame, but with **+520.4 deg** of uncommanded yaw and a forward drift of **-0.003 m** over the same 10 s. The sideways magnitude survived (the previous round measured +0.240 m/s) while the axis discipline collapsed, so this mode is **not usable** |
| Turn in place | Command 0.5 rad/s → **0.1 %** of the commanded yaw, i.e. **+0.3 deg** in 10 s. The robot does not turn on the spot |
| Walk and turn together | 0.4 m/s plus 0.5 rad/s → forward **109 %**, yaw **7 %** |
| Tool | `measure_twist_tracking.py --run walk_v3` |

Two warnings, both about honesty rather than capability:

- The shipped `walk_r3` checkpoint was trained under a different command range from the one the current configuration uses, so measurements of it under the current range are **not directly comparable** with the fresh table. Its behaviour is best judged by driving the interactive keyboard demo, not by quoting either table. Walking is being retrained (`walk_v4r`).
- The ruler itself was replaced for this round. The old criterion used the net world-frame displacement, which cannot tell "cannot walk" from "walked in a circle"; the numbers above are body-frame integrals of the same quantity the training reward uses, and the tool validates itself against analytic trajectories before measuring anything.

## 5. 1 cm rough terrain

| Field | Value |
| --- | --- |
| Policy | `rough_v2`, `model_5999.pt` |
| Setup | Generated terrain with 1 cm curbs and 1 cm step-downs, difficulty rows 0 to 5; 64 environments, 600 steps (12 s), forward command +0.30 m/s; curricula disabled so the difficulty row cannot change mid-measurement |
| Measured | Survived to the end **51/64 (79.7 %)**; mean forward speed **+0.183 m/s = 61 %** of the command; moved forward by more than 0.1 m in **53/64**; median / p90 max tilt **7.7 / 8.3 deg** |
| Hard rows only | On difficulty rows 3 and above (n = 33): survived **24/33**, mean speed **+0.157 m/s** |
| Tool | `eval_rough.py --envs 64` (round `rough_v2`) |

The 61 % is a real loss of speed, and it is measured against the commanded speed, not against the policy's flat-ground speed. **No flat-ground control run was made in the same batch**, so this page does not attribute the loss to the terrain alone.

## 6. Sit / stand

| Field | Value |
| --- | --- |
| Policy | `sit_stand_v2`, `model_2499.pt` (shipped) |
| Control | One key toggles between sitting and standing; two more keys raise and lower the target height |
| Measured | Interactive only. No acceptance numbers were recorded for this round in the same batch, so none are claimed here |
| Tools | `play_sit_stand.py`, `diagnose_stand_play.py` |

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
- **Not reproducible from this repository.** The policies, the scene, and the measuring tools are private. This page is a measurement report.
- **No perception, thermal, or endurance results.** Nothing here covers the camera, the runtime software, duty cycles, or long-duration reliability.
- **The get-up strict criterion is not met** (0/64), and **walking side-stepping and in-place turning do not work**. Those are open items, not rounding errors.
- **The training model is not the published model.** The results describe the simulation model used for training, which currently differs from the published URDF in measured-mass updates.

The areas where documentation is deliberately still thin are tracked in the [roadmap](roadmap.md).
