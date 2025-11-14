#!/usr/bin/env python3
"""
Google Scholar Scraper for ITA Language Assessment Research.

This version fetches search results in configurable chunks, records progress in
a checkpoint file, writes every paper to CSV/JSON outputs, generates a
human-friendly report, and inserts a gentle randomized pause between papers to
stay under Scholar's rate limits. Resume support takes the last saved index so
you can run the script multiple times while only processing a manageable batch
of papers per run.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scholarly import scholarly
from scholarly._proxy_generator import MaxTriesExceededException

Paper = Dict[str, Any]

# ==================== CONFIGURATION - CUSTOMIZE IF NEEDED =====================
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

DEFAULT_MAX_RESULTS = 1000  # Hard cap on the total number of papers collected
DEFAULT_CHUNK_SIZE = 50    # Number of papers to fetch per run
DEFAULT_MIN_DELAY = 0.5     # Minimum pause between fetching consecutive papers (seconds)
DEFAULT_MAX_DELAY = 1.3     # Maximum pause between fetching consecutive papers (seconds)

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


def throttle_between_requests(min_delay: float, max_delay: float) -> None:
    """
    Pause between consecutive fetches to reduce the risk of hitting Scholar rate limits.
    """
    if max_delay <= 0:
        return
    wait_time = random.uniform(min_delay, max_delay) if max_delay > min_delay else min_delay
    time.sleep(wait_time)


# ==============================================================================
def build_query(ita_keywords: List[str], assessment_keywords: List[str]) -> str:
    """
    Build a Google Scholar query that mirrors the user's boolean expression.
    Uses exact phrase matching and excludes Italian language results.
    """
    ita_terms = " OR ".join([f'"{kw}"' for kw in ita_keywords])
    assessment_terms = " OR ".join([f'"{kw}"' for kw in assessment_keywords])
    # Exclude Italian language results to avoid "ITA" being interpreted as Italian
    return f"({ita_terms}) AND ({assessment_terms}) -Italian -lingua"


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """
    Check if text contains any of the keywords (case-insensitive).
    Handles wildcard (*) by checking if keyword prefix appears in text.
    """
    if not text:
        return False
    text_lower = text.lower()
    for kw in keywords:
        if kw.endswith('*'):
            # Wildcard: check if text contains the prefix
            prefix = kw[:-1].lower()
            if prefix in text_lower:
                return True
        else:
            # Check if keyword appears in text (case-insensitive)
            if kw.lower() in text_lower:
                return True
    return False


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments so chunk size, pacing, or reset behavior can be overridden.
    """
    parser = argparse.ArgumentParser(
        description="Chunked Google Scholar scraper for International TA language assessment research."
    )
    parser.add_argument(
        "--chunk-size",
        "-c",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Number of new papers to collect per invocation (default: %(default)s).",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=DEFAULT_MIN_DELAY,
        help="Minimum delay in seconds between Scholar requests (default: %(default)s).",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=DEFAULT_MAX_DELAY,
        help="Maximum delay in seconds between Scholar requests (default: %(default)s).",
    )
    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help="Maximum number of papers to collect in total (default: %(default)s).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing checkpoint and output files before running.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Limit the entire run to 10 papers for quick verification.",
    )
    return parser.parse_args()


def clear_outputs(paths: Iterable[Path]) -> None:
    """
    Delete files so the next run starts fresh. Used when the user passes --reset.
    """
    for path in paths:
        try:
            if path.exists():
                path.unlink()
                print(f"Removed stale file: {path}")
        except OSError as exc:
            print(f"Warning: could not delete {path}: {exc}")


def rotate_path(path: Path) -> None:
    """
    Rename an existing output file (appending a timestamp) before writing new data.
    """
    if not path.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rotated = path.with_name(f"{path.stem}.old-{timestamp}{path.suffix}")
    try:
        path.rename(rotated)
        print(f"Rotated {path.name} to {rotated.name}")
    except OSError as exc:
        print(f"Warning: could not rotate {path.name}: {exc}")


def read_json_results(path: Path) -> List[Paper]:
    """
    Load previously saved papers from the JSON output.
    """
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data.get("papers", [])
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not read {path}: {exc}")
        return []


def save_json_results(papers: List[Paper], query: str, path: Path) -> None:
    """
    Serialize aggregated papers in the familiar JSON format.
    """
    payload = {
        "query_info": {
            "search_query": query,
            "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_papers": len(papers),
        },
        "papers": papers,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    print(f"Saved JSON data to {path}")


def append_to_csv(papers: List[Paper], path: Path) -> None:
    """
    Append newly fetched papers to the CSV file used for manual review.
    """
    if not papers:
        return
    should_write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        if should_write_header:
            writer.writeheader()
        for paper in papers:
            writer.writerow({field: paper.get(field, "N/A") for field in CSV_FIELDS})
    print(f"Appended {len(papers)} rows to {path}")


def generate_report(papers: List[Paper], query: str, path: Path) -> None:
    """
    Emit a lightweight text report summarizing results for quick inspection.
    """
    with path.open("w", encoding="utf-8") as handle:
        handle.write("=" * 80 + "\n")
        handle.write("GOOGLE SCHOLAR SEARCH REPORT\n")
        handle.write("ITA Language Assessment Research\n")
        handle.write("=" * 80 + "\n\n")
        handle.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        handle.write(f"Search Query: {query}\n")
        handle.write(f"Total Papers Found: {len(papers)}\n\n")
        handle.write("-" * 80 + "\n")
        handle.write("PAPERS\n")
        handle.write("-" * 80 + "\n\n")
        for paper in sorted(papers, key=lambda entry: entry["number"]):
            handle.write(f"[{paper['number']}] {paper['title']}\n")
            handle.write(f"Authors: {paper['authors']}\n")
            handle.write(f"Year: {paper['year']}\n")
            handle.write(f"Venue: {paper['venue']}\n")
            handle.write(f"Citations: {paper['citations']}\n")
            if paper["abstract"] != "N/A":
                handle.write(f"Abstract: {paper['abstract']}\n")
            if paper["url"] != "N/A":
                handle.write(f"URL: {paper['url']}\n")
            handle.write("\n" + "-" * 80 + "\n\n")
    print(f"Report saved to {path}")


def load_checkpoint(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load progress metadata from disk if it exists.
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not load checkpoint at {path}: {exc}")
        return None


def save_checkpoint(path: Path, checkpoint: Dict[str, Any]) -> None:
    """
    Persist the current checkpoint so future runs know where to resume.
    """
    with path.open("w", encoding="utf-8") as handle:
        json.dump(checkpoint, handle, indent=2, ensure_ascii=False)
    print(f"Checkpoint updated at {path}")


def is_checkpoint_compatible(
    checkpoint: Optional[Dict[str, Any]],
    query: str,
    chunk_size: int,
    max_results: int,
) -> bool:
    """
    Determine if the stored checkpoint matches the current configuration.
    """
    if checkpoint is None:
        return False
    if checkpoint.get("query") != query:
        print("Keyword expression changed since the last run; will start fresh.")
        return False
    if checkpoint.get("ita_keywords") != ITA_KEYWORDS or checkpoint.get(
        "assessment_keywords"
    ) != ASSESSMENT_KEYWORDS:
        print("Keyword lists were edited; will start a new search.")
        return False
    return True


def fetch_chunk(
    query: str,
    start_index: int,
    end_index: int,
    min_delay: float,
    max_delay: float,
) -> Tuple[List[Paper], int, bool]:
    """
    Walk the Scholar iterator and return only the papers within [start_index, end_index].
    Applies the configured delay between consecutive requests.
    Also filters results client-side to enforce AND logic between ITA and assessment keywords.
    """
    if start_index > end_index:
        return [], start_index - 1, False

    try:
        search_query = scholarly.search_pubs(query)
    except MaxTriesExceededException as exc:
        print(
            "Google Scholar throttling detected before consuming the iterator. "
            "Switch VPN/proxy and retry the same chunk."
        )
        raise exc

    papers: List[Paper] = []
    reached_end = False
    last_index = start_index - 1

    for idx in range(1, end_index + 1):
        try:
            raw = next(search_query)
        except MaxTriesExceededException as exc:
            print(
                f"Google Scholar throttling detected around result {idx}. "
                "Switch VPN/proxy before resuming."
            )
            raise exc
        except StopIteration:
            reached_end = True
            last_index = idx - 1
            break

        if idx < start_index:
            last_index = idx
            continue

        bib = raw.get("bib", {})
        title = bib.get("title", "")
        abstract = bib.get("abstract", "")
        
        # Client-side filtering: enforce AND logic
        # Paper must match BOTH an ITA keyword AND an assessment keyword
        has_ita = _matches_keywords(title + " " + abstract, ITA_KEYWORDS)
        has_assessment = _matches_keywords(title + " " + abstract, ASSESSMENT_KEYWORDS)
        
        if not (has_ita and has_assessment):
            # Skip this result as it doesn't match both keyword sets
            continue
        
        paper = {
            "number": idx,
            "title": title,
            "authors": bib.get("author", "N/A"),
            "year": bib.get("pub_year", "N/A"),
            "venue": bib.get("venue", "N/A"),
            "citations": raw.get("num_citations", 0),
            "abstract": abstract if abstract else "N/A",
            "url": raw.get("pub_url", "N/A"),
        }
        papers.append(paper)
        last_index = idx
        print(
            f"[{paper['number']}] {paper['title'][:80]}... ({paper['year']}) - {paper['citations']} citations"
        )

        if idx < end_index:
            throttle_between_requests(min_delay, max_delay)

    return papers, last_index, reached_end


def main() -> None:
    args = parse_args()

    if args.chunk_size <= 0:
        raise SystemExit("Chunk size must be a positive integer.")
    if args.max_results <= 0:
        raise SystemExit("Max results must be a positive integer.")
    if args.min_delay < 0 or args.max_delay < 0:
        raise SystemExit("Delays must be non-negative.")
    if args.min_delay > args.max_delay:
        raise SystemExit("Minimum delay cannot exceed maximum delay.")

    if args.test:
        print("*** TEST MODE: limiting to 10 total results ***")
        args.max_results = min(args.max_results, 10)
        args.chunk_size = min(args.chunk_size, 10)

    query = build_query(ITA_KEYWORDS, ASSESSMENT_KEYWORDS)
    print("Configuration:")
    print(f"  Chunk size: {args.chunk_size}")
    print(f"  Max results: {args.max_results}")
    print(f"  Delay per paper: {args.min_delay:.2f}-{args.max_delay:.2f} seconds")
    print(f"  Keywords → ITA: {', '.join(ITA_KEYWORDS)}")
    print(f"  Keywords → Assessment: {', '.join(ASSESSMENT_KEYWORDS)}")
    print(f"  Query: {query}")
    print("-" * 80)

    if args.reset:
        clear_outputs((CHECKPOINT_PATH, CSV_PATH, JSON_PATH, REPORT_PATH))

    checkpoint = load_checkpoint(CHECKPOINT_PATH)
    resume = is_checkpoint_compatible(checkpoint, query, args.chunk_size, args.max_results)

    if not resume and checkpoint:
        rotate_path(JSON_PATH)
        rotate_path(CSV_PATH)
        rotate_path(REPORT_PATH)
        try:
            checkpoint.unlink()
            print(f"Removed stale checkpoint at {CHECKPOINT_PATH}")
        except (OSError, AttributeError):
            pass
        checkpoint = None

    existing_papers: List[Paper] = []
    start_index = 1
    if resume:
        existing_papers = read_json_results(JSON_PATH)
        start_index = max(1, checkpoint.get("next_index", 1))
        print(f"Resuming from paper number {start_index}")
    else:
        if JSON_PATH.exists() or CSV_PATH.exists():
            print(
                "NOTE: Outputs from a previous run remain on disk. Use --reset if you want to "
                "discard them before collecting new keywords."
            )

    if start_index > args.max_results:
        print("Maximum result limit already reached according to the checkpoint.")
        return

    remaining = args.max_results - (start_index - 1)
    if remaining <= 0:
        print("No remaining results to collect.")
        return

    chunk_size = min(args.chunk_size, remaining)
    target_end_index = start_index + chunk_size - 1
    print(f"Fetching papers {start_index} through {target_end_index}...")

    new_papers, last_index, exhausted = fetch_chunk(
        query,
        start_index,
        target_end_index,
        args.min_delay,
        args.max_delay,
    )

    combined_map: Dict[int, Paper] = {paper["number"]: paper for paper in existing_papers}
    for paper in new_papers:
        combined_map[paper["number"]] = paper
    combined_papers = [combined_map[number] for number in sorted(combined_map.keys())]

    save_json_results(combined_papers, query, JSON_PATH)
    append_to_csv(new_papers, CSV_PATH)
    generate_report(combined_papers, query, REPORT_PATH)

    next_index = start_index
    if last_index >= start_index:
        next_index = last_index + 1

    completed = exhausted or next_index > args.max_results

    checkpoint_payload = {
        "query": query,
        "ita_keywords": ITA_KEYWORDS,
        "assessment_keywords": ASSESSMENT_KEYWORDS,
        "chunk_size": args.chunk_size,
        "max_results": args.max_results,
        "next_index": next_index,
        "last_updated": datetime.now().isoformat(),
        "completed": completed,
    }
    save_checkpoint(CHECKPOINT_PATH, checkpoint_payload)

    print("\n" + "=" * 80)
    print("SESSION SUMMARY")
    print("=" * 80)
    print(f"New papers fetched this run: {len(new_papers)}")
    print(f"Total papers saved so far: {len(combined_papers)}")
    if completed:
        print("Search marked as complete; no further runs needed unless you reset the checkpoint.")
    else:
        print(f"Resume next time from paper number {next_index}")
    print(f"  CSV output: {CSV_PATH}")
    print(f"  JSON output: {JSON_PATH}")
    print(f"  Report: {REPORT_PATH}")
    print(f"  Checkpoint: {CHECKPOINT_PATH}")
    print("=" * 80)
    print("Re-run the script when you are ready to collect the next chunk of papers.")
    print("=" * 80)


if __name__ == "__main__":
    main()
