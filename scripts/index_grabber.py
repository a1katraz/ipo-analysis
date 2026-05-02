import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd


URL = "https://www.sptulsian.com/f/ipo-analysis"
OUTPUT_CSV = "outputs/sptulsian_ipo_analysis_index_all.csv"
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape SPTulsian IPO analysis index."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Number of pages to scrape. Omit to scrape all available pages.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pages is not None and args.pages <= 0:
        raise ValueError("--pages must be a positive integer.")

    df = pd.DataFrame(columns=["company_name", "link", "desc"])
    seen_links = set()
    page = 1
    while args.pages is None or page <= args.pages:
        page_url = URL if page == 1 else f"{URL}?page={page}"
        response = requests.get(
            page_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        divs = soup.select("div.listing-article-class")
        if not divs:
            break

        new_count = 0
        for div in divs:
            title = div.find("h2", class_="font_size_20_article")
            if title is None or title.a is None:
                continue

            company_name = title.get_text(strip=True)
            link = urljoin(URL, title.a.get("href", "").strip())
            if not link or link in seen_links:
                continue

            desc_div = div.find("div", class_="form-group row")
            if desc_div is None:
                continue

            for br in desc_div.find_all("br"):
                br.replace_with("\n")
            desc = desc_div.get_text(strip=True)
            desc = desc.replace("--", "")                               #get rid of the line dashes to save tokens

            df.loc[len(df)] = [company_name, link, desc]
            seen_links.add(link)
            new_count += 1

        print(f"Page {page}: added {new_count} rows")
        if new_count == 0:
            break
        page += 1

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT_CSV}")
    #div = soup.select_one("div.listing-article-class")
    #
    #if div is None:
    #    print("No <div class='listing-article-class'> found.")
    #    return

    # Remove images so image-related content is ignored.
    #for img in div.select("img"):
    #    img.decompose()

    #article_text = " ".join(div.stripped_strings)

    #links = []
    #for a_tag in div.select("a[href]"):
    #    href = urljoin(URL, a_tag.get("href", "").strip())
    #    if href:
    #        links.append(href)

    # Keep unique links while preserving order.
    #seen = set()
    #unique_links = []
    #for link in links:
    #    if link not in seen:
    #        seen.add(link)
    #        unique_links.append(link)

    #print("text | href")
    #print("-" * 120)
    #if unique_links:
    #    for href in unique_links:
    #        print(f"{article_text} | {href}")
    #else:
    #    print(f"{article_text} | ")


if __name__ == "__main__":
    main()
