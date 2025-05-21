from sim_node import SimNode
from node_behavior import generate_behavior_profile

def generate_nodes(rng, count, config):
    nodes = []
    for i in range(count):
        node_id = f"node_{i}"
        upload_speed = rng.randint(1, 5)        # MB/s
        download_speed = rng.randint(2, 8)      # MB/s
        total_space = rng.randint(10, 100)      # GB
        is_new_user = rng.random() < 0.7        # 70% new users

        node = SimNode(
            node_id=node_id,
            upload_speed_mb_s=upload_speed,
            download_speed_mb_s=download_speed,
            total_space_gb=total_space,
            is_new_user=is_new_user,
            config=config
        )

        # Assign behavior profile (deterministic based on seed)
        profile_types = list(config.behavior_distribution.keys())
        weights = list(config.behavior_distribution.values())
        profile_type = rng.choices(profile_types, weights=weights)[0]

        node.behavior_profile = generate_behavior_profile(profile_type, rng, config.total_ticks)
        if node.behavior_profile is None:
            raise ValueError(f"Behavior profile generation failed for {node.id} with type '{profile_type}'")

        # Assign timezone offset (in ticks, 3 hour buckets)
        timezone_buckets = [0, 10800, 21600, 32400, 43200, 54000, 64800, 75600]
        tz_rng = config.child_rng(f"timezone_offset_{node_id}")
        
        # Assign timezone offset (in ticks, weighted by estimated global internet use)
        timezone_buckets = [
            0,     # UTC
            10800, # UTC+3
            21600, # UTC+6
            32400, # UTC+9
            43200, # UTC+12
            54000, # UTC+15
            64800, # UTC+18
            75600  # UTC+21
        ]

        # Approximate weightings for global population with internet access
        weights = [
            0.12,  # UTC      (Europe, North Africa)
            0.08,  # UTC+3    (East Africa, Middle East)
            0.20,  # UTC+6    (India, Bangladesh, Central Asia)
            0.25,  # UTC+9    (China, Japan, Korea)
            0.10,  # UTC+12   (Pacific + some Oceania)
            0.10,  # UTC+15   (Australia east coast + oceanic)
            0.10,  # UTC+18   (mostly sparse but catch-all)
            0.05   # UTC+21   (extremely sparse)
        ]

        tz_rng = config.child_rng(f"timezone_offset_{node_id}")
        node.timezone_offset = tz_rng.choices(timezone_buckets, weights=weights)[0]

        # Set initial online status
        initial_status = node.behavior_profile.is_online(0, node)
        node.online = initial_status
        node.was_online_last_tick = False

        nodes.append(node)

    return nodes
