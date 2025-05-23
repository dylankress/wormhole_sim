from import_files import receive_files

class FileUploader:
    def __init__(self, rng, config, nodes, nal, reverse_index):
        self.rng = rng
        self.config = config
        self.nodes = nodes
        self.next_file_index = 0
        self.pending_writes = []
        self.pending_chunks = []
        self.nal = nal
        self.reverse_index = reverse_index

        self.total_attempts = 0
        self.total_successes = 0
        self.total_files_attempted = 0
        self.total_files_successful = 0
        self.total_data_uploaded_mb = 0

        self.pending_file_uploads = {}
        self.replicated_files = 0
        self.replication_timers = {}
        self.pending_replicas = {}
        self.disk_full_skips = 0

    def get_next_online_high_score_peer(self, uploader):
        online_peers = [p for p in uploader.known_peers if p.online]
        if not online_peers:
            return None
        top_peers = sorted(online_peers, key=lambda p: (-p.score, p.id))[:20]
        if not top_peers:
            return None
        target = top_peers[uploader.round_robin_index % len(top_peers)]
        uploader.round_robin_index += 1
        return target

    def tick(self, current_tick):
        new_files = []

        if self.rng.random() < self.config.file_upload_rate:
            num_files = self.rng.randint(1, self.config.max_files_per_tick)
            online_nodes = [n for n in self.nodes if n.online]
            if not online_nodes:
                return []

            chosen_node = self.rng.choice(online_nodes)
            assert chosen_node.online

            files = receive_files(self.rng, self.next_file_index, num_files, chosen_node)
            self.next_file_index += num_files

            for f in files:
                chosen_node.files_uploaded.append(f)

            total_size = sum(f.file_size for f in files)
            ticks_needed = max(1, int(total_size / self.config.disk_write_speed_mb_s))

            self.pending_writes.append({
                "files": files,
                "uploader": chosen_node,
                "ready_at": current_tick + ticks_needed
            })

        ready_files = []
        for batch in self.pending_writes[:]:
            if batch["ready_at"] <= current_tick:
                files = batch["files"]
                uploader = batch["uploader"]
                ready_files.extend(files)
                self.pending_writes.remove(batch)

                for file in files:
                    chunk_size_mb = self.config.chunk_size_mb
                    total_chunks = max(1, file.file_size // chunk_size_mb)
                    self.total_files_attempted += 1
                    self.pending_file_uploads[file.file_name] = total_chunks
                    self.total_data_uploaded_mb += file.file_size

                    for i in range(total_chunks):
                        chunk_id = f"{file.file_name}_chunk_{i}"
                        chunk_data = f"chunkdata:{chunk_id}".encode("utf-8")
                        target_node = None
                        peer_pool = sorted(
                            [p for p in uploader.known_peers if p.online],
                            key=lambda p: (-p.score, p.id)
                        )

                        target_node = None
                        for _ in range(len(peer_pool)):
                            candidate = peer_pool[uploader.round_robin_index % len(peer_pool)]
                            uploader.round_robin_index += 1
                            if candidate.free_space_gb >= (chunk_size_mb / 1024):
                                target_node = candidate
                                break

                        if not target_node:
                            self.disk_full_skips += 1
                            continue

                        speed = min(uploader.upload_speed_mb_s, target_node.download_speed_mb_s)
                        transfer_ticks = max(1, int(chunk_size_mb / speed))

                        self.pending_chunks.append({
                            "chunk_id": chunk_id,
                            "chunk_data": chunk_data,
                            "uploader": uploader,
                            "target": target_node,
                            "file_name": file.file_name,
                            "ready_at": current_tick + transfer_ticks,
                            "replication_origin": "uploader"
                        })

        still_pending = []
        for job in self.pending_chunks:
            if job["ready_at"] > current_tick:
                still_pending.append(job)
                continue

            self.total_attempts += 1

            if job["target"].free_space_gb < (self.config.chunk_size_mb / 1024):
                self.disk_full_skips += 1
                continue

            success = self.nal.upload_chunk(
                chunk_id=job["chunk_id"],
                chunk_data=job["chunk_data"],
                target_peer=job["target"].id,
                uploader_id=job["uploader"].id
            )

            if success:
                self.total_successes += 1
                job["target"].hosted_chunks.add(job["chunk_id"])
                job["target"].free_space_gb -= (self.config.chunk_size_mb / 1024)

                base_chunk_id = job["chunk_id"]
                if "_replica_" in base_chunk_id:
                    base_chunk_id = base_chunk_id.split("_replica_")[0]
                self.reverse_index.setdefault(base_chunk_id, set()).add(job["target"].id)

                if job["replication_origin"] == "uploader":
                    host_node = job["target"]
                    uploader_id = job["uploader"].id
                    eligible = [p for p in host_node.known_peers if p.online and p.id != uploader_id]
                    top_targets = sorted(eligible, key=lambda p: (-p.score, p.id))

                    replicas = 0
                    for peer in top_targets:
                        if peer.free_space_gb < (self.config.chunk_size_mb / 1024):
                            self.disk_full_skips += 1
                            continue

                        replica_id = f"{job['chunk_id']}_replica_{replicas}"
                        speed = min(host_node.upload_speed_mb_s, peer.download_speed_mb_s)
                        transfer_ticks = max(1, int(self.config.chunk_size_mb / speed))

                        self.pending_chunks.append({
                            "chunk_id": replica_id,
                            "chunk_data": job["chunk_data"],
                            "uploader": host_node,
                            "target": peer,
                            "file_name": job["file_name"],
                            "ready_at": current_tick + transfer_ticks,
                            "replication_origin": "replica"
                        })
                        replicas += 1
                        if replicas == 2:
                            break

                if job["replication_origin"] == "replica":
                    if job["file_name"] in self.pending_replicas:
                        self.pending_replicas[job["file_name"]] -= 1
                        if self.pending_replicas[job["file_name"]] == 0:
                            self.replicated_files += 1
                            self.replication_timers[job["file_name"]][1] = current_tick
                            for node in self.nodes:
                                if any(f.file_name == job["file_name"] for f in node.files_uploaded):
                                    node.replication_status[job["file_name"]] = "replicated"

                if job["file_name"] in self.pending_file_uploads:
                    self.pending_file_uploads[job["file_name"]] -= 1
                    if self.pending_file_uploads[job["file_name"]] <= 0:
                        del self.pending_file_uploads[job["file_name"]]
                        self.replication_timers[job["file_name"]] = [current_tick, None]
                        self.pending_replicas[job["file_name"]] = sum(
                            1 for cid in job["uploader"].hosted_chunks if cid.startswith(f"{job['file_name']}_chunk_")
                        ) * 2
            else:
                print(f"[FAILED] {job['file_name']} ✖ {job['target'].id} ({job['chunk_id']})")

        to_delete = [fname for fname, count in self.pending_replicas.items() if count <= 0]
        for fname in to_delete:
            del self.pending_replicas[fname]

        self.pending_chunks = still_pending
        return ready_files

    def print_summary(self, total_ticks):
        total_gb = self.total_data_uploaded_mb / 1024
        completed_files = set(self.replication_timers.keys()) - set(self.pending_file_uploads.keys())
        completed_count = len([f for f in completed_files if self.replication_timers[f][0] is not None])
        avg_file_size_gb = (total_gb / completed_count) if completed_count else 0
        sim_hours = total_ticks / 3600

        print(f"\n[SUMMARY]")
        print(f"  Simulation time  : {sim_hours:.2f} hours")
        print(f"  Files attempted  : {self.total_files_attempted}")
        print(f"  Files uploaded   : {completed_count}")
        print(f"  Success rate     : {100 * completed_count / max(1, self.total_files_attempted):.2f}%")
        print(f"  Data uploaded    : {total_gb:.2f} GB")
        print(f"  Avg file size    : {avg_file_size_gb:.2f} GB")
        print(f"  Disk full skips  : {self.disk_full_skips}")

        pending_replication_files = {
            fname for fname, (start, end) in self.replication_timers.items()
            if start is not None and end is None and fname not in self.pending_file_uploads
        }
        pending = len(pending_replication_files)

        replication_pct = (100 * self.replicated_files / max(1, len(self.replication_timers)))
        completed = [
            (end - start) for (start, end) in self.replication_timers.values()
            if start is not None and end is not None
        ]
        avg_rep_minutes = (sum(completed) / len(completed) / 60) if completed else 0

        print(f"\n[REPLICATION]")
        print(f"  Files replicated : {self.replicated_files}")
        print(f"  Pending files    : {pending}")
        print(f"  Success rate     : {replication_pct:.2f}%")
        print(f"  Avg replication  : {avg_rep_minutes:.2f} min")

        print(f"\n[HOSTED CHUNKS PER NODE]")
        sorted_nodes = sorted(
            [node for node in self.nodes if len(node.hosted_chunks) > 0],
            key=lambda n: len(n.hosted_chunks),
            reverse=True
        )
        for node in sorted_nodes:
            count = len(node.hosted_chunks)
            gb = (count * self.config.chunk_size_mb) / 1024
            print(f"{node.id} (score: {node.score}) : {count} chunk(s), {gb:.2f} GB")
