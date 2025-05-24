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

        self.replication_status = {}  # file_name → status string like "replicated"

        # Uptime estimate (still used for analytics or modeling)
        uptime = self.config.profile_uptime_estimates.get(self.behavior_profile, 0.5)
        normalized_download = self.download_speed_mb_s / 500
        normalized_space = self.free_space_gb / self.total_space_gb

        # You can retain this if you want score for logging or node sorting
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

        self.force_offline_until = None
        self.auth_secret = "default"
        self.password_seed = "default"
        self.timezone_offset = None  # Set in generator
        self.files_uploaded = []

    def __repr__(self):
        return (f"<SimNode id={self.id} "
                f"online={self.online} "
                f"upload_speed={self.upload_speed_mb_s}MB/s "
                f"free={self.free_space_gb}GB "
                f"blackout={self.force_offline_until is not None}>")

    def attempt_join(self, current_tick):
        self.nal.register_peer(self.id, self)

        # Simulated network delay to join
        announce_payload_kb = self.config.join_announcement_size_kb
        upload_speed_kbps = self.upload_speed_mb_s * 1024
        delay_ticks = announce_payload_kb / upload_speed_kbps

        jitter = self.cached_rng.uniform(0, 0.25)
        total_delay = delay_ticks + jitter

        # Previously: known_peers = self.nal.announce_self(...) — no longer needed
        self.join_tick = current_tick
        self.has_joined = True

        print(f"[JOIN] {self.id} joined at tick {current_tick}")
