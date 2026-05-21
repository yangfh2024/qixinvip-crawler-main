# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two independent tools in this repo:

1. **Qixinbao VIP Crawler** (`qixinvip-crawler`) — Playwright-based web scraper for extracting business registration data from qixin.com using VIP cookie authentication. Supports single, batch, and interactive modes with Excel/CSV export.

2. **Reduction Scraper** (`reduction_scraper.py`) — A-share stock reduction announcement reporting system that fetches announcements from cninfo.com.cn, extracts structured fields via regex, merges AKShare real-time market data, and outputs formatted Excel reports.

## Quick Start

```bash
pip install -r requirements.txt           # Qixinbao crawler deps
playwright install chromium               # Browser engine
python main.py                            # Run crawler (config cookie first)
```

For the reduction scraper:
```bash
pip install -r requirements_reduction.txt
python reduction_scraper.py --mode run    # Fetch today's reports
python reduction_scraper.py --mode daemon # Scheduled daemon (daily 21:00)
```

## Key Commands

- `python main.py` — Launch crawler (menu: single/batch/interactive)
- `python test_single.py` — Quick single-company crawl test
- `python test.py` — Run configuration & selector diagnostic tests
- `python reduction_scraper.py --mode run --date YYYY-MM-DD` — Run reduction scraper for a specific date
- `python reduction_scraper.py --mode test` — Test mode with sample data

## Architecture (Qixinbao Crawler)

```
main.py              → Entry point (3 modes: single/batch/interactive)
crawler.py           → QixinbaoCrawler class (search → click → extract pipeline)
browser.py           → BrowserManager (Playwright lifecycle, stealth mode, context)
exporter.py          → ExcelExporter / CSVExporter (pandas-based, factory pattern via get_exporter())
utils.py             → Config loading, cookie parsing, random delays, anti-detection helpers
selectors.json       → Multi-tier CSS selectors per field (fallback chain pattern)
config.json          → Runtime config (delays, browser opts, output format, anti-detection flags)
cookie.txt           → Cookie file (auto-loaded with higher priority than config.json)
```

### Key Design Patterns

- **Fallback selector chains**: Every extracted field has multiple CSS selectors tried in priority order (defined in both `crawler.py` and `selectors.json`). When the site changes its DOM, add new selectors to the front of the list.
- **Anti-detection**: `BrowserManager._init_stealth_mode()` injects JS overrides at context creation to mask Playwright automation signals. Random mouse moves, scrolls, and delays are configurable.
- **New window handling**: `click_first_result_with_page_switch()` detects popup windows from search results and switches to the correct page context.
- **Cookie priority**: `load_config()` reads from `cookie.txt` first (if exists), then falls back to `config.json["cookie"]`.
- **UTF-8 stdout override**: All entry scripts force UTF-8 encoding on stdout to prevent Windows GBK encoding issues.

### Extraction Pipeline (per company)

1. `search_company()` — Navigate to qixin.com, fill search form, wait for results
2. `click_first_result_with_page_switch()` — Click first result, handle new tab
3. `extract_basic_info()` — 9 fields via fallback selector chains
4. `extract_contact_info()` — Phone, email, address (checks VIP lock first)
5. `extract_shareholders()` / `extract_executives()` — Click sub-tabs, parse lists
6. `ExcelExporter.save()` — Write to timestamped `.xlsx`

## Architecture (Reduction Scraper)

`reduction_scraper.py` is a standalone ~1500-line script with:
- **CLI dispatch**: `--mode run|daemon|test`, `--date`, `--pdf` flags
- **cninfo.com.cn API**: Fetches announcement listings and detail pages
- **Regex extraction**: Parses structured fields (reduction ratio, method, price range) from announcement titles and summaries
- **AKShare integration**: Merges real-time market cap and close price per stock
- **Excel output**: Multi-sheet workbook with summary statistics and formatted data
- **Daemon mode**: `schedule` library runs daily at 21:00

## Common Maintenance Tasks

- **Selector update**: Find new CSS selectors via browser DevTools → add to both `crawler.py` field dicts AND `selectors.json`
- **Cookie refresh**: Export cookie from browser extension → paste into `cookie.txt`. The file supports multi-line format with `#` comment lines.
- **Debugging**: Set `headless: false` in config.json to watch browser actions. Failed searches auto-save `search_page_debug.png` screenshots.
- **New data fields**: Add selectors to `crawler.py` extract methods, add column mapping in `exporter.py`, add Chinese label in column_mapping dict.
