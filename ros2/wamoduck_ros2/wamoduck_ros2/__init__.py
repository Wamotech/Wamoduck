"""Wamoduck (wmduck) ROS 2 nodes: gait replay, policy skeleton, link bridge.

Layout, and why it is split this way:

``frame_codec``
    The binary link contract (deployment protocol v1) with no ROS and no hardware
    dependency. Fully unit-tested -- this is the part that can be proven today.
``model_contract``
    The frozen policy contract (joint order, observation layout, timing, command ranges) and
    the URDF reader that must agree with it.
``gait_csv``
    Reader for the reference gait CSVs in ``tools/matlab/data/``.
``policy_interface``
    Observation assembly, command clamping, the actuator -> joint permutation and the target
    computation, as pure functions, so they are testable without ONNX or a robot.
``policy_runner``
    The ONNX Runtime boundary. Skeleton; never executed in this tree.
``gait_player`` / ``policy_node`` / ``bridge_stub``
    The three nodes.
"""

__all__ = [
    'bridge_stub',
    'frame_codec',
    'gait_csv',
    'gait_player',
    'model_contract',
    'policy_interface',
    'policy_node',
    'policy_runner',
]
