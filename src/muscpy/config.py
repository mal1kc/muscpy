IDLE_TIMEOUT = 10 * 60  # 10 mins = 600 seconds
# IDLE_TIMEOUT = 30  # seconds
IDLE_CHECK_TIMEOUT = 10  # seconds

if IDLE_TIMEOUT <= 0:
    raise ImportError("IDLE_TIMEOUT can't be below or equal to 0")
