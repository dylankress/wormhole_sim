import random
import hashlib

class SimulationConfig:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)

        self.total_ticks = 10000
        self.total_nodes = 1000
        self.target_active_ratio = 0.01

        self.file_upload_rate = 0.4
        self.max_files_per_tick = 3
        self.disk_write_speed_mb_s = 200

        self.bootstrap_peer_sample_size = 5
        self.join_announcement_size_kb = 2

        self.rebootstrap_cooldown_ticks = 1000

        # Estimated average online uptime for each profile
        profile_uptime_estimates = {
            "always_online": 1.00,
            "mostly_online": 0.90,
            "balanced":      0.65,
            "flaky":         0.35,
            "erratic":       0.10
        }

        # Sort profiles by how "available" they are
        sorted_profiles = sorted(profile_uptime_estimates.items(), key=lambda x: -x[1])

        remaining_nodes = self.total_nodes
        remaining_uptime_budget = self.target_active_ratio * self.total_nodes

        distribution = {}

        for profile, uptime_fraction in sorted_profiles:
            max_nodes_for_profile = min(
                remaining_nodes,
                int(remaining_uptime_budget / uptime_fraction)
            )
            share = max_nodes_for_profile / self.total_nodes
            distribution[profile] = share

            remaining_nodes -= max_nodes_for_profile
            remaining_uptime_budget -= max_nodes_for_profile * uptime_fraction

            if remaining_nodes <= 0 or remaining_uptime_budget <= 0:
                break

        # Fill remainder with erratic if there's a gap
        if sum(distribution.values()) < 1.0:
            distribution["erratic"] = distribution.get("erratic", 0.0) + (1.0 - sum(distribution.values()))

        self.behavior_distribution = distribution


    def child_rng(self, namespace: str):
        full_seed = f"{self.seed}_{namespace}".encode()
        digest = hashlib.sha256(full_seed).digest()
        int_seed = int.from_bytes(digest[:4], byteorder="big")
        return random.Random(int_seed)
