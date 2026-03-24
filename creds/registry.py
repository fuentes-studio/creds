"""Service registry — loads service definitions from YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

DEFAULT_REGISTRY = Path(__file__).parent / "services.yaml"


@dataclass
class Field:
    id: str
    label: str
    env_var: str
    required: bool = True
    secret: bool = True


@dataclass
class LegacyKey:
    service: str
    account: str


@dataclass
class Service:
    id: str
    label: str
    category: str
    fields: list[Field]
    required: bool = False
    multi_instance: bool = False
    context: str = "personal"
    hint: str = ""
    legacy_keys: list[LegacyKey] = field(default_factory=list)


class Registry:
    def __init__(self, registry_path: Path = DEFAULT_REGISTRY) -> None:
        self._services: dict[str, Service] = {}
        self._load(registry_path)

    def _load(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)
        for svc_data in data.get("services", []):
            fields = [
                Field(
                    id=fld["id"],
                    label=fld["label"],
                    env_var=fld.get("env_var", ""),
                    required=fld.get("required", True),
                    secret=fld.get("secret", True),
                )
                for fld in svc_data.get("fields", [])
            ]
            legacy_keys = [
                LegacyKey(service=lk["service"], account=lk["account"])
                for lk in svc_data.get("legacy_keys", [])
            ]
            svc = Service(
                id=svc_data["id"],
                label=svc_data["label"],
                category=svc_data.get("category", "General"),
                fields=fields,
                required=svc_data.get("required", False),
                multi_instance=svc_data.get("multi_instance", False),
                context=svc_data.get("context", "personal"),
                hint=svc_data.get("hint", ""),
                legacy_keys=legacy_keys,
            )
            self._services[svc.id] = svc

    def all(self) -> list[Service]:
        return list(self._services.values())

    def get(self, service_id: str) -> Optional[Service]:
        return self._services.get(service_id)

    def by_category(self) -> dict[str, list[Service]]:
        result: dict[str, list[Service]] = {}
        for svc in self._services.values():
            result.setdefault(svc.category, []).append(svc)
        return result
