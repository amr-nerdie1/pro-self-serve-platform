"""A contractor's journey, end to end:  python demo.py"""
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from proplatform import PROMOS, Account, QuoteError, QuoteService, price_cart, verify_pro  # noqa: E402

fixed_now = lambda: datetime(2026, 10, 15, 9, 0)  # noqa: E731
svc = QuoteService(PROMOS, now=fixed_now)

print("1. Sign up as a Pro")
ridge = Account("A-100", "Ridge Renovations", ein="12-3456789", ttm_spend=48_000)
print("   verification:", verify_pro(ridge))
walkin = Account("A-999", "Weekend DIYer")
print("   no EIN, no licence:", verify_pro(walkin), "-> sees retail prices")

cart = [("FL-OAK-7", 1200), ("TL-POR-24", 300), ("DK-CMP-16", 400)]
print("\n2. Price the cart: Pro vs retail")
for who in (ridge, walkin):
    r = price_cart(cart, who, PROMOS)
    print(f"   {who.name:<18} tier={r['tier']:<7} subtotal=${r['subtotal']:>9,}  savings=${r['savings']:,}")
for p in price_cart(cart, ridge, PROMOS)["lines"]:
    print(f"     {p.sku:<10} {p.qty:>5} @ ${p.unit_price}  {', '.join(p.applied)}")

print("\n3. Contract pricing below the margin floor is clamped and flagged")
harbour = Account("A-200", "Harbour Builders", ein="98-7654321", ttm_spend=160_000,
                  contract_prices={"FL-LVP-12": Decimal("1.69")})
verify_pro(harbour)
r = price_cart([("FL-LVP-12", 2000)], harbour, PROMOS)
print(f"   unit ${r['lines'][0].unit_price}  applied={r['lines'][0].applied}  flags={r['margin_flags']}")

print("\n4. Quote, revise, schedule, convert")
q = svc.create(ridge, cart)
print(f"   {q.id} v{q.current.version} ${q.current.subtotal:,}  expires {q.expires_at:%Y-%m-%d}")
q = svc.revise(q.id, [("FL-OAK-7", 1500), ("TL-POR-24", 300)])
print(f"   {q.id} v{q.current.version} ${q.current.subtotal:,}  (more oak, decking dropped: new version, prior kept)")
slots = svc.delivery_windows(q.current.lines)
print("   delivery windows:", ", ".join(d.strftime("%a %b %d") for d in slots))
o = svc.convert(q.id, slots[1])
print(f"   -> order {o.id} for ${o.subtotal:,}, delivering {o.delivery_date:%a %b %d}")
try:
    svc.convert(q.id, slots[1])
except QuoteError as e:
    print("   converting twice is blocked:", e)

print("\n5. One-click repeat order at today's prices")
rq = svc.reorder(o.id)
print(f"   new quote {rq.id} ${rq.current.subtotal:,}, ready to confirm")
