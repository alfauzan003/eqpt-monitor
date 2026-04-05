"""OPC-UA server exposing equipment nodes."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from asyncua import Server, ua

from simulator.batch_tracker import BatchTracker
from simulator.config import EquipmentConfig
from simulator.equipment import EquipmentSimulator
from simulator.state_machine import EquipmentState, StateMachine

logger = logging.getLogger(__name__)

NAMESPACE_URI = "urn:factory-pulse:simulator"


class EquipmentNode:
    """Holds the OPC-UA node handles for a single piece of equipment."""

    def __init__(
        self,
        config: EquipmentConfig,
        state: StateMachine,
        sim: EquipmentSimulator,
        tracker: BatchTracker,
    ) -> None:
        self.config = config
        self.state = state
        self.sim = sim
        self.tracker = tracker
        # Populated during server setup
        self.status_node: ua.NodeId | None = None
        self.fault_code_node: ua.NodeId | None = None
        self.current_batch_node: ua.NodeId | None = None
        self.current_unit_node: ua.NodeId | None = None
        self.metric_nodes: dict[str, ua.NodeId] = {}


async def build_server(
    endpoint: str, equipment_configs: list[EquipmentConfig]
) -> tuple[Server, list[EquipmentNode]]:
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("factory-pulse simulator")

    idx = await server.register_namespace(NAMESPACE_URI)

    objects = server.nodes.objects
    factory = await objects.add_object(idx, "Factory")
    equipment_folder = await factory.add_object(idx, "Equipment")

    now = datetime.now(timezone.utc)
    nodes: list[EquipmentNode] = []

    for i, cfg in enumerate(equipment_configs):
        obj = await equipment_folder.add_object(idx, cfg.id)
        status = await obj.add_variable(idx, "Status", "idle", ua.VariantType.String)
        await status.set_writable()
        fault = await obj.add_variable(idx, "FaultCode", "", ua.VariantType.String)
        await fault.set_writable()
        batch = await obj.add_variable(idx, "CurrentBatchId", "", ua.VariantType.String)
        await batch.set_writable()
        unit = await obj.add_variable(idx, "CurrentUnitId", "", ua.VariantType.String)
        await unit.set_writable()

        metric_vars: dict[str, ua.NodeId] = {}
        for metric in cfg.metrics:
            var = await obj.add_variable(idx, metric, 0.0, ua.VariantType.Double)
            await var.set_writable()
            metric_vars[metric] = var

        node = EquipmentNode(
            config=cfg,
            state=StateMachine(seed=hash(cfg.id) & 0xFFFFFFFF),
            sim=EquipmentSimulator(cfg.type, cfg.metrics, seed=i * 7919),
            tracker=BatchTracker(
                unit_duration_seconds=cfg.unit_duration_seconds,
                unit_id_prefix=cfg.unit_id_prefix,
                now=now,
            ),
        )
        node.status_node = status
        node.fault_code_node = fault
        node.current_batch_node = batch
        node.current_unit_node = unit
        node.metric_nodes = metric_vars
        nodes.append(node)

    return server, nodes


async def tick_equipment(node: EquipmentNode, now: datetime) -> None:
    node.state.tick()
    node.tracker.advance(now)
    samples = node.sim.sample(node.state.state)

    await node.status_node.write_value(node.state.state.value)  # type: ignore[union-attr]
    await node.fault_code_node.write_value(node.state.fault_code or "")  # type: ignore[union-attr]
    await node.current_batch_node.write_value(node.tracker.current_batch_id)  # type: ignore[union-attr]
    await node.current_unit_node.write_value(node.tracker.current_unit_id)  # type: ignore[union-attr]
    for s in samples:
        var = node.metric_nodes.get(s.name)
        if var is not None:
            await var.write_value(s.value)
