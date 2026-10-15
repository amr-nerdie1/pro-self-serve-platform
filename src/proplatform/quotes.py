"""Quotes, orders, repeat orders and delivery scheduling.

Design decision (from the real build): quotes live in their own service, not as
draft orders in the OMS. Quotes are editable, versioned and expire; the OMS isn't
built for that, and draft writes would compete with live order traffic under its
rate limits. The OMS is only touched at conversion, after re-validation.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .catalog import CATALOG, Account, Promo
from .pricing import price_cart

QUOTE_TTL_DAYS = 30
PRICE_TOLERANCE = Decimal("0.02")   # re-quote if price moved more than 2% since the quote
LEAD_DAYS = {"parcel": 2, "LTL": 4}
_ids = itertools.count(1001)


class QuoteError(Exception):
    pass


@dataclass
class QuoteVersion:
    version: int
    lines: list[tuple[str, int]]
    subtotal: Decimal
    unit_prices: dict[str, Decimal]
    created: datetime


@dataclass
class Quote:
    id: str
    account: Account
    versions: list[QuoteVersion] = field(default_factory=list)
    status: str = "draft"            # draft | sent | converted | expired
    expires_at: datetime | None = None

    @property
    def current(self) -> QuoteVersion:
        return self.versions[-1]


@dataclass
class Order:
    id: str
    account: Account
    lines: list[tuple[str, int]]
    subtotal: Decimal
    delivery_date: date
    source_quote: str | None = None


class QuoteService:
    def __init__(self, promos: list[Promo] | None = None, now=datetime.now):
        self.quotes: dict[str, Quote] = {}
        self.orders: dict[str, Order] = {}
        self.promos = promos or []
        self.now = now

    def _version(self, account, lines, n) -> QuoteVersion:
        for sku, qty in lines:
            if sku not in CATALOG:
                raise QuoteError(f"unknown SKU {sku}")
            if qty <= 0:
                raise QuoteError("quantity must be positive")
        priced = price_cart(lines, account, self.promos)
        return QuoteVersion(n, list(lines), priced["subtotal"], {p.sku: p.unit_price for p in priced["lines"]}, self.now())

    def create(self, account: Account, lines: list[tuple[str, int]]) -> Quote:
        q = Quote(f"Q-{next(_ids)}", account, [self._version(account, lines, 1)], "sent",
                  self.now() + timedelta(days=QUOTE_TTL_DAYS))
        self.quotes[q.id] = q
        return q

    def revise(self, quote_id: str, lines: list[tuple[str, int]]) -> Quote:
        q = self._open(quote_id)
        q.versions.append(self._version(q.account, lines, q.current.version + 1))
        q.expires_at = self.now() + timedelta(days=QUOTE_TTL_DAYS)
        return q

    def _open(self, quote_id: str) -> Quote:
        q = self.quotes.get(quote_id)
        if not q:
            raise QuoteError("quote not found")
        if q.status == "converted":
            raise QuoteError("quote already converted")
        if self.now() > q.expires_at:
            q.status = "expired"
            raise QuoteError("quote expired: re-quote at current prices")
        return q

    def delivery_windows(self, lines: list[tuple[str, int]], start: date | None = None, n: int = 5) -> list[date]:
        """Next n weekday delivery dates after the slowest line's lead time."""
        lead = max(LEAD_DAYS[CATALOG[s].ship_mode] for s, _ in lines)
        d, out = (start or self.now().date()), []
        added = 0
        while added < lead:
            d += timedelta(days=1)
            if d.weekday() < 5:
                added += 1
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d)
            d += timedelta(days=1)
        return out

    def convert(self, quote_id: str, delivery_date: date) -> Order:
        """Re-validate stock and price, then (and only then) write the order."""
        q = self._open(quote_id)
        lines = q.current.lines
        for sku, qty in lines:
            if CATALOG[sku].stock < qty:
                raise QuoteError(f"{sku}: only {CATALOG[sku].stock} in stock")
        fresh = price_cart(lines, q.account, self.promos)
        for p in fresh["lines"]:
            quoted = q.current.unit_prices[p.sku]
            if quoted and abs(p.unit_price - quoted) / quoted > PRICE_TOLERANCE:
                raise QuoteError(f"{p.sku}: price moved {quoted} -> {p.unit_price}; re-quote required")
        if delivery_date not in self.delivery_windows(lines, n=15):
            raise QuoteError("delivery date not available")
        o = Order(f"O-{next(_ids)}", q.account, lines, q.current.subtotal, delivery_date, q.id)
        self.orders[o.id] = o
        q.status = "converted"
        return o

    def reorder(self, order_id: str) -> Quote:
        """One-click repeat order: same lines, today's prices, new quote ready to confirm."""
        o = self.orders[order_id]
        return self.create(o.account, o.lines)
