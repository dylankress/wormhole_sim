from sim_file import SimFile

def receive_file(rng, index, owner):
    suffix = rng.randint(1000, 9999)
    file_name = f"file_{index}_{suffix}"
    file_size = rng.randint(1, 1000)  # Simulate file size between 1MB and 10GB
    return SimFile(file_name, file_size, owner=owner)

def receive_files(rng, start_index, count, owner):
    return [receive_file(rng, start_index + i, owner) for i in range(count)]