#!/usr/bin/env python3
"""
Cross-Reference and Relevance Checker

Combines results from Google Scholar and ERIC, removes duplicates using fuzzy
title matching, and scores relevance (High/Medium/Low) for manual review.

Requirements:
- pip install rapidfuzz
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    print("ERROR: rapidfuzz not installed.")
    print("Install with: pip install rapidfuzz")
    exit(1)

Paper = Dict[str, Any]

# ==================== CONFIGURATION =====================
SCHOLAR_JSON = Path("scholar_results.json")
ERIC_JSON = Path("eric_results.json")

OUTPUT_CSV = Path("combined_results.csv")
OUTPUT_REPORT = Path("combined_report.txt")

FUZZY_THRESHOLD = 90  # 90% similarity for duplicate detection

# Relevance scoring patterns
ITA_PATTERNS = [
    r"\binternational\s+teaching\s+assistant",
    r"\bforeign\s+teaching\s+assistant",
    r"\bnon-native\s+teaching\s+assistant",
    r"\bITAs?\b",
    r"\bFTAs?\b",
    r"\bNNTAs?\b",
]

ASSESSMENT_PATTERNS = [
    r"\bassessment",
    r"\brubrics?\b",
    r"\bevaluation",
    r"\bproficiency",
    r"\bintelligibility",
    r"\baccent",
    r"\bspeaking\s+test",
    r"\boral\s+test",
]

CSV_FIELDS = [
    "source",
    "relevance",
    "title",
    "authors",
    "year",
    "citations_or_peer_reviewed",
    "abstract",
    "url",
    "original_source_id",
]


def load_papers(path: Path, source: str) -> List[Paper]:
    """Load papers from JSON file."""
    if not path.exists():
        print(f"Warning: {path} not found. Skipping {source} papers.")
        return []

    try:
        with path.open("r") as f:
            data = json.load(f)
            papers = data.get("papers", [])
            # Add source identifier
            for paper in papers:
                paper["_source"] = source
            print(f"Loaded {len(papers)} papers from {source}")
            return papers
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return []


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    # Convert to lowercase, remove extra whitespace
    title = title.lower().strip()
    # Remove common prefixes
    title = re.sub(r"^\[pdf\]\s*", "", title)
    title = re.sub(r"^\[html\]\s*", "", title)
    title = re.sub(r"^\[book\]\s*", "", title)
    # Remove punctuation for better matching
    title = re.sub(r"[^\w\s]", " ", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def find_duplicates(papers: List[Paper]) -> List[Tuple[int, int, float]]:
    """
    Find duplicate papers using fuzzy title matching.
    Returns list of (index1, index2, similarity_score) tuples.
    """
    duplicates = []
    normalized_titles = [normalize_title(p.get("title", "")) for p in papers]

    for i in range(len(papers)):
        for j in range(i + 1, len(papers)):
            similarity = fuzz.ratio(normalized_titles[i], normalized_titles[j])
            if similarity >= FUZZY_THRESHOLD:
                duplicates.append((i, j, similarity))

    return duplicates


def calculate_relevance(paper: Paper) -> str:
    """
    Calculate relevance score (High/Medium/Low) based on title and abstract.

    High: Strong matches for both ITA and assessment terms
    Medium: Strong match for one category
    Low: Weak matches overall
    """
    # Combine title and abstract for analysis
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()

    # Count pattern matches
    ita_matches = sum(1 for pattern in ITA_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    assessment_matches = sum(1 for pattern in ASSESSMENT_PATTERNS if re.search(pattern, text, re.IGNORECASE))

    # Scoring logic
    if ita_matches >= 1 and assessment_matches >= 2:
        return "High"
    elif ita_matches >= 2 or assessment_matches >= 3:
        return "Medium"
    elif ita_matches >= 1 or assessment_matches >= 1:
        return "Medium"
    else:
        return "Low"


def merge_duplicates(papers: List[Paper], duplicates: List[Tuple[int, int, float]]) -> List[Paper]:
    """
    Merge duplicate papers, preferring Scholar data but marking source as 'Both'.
    Returns deduplicated list.
    """
    # Track which papers to skip (duplicates)
    skip_indices: Set[int] = set()
    # Track which papers appear in both sources
    merged_papers: List[Paper] = []

    # Build a map of duplicates
    duplicate_map: Dict[int, List[int]] = {}
    for idx1, idx2, _ in duplicates:
        if idx1 not in duplicate_map:
            duplicate_map[idx1] = []
        duplicate_map[idx1].append(idx2)
        skip_indices.add(idx2)

    # Process papers
    for i, paper in enumerate(papers):
        if i in skip_indices:
            continue

        # Check if this paper has duplicates
        if i in duplicate_map:
            duplicate_indices = duplicate_map[i]
            # Check if any duplicate is from a different source
            sources = {paper["_source"]}
            for dup_idx in duplicate_indices:
                sources.add(papers[dup_idx]["_source"])

            # If both sources present, mark as "Both"
            if len(sources) > 1:
                paper["_source"] = "Both"

        merged_papers.append(paper)

    return merged_papers


def normalize_paper_data(paper: Paper) -> Dict[str, Any]:
    """Normalize paper data for consistent output."""
    source = paper.get("_source", "Unknown")

    # Handle citations/peer-reviewed field
    if source == "Scholar" or (source == "Both" and "citations" in paper):
        citations_or_pr = str(paper.get("citations", 0)) + " citations"
    elif source == "ERIC" or (source == "Both" and "peer_reviewed" in paper):
        citations_or_pr = f"Peer reviewed: {paper.get('peer_reviewed', 'N/A')}"
    else:
        citations_or_pr = "N/A"

    # Original source ID
    if "eric_id" in paper:
        original_id = paper.get("eric_id", "N/A")
    else:
        original_id = f"Scholar #{paper.get('number', 'N/A')}"

    return {
        "source": source,
        "relevance": calculate_relevance(paper),
        "title": paper.get("title", "N/A"),
        "authors": paper.get("authors", "N/A"),
        "year": paper.get("year", "N/A"),
        "citations_or_peer_reviewed": citations_or_pr,
        "abstract": paper.get("abstract", "N/A"),
        "url": paper.get("url", "N/A"),
        "original_source_id": original_id,
    }


def save_csv(papers: List[Dict[str, Any]], path: Path) -> None:
    """Save papers to CSV."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(papers)


def generate_report(papers: List[Dict[str, Any]], duplicates_removed: int, path: Path) -> None:
    """Generate text report with statistics and organized sections."""
    # Organize by relevance
    high = [p for p in papers if p["relevance"] == "High"]
    medium = [p for p in papers if p["relevance"] == "Medium"]
    low = [p for p in papers if p["relevance"] == "Low"]

    # Count by source
    scholar_only = [p for p in papers if p["source"] == "Scholar"]
    eric_only = [p for p in papers if p["source"] == "ERIC"]
    both_sources = [p for p in papers if p["source"] == "Both"]

    with path.open("w") as f:
        f.write("=" * 80 + "\n")
        f.write("COMBINED RESULTS REPORT\n")
        f.write("Cross-Reference of Google Scholar and ERIC\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Statistics
        f.write("-" * 80 + "\n")
        f.write("STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total unique papers: {len(papers)}\n")
        f.write(f"Duplicates removed: {duplicates_removed}\n\n")

        f.write(f"By Source:\n")
        f.write(f"  Scholar only: {len(scholar_only)}\n")
        f.write(f"  ERIC only: {len(eric_only)}\n")
        f.write(f"  Both sources: {len(both_sources)}\n\n")

        f.write(f"By Relevance:\n")
        f.write(f"  High: {len(high)}\n")
        f.write(f"  Medium: {len(medium)}\n")
        f.write(f"  Low: {len(low)}\n\n")

        # High relevance papers
        f.write("=" * 80 + "\n")
        f.write(f"HIGH RELEVANCE ({len(high)} papers)\n")
        f.write("=" * 80 + "\n\n")
        for paper in sorted(high, key=lambda p: p["year"], reverse=True):
            f.write(f"[{paper['source']}] {paper['title']}\n")
            f.write(f"  Authors: {paper['authors']}\n")
            f.write(f"  Year: {paper['year']}\n")
            f.write(f"  {paper['citations_or_peer_reviewed']}\n")
            f.write(f"  URL: {paper['url']}\n\n")

        # Medium relevance papers
        f.write("=" * 80 + "\n")
        f.write(f"MEDIUM RELEVANCE ({len(medium)} papers)\n")
        f.write("=" * 80 + "\n\n")
        for paper in sorted(medium, key=lambda p: p["year"], reverse=True):
            f.write(f"[{paper['source']}] {paper['title']}\n")
            f.write(f"  Authors: {paper['authors']}\n")
            f.write(f"  Year: {paper['year']}\n")
            f.write(f"  {paper['citations_or_peer_reviewed']}\n\n")

        # Low relevance papers (condensed)
        f.write("=" * 80 + "\n")
        f.write(f"LOW RELEVANCE ({len(low)} papers)\n")
        f.write("=" * 80 + "\n\n")
        for paper in sorted(low, key=lambda p: p["year"], reverse=True):
            f.write(f"[{paper['source']}] {paper['title']} ({paper['year']})\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Cross-reference Scholar and ERIC results, remove duplicates, score relevance"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=FUZZY_THRESHOLD,
        help=f"Fuzzy match threshold for duplicates (default: {FUZZY_THRESHOLD})",
    )
    parser.add_argument(
        "--scholar-json",
        type=Path,
        default=SCHOLAR_JSON,
        help="Path to Scholar JSON results",
    )
    parser.add_argument(
        "--eric-json",
        type=Path,
        default=ERIC_JSON,
        help="Path to ERIC JSON results",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("Cross-Reference & Relevance Scorer")
    print("=" * 60)
    print(f"  Scholar JSON : {args.scholar_json}")
    print(f"  ERIC JSON    : {args.eric_json}")
    print(f"  Dedup thresh : {args.threshold}% title similarity")
    print("=" * 60)

    # Load papers from both sources
    scholar_papers = load_papers(args.scholar_json, "Scholar")
    eric_papers = load_papers(args.eric_json, "ERIC")

    if not scholar_papers and not eric_papers:
        print("\nERROR: No papers found. Run scholar_scraper_bs4.py and/or eric_scraper_bs4.py first.")
        return

    # Combine, deduplicate, score
    all_papers = scholar_papers + eric_papers
    print(f"\nLoaded {len(all_papers)} total papers ({len(scholar_papers)} Scholar, {len(eric_papers)} ERIC)")

    print("Finding duplicates...")
    duplicates = find_duplicates(all_papers)
    print(f"  {len(duplicates)} duplicate pairs found")

    unique_papers = merge_duplicates(all_papers, duplicates)
    print(f"  {len(unique_papers)} unique papers after deduplication")

    print("Scoring relevance...")
    normalized_papers = [normalize_paper_data(p) for p in unique_papers]

    high = sum(1 for p in normalized_papers if p["relevance"] == "High")
    medium = sum(1 for p in normalized_papers if p["relevance"] == "Medium")
    low = sum(1 for p in normalized_papers if p["relevance"] == "Low")

    save_csv(normalized_papers, OUTPUT_CSV)
    generate_report(normalized_papers, len(duplicates), OUTPUT_REPORT)

    print("\n" + "=" * 60)
    print("Done")
    print("=" * 60)
    print(f"  Unique papers : {len(normalized_papers)}")
    print(f"  Duplicates    : {len(duplicates)} removed")
    print(f"  Relevance     : {high} High / {medium} Medium / {low} Low")
    print(f"  CSV output    : {OUTPUT_CSV}")
    print(f"  Report        : {OUTPUT_REPORT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
