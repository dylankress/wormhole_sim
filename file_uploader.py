from import_files import receive_files

class FileUploader:
    def __init__(self, rng, config, nodes, nal):
        self.rng = rng
        self.config = config
        self.nodes = nodes
        self.next_file_index = 0
        self.pending_writes = []  # files currently being written
        self.nal = nal

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
                "ready_at": current_tick + ticks_needed
            })

            print(f"[WRITE] Node {chosen_node.id} uploading {num_files} file(s), ready @ tick {current_tick + ticks_needed}")

        ready_files = []
        for batch in self.pending_writes[:]:
            if batch["ready_at"] <= current_tick:
                ready_files.extend(batch["files"])
                self.pending_writes.remove(batch)

                for file in ready_files:
                    self._process_file_upload(file)

        return ready_files
    
    def _process_file_upload(self, file):
        # Simulate chunking the file into pieces
        chunk_size_mb = self.config.chunk_size_mb
        total_chunks = max(1, file.file_size // chunk_size_mb)

        for i in range(total_chunks):
            chunk_id = f"{file.file_name}_chunk_{i}"
            chunk_data = f"chunkdata:{chunk_id}".encode("utf-8")  # Simulated bytes
            target_node = self.rng.choice(self.nodes)

            success = self.nal.upload_chunk(chunk_id, chunk_data, target_node.id)
            if success:
                target_node.hosted_chunks.add(chunk_id)
                print(f"[UPLOAD] {file.file_name} → {target_node.id} ({chunk_id})")

        # Optionally log
        # print(f"[UPLOAD] File {file.file_id} uploaded in {total_chunks} chunks.")
