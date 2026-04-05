import pytest
from simulator.state_machine import EquipmentState, StateMachine


def test_initial_state_is_idle():
    sm = StateMachine(seed=42)
    assert sm.state == EquipmentState.IDLE


def test_idle_transitions_to_running():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    assert sm.state == EquipmentState.RUNNING


def test_invalid_transition_raises():
    sm = StateMachine(seed=42)
    # idle -> fault is not allowed (must go through running)
    with pytest.raises(ValueError, match="invalid transition"):
        sm.transition_to(EquipmentState.FAULT)


def test_running_can_go_to_fault():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    assert sm.state == EquipmentState.FAULT


def test_fault_can_go_to_maintenance():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    assert sm.state == EquipmentState.MAINTENANCE


def test_maintenance_returns_to_idle():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    sm.transition_to(EquipmentState.IDLE)
    assert sm.state == EquipmentState.IDLE


def test_auto_tick_eventually_runs():
    # With a deterministic seed, after enough ticks we should be running
    sm = StateMachine(seed=42)
    for _ in range(100):
        sm.tick()
    # Seed 42 should have entered RUNNING at some point
    assert sm.total_transitions > 0


def test_fault_code_set_in_fault_state():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    assert sm.fault_code is not None
    assert sm.fault_code.startswith("F-")


def test_fault_code_cleared_on_idle():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    sm.transition_to(EquipmentState.IDLE)
    assert sm.fault_code is None
