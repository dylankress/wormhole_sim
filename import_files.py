from sim_file import SimFile

def generate_file_size(rng):
    size_ranges = [
        (1, 10),          # 1–10 MB: text documents, small photos
        (10, 100),        # high-res images, app installers
        (100, 500),       # low-res videos, compressed folders
        (500, 1024),      # HD videos, game data
        (1024, 10240),    # full movies, larger app bundles
        (10240, 102400),  # 4K footage, compressed backups
        (102400, 1048576) # raw 4K/8K footage, disk images
    ]
    weights = [25, 30, 20, 10, 10, 4, 1]
    selected_range = rng.choices(size_ranges, weights=weights, k=1)[0]
    return rng.randint(selected_range[0], selected_range[1])  # in MB

def receive_file(rng, index, owner):
    suffix = rng.randint(1000, 9999)
    file_name = f"file_{index}_{suffix}"
    file_size = generate_file_size(rng)
    return SimFile(file_name, file_size, owner=owner)

def receive_files(rng, start_index, count, owner):
    return [receive_file(rng, start_index + i, owner) for i in range(count)]