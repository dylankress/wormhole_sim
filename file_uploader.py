from import_files import receive_files

class FileUploader:
    def __init__(self, rng, config, nodes, nal, reverse_index):
        self.rng = rng
        self.config = config
        self.nodes = nodes
        self.nal = nal
        self.reverse_index = reverse_index

        self.next_file_index = 0
        self.total_attempts = 0
        self.total_successes = 0
        self.total_files_attempted = 0
        self.total_files_successful = 0
        self.total_data_uploaded_mb = 0
        self.disk_full_skips = 0

    def tick(self, current_tick):
        ready_files = []

        # Exit early if upload is not triggered this tick
        if self.rng.random() >= self.config.file_upload_rate:
            return ready_files

        # Find eligible uploaders
        num_files = self.rng.randint(1, self.config.max_files_per_tick)
        online_nodes = [n for n in self.nodes if n.online and n.free_space_gb > 0]
        if not online_nodes:
            return ready_files

        chosen_node = self.rng.choice(online_nodes)
        files = receive_files(self.rng, self.next_file_index, num_files, chosen_node)
        self.next_file_index += num_files
        self.total_files_attempted += len(files)

        for file in files:
            chosen_node.files_uploaded.append(file)
            chunk_size = self.config.chunk_size_mb
            replication_factor = self.config.replication_factor
            num_chunks = max(1, file.file_size // chunk_size + int(file.file_size % chunk_size > 0))

            eligible_peers = self.nal.get_eligible_upload_targets(
                exclude_ids={chosen_node.id},
                min_free_gb=(chunk_size / 1024)
            )

            if len(eligible_peers) < replication_factor:
                continue  # Not enough replication targets

            selected_peers = sorted(
                self.rng.sample(eligible_peers, min(len(eligible_peers), replication_factor * 2)),
                key=lambda p: (p.free_space_gb, -p.upload_speed_mb_s)
            )[:replication_factor]

            for i in range(num_chunks):
                chunk_id = f"{file.file_name}_chunk_{i}"
                chunk_data = f"chunkdata:{chunk_id}".encode("utf-8")

                for peer in selected_peers:
                    if peer.free_space_gb < (chunk_size / 1024):
                        self.disk_full_skips += 1
                        continue

                    success = self.nal.upload_chunk(chunk_id, chunk_data, peer.id, uploader_id=chosen_node.id)
                    self.total_attempts += 1

                    if success:
                        self.total_successes += 1
                        peer.hosted_chunks.add(chunk_id)
                        peer.free_space_gb -= (chunk_size / 1024)
                        self.reverse_index.setdefault(chunk_id, set()).add(peer.id)
                        self.total_data_uploaded_mb += chunk_size
                    else:
                        print(f"[UPLOAD FAILED] {chunk_id} to {peer.id}")

            self.total_files_successful += 1
            ready_files.append(file)
            for node in self.nodes:
                if file.file_name in [f.file_name for f in node.files_uploaded]:
                    node.replication_status[file.file_name] = "replicated"

        return ready_files

    def print_summary(self, total_ticks):
        total_gb = self.total_data_uploaded_mb / 1024
        avg_file_size_gb = total_gb / max(1, self.total_files_successful)
        sim_hours = total_ticks / 3600

        print(f"\n[SUMMARY]")
        print(f"  Simulation time  : {sim_hours:.2f} hours")
        print(f"  Files attempted  : {self.total_files_attempted}")
        print(f"  Files uploaded   : {self.total_files_successful}")
        print(f"  Success rate     : {100 * self.total_files_successful / max(1, self.total_files_attempted):.2f}%")
        print(f"  Data uploaded    : {total_gb:.2f} GB")
        print(f"  Avg file size    : {avg_file_size_gb:.2f} GB")
        print(f"  Disk full skips  : {self.disk_full_skips}")

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

        underutilized = [n for n in self.nodes if len(n.hosted_chunks) < 100]
        print(f"\n[UNDERUTILIZED PEERS]: {len(underutilized)} nodes with < 100 chunks")
