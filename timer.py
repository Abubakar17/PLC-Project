"""PLC-style timer implementations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TonTimer:
    """TON on-delay timer.

    EN is true while the input condition is true.
    ACC accumulates while EN is true.
    DONE becomes true once ACC reaches the preset delay.
    """

    name: str
    delay_seconds: float
    en: bool = False
    done: bool = False
    acc: float = 0.0

    def update(self, enabled: bool, dt: float) -> None:
        self.en = bool(enabled)
        if self.en:
            self.acc = min(self.acc + max(dt, 0.0), max(self.delay_seconds, 0.0))
            self.done = self.acc >= self.delay_seconds
        else:
            self.acc = 0.0
            self.done = False

    def reset(self) -> None:
        self.en = False
        self.done = False
        self.acc = 0.0

    def export_signals(self) -> dict[str, bool | float]:
        prefix = self.name.upper()
        return {
            f"{prefix}_EN": self.en,
            f"{prefix}_DONE": self.done,
            f"{prefix}_ACC": self.acc,
        }
