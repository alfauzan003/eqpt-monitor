"""Equipment model: generates metric values based on type and state."""
from __future__ import annotations

import random
from dataclasses import dataclass

from simulator.state_machine import EquipmentState


@dataclass
class MetricValue:
    name: str
    value: float


# Baseline ranges per metric, per equipment type.
# Format: (mean_running, noise_stddev, idle_value, fault_value)
_METRIC_PROFILES: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "formation_cycler": {
        "temperature": (45.0, 1.5, 22.0, 85.0),
        "voltage": (3.7, 0.05, 0.0, 4.3),
        "throughput": (120.0, 10.0, 0.0, 0.0),
        "cycle_count": (1.0, 0.0, 0.0, 0.0),  # monotonic-ish counter
    },
    "aging_chamber": {
        "temperature": (55.0, 0.8, 25.0, 90.0),
        "throughput": (280.0, 15.0, 0.0, 0.0),
    },
    "electrode_coater": {
        "temperature": (80.0, 2.0, 25.0, 120.0),
        "thickness": (0.15, 0.005, 0.0, 0.0),
        "throughput": (75.0, 5.0, 0.0, 0.0),
    },
    "calendering_machine": {
        "pressure": (250.0, 8.0, 0.0, 350.0),
        "thickness": (0.10, 0.003, 0.0, 0.0),
        "throughput": (95.0, 6.0, 0.0, 0.0),
    },
    "cell_assembler": {
        "temperature": (30.0, 1.0, 22.0, 55.0),
        "throughput": (190.0, 12.0, 0.0, 0.0),
        "cycle_count": (1.0, 0.0, 0.0, 0.0),
    },
}


class EquipmentSimulator:
    def __init__(self, equipment_type: str, metrics: list[str], seed: int) -> None:
        if equipment_type not in _METRIC_PROFILES:
            raise ValueError(f"unknown equipment type: {equipment_type}")
        self._type = equipment_type
        self._metrics = metrics
        self._rng = random.Random(seed)
        self._cycle_count = 0

    def sample(self, state: EquipmentState) -> list[MetricValue]:
        profile = _METRIC_PROFILES[self._type]
        out: list[MetricValue] = []
        for metric in self._metrics:
            if metric not in profile:
                continue
            mean_run, noise, idle_val, fault_val = profile[metric]
            if metric == "cycle_count":
                if state == EquipmentState.RUNNING:
                    self._cycle_count += 1
                out.append(MetricValue(metric, float(self._cycle_count)))
                continue
            if state == EquipmentState.RUNNING:
                v = self._rng.gauss(mean_run, noise)
            elif state == EquipmentState.FAULT:
                v = fault_val if fault_val > 0 else idle_val
            else:
                v = idle_val
            out.append(MetricValue(metric, round(v, 3)))
        return out
