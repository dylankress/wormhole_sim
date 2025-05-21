from import_files import receive_files

class FileUploader:
    def __init__(self, rng, config, nodes):
        self.rng = rng
        self.config = config
        self.nodes = nodes
        self.next_file_index = 0
        self.pending_writes = []  # files currently being written

    def tick(self, current_tick):
        new_files = []

        if self.rng.random() < self.config.file_upload_rate:
            num_files = self.rng.randint(1, self.config.max_files_per_tick)
            chosen_node = self.rng.choice(self.nodes)
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

            #print(f"[TICK {current_tick}] Node {chosen_node.id} started uploading {num_files} file(s) ({total_size}MB), ready at tick {current_tick + ticks_needed}")

        ready_files = []
        for batch in self.pending_writes[:]:
            if batch["ready_at"] <= current_tick:
                ready_files.extend(batch["files"])
                self.pending_writes.remove(batch)

        return ready_files