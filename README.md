# Scholar Scraper - Selenium

Scrapes Google Scholar with manual CAPTCHA solving. Fetches 50 papers per run, saves progress, resumes automatically.

## Install

```bash
pip install selenium webdriver-manager beautifulsoup4 lxml
```

## Usage

```bash
# Basic - fetch 50 papers
python scholar_scraper_selenium.py

# Resume (automatic)
python scholar_scraper_selenium.py

# Custom chunk size
python scholar_scraper_selenium.py -c 100

# Custom delays (if getting blocked)
python scholar_scraper_selenium.py --min-delay 5 --max-delay 10

# Start fresh
python scholar_scraper_selenium.py --reset

# Test with 10 papers
python scholar_scraper_selenium.py --test
```

## When CAPTCHA Appears

1. Browser window opens
2. Console shows: "⚠️ CAPTCHA DETECTED!"
3. Solve it in the browser
4. Script automatically continues

## Output Files

- `scholar_results.csv` - Spreadsheet
- `scholar_results.json` - Structured data
- `scholar_report.txt` - Text report
- `checkpoint.json` - Progress tracker

## Keywords

Edit these in the script if needed:

```python
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
    "assessment*",
]
```

## Options

```
-c, --chunk-size     Papers per run (default: 50)
-m, --max-results    Total papers to collect (default: 1000)
--min-delay          Min seconds between pages (default: 3.0)
--max-delay          Max seconds between pages (default: 7.0)
--reset              Delete checkpoint and start fresh
--test               Test mode (10 papers only)
--headless           Run invisible browser (won't work with CAPTCHAs)
```

## Tips

- Run 50 papers at a time
- Solve CAPTCHAs quickly when they appear
- If blocked too much, increase delays or wait hours before resuming
- Switch networks/VPN if needed