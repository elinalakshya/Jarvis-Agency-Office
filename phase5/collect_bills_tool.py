#!/usr/bin/env python3
"""
Billing Data Collection Tool for Avenger Runs.

This tool aggregates billing data from completed avenger runs across multiple
data sources (database, file system, API) and outputs consolidated reports.
"""

import argparse
import csv
import json
import logging
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class BillingRecord:
    """Represents a single billing record from an avenger run."""

    run_id: str
    avenger_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    cpu_hours: float
    memory_gb_hours: float
    storage_gb_hours: float
    network_gb: float
    cost_usd: float
    status: str
    tags: dict[str, str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BillingRecord":
        """Create instance from dictionary."""
        return cls(**data)


class BillingDataSource:
    """Abstract base class for billing data sources."""

    def fetch_completed_runs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        avenger_ids: list[str] | None = None,
    ) -> list[BillingRecord]:
        """Fetch completed billing records."""
        raise NotImplementedError


class FileSystemDataSource(BillingDataSource):
    """Read billing data from JSON files on the filesystem."""

    def __init__(self, base_path: str | Path, pattern: str = "*.billing.json"):
        self.base_path = Path(base_path)
        self.pattern = pattern

    def fetch_completed_runs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        avenger_ids: list[str] | None = None,
    ) -> list[BillingRecord]:
        records = []
        for file_path in self.base_path.rglob(self.pattern):
            try:
                with open(file_path) as f:
                    data = json.load(f)

                # Handle both single record and array of records
                if isinstance(data, list):
                    items = data
                else:
                    items = [data]

                for item in items:
                    record = BillingRecord.from_dict(item)
                    if self._matches_filters(record, since, until, avenger_ids):
                        records.append(record)

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to parse {file_path}: {e}")

        return records

    def _matches_filters(
        self,
        record: BillingRecord,
        since: datetime | None,
        until: datetime | None,
        avenger_ids: list[str] | None,
    ) -> bool:
        if record.status != "completed":
            return False

        if since:
            run_start = datetime.fromisoformat(record.start_time.replace("Z", "+00:00"))
            if run_start < since:
                return False

        if until:
            run_start = datetime.fromisoformat(record.start_time.replace("Z", "+00:00"))
            if run_start > until:
                return False

        if avenger_ids and record.avenger_id not in avenger_ids:
            return False

        return True


class DatabaseDataSource(BillingDataSource):
    """Read billing data from SQLite database."""

    def __init__(self, db_path: str | Path, table: str = "billing_records"):
        self.db_path = Path(db_path)
        self.table = table

    def fetch_completed_runs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        avenger_ids: list[str] | None = None,
    ) -> list[BillingRecord]:
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return []

        query = f"SELECT * FROM {self.table} WHERE status = 'completed'"
        params: list[Any] = []

        if since:
            query += " AND start_time >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND start_time <= ?"
            params.append(until.isoformat())

        if avenger_ids:
            placeholders = ",".join(["?"] * len(avenger_ids))
            query += f" AND avenger_id IN ({placeholders})"
            params.extend(avenger_ids)

        query += " ORDER BY start_time DESC"

        records = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                for row in cursor:
                    # Parse JSON fields
                    tags = json.loads(row["tags"]) if row["tags"] else {}
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}

                    record = BillingRecord(
                        run_id=row["run_id"],
                        avenger_id=row["avenger_id"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_seconds=row["duration_seconds"],
                        cpu_hours=row["cpu_hours"],
                        memory_gb_hours=row["memory_gb_hours"],
                        storage_gb_hours=row["storage_gb_hours"],
                        network_gb=row["network_gb"],
                        cost_usd=row["cost_usd"],
                        status=row["status"],
                        tags=tags,
                        metadata=metadata,
                    )
                    records.append(record)

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")

        return records


class APIDataSource(BillingDataSource):
    """Fetch billing data from a REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def fetch_completed_runs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        avenger_ids: list[str] | None = None,
    ) -> list[BillingRecord]:
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed. Install with: pip install requests")
            return []

        params: dict[str, Any] = {"status": "completed", "limit": 1000}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if avenger_ids:
            params["avenger_ids"] = ",".join(avenger_ids)

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        records = []
        url = f"{self.base_url}/api/v1/billing/records"

        try:
            while url:
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                for item in data.get("records", []):
                    records.append(BillingRecord.from_dict(item))

                # Handle pagination
                url = data.get("next_page")
                params = {}  # Params only needed for first request

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")

        return records


class BillingAggregator:
    """Aggregates billing records into summary reports."""

    def __init__(self, records: list[BillingRecord]):
        self.records = records

    def get_summary(self) -> dict[str, Any]:
        """Generate overall billing summary."""
        if not self.records:
            return {
                "total_runs": 0,
                "total_cost_usd": 0.0,
                "total_cpu_hours": 0.0,
                "total_memory_gb_hours": 0.0,
                "total_storage_gb_hours": 0.0,
                "total_network_gb": 0.0,
                "total_duration_seconds": 0.0,
                "unique_avengers": 0,
                "date_range": {"earliest": None, "latest": None},
            }

        total_cost = sum(r.cost_usd for r in self.records)
        total_cpu = sum(r.cpu_hours for r in self.records)
        total_memory = sum(r.memory_gb_hours for r in self.records)
        total_storage = sum(r.storage_gb_hours for r in self.records)
        total_network = sum(r.network_gb for r in self.records)
        total_duration = sum(r.duration_seconds for r in self.records)

        start_times = [datetime.fromisoformat(r.start_time.replace("Z", "+00:00")) for r in self.records]

        return {
            "total_runs": len(self.records),
            "total_cost_usd": round(total_cost, 4),
            "total_cpu_hours": round(total_cpu, 4),
            "total_memory_gb_hours": round(total_memory, 4),
            "total_storage_gb_hours": round(total_storage, 4),
            "total_network_gb": round(total_network, 4),
            "total_duration_seconds": round(total_duration, 2),
            "unique_avengers": len({r.avenger_id for r in self.records}),
            "date_range": {
                "earliest": min(start_times).isoformat(),
                "latest": max(start_times).isoformat(),
            },
        }

    def get_by_avenger(self) -> dict[str, dict[str, Any]]:
        """Aggregate billing by avenger ID."""
        by_avenger: dict[str, list[BillingRecord]] = {}
        for record in self.records:
            by_avenger.setdefault(record.avenger_id, []).append(record)

        result = {}
        for avenger_id, records in by_avenger.items():
            result[avenger_id] = {
                "run_count": len(records),
                "total_cost_usd": round(sum(r.cost_usd for r in records), 4),
                "total_cpu_hours": round(sum(r.cpu_hours for r in records), 4),
                "total_memory_gb_hours": round(sum(r.memory_gb_hours for r in records), 4),
                "total_storage_gb_hours": round(sum(r.storage_gb_hours for r in records), 4),
                "total_network_gb": round(sum(r.network_gb for r in records), 4),
                "avg_duration_seconds": round(sum(r.duration_seconds for r in records) / len(records), 2),
            }
        return result

    def get_by_tag(self, tag_key: str) -> dict[str, dict[str, Any]]:
        """Aggregate billing by a specific tag."""
        by_tag: dict[str, list[BillingRecord]] = {}
        for record in self.records:
            tag_value = record.tags.get(tag_key, "untagged")
            by_tag.setdefault(tag_value, []).append(record)

        result = {}
        for tag_value, records in by_tag.items():
            result[tag_value] = {
                "run_count": len(records),
                "total_cost_usd": round(sum(r.cost_usd for r in records), 4),
                "total_cpu_hours": round(sum(r.cpu_hours for r in records), 4),
            }
        return result

    def get_daily_breakdown(self) -> dict[str, dict[str, Any]]:
        """Aggregate billing by day."""
        by_day: dict[str, list[BillingRecord]] = {}
        for record in self.records:
            dt = datetime.fromisoformat(record.start_time.replace("Z", "+00:00"))
            day_key = dt.date().isoformat()
            by_day.setdefault(day_key, []).append(record)

        result = {}
        for day, records in sorted(by_day.items()):
            result[day] = {
                "run_count": len(records),
                "total_cost_usd": round(sum(r.cost_usd for r in records), 4),
                "total_cpu_hours": round(sum(r.cpu_hours for r in records), 4),
                "unique_avengers": len({r.avenger_id for r in records}),
            }
        return result

    def get_top_cost_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the most expensive runs."""
        sorted_records = sorted(self.records, key=lambda r: r.cost_usd, reverse=True)
        return [
            {
                "run_id": r.run_id,
                "avenger_id": r.avenger_id,
                "cost_usd": r.cost_usd,
                "cpu_hours": r.cpu_hours,
                "duration_seconds": r.duration_seconds,
                "start_time": r.start_time,
            }
            for r in sorted_records[:limit]
        ]


class OutputFormatter:
    """Format aggregated billing data for output."""

    @staticmethod
    def to_json(data: dict[str, Any], pretty: bool = True) -> str:
        """Format as JSON."""
        indent = 2 if pretty else None
        return json.dumps(data, indent=indent, default=str)

    @staticmethod
    def to_csv(records: list[BillingRecord]) -> str:
        """Format records as CSV."""
        if not records:
            return ""

        fieldnames = [
            "run_id",
            "avenger_id",
            "start_time",
            "end_time",
            "duration_seconds",
            "cpu_hours",
            "memory_gb_hours",
            "storage_gb_hours",
            "network_gb",
            "cost_usd",
            "status",
        ]

        output = []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            row = {k: getattr(record, k) for k in fieldnames}
            writer.writerow(row)

        return "\n".join(output)

    @staticmethod
    def to_summary_table(summary: dict[str, Any]) -> str:
        """Format summary as human-readable table."""
        lines = [
            "═══════════════════════════════════════",
            "         BILLING SUMMARY REPORT        ",
            "═══════════════════════════════════════",
            f"  Total Runs:           {summary['total_runs']:>10}",
            f"  Unique Avengers:      {summary['unique_avengers']:>10}",
            f"  Date Range:           {summary['date_range']['earliest'] or 'N/A':>10} to {summary['date_range']['latest'] or 'N/A':<10}",
            "──────────────────────────────────────",
            f"  Total Cost (USD):     ${summary['total_cost_usd']:>10.4f}",
            f"  Total CPU Hours:      {summary['total_cpu_hours']:>10.4f}",
            f"  Total Memory (GB-hr): {summary['total_memory_gb_hours']:>10.4f}",
            f"  Total Storage (GB-hr):{summary['total_storage_gb_hours']:>10.4f}",
            f"  Total Network (GB):   {summary['total_network_gb']:>10.4f}",
            f"  Total Duration (sec): {summary['total_duration_seconds']:>10.2f}",
            "═══════════════════════════════════════",
        ]
        return "\n".join(lines)


def create_data_source(source_type: str, config: dict[str, Any]) -> BillingDataSource:
    """Factory function to create data source instances."""
    if source_type == "filesystem":
        return FileSystemDataSource(
            base_path=config.get("path", "./billing_data"),
            pattern=config.get("pattern", "*.billing.json"),
        )
    elif source_type == "database":
        return DatabaseDataSource(
            db_path=config.get("path", "./billing.db"),
            table=config.get("table", "billing_records"),
        )
    elif