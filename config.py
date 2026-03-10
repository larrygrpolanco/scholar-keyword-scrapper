"""
config.py — Edit this file to customize your keyword search.

This file is shared by all three scripts:
  - scholar_scraper_bs4.py  (Google Scholar)
  - eric_scraper_bs4.py     (ERIC database)
  - cross_reference.py      (combine + deduplicate + score)

HOW IT WORKS
------------
The scrapers search for papers matching:
  ANY of TOPIC_KEYWORDS  AND  ANY of SCOPE_KEYWORDS

RELEVANCE SCORING (used by cross_reference.py)
----------------------------------------------
  High   — 1+ topic match AND 2+ scope matches
  Medium — 2+ topic matches OR 3+ scope matches, OR any topic + scope combo
  Low    — everything else

WILDCARD SUPPORT
----------------
Append * to match word variations:
  "assess*" matches "assessment", "assessing", "assessed", etc.

EXAMPLE CONFIGS
---------------
Climate change research:
  TOPIC_KEYWORDS = ["climate change*", "global warming", "greenhouse gas*"]
  SCOPE_KEYWORDS = ["policy*", "mitigation", "adaptation", "carbon emission*"]

Medical education:
  TOPIC_KEYWORDS = ["medical student*", "clinical training", "residency program*"]
  SCOPE_KEYWORDS = ["simulation", "assessment*", "competency", "feedback"]
"""

# ── YOUR KEYWORDS ──────────────────────────────────────────────────────────────

# The main subject you are researching (who/what)
TOPIC_KEYWORDS = [
    "International teaching assistant*",
    "Foreign teaching assistant*",
    "Non-native teaching assistant*",
]

# The aspect or lens you are focusing on (how/what about it)
SCOPE_KEYWORDS = [
    "speaking assessment*",
    "rubric*",
    "language proficiency",
    "oral proficiency",
    "language assessment",
    "accent assessment",
    "intelligibility assessment",
]
