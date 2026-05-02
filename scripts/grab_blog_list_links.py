import argparse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd

URL = "https://www.sptulsian.com/f/ipo-analysis"
TOOLTIP_DT_FORMAT = "%d %b %Y at %I:%M %p"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grab IPO analysis links within a date range."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD format (inclusive).",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD format (inclusive).",
    )
    return parser.parse_args()


def parse_cli_date(value: str, field_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def main() -> None:
    args = parse_args()
    start_date = parse_cli_date(args.start_date, "--start-date")
    # Include the full day for end-date filtering.
    end_date = parse_cli_date(args.end_date, "--end-date").replace(
        hour=23, minute=59, second=59
    )
    if start_date > end_date:
        raise ValueError("--start-date must be before or equal to --end-date.")

    response = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    df = pd.DataFrame(columns=["text", "href", "posted_at"])

    soup = BeautifulSoup(response.text, "html.parser")
    container = soup.select_one("div.create_blog_article_box.well.text-justify")
    if container is None:
        print("Container div not found.")
        return

    ul_tag = container.find("ul")
    if ul_tag is None:
        print("No <ul> found inside container.")
        return

    li_main_tags = ul_tag.find_all("li", class_="col-lg-12 col-md-12 col-sm-12 row")
    if not li_main_tags:
        print("No <li> items found.")
        return

    li_date_tags = ul_tag.find_all("li", class_="padding-bottom-10")
    if not li_date_tags:
        print("No <li> items found.")
        return
    
    result_index = 1
    for li, li_date in zip(li_main_tags, li_date_tags):

        a_tag = li.find("a", href=True)
        if a_tag is None:
            continue

        date_span = li_date.find("span", attrs={"title": True})

        art_date = (
            (date_span.get("title") if date_span else "") or ""
        ).strip()

        if not art_date:
            continue
        try:
            posted_at = datetime.strptime(art_date, TOOLTIP_DT_FORMAT)
        except ValueError:
            continue
        if not (start_date <= posted_at <= end_date):
            continue

        #print(li.text, li_date.text)
        
        text = a_tag.get_text(" ", strip=True)
        href = urljoin(URL, a_tag["href"].strip())
        #print(f"{result_index}. {text} | {href} | {posted_at}")
        df.loc[len(df)] = [text, href, posted_at]
        #result_index += 1

    df.to_csv("outputs/sptulsian_ipo_analysis_blog_list_links.csv", index=False)

if __name__ == "__main__":
    main()
