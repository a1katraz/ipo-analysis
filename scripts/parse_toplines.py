import argparse
import json
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from openai import OpenAI


INPUT_CSV = "outputs/sptulsian_ipo_analysis_index.csv"
OUTPUT_CSV = "outputs/sptulsian_ipo_analysis_parsed.csv"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse IPO toplines from CSV using OpenAI."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Number of rows to process. Omit to process the whole file.",
    )
    return parser.parse_args()


def normalize_date(value: Any) -> str:
    """
    Return date in mm/dd/yyyy format or empty string if unavailable.
    """
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    for fmt in ("%d %b %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return ""


def extract_number(value: Any) -> Optional[float]:
    """
    Extract first numeric value from a string.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", raw)
    if not match:
        return None

    number = match.group(0).replace(",", "")
    try:
        return float(number)
    except ValueError:
        return None


def clean_number(value: Any) -> Optional[float]:
    """
    Pass through numeric values and extract from strings when needed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    return extract_number(value)


def parse_desc_with_llm(client: OpenAI, desc_text: str) -> Dict[str, Any]:
    system_prompt = (
        "You are an expert data extraction assistant.\n"
        "Extract IPO details from text and return ONLY valid JSON with exact keys.\n"
        "Rules:\n"
        "1) nature_of_ipo is the first line of the text.\n"
        "2) Dates must be formatted as mm/dd/yyyy. If missing, use empty string.\n"
        "3) issue_size_crores must be numeric only (no currency text).\n"
        "4) issue_type must be one of: Fresh Issue, Fresh cum OFS, OFS, or empty string.\n"
        "5) ipo_price_lower_end and ipo_price_upper_end must be numeric.\n"
        "   If only one price exists, set both equal.\n"
        "6) overall_subscription_multiple, qib_multiple, hni_multiple, listing_price must be numeric if present.\n"
        "   If missing, set null.\n"
        "7) Do not invent values.\n"
    )

    user_prompt = f"DESC:\n{desc_text}"

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def normalize_record(parsed: Dict[str, Any]) -> Dict[str, Any]:
    lower = clean_number(parsed.get("ipo_price_lower_end"))
    upper = clean_number(parsed.get("ipo_price_upper_end"))
    if lower is not None and upper is None:
        upper = lower
    if upper is not None and lower is None:
        lower = upper

    return {
        "nature_of_ipo": str(parsed.get("nature_of_ipo", "") or "").strip(),
        "subscription_start_date": normalize_date(parsed.get("subscription_start_date")),
        "subscription_end_date": normalize_date(parsed.get("subscription_end_date")),
        "listing_date": normalize_date(parsed.get("listing_date")),
        "issue_size_crores": clean_number(parsed.get("issue_size_crores")),
        "issue_type": str(parsed.get("issue_type", "") or "").strip(),
        "ipo_price_lower_end": lower,
        "ipo_price_upper_end": upper,
        "overall_subscription_multiple": clean_number(parsed.get("overall_subscription_multiple")),
        "qib_multiple": clean_number(parsed.get("qib_multiple")),
        "hni_multiple": clean_number(parsed.get("hni_multiple")),
        "listing_price": clean_number(parsed.get("listing_price")),
    }


def main() -> None:
    args = parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    df = pd.read_csv(INPUT_CSV)
    if args.rows is not None:
        if args.rows <= 0:
            raise ValueError("--rows must be a positive integer.")
        df = df.head(args.rows)

    client = OpenAI()

    output_rows = []
    total = len(df)

    for idx, row in df.iterrows():
        desc = str(row.get("desc", "") or "").strip()
        if not desc:
            continue

        parsed_raw = parse_desc_with_llm(client, desc)
        parsed = normalize_record(parsed_raw)

        output_rows.append(
            {
                "company_name": row.get("company_name", ""),
                "link": row.get("link", ""),
                "desc": desc,
                **parsed,
                "parsed_json": json.dumps(parsed, ensure_ascii=True),
            }
        )
        print(f"Processed {idx + 1}/{total}: {row.get('company_name', '')}")

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved parsed output to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
