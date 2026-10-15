import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from proplatform import CATALOG, PROMOS, Account, QuoteError, QuoteService, price_cart, price_line, tier_for, verify_pro  # noqa: E402
from proplatform.pricing import money  # noqa: E402


def pro(spend=48_000, **kw):
    a = Account("A", "Test Pro", ein="12-3456789", ttm_spend=spend, **kw)
    verify_pro(a)
    return a


# ----------------------------------------------------------------- pricing
def test_unverified_accounts_get_retail_and_no_pro_promos():
    a = Account("R", "Retail")
    assert verify_pro(a) == "rejected" and tier_for(a) == "retail"
    line = price_line("TL-POR-24", 10, a, PROMOS)
    assert line.unit_price == CATALOG["TL-POR-24"].list_price and line.applied == []


@pytest.mark.parametrize("spend,tier", [(10_000, "bronze"), (25_000, "silver"), (150_000, "gold")])
def test_tiers_by_trailing_spend(spend, tier):
    assert tier_for(pro(spend)) == tier


def test_exclusive_promo_competes_best_price_wins():
    # gold (12%) beats SPRING15 on list? 15% off list < 12% off list, so the promo wins
    line = price_line("FL-OAK-7", 10, pro(150_000), PROMOS)
    assert any(a.startswith("promo:SPRING15") for a in line.applied)
    assert not any(a.startswith("tier:") for a in line.applied)


def test_contract_price_takes_precedence_and_ignores_promos():
    a = pro(contract_prices={"FL-BAM-5": Decimal("3.40")})
    line = price_line("FL-BAM-5", 50, a, PROMOS)
    assert line.unit_price == Decimal("3.40") and line.applied == ["contract"]


def test_margin_floor_clamps_and_flags():
    a = pro(contract_prices={"FL-LVP-12": Decimal("1.50")})
    r = price_cart([("FL-LVP-12", 100)], a, PROMOS)
    floor = money(CATALOG["FL-LVP-12"].cost * Decimal("1.12"))
    assert r["lines"][0].unit_price == floor and r["margin_flags"] == ["FL-LVP-12"]


def test_no_line_ever_below_floor():
    for sku, item in CATALOG.items():
        for qty in (1, 600, 1200, 3500):
            for spend in (0, 30_000, 200_000):
                line = price_line(sku, qty, pro(spend), PROMOS)
                assert line.unit_price >= money(item.cost * (1 + Decimal("0.10")))


def test_rounding_half_up_and_totals_reconcile():
    assert money(Decimal("99.995")) == Decimal("100.00")
    r = price_cart([("FL-OAK-7", 333), ("TL-SUB-3", 77), ("DK-IPE-8", 41)], pro(), PROMOS)
    assert r["subtotal"] == sum(l.line_total for l in r["lines"])
    for l in r["lines"]:
        assert l.line_total == l.unit_price * l.qty          # no hidden sub-cent drift
        assert l.unit_price.as_tuple().exponent == -2


# ----------------------------------------------------------------- quotes
@pytest.fixture
def clock():
    t = {"now": datetime(2026, 10, 15, 9)}
    return t


def svc_with(clock):
    return QuoteService(PROMOS, now=lambda: clock["now"])


def test_quote_versions_and_conversion(clock):
    s = svc_with(clock)
    q = s.create(pro(), [("FL-OAK-7", 500)])
    s.revise(q.id, [("FL-OAK-7", 800)])
    assert [v.version for v in q.versions] == [1, 2]
    d = s.delivery_windows(q.current.lines)[0]
    o = s.convert(q.id, d)
    assert o.subtotal == q.current.subtotal and q.status == "converted"
    with pytest.raises(QuoteError):
        s.convert(q.id, d)


def test_expired_quote_must_be_requoted(clock):
    s = svc_with(clock)
    q = s.create(pro(), [("TL-SUB-3", 100)])
    clock["now"] += timedelta(days=31)
    with pytest.raises(QuoteError, match="expired"):
        s.convert(q.id, s.delivery_windows(q.current.lines)[0])


def test_price_move_beyond_tolerance_blocks_conversion(clock):
    s = svc_with(clock)
    a = pro()
    q = s.create(a, [("FL-BAM-5", 100)])
    s.promos = []          # promo ended after the quote was issued: price moves up
    with pytest.raises(QuoteError, match="re-quote"):
        s.convert(q.id, s.delivery_windows(q.current.lines)[0])


def test_ltl_lead_time_and_weekday_delivery(clock):
    s = svc_with(clock)
    days = s.delivery_windows([("FL-OAK-7", 10)])        # LTL: 4 business days
    assert all(d.weekday() < 5 for d in days)
    assert days[0] > clock["now"].date() + timedelta(days=4)


def test_reorder_reprices_at_today(clock):
    s = svc_with(clock)
    q = s.create(pro(), [("DK-CMP-16", 300)])
    o = s.convert(q.id, s.delivery_windows(q.current.lines)[0])
    rq = s.reorder(o.id)
    assert rq.current.lines == o.lines and rq.status == "sent"


# ----------------------------------------------------------------- API
def test_api_flow():
    from fastapi.testclient import TestClient
    from proplatform.api import app
    c = TestClient(app)
    body = {"account_id": "A-100", "lines": [{"sku": "FL-OAK-7", "qty": 400}]}
    assert c.post("/price", json=body).json()["tier"] == "silver"
    qid = c.post("/quotes", json=body).json()["quote_id"]
    day = c.get(f"/quotes/{qid}/delivery-windows").json()[0]
    r = c.post(f"/quotes/{qid}/convert", params={"delivery_date": day})
    assert r.status_code == 200
    assert c.post(f"/quotes/{qid}/convert", params={"delivery_date": day}).status_code == 409
