# Google Scholar Keyword Scraper

Simple Python script to scrape Google Scholar for papers on International Teaching Assistants (ITA) and language proficiency assessment.

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

1. **Edit keywords** in `scrape_scholar.py` (lines 15-29):
   - Add/remove ITA-related terms
   - Add/remove assessment-related terms

2. **Run the script**:
   ```bash
   python scrape_scholar.py
   ```

3. **Get results**:
   - View progress in terminal
   - Final count of papers found
   - Two output files with detailed information

## Configuration (Edit at Top of Script)

All settings are in the configuration section at the top of `scrape_scholar.py`:

```python
# ITA-related keywords
ITA_KEYWORDS = [
    "ITA",
    "Foreign teaching assistant",
    "International teaching assistant",
    "Non-native teaching assistant",
]

# Assessment-related keywords
ASSESSMENT_KEYWORDS = [
    "speaking assessment",
    "rubric",
    "language proficiency",
    "oral proficiency",
    "assessment",
]

# Search settings
MAX_RESULTS = 2000      # Maximum papers to retrieve
DELAY_SECONDS = 2       # Delay between requests
TEST_MODE = False       # Set True for quick 10-result test
```

## Test Mode

Before running a full search, you can test with just 10 results:

1. Set `TEST_MODE = True` in the script
2. Run: `python scrape_scholar.py`
3. Check if results are what you expect
4. Set `TEST_MODE = False` for full search

## Output Files

- **scholar_results.json**: Complete data in JSON format with search query and metadata
- **scholar_report.txt**: Human-readable report with all paper details

Each paper includes:
- Title
- Authors
- Year
- Venue/Publication
- Citation count
- Abstract
- URL (when available)

## Important Notes

- **Rate Limiting**: Script includes 2-second delay between requests to avoid blocking
- **Search Syntax**: Uses simplified query format optimized for scholarly library
- **Error Handling**: Will show helpful messages if Google Scholar blocks requests
- **Progress**: Shows each paper as it's retrieved with running count

## Customization Examples

### Change keywords:
```python
ITA_KEYWORDS = ["International TA", "Foreign TA"]
ASSESSMENT_KEYWORDS = ["language test", "proficiency exam"]
```

### Adjust speed/safety:
```python
DELAY_SECONDS = 3  # Slower, safer
# or
DELAY_SECONDS = 1  # Faster, riskier
```

### Limit results:
```python
MAX_RESULTS = 50  # Only get first 50 papers
```
