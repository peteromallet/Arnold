"""Effect ledger pre-recording contract."""

from __future__ import annotations

from dataclasses import dataclass, field

from arnold.kernel.effect import EffectDescriptor


@dataclass
class EffectLedger:
    """In-memory contract model for idempotency de-duplication tests."""

    _records: dict[str, EffectDescriptor] = field(default_factory=dict)

    def prerecord(self, effect: EffectDescriptor) -> bool:
        """Record an effect intent before execution.

        Returns ``True`` for a new key and ``False`` when a duplicate key was
        already recorded.
        """

        if effect.idempotency_key in self._records:
            return False
        self._records[effect.idempotency_key] = effect
        return True

    def get(self, idempotency_key: str) -> EffectDescriptor | None:
        return self._records.get(idempotency_key)
