"""HTTP API (FastAPI). In-memory store; run with:  uvicorn proplatform.api:app --reload"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .catalog import CATALOG, PROMOS, Account, verify_pro
from .pricing import price_cart
from .quotes import QuoteError, QuoteService

app = FastAPI(title="Pro self-serve platform", version="1.0")
svc = QuoteService(PROMOS)
ACCOUNTS: dict[str, Account] = {
    "A-100": Account("A-100", "Ridge Renovations", ein="12-3456789", ttm_spend=48_000),
    "A-200": Account("A-200", "Harbour Builders", ein="98-7654321", ttm_spend=160_000,
                     contract_prices={"FL-LVP-12": Decimal("1.89")}),
}
for a in ACCOUNTS.values():
    verify_pro(a)


class Line(BaseModel):
    sku: str
    qty: int


class Cart(BaseModel):
    account_id: str
    lines: list[Line]


def _acct(aid: str) -> Account:
    if aid not in ACCOUNTS:
        raise HTTPException(404, "account not found")
    return ACCOUNTS[aid]


def _lines(c: Cart):
    return [(l.sku, l.qty) for l in c.lines]


@app.get("/catalog")
def catalog():
    return [{"sku": i.sku, "name": i.name, "category": i.category, "unit": i.unit, "list_price": str(i.list_price),
             "ship_mode": i.ship_mode, "stock": i.stock} for i in CATALOG.values()]


@app.post("/price")
def price(c: Cart):
    r = price_cart(_lines(c), _acct(c.account_id), PROMOS)
    return {"tier": r["tier"], "subtotal": str(r["subtotal"]), "savings": str(r["savings"]),
            "lines": [{"sku": p.sku, "qty": p.qty, "unit_price": str(p.unit_price), "line_total": str(p.line_total),
                       "applied": p.applied} for p in r["lines"]]}


@app.post("/quotes")
def create_quote(c: Cart):
    try:
        q = svc.create(_acct(c.account_id), _lines(c))
    except QuoteError as e:
        raise HTTPException(422, str(e))
    return {"quote_id": q.id, "version": q.current.version, "subtotal": str(q.current.subtotal),
            "expires_at": q.expires_at.isoformat()}


@app.put("/quotes/{quote_id}")
def revise_quote(quote_id: str, c: Cart):
    try:
        q = svc.revise(quote_id, _lines(c))
    except QuoteError as e:
        raise HTTPException(422, str(e))
    return {"quote_id": q.id, "version": q.current.version, "subtotal": str(q.current.subtotal)}


@app.get("/quotes/{quote_id}/delivery-windows")
def windows(quote_id: str):
    q = svc.quotes.get(quote_id)
    if not q:
        raise HTTPException(404, "quote not found")
    return [d.isoformat() for d in svc.delivery_windows(q.current.lines)]


@app.post("/quotes/{quote_id}/convert")
def convert(quote_id: str, delivery_date: date):
    try:
        o = svc.convert(quote_id, delivery_date)
    except QuoteError as e:
        raise HTTPException(409, str(e))
    return {"order_id": o.id, "subtotal": str(o.subtotal), "delivery_date": o.delivery_date.isoformat()}


@app.post("/orders/{order_id}/reorder")
def reorder(order_id: str):
    if order_id not in svc.orders:
        raise HTTPException(404, "order not found")
    q = svc.reorder(order_id)
    return {"quote_id": q.id, "subtotal": str(q.current.subtotal)}
