import os
import random
import datetime
import argparse
import csv
import matplotlib.pyplot as plt
import pandas as pd

from config import SimulationConfig
from sim_clock import SimClock
from file_uploader import FileUploader
from node_generator import generate_nodes
from bootstrap_server import BootstrapServer

def parse_args():
    parser = argparse.ArgumentParser(description="Run Wormhole simulation.")
    parser.add_argument("--seed", type=int, help="use seed to generate a repeatable simulation outcome")
    return parser.parse_args()

def save_seed(seed: int, output_dir: str = "logs/seeds"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_file = os.path.join(output_dir, f"seed_{timestamp}.txt")
    with open(seed_file, "w") as f:
        f.write(f"{seed}\n")

def main():
    args = parse_args()
    seed = args.seed if args.seed is not None else random.randint(1, 1_000_000)
    save_seed(seed)

    connected_counts = []

    config = SimulationConfig(seed=seed)
    clock = SimClock()

    node_rng = config.child_rng("nodes")
    nodes = generate_nodes(node_rng, config.total_nodes, config)
    bootstrap_server = BootstrapServer(config)

    # Set last tick status for all nodes
    for node in nodes:
        node.was_online_last_tick = False

    file_rng = config.child_rng("file")
    uploader = FileUploader(file_rng, config, nodes)
    all_uploaded_files = []

    for _ in range(config.total_ticks):
        current_tick = clock.current()

        if current_tick == 0:
            for profile, weight in config.behavior_distribution.items():
                print(f"  - {profile:15s}: {weight*100:.1f}%")

        for node in nodes:
            node.online = node.behavior_profile.is_online(current_tick)
            came_online = node.online and not node.was_online_last_tick
            went_offline = not node.online and node.was_online_last_tick

            if came_online:
                print(f"[JOIN EVENT] {node.id} online at tick {current_tick}, joined={node.has_joined}, peers={len(node.known_peers)}")
                if not node.has_joined:
                    node.attempt_join(bootstrap_server, current_tick)
                    node.last_bootstrap_tick = current_tick
                elif len(node.known_peers) < 2:
                    cooldown = config.rebootstrap_cooldown_ticks
                    last = node.last_bootstrap_tick or -cooldown
                    if current_tick - last >= cooldown:
                        node.attempt_join(bootstrap_server, current_tick)
                        node.last_bootstrap_tick = current_tick

            if went_offline:
                print(f"[OFFLINE EVENT] {node.id} went offline at tick {current_tick}")

            node.was_online_last_tick = node.online

        count_connected = sum(1 for n in nodes if n.online and n.has_joined)
        connected_counts.append((current_tick, count_connected))

        new_files = uploader.tick(current_tick)
        for f in new_files:
            all_uploaded_files.append(f)

        clock.advance()

    os.makedirs("logs", exist_ok=True)
    with open("logs/connected_counts.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tick", "connected_nodes"])
        for tick, count in connected_counts:
            writer.writerow([tick, count])

    df = pd.read_csv("logs/connected_counts.csv")
    plt.plot(df["tick"], df["connected_nodes"])
    plt.xlabel("Tick")
    plt.ylabel("Connected Nodes")
    plt.title("Connected Node Count Over Time")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
