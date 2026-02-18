import datetime
import logging
import os
import time
from collections import Counter
from pathlib import Path
from typing import List
from typing import Optional
from typing import Tuple

import cloudscraper
from bs4 import BeautifulSoup

from src.cache import get_cached
from src.cache import get_stale_cached
from src.cache import save_to_cache
from src.models import DiaryEntry
from src.models import FilmCount
from src.models import FilmStreak
from src.models import UserProfile
from src.models import WeeklyFilmCount


logger = logging.getLogger(__name__)


class LetterboxdManager:
    def __init__(
        self,
        user: str,
        feminine: bool = False,
        cache_dir: Optional[str] = None,
    ):
        self.file_dir = Path(__file__).resolve().parent
        self.user = user
        self.feminine = feminine
        if cache_dir is not None:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = os.environ.get("LB_CACHE_DIR", "./cache")
        self.scraper = cloudscraper.create_scraper()

        raw_profile_data = self._fetch_profile_data()

        if raw_profile_data is None:
            # Means user doesn't exist or 404
            self.film_count: FilmCount = FilmCount(0, 0)
            self.diary_entries: List[DiaryEntry] = []
            self.weekly_film_count: WeeklyFilmCount = WeeklyFilmCount(0, 0)
            self.streak: FilmStreak = FilmStreak(0, 0)
            self.rate: float = 0.0
            self.highlights: List[str] = []
            self.profile: UserProfile = UserProfile()
            self.taste_labels: List[str] = []
            self.busiest_day: Optional[Tuple[datetime.date, int]] = None
        else:
            # Parse the real data
            self.film_count = self._get_film_count(raw_profile_data)
            self.diary_entries = self._get_diary_entries()
            self.weekly_film_count = self._get_weekly_film_count(self.diary_entries)
            self.streak = self._get_streak(self.diary_entries)
            self.rate = self._get_rate(self.film_count)
            self.highlights = self._generate_highlights(self.diary_entries)
            self.profile = self._get_profile(raw_profile_data)
            self.taste_labels = self._generate_taste_labels()
            self.busiest_day = self._get_busiest_day()

    def _fetch_profile_data(self) -> str:
        """Fetch profile HTML, using cache when available."""
        cache_key = f"{self.user}_profile.html"
        cached = get_cached(self.cache_dir, cache_key)
        if cached is not None:
            return cached

        url = f"https://letterboxd.com/{self.user}/"
        response = self.scraper.get(url)
        if response.status_code != 200:
            stale = get_stale_cached(self.cache_dir, cache_key)
            if stale is not None:
                return stale
            return None
        save_to_cache(self.cache_dir, cache_key, response.text)
        return response.text

    def _fetch_diary_data(self) -> List[str]:
        """Fetch all diary pages for the specified Letterboxd user and year."""
        year = datetime.date.today().year
        page_num = 1
        all_pages = []
        needs_delay = True

        while True:
            cache_key = f"{self.user}_diary_{year}_page_{page_num}.html"
            cached = get_cached(self.cache_dir, cache_key)

            if cached is not None:
                html = cached
            else:
                if needs_delay:
                    time.sleep(2)
                    needs_delay = False
                else:
                    time.sleep(2)

                diary_scraper = cloudscraper.create_scraper()
                url = (
                    f"https://letterboxd.com/{self.user}/"
                    f"diary/films/for/{year}/page/{page_num}/"
                )
                print(f"Fetching page {page_num} for {self.user} in {year}...")
                response = diary_scraper.get(url)
                if response.status_code != 200:
                    print(
                        f"Page {page_num} returned status "
                        f"{response.status_code}, stopping."
                    )
                    stale = get_stale_cached(self.cache_dir, cache_key)
                    if stale is not None:
                        html = stale
                    else:
                        break
                else:
                    html = response.text
                    save_to_cache(self.cache_dir, cache_key, html)

            all_pages.append(html)

            soup = BeautifulSoup(html, "html.parser")
            pagination_div = soup.find("div", class_="pagination")
            if not pagination_div:
                break

            next_link = pagination_div.find("a", class_="next")
            if not next_link:
                break

            parent_classes = next_link.parent.get("class", [])
            if "paginate-disabled" in parent_classes:
                break

            page_num += 1

        return all_pages

    def _get_film_count(self, raw_profile_data: str) -> FilmCount:
        if raw_profile_data is None:
            return FilmCount(total=0, this_year=0)

        soup = BeautifulSoup(raw_profile_data, "html.parser")

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

    def _get_profile(self, raw_profile_data: str) -> UserProfile:
        """Extract avatar URL and favourite films from the profile page."""
        soup = BeautifulSoup(raw_profile_data, "html.parser")

        # Avatar: <span class="avatar -large"> <img src="...">
        avatar_url = ""
        avatar_span = soup.find(
            "span", class_=lambda c: c and "avatar" in c and "-large" in c
        )
        if avatar_span:
            img = avatar_span.find("img")
            if img and img.get("src"):
                avatar_url = img["src"]

        # Favourite films: <li class="favourite-production-poster-container">
        #   -> child div with data-item-name="Title (Year)"
        favourite_films = []
        fav_items = soup.find_all("li", class_="favourite-production-poster-container")
        for li in fav_items:
            div = li.find("div", attrs={"data-item-name": True})
            if div:
                favourite_films.append(div["data-item-name"])

        return UserProfile(avatar_url=avatar_url, favourite_films=favourite_films)

    def _get_diary_entries(self) -> List[DiaryEntry]:
        page_list = self._fetch_diary_data()
        if not page_list:
            return []

        html = "".join(page_list)

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr", class_="diary-entry-row")

        entries = []
        for row in rows:
            # 1) Parse the date from the anchor's href
            day_cell = row.find("td", class_="col-daydate")
            date_anchor = day_cell.find("a") if day_cell else None
            if not date_anchor:
                continue

            href = date_anchor.get("href", "")
            parts = href.strip("/").split("/")
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
                    continue
            else:
                continue

            # 2) Parse the title from <h2> in the production cell
            film_cell = row.find("td", class_="col-production")
            title_elem = film_cell.find("h2") if film_cell else None
            if title_elem:
                raw_title = title_elem.get_text()
                title = " ".join(raw_title.split())
            else:
                title = "Unknown"

            # 3) Parse the release year
            release_year_elem = row.find("td", class_="col-releaseyear")
            release_year = (
                release_year_elem.get_text(strip=True)
                if release_year_elem
                else "Unknown"
            )

            # 4) Parse rating
            row_classes = row.get("class", [])
            if "not-rated" in row_classes or "-has-no-rating" in row_classes:
                rating = None
            else:
                rating_input = row.find("input", class_="rateit-field")
                if rating_input:
                    rating_str = rating_input.get("value", "")
                    try:
                        rating = int(rating_str)
                        if rating == 0:
                            rating = None
                    except ValueError:
                        rating = None
                else:
                    rating = None

            # 5) Parse liked status
            # The like cell contains <span class="icon-liked"> for liked entries
            liked = False
            like_cell = row.find("td", class_="col-like")
            if like_cell:
                liked_icon = like_cell.find("span", class_="icon-liked")
                if liked_icon:
                    liked = True

            # 6) Parse rewatch status
            # If the rewatch td has "icon-status-off" in its classes, it's NOT a rewatch
            is_rewatch = False
            rewatch_cell = row.find("td", class_="col-rewatch")
            if rewatch_cell:
                rewatch_classes = rewatch_cell.get("class", [])
                if "icon-status-off" not in rewatch_classes:
                    is_rewatch = True

            entry = DiaryEntry(
                entry_date=entry_date,
                title=title,
                release_year=release_year,
                rating=rating,
                liked=liked,
                is_rewatch=is_rewatch,
            )
            entries.append(entry)

        return entries

    def _get_weekly_film_count(
        self, diary_entries: List[DiaryEntry]
    ) -> WeeklyFilmCount:
        """Return how many diary entries occurred in the last n days."""
        this_week_threshold = datetime.date.today() - datetime.timedelta(days=7)
        this_week_count = 0
        for e in diary_entries:
            if e.entry_date >= this_week_threshold:
                this_week_count += 1

        last_week_threshold = this_week_threshold - datetime.timedelta(days=7)
        last_week_count = 0
        for e in diary_entries:
            if (
                e.entry_date >= last_week_threshold
                and e.entry_date < this_week_threshold
            ):
                last_week_count += 1

        return WeeklyFilmCount(
            last_week=last_week_count,
            this_week=this_week_count,
        )

    def _get_streak(self, diary_entries: List[DiaryEntry]) -> FilmStreak:
        """Calculate current and longest viewing streaks."""
        sorted_entries = sorted(diary_entries, key=lambda e: e.entry_date)

        longest_streak = 0
        current_streak = 0

        for i in range(1, len(sorted_entries)):
            prev_day = sorted_entries[i - 1].entry_date
            this_day = sorted_entries[i].entry_date
            gap = (this_day - prev_day).days

            if gap == 1:
                current_streak += 1
            else:
                current_streak = 1

            if current_streak > longest_streak:
                longest_streak = current_streak

        return FilmStreak(
            current_streak=current_streak,
            longest_streak=longest_streak,
        )

    def _get_rate(self, film_count: FilmCount) -> float:
        day_of_year = datetime.date.today().timetuple().tm_yday
        return film_count.this_year / day_of_year

    def _generate_highlights(self, diary_entries: List[DiaryEntry]) -> List[str]:
        """Return a list of interesting stats about this user's viewing history."""
        if not diary_entries:
            return []

        valid_year_entries = [e for e in diary_entries if e.release_year.isdigit()]
        if not valid_year_entries:
            oldest_str = "No valid release years found."
            newest_str = "No valid release years found."
        else:
            oldest_entry = min(valid_year_entries, key=lambda e: int(e.release_year))
            newest_entry = max(valid_year_entries, key=lambda e: int(e.release_year))
            oldest_str = (
                f"Oldest film: '{oldest_entry.title}' ({oldest_entry.release_year})"
            )
            newest_str = (
                f"Newest film: '{newest_entry.title}' ({newest_entry.release_year})"
            )

        rated_entries = [e for e in diary_entries if e.rating is not None]
        if rated_entries:
            highest_rated = max(rated_entries, key=lambda e: e.rating or 0)
            lowest_rated = min(rated_entries, key=lambda e: e.rating or 0)
            highest_rated_str = f"Highest rated: '{highest_rated.title}' ({highest_rated.release_year}) with {highest_rated.rating}/10"
            lowest_rated_str = f"Lowest rated: '{lowest_rated.title}' ({lowest_rated.release_year}) with {lowest_rated.rating}/10"
        else:
            highest_rated_str = "No films have been rated."
            lowest_rated_str = "No films have been rated."

        total_films = len(diary_entries)
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

        highlights = [
            oldest_str,
            newest_str,
            highest_rated_str,
            lowest_rated_str,
            total_str,
            rated_str,
            avg_str,
        ]
        return highlights

    def _generate_taste_labels(self) -> List[str]:
        """Auto-assign fun taste labels based on viewing data."""
        labels: List[str] = []
        if not self.diary_entries:
            return labels

        f = self.feminine
        rated = [e for e in self.diary_entries if e.rating is not None]
        if rated:
            avg = sum(e.rating for e in rated if e.rating is not None) / len(rated)
            if avg >= 7.5:
                labels.append("La Romantica" if f else "El Romantico")
            elif avg < 5:
                labels.append("La Critica Implacable" if f else "El Critico Implacable")

        valid_years = [e for e in self.diary_entries if e.release_year.isdigit()]
        if valid_years:
            years = [int(e.release_year) for e in valid_years]
            sorted_years = sorted(years)
            median_year = sorted_years[len(sorted_years) // 2]
            if median_year < 2000:
                labels.append("Arqueologa del Cine" if f else "Arqueologo del Cine")

        if self.streak.longest_streak >= 7:
            labels.append("Maratonista")

        rewatch_count = sum(1 for e in self.diary_entries if e.is_rewatch)
        if rewatch_count >= 3:
            labels.append("La Nostalgica" if f else "El Nostalgico")

        like_count = sum(1 for e in self.diary_entries if e.liked)
        if like_count >= len(self.diary_entries) * 0.4 and len(self.diary_entries) >= 5:
            labels.append("Corazon Generoso")

        if self.weekly_film_count.this_week >= 5:
            labels.append("En Racha")

        return labels[:3]

    def _get_busiest_day(self) -> Optional[Tuple[datetime.date, int]]:
        """Find the date with the most diary entries."""
        if not self.diary_entries:
            return None

        date_counts = Counter(e.entry_date for e in self.diary_entries)
        busiest_date, count = date_counts.most_common(1)[0]
        if count >= 2:
            return (busiest_date, count)
        return None
