"""Simulator entry point."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from simulator.config import load_equipment_config
from simulator.logging_config import setup_logging
from simulator.opcua_server import build_server, tick_equipment

setup_logging()
logger = logging.getLogger("simulator")


async def run() -> None:
    endpoint = os.environ.get("OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4840")
    tick_seconds = float(os.environ.get("SIMULATOR_TICK_SECONDS", "1.0"))
    config_path = Path(os.environ.get("EQUIPMENT_CONFIG", "/config/equipment.yaml"))

    configs = load_equipment_config(config_path)
    logger.info("loaded %d equipment configs", len(configs))

    server, nodes = await build_server(endpoint, configs)
    logger.info("starting OPC-UA server on %s", endpoint)
    async with server:
        while True:
            now = datetime.now(timezone.utc)
            for node in nodes:
                try:
                    await tick_equipment(node, now)
                except Exception:
                    logger.exception("tick failed for %s", node.config.id)
            await asyncio.sleep(tick_seconds)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
