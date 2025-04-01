import datetime
import logging
from pathlib import Path
from typing import List

import requests
from bs4 import BeautifulSoup

from src.models import DiaryEntry
from src.models import FilmCount
from src.models import FilmStreak
from src.models import WeeklyFilmCount


logger = logging.getLogger(__name__)


class LetterboxdManager:
    def __init__(self, user: str):
        self.file_dir = Path(__file__).resolve().parent
        self.user = user

        self.film_count: FilmCount = self._get_film_count()
        self.diary_entries: List[DiaryEntry] = self._get_diary_entries()
        self.weekly_film_count: WeeklyFilmCount = self._get_weekly_film_count()
        self.streak: FilmStreak = self._get_streak()
        self.rate: float = self._get_rate()
        self.highlights: List[str] = self._generate_highlights()

    def _fetch_profile_data(self) -> str:
        local_data = self.file_dir / "fixtures" / f"profile_{self.user}.html"
        if local_data.exists():
            return local_data.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"No local file found at {local_data}")

        url = f"https://letterboxd.com/{self.user}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
        }
        response = requests.get(url, headers=headers)
        return response.text

    def _fetch_diary_data(self) -> list[str]:
        """Fetch all diary pages for the specified Letterboxd user and year, returning a list of HTML strings (one per page)."""
        local_data = self.file_dir / "fixtures" / f"diary_{self.user}_1.html"
        if local_data.exists():
            return local_data.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"No local file found at {local_data}")

        year = datetime.date.today().year
        page_num = 1
        all_pages = []

        while True:
            url = f"https://letterboxd.com/{self.user}/films/diary/for/{year}/page/{page_num}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
            }

            print(f"Fetching page {page_num} for {self.user} in {year}...")

            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                # If we get a non-200, we break out (could raise an exception if you prefer)
                print(
                    f"Page {page_num} returned status {response.status_code}, stopping."
                )
                break

            # Store or parse data here
            html = response.text
            all_pages.append(html)

            # Check if there's a "next" link
            soup = BeautifulSoup(html, "html.parser")
            pagination_div = soup.find("div", class_="pagination")
            if not pagination_div:
                # No pagination block at all => no more pages
                break

            next_link = pagination_div.find("a", class_="next")
            if not next_link:
                # There's no 'next' link => last page
                break

            # If the parent has "paginate-disabled", or something else signals no more pages, break
            parent_classes = next_link.parent.get("class", [])
            if "paginate-disabled" in parent_classes:
                # "Older" link is disabled => no more pages
                break

            # Otherwise, let's move on to the next page
            page_num += 1
            print(f"Moving to page {page_num} for {self.user} in {year}...")

        return all_pages

    def _get_film_count(self) -> FilmCount:
        content = self._fetch_profile_data()
        soup = BeautifulSoup(content, "html.parser")

        films_count = 0
        this_year_count = 0

        stats_div = soup.find("div", {"class": "profile-stats js-profile-stats"})
        if stats_div:
            h4_elements = stats_div.find_all("h4", class_="profile-statistic statistic")
            for h4 in h4_elements:
                value_span = h4.find("span", class_="value")
                definition_span = h4.find("span", class_="definition")

                if not value_span or not definition_span:
                    continue

                definition_text = definition_span.get_text(strip=True)
                value_text = value_span.get_text(strip=True)

                if definition_text == "Films":
                    try:
                        films_count = int(value_text.replace(",", ""))
                    except ValueError:
                        logger.error(f"Could not parse value: {value_text}")
                elif definition_text == "This year":
                    try:
                        this_year_count = int(value_text)
                    except ValueError:
                        logger.error(f"Could not parse value: {value_text}")

        return FilmCount(total=films_count, this_year=this_year_count)

    def _get_diary_entries(self) -> List[DiaryEntry]:
        page_list = self._fetch_diary_data()
        # Combine all pages into a single HTML string
        html = "".join(page_list)

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr", class_="diary-entry-row")

        entries = []
        for row in rows:
            # 1) Parse the date from the anchor's href, e.g. /unnonueve/films/diary/for/2025/02/06/
            day_cell = row.find("td", class_="td-day")
            date_anchor = day_cell.find("a") if day_cell else None
            if not date_anchor:
                continue

            href = date_anchor.get("href", "")
            # Example href format: /unnonueve/films/diary/for/2025/02/06/
            # We'll split on '/' and pick out the parts
            parts = href.strip("/").split("/")
            # parts might be: ["unnonueve", "films", "diary", "for", "2025", "02", "06"]
            # year = parts[4], month = parts[5], day = parts[6]
            if len(parts) >= 7:
                year_str = parts[4]
                month_str = parts[5]
                day_str = parts[6]
                try:
                    y = int(year_str)
                    m = int(month_str)
                    d = int(day_str)
                    entry_date = datetime.date(y, m, d)
                except ValueError:
                    # If there's an unexpected parse error, skip
                    continue
            else:
                continue

            # 2) Parse the title from <h3 class="headline-3">
            title_elem = row.find("h3", class_="headline-3")
            if title_elem:
                raw_title = title_elem.get_text()
                # Convert all internal whitespace to single spaces
                title = " ".join(raw_title.split())
            else:
                title = "Unknown"

            # 3) Parse the release year from <td class="td-released center"><span>1993</span></td>
            release_year_elem = row.find("td", class_="td-released")
            release_year = (
                release_year_elem.get_text(strip=True)
                if release_year_elem
                else "Unknown"
            )

            # 4) Parse rating
            #    If the row has class "not-rated", rating = None
            #    Otherwise read the <input class="rateit-field"> value
            if "not-rated" in row.get("class", []):
                rating = None
            else:
                rating_input = row.find("input", class_="rateit-field")
                if rating_input:
                    rating_str = rating_input.get("value", "")
                    try:
                        rating = int(rating_str)
                    except ValueError:
                        rating = None
                else:
                    rating = None

            # 5) Construct DiaryEntry and add to the list
            entry = DiaryEntry(
                entry_date=entry_date,
                title=title,
                release_year=release_year,
                rating=rating,
            )
            entries.append(entry)

        return entries

    def _get_weekly_film_count(self) -> WeeklyFilmCount:
        """Return how many diary entries occurred in the last n days."""
        this_week_threshold = datetime.date.today() - datetime.timedelta(days=7)
        this_week_count = 0
        for e in self.diary_entries:
            if e.entry_date >= this_week_threshold:
                this_week_count += 1

        last_week_threshold = this_week_threshold - datetime.timedelta(days=7)
        last_week_count = 0
        for e in self.diary_entries:
            if (
                e.entry_date >= last_week_threshold
                and e.entry_date < this_week_threshold
            ):
                last_week_count += 1

        return WeeklyFilmCount(
            last_week=last_week_count,
            this_week=this_week_count,
        )

    def _get_streak(self) -> FilmStreak:
        if not self.diary_entries:
            return FilmStreak(current_streak=0, longest_streak=0)

        # Sort entries by date ascending
        sorted_entries = sorted(self.diary_entries, key=lambda e: e.entry_date)

        # We'll track consecutive days by comparing each date to the previous one
        longest_streak = 1
        current_streak = 1

        for i in range(1, len(sorted_entries)):
            prev_day = sorted_entries[i - 1].entry_date
            this_day = sorted_entries[i].entry_date
            gap = (this_day - prev_day).days

            if gap == 1:
                current_streak += 1
            else:
                # Reset streak
                current_streak = 1

            if current_streak > longest_streak:
                longest_streak = current_streak

        # After the loop, current_streak will be how many days consecutively up to the last entry
        return FilmStreak(
            current_streak=current_streak,
            longest_streak=longest_streak,
        )

    def _get_rate(self) -> float:
        day_of_year = datetime.date.today().timetuple().tm_yday  # e.g. 1..365 or 366
        return self.film_count.this_year / day_of_year

    def _generate_highlights(self) -> List[str]:
        """Return a list of interesting stats about this user's viewing history."""
        if not self.diary_entries:
            return []

        # Sort by release_year, converting to int; handle missing or invalid years gracefully
        valid_year_entries = [e for e in self.diary_entries if e.release_year.isdigit()]
        if not valid_year_entries:
            # If no valid years, skip these facts
            oldest_str = "No valid release years found."
            newest_str = "No valid release years found."
        else:
            # Find entry with min year and max year
            oldest_entry = min(valid_year_entries, key=lambda e: int(e.release_year))
            newest_entry = max(valid_year_entries, key=lambda e: int(e.release_year))
            oldest_str = (
                f"Oldest film: '{oldest_entry.title}' ({oldest_entry.release_year})"
            )
            newest_str = (
                f"Newest film: '{newest_entry.title}' ({newest_entry.release_year})"
            )

        # For ratings, only consider entries that actually have a rating
        rated_entries = [e for e in self.diary_entries if e.rating is not None]
        if rated_entries:
            highest_rated: DiaryEntry = max(rated_entries, key=lambda e: e.rating)
            lowest_rated: DiaryEntry = min(rated_entries, key=lambda e: e.rating)
            highest_rated_str = f"Highest rated: '{highest_rated.title}' ({highest_rated.release_year}) with {highest_rated.rating}/10"
            lowest_rated_str = f"Lowest rated: '{lowest_rated.title}' ({lowest_rated.release_year}) with {lowest_rated.rating}/10"
        else:
            highest_rated_str = "No films have been rated."
            lowest_rated_str = "No films have been rated."

        # Example: total films, total rated, rating average...
        total_films = len(self.diary_entries)
        total_rated = len(rated_entries)
        avg_rating = None
        if total_rated > 0:
            avg_rating = (
                sum(e.rating for e in rated_entries if e.rating is not None)
                / total_rated
            )

        total_str = f"Total films logged: {total_films}"
        rated_str = f"Rated films: {total_rated}"
        avg_str = (
            f"Average rating: {avg_rating:.1f}"
            if avg_rating is not None
            else "No average rating (no rated films)."
        )

        # Build a list of highlight strings. You can reorder or expand these as you like.
        highlights = [
            oldest_str,
            newest_str,
            highest_rated_str,
            lowest_rated_str,
            total_str,
            rated_str,
            avg_str,
            # Add more creative facts if desired
        ]
        return highlights
