"""Signal storage for the mini PLC simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable


DEFAULT_INPUTS = ("START", "STOP", "ESTOP", "SENSOR1", "SENSOR2", "BOX_TYPE")
INPUT_SET = set(DEFAULT_INPUTS)
DEFAULT_OUTPUTS = (
    "MOTOR",
    "GATE",
    "CLAMP",
    "DIVERTER",
    "READY",
    "ALARM",
    "TIMER1_DONE",
    "TIMER2_DONE",
)


@dataclass
class SignalStore:
    """Central dictionary for PLC inputs, outputs, and internal bits."""

    inputs: Iterable[str] = DEFAULT_INPUTS
    outputs: Iterable[str] = DEFAULT_OUTPUTS
    values: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (*self.inputs, *self.outputs):
            self.values.setdefault(name, False)

    def get(self, name: str) -> bool:
        return bool(self.values.get(self.normalize(name), False))

    def set(self, name: str, value: Any) -> None:
        self.values[self.normalize(name)] = value

    def update_many(self, values: Dict[str, Any]) -> None:
        for name, value in values.items():
            self.set(name, value)

    def reset_outputs(self) -> None:
        for name in self.outputs:
            self.set(name, False)

    def reset_runtime(self) -> None:
        """Clear outputs and internal bits while preserving operator inputs."""
        for name in list(self.values):
            if name not in INPUT_SET:
                self.values[name] = False

    def snapshot(self) -> Dict[str, Any]:
        return dict(self.values)

    @staticmethod
    def normalize(name: str) -> str:
        return name.strip().upper().replace(".", "_")
