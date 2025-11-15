#!/usr/bin/env python3
"""
Google Scholar Scraper with Manual CAPTCHA Solving.

This version opens a browser window where YOU can solve CAPTCHAs manually.
The script waits for you to solve them, then continues scraping automatically.

Requirements:
- pip install selenium beautifulsoup4
- Chrome browser installed
- ChromeDriver (will auto-install with webdriver-manager)
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Install with: pip install selenium webdriver-manager beautifulsoup4")
    exit(1)

from bs4 import BeautifulSoup

Paper = Dict[str, Any]

# ==================== CONFIGURATION =====================
ITA_KEYWORDS = [
    "ITA",
    "Foreign teaching assistant*",
    "International teaching assistant*",
    "Non-native teaching assistant*",
]

ASSESSMENT_KEYWORDS = [
    "speaking assessment*",
    "rubric*",
    "language proficiency",
    "oral proficiency",
    "language assessment",
    "accent assessment",
    "intelligibility assessment",
]

DEFAULT_MAX_RESULTS = 1000
DEFAULT_CHUNK_SIZE = 100
DEFAULT_MIN_DELAY = 3.0
DEFAULT_MAX_DELAY = 7.0

CHECKPOINT_PATH = Path("checkpoint.json")
CSV_PATH = Path("scholar_results.csv")
JSON_PATH = Path("scholar_results.json")
REPORT_PATH = Path("scholar_report.txt")

CSV_FIELDS = [
    "number",
    "title",
    "authors",
    "year",
    "venue",
    "citations",
    "abstract",
    "url",
]


def build_query(ita_keywords: List[str], assessment_keywords: List[str]) -> str:
    """Build the search query."""
    ita_terms = " OR ".join([f'"{kw}"' for kw in ita_keywords])
    assessment_terms = " OR ".join([f'"{kw}"' for kw in assessment_keywords])
    return f"({ita_terms}) AND ({assessment_terms}) -Italian -lingua"


def setup_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Set up Chrome WebDriver with options to appear more human-like.
    If headless=False, you'll see the browser window (needed for manual CAPTCHA solving).
    """
    chrome_options = Options()

    if headless:
        chrome_options.add_argument("--headless")

    # Options to avoid detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Remove webdriver property
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


def check_for_captcha(driver: webdriver.Chrome) -> bool:
    """Check if current page has a CAPTCHA."""
    page_source = driver.page_source.lower()
    return (
        "unusual traffic" in page_source
        or "captcha" in page_source
        or "recaptcha" in page_source
    )


def wait_for_captcha_solve(driver: webdriver.Chrome, max_wait: int = 300) -> bool:
    """
    Wait for user to manually solve CAPTCHA.
    Returns True if CAPTCHA was solved, False if timeout.
    """
    print("\n" + "=" * 80)
    print("⚠️  CAPTCHA DETECTED!")
    print("=" * 80)
    print("Please solve the CAPTCHA in the browser window that just opened.")
    print("The script will automatically continue once you solve it.")
    print(f"Maximum wait time: {max_wait} seconds")
    print("=" * 80 + "\n")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        time.sleep(2)
        if not check_for_captcha(driver):
            print("✓ CAPTCHA solved! Continuing...")
            return True

        elapsed = int(time.time() - start_time)
        if elapsed % 10 == 0:
            print(f"  Still waiting... ({elapsed}s elapsed)")

    print("⚠️  Timeout waiting for CAPTCHA to be solved.")
    return False


def fetch_page_with_selenium(
    driver: webdriver.Chrome, query: str, start: int
) -> Optional[BeautifulSoup]:
    """
    Fetch a Google Scholar page using Selenium.
    Handles CAPTCHAs by waiting for user to solve them manually.
    """
    url = f"https://scholar.google.com/scholar?q={query}&hl=en&start={start}"

    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))  # Wait for page to load

        # Check for CAPTCHA
        if check_for_captcha(driver):
            if not wait_for_captcha_solve(driver):
                return None

        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        return soup

    except Exception as e:
        print(f"  ⚠️  Error fetching page: {e}")
        return None


def parse_scholar_result(
    result_div: BeautifulSoup, result_number: int
) -> Optional[Paper]:
    """Parse a single Google Scholar result."""
    try:
        # Extract title
        title_elem = result_div.select_one(".gs_rt")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        title = (
            title.replace("[PDF]", "")
            .replace("[HTML]", "")
            .replace("[BOOK]", "")
            .strip()
        )

        # Extract URL
        link_elem = title_elem.select_one("a")
        url = link_elem["href"] if link_elem and link_elem.has_attr("href") else "N/A"

        # Extract authors, year, venue
        authors_elem = result_div.select_one(".gs_a")
        authors = "N/A"
        year = "N/A"
        venue = "N/A"

        if authors_elem:
            authors_text = authors_elem.get_text(strip=True)
            parts = authors_text.split(" - ")

            if len(parts) >= 1:
                authors = parts[0].strip()

            if len(parts) >= 2:
                venue_year = parts[1].strip()
                import re

                year_match = re.search(r"\b(19|20)\d{2}\b", venue_year)
                if year_match:
                    year = year_match.group(0)
                    venue = venue_year.replace(year, "").strip().rstrip(",").strip()
                else:
                    venue = venue_year

        # Extract abstract
        snippet_elem = result_div.select_one(".gs_rs")
        abstract = snippet_elem.get_text(strip=True) if snippet_elem else "N/A"

        # Extract citations
        citations = 0
        cite_elem = result_div.select_one(".gs_fl a")
        if cite_elem:
            cite_text = cite_elem.get_text(strip=True)
            if "Cited by" in cite_text:
                import re

                cite_match = re.search(r"Cited by (\d+)", cite_text)
                if cite_match:
                    citations = int(cite_match.group(1))

        return {
            "number": result_number,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "citations": citations,
            "abstract": abstract,
            "url": url,
        }
    except Exception as e:
        print(f"  Warning: Failed to parse result {result_number}: {e}")
        return None


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Google Scholar scraper with manual CAPTCHA solving"
    )
    parser.add_argument(
        "--chunk-size",
        "-c",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Papers to fetch per run (default: %(default)s)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=DEFAULT_MIN_DELAY,
        help="Min delay between pages in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=DEFAULT_MAX_DELAY,
        help="Max delay between pages in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help="Maximum total papers (default: %(default)s)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Remove checkpoint and start fresh"
    )
    parser.add_argument(
        "--test", action="store_true", help="Test mode: limit to 10 papers"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (can't solve CAPTCHAs!)",
    )
    return parser.parse_args()


def clear_outputs(paths) -> None:
    """Delete output files."""
    for path in paths:
        try:
            if path.exists():
                path.unlink()
                print(f"Removed: {path}")
        except OSError as e:
            print(f"Warning: could not delete {path}: {e}")


def load_checkpoint(path: Path) -> Optional[Dict[str, Any]]:
    """Load checkpoint from disk."""
    if not path.exists():
        return None
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not load checkpoint: {e}")
        return None


def save_checkpoint(path: Path, checkpoint: Dict[str, Any]) -> None:
    """Save checkpoint to disk."""
    with path.open("w") as f:
        json.dump(checkpoint, f, indent=2)
    print(f"Checkpoint saved: {path}")


def read_json_results(path: Path) -> List[Paper]:
    """Load existing papers from JSON."""
    if not path.exists():
        return []
    try:
        with path.open("r") as f:
            data = json.load(f)
            return data.get("papers", [])
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
        return []


def save_json_results(papers: List[Paper], query: str, path: Path) -> None:
    """Save papers to JSON."""
    payload = {
        "query_info": {
            "search_query": query,
            "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_papers": len(papers),
        },
        "papers": papers,
    }
    with path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def append_to_csv(papers: List[Paper], path: Path) -> None:
    """Append papers to CSV."""
    if not papers:
        return
    should_write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if should_write_header:
            writer.writeheader()
        for paper in papers:
            writer.writerow({field: paper.get(field, "N/A") for field in CSV_FIELDS})
    print(f"Appended {len(papers)} rows to {path}")


def generate_report(papers: List[Paper], query: str, path: Path) -> None:
    """Generate text report."""
    with path.open("w") as f:
        f.write("=" * 80 + "\n")
        f.write("GOOGLE SCHOLAR SEARCH REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"Search Query: {query}\n")
        f.write(f"Total Papers: {len(papers)}\n\n")
        f.write("-" * 80 + "\n")
        for paper in sorted(papers, key=lambda p: p["number"]):
            f.write(f"[{paper['number']}] {paper['title']}\n")
            f.write(f"Authors: {paper['authors']}\n")
            f.write(f"Year: {paper['year']}\n")
            f.write(f"Citations: {paper['citations']}\n\n")
    print(f"Report saved: {path}")


def fetch_chunk(
    driver: webdriver.Chrome,
    query: str,
    start_index: int,
    chunk_size: int,
    min_delay: float,
    max_delay: float,
) -> tuple:
    """Fetch a chunk of papers using Selenium."""
    papers = []
    results_per_page = 10

    start_offset = ((start_index - 1) // results_per_page) * results_per_page
    current_number = start_index
    reached_end = False

    print(f"\n🚀 Fetching {chunk_size} papers starting from #{start_index}...")

    # Calculate pages needed
    pages_needed = (chunk_size // results_per_page) + 1

    for page_num in range(pages_needed):
        if len(papers) >= chunk_size:
            break

        offset = start_offset + (page_num * results_per_page)
        print(
            f"\n📄 Page {page_num + 1} (offset={offset}) - {len(papers)}/{chunk_size} papers collected..."
        )

        soup = fetch_page_with_selenium(driver, query, offset)

        if soup is None:
            print("  ❌ Failed to fetch page")
            reached_end = True
            break

        # Parse results
        results = soup.select(".gs_r.gs_or.gs_scl") or soup.select(".gs_ri")

        if not results:
            print("  ℹ️  No results found. Reached end.")
            reached_end = True
            break

        print(f"  Found {len(results)} results")

        for result_div in results:
            if len(papers) >= chunk_size:
                break

            paper = parse_scholar_result(result_div, current_number)

            if paper is None:
                continue

            papers.append(paper)
            print(
                f"  ✓ [{paper['number']}] {paper['title'][:60]}... ({paper['year']}) - {paper['citations']} cites"
            )
            current_number += 1

        # Delay between pages
        if len(papers) < chunk_size and not reached_end:
            wait_time = random.uniform(min_delay, max_delay)
            print(f"  Waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

    return papers, reached_end


def main():
    args = parse_args()

    if args.test:
        print("*** TEST MODE: 10 papers max ***")
        args.max_results = min(args.max_results, 10)
        args.chunk_size = min(args.chunk_size, 10)

    if args.headless:
        print("⚠️  WARNING: Headless mode enabled. You won't be able to solve CAPTCHAs!")
        print("   Press Ctrl+C to cancel and remove --headless flag.")
        time.sleep(3)

    query = build_query(ITA_KEYWORDS, ASSESSMENT_KEYWORDS)

    print("=" * 80)
    print("GOOGLE SCHOLAR SCRAPER - SELENIUM WITH MANUAL CAPTCHA")
    print("=" * 80)
    print(f"Chunk size: {args.chunk_size}")
    print(f"Max results: {args.max_results}")
    print(f"Delay: {args.min_delay}-{args.max_delay}s")
    print(f"Query: {query}")
    print("=" * 80)

    if args.reset:
        clear_outputs([CHECKPOINT_PATH, CSV_PATH, JSON_PATH, REPORT_PATH])

    # Load checkpoint
    checkpoint = load_checkpoint(CHECKPOINT_PATH)
    existing_papers = read_json_results(JSON_PATH)
    start_index = 1

    if checkpoint and checkpoint.get("query") == query:
        start_index = checkpoint.get("next_index", 1)
        print(f"✓ Resuming from paper #{start_index}")

    if start_index > args.max_results:
        print("Already reached max results!")
        return

    # Set up Selenium
    print("\n🌐 Starting Chrome browser...")
    driver = setup_driver(headless=args.headless)

    try:
        # Fetch chunk
        chunk_size = min(args.chunk_size, args.max_results - start_index + 1)
        new_papers, exhausted = fetch_chunk(
            driver, query, start_index, chunk_size, args.min_delay, args.max_delay
        )

        if not new_papers:
            print("\n⚠️  No papers collected this run")
            return

        # Combine and save
        combined_map = {p["number"]: p for p in existing_papers}
        for p in new_papers:
            combined_map[p["number"]] = p
        combined_papers = [combined_map[n] for n in sorted(combined_map.keys())]

        save_json_results(combined_papers, query, JSON_PATH)
        append_to_csv(new_papers, CSV_PATH)
        generate_report(combined_papers, query, REPORT_PATH)

        # Update checkpoint
        next_index = start_index + len(new_papers)
        checkpoint_data = {
            "query": query,
            "ita_keywords": ITA_KEYWORDS,
            "assessment_keywords": ASSESSMENT_KEYWORDS,
            "chunk_size": args.chunk_size,
            "max_results": args.max_results,
            "next_index": next_index,
            "last_updated": datetime.now().isoformat(),
            "completed": exhausted or next_index > args.max_results,
        }
        save_checkpoint(CHECKPOINT_PATH, checkpoint_data)

        # Summary
        print("\n" + "=" * 80)
        print("SESSION SUMMARY")
        print("=" * 80)
        print(f"New papers: {len(new_papers)}")
        print(f"Total papers: {len(combined_papers)}")
        print(f"Next index: {next_index}")
        print(f"Files: {CSV_PATH}, {JSON_PATH}, {REPORT_PATH}")
        print("=" * 80)

    finally:
        print("\n🛑 Closing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
