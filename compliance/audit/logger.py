import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
from contextvars import ContextVar

import aiofiles
import aiofiles.os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

try:
    import orjson
    _JSON_DUMPS = orjson.dumps
    _JSON_LOADS = orjson.loads
except ImportError:
    import json as _json
    _JSON_DUMPS = lambda obj: _json.dumps(obj, separators=(',', ':')).encode()
    _JSON_LOADS = _json.loads


class AuditEventType(Enum):
    """Standardized audit event types for financial operations."""
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_UPDATED = "account.updated"
    ACCOUNT_CLOSED = "account.closed"
    TRANSACTION_INITIATED = "transaction.initiated"
    TRANSACTION_AUTHORIZED = "transaction.authorized"
    TRANSACTION_CAPTURED = "transaction.captured"
    TRANSACTION_VOIDED = "transaction.voided"
    TRANSACTION_REFUNDED = "transaction.refunded"
    TRANSACTION_FAILED = "transaction.failed"
    TRANSFER_INITIATED = "transfer.initiated"
    TRANSFER_COMPLETED = "transfer.completed"
    TRANSFER_FAILED = "transfer.failed"
    BALANCE_ADJUSTMENT = "balance.adjustment"
    BALANCE_INQUIRY = "balance.inquiry"
    KYC_VERIFICATION = "kyc.verification"
    KYC_REJECTED = "kyc.rejected"
    SANCTIONS_CHECK = "sanctions.check"
    SANCTIONS_HIT = "sanctions.hit"
    FRAUD_ALERT = "fraud.alert"
    FRAUD_BLOCKED = "fraud.blocked"
    COMPLIANCE_REVIEW = "compliance.review"
    DATA_ACCESS = "data.access"
    DATA_EXPORT = "data.export"
    CONFIGURATION_CHANGE = "configuration.change"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    ERROR_OCCURRED = "error.occurred"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    DEBUG = 10
    INFO = 20
    NOTICE = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    ALERT = 60
    EMERGENCY = 70


class IntegrityAlgorithm(Enum):
    """Supported integrity algorithms."""
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    ED25519 = "ed25519"
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Immutable context for audit events."""
    correlation_id: str
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    service_name: str = "unknown"
    service_version: str = "unknown"
    environment: str = "production"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_updates(self, **kwargs) -> 'AuditContext':
        """Create new context with updated fields."""
        return AuditContext(**{**asdict(self), **kwargs})


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable audit log entry."""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    context: AuditContext
    payload: Dict[str, Any]
    previous_hash: str
    entry_hash: str
    signature: Optional[str] = None
    encryption_info: Optional[Dict[str, str]] = None
    sequence_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        data['context'] = asdict(self.context)
        return data

    def to_json(self) -> bytes:
        """Serialize to JSON bytes."""
        return _JSON_DUMPS(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """Deserialize from dictionary."""
        data = data.copy()
        data['event_type'] = AuditEventType(data['event_type'])
        data['severity'] = AuditSeverity(data['severity'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['context'] = AuditContext(**data['context'])
        return cls(**data)

    @classmethod
    def from_json(cls, json_bytes: bytes) -> 'AuditEntry':
        """Deserialize from JSON bytes."""
        return cls.from_dict(_JSON_LOADS(json_bytes))


class AuditSink(ABC):
    """Abstract base class for audit log sinks."""

    @abstractmethod
    async def write(self, entry: AuditEntry) -> None:
        """Write a single audit entry."""
        pass

    @abstractmethod
    async def write_batch(self, entries: List[AuditEntry]) -> None:
        """Write multiple audit entries atomically."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush any buffered entries."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the sink and release resources."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if sink is healthy."""
        pass


class FileAuditSink(AuditSink):
    """File-based audit sink with rotation and integrity."""

    def __init__(
        self,
        path: Union[str, Path],
        max_size_mb: int = 100,
        max_files: int = 10,
        compress: bool = True,
        integrity_algorithm: IntegrityAlgorithm = IntegrityAlgorithm.SHA256,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        encryption_key: Optional[bytes] = None,
    ):
        self.path = Path(path)
        self.max_size = max_size_mb * 1024 * 1024
        self.max_files = max_files
        self.compress = compress
        self.integrity_algorithm = integrity_algorithm
        self.signing_key = signing_key
        self.encryption_key = encryption_key
        
        self._file: Optional[aiofiles.threadpool.AsyncFileIO] = None
        self._current_size = 0
        self._sequence = 0
        self._previous_hash = "0" * 64
        self._lock = asyncio.Lock()
        self._buffer: List[AuditEntry] = []
        self._buffer_size = 0
        self._max_buffer_size = 1000
        self._closed = False
        
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, data: bytes) -> str:
        """Compute hash of data using configured algorithm."""
        if self.integrity_algorithm == IntegrityAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif self.integrity_algorithm == IntegrityAlgorithm.SHA384:
            return hashlib.sha384(data).hexdigest()
        elif self.integrity_algorithm == IntegrityAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif self.integrity_algorithm == IntegrityAlgorithm.HMAC_SHA256:
            key = self.encryption_key or b'default-key'
            return hmac.new(key, data, hashlib.sha256).hexdigest()
        elif self.integrity_algorithm == IntegrityAlgorithm.HMAC_SHA512:
            key = self.encryption_key or b'default-key'
            return hmac.new(key, data, hashlib.sha512).hexdigest()
        return hashlib.sha256(data).hexdigest()

    def _sign_entry(self, entry_hash: str) -> Optional[str]:
        """Sign entry hash with private key."""
        if not self.signing_key:
            return None
        signature = self.signing_key.sign(entry_hash.encode())
        return signature.hex()

    def _encrypt_payload(self, payload: Dict[str, Any]) -> tuple[bytes, Dict[str, str]]:
        """Encrypt sensitive payload data."""
        if not self.encryption_key:
            return _JSON_DUMPS(payload), {}
        
        aesgcm = AESGCM(self.encryption_key[:32])
        nonce = secrets.token_bytes(12)
        plaintext = _JSON_DUMPS(payload)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        return ciphertext, {
            'algorithm': 'AES-GCM',
            'nonce': nonce.hex(),
            'key_id': hashlib.sha256(self.encryption_key).hexdigest()[:16]
        }

    def _create_entry(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        context: AuditContext,
        payload: Dict[str, Any],
    ) -> AuditEntry:
        """Create a new audit entry with integrity."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        self._sequence += 1
        
        payload_bytes, encryption_info = self._encrypt_payload(payload)
        
        entry_data = {
            'event_id': event_id,
            'event_type': event_type.value,
            'severity': severity.value,
            'timestamp': timestamp.isoformat(),
            'context': asdict(context),
            'payload_hash': hashlib.sha256(payload_bytes).hexdigest(),
            'previous_hash': self._previous_hash,
            'sequence_number': self._sequence,
        }
        
        entry_bytes = _JSON_DUMPS(entry_data, option=orjson.OPT_SORT_KEYS)
        entry_hash = self._compute_hash(entry_bytes)
        signature = self._sign_entry(entry_hash)
        
        entry = AuditEntry(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=timestamp,
            context=context,
            payload=payload,
            previous_hash=self._previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            encryption_info=encryption_info if encryption_info else None,
            sequence_number=self._sequence,
        )
        
        self._previous_hash = entry_hash
        return entry

    async def _ensure_file(self) -> None:
        """Ensure file handle is open, rotate if needed."""
        if self._file is None or self._closed:
            self._file = await aiofiles.open(self.path, 'ab')
            stat = await aiofiles.os.stat(self.path)
            self._current_size = stat.st_size

    async def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if self._current_size >= self.max_size:
            await self._file.close()
            
            for i in range(self.max_files - 1, 0, -1):
                old_path = self.path.with_suffix(f'.{i}.log')
                new_path = self.path.with_suffix(f'.{i+1}.log')
                if await aiofiles.os.path.exists(old_path):
                    if i == self.max_files - 1:
                        await aiofiles.os.remove(old_path)
                    else:
                        await aiofiles.os.rename(old_path, new_path)
            
            await aiofiles.os.rename(self.path, self.path.with_suffix('.1.log'))
            self._file = await aiofiles.open(self.path, 'wb')
            self._current_size = 0

    async def write(self, entry: AuditEntry) -> None:
        """Write a single audit entry."""
        async with self._lock:
            await self._ensure_file()
            await self._rotate_if_needed()
            
            line = entry.to_json() + b'\n'
            await self._file.write(line)
            await self._file.flush()
            self._current_size += len(line)

    async def write_batch(self, entries: List[AuditEntry]) -> None:
        """Write multiple audit entries."""
        async with self._lock:
            await self._ensure_file()
            await self._rotate_if_needed()
            
            lines = b''.join(entry.to_json() + b'\n' for entry in entries)
            await self._file.write(lines)
            await self._file.flush()
            self._current_size += len(lines)

    async def flush(self) -> None:
        """Flush buffered entries."""
        async with self._lock:
            if self._file and not self._closed:
                await self._file.flush()

    async def close(self) -> None:
        """Close the sink."""
        async with self._lock:
            if self._file and not self._closed:
                await self._file.flush()
                await self._file.close()
                self._file = None
                self._closed = True

    async def health_check(self) -> bool:
        """Check if sink is healthy."""
        try:
            await aiofiles.os.access(self.path.parent, os.W_OK)
            return not self._closed
        except Exception:
            return False


class DatabaseAuditSink(AuditSink):
    """Database-backed audit sink for querying and retention."""

    def __init__(
        self,
        dsn: str,
        table_name: str = 'audit_log',
        pool_size: int = 10,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ):
        self.dsn = dsn
        self.table_name = table_name
        self.pool_size = pool_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._pool = None
        self._buffer: List[AuditEntry] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    async def _initialize(self) -> None:
        """Initialize database connection and schema."""
        import asyncpg
        
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=1,
            max_size=self.pool_size,
        )
        
        async with self._pool.acquire() as conn:
            await conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    event_id UUID PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    severity INTEGER NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    correlation_id UUID NOT NULL,
                    causation_id UUID,
                    user_id VARCHAR(255),
                    session_id VARCHAR(255),
                    ip_address INET,
                    user_agent TEXT,
                    request_id VARCHAR(255),
                    trace_id VARCHAR(255),
                    span_id VARCHAR(255),
                    service_name VARCHAR(100) NOT NULL,
                    service_version VARCHAR(50),
                    environment VARCHAR(50) NOT NULL,
                    payload JSONB NOT NULL,
                    previous_hash CHAR(64) NOT NULL,
                    entry_hash CHAR(64) NOT NULL,
                    signature TEXT,
                    encryption_info JSONB,
                    sequence_number BIGINT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp 
                    ON {self.table_name} (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_correlation 
                    ON {self.table_name} (correlation_id);
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_user 
                    ON {self.table_name} (user_id);
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_event_type 
                    ON {self.table_name} (event_type);
            ''')
        
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        """Periodically flush buffer."""
        while not self._closed:
            await asyncio.sleep(self.flush_interval)
            if self._buffer:
                await self