#!/usr/bin/env python3
"""
Google Scholar Scraper for ITA Language Assessment Research
Searches for papers on International Teaching Assistants and language proficiency assessment.
"""

from scholarly import scholarly
import json
from datetime import datetime
import time

# ==================== CONFIGURATION - EDIT KEYWORDS HERE ====================

# ITA-related keywords
ITA_KEYWORDS = [
    "ITA",
    "Foreign teaching assistant*",
    "International teaching assistant*",
    "Non-native teaching assistant*",
]

# Assessment-related keywords
ASSESSMENT_KEYWORDS = [
    "speaking assessment*",
    "rubric*",
    "language proficiency",
    "oral proficiency",
    "assessment*",
]

# Search settings
MAX_RESULTS = 100  # Maximum number of papers to retrieve
DELAY_SECONDS = 0  # Delay between requests to avoid rate limiting
TEST_MODE = False  # Set to True to only get first 10 results as a test

# ============================================================================


def build_query(ita_keywords, assessment_keywords):
    """
    Build a simple search query from keyword lists.
    Uses a simplified format that works better with scholarly library.
    """
    # Combine all keywords into a single search string
    # Format: (keyword1 OR keyword2) AND (keyword3 OR keyword4)
    ita_terms = " OR ".join([f'"{kw}"' for kw in ita_keywords])
    assessment_terms = " OR ".join([f'"{kw}"' for kw in assessment_keywords])

    query = f"({ita_terms}) AND ({assessment_terms})"
    return query


def search_scholar(query, max_results=2000):
    """
    Search Google Scholar for papers matching the query.

    Args:
        query: Search query string
        max_results: Maximum number of results to retrieve

    Returns:
        List of paper dictionaries with title, authors, year, citations, and abstract
    """
    print(f"Searching Google Scholar...")
    print(f"Query: {query}\n")
    print(f"Target: up to {max_results} results\n")
    print("=" * 80)

    # Try to initiate search with error handling
    try:
        search_query = scholarly.search_pubs(query)
    except Exception as e:
        print(f"\nERROR: Failed to connect to Google Scholar")
        print(f"Details: {e}")
        print("\nPossible solutions:")
        print("1. Check your internet connection")
        print("2. Google Scholar might be blocking requests - try again later")
        print("3. Try using a VPN or proxy")
        return []

    results = []
    print("\nRetrieving papers...\n")

    for i in range(max_results):
        try:
            result = next(search_query)
            paper = {
                "number": i + 1,
                "title": result["bib"].get("title", "N/A"),
                "authors": result["bib"].get("author", "N/A"),
                "year": result["bib"].get("pub_year", "N/A"),
                "venue": result["bib"].get("venue", "N/A"),
                "citations": result.get("num_citations", 0),
                "abstract": result["bib"].get("abstract", "N/A"),
                "url": result.get("pub_url", "N/A"),
            }
            results.append(paper)

            # Show progress every paper
            print(
                f"[{i+1}] {paper['title'][:70]}... ({paper['year']}) - {paper['citations']} citations"
            )

            # Add delay to avoid rate limiting (be respectful to Google Scholar)
            time.sleep(DELAY_SECONDS)

        except StopIteration:
            print(f"\n{'='*80}")
            print(f"Search complete: Found {len(results)} papers total")
            print(f"{'='*80}")
            break
        except Exception as e:
            print(f"Warning: Error retrieving result {i+1}: {e}")
            # Continue trying despite errors
            continue

    return results


def save_results(results, query, filename="scholar_results.json"):
    """Save results to JSON file."""
    output = {
        "query_info": {
            "search_query": query,
            "search_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_papers": len(results),
        },
        "papers": results,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {filename}")


def generate_report(results, query, filename="report.txt"):
    """Generate a simple text report for the paper."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("GOOGLE SCHOLAR SEARCH REPORT\n")
        f.write("ITA Language Assessment Research\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"Search Query: {query}\n")
        f.write(f"Total Papers Found: {len(results)}\n\n")

        f.write("-" * 80 + "\n")
        f.write("PAPERS\n")
        f.write("-" * 80 + "\n\n")

        for paper in results:
            f.write(f"[{paper['number']}] {paper['title']}\n")
            f.write(f"Authors: {paper['authors']}\n")
            f.write(f"Year: {paper['year']}\n")
            f.write(f"Venue: {paper['venue']}\n")
            f.write(f"Citations: {paper['citations']}\n")
            if paper["abstract"] != "N/A":
                f.write(f"Abstract: {paper['abstract']}\n")
            if paper["url"] != "N/A":
                f.write(f"URL: {paper['url']}\n")
            f.write("\n" + "-" * 80 + "\n\n")

    print(f"Report saved to {filename}")


def main():
    """Main function to run the scraper."""

    # Build query from configuration keywords
    query = build_query(ITA_KEYWORDS, ASSESSMENT_KEYWORDS)

    # Determine max results (test mode overrides)
    max_results = 10 if TEST_MODE else MAX_RESULTS

    if TEST_MODE:
        print("*** TEST MODE: Only retrieving first 10 results ***\n")

    # Display configuration
    print("Configuration:")
    print(f"  ITA Keywords: {', '.join(ITA_KEYWORDS)}")
    print(f"  Assessment Keywords: {', '.join(ASSESSMENT_KEYWORDS)}")
    print(f"  Max Results: {max_results}")
    print(f"  Delay: {DELAY_SECONDS} seconds\n")

    # Search and retrieve results
    results = search_scholar(query, max_results=max_results)

    # Save to JSON and generate report
    if results:
        save_results(results, query, "scholar_results.json")
        generate_report(results, query, "scholar_report.txt")

        print(f"\n{'='*80}")
        print(f"FINAL SUMMARY")
        print(f"{'='*80}")
        print(f"Total Papers Found: {len(results)}")
        print(f"Files Generated:")
        print(f"  - scholar_results.json (detailed data)")
        print(f"  - scholar_report.txt (formatted report)")
        print(f"{'='*80}")
    else:
        print("\nNo results found or error occurred.")


if __name__ == "__main__":
    main()
