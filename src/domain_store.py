import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List


class DomainStore:
    """Armazena objetos de domínio em um JSON local para reutilização."""

    def __init__(self, cache_path: str = "data/glpi_cache.json") -> None:
        self.cache_path = Path(cache_path)
        self.data: Dict[str, List[Dict[str, Any]]] = {
            "account": [],
            "users": [],
            "tickets": [],
            "articles": [],
            "categories": [],
            "timeline": [],
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    @staticmethod
    def _normalize(value: Any) -> Any:
        if is_dataclass(value):
            return DomainStore._normalize(asdict(value))
        if isinstance(value, dict):
            return {key: DomainStore._normalize(val) for key, val in value.items()}
        if isinstance(value, list):
            return [DomainStore._normalize(item) for item in value]
        if isinstance(value, tuple):
            return [DomainStore._normalize(item) for item in value]
        return value

    def load(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in self.data.items():
                    self.data[key] = raw.get(key, value)
        except (json.JSONDecodeError, OSError):
            self.data = {
                "account": [],
                "users": [],
                "tickets": [],
                "articles": [],
                "categories": [],
                "timeline": [],
            }

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._normalize(self.data)
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, domain: str, item: Dict[str, Any]) -> None:
        self.data.setdefault(domain, [])
        self.data[domain].append(self._normalize(item))
        self.save()

    def replace(self, domain: str, items: List[Dict[str, Any]]) -> None:
        self.data[domain] = [self._normalize(item) for item in items]
        self.save()
