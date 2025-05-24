import random

class FileDownloader:
    def __init__(self, config, nodes, nal, reverse_index, rng):
        self.config = config
        self.nodes = nodes
        self.nal = nal
        self.reverse_index = reverse_index
        self.rng = rng

        self.download_interval_range = (60, 300)  # 1–5 minutes in ticks
        self.next_download_tick = {}  # node_id → next scheduled tick
        self.pending_downloads = []

        # Tracking
        self.total_requests = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.total_download_time = 0
        self.download_durations = []

        self.downloaded_files = {}  # node_id → list of file names
        self.active_downloads = {}  # file_name → metadata

    def _next_trigger(self, current_tick):
        min_t, max_t = self.download_interval_range
        return current_tick + self.rng.randint(min_t, max_t)

    def schedule_next(self, node_id, current_tick):
        self.next_download_tick[node_id] = self._next_trigger(current_tick)

    def tick(self, current_tick):
        still_pending = []

        for job in self.pending_downloads:
            if current_tick < job["ready_at"]:
                still_pending.append(job)
                continue

            file_name = job["file_name"]
            if file_name in self.active_downloads:
                self.active_downloads[file_name]["chunks_downloaded"] += 1
                if self.active_downloads[file_name]["chunks_downloaded"] >= self.active_downloads[file_name]["chunks_total"]:
                    self.active_downloads[file_name]["completed"] = True
                    duration = current_tick - self.active_downloads[file_name]["start_tick"]
                    self.download_durations.append(duration)

        self.pending_downloads = still_pending

        for node in self.nodes:
            if not node.online:
                continue

            if node.id not in self.next_download_tick:
                self.schedule_next(node.id, current_tick)

            if current_tick < self.next_download_tick[node.id]:
                continue

            eligible_files = [
                f.file_name for f in node.files_uploaded
                if getattr(node, "replication_status", {}).get(f.file_name) == "replicated"
            ]

            if not eligible_files:
                self.schedule_next(node.id, current_tick)
                continue

            file_name = self.rng.choice(eligible_files)
            chunk_ids = [
                cid for cid in self.reverse_index
                if cid.startswith(file_name + "_chunk_") and "replica" not in cid
            ]

            if not chunk_ids:
                self.failed_downloads += 1
                self.total_requests += 1
                self.schedule_next(node.id, current_tick)
                continue

            chunks_downloaded = set()
            self.active_downloads[file_name] = {
                "start_tick": current_tick,
                "chunks_total": len(chunk_ids),
                "chunks_downloaded": 0,
                "completed": False
            }

            for chunk_id in chunk_ids:
                if chunk_id in chunks_downloaded:
                    continue

                hosts = [
                    peer for peer in self.nodes
                    if peer.id in self.reverse_index.get(chunk_id, []) and peer.online
                ]
                if not hosts:
                    continue  # silently skip this chunk

                source = self.rng.choice(hosts)
                speed = min(source.upload_speed_mb_s, node.download_speed_mb_s)
                ticks = max(1, int(self.config.chunk_size_mb / speed))

                self.pending_downloads.append({
                    "chunk_id": chunk_id,
                    "file_name": file_name,
                    "node_id": node.id,
                    "ready_at": current_tick + ticks
                })

                chunks_downloaded.add(chunk_id)

            self.total_requests += 1
            if len(chunks_downloaded) == len(chunk_ids):
                self.successful_downloads += 1
                self.downloaded_files.setdefault(node.id, []).append(file_name)
            else:
                self.failed_downloads += 1

            self.schedule_next(node.id, current_tick)

    def print_summary(self, total_ticks):
        sim_minutes = total_ticks / 60
        completed_downloads = self.successful_downloads
        in_progress_downloads = len([
            d for d in self.active_downloads.values()
            if not d.get("completed", False)
        ])

        print(f"\n[DOWNLOAD SUMMARY]")
        print(f"  Simulation time     : {sim_minutes:.2f} min")
        print(f"  Files requested     : {self.total_requests}")
        print(f"  Files downloaded    : {completed_downloads}")
        print(f"  Success rate        : {100 * completed_downloads / max(1, self.total_requests):.2f}%")

        avg_time = (sum(self.download_durations) / len(self.download_durations)) if self.download_durations else 0
        print(f"  Avg download time   : {avg_time:.2f} ticks")
        print(f"  In-progress (excluded): {in_progress_downloads}")
        print(f"  Failed downloads    : {self.failed_downloads}")
