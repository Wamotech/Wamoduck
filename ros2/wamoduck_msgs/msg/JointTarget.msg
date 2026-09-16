# Downlink joint target: the ROS-side image of the TYPE_CMD (0x01) payload of the
# wmduck deployment protocol v1.
#
# On the wire one frame is
#     SOF | TYPE | LEN | SEQ | <this payload> | CRC16
# i.e. 40 bytes of payload inside a 46-byte frame, sent host -> cerebellum at 50 Hz.
#
# The bridge node (wamoduck_ros2/bridge_stub) is the ONLY component that turns this
# message into bytes. Everything above it works in radians and SI units, so the
# fixed-point scaling and the byte order stay in one place.

# Downlink modes (deployment protocol v1).
uint8 MODE_OFF=0
uint8 MODE_HOLD=1
uint8 MODE_POLICY=2
uint8 MODE_CALIB=3

std_msgs/Header header

# One of MODE_*. MODE_POLICY for normal closed-loop operation.
uint8 mode

# Reserved for future use; send 0.
uint8 flags

# Sender clock in milliseconds. The cerebellum echoes link timing back through the
# age_ms field of the state frames, which is how end-to-end latency gets measured.
uint32 t_ms

# Joint angles in radians, ordered exactly like the policy contract's `joint_order`
# (joint-tree order, NOT the MJCF <actuator> order and NOT the URDF document order).
# 14 entries:
#   left_hip_yaw, left_hip_roll, left_hip_pitch, left_knee, left_ankle,
#   right_hip_yaw, right_hip_roll, right_hip_pitch, right_knee, right_ankle,
#   neck_pitch, head_pitch, head_yaw, head_roll
# On the wire this becomes int16 milliradians (scale 1000), which saturates at
# +/-32.767 rad. Saturation clamps; it never wraps.
float64[14] q_target_rad

# Command echo: (vx m/s, vy m/s, wz rad/s). Carried so that the cerebellum's log and the
# host log both record what the policy was asked to do. This is what makes "the policy was
# wrong" distinguishable from "the command was wrong".
# On the wire: int16 mm/s, int16 mm/s, int16 mrad/s (scale 1000 each).
float64[3] twist
