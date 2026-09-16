# Byte-level link health, published by the bridge. Counters are cumulative since node start
# and mirror the reference FrameParser bucket names, because three different faults look
# identical in a byte count but mean completely different things:
#   resync_bytes -- noise or a half frame; the stream lost SOF alignment
#   bad_len      -- the LEN byte was impossible; usually a real resync, occasionally a bug
#   bad_crc      -- a complete-length frame failed CRC; electrically noisy line

# Cerebellum status word bits (STATE_Q / STATE_DQ / STATE_IMU `status` field).
uint16 ST_ENABLED=1
uint16 ST_POLICY_MODE=2
uint16 ST_WATCHDOG=4
uint16 ST_FAULT_OVERCURRENT=8
uint16 ST_FAULT_OVERTEMP=16
uint16 ST_FAULT_ENCODER=32
uint16 ST_LIMIT_CLAMPED=64
uint16 ST_ESTOP=128
uint16 ST_CAN_ERROR=256
uint16 ST_FALLEN=512

std_msgs/Header header

# Latest status word received from the cerebellum.
uint16 status

# Freshness of the newest state sample, as reported by the cerebellum itself.
uint16 age_ms

uint32 rx_frames
uint32 tx_frames
uint32 resync_bytes
uint32 bad_len
uint32 bad_crc

# Is the byte transport (serial / CAN) currently usable?
bool transport_open

# Host-side latched emergency stop.
bool estop
