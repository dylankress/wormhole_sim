import random
import math

class BaseBehaviorProfile:
    def is_online(self, tick, node=None):
        raise NotImplementedError()


class RollingBehaviorProfile(BaseBehaviorProfile):
    def __init__(self, cycle_length, uptime_ticks, offset):
        self.cycle_length = cycle_length
        self.uptime_ticks = uptime_ticks
        self.offset = offset

    def is_online(self, tick, node=None):
        # Force blackout override
        if node and getattr(node, "force_offline_until", None):
            if tick < node.force_offline_until:
                return False

        # Normal behavior logic
        cycle_position = (tick + self.offset) % self.cycle_length
        base_online = cycle_position < self.uptime_ticks

        if node and node.timezone_offset is not None:
            local_time = (tick + node.timezone_offset) % 86400
            daylight = node.config.daylight_curve[local_time]
            return base_online and node.cached_rng.random() < daylight

        return base_online

def generate_behavior_profile(profile_type, rng, total_ticks):
    if profile_type == "always_online":
        return RollingBehaviorProfile(cycle_length=1, uptime_ticks=1, offset=0)

    elif profile_type == "mostly_online":
        cycle = rng.randint(12000, 18000)
        uptime = int(cycle * rng.uniform(0.88, 0.95))

    elif profile_type == "balanced":
        cycle = rng.randint(12000, 18000)
        uptime = int(cycle * rng.uniform(0.55, 0.7))

    elif profile_type == "flaky":
        cycle = rng.randint(6000, 10000)
        uptime = int(cycle * rng.uniform(0.2, 0.4))

    elif profile_type == "erratic":
        cycle = rng.randint(20000, 100000)
        uptime = int(cycle * rng.uniform(0.03, 0.1))

    else:
        raise ValueError(f"Unknown profile type: {profile_type}")

    offset = rng.randint(0, cycle)
    return RollingBehaviorProfile(cycle, uptime, offset)
