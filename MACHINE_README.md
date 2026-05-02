# MACHINE_README

Runtime / environment guide for `ipo-analysis`. The conceptual "what and why" of
the project lives in `README.md`. This file covers the "how to actually run it on
a machine": Python version, dependencies, environment variables, expected
input/output files, and the order in which to run each script.

---

## 1. Prerequisites

- **Python**: 3.10 or newer (uses `dict[str, Any]` and `X | Y` style typing).
- **OS**: Cross-platform. Tested on Windows (PowerShell). All paths in the
  scripts use forward slashes via `pathlib` / `os` and work on macOS/Linux too.
- **Network**: Outbound HTTPS to:
  - `https://www.sptulsian.com` (article scraping)
  - `https://api.openai.com` (LLM extraction)
  - Yahoo Finance endpoints used by `yfinance`
- **Disk**: A few hundred MB for `outputs/` is plenty.

## 2. Environment variables

| Variable         | Required by                                | Notes                                          |
| ---------------- | ------------------------------------------ | ---------------------------------------------- |
| `OPENAI_API_KEY` | `structure_ipo_articles_with_openai.py`, `parse_toplines.py` | Standard OpenAI key. The scripts hard-fail if missing. |
| `OPENAI_MODEL`   | `parse_toplines.py` (optional)             | Overrides the default `gpt-4o-mini`. The newer `structure_ipo_articles_with_openai.py` uses `--model` instead and defaults to `gpt-4.1-mini`. |

PowerShell:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

bash/zsh:

```bash
export OPENAI_API_KEY="sk-..."
```

## 3. Python dependencies

There is no `requirements.txt` checked in yet. Install the libraries the scripts
import directly:

```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install --upgrade pip
pip install requests beautifulsoup4 pandas openpyxl openai yfinance
```

Per-script breakdown of imports (for reference if you want to slim things down):

| Script                                    | Third-party imports                              |
| ----------------------------------------- | ------------------------------------------------ |
| `grab_blog_list_links.py`                 | `requests`, `beautifulsoup4`, `pandas`           |
| `grab_blog_articles_text.py`              | `requests`, `beautifulsoup4`, `pandas`, `openpyxl` |
| `structure_ipo_articles_with_openai.py`   | `pandas`, `openpyxl`, `openai`                   |
| `fetch_ipo_returns_yfinance.py`           | `pandas`, `openpyxl`, `yfinance`                 |
| `_analyze_verdict_vs_listing_return.py`   | `pandas`, `openpyxl`                             |
| `index_grabber.py` (legacy)               | `requests`, `beautifulsoup4`, `pandas`           |
| `parse_toplines.py` (legacy)              | `pandas`, `openai`                               |

## 4. Directory layout

```
ipo-analysis/
├── README.md                    Conceptual overview (the "why")
├── MACHINE_README.md            This file (the "how")
├── LICENSE
├── .gitignore                   Ignores inputs/ and a few intermediate outputs
├── scripts/                     All pipeline scripts (run from repo root)
└── outputs/                     All generated artefacts land here
```

Always run scripts **from the repository root** (e.g. `python scripts/foo.py`).
Output paths are relative (`outputs/...`), so running from inside `scripts/`
will write to the wrong place.

## 5. The end-to-end pipeline

The four primary stages and their data hand-offs:

```
sptulsian.com  ──[1]──>  blog_list_links.csv
                         │
                         └──[2]──>  articles_text.xlsx
                                    │
                                    └──[3]──>  articles_structured.xlsx
                                               │
                                               ├──[4]──>  ipo_returns.xlsx
                                               │
                                               └──[5]──>  verdict_vs_listing_day_return_analysis.md
```

### Step 1 — Grab article links for a date range

```bash
python scripts/grab_blog_list_links.py --start-date 2024-01-01 --end-date 2024-12-31
```

- **Inputs**: none (scrapes `sptulsian.com/f/ipo-analysis`).
- **Output**: `outputs/sptulsian_ipo_analysis_blog_list_links.csv`
  with columns `text, href, posted_at`.
- **Note**: the script **overwrites** the CSV each run.

### Step 2 — Fetch article text + metadata

```bash
# Process every link
python scripts/grab_blog_articles_text.py --all

# Or just one row (1-based) for debugging
python scripts/grab_blog_articles_text.py --line-number 5

# Or a slice
python scripts/grab_blog_articles_text.py --start-line 1 --end-line 50
```

- **Input**: `outputs/sptulsian_ipo_analysis_blog_list_links.csv`
  (override with `--links-file`).
- **Output**: `outputs/sptulsian_ipo_articles_text.xlsx`
  with columns `company_name, link, mini_desc, article_text`.
- **Important — append behaviour**: if the output file already exists, this
  script **appends** new rows to the `articles` sheet. Delete the file (or pass
  `--output-file` to a fresh path) if you want a clean run, otherwise you will
  end up with duplicates.

### Step 3 — LLM-structure the articles into fields

```bash
python scripts/structure_ipo_articles_with_openai.py --all
# Optional: pick a different model
python scripts/structure_ipo_articles_with_openai.py --all --model gpt-4.1-mini
```

- **Input**: `outputs/sptulsian_ipo_articles_text.xlsx`.
- **Output**: `outputs/sptulsian_ipo_articles_structured.xlsx`
  (overwritten every run).
- **Schema produced** (one row per article, see the script for the strict JSON
  schema): `company_name, ipo_start_date, ipo_end_date, issue_size_in_cr,
  issue_type, ipo_price_lower, ipo_price_higher, listing_date, fund_usage,
  ind_segment_guess, eval_params, eval_args, risk_factors, pricing_params,
  pricing_args, comp_fin_ratios, verdict`.
- **Cost note**: every row = one OpenAI chat completion. Use `--line-number`
  or `--start-line/--end-line` while iterating on prompts.
- **Note**: `verdict` is constrained to `positive` / `negative` only; the
  downstream analyser also handles `neutral / mixed / subscribe / avoid` if you
  ever loosen the schema.

### Step 4 — Fetch listing-day & follow-on returns from Yahoo Finance

This step needs ticker symbols, which the structured output does not contain.
Provide them via either:

a. an inline `ticker` column on the structured Excel, or
b. a separate ticker-map file with columns `[company_name, ticker]`. The repo
   ships `outputs/ticker_names.xlsx` for this.

Indian stocks need a Yahoo suffix: `.NS` (NSE) or `.BO` (BSE), e.g.
`RELIANCE.NS`.

```bash
python scripts/fetch_ipo_returns_yfinance.py \
  --all \
  --tickers-file outputs/ticker_names.xlsx
```

- **Input**: `outputs/sptulsian_ipo_articles_structured.xlsx`
  (must contain `company_name, listing_date, ipo_price_higher`).
- **Output**: `outputs/sptulsian_ipo_returns.xlsx` (overwritten each run).
- **Horizons**: listing day, 1m (30d), 1q (91d), 2q (182d), 1y (365d).
  Each target date is rolled forward by up to 7 calendar days to land on the
  next trading day. Returns are computed against `ipo_price_higher`.

### Step 5 — Verdict-vs-return summary

```bash
python scripts/_analyze_verdict_vs_listing_return.py
```

- **Inputs**: both `sptulsian_ipo_articles_structured.xlsx` and
  `sptulsian_ipo_returns.xlsx`.
- **Output**: prints to stdout. The committed
  `outputs/verdict_vs_listing_day_return_analysis.md` is a hand-saved snapshot
  of a previous run — redirect or copy-paste if you want to refresh it:

  ```bash
  python scripts/_analyze_verdict_vs_listing_return.py > outputs/verdict_vs_listing_day_return_analysis.md
  ```
- **Caveat**: the merge inside this script joins on
  `["company_name", "ticker"]`. The structured output produced by step 3 does
  **not** include a `ticker` column on its own — make sure the structured Excel
  has a `ticker` column merged in (e.g. by joining `ticker_names.xlsx` into it)
  before running this analysis, otherwise the inner-join will be empty.

## 6. Legacy / auxiliary scripts

These are not part of the current pipeline but live in `scripts/` and are kept
for reference:

- **`index_grabber.py`** — older paginated scraper. Writes to
  `outputs/sptulsian_ipo_analysis_index_all.csv` (gitignored).
- **`parse_toplines.py`** — older LLM parser that reads
  `outputs/sptulsian_ipo_analysis_index.csv` (gitignored) and writes
  `outputs/sptulsian_ipo_analysis_parsed.csv`. Uses `gpt-4o-mini` by default
  via the `OPENAI_MODEL` env var. Superseded by
  `structure_ipo_articles_with_openai.py`.
- **`scripts/analysis_headers.txt`** — plaintext copy of the extraction spec
  used to build the schema in `structure_ipo_articles_with_openai.py`.

## 7. Files that are gitignored

From `.gitignore`:

- `inputs/` — local-only inputs.
- `outputs/sptulsian_ipo_analysis.csv`
- `outputs/sptulsian_ipo_analysis_index.csv`
- `outputs/sptulsian_ipo_analysis_index_all.csv`
- `outputs/sptulsian_ipo_analysis_parsed.csv`
- `outputs/sptulsian_ipo_articles_structured_v1.xlsx`
- `outputs/sptulsian_ipo_articles_text_orig.xlsx`
- `scripts/__pycache__/`

So if a downstream script complains about a missing input that is not in this
repo, check whether it's a gitignored intermediate that needs to be regenerated
by an earlier step.

## 8. Common gotchas

- **Step 2 appends.** Re-running step 2 without deleting
  `sptulsian_ipo_articles_text.xlsx` will produce duplicate rows on the
  `articles` sheet.
- **`OPENAI_API_KEY` not visible to the script.** On Windows, setting it in one
  PowerShell tab does not propagate to other tabs. Set it in the same shell
  you use to run the script, or persist it via `setx OPENAI_API_KEY ...` (new
  shells only).
- **Yahoo tickers for Indian listings need `.NS` / `.BO`.** Without the
  suffix, `yfinance` will silently return empty history and you'll get rows
  with `error = "no price data returned"`.
- **Run from repo root.** The relative `outputs/...` paths assume the cwd is
  the repository root.
- **Date format mismatch.** The LLM step emits `mm/dd/yyyy`. The yfinance step
  also accepts `yyyy-mm-dd`, `dd/mm/yyyy`, `dd-mm-yyyy` as fallbacks, but if
  you hand-edit dates in Excel, double-check that Excel hasn't auto-converted
  them to a locale-specific format.

## 9. Quickstart (full pipeline)

```bash
# one-time setup
python -m venv .venv
.venv\Scripts\Activate.ps1                 # or: source .venv/bin/activate
pip install requests beautifulsoup4 pandas openpyxl openai yfinance
$env:OPENAI_API_KEY = "sk-..."             # or: export OPENAI_API_KEY=...

# run the pipeline (from repo root)
python scripts/grab_blog_list_links.py --start-date 2024-01-01 --end-date 2024-12-31
del outputs\sptulsian_ipo_articles_text.xlsx 2>$null   # avoid append duplicates
python scripts/grab_blog_articles_text.py --all
python scripts/structure_ipo_articles_with_openai.py --all
python scripts/fetch_ipo_returns_yfinance.py --all --tickers-file outputs/ticker_names.xlsx
python scripts/_analyze_verdict_vs_listing_return.py
```
