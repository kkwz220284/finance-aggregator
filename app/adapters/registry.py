from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import BankAdapter

_REGISTRY: dict[str, type["BankAdapter"]] = {}


def register(cls: type["BankAdapter"]) -> type["BankAdapter"]:
    _REGISTRY[cls.provider_id] = cls
    for alias in getattr(cls, "provider_aliases", ()):
        _REGISTRY[alias] = cls
    return cls


def get_adapter(provider_id: str) -> "BankAdapter":
    # Ensure all normalizers are registered
    import app.adapters.normalizers  # noqa: F401

    cls = _REGISTRY.get(provider_id)
    if cls is None:
        raise ValueError(f"No adapter registered for provider: {provider_id!r}")
    return cls()


def list_providers() -> list[str]:
    import app.adapters.normalizers  # noqa: F401

    return list(_REGISTRY.keys())
