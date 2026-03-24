"""One-time migration from legacy Keychain entries to io.creds.store canonical names."""
import subprocess
from dataclasses import dataclass
from typing import Optional

from creds.registry import Service, LegacyKey
from creds.store import Store


@dataclass
class LegacyResult:
    service: Service
    field_id: str
    value: str
    legacy_key: LegacyKey


def _read_legacy(service_name: str, account: str) -> Optional[str]:
    """Try reading from a legacy Keychain entry. Returns stripped value or None."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service_name, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def scan_legacy(service: Service) -> Optional[LegacyResult]:
    """Scan all legacy key locations for a service. Returns first match found."""
    if not service.legacy_keys:
        return None
    for legacy_key in service.legacy_keys:
        value = _read_legacy(legacy_key.service, legacy_key.account)
        if value:
            field_id = service.fields[0].id if service.fields else "value"
            return LegacyResult(
                service=service,
                field_id=field_id,
                value=value,
                legacy_key=legacy_key,
            )
    return None


def build_migration_plan(
    services: list[Service],
) -> tuple[list[LegacyResult], list[Service]]:
    """Scan all services with legacy_keys. Returns (found, not_found)."""
    found: list[LegacyResult] = []
    not_found: list[Service] = []
    for svc in services:
        if not svc.legacy_keys:
            continue
        result = scan_legacy(svc)
        if result:
            found.append(result)
        else:
            not_found.append(svc)
    return found, not_found


def migrate_entry(result: LegacyResult, store: Store, context: str = "personal") -> None:
    """Write a legacy credential to the canonical Keychain location via Store."""
    store.set(result.service.id, "", result.field_id, result.value, context=context)
