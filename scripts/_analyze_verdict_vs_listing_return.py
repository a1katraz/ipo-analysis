import pandas as pd

structured = pd.read_excel("outputs/sptulsian_ipo_articles_structured.xlsx")
returns = pd.read_excel("outputs/sptulsian_ipo_returns.xlsx")

print("structured rows:", len(structured), "| returns rows:", len(returns))
print("verdict counts (raw):")
print(structured["verdict"].value_counts(dropna=False))

merged = structured[["company_name", "ticker", "verdict"]].merge(
    returns[["company_name", "ticker", "ipo_price_higher",
             "close_listing_day", "return_listing_day_pct", "error"]],
    on=["company_name", "ticker"],
    how="inner",
)
print("\nmerged rows:", len(merged))

merged["verdict_norm"] = merged["verdict"].astype(str).str.strip().str.lower()
print("\nverdict_norm counts:")
print(merged["verdict_norm"].value_counts(dropna=False))

valid = merged.dropna(subset=["return_listing_day_pct"]).copy()
print(f"\nrows with valid listing-day return: {len(valid)} / {len(merged)}")

valid["gain_flag"] = valid["return_listing_day_pct"] > 0
valid["flat_flag"] = valid["return_listing_day_pct"] == 0
valid["loss_flag"] = valid["return_listing_day_pct"] < 0


def summarize(group_label: str, sub: pd.DataFrame) -> str:
    if sub.empty:
        return f"{group_label}: no rows"
    n = len(sub)
    mean = sub["return_listing_day_pct"].mean()
    median = sub["return_listing_day_pct"].median()
    gainers = int(sub["gain_flag"].sum())
    losers = int(sub["loss_flag"].sum())
    flats = int(sub["flat_flag"].sum())
    return (
        f"{group_label:>10} | n={n:>3} | mean={mean:+7.2f}% | median={median:+7.2f}% | "
        f"gainers={gainers}/{n} ({gainers/n*100:5.1f}%) | "
        f"losers={losers}/{n} ({losers/n*100:5.1f}%) | flats={flats}"
    )


print("\n--- LISTING-DAY RETURN BY VERDICT ---")
for v in ["positive", "negative", "neutral", "mixed", "subscribe", "avoid"]:
    sub = valid[valid["verdict_norm"] == v]
    if not sub.empty:
        print(summarize(v, sub))

known = {"positive", "negative", "neutral", "mixed", "subscribe", "avoid"}
other = valid[~valid["verdict_norm"].isin(known)]
if not other.empty:
    print(summarize("other", other))
print(summarize("ALL", valid))

print("\n--- POSITIVE VERDICTS - listing-day return distribution ---")
pos = valid[valid["verdict_norm"] == "positive"].sort_values(
    "return_listing_day_pct", ascending=False
)
print(
    pos[
        ["company_name", "ticker", "ipo_price_higher",
         "close_listing_day", "return_listing_day_pct"]
    ].to_string(index=False)
)

print("\n--- NEGATIVE VERDICTS that still gained on listing day (top 10) ---")
neg = valid[valid["verdict_norm"] == "negative"].sort_values(
    "return_listing_day_pct", ascending=False
)
print(
    neg.head(10)[
        ["company_name", "ticker", "ipo_price_higher",
         "close_listing_day", "return_listing_day_pct"]
    ].to_string(index=False)
)

print("\n--- ROBUST VIEW: trim extreme outliers (|return| > 50%) ---")
trimmed = valid[valid["return_listing_day_pct"].abs() <= 50].copy()
print(f"trimmed rows: {len(trimmed)} (dropped {len(valid)-len(trimmed)} extreme rows)")
for v in ["positive", "negative"]:
    sub = trimmed[trimmed["verdict_norm"] == v]
    print(summarize(v, sub))
print(summarize("ALL", trimmed))

print("\n--- 2x2 CONFUSION (verdict vs listing-day gain) ---")
ct = pd.crosstab(
    valid["verdict_norm"],
    valid["return_listing_day_pct"] > 0,
    rownames=["verdict"],
    colnames=["listing_day_gain"],
    margins=True,
)
print(ct)
