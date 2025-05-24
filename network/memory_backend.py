# network/memory_backend.py

import random
from collections import defaultdict
from network.interface import (
    PeerDiscoveryClient,
    ChunkTransferClient,
    ManifestSyncClient,
    ChunkCleanupClient,
    PeerGossipAgent,
)

class InMemoryNetwork(
    PeerDiscoveryClient,
    ChunkTransferClient,
    ManifestSyncClient,
    ChunkCleanupClient,
    PeerGossipAgent
):
    def __init__(self, seed: int = 42, config=None):
        self.rng = random.Random(seed)
        self.config = config or {}
        self.peers = {}  # peer_id -> metadata dict
        self.peer_chunks = defaultdict(dict)  # peer_id -> {chunk_id: bytes}
        self.manifests = defaultdict(dict)  # file_id -> manifest bytes
        self.peer_scores = {}  # peer_id -> float
        self.uploads_this_tick = {}       # peer_id → chunk count this tick
        self.peer_nodes = {}              # peer_id → SimNode reference
        self.last_tick = -1

    # --- PeerDiscoveryClient ---

    def get_eligible_upload_targets(self, exclude_ids=None, min_free_gb=0.01):
        """
        Return a list of online peers that have at least `min_free_gb` available.
        Optionally excludes peers by ID (e.g., uploader).
        """
        exclude_ids = exclude_ids or set()
        return [
            node for node in self.peer_nodes.values()
            if node.online
            and node.free_space_gb >= min_free_gb
            and node.id not in exclude_ids
        ]

    def announce_self(self, peer_id: str, port: int, capabilities: dict) -> list:
        self.peers[peer_id] = {
            "port": port,
            "capabilities": capabilities,
        }

        candidates = [
            (pid, self.peer_nodes[pid])
            for pid in self.peers
            if pid != peer_id and pid in self.peer_nodes and self.peer_nodes[pid].online
        ]

        # Sort by score descending, then randomly shuffle top N
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (-self.peer_scores.get(x[0], 0.0), x[0])
        )

        top_peers = [node for _, node in sorted_candidates[:20]]
        self.rng.shuffle(top_peers)
        return top_peers

    def fetch_peer_list(self, peer_id: str) -> list[str]:
        online_peers = [
            pid for pid in self.peers
            if pid != peer_id and pid in self.peer_nodes and self.peer_nodes[pid].online
        ]
        self.rng.shuffle(online_peers)
        return online_peers[:20]

    def refresh_peer_score(self, peer_id: str, score: float) -> None:
        self.peer_scores[peer_id] = score

    # --- ChunkTransferClient ---
    def upload_chunk(self, chunk_id: str, chunk_data: bytes, target_peer: str, uploader_id: str) -> bool:
        self.peer_chunks[target_peer][chunk_id] = chunk_data
        #print(f"[NAL] Uploaded {chunk_id} to {target_peer} from {uploader_id}")
        return True

    def download_chunk(self, chunk_id: str, source_peer: str) -> bytes:
        return self.peer_chunks[source_peer].get(chunk_id, b"")

    def verify_chunk_integrity(self, chunk_id: str, hash_val: str, peer_id: str) -> bool:
        chunk = self.peer_chunks[peer_id].get(chunk_id)
        return chunk is not None and hash(chunk) == hash(hash_val)

    # --- ManifestSyncClient ---
    def update_manifest_chunk_location(self, file_id: str, chunk_id: str, new_peer: str) -> None:
        self.manifests[file_id][chunk_id] = new_peer
        print(f"[MANIFEST] {file_id}: {chunk_id} → {new_peer}")

    def push_full_manifest(self, file_id: str, encrypted_manifest: bytes, owner_peer: str) -> bool:
        self.manifests[file_id]["manifest"] = encrypted_manifest
        return True

    def fetch_manifest(self, file_id: str, auth_token: str) -> bytes:
        return self.manifests[file_id].get("manifest", b"")

    # --- ChunkCleanupClient ---
    def acknowledge_download_complete(self, file_id: str, chunk_ids: list[str], source_peer: str) -> None:
        for chunk_id in chunk_ids:
            self.peer_chunks[source_peer].pop(chunk_id, None)

    def delete_chunk(self, chunk_id: str, peer_id: str) -> bool:
        return self.peer_chunks[peer_id].pop(chunk_id, None) is not None

    def cleanup_stale_chunks(self, peer_id: str) -> int:
        count = len(self.peer_chunks[peer_id])
        self.peer_chunks[peer_id] = {}
        return count

    # --- PeerGossipAgent ---
    def broadcast_peer_state(self, peer_id: str, score: float, storage_used: int, uptime: float) -> None:
        self.peer_scores[peer_id] = score

    def receive_peer_updates(self) -> list[dict]:
        return [
            {"peer_id": pid, "score": self.peer_scores.get(pid, 0.0)}
            for pid in sorted(self.peers.keys())
        ]

    def register_peer(self, peer_id: str, node) -> None:
        self.peer_nodes[peer_id] = node
        if peer_id not in self.peer_chunks:
            self.peer_chunks[peer_id] = {}