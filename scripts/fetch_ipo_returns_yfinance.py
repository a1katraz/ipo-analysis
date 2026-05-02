import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf


DEFAULT_INPUT_XLSX = "outputs/sptulsian_ipo_articles_structured.xlsx"
DEFAULT_OUTPUT_XLSX = "outputs/sptulsian_ipo_returns.xlsx"

# Trading-day offsets (calendar days). The script searches forward up to a
# small window from each target date to land on the next available trading day.
HORIZON_DAYS = {
    "listing_day": 0,
    "1m": 30,
    "1q": 91,
    "2q": 182,
    "1y": 365,
}

LOOKAHEAD_TRADING_BUFFER_DAYS = 7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch listing-day, 1M, 1Q, 2Q and 1Y closes from Yahoo Finance "
            "and compute returns vs ipo_price_higher."
        )
    )
    parser.add_argument(
        "--input-file",
        default=DEFAULT_INPUT_XLSX,
        help=f"Structured IPO Excel (must contain company_name, listing_date, ipo_price_higher). Default: {DEFAULT_INPUT_XLSX}",
    )
    parser.add_argument(
        "--tickers-file",
        help=(
            "Optional CSV/Excel with columns [company_name, ticker]. "
            "If omitted, the script expects a 'ticker' column in --input-file."
        ),
    )
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_XLSX,
        help=f"Output Excel path (overwritten each run). Default: {DEFAULT_OUTPUT_XLSX}",
    )
    parser.add_argument("--line-number", type=int, help="Single row number (1-based).")
    parser.add_argument("--start-line", type=int, help="Range start row (1-based).")
    parser.add_argument("--end-line", type=int, help="Range end row (1-based).")
    parser.add_argument("--all", action="store_true", help="Process all rows.")
    return parser.parse_args()


def validate_selection_args(args: argparse.Namespace) -> None:
    if args.line_number is not None:
        if args.line_number <= 0:
            raise ValueError("--line-number must be >= 1.")
        if args.start_line is not None or args.end_line is not None or args.all:
            raise ValueError(
                "Use only one selection mode: --line-number OR --start-line/--end-line OR --all."
            )
        return

    if args.start_line is not None or args.end_line is not None:
        if args.all:
            raise ValueError(
                "Use only one selection mode: --line-number OR --start-line/--end-line OR --all."
            )
        if args.start_line is None or args.end_line is None:
            raise ValueError("Both --start-line and --end-line are required for range mode.")
        if args.start_line <= 0 or args.end_line <= 0:
            raise ValueError("--start-line and --end-line must be >= 1.")
        if args.start_line > args.end_line:
            raise ValueError("--start-line must be <= --end-line.")
        return

    if args.all:
        return

    raise ValueError(
        "Please choose one mode: --line-number, --start-line/--end-line, or --all."
    )


def select_rows(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if args.line_number is not None:
        idx = args.line_number - 1
        if idx >= len(df):
            raise ValueError(f"--line-number {args.line_number} exceeds input length {len(df)}.")
        return df.iloc[[idx]].copy()

    if args.start_line is not None and args.end_line is not None:
        start_idx = args.start_line - 1
        end_idx = min(args.end_line - 1, len(df) - 1)
        if start_idx >= len(df):
            raise ValueError(f"--start-line {args.start_line} exceeds input length {len(df)}.")
        return df.iloc[start_idx : end_idx + 1].copy()

    return df.copy()


def parse_listing_date(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        return pd.to_datetime(text).to_pydatetime()
    except Exception:  # noqa: BLE001
        return None


def load_ticker_map(tickers_file: Optional[str]) -> dict[str, str]:
    if not tickers_file:
        return {}
    path = Path(tickers_file)
    if not path.exists():
        raise FileNotFoundError(f"Tickers file not found: {tickers_file}")

    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    required = {"company_name", "ticker"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Tickers file missing required columns: {sorted(missing)}. Expected: company_name, ticker."
        )

    df = df.dropna(subset=["company_name", "ticker"]).copy()
    df["company_name"] = df["company_name"].astype(str).str.strip()
    df["ticker"] = df["ticker"].astype(str).str.strip()
    return dict(zip(df["company_name"], df["ticker"]))


def find_close_on_or_after(
    history: pd.DataFrame,
    target_date: datetime,
    lookahead_days: int = LOOKAHEAD_TRADING_BUFFER_DAYS,
) -> Optional[float]:
    if history.empty:
        return None

    target = pd.Timestamp(target_date.date())
    window_end = target + pd.Timedelta(days=lookahead_days)

    mask = (history.index >= target) & (history.index <= window_end)
    window = history.loc[mask]
    if window.empty:
        return None

    close_value = window.iloc[0]["Close"]
    if pd.isna(close_value):
        return None
    return float(close_value)


def fetch_history(ticker: str, listing_dt: datetime) -> pd.DataFrame:
    # Pad start by 3 days for IPO-day availability and end by ~1.5 months
    # beyond the 1Y horizon to allow lookahead landing on a trading day.
    start = (listing_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    end = (listing_dt + timedelta(days=400)).strftime("%Y-%m-%d")
    hist = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    return hist


def compute_returns_for_row(
    ticker: str, listing_dt: datetime, ipo_price: Optional[float]
) -> dict:
    result: dict = {f"close_{label}": None for label in HORIZON_DAYS}
    result.update({f"return_{label}_pct": None for label in HORIZON_DAYS if label != "listing_day"})
    result["return_listing_day_pct"] = None
    result["error"] = ""

    try:
        history = fetch_history(ticker, listing_dt)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"download failed: {exc}"
        return result

    if history.empty:
        result["error"] = "no price data returned"
        return result

    for label, days in HORIZON_DAYS.items():
        target = listing_dt + timedelta(days=days)
        close = find_close_on_or_after(history, target)
        result[f"close_{label}"] = close
        if close is not None and ipo_price not in (None, 0) and not pd.isna(ipo_price):
            result[f"return_{label}_pct"] = ((close - ipo_price) / ipo_price) * 100.0

    return result


def main() -> None:
    args = parse_args()
    validate_selection_args(args)

    df = pd.read_excel(args.input_file)

    required_columns = {"company_name", "listing_date", "ipo_price_higher"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Input missing required columns: {sorted(missing)}. "
            "Expected at minimum: company_name, listing_date, ipo_price_higher."
        )
    if df.empty:
        print("Input file has no rows.")
        return

    ticker_map = load_ticker_map(args.tickers_file)
    has_inline_ticker = "ticker" in df.columns

    if not ticker_map and not has_inline_ticker:
        raise ValueError(
            "No ticker source found. Either include a 'ticker' column in the input file, "
            "or pass --tickers-file pointing to a CSV/Excel with [company_name, ticker]. "
            "For Indian stocks use suffixes like .NS (NSE) or .BO (BSE), e.g. 'RELIANCE.NS'."
        )

    selected = select_rows(df, args).reset_index(drop=False).rename(columns={"index": "source_index"})
    print(f"Selected {len(selected)} row(s) from {len(df)} total rows.")

    output_rows: list[dict] = []

    for _, row in selected.iterrows():
        source_line = int(row["source_index"]) + 1
        company_name = str(row.get("company_name", "")).strip()
        listing_dt = parse_listing_date(row.get("listing_date"))
        ipo_price_higher = row.get("ipo_price_higher")

        ticker = ""
        if has_inline_ticker:
            inline = row.get("ticker")
            if inline is not None and not (isinstance(inline, float) and math.isnan(inline)):
                ticker = str(inline).strip()
        if not ticker and ticker_map:
            ticker = ticker_map.get(company_name, "").strip()

        print("\n" + "=" * 80)
        print(f"SOURCE_LINE: {source_line}")
        print(f"COMPANY_NAME: {company_name}")
        print(f"TICKER: {ticker or '(missing)'}")
        print(f"LISTING_DATE: {listing_dt.strftime('%m/%d/%Y') if listing_dt else '(missing)'}")
        print(f"IPO_PRICE_HIGHER: {ipo_price_higher}")

        record: dict = {
            "company_name": company_name,
            "ticker": ticker,
            "listing_date": listing_dt.strftime("%m/%d/%Y") if listing_dt else "",
            "ipo_price_higher": ipo_price_higher,
            "close_listing_day": None,
            "return_listing_day_pct": None,
            "close_1m": None,
            "return_1m_pct": None,
            "close_1q": None,
            "return_1q_pct": None,
            "close_2q": None,
            "return_2q_pct": None,
            "close_1y": None,
            "return_1y_pct": None,
            "error": "",
        }

        if not ticker:
            record["error"] = "missing ticker"
            print("ERROR: missing ticker; skipping price fetch.")
            output_rows.append(record)
            continue
        if listing_dt is None:
            record["error"] = "missing/unparseable listing_date"
            print("ERROR: missing/unparseable listing_date; skipping price fetch.")
            output_rows.append(record)
            continue

        try:
            ipo_price_value = float(ipo_price_higher) if ipo_price_higher not in (None, "") else None
        except (TypeError, ValueError):
            ipo_price_value = None

        returns = compute_returns_for_row(ticker, listing_dt, ipo_price_value)
        record.update(returns)

        for label in HORIZON_DAYS:
            close_val = record.get(f"close_{label}")
            ret_val = record.get(f"return_{label}_pct")
            close_str = f"{close_val:.2f}" if isinstance(close_val, (int, float)) else "n/a"
            ret_str = f"{ret_val:+.2f}%" if isinstance(ret_val, (int, float)) else "n/a"
            print(f"{label.upper():>11}: close={close_str:>10}  return={ret_str}")

        if record["error"]:
            print(f"ERROR: {record['error']}")

        output_rows.append(record)

    output_columns = [
        "company_name",
        "ticker",
        "listing_date",
        "ipo_price_higher",
        "close_listing_day",
        "return_listing_day_pct",
        "close_1m",
        "return_1m_pct",
        "close_1q",
        "return_1q_pct",
        "close_2q",
        "return_2q_pct",
        "close_1y",
        "return_1y_pct",
        "error",
    ]
    out_df = pd.DataFrame(output_rows, columns=output_columns)

    output_path = Path(args.output_file)
    if output_path.parent:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_excel(output_path, index=False)
    print(f"\nWrote returns for {len(out_df)} row(s) to: {output_path}")


if __name__ == "__main__":
    main()
