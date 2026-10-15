"""Synthetic building-materials catalogue, accounts and promotions (all invented)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

D = Decimal


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    category: str      # flooring | decking | tile
    unit: str          # sq ft | lin ft
    list_price: Decimal
    cost: Decimal
    ship_mode: str     # parcel | LTL
    stock: int


@dataclass
class Account:
    id: str
    name: str
    ein: str | None = None
    verified: bool = False
    ttm_spend: float = 0.0
    contract_prices: dict[str, Decimal] = field(default_factory=dict)
    delivery_zone: str = "BC-LowerMainland"


@dataclass(frozen=True)
class Promo:
    code: str
    pct: Decimal
    categories: tuple[str, ...]
    exclusive: bool = True     # exclusive promos compete with Pro pricing; stackable ones add on
    priority: int = 10
    pro_only: bool = False

    def applies_to(self, item: Item, is_pro: bool = True) -> bool:
        return item.category in self.categories and (is_pro or not self.pro_only)


MARGIN_FLOOR = {"flooring": D("0.12"), "decking": D("0.10"), "tile": D("0.12")}

CATALOG = {i.sku: i for i in [
    Item("FL-OAK-7", "Engineered oak 7in, natural", "flooring", "sq ft", D("4.29"), D("2.95"), "LTL", 18000),
    Item("FL-LVP-12", "Luxury vinyl plank 12mil, grey", "flooring", "sq ft", D("2.49"), D("1.62"), "LTL", 42000),
    Item("FL-BAM-5", "Strand bamboo 5in, carbonized", "flooring", "sq ft", D("3.79"), D("2.71"), "LTL", 9000),
    Item("DK-CMP-16", "Composite deck board 16ft, teak", "decking", "lin ft", D("3.99"), D("2.80"), "LTL", 25000),
    Item("DK-IPE-8", "Ipe hardwood decking 8ft", "decking", "lin ft", D("8.95"), D("6.70"), "LTL", 4000),
    Item("TL-POR-24", "Porcelain 24x24, matte white", "tile", "sq ft", D("3.15"), D("2.05"), "parcel", 12000),
    Item("TL-SUB-3", "Ceramic subway 3x6, gloss", "tile", "sq ft", D("1.89"), D("1.12"), "parcel", 30000),
]}

PROMOS = [
    Promo("SPRING15", D("0.15"), ("flooring",), exclusive=True),
    Promo("PRO2", D("0.02"), ("flooring", "decking", "tile"), exclusive=False, priority=20, pro_only=True),
]


EIN_RE = re.compile(r"^\d{2}-?\d{7}$")


def verify_pro(account: Account, license_uploaded: bool = False) -> str:
    """Lightweight Pro verification: a well-formed EIN auto-verifies (a production system
    calls a validation API here); a trade licence upload goes to a 24h manual review queue."""
    if account.ein and EIN_RE.match(account.ein):
        account.verified = True
        return "verified"
    if license_uploaded:
        return "manual_review"
    return "rejected"
