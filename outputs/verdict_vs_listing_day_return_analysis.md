# Verdict vs Listing-Day Return — Analysis

**Question:** Do IPOs with a **positive** verdict (per the SP Tulsian framework) deliver a listing-day gain when bought at `ipo_price_higher`?

**Short answer:** **No** — positive verdicts did *not* reliably deliver listing-day gains. The bucket actually had a **lower hit rate** than the negative bucket, although it had a higher mean (driven by a few outsized winners).

---

## Data sources

- **Verdict source:** `outputs/sptulsian_ipo_articles_structured.xlsx` (column: `verdict`)
- **Returns source:** `outputs/sptulsian_ipo_returns.xlsx` (columns: `close_listing_day`, `return_listing_day_pct`)
- **Join keys:** `company_name` + `ticker`
- **Universe:** 98 IPOs total · 93 had valid listing-day returns (5 missing price data)
- **Verdict split:** 37 positive, 61 negative (matches the framework's stated 37% positive base rate)

---

## Headline numbers

| Bucket | n | Gainers | Hit rate | Mean return | Median return |
|---|---|---|---|---|---|
| **Positive verdict** | 35 | 18 | **51.4%** | +9.62% | +2.25% |
| **Negative verdict** | 58 | 34 | **58.6%** | +1.48% | +1.04% |
| All | 93 | 52 | 55.9% | +4.55% | +1.11% |

### 2x2 confusion matrix

| verdict \ listing_day_gain | Loss | Gain | Total |
|---|---|---|---|
| Negative | 24 | 34 | 58 |
| Positive | 17 | 18 | 35 |
| **Total** | **41** | **52** | **93** |

---

## Robust view (excluding `|return| > 50%` outliers)

7 extreme rows trimmed.

| Bucket | n | Hit rate | Mean | Median |
|---|---|---|---|---|
| Positive | 32 | 50.0% | +8.78% | +0.89% |
| Negative | 54 | 57.4% | −0.43% | +0.82% |
| All | 86 | 54.7% | +3.00% | +0.82% |

---

## Key observations

1. **Hit-rate inversion.** A coin flip is ~50%. Positive verdicts hit gain only **51.4%** of the time, while negative verdicts hit gain **58.6%** — i.e., the verdict signal has effectively **no edge for predicting listing-day direction**, and is mildly contrarian on hit-rate.
2. **Mean is misleading.** The positive-bucket mean of **+9.62%** is propped up by a handful of big pops:
   - Highway Infra +72.5%, Meesho +53.2%, LG +48.2%, Jain Recycling +37.1%, Corona Remedies +35.4%, Groww +31.3%, Sudeep +30.5%, Sri Lotus +30.4%, Rubicon +29.5%, Regaal +29.0%, Anthem +28.1%
   - Strip outliers and the mean drops to **+8.78%** and median to a meek **+0.89%**.
3. **Negative verdicts pop frequently too.** Some of the largest listing-day pops in the dataset come from "negative" calls:
   - Bharat Coking Coal +76.4%, Urban Company +62.0%, Aditya Infotech +60.4%, PhysicsWallah +42.4%, GNG Electronics +40.7%, Tenneco +23.6%, Pine Labs +13.5%
   - Exactly what you'd expect when GMP / hype / scarcity overrides fundamentals on day one.
4. **Data caveat — ICICI Prudential.** Row shows IPO price ₹2165 → close ₹650 (−70%), which is almost certainly an LLM extraction error (real 2016 band was ₹300–334). Worth re-running through the structuring step or filtering out before publishing any final view.

---

## Why this makes sense

The Tulsian framework is built around **valuation, fundamentals, and long-term capital protection**, not short-term listing-day momentum. Listing-day price is overwhelmingly driven by:

- Grey market premium
- Allotment scarcity
- Subscription frenzy / retail sentiment

…none of which the framework optimises for. A *negative* verdict says **"this IPO is overpriced relative to fundamentals"**, not **"this won't pop on day one."**

The real test of the framework is the **1-month, 1-quarter, 2-quarter, and 1-year** horizons, where overpriced IPOs typically mean-revert and well-priced ones compound. Those columns currently sit empty in `sptulsian_ipo_returns.xlsx` because most IPOs in the dataset are too recent — re-running the returns script later will close that loop.

---

## Reproducibility

- Analysis script (one-off): `scripts/_analyze_verdict_vs_listing_return.py`
- Inputs: `outputs/sptulsian_ipo_articles_structured.xlsx`, `outputs/sptulsian_ipo_returns.xlsx`
- Run: `python scripts/_analyze_verdict_vs_listing_return.py`

---

*Snapshot generated 2026-04-29 from the current state of the structured + returns files. Re-run after long-horizon (`1m`, `1q`, `2q`, `1y`) data matures for a more meaningful framework backtest.*
