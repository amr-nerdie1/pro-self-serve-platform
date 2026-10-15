# Pro self-serve platform

> Contractors were ordering by phone because the website couldn't give them a Pro price, a quote they could hold, or a delivery date. This is the platform that moved them online.

A clean-room reference implementation, **on synthetic data**, of a B2B self-serve platform I led as Senior PM at an online building-materials marketplace. The original launch, within six weeks:

| Online Pro sales | Repeat orders | Scheduled deliveries | Pro revenue (YoY) |
|---|---|---|---|
| **+25%** | **+18%** | **+30%** | **+12%** |

Start with the **[PRD](docs/PRD.md)**: problem, personas, metrics, increments, decisions and risks. The code shows the decisions working.

## What's in it

| Capability | Where | The product decision behind it |
|---|---|---|
| **Pro verification** | `catalog.verify_pro` | EIN auto-check, licence to a review queue. Unverified accounts see retail prices, which answered "anyone can sign up as a Pro" |
| **Tiered pricing** | `pricing.py` | Bronze / Silver / Gold by trailing spend, plus volume breaks. No phone negotiation |
| **Contract prices** | `pricing.py` | Rep-negotiated deals still win, and promos never stack on them |
| **Promo rules** | `pricing.py` | Exclusive promos compete with Pro pricing (best price wins); stackable Pro-only promos add on |
| **Margin floor** | `pricing.py` | No line below cost × (1 + floor). Breaches are clamped **and flagged**: the condition for vendor managers to approve published Pro prices |
| **Exact money** | `pricing.money` | Decimal, half-up, once per line; totals = sum of lines. A rounding mismatch between systems once failed real payments |
| **Quotes** | `quotes.py` | A separate service: versions, 30-day expiry, revise. The OMS is touched only at conversion |
| **Safe conversion** | `QuoteService.convert` | Re-checks expiry, stock and price (>2% move → re-quote) before writing the order |
| **Delivery windows** | `QuoteService.delivery_windows` | Weekday slots after the slowest line's lead time (LTL 4 days, parcel 2) |
| **One-click reorder** | `QuoteService.reorder` | Same lines, today's prices, ready to confirm |
| **API** | `api.py` | FastAPI: `/price`, `/quotes`, `/quotes/{id}/convert`, `/orders/{id}/reorder` |

## A contractor's journey

```
1. Sign up as a Pro
   verification: verified
   no EIN, no licence: rejected -> sees retail prices

2. Price the cart: Pro vs retail
   Ridge Renovations  tier=silver  subtotal=$ 6,576.00  savings=$1,113.00
   Weekend DIYer      tier=retail  subtotal=$ 6,921.00  savings=$768.00
     FL-OAK-7    1200 @ $3.57  promo:SPRING15, promo:PRO2
     TL-POR-24    300 @ $2.84  tier:silver, promo:PRO2
     DK-CMP-16    400 @ $3.60  tier:silver, promo:PRO2

3. Contract pricing below the margin floor is clamped and flagged
   unit $1.81  applied=['contract', 'floor-clamped']  flags=['FL-LVP-12']

4. Quote, revise, schedule, convert
   Q-1001 v1 $6,576.00  expires 2026-11-14
   Q-1001 v2 $6,207.00  (more oak, decking dropped: new version, prior kept)
   delivery windows: Wed Oct 21, Thu Oct 22, Fri Oct 23, Mon Oct 26, Tue Oct 27
   -> order O-1002 for $6,207.00, delivering Thu Oct 22
   converting twice is blocked: quote already converted

5. One-click repeat order at today's prices
   new quote Q-1003 $6,207.00, ready to confirm
```

## Run it

```bash
pip install -r requirements.txt
python demo.py                                   # the journey above
pytest -q                                        # 15 tests: tiers, promo rules, margin floor, rounding, quote lifecycle, API
PYTHONPATH=src uvicorn proplatform.api:app --reload   # then open http://127.0.0.1:8000/docs
```

## Design notes
- **Guardrails over approvals.** The margin floor lets the business publish prices without approving each one.
- **Re-validate at the moment of commitment.** A quote is a promise with an expiry; conversion is where stock and price get checked again.
- **Ship value every four weeks.** Pricing first (biggest pain), then quotes, then repeat ordering. See the PRD.

---
**Amrisha Rajkhowa** · Product & analytics leader · [LinkedIn](https://ca.linkedin.com/in/amrisha-rajkhowa-ubc) · more: [sku-profitability-agent](https://github.com/amr-nerdie1/sku-profitability-agent) · [bayesian-bid-pricing](https://github.com/amr-nerdie1/bayesian-bid-pricing)
