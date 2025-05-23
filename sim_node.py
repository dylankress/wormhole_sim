class SimNode:
    def __init__(self, node_id: str, upload_speed_mb_s: int, download_speed_mb_s: int, total_space_gb: int, is_new_user: bool, behavior_profile: str, config, nal):
        
        self.config = config
        self.cached_rng = config.child_rng(f"node_rng_{node_id}")
        self.id = node_id
        self.nal = nal

        self.upload_speed_mb_s = upload_speed_mb_s
        self.download_speed_mb_s = download_speed_mb_s

        self.behavior_profile = behavior_profile

        self.free_space_gb = total_space_gb
        self.total_space_gb = total_space_gb

        self.is_new_user = is_new_user
        self.online = False
        self.known_peers = set()

        max_download_speed = 500  # or derive from actual list if needed
        normalized_download = self.download_speed_mb_s / max_download_speed
        normalized_space = self.free_space_gb / self.total_space_gb

        # Uptime from config
        uptime = self.config.profile_uptime_estimates.get(self.behavior_profile, 0.5)

        # Composite score
        self.score = round(
            0.5 * normalized_download +
            0.3 * normalized_space +
            0.2 * uptime,
            2
        )

        self.join_tick = None
        self.hosted_chunks = set()
        self.has_joined = False
        self.last_bootstrap_tick = None
        self.was_online_last_tick = False

        self.force_offline_until = None  # Used by blackout_manager to override uptime

        self.auth_secret = "default"
        self.password_seed = "default"
        
        self.timezone_offset = None  # Assigned in node_generator

        self.files_uploaded = []

        self.round_robin_index = 0

    def __repr__(self):
        return (f"<SimNode id={self.id} "
                f"online={self.online} "
                f"upload_speed={self.upload_speed_mb_s}MB/s "
                f"peers={len(self.known_peers)} "
                f"free={self.free_space_gb}GB "
                f"blackout={self.force_offline_until is not None}>")
    
    def attempt_join(self, current_tick):
        self.nal.register_peer(self.id, self)

        announce_payload_kb = self.config.join_announcement_size_kb
        upload_speed_kbps = self.upload_speed_mb_s * 1024
        delay_ticks = announce_payload_kb / upload_speed_kbps

        rng = self.cached_rng
        jitter = rng.uniform(0, 0.25)
        total_delay = delay_ticks + jitter

        # Announce self to network
        capabilities = {
            "upload_speed": self.upload_speed_mb_s,
            "download_speed": self.download_speed_mb_s,
            "storage_gb": self.total_space_gb,
        }
        known_peers = self.nal.announce_self(self.id, port=5200, capabilities=capabilities)

        self.join_tick = current_tick
        self.known_peers.update(known_peers)
        self.has_joined = True

        print(f"[JOIN] {self.id} joined with {len(known_peers)} peers at tick {current_tick}")

