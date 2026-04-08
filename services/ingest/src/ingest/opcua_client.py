"""OPC-UA client: browse equipment and subscribe to nodes."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from asyncua import Client, Node, ua

logger = logging.getLogger(__name__)


@dataclass
class EquipmentState:
    equipment_id: str
    status: str | None = None
    batch_id: str | None = None
    unit_id: str | None = None
    metrics: dict[str, float] | None = None


# Fixed names (not metrics) exposed on each equipment object.
_META_NODES = {"Status", "FaultCode", "CurrentBatchId", "CurrentUnitId"}


class _SubHandler:
    """asyncua subscription handler."""

    def __init__(
        self,
        node_index: dict[str, tuple[str, str]],
        state: dict[str, EquipmentState],
        on_update: Callable[[str], None],
    ) -> None:
        self._idx = node_index
        self._state = state
        self._on_update = on_update

    def datachange_notification(self, node: Node, val, data) -> None:
        key = node.nodeid.to_string()
        entry = self._idx.get(key)
        if entry is None:
            return
        equipment_id, field = entry
        st = self._state.setdefault(equipment_id, EquipmentState(equipment_id=equipment_id))
        if field == "Status":
            st.status = val if val else None
        elif field == "CurrentBatchId":
            st.batch_id = val if val else None
        elif field == "CurrentUnitId":
            st.unit_id = val if val else None
        elif field == "FaultCode":
            pass
        else:
            if st.metrics is None:
                st.metrics = {}
            try:
                st.metrics[field] = float(val)
            except (TypeError, ValueError):
                return
        self._on_update(equipment_id)


async def connect_and_subscribe(
    endpoint: str,
    on_update: Callable[[str, EquipmentState, datetime], None],
    state_store: dict[str, EquipmentState],
) -> Client:
    """Connect, browse equipment, subscribe to all nodes. Returns live client."""
    client = Client(url=endpoint)
    await client.connect()
    logger.info("connected to OPC-UA %s", endpoint)

    # Look up the simulator namespace index by URI so we're not hardcoding it
    ns = await client.get_namespace_index("urn:factory-pulse:simulator")
    logger.info("simulator namespace index: %d", ns)

    factory = await client.nodes.objects.get_child([f"{ns}:Factory"])
    equipment_folder = await factory.get_child([f"{ns}:Equipment"])
    equipment_objs = await equipment_folder.get_children()

    node_index: dict[str, tuple[str, str]] = {}
    variables_to_subscribe: list[Node] = []

    for obj in equipment_objs:
        qname = await obj.read_browse_name()
        equipment_id = qname.Name
        children = await obj.get_children()
        for child in children:
            cname = (await child.read_browse_name()).Name
            node_index[child.nodeid.to_string()] = (equipment_id, cname)
            variables_to_subscribe.append(child)

    logger.info("subscribing to %d nodes across %d equipment", len(variables_to_subscribe), len(equipment_objs))

    def _trigger(equipment_id: str) -> None:
        st = state_store.get(equipment_id)
        if st is None:
            return
        on_update(equipment_id, st, datetime.now(timezone.utc))

    handler = _SubHandler(node_index, state_store, _trigger)
    sub = await client.create_subscription(1000, handler)
    await sub.subscribe_data_change(variables_to_subscribe)
    return client
