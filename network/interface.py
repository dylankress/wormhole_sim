# network/interface.py

from abc import ABC, abstractmethod

class PeerDiscoveryClient(ABC):
    @abstractmethod
    def announce_self(self, peer_id: str, port: int, capabilities: dict) -> list[str]: ...
    
    @abstractmethod
    def fetch_peer_list(self, peer_id: str) -> list[str]: ...
    
    @abstractmethod
    def refresh_peer_score(self, peer_id: str, score: float) -> None: ...


class ChunkTransferClient(ABC):
    @abstractmethod
    def upload_chunk(self, chunk_id: str, chunk_data: bytes, target_peer: str) -> bool: ...
    
    @abstractmethod
    def download_chunk(self, chunk_id: str, source_peer: str) -> bytes: ...
    
    @abstractmethod
    def verify_chunk_integrity(self, chunk_id: str, hash_val: str, peer_id: str) -> bool: ...


class ManifestSyncClient(ABC):
    @abstractmethod
    def update_manifest_chunk_location(self, file_id: str, chunk_id: str, new_peer: str) -> None: ...
    
    @abstractmethod
    def push_full_manifest(self, file_id: str, encrypted_manifest: bytes, owner_peer: str) -> bool: ...
    
    @abstractmethod
    def fetch_manifest(self, file_id: str, auth_token: str) -> bytes: ...


class ChunkCleanupClient(ABC):
    @abstractmethod
    def acknowledge_download_complete(self, file_id: str, chunk_ids: list[str], source_peer: str) -> None: ...
    
    @abstractmethod
    def delete_chunk(self, chunk_id: str, peer_id: str) -> bool: ...
    
    @abstractmethod
    def cleanup_stale_chunks(self, peer_id: str) -> int: ...


class PeerGossipAgent(ABC):
    @abstractmethod
    def broadcast_peer_state(self, peer_id: str, score: float, storage_used: int, uptime: float) -> None: ...
    
    @abstractmethod
    def receive_peer_updates(self) -> list[dict]: ...
