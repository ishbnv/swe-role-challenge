"""Tests for Inventory module assembly with a mocked BootContext."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from adapters.persistence_sqlalchemy.bootstrap import SESSION_FACTORY
from adapters.persistence_sqlalchemy.session import SessionFactory
from core.runtime_spi import INVOKER, ArtifactKey, Command, Operation
from plugins.inventory.module import inventory_module
from plugins.inventory.public import (
    RESERVE_STOCK,
    STOCK_OF,
    StockOfInput,
)


class MockBootContext:
    def __init__(self, artifacts: dict[ArtifactKey[Any], Any]) -> None:
        self.artifacts = artifacts
        self.bound_handlers: dict[Operation[Any, Any], Callable[..., Any]] = {}
        self.contributed_commands: list[Command] = []

    def require(self, key: ArtifactKey[Any]) -> Any:
        if key not in self.artifacts:
            raise KeyError(f"Missing artifact: {key.name}")
        return self.artifacts[key]

    def provide(self, key: ArtifactKey[Any], value: Any) -> None:
        self.artifacts[key] = value

    def bind(self, operation: Operation[Any, Any], handler: Callable[..., Any]) -> None:
        if operation in self.bound_handlers:
            raise ValueError(f"Operation {operation.name} already bound")
        self.bound_handlers[operation] = handler

    def contribute(self, command: Command) -> None:
        self.contributed_commands.append(command)


def test_inventory_module_declarations() -> None:
    assert inventory_module.name == "inventory"
    assert inventory_module.operations == frozenset({RESERVE_STOCK, STOCK_OF})
    assert len(inventory_module.steps) == 1

    step = inventory_module.steps[0]
    assert step.name == "inventory.assemble"
    assert step.requires == frozenset({SESSION_FACTORY, INVOKER})
    assert step.provides == frozenset()


def test_inventory_module_assembly_with_mock_boot_context() -> None:
    mock_session_factory = MagicMock(spec=SessionFactory)
    mock_invoker = MagicMock()

    mock_ctx = MockBootContext(
        {
            SESSION_FACTORY: mock_session_factory,
            INVOKER: mock_invoker,
        }
    )

    step = inventory_module.steps[0]
    step.run(mock_ctx)

    # 1. Verify operations bound
    assert STOCK_OF in mock_ctx.bound_handlers
    assert RESERVE_STOCK in mock_ctx.bound_handlers

    # 2. Verify command contributed
    assert len(mock_ctx.contributed_commands) == 1
    cmd = mock_ctx.contributed_commands[0]
    assert cmd.name == "stock"

    # 3. Test CLI execution calls invoker
    mock_invoker.return_value = 10
    output = cmd.run(["A1"])
    assert output == "10"
    mock_invoker.assert_called_once_with(STOCK_OF, StockOfInput(sku="A1"))

    # 4. Test CLI argument validation
    with pytest.raises(ValueError, match="Usage: stock <sku>"):
        cmd.run([])

    with pytest.raises(ValueError, match="Usage: stock <sku>"):
        cmd.run(["A1", "extra"])
