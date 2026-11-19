"""Short-lived, in-memory store for completed analyses.

Images are kept in memory only for as long as a report needs them. Nothing is
written to disk, and every record expires automatically.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_report_id() -> str:
    raw = "".join(secrets.choice(ID_ALPHABET) for _ in range(8))
    return f"CNC-{raw[:4]}-{raw[4:]}"


@dataclass
class AnalysisRecord:
    report_id: str
    created_at: float
    filename: str
    width: int
    height: int
    inference_ms: int
    result: dict[str, Any]
    image_jpeg: bytes


class AnalysisStore:
    """Thread-safe TTL cache with a hard entry limit."""

    def __init__(self, ttl_seconds: int = 1800, max_entries: int = 48) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._records: dict[str, AnalysisRecord] = {}
        self._lock = threading.Lock()

    def put(self, record: AnalysisRecord) -> None:
        with self._lock:
            self._purge_locked()
            self._records[record.report_id] = record
            while len(self._records) > self.max_entries:
                oldest = min(
                    self._records.values(), key=lambda item: item.created_at
                )
                self._records.pop(oldest.report_id, None)

    def get(self, report_id: str) -> AnalysisRecord | None:
        with self._lock:
            self._purge_locked()
            return self._records.get(report_id)

    def purge(self) -> None:
        with self._lock:
            self._purge_locked()

    def _purge_locked(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        expired = [
            key
            for key, record in self._records.items()
            if record.created_at < cutoff
        ]
        for key in expired:
            self._records.pop(key, None)
