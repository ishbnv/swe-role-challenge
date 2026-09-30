"""Unit tests for Inventory domain and application layers without DB or runtime."""

from typing import cast

import pytest

from core.runtime_spi import Operation
from plugins.inventory.adapters.cli import make_stock_cli
from plugins.inventory.adapters.handlers import (
    make_reserve_stock_handler,
    make_stock_of_handler,
)
from plugins.inventory.application.ports import StockRepository
from plugins.inventory.application.use_cases import GetStockUseCase, ReserveStockUseCase
from plugins.inventory.domain.stock import Stock, deduct_stock, validate_qty
from plugins.inventory.public import (
    STOCK_OF,
    InsufficientStock,
    ReserveStockInput,
    StockOfInput,
)


class InMemoryStockRepo(StockRepository):
    def __init__(self, initial: dict[str, int] | None = None) -> None:
        self.stocks: dict[str, int] = dict(initial or {})

    def get_stock(self, sku: str) -> int | None:
        return self.stocks.get(sku)

    def reserve_stock(self, sku: str, qty: int) -> None:
        if sku not in self.stocks:
            raise InsufficientStock(f"Unknown SKU: {sku}")
        self.stocks[sku] = deduct_stock(self.stocks[sku], qty)


def test_validate_qty() -> None:
    validate_qty(1)
    validate_qty(10)
    with pytest.raises(ValueError, match="positive"):
        validate_qty(0)
    with pytest.raises(ValueError, match="positive"):
        validate_qty(-5)


def test_deduct_stock_success() -> None:
    assert deduct_stock(10, 3) == 7
    assert deduct_stock(5, 5) == 0


def test_deduct_stock_insufficient() -> None:
    with pytest.raises(InsufficientStock, match="Insufficient stock"):
        deduct_stock(5, 6)


def test_deduct_stock_invalid_qty() -> None:
    with pytest.raises(ValueError, match="positive"):
        deduct_stock(10, 0)
    with pytest.raises(ValueError, match="positive"):
        deduct_stock(10, -2)


def test_stock_entity_creation_and_properties() -> None:
    s1 = Stock(sku="A1", current=10)
    assert s1.sku == "A1"
    assert s1.current == 10
    assert s1.qty == 10
    assert s1.quantity == 10

    s2 = Stock(sku="B2", qty=5)
    assert s2.current == 5

    s3 = Stock(sku="C3", quantity=2)
    assert s3.current == 2

    # Setting negative values fails
    with pytest.raises(ValueError, match="negative"):
        Stock(sku="A1", current=-1)
    with pytest.raises(ValueError, match="negative"):
        s1.qty = -3
    with pytest.raises(ValueError, match="negative"):
        s1.quantity = -2

    # Missing initial value raises TypeError
    with pytest.raises(TypeError):
        Stock(sku="A1")


def test_stock_entity_reserve_and_decrease() -> None:
    stock = Stock(sku="A1", current=10)
    stock.reserve(3)
    assert stock.current == 7
    assert stock.qty == 7

    stock.decrease(2)
    assert stock.current == 5

    # Insufficient stock
    with pytest.raises(InsufficientStock):
        stock.reserve(10)
    assert stock.current == 5  # unchanged

    # Non-positive quantity
    with pytest.raises(ValueError, match="positive"):
        stock.reserve(0)
    with pytest.raises(ValueError, match="positive"):
        stock.reserve(-1)
    with pytest.raises(ValueError, match="positive"):
        stock.decrease(0)
    assert stock.current == 5  # unchanged


def test_get_stock_use_case() -> None:
    repo = InMemoryStockRepo({"A1": 10})
    uc = GetStockUseCase(repo)
    assert uc.execute("A1") == 10
    assert uc("A1") == 10
    assert uc.execute("UNKNOWN") == 0
    assert uc("UNKNOWN") == 0


def test_reserve_stock_use_case_success() -> None:
    repo = InMemoryStockRepo({"A1": 10})
    uc = ReserveStockUseCase(repo)
    uc.execute("A1", 4)
    assert repo.get_stock("A1") == 6
    uc("A1", 2)
    assert repo.get_stock("A1") == 4


def test_reserve_stock_use_case_insufficient() -> None:
    repo = InMemoryStockRepo({"A1": 3})
    uc = ReserveStockUseCase(repo)
    with pytest.raises(InsufficientStock):
        uc.execute("A1", 5)
    assert repo.get_stock("A1") == 3


def test_reserve_stock_use_case_invalid_qty() -> None:
    repo = InMemoryStockRepo({"A1": 10})
    uc = ReserveStockUseCase(repo)
    with pytest.raises(ValueError, match="positive"):
        uc.execute("A1", 0)
    with pytest.raises(ValueError, match="positive"):
        uc("A1", -3)
    assert repo.get_stock("A1") == 10


def test_operation_handlers() -> None:
    repo = InMemoryStockRepo({"A1": 10})
    get_uc = GetStockUseCase(repo)
    reserve_uc = ReserveStockUseCase(repo)

    stock_of_handler = make_stock_of_handler(get_uc)
    reserve_handler = make_reserve_stock_handler(reserve_uc)

    assert stock_of_handler(StockOfInput(sku="A1")) == 10
    assert stock_of_handler(StockOfInput(sku="NONE")) == 0

    reserve_handler(ReserveStockInput(sku="A1", qty=4))
    assert stock_of_handler(StockOfInput(sku="A1")) == 6


def test_stock_cli_command() -> None:
    def fake_invoker[I, O](operation: Operation[I, O], input: I) -> O:
        if operation is STOCK_OF and isinstance(input, StockOfInput):
            return cast(O, 10 if input.sku == "A1" else 0)
        raise ValueError(f"Unexpected op: {operation}")

    cli_run = make_stock_cli(fake_invoker)
    assert cli_run(["A1"]) == "10"
    assert cli_run(["UNKNOWN"]) == "0"

    with pytest.raises(ValueError, match="Usage: stock <sku>"):
        cli_run([])

    with pytest.raises(ValueError, match="Usage: stock <sku>"):
        cli_run(["A1", "extra"])
