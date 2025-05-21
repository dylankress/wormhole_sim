import random

class BootstrapServer:
    def __init__(self, config):
        self.config = config
        self.registered_peers = {}  # peer_id -> SimNode reference

    def register_node(self, node, tick):
        """
        Simulates a node announcing itself to the network.
        Returns a deterministic list of known peer IDs for bootstrap discovery.
        """
        peer_id = node.id

        # Register the node
        self.registered_peers[peer_id] = node

        # Log join
        if tick > 0:
            print(f"🛰 Tick {tick}: node {peer_id} joined the network")

        # Return a deterministic list of other peer IDs
        rng = self.config.child_rng(f"bootstrap_response_{peer_id}_{tick}")
        known_peer_ids = list(self.registered_peers.keys())
        known_peer_ids.remove(peer_id)  # Don't return self

        # Limit to a max peer list size (e.g., 5)
        sample_size = min(len(known_peer_ids), self.config.bootstrap_peer_sample_size)
        known_sample = rng.sample(known_peer_ids, sample_size) if sample_size > 0 else []

        return known_sample