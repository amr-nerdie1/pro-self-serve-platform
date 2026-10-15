"""Pro pricing engine.

Replaces phone-negotiated pricing with rules a contractor can trust online:

1. Contract price (account + SKU) if one exists
2. Otherwise list price less the account's Pro tier discount
3. Volume break for large orders of the same SKU
4. Promotions: exclusive promos compete with Pro pricing (best price wins);
   stackable promos apply on top
5. **Margin floor**: no line can price below cost x (1 + category floor). If a rule
   would break it, the price is clamped and the line is flagged for the category
   manager. This is what let vendor managers sign off on publishing Pro prices.

All money is ``Decimal`` and rounded once, half-up, at the line level. Float math and
inconsistent rounding between systems caused real checkout failures in the
replatform this is modelled on, so the rule is explicit and tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .catalog import CATALOG, MARGIN_FLOOR, Account, Promo

CENT = Decimal("0.01")
TIER_DISCOUNT = {"retail": Decimal("0"), "bronze": Decimal("0.05"), "silver": Decimal("0.08"), "gold": Decimal("0.12")}
# category: [(min qty, extra discount)] in descending qty order
VOLUME_BREAKS = {"flooring": [(3000, Decimal("0.05")), (1000, Decimal("0.03"))],
                 "decking": [(2000, Decimal("0.04")), (800, Decimal("0.02"))],
                 "tile": [(1500, Decimal("0.04")), (500, Decimal("0.02"))]}


def money(x) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class PricedLine:
    sku: str
    qty: int
    list_price: Decimal
    unit_price: Decimal
    line_total: Decimal
    applied: list[str] = field(default_factory=list)
    margin_flag: bool = False

    @property
    def savings(self) -> Decimal:
        return money(self.list_price * self.qty) - self.line_total


def tier_for(account: Account) -> str:
    """Tier from trailing-12-month spend; unverified accounts always get retail pricing."""
    if not account.verified:
        return "retail"
    s = account.ttm_spend
    return "gold" if s >= 100_000 else "silver" if s >= 25_000 else "bronze"


def price_line(sku: str, qty: int, account: Account, promos: list[Promo] | None = None) -> PricedLine:
    item = CATALOG[sku]
    lst = item.list_price
    applied = []

    # 1-2. contract price or tier discount
    if account.verified and sku in account.contract_prices:
        base = account.contract_prices[sku]
        applied.append("contract")
    else:
        tier = tier_for(account)
        base = lst * (1 - TIER_DISCOUNT[tier])
        if tier != "retail":
            applied.append(f"tier:{tier}")

    # 3. volume break (only on non-contract lines; contracts already reflect volume)
    if "contract" not in applied:
        for min_qty, d in VOLUME_BREAKS.get(item.category, []):
            if qty >= min_qty:
                base = base * (1 - d)
                applied.append(f"volume:{min_qty}+")
                break

    # 4. promotions (contract lines are already negotiated: no promos on top)
    is_pro = tier_for(account) != "retail"
    for p in sorted(promos or [], key=lambda p: p.priority):
        if "contract" in applied or not p.applies_to(item, is_pro):
            continue
        promo_price = (lst if p.exclusive else base) * (1 - p.pct)
        if p.exclusive:
            if promo_price < base:              # best price wins, no stacking
                base, applied = promo_price, [f"promo:{p.code}"]
        else:
            base = promo_price
            applied.append(f"promo:{p.code}")

    # 5. margin floor guardrail
    floor = item.cost * (1 + MARGIN_FLOOR[item.category])
    flag = False
    if base < floor:
        base, flag = floor, True
        applied.append("floor-clamped")

    unit = money(base)
    return PricedLine(sku, qty, lst, unit, money(unit * qty), applied, flag)


def price_cart(lines: list[tuple[str, int]], account: Account, promos: list[Promo] | None = None) -> dict:
    priced = [price_line(s, q, account, promos) for s, q in lines]
    subtotal = sum((p.line_total for p in priced), Decimal("0"))
    return {"lines": priced, "subtotal": subtotal, "savings": sum((p.savings for p in priced), Decimal("0")),
            "margin_flags": [p.sku for p in priced if p.margin_flag], "tier": tier_for(account)}
