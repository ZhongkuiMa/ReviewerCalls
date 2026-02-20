# Contributing to ReviewerCalls

## Adding a Reviewer Call

1. Check the [curated list](https://ZhongkuiMa.github.io/ReviewerCalls/) to avoid duplicates
2. Verify the URL is an official self-nomination page (not just a CFP)
3. Either:
   - **Open an Issue** using the [Candidate template](../../issues/new/choose)
   - **Submit a PR** editing `data/calls.yaml` directly

### What Qualifies

A page qualifies only if it explicitly invites individuals to apply or nominate themselves for:
- Reviewer / External Reviewer
- Program Committee (PC)
- Senior Program Committee (SPC)
- Area Chair (AC) / Senior Area Chair (SAC)
- Artifact Evaluation Committee (AEC)
- Emergency Reviewer

**Out of scope:** invitation-only calls, chair-nominated processes, private or login-required pages.

### PR Format for `data/calls.yaml`

Entries are ordered by date descending (newest first).

```yaml
calls:
  - conference: AAAI          # Must match short name in data/conferences.yaml
    year: 2026
    role: Reviewer             # One of: Reviewer, External Reviewer, PC, SPC, AC, SAC, AEC, Emergency Reviewer
    url: "https://..."         # Official self-nomination page
    label: Main                # Main, Workshop, Industry, or Shadow/Junior
    date: "2026-01-10"         # Page creation/publication date (YYYY-MM-DD)
    confirmed: true            # true = verified by human, false = auto-discovered
```

Multiple entries for the same conference/role are allowed when there are separate pages (e.g., main conference vs. workshops). Use `label` to distinguish them.

### Handling Multi-Round Conferences

- Prefer the main "Call for Nominations" page that covers all rounds
- If no main page exists, link to the first round's nomination page
- Avoid creating separate entries for each round of the same conference/year

---

## Local Development

### Setup

```bash
git clone https://github.com/ZhongkuiMa/ReviewerCalls.git
cd ReviewerCalls

conda env create -f environment.yaml
conda activate reviewercalls

pip install -e ".[dev]"
```

### Common Tasks

```bash
# Run tests
pytest tests/ -v

# Lint and format
ruff check .
ruff format .

# Run discovery (dry run: no file writes or GitHub ops)
python -m discover --dry-run

# Run discovery with filters
python -m discover --area AI --rank A
python -m discover --conference IJCAI
python -m discover --dry-run --limit 5

# Use Serper search provider
python -m discover --search-provider serper --serper-key YOUR_KEY

# Validate candidates using LLM (filters false positives)
python -m validate --dry-run
python -m validate --log-level DEBUG
python -m validate --apply  # Actually apply results

# Build and preview website locally
python -m build
python -m http.server -d docs 8000
# Visit http://localhost:8000
```

### CLI Options

**discover:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Skip file writes and GitHub operations | off |
| `--init` | Initialize database (search past year) | off |
| `--search-provider` | Search engine (`duckduckgo` or `serper`) | `duckduckgo` |
| `--serper-key` | Serper API key ([serper.dev](https://serper.dev), 2500 free/month) | - |
| `--repo` | GitHub repository in `owner/repo` format | - |
| `--date-range` | Search date range: `d`, `w`, `m`, `y`, `none` | `m` |
| `--conference` | Filter by conference short name | - |
| `--rank` | Filter by CCF rank (A, B, C) | - |
| `--area` | Filter by area code (AI, SE, etc.) | - |
| `--limit` | Max conferences to search | - |
| `--max-links` | Max links to explore from homepage | 15 |

DuckDuckGo is free but rate-limited (~1s/query). Serper is faster with 2500 free searches/month.

**validate:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview results without writing to files | off |
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `-q, --quiet` | Suppress output | off |

**build:**

| Option | Description | Default |
|--------|-------------|---------|
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `-q, --quiet` | Suppress output | off |

---

## Project Structure

```
ReviewerCalls/
├── data/
│   ├── conferences.yaml          321 CCF/CORE conferences (from ccfddl)
│   ├── calls.yaml                Curated reviewer calls
│   ├── calls.yaml.backup         Auto-created backup
│   └── rejected_urls.yaml        False positives (auto-cleaned monthly)
├── discover/                     Discovery system
│   ├── __main__.py               Entry point (python -m discover)
│   ├── main.py                   CLI parsing + orchestrator
│   ├── config.py                 Runtime settings
│   ├── constants.py              Keywords, patterns, regex
│   ├── pipeline.py               4-step pipeline (search, explore L1/L2, analyze)
│   ├── search.py                 DuckDuckGo/Serper abstraction
│   ├── batch.py                  Async parallel HTTP
│   ├── data.py                   YAML I/O and data management
│   ├── filters.py                Link filtering by domain/text/patterns
│   ├── validators.py             Content validation + false positive filtering
│   ├── parsers.py                HTML link extraction
│   ├── http.py                   HTTP client
│   ├── github.py                 GitHub issue creation via gh CLI
│   └── utils.py                  URL normalization and utilities
├── validate/                     LLM-powered validator
│   ├── __main__.py               Entry point (python -m validate)
│   ├── config.py                 Configuration loader
│   ├── config.yaml.template      Template for Ollama setup
│   ├── client.py                 Ollama client with SSH tunnel
│   ├── fetcher.py                URL fetching and text extraction
│   ├── prompt.py                 LLM prompt builders
│   └── validator.py              Main validation pipeline
├── build/                        Site builder
│   ├── __main__.py               Entry point (python -m build)
│   └── main.py                   YAML → JSON for website
├── docs/                         Static website (GitHub Pages)
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   ├── calls.json                Generated by python -m build
│   └── conferences.json          Generated by python -m build
├── tests/                        Test suite
│   ├── test_discover.py          Discovery workflow tests
│   ├── test_discovery_steps.py   Pipeline step tests
│   ├── test_discovery_args.py    CLI argument tests
│   ├── test_validators.py        Content validator tests
│   ├── test_constants.py         Keyword and pattern tests
│   ├── test_integration.py       End-to-end tests
│   ├── test_build.py             Site builder tests
│   ├── test_validate.py          LLM validator tests
│   ├── test_data_manager.py      Data I/O tests
│   ├── test_date_extractor.py    Date extraction tests
│   ├── test_github_issue.py      GitHub integration tests
│   ├── test_batch_processor.py   Async HTTP tests
│   ├── test_link_filter.py       Link filtering tests
│   ├── test_link_scorer.py       Link scoring tests
│   ├── test_html_parser.py       HTML parsing tests
│   ├── test_url_utils.py         URL utility tests
│   └── test_helpers.py           Helper function tests
├── pyproject.toml
├── environment.yaml
└── .pre-commit-config.yaml
```

## Architecture

The discovery system follows a clean 4-step pipeline:

```
Conference list (data/conferences.yaml)
  → Filter by recruitment window (2-10 months before conf_date)
  → For each conference:
      Step 1: Search for homepage + reviewer pages (DuckDuckGo/Serper)
      Step 2: Extract links from homepage + subdirectories
      Step 3: Follow promising links one level deeper
      Step 4: Analyze content (keywords, positive signals, date extraction)
  → Deduplicate against existing calls.yaml
  → Write candidates (confirmed: false) + create GitHub Issues
```

### Import Conventions

```python
# CORRECT (after pip install -e .)
from discover import config
from discover.data import load_confs
from discover.filters import has_promising_keywords

# WRONG (don't use sys.path hacks)
import sys; sys.path.insert(0, "scripts")
```

---

## GitHub Actions Workflows

### Discover Reviewer Calls (`.github/workflows/discover.yaml`)

Runs weekly (Monday 08:00 UTC). Searches conferences in recruitment window, creates GitHub Issues with "candidate" label. Manual trigger available via the Actions tab.

### Validate (`.github/workflows/validate.yaml`)

Runs on PRs to main. Lints with Ruff and runs the test suite.

### Deploy Site (`.github/workflows/deploy.yaml`)

Runs on push to main when `data/calls.yaml`, `docs/**`, or `build/**` change. Builds JSON and deploys to GitHub Pages.

---

## Maintainer Workflow

```
Discovery (automated, weekly)
  → Searches conferences via DuckDuckGo/Serper
  → Writes candidates to data/calls.yaml with confirmed: false
  → Creates GitHub Issues labeled "candidate"

Validation (optional, automated)
  → Filters false positives using Ollama LLM
  → Binary classification: is this a reviewer call? yes/no
  → Moves invalid entries to rejected_urls.yaml
  → Reduces manual review burden

Triage (manual)
  → Review remaining unconfirmed Issues
  → For verified calls: edit data/calls.yaml, set confirmed: true
  → Close Issue

Deploy (automated)
  → Push to main triggers website rebuild
  → Only confirmed: true entries appear on the site
```
