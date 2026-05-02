import argparse
import json
import os
from typing import Any

import pandas as pd
from openai import OpenAI


DEFAULT_INPUT_XLSX = "outputs/sptulsian_ipo_articles_text.xlsx"
DEFAULT_OUTPUT_XLSX = "outputs/sptulsian_ipo_articles_structured.xlsx"
DEFAULT_MODEL = "gpt-4.1-mini"


JSON_SCHEMA: dict[str, Any] = {
    "name": "ipo_article_structured_output",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ipo_start_date": {"type": "string"},
            "ipo_end_date": {"type": "string"},
            "issue_size_in_cr": {"type": "number"},
            "issue_type": {
                "type": "string",
                "enum": ["Fresh Issue", "Fresh cum OFS", "OFS", "none"],
            },
            "ipo_price_lower": {"type": "number"},
            "ipo_price_higher": {"type": "number"},
            "listing_date": {"type": "string"},
            "fund_usage": {"type": "string"},
            "ind_segment_guess": {"type": "string"},
            "eval_params": {"type": "array", "items": {"type": "string"}},
            "eval_args": {"type": "array", "items": {"type": "string"}},
            "risk_factors": {"type": "array", "items": {"type": "string"}},
            "pricing_params": {"type": "array", "items": {"type": "string"}},
            "pricing_args": {"type": "array", "items": {"type": "string"}},
            "comp_fin_ratios": {"type": "array", "items": {"type": "string"}},
            "verdict": {"type": "string", "enum": ["positive", "negative"]}
        },
        "required": [
            "ipo_start_date",
            "ipo_end_date",
            "issue_size_in_cr",
            "issue_type",
            "ipo_price_lower",
            "ipo_price_higher",
            "listing_date",
            "fund_usage",
            "ind_segment_guess",
            "eval_params",
            "eval_args",
            "risk_factors",
            "pricing_params",
            "pricing_args",
            "comp_fin_ratios",
            "verdict",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured IPO fields from article text using OpenAI."
    )
    parser.add_argument(
        "--input-file",
        default=DEFAULT_INPUT_XLSX,
        help=f"Input Excel path. Default: {DEFAULT_INPUT_XLSX}",
    )
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_XLSX,
        help=f"Output Excel path (overwritten each run). Default: {DEFAULT_OUTPUT_XLSX}",
    )
    parser.add_argument("--line-number", type=int, help="Single row number (1-based).")
    parser.add_argument(
        "--start-line",
        type=int,
        help="Start row number (1-based, inclusive) for range mode.",
    )
    parser.add_argument(
        "--end-line",
        type=int,
        help="End row number (1-based, inclusive) for range mode.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all rows from input Excel.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use. Default: {DEFAULT_MODEL}",
    )
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
        end_idx = args.end_line - 1
        if start_idx >= len(df):
            raise ValueError(f"--start-line {args.start_line} exceeds input length {len(df)}.")
        end_idx = min(end_idx, len(df) - 1)
        return df.iloc[start_idx : end_idx + 1].copy()

    return df.copy()


def build_prompt(mini_desc: str, article_text: str) -> str:
    return f"""You are an IPO analyst data extraction engine.

Read the provided text and return ONLY valid JSON that strictly matches the schema.

Rules:
- Dates must be in mm/dd/yyyy format. If unknown, use empty string.
- issue_size_in_cr must be numeric. If unknown, use 0.
- issue_type must be one of: Fresh Issue | Fresh cum OFS | OFS | none.
- ipo_price_lower and ipo_price_higher must be numeric. If only one price is found, set both to that value. If unknown, use 0.
- Lists must contain concise string points. If none, return [].
- Do not include markdown or explanations.

Extraction Process from mini_desc:
a. IPO subscription start date in mm/dd/yyyy format (ipo_start_date)
b. IPO subscription end date in  mm/dd/yyyy format (ipo_end_date)
c. Issue size in  Crores as a number, no cr symbol needed (issue_size_in_cr)
d. issue type: Fresh Issue | Fresh cum OFS | OFS | none (issue_type)
e. price band lower in number format (ipo_price_lower)
f. price band upper in number format, if it does not exist, use the same value as pioce band lower (ipo_price_higher)

Extraction process from article_text:
a. find the listing date as mm/dd/yyyy (listing_date)
b. find the usage of the funds as text blob (fund_usage)
c. find the industry segment of the company on best guess basis (ind_segment_guess)
d. understand the financial parameters being used in the article, ignoring their values, for company evaluation and give this as a list ([eval_params])
e. understand the arguments made in the article to adjudge the correctness of these financial parameters as a list ([eval_args])
f. find the associated risk factors in the ipo as a list ([risk_factors])
g. understand the factors used to adjudge the pricing of the ipo as a list ([pricing_params])
h. evaluation arguments made to adjudge if the pricing is  okay as a list ([pricing_args])
i. if any comparators are used, find the financial ratios compared as a list ([comp_fin_ratios])
j. give the investment verdict as positive or negative based on the article text sentiment (verdict)

mini_desc:
{mini_desc}

article_text:
{article_text}
"""


def extract_structured_json(
    client: OpenAI, model: str, mini_desc: str, article_text: str
) -> dict[str, Any]:
    prompt = build_prompt(mini_desc=mini_desc, article_text=article_text)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return only strict JSON matching the supplied schema.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_schema", "json_schema": JSON_SCHEMA},
        temperature=0,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content.")
    return json.loads(content)


def main() -> None:
    args = parse_args()
    validate_selection_args(args)

    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    df = pd.read_excel(args.input_file)
    required_columns = {"company_name", "mini_desc", "article_text"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in input file: {sorted(missing)}. "
            "Expected: company_name, mini_desc, article_text."
        )
    if df.empty:
        print("Input file has no rows.")
        return

    selected = select_rows(df, args).reset_index(drop=False).rename(columns={"index": "source_index"})
    print(f"Selected {len(selected)} row(s) from {len(df)} total rows.")

    client = OpenAI()
    output_rows: list[dict[str, Any]] = []

    for _, row in selected.iterrows():
        source_line = int(row["source_index"]) + 1
        company_name = str(row.get("company_name", "")).strip()
        mini_desc = str(row.get("mini_desc", "")).strip()
        article_text = str(row.get("article_text", "")).strip()

        print("\n" + "=" * 80)
        print(f"SOURCE_LINE: {source_line}")
        print(f"COMPANY_NAME: {company_name}")
        try:
            parsed = extract_structured_json(
                client=client,
                model=args.model,
                mini_desc=mini_desc,
                article_text=article_text,
            )
        except Exception as exc:  # noqa: BLE001 - continue processing other rows.
            print(f"ERROR: Failed to parse row: {exc}")
            continue

        output_rows.append({"company_name": company_name, **parsed})
        print("PARSE_STATUS: success")
        print("=" * 80)

    output_columns = [
        "company_name",
        "ipo_start_date",
        "ipo_end_date",
        "issue_size_in_cr",
        "issue_type",
        "ipo_price_lower",
        "ipo_price_higher",
        "listing_date",
        "fund_usage",
        "ind_segment_guess",
        "eval_params",
        "eval_args",
        "risk_factors",
        "pricing_params",
        "pricing_args",
        "comp_fin_ratios",
        "verdict",
    ]
    out_df = pd.DataFrame(output_rows, columns=output_columns)
    list_columns = [
        "eval_params",
        "eval_args",
        "risk_factors",
        "pricing_params",
        "pricing_args",
        "comp_fin_ratios"
    ]
    for col in list_columns:
        out_df[col] = out_df[col].apply(lambda v: json.dumps(v, ensure_ascii=True))
    out_df.to_excel(args.output_file, index=False)
    print(f"\nWrote {len(out_df)} parsed row(s) to: {args.output_file}")


if __name__ == "__main__":
    main()
