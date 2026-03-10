#!/usr/bin/env python3
"""
ERIC Scraper with Manual CAPTCHA Solving.

This version scrapes the ERIC (Education Resources Information Center) database
at https://eric.ed.gov/. Opens a browser window where YOU can solve CAPTCHAs manually.
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
import re
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
# Keywords are loaded from config.py — edit that file to customize your search.
try:
    from config import TOPIC_KEYWORDS as ITA_KEYWORDS, SCOPE_KEYWORDS as ASSESSMENT_KEYWORDS
    # Strip wildcards — ERIC uses exact phrase matching
    ITA_KEYWORDS = [kw.rstrip("*") for kw in ITA_KEYWORDS]
    ASSESSMENT_KEYWORDS = [kw.rstrip("*") for kw in ASSESSMENT_KEYWORDS]
except ImportError:
    # Fallback defaults if config.py is missing
    ITA_KEYWORDS = [
        "Foreign teaching assistant",
        "International teaching assistant",
        "Non-native teaching assistant",
    ]
    ASSESSMENT_KEYWORDS = [
        "speaking assessment",
        "rubric",
        "language proficiency",
        "oral proficiency",
        "language assessment",
        "accent assessment",
        "intelligibility assessment",
    ]

DEFAULT_MAX_RESULTS = 1000
DEFAULT_CHUNK_SIZE = 500  # ERIC shows more results per page
DEFAULT_MIN_DELAY = 2.0
DEFAULT_MAX_DELAY = 5.0

# Different naming scheme to avoid interference with scholar results
CHECKPOINT_PATH = Path("eric_checkpoint.json")
CSV_PATH = Path("eric_results.csv")
JSON_PATH = Path("eric_results.json")
REPORT_PATH = Path("eric_report.txt")

CSV_FIELDS = [
    "number",
    "eric_id",
    "title",
    "authors",
    "year",
    "source",
    "publication_type",
    "peer_reviewed",
    "abstract",
    "descriptors",
    "url",
]


def build_query(ita_keywords: List[str], assessment_keywords: List[str]) -> str:
    """Build the search query for ERIC."""
    # ERIC uses simpler query syntax
    ita_terms = " OR ".join([f'"{kw}"' for kw in ita_keywords])
    assessment_terms = " OR ".join([f'"{kw}"' for kw in assessment_keywords])
    return f"({ita_terms}) AND ({assessment_terms})"


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
    """Check if current page has a CAPTCHA or error."""
    try:
        # Check for actual CAPTCHA elements
        page_source = driver.page_source.lower()

        # More specific checks - look for actual CAPTCHA indicators
        has_recaptcha_frame = len(driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")) > 0
        has_captcha_image = len(driver.find_elements(By.CSS_SELECTOR, "img[src*='captcha']")) > 0

        # Only flag as CAPTCHA if we have strong evidence
        if has_recaptcha_frame or has_captcha_image:
            return True

        # Check for specific error messages (not just the word "captcha" anywhere)
        if "unusual traffic from your computer" in page_source:
            return True
        if "access denied" in page_source and "captcha" in page_source:
            return True

        return False
    except:
        # If we can't check, assume no CAPTCHA
        return False


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
    driver: webdriver.Chrome, query: str, page: int
) -> Optional[BeautifulSoup]:
    """
    Fetch an ERIC page using Selenium.
    Handles CAPTCHAs by waiting for user to solve them manually.
    """
    # ERIC uses page numbers starting from 1
    if page == 1:
        url = f"https://eric.ed.gov/?q={query}"
    else:
        url = f"https://eric.ed.gov/?q={query}&pg={page}"

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


def parse_eric_result(result_elem, result_number: int) -> Optional[Paper]:
    """Parse a single ERIC result."""
    try:
        # Extract ERIC ID from link
        eric_id = "N/A"
        title_link = result_elem.select_one("a[href*='id=']")
        if title_link and title_link.has_attr("href"):
            href = title_link["href"]
            id_match = re.search(r"id=(EJ\d+|ED\d+)", href)
            if id_match:
                eric_id = id_match.group(1)

        # Extract title
        title = "N/A"
        if title_link:
            title = title_link.get_text(strip=True)

        # Build full URL
        url = f"https://eric.ed.gov/?id={eric_id}" if eric_id != "N/A" else "N/A"

        # Extract all text content for parsing
        text_content = result_elem.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]

        # Parse metadata - authors typically follow the title
        authors = "N/A"
        year = "N/A"
        source = "N/A"
        publication_type = "N/A"
        peer_reviewed = False
        abstract = "N/A"
        descriptors = []

        # Check for peer reviewed status
        peer_reviewed_img = result_elem.select_one("img[src*='reviewed']")
        if peer_reviewed_img:
            peer_reviewed = True

        # Try to parse the structured text
        for i, line in enumerate(lines):
            # Look for year (4 digits)
            if re.search(r"\b(19|20)\d{2}\b", line) and year == "N/A":
                year_match = re.search(r"\b(19|20)\d{2}\b", line)
                if year_match:
                    year = year_match.group(0)

            # Source is typically a line with journal/publication name
            if "journal" in line.lower() or "eric" in line.lower():
                source = line

            # Descriptors typically start with "Descriptors:"
            if line.lower().startswith("descriptor"):
                # Collect remaining lines as descriptors
                desc_text = " ".join(lines[i + 1 :])
                descriptors = [d.strip() for d in desc_text.split(",") if d.strip()]
                break

        # Try to find abstract (usually longer text block)
        text_blocks = [line for line in lines if len(line) > 100]
        if text_blocks:
            abstract = text_blocks[0]

        # Authors are typically after title and before year
        if len(lines) > 2:
            for line in lines[1:5]:  # Check first few lines after title
                # Authors typically contain names (has commas or 'and')
                if ("," in line or " and " in line.lower()) and year not in line:
                    authors = line
                    break

        return {
            "number": result_number,
            "eric_id": eric_id,
            "title": title,
            "authors": authors,
            "year": year,
            "source": source,
            "publication_type": publication_type,
            "peer_reviewed": "Yes" if peer_reviewed else "No",
            "abstract": abstract,
            "descriptors": "; ".join(descriptors) if descriptors else "N/A",
            "url": url,
        }

    except Exception as e:
        print(f"  Warning: Failed to parse result {result_number}: {e}")
        return None


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ERIC scraper with manual CAPTCHA solving"
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
            "source": "ERIC (eric.ed.gov)",
        },
        "papers": papers,
    }
    with path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


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


def generate_report(papers: List[Paper], query: str, path: Path) -> None:
    """Generate text report."""
    with path.open("w") as f:
        f.write("=" * 80 + "\n")
        f.write("ERIC SEARCH REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"Search Query: {query}\n")
        f.write(f"Total Papers: {len(papers)}\n")
        f.write(f"Source: ERIC (eric.ed.gov)\n\n")
        f.write("-" * 80 + "\n")
        for paper in sorted(papers, key=lambda p: p["number"]):
            f.write(f"[{paper['number']}] {paper['title']}\n")
            f.write(f"ERIC ID: {paper['eric_id']}\n")
            f.write(f"Authors: {paper['authors']}\n")
            f.write(f"Year: {paper['year']}\n")
            f.write(f"Peer Reviewed: {paper['peer_reviewed']}\n\n")


def fetch_chunk(
    driver: webdriver.Chrome,
    query: str,
    start_page: int,
    chunk_size: int,
    min_delay: float,
    max_delay: float,
) -> tuple:
    """Fetch a chunk of papers using Selenium."""
    papers = []
    results_per_page = 20  # ERIC typically shows ~20 results per page
    current_number = (start_page - 1) * results_per_page + 1
    reached_end = False

    print(f"\nFetching up to {chunk_size} papers starting from page {start_page}...")

    # Calculate pages needed
    pages_needed = (chunk_size // results_per_page) + 1
    current_page = start_page

    for page_offset in range(pages_needed):
        if len(papers) >= chunk_size:
            break

        print(f"\n[Page {current_page}] Progress: {len(papers)}/{chunk_size} papers collected")

        soup = fetch_page_with_selenium(driver, query, current_page)

        if soup is None:
            print("  ERROR: Failed to fetch page")
            reached_end = True
            break

        # Parse results - ERIC uses different HTML structure
        # Results are typically in a list or div structure
        results = soup.select("div.r") or soup.select("div[class*='result']")

        # If above doesn't work, try finding links with ERIC IDs
        if not results:
            # Look for all links with ERIC IDs and get their parent containers
            eric_links = soup.select("a[href*='id=EJ'], a[href*='id=ED']")
            if eric_links:
                # Get unique parent containers
                result_containers = []
                seen = set()
                for link in eric_links:
                    # Go up to find the result container
                    parent = link.find_parent("div") or link.find_parent("li")
                    if parent and id(parent) not in seen:
                        result_containers.append(parent)
                        seen.add(id(parent))
                results = result_containers

        if not results:
            print("  No results found — reached end or parser needs adjustment.")
            reached_end = True
            break

        for result_elem in results:
            if len(papers) >= chunk_size:
                break

            paper = parse_eric_result(result_elem, current_number)

            if paper is None:
                continue

            papers.append(paper)
            print(f"  [{paper['number']:>4}] {paper['title'][:65]}  ({paper['year']}) — {paper['eric_id']}")
            current_number += 1

        current_page += 1

        # Delay between pages
        if len(papers) < chunk_size and not reached_end:
            wait_time = random.uniform(min_delay, max_delay)
            print(f"  Waiting {wait_time:.1f}s before next page...")
            time.sleep(wait_time)

    return papers, reached_end, current_page


def main():
    args = parse_args()

    if args.test:
        print("[TEST MODE] Limiting to 10 papers.")
        args.max_results = min(args.max_results, 10)
        args.chunk_size = min(args.chunk_size, 10)

    if args.headless:
        print("WARNING: Headless mode enabled — you won't be able to solve CAPTCHAs!")
        print("Press Ctrl+C to cancel, then remove the --headless flag.")
        time.sleep(3)

    query = build_query(ITA_KEYWORDS, ASSESSMENT_KEYWORDS)

    print("=" * 60)
    print("ERIC Scraper (eric.ed.gov)")
    print("=" * 60)
    print(f"  Chunk size : {args.chunk_size}")
    print(f"  Max results: {args.max_results}")
    print(f"  Delay      : {args.min_delay}–{args.max_delay}s between pages")
    print(f"  Query      : {query[:80]}{'...' if len(query) > 80 else ''}")
    print("=" * 60)

    if args.reset:
        clear_outputs([CHECKPOINT_PATH, CSV_PATH, JSON_PATH, REPORT_PATH])

    # Load checkpoint
    checkpoint = load_checkpoint(CHECKPOINT_PATH)
    existing_papers = read_json_results(JSON_PATH)
    start_page = 1

    if checkpoint and checkpoint.get("query") == query:
        start_page = checkpoint.get("next_page", 1)
        print(f"Resuming from page {start_page}")

    print("\nStarting Chrome browser...")
    driver = setup_driver(headless=args.headless)

    try:
        # Fetch chunk
        new_papers, exhausted, next_page = fetch_chunk(
            driver, query, start_page, args.chunk_size, args.min_delay, args.max_delay
        )

        if not new_papers:
            print("\nNo papers collected this run.")
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
        done = exhausted or len(combined_papers) >= args.max_results
        checkpoint_data = {
            "query": query,
            "topic_keywords": ITA_KEYWORDS,
            "scope_keywords": ASSESSMENT_KEYWORDS,
            "chunk_size": args.chunk_size,
            "max_results": args.max_results,
            "next_page": next_page,
            "last_updated": datetime.now().isoformat(),
            "completed": done,
        }
        save_checkpoint(CHECKPOINT_PATH, checkpoint_data)

        print("\n" + "=" * 60)
        print("Session Complete")
        print("=" * 60)
        print(f"  New papers this run : {len(new_papers)}")
        print(f"  Total papers saved  : {len(combined_papers)}")
        if done:
            print("  Status              : Search complete!")
        else:
            print(f"  Next run starts at  : page {next_page} (re-run script to continue)")
        print(f"  Output files        : {CSV_PATH}, {JSON_PATH}, {REPORT_PATH}")
        print("=" * 60)

    finally:
        print("\nClosing browser...")
        driver.quit()


if __name__ == "__main__":
    main()
