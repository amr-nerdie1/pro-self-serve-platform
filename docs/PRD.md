# PRD: Pro self-serve ordering

**Author:** Amrisha Rajkhowa, Senior PM · **Status:** shipped in three 4-week increments
**Context:** online building-materials marketplace (flooring, decking, tile) with a growing B2B "Pro" segment. This repo is a clean-room reference implementation; the figures in *Results* are from the original launch.

## 1. Problem
Pros (contractors, renovators, builders) placed most orders by **phone**: a sales rep quoted manually, negotiated price, and keyed the order. The website was capable, but it showed Pros the same prices as retail shoppers and had no quotes, repeat ordering or delivery scheduling. Phone ordering capped Pro growth and tied sales reps up in transactions instead of accounts.

## 2. Who we're building for
| Persona | Job to be done | Today's pain |
|---|---|---|
| **Small contractor** (1–5 crew) | Price a job fast, order the same materials job after job | Waits for a callback to get "Pro pricing"; re-keys the same order every job |
| **Mid-size builder** (procurement person) | Get approved pricing, hold a quote while the client decides, book delivery to site | Quotes in email threads, no expiry or versions; delivery booked by phone |
| **Sales rep** (internal) | Spend time on accounts, not data entry | Most of the day is quoting and order entry |
| **Category / vendor manager** (internal) | Protect margin | Fears published Pro prices will undercut negotiated deals |

**Discovery:** contextual interviews with Pros and sales reps, a Pro survey, web analytics, and affinity mapping of findings. Two junior PMs ran discovery sessions with me.

**Top three needs:** (1) automated quotes, (2) tiered Pro pricing without negotiating, (3) easy repeat orders with delivery scheduling.

## 3. Goals and metrics
| | Metric | Why |
|---|---|---|
| **North star** | Share of Pro revenue ordered online | The behaviour change we need |
| Input | Quote-to-order conversion | Are quotes trusted enough to act on? |
| Input | Repeat-order rate (Pro) | Is reordering really one click? |
| Input | Scheduled-delivery uptake | Does self-serve cover the whole job? |
| **Guardrail** | Lines priced below margin floor (must be 0) | Vendor-manager trust |
| Guardrail | Checkout payment failures | No regressions in the money path |

## 4. Scope by increment
| Increment (4 wks) | Ships | User value |
|---|---|---|
| **1. Pro pricing** | Pro verification (EIN auto-check + licence review queue) · tiers by trailing spend · volume breaks · contract prices · margin floor with flagging | "I see my price without calling" |
| **2. Quotes** | Versioned quotes with 30-day expiry · revise · convert with stock + price re-validation · delivery windows by ship mode | "I can hold a quote for my client and book site delivery" |
| **3. Repeat & scale** | One-click reorder at today's prices · order history · rep dashboards | "Same job, same order, two clicks" |

**Out of scope (v1):** credit terms, project-level billing, mobile app.

## 5. Key requirements and decisions
1. **Unverified = retail.** Pro prices only after verification. This answered Marketing's concern that anyone could sign up as a "Pro".
2. **Pricing precedence:** contract → tier → volume break → promotions (exclusive promos compete, best price wins; stackable promos only for verified Pros; none on contract lines).
3. **Margin floor:** no line below cost × (1 + category floor). Breaches are clamped **and flagged** to the category manager. This was the condition for vendor managers to approve publishing Pro prices.
4. **Money is exact:** decimal arithmetic, half-up rounding once per line, totals equal the sum of lines. (A rounding mismatch between systems had caused payment failures before.)
5. **Quotes are their own service**, not draft orders in the OMS: they need versions and expiry, and draft writes would compete with live orders under OMS rate limits. The OMS is called only at conversion.
6. **Conversion re-validates**: expired → re-quote; price moved > 2% → re-quote; stock short → block.

## 6. Risks
| Risk | Mitigation |
|---|---|
| Margin erosion from published Pro prices | Margin floor + flags; tier discounts set with Finance |
| Non-Pros getting Pro prices | Verification gate; manual review queue for licences |
| Reps feel replaced | Reps own accounts and contract prices; dashboards show their accounts' online orders |
| Low adoption | Sales-led onboarding, demos, webinars, in-product guides |

## 7. Go-to-market
Sales Enablement and Marketing: rep training, Pro webinars, product demos, support guides, targeted email to high-value Pros.

## 8. Results (original launch, within six weeks)
- **Online Pro sales +25%**
- **Repeat orders +18%**
- **Scheduled-delivery uptake +30%**
- **Pro segment revenue +12% year over year**
- Both junior PMs went on to lead follow-on work (mobile UX, advanced reporting).
