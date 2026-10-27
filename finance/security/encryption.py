"""
Encryption module for sensitive financial data.
Provides encryption at rest and in transit using industry-standard algorithms.
"""

import os
import base64
import secrets
import logging
from typing import Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
    BestAvailableEncryption,
    load_pem_private_key,
    load_pem_public_key,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidTag, InvalidSignature
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "AES-256-GCM"
    CHACHA20_POLY1305 = "CHACHA20-POLY1305"
    FERNET = "FERNET"  # AES-128-CBC with HMAC


class KeyDerivationAlgorithm(Enum):
    """Supported key derivation functions."""
    PBKDF2_SHA256 = "PBKDF2-SHA256"
    HKDF_SHA256 = "HKDF-SHA256"


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata."""
    ciphertext: bytes
    nonce: bytes
    tag: Optional[bytes] = None
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    associated_data: Optional[bytes] = None
    key_id: Optional[str] = None

    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage/transmission."""
        parts = [
            self.algorithm.value.encode(),
            base64.b64encode(self.nonce),
            base64.b64encode(self.ciphertext),
        ]
        if self.tag:
            parts.append(base64.b64encode(self.tag))
        if self.associated_data:
            parts.append(base64.b64encode(self.associated_data))
        if self.key_id:
            parts.append(self.key_id.encode())
        return b"|".join(parts)

    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedData":
        """Deserialize from bytes."""
        parts = data.split(b"|")
        if len(parts) < 3:
            raise ValueError("Invalid encrypted data format")

        algorithm = EncryptionAlgorithm(parts[0].decode())
        nonce = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        tag = base64.b64decode(parts[3]) if len(parts) > 3 and parts[3] else None
        associated_data = base64.b64decode(parts[4]) if len(parts) > 4 and parts[4] else None
        key_id = parts[5].decode() if len(parts) > 5 and parts[5] else None

        return cls(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            algorithm=algorithm,
            associated_data=associated_data,
            key_id=key_id,
        )


@dataclass
class KeyPair:
    """Asymmetric key pair for hybrid encryption."""
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    key_id: str

    @classmethod
    def generate(cls, key_size: int = 4096, key_id: Optional[str] = None) -> "KeyPair":
        """Generate a new RSA key pair."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        public_key = private_key.public_key()
        key_id = key_id or secrets.token_urlsafe(16)
        return cls(private_key=private_key, public_key=public_key, key_id=key_id)

    def export_private_key(self, password: Optional[bytes] = None) -> bytes:
        """Export private key as PEM."""
        encryption = BestAvailableEncryption(password) if password else NoEncryption()
        return self.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )

    def export_public_key(self) -> bytes:
        """Export public key as PEM."""
        return self.public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )

    @classmethod
    def load_private_key(cls, pem_data: bytes, password: Optional[bytes] = None, key_id: Optional[str] = None) -> "KeyPair":
        """Load private key from PEM and derive public key."""
        private_key = load_pem_private_key(pem_data, password=password)
        public_key = private_key.public_key()
        key_id = key_id or secrets.token_urlsafe(16)
        return cls(private_key=private_key, public_key=public_key, key_id=key_id)

    @classmethod
    def load_public_key(cls, pem_data: bytes, key_id: Optional[str] = None) -> "KeyPair":
        """Load public key from PEM (private key will be None)."""
        public_key = load_pem_public_key(pem_data)
        key_id = key_id or secrets.token_urlsafe(16)
        # Create a dummy private key placeholder - only public operations will work
        return cls(private_key=None, public_key=public_key, key_id=key_id)


class KeyManager:
    """Manages encryption keys with secure storage and rotation."""

    def __init__(self, key_dir: Optional[Path] = None, master_key: Optional[bytes] = None):
        """
        Initialize key manager.

        Args:
            key_dir: Directory for storing encrypted keys
            master_key: Master key for encrypting stored keys (32 bytes)
        """
        self.key_dir = key_dir or Path(os.environ.get("ENCRYPTION_KEY_DIR", "./keys"))
        self.key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        if master_key:
            if len(master_key) != 32:
                raise ValueError("Master key must be 32 bytes")
            self._master_key = master_key
        else:
            self._master_key = self._load_or_create_master_key()

        self._key_cache: dict[str, bytes] = {}
        self._key_pairs: dict[str, KeyPair] = {}

    def _load_or_create_master_key(self) -> bytes:
        """Load or create master key from environment/file."""
        # Try environment first
        env_key = os.environ.get("MASTER_ENCRYPTION_KEY")
        if env_key:
            return base64.b64decode(env_key)

        # Try key file
        key_file = self.key_dir / ".master.key"
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()

        # Generate new master key
        master_key = secrets.token_bytes(32)
        with open(key_file, "wb") as f:
            f.write(master_key)
        key_file.chmod(0o600)
        logger.warning("Generated new master encryption key. Store securely!")
        return master_key

    def _encrypt_key(self, key: bytes) -> bytes:
        """Encrypt a key with master key using Fernet."""
        f = Fernet(base64.urlsafe_b64encode(self._master_key))
        return f.encrypt(key)

    def _decrypt_key(self, encrypted_key: bytes) -> bytes:
        """Decrypt a key with master key using Fernet."""
        f = Fernet(base64.urlsafe_b64encode(self._master_key))
        return f.decrypt(encrypted_key)

    def generate_symmetric_key(
        self,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        key_id: Optional[str] = None,
    ) -> Tuple[str, bytes]:
        """
        Generate a new symmetric encryption key.

        Returns:
            Tuple of (key_id, raw_key)
        """
        key_id = key_id or secrets.token_urlsafe(16)

        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            key = secrets.token_bytes(32)  # 256 bits
        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            key = secrets.token_bytes(32)  # 256 bits
        elif algorithm == EncryptionAlgorithm.FERNET:
            key = Fernet.generate_key()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        encrypted_key = self._encrypt_key(key)
        key_file = self.key_dir / f"{key_id}.key"
        with open(key_file, "wb") as f:
            f.write(encrypted_key)
        key_file.chmod(0o600)

        self._key_cache[key_id] = key
        logger.info(f"Generated new symmetric key: {key_id} ({algorithm.value})")
        return key_id, key

    def get_symmetric_key(self, key_id: str) -> bytes:
        """Retrieve a symmetric key by ID."""
        if key_id in self._key_cache:
            return self._key_cache[key_id]

        key_file = self.key_dir / f"{key_id}.key"
        if not key_file.exists():
            raise KeyError(f"Key not found: {key_id}")

        encrypted_key = key_file.read_bytes()
        key = self._decrypt_key(encrypted_key)
        self._key_cache[key_id] = key
        return key

    def generate_key_pair(
        self,
        key_size: int = 4096,
        key_id: Optional[str] = None,
        password: Optional[bytes] = None,
    ) -> KeyPair:
        """Generate and store an asymmetric key pair."""
        key_pair = KeyPair.generate(key_size=key_size, key_id=key_id)

        # Store private key encrypted
        private_pem = key_pair.export_private_key(password=password)
        encrypted_private = self._encrypt_key(private_pem)
        private_file = self.key_dir / f"{key_pair.key_id}.private.pem"
        with open(private_file, "wb") as f:
            f.write(encrypted_private)
        private_file.chmod(0o600)

        # Store public key
        public_pem = key_pair.export_public_key()
        public_file = self.key_dir / f"{key_pair.key_id}.public.pem"
        with open(public_file, "wb") as f:
            f.write(public_pem)
        public_file.chmod(0o644)

        self._key_pairs[key_pair.key_id] = key_pair
        logger.info(f"Generated new key pair: {key_pair.key_id}")
        return key_pair

    def get_key_pair(self, key_id: str, password: Optional[bytes] = None) -> KeyPair:
        """Retrieve a key pair by ID."""
        if key_id in self._key_pairs:
            return self._key_pairs[key_id]

        private_file = self.key_dir / f"{key_id}.private.pem"
        if not private_file.exists():
            raise KeyError(f"Key pair not found: {key_id}")

        encrypted_private = private_file.read_bytes()
        private_pem = self._decrypt_key(encrypted_private)
        key_pair = KeyPair.load_private_key(private_pem, password=password, key_id=key_id)
        self._key_pairs[key_id] = key_pair
        return key_pair

    def get_public_key(self, key_id: str) -> rsa.RSAPublicKey:
        """Retrieve a public key by ID."""
        key_pair = self.get_key_pair(key_id)
        return key_pair.public_key

    def rotate_key(self, key_id: str) -> Tuple[str, bytes]:
        """Rotate a symmetric key (generate new, mark old as deprecated)."""
        # Get old key metadata
        old_key = self.get_symmetric_key(key_id)

        # Generate new key with same ID pattern
        new_key_id = f"{key_id}_v{secrets.token_urlsafe(4)}"
        return self.generate_symmetric_key(key_id=new_key_id)

    def delete_key(self, key_id: str) -> bool:
        """Securely delete a key."""
        key_file = self.key_dir / f"{key_id}.key"
        if key_file.exists():
            # Overwrite before deletion
            key_file.write_bytes(secrets.token_bytes(key_file.stat().st_size))
            key_file.unlink()

        self._key_cache.pop(key_id, None)
        logger.info(f"Deleted key: {key_id}")
        return True


class SymmetricEncryption:
    """Symmetric encryption for data at rest."""

    def __init__(self, key_manager: KeyManager, default_key_id: Optional[str] = None):
        self.key_manager = key_manager
        self.default_key_id = default_key_id

    def encrypt(
        self,
        plaintext: Union[str, bytes],
        key_id: Optional[str] = None,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        associated_data: Optional[bytes] = None,
    ) -> EncryptedData:
        """
        Encrypt plaintext using symmetric encryption.

        Args:
            plaintext: Data to encrypt
            key_id: Key identifier (uses default if not provided)
            algorithm: Encryption algorithm
            associated_data: Additional authenticated data (AAD)

        Returns:
            EncryptedData container
        """
        key_id = key_id or self.default_key_id
        if not key_id:
            raise ValueError("No key_id provided and no default key set")

        key = self.key_manager.get_symmetric_key(key_id)

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        if associated_data and isinstance(associated_data, str):
            associated_data = associated_data.encode("utf-8")

        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM/ChaCha20

        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            cipher = AESGCM(key)
            ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
            # AESGCM returns ciphertext + tag combined
            tag = ciphertext[-16:]
            ciphertext = ciphertext[:-16]

        elif algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            cipher = ChaCha20Poly1305(key)
            ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
            tag = ciphertext[-16:]
            ciphertext = ciphertext[:-16]

        elif algorithm == EncryptionAlgorithm.FERNET:
            f = Fernet(key)
            token = f.encrypt(plaintext)
            # Fernet handles nonce/tag internally
            return EncryptedData(
                ciphertext=token,
                nonce=b"",
                algorithm=algorithm,
                associated_data=associated_data,
                key_id=key_id,
            )

        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        return EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            algorithm=algorithm,
            associated_data=associated_data,
            key_id=key_id,
        )

    def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """
        Decrypt encrypted data.

        Args:
            encrypted_data: EncryptedData container

        Returns:
            Decrypted plaintext bytes
        """
        key = self.key_manager.get_symmetric_key(encrypted_data.key_id)

        if encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
            cipher = AESGCM(key)
            # Reconstruct ciphertext + tag for AESGCM
            full_ciphertext = encrypted_data.ciphertext + (encrypted_data.tag or b"")
            try:
                plaintext = cipher.decrypt(
                    encrypted_data.nonce,
                    full_ciphertext,
                    encrypted_data.associated_data,
                )
            except InvalidTag:
                raise ValueError("Decryption failed: invalid tag (data tampered or wrong key)")

        elif encrypted_data.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            cipher = ChaCha20Poly1305(key)
            full_ciphertext = encrypted_data.ciphertext + (encrypted_data.tag or b"")
            try:
                plaintext = cipher.decrypt(
                    encrypted_data.nonce,
                    full_ciphertext,
                    encrypted_data.associated_data,
                )
            except InvalidTag:
                raise ValueError("Decryption failed: invalid tag (data tampered or wrong key)")

        elif encrypted_data.algorithm == EncryptionAlgorithm.FERNET:
            f = Fernet(key)
            try:
                plaintext = f.decrypt(encrypted_data.ciphertext)
            except InvalidSignature:
                raise ValueError("Decryption failed: invalid signature (data tampered or wrong key)")

        else:
            raise ValueError(f"Unsupported algorithm: {encrypted_data.algorithm}")

        return plaintext

    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path,
        key_id: Optional[str] = None,
        algorithm: Encryption