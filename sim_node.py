class SimNode:
    def __init__(self, node_id: str, upload_speed_mb_s: int, download_speed_mb_s: int, total_space_gb: int, is_new_user: bool, config):
        self.id = node_id

        self.upload_speed_mb_s = upload_speed_mb_s
        self.download_speed_mb_s = download_speed_mb_s

        self.free_space_gb = total_space_gb
        self.total_space_gb = total_space_gb

        self.is_new_user = is_new_user
        self.online = False
        self.known_peers = set()

        self.join_tick = None
        self.hosted_chunks = set()
        self.has_joined = False
        self.last_bootstrap_tick = None
        self.was_online_last_tick = False

        self.force_offline_until = None  # Used by blackout_manager to override uptime

        self.auth_secret = "default"
        self.password_seed = "default"

        self.config = config
        self.timezone_offset = None  # Assigned in node_generator

        self.files_uploaded = []

    def __repr__(self):
        return (f"<SimNode id={self.id} "
                f"online={self.online} "
                f"upload_speed={self.upload_speed_mb_s}MB/s "
                f"peers={len(self.known_peers)} "
                f"free={self.free_space_gb}GB "
                f"blackout={self.force_offline_until is not None}>")
    
    def attempt_join(self, bootstrap_server, current_tick):
        # Simulate announcement delay
        announce_payload_kb = self.config.join_announcement_size_kb
        upload_speed_kbps = self.upload_speed_mb_s * 1024
        delay_ticks = announce_payload_kb / upload_speed_kbps

        rng = self.config.child_rng(f"join_delay_{self.id}_{current_tick}")
        jitter = rng.uniform(0, 0.25)
        total_delay = delay_ticks + jitter

        simulated_completion_tick = current_tick + total_delay

        known_peers = bootstrap_server.register_node(self, current_tick)
        self.join_tick = current_tick
        self.known_peers.update(known_peers)
        self.has_joined = True

        #if current_tick > 0:
            #print(f"🛰 Tick {current_tick}: node {self.id} joined the network")
            #print(f"Tick {current_tick:.2f}: node {self.id} is now online with {len(self.known_peers)} known peers")
