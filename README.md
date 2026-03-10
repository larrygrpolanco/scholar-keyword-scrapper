# Academic Literature Scraper

Search Google Scholar and the ERIC database for research papers matching your keywords, then automatically deduplicate and score results by relevance.

Built for researchers who need to do a broad literature sweep across multiple academic databases.

---

## What It Does

1. **`scholar_scraper_bs4.py`** — Searches Google Scholar and saves results (title, authors, year, citations, abstract, URL)
2. **`eric_scraper_bs4.py`** — Searches the [ERIC database](https://eric.ed.gov/) and saves results (same fields + ERIC ID, peer-review status)
3. **`cross_reference.py`** — Combines both result sets, removes duplicates using fuzzy title matching, and labels each paper **High / Medium / Low** relevance

You can run either scraper independently, or run both and combine them.

---

## Requirements

- Python 3.8+
- [Google Chrome](https://www.google.com/chrome/) installed
- ChromeDriver is installed automatically

---

## Installation

```bash
git clone https://github.com/your-username/scholar-keyword-scrapper.git
cd scholar-keyword-scrapper
pip install -r requirements.txt
```

The `requirements.txt` includes:
```
selenium
webdriver-manager
beautifulsoup4
lxml
rapidfuzz
```

---

## Configuration

Open `config.py` and replace the keywords with your own research topic:

```python
# The main subject you are researching (who/what)
TOPIC_KEYWORDS = [
    "International teaching assistant*",
    "Foreign teaching assistant*",
]

# The aspect or lens you are focusing on (how/what about it)
SCOPE_KEYWORDS = [
    "language assessment",
    "oral proficiency",
    "speaking assessment*",
]
```

The scrapers search for papers matching **any** topic keyword **and** any scope keyword.

Append `*` to a keyword to match word variations (`assess*` matches "assessment", "assessing", etc.).

---

## Usage

### Step 1 — Scrape Google Scholar

```bash
python scholar_scraper_bs4.py
```

This opens a Chrome browser window. If Google shows a CAPTCHA, solve it manually — the script will wait and then continue automatically.

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-c`, `--chunk-size` | Papers to collect per run | 500 |
| `-m`, `--max-results` | Total papers to collect | 1000 |
| `--min-delay` | Min seconds between pages | 3.0 |
| `--max-delay` | Max seconds between pages | 7.0 |
| `--reset` | Delete checkpoint and start fresh | — |
| `--test` | Test run (10 papers only) | — |
| `--headless` | Hide browser window (disables CAPTCHA solving) | — |

Run the script multiple times to collect papers in chunks — it resumes automatically from where it left off.

### Step 2 — Scrape ERIC

```bash
python eric_scraper_bs4.py
```

Same usage and flags as the Scholar scraper.

### Step 3 — Combine & Score

```bash
python cross_reference.py
```

Reads `scholar_results.json` and `eric_results.json`, removes duplicates, and scores relevance.

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--threshold` | Fuzzy match % for duplicate detection | 90 |
| `--scholar-json` | Path to Scholar results | `scholar_results.json` |
| `--eric-json` | Path to ERIC results | `eric_results.json` |

---

## Output Files

After running the scrapers, you'll find these files in your working directory:

| File | Contents |
|------|----------|
| `scholar_results.csv` | Scholar papers (spreadsheet) |
| `scholar_results.json` | Scholar papers (structured) |
| `scholar_report.txt` | Scholar papers (readable text) |
| `eric_results.csv` | ERIC papers (spreadsheet) |
| `eric_results.json` | ERIC papers (structured) |
| `eric_report.txt` | ERIC papers (readable text) |
| `combined_results.csv` | All papers, deduplicated + scored |
| `combined_report.txt` | Report organized by relevance |
| `checkpoint.json` | Scholar progress (auto-managed) |
| `eric_checkpoint.json` | ERIC progress (auto-managed) |

### Relevance Scoring

`cross_reference.py` scores each paper based on how well its title and abstract match your keywords:

- **High** — Strong match on both topic and scope terms
- **Medium** — Strong match on one category, or partial match on both
- **Low** — Weak match overall (may still be relevant — check manually)

---

## Tips

**CAPTCHAs:** Google Scholar frequently shows CAPTCHAs during automated browsing. When one appears, solve it in the browser window — the script waits up to 5 minutes. ERIC rarely shows CAPTCHAs.

**Rate limiting:** If you're getting blocked, increase delays:
```bash
python scholar_scraper_bs4.py --min-delay 8 --max-delay 15
```

**Run in chunks:** Collecting 500 papers at a time is safer than running for 1000+ at once. The checkpoint system means you can re-run the script anytime to continue.

**Resuming:** Just re-run the same script — it automatically picks up from the last checkpoint. Use `--reset` to start fresh.

**VPN / network change:** If you get blocked repeatedly, switch networks or wait a few hours before resuming.

---

## Example

See the [`examples/ita_research/`](examples/ita_research/) folder for a complete sample run searching for literature on International Teaching Assistants (ITAs) and language assessment — 500 Scholar papers and 86 ERIC papers collected, combined into 540 unique results.
