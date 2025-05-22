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

    def apply_blackout(self, tick):
        # Trigger blackout after number of ticks
        if not self.blackout_triggered and tick >= 1000:
            self.blackout_triggered = True
            self.blackout_active = True
            self.blackout_start_tick = tick
            self.blackout_end_tick = tick + self.blackout_duration
            print(f"🚨 Blackout begins at tick {tick} for region {self.blackout_region // 3600}h")

            for node in self.nodes:
                if node.timezone_offset == self.blackout_region:
                    node.force_offline_until = self.blackout_end_tick + self.ramp_duration

        # Handle ramp-up phase
        if self.blackout_active and tick > self.blackout_end_tick:
            elapsed = tick - self.blackout_end_tick
            ramp_ratio = min(elapsed / self.ramp_duration, 1.0)

            for node in self.nodes:
                if node.timezone_offset == self.blackout_region:
                    if hasattr(node, "force_offline_until"):
                        # Deterministically stagger return to service
                        node_rng = self.config.child_rng(f"ramp_{node.id}_{tick}")
                        if node_rng.random() < ramp_ratio:
                            node.force_offline_until = None  # fully back online

            if ramp_ratio >= 1.0:
                print(f"✅ Region {self.blackout_region // 3600}h fully recovered at tick {tick}")
                self.blackout_active = False
