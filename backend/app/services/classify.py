"""Service classification mapping loaded from service_classes.json."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings

_CACHE: Optional[Dict[str, str]] = None
_PROVISIONED_SERVICES: Optional[set] = None


def _load_classes() -> None:
    global _CACHE, _PROVISIONED_SERVICES
    if _CACHE is not None:
        return

    json_path = settings.REFERENCE_DIR / "service_classes.json"
    if not json_path.is_file():
        raise FileNotFoundError(f"service_classes.json not found at {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    classes_dict = {}
    provisioned = set()
    for class_name, info in data.get("classes", {}).items():
        for svc in info.get("services", []):
            classes_dict[svc] = class_name
            if class_name == "provisioned":
                provisioned.add(svc)

    _CACHE = classes_dict
    _PROVISIONED_SERVICES = provisioned


def get_service_class(service_name: str) -> str:
    """Return the service class for a given service name, or 'other_managed' as fallback."""
    _load_classes()
    assert _CACHE is not None
    return _CACHE.get(service_name, "other_managed")


def is_provisioned(service_name: str) -> bool:
    """Check if a service is classified as provisioned (Compute, GKE, Cloud SQL, Memorystore, Dataproc)."""
    _load_classes()
    assert _PROVISIONED_SERVICES is not None
    return service_name in _PROVISIONED_SERVICES


def get_all_classes() -> Dict[str, str]:
    """Return a mapping of all registered service names to their classes."""
    _load_classes()
    assert _CACHE is not None
    return dict(_CACHE)

