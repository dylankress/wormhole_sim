import random

class BlackoutManager:
    def __init__(self, config, nodes):
        self.config = config
        self.nodes = nodes
        self.blackout_triggered = False
        self.blackout_active = False
        self.blackout_region = None
        self.blackout_start_tick = None
        self.blackout_end_tick = None
        self.ramp_duration = 2000  # ticks over which nodes will ramp back online (e.g. ~1.5 hours)

        self.rng = config.child_rng("blackout_manager")

        # Choose a region to blackout based on presence
        regions = list(set(n.timezone_offset for n in nodes if n.timezone_offset is not None))
        self.blackout_region = self.rng.choice(regions)

        # Duration: in ticks
        self.blackout_duration = 4000

        print(f"🌐 Blackout scheduled for region {self.blackout_region // 3600}h offset")
        print(f"🌒 Duration will be {self.blackout_duration} ticks (~{self.blackout_duration // 3600:.1f} hours)")

        region_count = sum(1 for n in nodes if n.timezone_offset == self.blackout_region)
        print(f"📊 {region_count} nodes assigned to region {self.blackout_region // 3600}h")

        # Cache nodes affected by this region
        self.affected_nodes = [n for n in self.nodes if n.timezone_offset == self.blackout_region]

    def apply_blackout(self, tick):
        if not self.blackout_triggered and tick < 1000:
            return

        if not self.blackout_triggered and tick >= 1000:
            self.blackout_triggered = True
            self.blackout_active = True
            self.blackout_start_tick = tick
            self.blackout_end_tick = tick + self.blackout_duration

            print(f"Blackout begins at tick {tick} for region {self.blackout_region // 3600}h")

            for node in self.affected_nodes:
                node.force_offline_until = self.blackout_end_tick + self.ramp_duration

            return

        if not self.blackout_active or tick <= self.blackout_end_tick:
            return

        elapsed = tick - self.blackout_end_tick
        ramp_ratio = min(elapsed / self.ramp_duration, 1.0)

        still_offline = [n for n in self.affected_nodes if n.force_offline_until is not None]
        target_unlock_count = int(len(self.affected_nodes) * ramp_ratio)
        unlock_now = still_offline[:target_unlock_count]

        for node in unlock_now:
            node.force_offline_until = None

        if ramp_ratio >= 1.0:
            print(f"Region {self.blackout_region // 3600}h fully recovered at tick {tick}")
            self.blackout_active = False

