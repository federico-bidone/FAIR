"""Italian tax primitives for execution."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MinusLot:
    """Represent a loss carry-forward amount with an expiry date.

    Attributes:
      amount: Loss amount available for offsetting future gains.
      expiry: Date when the loss expires (inclusive).
    """

    amount: float
    expiry: dt.date


class MinusBag:
    """Track loss carry-forward amounts over the four-year Italian horizon."""

    def __init__(self, lots: Iterable[MinusLot] | None = None) -> None:
        self._lots: list[MinusLot] = []
        if lots:
            self._lots.extend(sorted(lots, key=lambda lot: lot.expiry))

    def _purge(self, as_of: dt.date) -> None:
        self._lots = [lot for lot in self._lots if lot.expiry >= as_of]

    def consume(self, amount: float, as_of: dt.date) -> float:
        """Consume available losses up to ``amount`` and return the utilised value."""

        if amount <= 0.0:
            return 0.0
        self._purge(as_of)
        remaining = float(amount)
        consumed: list[MinusLot] = []
        updated: list[MinusLot] = []
        for lot in self._lots:
            if remaining <= 0.0:
                updated.append(lot)
                continue
            usable = min(lot.amount, remaining)
            consumed.append(MinusLot(amount=usable, expiry=lot.expiry))
            leftover = lot.amount - usable
            if leftover > 0.0:
                updated.append(MinusLot(amount=leftover, expiry=lot.expiry))
            remaining -= usable
        self._lots = updated
        return float(sum(lot.amount for lot in consumed))

    def add_loss(self, amount: float, trade_date: dt.date) -> None:
        """Store a new loss amount with four-year expiry from ``trade_date``."""

        if amount <= 0.0:
            return
        expiry = _add_years(trade_date, 4)
        self._lots.append(MinusLot(amount=float(amount), expiry=expiry))
        self._lots.sort(key=lambda lot: lot.expiry)

    def snapshot(self) -> list[MinusLot]:
        """Return a copy of the remaining loss lots."""

        return list(self._lots)

    @property
    def total(self) -> float:
        """Total loss amount still available for offsetting."""

        return float(sum(lot.amount for lot in self._lots))


@dataclass(frozen=True)
class TaxRules:
    """Configuration bundle for Italian tax computations.

    Attributes:
      method: Tax lot matching method (``fifo``, ``lifo``, ``min_tax``).
      stamp_duty_rate: Pro-rata "bollo" duty rate applied to the portfolio value.
      govies_threshold: Minimum government share triggering the 12.5% rate.
      minus_bag: Optional loss carry container shared across periods.
      portfolio_value: Current positive portfolio value used for stamp duty.
    """

    method: str
    stamp_duty_rate: float = 0.002
    govies_threshold: float = 0.51
    minus_bag: MinusBag | None = None
    portfolio_value: float = 0.0


@dataclass(frozen=True)
class TaxComputation:
    """Structured summary of a tax computation.

    Attributes:
      capital_gains_tax: Total capital gains tax due after offsets.
      stamp_duty: Bollo computed from the configured portfolio value.
      taxable_other: Remaining taxable gains taxed at 26%.
      taxable_govies: Remaining taxable gains taxed at 12.5%.
      minus_consumed: Losses consumed from the minus bag during the computation.
      minus_added: New losses added to the minus bag with four-year expiry.
    """

    capital_gains_tax: float
    stamp_duty: float
    taxable_other: float
    taxable_govies: float
    minus_consumed: float
    minus_added: float

    @property
    def total_tax(self) -> float:
        """Return the total tax burden combining capital gains and stamp duty."""

        return self.capital_gains_tax + self.stamp_duty


def tax_penalty_it(
    realized_pnl: np.ndarray,
    govies_ratio: np.ndarray,
    stamp_duty_rate: float = 0.002,
) -> float:
    """Estimate Italian-style tax penalties using aggregate PnL arrays.

    Args:
      realized_pnl: Realised PnL per instrument expressed in currency units.
      govies_ratio: Share of qualifying government securities (≥51% => 12.5% tax
        rate) per instrument.
      stamp_duty_rate: Pro-rata "bollo" duty rate applied to positive balances.

    Returns:
      Estimated tax penalty (capital gains plus stamp duty).

    Raises:
      ValueError: If the arrays have mismatched shapes.
    """

    pnl = np.asarray(realized_pnl, dtype=float)
    govies_ratio = np.asarray(govies_ratio, dtype=float)
    if pnl.shape != govies_ratio.shape:
        raise ValueError("realized_pnl and govies_ratio must share the same shape")

    gains = np.maximum(pnl, 0.0)
    losses = -np.minimum(pnl, 0.0)
    govies_mask = govies_ratio >= 0.51

    other_gains = gains[~govies_mask].sum()
    govies_gains = gains[govies_mask].sum()
    loss_pool = losses.sum()

    taxable_other = max(0.0, other_gains - loss_pool)
    remaining_losses = max(0.0, loss_pool - other_gains)
    taxable_govies = max(0.0, govies_gains - remaining_losses)

    capital_gains_tax = 0.26 * taxable_other + 0.125 * taxable_govies
    stamp_base = gains.sum()
    stamp_duty = stamp_duty_rate * stamp_base

    return float(capital_gains_tax + stamp_duty)


def compute_tax_penalty(
    orders: pd.DataFrame,
    inventory: pd.DataFrame,
    tax_rules: TaxRules,
) -> TaxComputation:
    """Compute Italian tax penalties using per-lot matching.

    Args:
      orders: DataFrame with executed trades. Columns required: ``instrument_id``,
        ``quantity`` (positive for buys, negative for sells), ``price``,
        ``trade_date``, ``govies_share``.
      inventory: DataFrame describing current holdings. Columns required:
        ``instrument_id``, ``lot_id``, ``quantity``, ``cost_basis``, ``acquired``,
        ``govies_share``.
      tax_rules: Configuration bundle specifying matching method, stamp duty,
        government threshold, optional minus bag, and portfolio value.

    Returns:
      ``TaxComputation`` detailing taxable amounts, consumed/added losses, and
      total taxes.

    Raises:
      ValueError: If inputs are missing required columns or if sells exceed
        inventory quantities.
    """

    required_orders = {
        "instrument_id",
        "quantity",
        "price",
        "trade_date",
        "govies_share",
    }
    required_inventory = {
        "instrument_id",
        "lot_id",
        "quantity",
        "cost_basis",
        "acquired",
        "govies_share",
    }
    missing_orders = required_orders.difference(orders.columns)
    missing_inventory = required_inventory.difference(inventory.columns)
    if missing_orders:
        raise ValueError(f"orders missing columns: {sorted(missing_orders)}")
    if missing_inventory:
        raise ValueError(f"inventory missing columns: {sorted(missing_inventory)}")

    sells = orders[orders["quantity"] < 0.0]
    inventory_copy = inventory.copy()
    lots_by_instrument: dict[str, list[dict[str, object]]] = {}
    for idx, row in enumerate(inventory_copy.itertuples(index=False), start=1):
        instrument = str(row.instrument_id)
        lots_by_instrument.setdefault(instrument, []).append(
            {
                "sequence": idx,
                "remaining": float(row.quantity),
                "cost_basis": float(row.cost_basis),
                "acquired": _coerce_date(row.acquired),
                "govies_share": float(row.govies_share),
            }
        )

    gain_records: list[tuple[float, bool]] = []
    trade_dates: list[dt.date] = []
    method = tax_rules.method.lower()
    for order in sells.itertuples(index=False):
        instrument = str(order.instrument_id)
        available = lots_by_instrument.get(instrument, [])
        trade_qty = float(abs(order.quantity))
        if trade_qty == 0.0:
            continue
        total_available = sum(lot["remaining"] for lot in available)
        if trade_qty > total_available + 1e-9:
            raise ValueError(f"insufficient inventory for instrument {instrument}")

        trade_date = _coerce_date(order.trade_date)
        trade_dates.append(trade_date)
        price = float(order.price)
        method_key = method
        if float(order.govies_share) >= tax_rules.govies_threshold:
            if all(float(lot["govies_share"]) >= tax_rules.govies_threshold for lot in available):
                method_key = "fifo"
        lots_sorted = _sort_lots(available, method_key)
        remaining_qty = trade_qty
        for lot in lots_sorted:
            if remaining_qty <= 0.0:
                break
            lot_remaining = float(lot["remaining"])
            if lot_remaining <= 0.0:
                continue
            take = min(lot_remaining, remaining_qty)
            lot["remaining"] = lot_remaining - take
            gain = (price - float(lot["cost_basis"])) * take
            govies_flag = float(lot["govies_share"]) >= tax_rules.govies_threshold
            gain_records.append((float(gain), govies_flag))
            remaining_qty -= take
        if remaining_qty > 1e-9:
            raise ValueError(f"lot matching failed for instrument {instrument}")

    other_gains = sum(max(0.0, gain) for gain, flag in gain_records if not flag)
    govies_gains = sum(max(0.0, gain) for gain, flag in gain_records if flag)
    loss_pool = sum(max(0.0, -gain) for gain, _ in gain_records)

    taxable_other = max(0.0, other_gains - loss_pool)
    remaining_losses = max(0.0, loss_pool - other_gains)
    taxable_govies = max(0.0, govies_gains - remaining_losses)
    leftover_losses = max(0.0, remaining_losses - govies_gains)

    minus_consumed = 0.0
    minus_added = 0.0
    reference_date = max(trade_dates) if trade_dates else dt.date.today()
    if tax_rules.minus_bag is not None:
        consumed_other = tax_rules.minus_bag.consume(taxable_other, reference_date)
        taxable_other = max(0.0, taxable_other - consumed_other)
        consumed_govies = tax_rules.minus_bag.consume(taxable_govies, reference_date)
        taxable_govies = max(0.0, taxable_govies - consumed_govies)
        minus_consumed += consumed_other + consumed_govies
        if leftover_losses > 0.0:
            tax_rules.minus_bag.add_loss(leftover_losses, reference_date)
            minus_added = leftover_losses

    capital_gains_tax = 0.26 * taxable_other + 0.125 * taxable_govies
    stamp_base = max(0.0, tax_rules.portfolio_value)
    stamp_duty = max(0.0, tax_rules.stamp_duty_rate) * stamp_base

    return TaxComputation(
        capital_gains_tax=float(capital_gains_tax),
        stamp_duty=float(stamp_duty),
        taxable_other=float(taxable_other),
        taxable_govies=float(taxable_govies),
        minus_consumed=float(minus_consumed),
        minus_added=float(minus_added),
    )


def _add_years(start: dt.date, years: int) -> dt.date:
    """Return ``start`` advanced by ``years`` while handling leap years."""

    try:
        return start.replace(year=start.year + years)
    except ValueError:
        # Handle February 29th by falling back to February 28th.
        return start.replace(month=2, day=28, year=start.year + years)


def _coerce_date(value: object) -> dt.date:
    """Convert supported date representations into ``datetime.date``."""

    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    parsed = pd.to_datetime(value, utc=False)
    if isinstance(parsed, pd.Timestamp):
        if pd.isna(parsed):
            raise ValueError("Date value cannot be NaT")
        return parsed.date()
    raise TypeError(f"Unsupported date value: {value!r}")


def _sort_lots(lots: list[dict[str, object]], method: str) -> list[dict[str, object]]:
    """Return lots sorted according to the selected matching method."""

    if method not in {"fifo", "lifo", "min_tax"}:
        raise ValueError(f"Unsupported tax matching method: {method}")

    if method == "fifo":
        return sorted(
            lots,
            key=lambda lot: (lot["acquired"], lot["sequence"]),
        )
    if method == "lifo":
        return sorted(
            lots,
            key=lambda lot: (
                -_to_ordinal(lot["acquired"]),
                -int(lot["sequence"]),
            ),
        )
    return sorted(
        lots,
        key=lambda lot: (
            -float(lot["cost_basis"]),
            lot["acquired"],
            lot["sequence"],
        ),
    )


def _to_ordinal(value: object) -> int:
    """Return the ordinal representation of a date-like object."""

    date_value = _coerce_date(value)
    return date_value.toordinal()
