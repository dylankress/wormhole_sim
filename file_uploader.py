from import_files import receive_files

class FileUploader:
    def __init__(self, rng, config, nodes, nal):
        self.rng = rng
        self.config = config
        self.nodes = nodes
        self.next_file_index = 0
        self.pending_writes = []  # files currently being written
        self.pending_chunks = []  # deferred chunks due to throttling
        self.nal = nal

        self.total_attempts = 0
        self.total_successes = 0

    def tick(self, current_tick):
        new_files = []

        if self.rng.random() < self.config.file_upload_rate:
            num_files = self.rng.randint(1, self.config.max_files_per_tick)

            # ✅ Choose from online nodes only
            online_nodes = [n for n in self.nodes if n.online]
            if not online_nodes:
                return []  # No one is online this tick

            chosen_node = self.rng.choice(online_nodes)

            assert chosen_node.online, f"[ERROR] Upload initiated by offline node: {chosen_node.id}"

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

            print(f"[WRITE] Node {chosen_node.id} uploading {num_files} file(s), ready @ tick {current_tick + ticks_needed}")

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

                    for i in range(total_chunks):
                        chunk_id = f"{file.file_name}_chunk_{i}"
                        chunk_data = f"chunkdata:{chunk_id}".encode("utf-8")
                        target_node = self.rng.choice(self.nodes)

                        # Calculate time delay based on bottleneck speed
                        speed = min(uploader.upload_speed_mb_s, target_node.download_speed_mb_s)
                        transfer_ticks = max(1, int(chunk_size_mb / speed))

                        self.pending_chunks.append({
                            "chunk_id": chunk_id,
                            "chunk_data": chunk_data,
                            "uploader": uploader,
                            "target": target_node,
                            "file_name": file.file_name,
                            "ready_at": current_tick + transfer_ticks
                        })

        # Process chunks that are ready
        still_pending = []
        for job in self.pending_chunks:
            if job["ready_at"] > current_tick:
                still_pending.append(job)
                continue

            self.total_attempts += 1
            success = self.nal.upload_chunk(
                chunk_id=job["chunk_id"],
                chunk_data=job["chunk_data"],
                target_peer=job["target"].id,
                uploader_id=job["uploader"].id
            )

            if success:
                self.total_successes += 1
                job["target"].hosted_chunks.add(job["chunk_id"])
                print(f"[UPLOAD] {job['file_name']} → {job['target'].id} ({job['chunk_id']})")
            else:
                print(f"[FAILED] {job['file_name']} ✖ {job['target'].id} ({job['chunk_id']})")

        self.pending_chunks = still_pending
        return ready_files

    def print_summary(self):
        total_chunks = self.total_successes
        chunk_size_mb = self.config.chunk_size_mb
        total_gb = (total_chunks * chunk_size_mb) / 1024

        print(f"\n[SUMMARY]")
        print(f"  Upload attempts  : {self.total_attempts}")
        print(f"  Successes        : {self.total_successes}")
        print(f"  Success rate     : {100 * self.total_successes / max(1, self.total_attempts):.2f}%")
        print(f"  Data uploaded    : {total_gb:.2f} GB\n")

        print("[HOSTED CHUNKS PER NODE]")
        for node in self.nodes:
            count = len(node.hosted_chunks)
            if count > 0:
                print(f"  {node.id} : {count} chunk(s)")
