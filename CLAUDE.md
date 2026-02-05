# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit web application that creates a "Death Race" dashboard comparing Letterboxd viewing statistics between two users. It scrapes Letterboxd profile and diary pages to analyze viewing patterns, streaks, ratings, and provide visualizations.

## Development Setup

### Environment Setup
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
streamlit run streamlit_app.py
```

### Code Quality Tools

Run pre-commit hooks (includes formatting, linting, and style checks):
```bash
pre-commit run --all-files
```

Individual linting/formatting:
```bash
# Formatting with black
black src/ streamlit_app.py

# Linting with ruff
ruff check --fix src/ streamlit_app.py

# Type checking with mypy
mypy src/ streamlit_app.py --config=setup.cfg

# Linting with flake8
flake8 src/ streamlit_app.py --config=setup.cfg

# Docstring style checking
pydocstyle src/ streamlit_app.py --config=setup.cfg
```

## Architecture

### Component Responsibilities

**`LetterboxdManager` (src/letterboxd_manager.py)**
- Core scraping engine for a single user
- Fetches and parses Letterboxd profile and diary HTML pages
- Responsible for all data extraction logic (film counts, ratings, streaks, diary entries)
- Calculates derived statistics (viewing rate, weekly counts, highlights)
- Handles pagination when scraping diary pages
- **Note:** Contains commented-out code for loading from local HTML fixtures (useful for testing without hitting Letterboxd servers)

**`DeathRaceManager` (src/death_race_manager.py)**
- Orchestrates comparison between two users
- Manages two `LetterboxdManager` instances
- Implements comparative analytics (gap calculation, projections, catch-up estimates)
- Handles all Streamlit UI rendering and visualization
- Creates plots (accumulated movies chart, Venn diagram)
- Computes cross-user statistics (common films, average ratings)

**`models.py`**
- Dataclass definitions for typed data structures
- `FilmCount`: total and yearly film counts
- `WeeklyFilmCount`: last week vs this week comparison
- `FilmStreak`: current and longest viewing streaks
- `DiaryEntry`: individual film entry with date, title, year, rating

**`utils.py`**
- Utility functions (currently only `rating_to_stars()` for converting 0-10 ratings to star symbols)

**`streamlit_app.py`**
- Entry point that instantiates `DeathRaceManager` and calls `main()`
- Currently hardcoded to compare "unnonuene" vs "garciamorales"

### Data Flow

1. `streamlit_app.py` creates a `DeathRaceManager` with two usernames
2. `DeathRaceManager.__init__()` creates two `LetterboxdManager` instances
3. Each `LetterboxdManager` immediately:
   - Fetches profile HTML (scrapes `https://letterboxd.com/{user}/`)
   - Fetches all diary pages for current year (scrapes `https://letterboxd.com/{user}/films/diary/for/{year}/page/{n}/`)
   - Parses HTML to extract film counts, diary entries, streaks, ratings
   - Calculates viewing rate and weekly counts
4. `DeathRaceManager.main()` orchestrates Streamlit UI, calling various section methods to render comparisons

### Web Scraping Strategy

The scraper uses `cloudscraper` to bypass Cloudflare's bot protection and relies on specific HTML structure from Letterboxd:

- **Profile page**: Uses `div.profile-stats` → `h4.profile-statistic` to extract film counts
- **Diary pages**: Parses `tr.diary-entry-row` elements, extracting:
  - Date from `td.col-daydate` anchor href: `/user/diary/films/for/YYYY/MM/DD/`
  - Title from `h2` element inside `td.col-production`
  - Release year from `td.col-releaseyear`
  - Rating from `input.rateit-field` value (0-10 scale), or None if `not-rated` class present
- **Pagination**: Continues fetching pages until no `a.next` link found or `paginate-disabled` class detected

**Critical Notes:**
- Uses `cloudscraper` library to bypass Cloudflare bot detection
- **Must create a fresh scraper instance for each diary page** to avoid 403 errors (Cloudflare tracks and blocks scraper sessions)
- URL format: `https://letterboxd.com/{user}/diary/films/for/{year}/page/{page_num}/` (note: `diary/films`, not `films/diary`)
- If Letterboxd changes their HTML structure, the scrapers will break. The commented-out fixture loading code and saved fixtures in `src/new_fixtures/` are useful for debugging scraping issues.

## Key Implementation Details

### Streak Calculation
Streaks count consecutive days with at least one diary entry. The algorithm sorts entries by date and tracks gaps between consecutive dates. A 1-day gap continues the streak; larger gaps reset it.

### Rate Projection
Viewing rate is calculated as `films_this_year / day_of_year`. This rate is then multiplied by 365 (or 366 for leap years) to project end-of-year total.

### Gap Analysis
The `calculate_gap()` method not only shows current difference but also estimates "days to catch up" if the trailing user has a higher viewing rate than the leader.

### Common Films
The `top_common_by_avg_rating()` method identifies films both users have watched (matched on normalized title + year), averages their ratings, and returns top 10. Unrated films still appear in the intersection but sort to the bottom.

## Code Style and Linting

This project uses an aggressive pre-commit setup:
- **black**: Automatic code formatting
- **ruff**: Fast Python linter (fixes issues automatically with `--fix`)
- **flake8**: Additional linting (ignores E501 - line too long)
- **mypy**: Type checking (configured in setup.cfg)
- **pydocstyle**: Docstring style enforcement
- **djhtml**: HTML template formatting
- **reorder-python-imports**: Automatic import sorting
- **commitizen**: Enforces conventional commit messages
- Custom hook: Prevents committing .db or .sqlite3 files

All pre-commit hooks run automatically on commit. To bypass hooks (not recommended): `git commit --no-verify`

## Testing Strategy

Currently no test suite exists. When adding tests:
- Consider using the commented-out fixture loading in `LetterboxdManager` to avoid hitting Letterboxd servers during tests
- Mock HTTP requests or use saved HTML fixtures from `src/fixtures/` directory
- Test HTML parsing separately from HTTP fetching for better test isolation

## Configuration Notes

- Python version: 3.11 (specified in README)
- Main branch: `main`
- Type checking: mypy configured for Python 3.8 compatibility (see setup.cfg)
- Flake8: Ignores E501 (line too long), uses smarkets import ordering style
- **Dependencies**:
  - `cloudscraper` is required for bypassing Cloudflare protection when scraping Letterboxd
  - Standard dependencies: `streamlit`, `beautifulsoup4`, `matplotlib`, `matplotlib-venn`
