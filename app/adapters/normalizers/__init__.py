# Import all normalizers so they self-register via @register
from app.adapters.normalizers.amex import AmexAdapter
from app.adapters.normalizers.chase import ChaseAdapter
from app.adapters.normalizers.monzo import MonzoAdapter
from app.adapters.normalizers.natwest import NatWestAdapter

__all__ = ["AmexAdapter", "ChaseAdapter", "MonzoAdapter", "NatWestAdapter"]
