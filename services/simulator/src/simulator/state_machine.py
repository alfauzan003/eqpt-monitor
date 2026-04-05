"""Equipment state machine: idle -> running -> fault -> maintenance -> idle."""
from __future__ import annotations

import random
from enum import Enum


class EquipmentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAULT = "fault"
    MAINTENANCE = "maintenance"


# Allowed transitions.
_ALLOWED: dict[EquipmentState, set[EquipmentState]] = {
    EquipmentState.IDLE: {EquipmentState.RUNNING},
    EquipmentState.RUNNING: {EquipmentState.FAULT, EquipmentState.IDLE},
    EquipmentState.FAULT: {EquipmentState.MAINTENANCE},
    EquipmentState.MAINTENANCE: {EquipmentState.IDLE},
}

# Per-tick transition probabilities (approximate). Tuned for ~1s ticks.
_TICK_PROBABILITIES: dict[EquipmentState, list[tuple[EquipmentState, float]]] = {
    EquipmentState.IDLE: [(EquipmentState.RUNNING, 0.20)],
    EquipmentState.RUNNING: [
        (EquipmentState.FAULT, 0.002),   # rare
        (EquipmentState.IDLE, 0.005),    # occasional planned stop
    ],
    EquipmentState.FAULT: [(EquipmentState.MAINTENANCE, 0.10)],
    EquipmentState.MAINTENANCE: [(EquipmentState.IDLE, 0.05)],
}

_FAULT_CODES = ["F-001", "F-002", "F-003", "F-TEMP-HIGH", "F-COMM-LOST"]


class StateMachine:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self.state: EquipmentState = EquipmentState.IDLE
        self.fault_code: str | None = None
        self.total_transitions: int = 0

    def transition_to(self, new_state: EquipmentState) -> None:
        if new_state not in _ALLOWED[self.state]:
            raise ValueError(
                f"invalid transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state
        self.total_transitions += 1
        if new_state == EquipmentState.FAULT:
            self.fault_code = self._rng.choice(_FAULT_CODES)
        elif new_state == EquipmentState.IDLE:
            self.fault_code = None

    def tick(self) -> None:
        """Advance time by one tick, possibly transitioning stochastically."""
        for target, prob in _TICK_PROBABILITIES.get(self.state, []):
            if self._rng.random() < prob:
                self.transition_to(target)
                return
