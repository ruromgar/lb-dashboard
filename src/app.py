import datetime
import logging
import os
from pathlib import Path
from typing import Dict
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from matplotlib_venn import venn2

from src.models import DiaryEntry
from src.models import FilmCount
from src.models import WeeklyFilmCount


plt.style.use("fivethirtyeight")
logger = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent


@st.cache_data(ttl=3600)
def fetch_profile_data(user: str) -> str:
    # local_data = APP_DIR / "fixtures" / f"profile_{user}.html"
    # if local_data.exists():
    #     return local_data.read_text(encoding="utf-8")
    # else:
    #     raise FileNotFoundError(f"No local file found at {local_data}")

    url = f"https://letterboxd.com/{user}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
    }
    response = requests.get(url, headers=headers)
    return response.text


@st.cache_data(ttl=3600)
def fetch_diary_data(user: str) -> list[str]:
    """Fetch all diary pages for the specified Letterboxd user and year, returning a list of HTML strings (one per page)."""
    # local_data = APP_DIR / "fixtures" / f"diary_{user}_1.html"
    # if local_data.exists():
    #     return local_data.read_text(encoding="utf-8")
    # else:
    #     raise FileNotFoundError(f"No local file found at {local_data}")

    year = datetime.date.today().year
    page_num = 1
    all_pages = []

    while True:
        url = f"https://letterboxd.com/{user}/films/diary/for/{year}/page/{page_num}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
        }

        print(f"Fetching page {page_num} for {user} in {year}...")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            # If we get a non-200, we break out (could raise an exception if you prefer)
            print(f"Page {page_num} returned status {response.status_code}, stopping.")
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
        print(f"Moving to page {page_num} for {user} in {year}...")

    return all_pages


def extract_total_and_ytd(user: str) -> FilmCount:
    content = fetch_profile_data(user)
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


def parse_diary_entries(user: str) -> List[DiaryEntry]:
    page_list = fetch_diary_data(user)
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
            release_year_elem.get_text(strip=True) if release_year_elem else "Unknown"
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
            entry_date=entry_date, title=title, release_year=release_year, rating=rating
        )
        entries.append(entry)

    return entries


def films_in_last_week(entries: list[DiaryEntry]) -> WeeklyFilmCount:
    """Return how many diary entries occurred in the last n days."""
    this_week_threshold = datetime.date.today() - datetime.timedelta(days=7)
    this_week_count = 0
    for e in entries:
        if e.entry_date >= this_week_threshold:
            this_week_count += 1

    last_week_threshold = this_week_threshold - datetime.timedelta(days=7)
    last_week_count = 0
    for e in entries:
        if e.entry_date >= last_week_threshold and e.entry_date < this_week_threshold:
            last_week_count += 1

    return WeeklyFilmCount(
        last_week=last_week_count,
        this_week=this_week_count,
    )


def rating_to_stars(rating: int) -> str:
    """Convert a 0–10 integer rating into a 5-star (with optional half-star) string.

    For instance:   10 -> "★★★★★"   9  -> "★★★★½"   7  -> "★★★½"   None
    -> "-"
    """
    if rating is None:
        return "-"
    # We'll map 10 -> 5 stars. So each 2 points = 1 star, with 1 leftover => half star.
    full_stars = rating // 2  # integer division
    half_star = (rating % 2) == 1
    stars_str = "★" * full_stars
    if half_star:
        stars_str += "½"
    return stars_str


def calculate_accumulated_movies(
    diary_entries_1: List[DiaryEntry],
    diary_entries_2: List[DiaryEntry],
    user1_name: str = "UserOne",
    user2_name: str = "UserTwo",
) -> pd.DataFrame:
    """Plot two lines showing each user's accumulated movie count from Jan 1 through today."""
    today = datetime.date.today()
    start_of_year = datetime.date(today.year, 1, 1)

    # --- 1) Filter each user's entries to [Jan1..today] ---
    filtered_1 = [e for e in diary_entries_1 if start_of_year <= e.entry_date <= today]
    filtered_2 = [e for e in diary_entries_2 if start_of_year <= e.entry_date <= today]

    # --- 2) Build daily watch counts for each user ---
    daily_counts_1: Dict[datetime.date, int] = {}
    for entry in filtered_1:
        daily_counts_1[entry.entry_date] = daily_counts_1.get(entry.entry_date, 0) + 1

    daily_counts_2: Dict[datetime.date, int] = {}
    for entry in filtered_2:
        daily_counts_2[entry.entry_date] = daily_counts_2.get(entry.entry_date, 0) + 1

    # --- 3) Create a date range from Jan 1 to today ---
    all_dates = pd.date_range(start=start_of_year, end=today)
    df = pd.DataFrame({"date": all_dates})
    df["date"] = pd.to_datetime(df["date"])  # ensure datetime
    df.set_index("date", inplace=True)

    # --- 4) Insert daily counts, then compute cumulative sums ---
    # Create a new column from a list comprehension
    df[user1_name] = [daily_counts_1.get(d.date(), 0) for d in df.index]
    df[user2_name] = [daily_counts_2.get(d.date(), 0) for d in df.index]

    # Now each column is a Series, so we can do cumsum() directly
    df[user1_name] = df[user1_name].cumsum()
    df[user2_name] = df[user2_name].cumsum()

    return df


def calculate_venn_diagram(
    diary_data_1: List[DiaryEntry],
    diary_data_2: List[DiaryEntry],
    user1_name: str,
    user2_name: str,
):
    """Create a Venn diagram for the unique set of movies (title + release_year) in each user's diary."""
    set1 = {(e.title.strip().lower(), e.release_year.strip()) for e in diary_data_1}
    set2 = {(e.title.strip().lower(), e.release_year.strip()) for e in diary_data_2}

    fig, ax = plt.subplots(figsize=(4, 4))
    venn2([set1, set2], set_labels=(user1_name, user2_name), ax=ax)
    return fig


def bak_top_common_by_avg_rating(
    diary_data_1: List[DiaryEntry],
    diary_data_2: List[DiaryEntry],
    user1_name: str,
    user2_name: str,
):
    """Find common movies (same title+year) in both diaries, compute an average rating, then return the top 10 sorted descending."""
    # 1) Build dictionaries of {movie_key: [ratings]} for each user
    #    We could store multiple watches or just keep track of the average.
    user1_ratings: Dict[tuple, List[int]] = {}
    for e in diary_data_1:
        key = (e.title.strip().lower(), e.release_year.strip())
        if e.rating is not None:
            user1_ratings.setdefault(key, []).append(e.rating)

    user2_ratings: Dict[tuple, List[int]] = {}
    for e in diary_data_2:
        key = (e.title.strip().lower(), e.release_year.strip())
        if e.rating is not None:
            user2_ratings.setdefault(key, []).append(e.rating)

    # 2) Gather sets of unique keys
    set1 = set(user1_ratings.keys())
    set2 = set(user2_ratings.keys())
    common_keys = set1 & set2

    # 3) Compute average rating for each user, then the average across both
    common_items = []
    for key in common_keys:
        # user1’s average
        r1_list = user1_ratings[key]  # guaranteed to exist now
        avg1 = sum(r1_list) / len(r1_list) if r1_list else None

        # user2’s average
        r2_list = user2_ratings[key]
        avg2 = sum(r2_list) / len(r2_list) if r2_list else None

        # combined average
        if avg1 is None and avg2 is None:
            avg_both = None
        elif avg1 is None:
            avg_both = avg2
        elif avg2 is None:
            avg_both = avg1
        else:
            avg_both = (avg1 + avg2) / 2

        # Reconstruct the actual display title from the key
        # (We stored it in lowercase, so let's just do best effort)
        display_title = key[
            0
        ].title()  # e.g. "the wrong trousers" -> "The Wrong Trousers"
        display_year = key[1]

        common_items.append(
            {
                "Título": display_title,
                "Año": display_year,
                f"Nota {user2_name}": avg2,
                f"Nota {user1_name}": avg1,
                "Nota media": avg_both,
            }
        )

    # 4) Sort by combined_avg descending, then take top 10
    common_items.sort(
        key=lambda x: (x["Nota media"] if x["Nota media"] is not None else -9999),
        reverse=True,
    )
    top_10 = common_items[:10]

    # Return or display them. Let’s show them in a table.
    return top_10


def top_common_by_avg_rating(
    diary_data_1: List[DiaryEntry],
    diary_data_2: List[DiaryEntry],
    user1_name: str,
    user2_name: str,
):
    """Find films (title+year) that BOTH users have in their diary (rated or not). Compute each user's average rating, then the combined average.

    Return the top 10 sorted descending by combined average, with None
    considered lowest. Even if a film is unrated (avg=None), it still
    appears if it's in the intersection.
    """
    # 1) Build dictionaries tracking *all* watches, including unrated
    #    We'll store a list of numeric ratings if present (possibly empty).
    from collections import defaultdict

    user1_ratings: Dict[tuple, List[int]] = defaultdict(list)
    user1_watched: set = set()  # which keys user1 has watched at all

    for e in diary_data_1:
        key = (e.title.strip().lower(), e.release_year.strip())
        user1_watched.add(key)
        if e.rating is not None:
            user1_ratings[key].append(e.rating)

    user2_ratings: Dict[tuple, List[int]] = defaultdict(list)
    user2_watched: set = set()

    for e in diary_data_2:
        key = (e.title.strip().lower(), e.release_year.strip())
        user2_watched.add(key)
        if e.rating is not None:
            user2_ratings[key].append(e.rating)

    # 2) Intersection of all watched keys (including unrated)
    common_keys = user1_watched & user2_watched

    # 3) Compute average rating for each user & combined
    common_items = []
    for key in common_keys:
        # user1’s average
        r1_list = user1_ratings.get(key, [])
        avg1 = (sum(r1_list) / len(r1_list)) if r1_list else None

        # user2’s average
        r2_list = user2_ratings.get(key, [])
        avg2 = (sum(r2_list) / len(r2_list)) if r2_list else None

        # combined average
        if avg1 is None and avg2 is None:
            avg_both = None
        elif avg1 is None:
            avg_both = avg2
        elif avg2 is None:
            avg_both = avg1
        else:
            avg_both = (avg1 + avg2) / 2

        # Reconstruct display version
        display_title = key[0].title()  # "the wrong trousers" -> "The Wrong Trousers"
        display_year = key[1]

        common_items.append(
            {
                "Título": display_title,
                "Año": display_year,
                f"Nota {user2_name}": int(avg2) if avg2 is not None else None,
                f"Nota {user1_name}": int(avg1) if avg1 is not None else None,
                "Nota media": f"{avg_both:.2f}" if avg_both is not None else None,
            }
        )

    # 4) Sort by combined_avg descending, treating None as very low
    #    (We can use -9999 or any sentinel for None)
    def sort_key(item):
        val = item["Nota media"]
        return val if val is not None else -9999

    common_items.sort(key=sort_key, reverse=True)
    return common_items[:10]


def main():
    st.markdown(
        """
        <style>
        body {
            background: linear-gradient(to bottom right, #e8f9fd, #ffffff);
        }
        .big-title {
            font-size: 2.2em;
            font-weight: bold;
            color: #2b7bba;
        }
        .subsection {
            font-size: 1.3em;
            color: #444444;
            text-decoration: underline;
        }
        .highlight {
            background-color: #ffecb3;
            padding: 0.2em 0.4em;
            border-radius: 5px;
        }
        .winning {
            color: green;
            font-weight: bold;
        }
        .losing {
            color: red;
            font-weight: bold;
        }
        hr.solid {
            border: 1px solid #ccc;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="big-title">🎬 Letterboxd: la competición definitiva 🎬</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "¡Te damos la bienvenida a este show de gente pringada! ¡Dos gafas que no tienen nada más que hacer que pelearse por quién ve más películas!"
    )

    user1 = os.getenv("LB_USER_1", "unnonueve")
    user2 = os.getenv("LB_USER_2", "garciamorales")

    film_data_1 = extract_total_and_ytd(user1)
    film_data_2 = extract_total_and_ytd(user2)

    diary_data_1 = parse_diary_entries(user1)
    diary_data_2 = parse_diary_entries(user2)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{user1}</span></span>',
            unsafe_allow_html=True,
        )

        st.write("**Número de películas:**", film_data_1.total)
        st.write("### Últimas vistas")
        for entry in diary_data_1[:10]:
            # Format date, e.g. "Feb 06"
            date_str = entry.entry_date.strftime("%b %d")
            # Build the star/half-star string from the rating
            rating_str = rating_to_stars(entry.rating)

            html_block = f"""
            <div style="padding: 8px; margin-bottom: 8px; border-radius: 5px;">
            <div style="color: #666; font-size: 0.9em; margin-bottom: 4px;">
                {date_str}
            </div>
            <div>
                <strong>{entry.title} ({entry.release_year})</strong>
                <span style="float:right; font-weight:bold;">
                    {rating_str}
                </span>
            </div>
            </div>
            """
            st.markdown(html_block, unsafe_allow_html=True)

        weekly_count_1 = films_in_last_week(diary_data_1)
        st.metric(
            label="Películas en los últimos 7 días",
            value=weekly_count_1.this_week,
            delta=weekly_count_1.this_week - weekly_count_1.last_week,
            help="La diferencia es el número de películas vistas en los últimos 7 días comparado con las vistas en los 7 días anteriores",
        )
    with col2:
        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{user2}</span></span>',
            unsafe_allow_html=True,
        )

        st.write("**Número de películas:**", film_data_2.total)
        st.write("### Últimas vistas")
        for entry in diary_data_2[:10]:
            # Format date, e.g. "Feb 06"
            date_str = entry.entry_date.strftime("%b %d")
            # Build the star/half-star string from the rating
            rating_str = rating_to_stars(entry.rating)

            html_block = f"""
            <div style="padding: 8px; margin-bottom: 8px; border-radius: 5px;">
            <div style="color: #666; font-size: 0.9em; margin-bottom: 4px;">
                {date_str}
            </div>
            <div>
                <strong>{entry.title} ({entry.release_year})</strong>
                <span style="float:right; font-weight:bold;">
                    {rating_str}
                </span>
            </div>
            </div>
            """
            st.markdown(html_block, unsafe_allow_html=True)

        weekly_count_2 = films_in_last_week(diary_data_2)
        st.metric(
            label="Películas en los últimos 7 días",
            value=weekly_count_2.this_week,
            delta=weekly_count_2.this_week - weekly_count_2.last_week,
            help="La diferencia es el número de películas vistas en los últimos 7 días comparado con las vistas en los 7 días anteriores",
        )

    message = ""
    if weekly_count_1.this_week > weekly_count_2.this_week:
        st.warning(f"{user1} va ganando los últimos 7 días! 🏆", icon="⚠️")
    elif weekly_count_2.this_week > weekly_count_1.this_week:
        st.warning(f"{user2} va ganando los últimos 7 días! 🏆", icon="⚠️")
    else:
        st.warning("Hay un empate en los últimos 7 días! 🤝", icon="⚠️")

    st.markdown(message, unsafe_allow_html=True)
    st.markdown("<hr class='solid'>", unsafe_allow_html=True)

    st.write("### 📊 Métricas de rendimiento 📊")
    today = datetime.date.today()
    day_of_year = today.timetuple().tm_yday  # e.g. 1..365 or 366
    rate1 = film_data_1.this_year / day_of_year
    rate2 = film_data_2.this_year / day_of_year

    days_in_year = (
        366
        if (today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0))
        else 365
    )
    proj1 = rate1 * days_in_year
    proj2 = rate2 * days_in_year

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{user1}</span></span>',
            unsafe_allow_html=True,
        )
        st.write("**Películas Este Año:**", film_data_1.this_year)
        st.write("**Velocidad:**", f"{rate1:.2f} pelis/día")
        col1.metric(f"Proyección ({datetime.date.today().year})", f"{int(proj1)}")
    with col2:
        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{user2}</span></span>',
            unsafe_allow_html=True,
        )
        st.write("**Películas Este Año:**", film_data_2.this_year)
        st.write("**Velocidad:**", f"{rate2:.2f} films/day")
        col2.metric(f"Proeycción ({datetime.date.today().year})", f"{int(proj2)}")

    # Determine the YTD gap and see if a catch-up is possible
    gap = film_data_1.total - film_data_2.total  # how many films user1 leads by
    st.markdown(f"**Diferencia actual**: `{abs(gap)}`")

    # If user2 is behind but has a higher daily rate, estimate days to catch up
    if gap > 0 and rate2 > rate1:
        daily_diff = rate2 - rate1
        days_to_catch = gap / daily_diff
        st.success(
            f"{user2} va por detrás por {abs(gap)} películas, **pero** está remontando a una velocidad de ~{daily_diff:.2f} películas/día."
            f" La estimación es de **{days_to_catch:.1f} días** para alcanzar a {user1}!"
        )
    elif gap < 0 and rate1 > rate2:
        # If user1 is behind but has a higher rate, user1 can catch up
        gap = abs(gap)
        daily_diff = rate1 - rate2
        days_to_catch = gap / daily_diff
        st.success(
            f"{user1} va por detrás por {gap} películas, **pero** está remontando a una velocidad de ~{daily_diff:.2f} películas/día."
            f" La estimación es de **{days_to_catch:.1f} días** para alcanzar a {user2}!"
        )
    else:
        # If the leading user also has the higher rate, the gap will widen.
        # Or if the rates are exactly the same.
        if gap == 0:
            st.info(
                f"{user1} y {user2} están **empatados** en {datetime.date.today().year}!"
            )
        elif gap > 0 and rate1 >= rate2:
            st.warning(
                f"{user1} lleva {gap} películas de ventaja **y** va a más velocidad. La diferencia va a **aumentar!"
            )
        elif gap < 0 and rate2 >= rate1:
            st.warning(
                f"{user2} lleva {abs(gap)} películas de ventaja **y** va a más velocidad. La diferencia va a **aumentar!"
            )

    message = ""
    if film_data_1.total - film_data_2.total > 0:
        message = f"<h3> 🏆 <span class='winning'>{user1} va ganando!</span> 🏆</h3>"
    elif film_data_1.total - film_data_2.total < 0:
        message = f"<h3> 🏆 <span class='winning'>{user2} va ganando!</span> 🏆</h3>"
    else:
        message = "<h3>🤝 Empate! 🤝</h3>"

    st.markdown(message, unsafe_allow_html=True)

    df = calculate_accumulated_movies(
        diary_entries_1=diary_data_1,
        diary_entries_2=diary_data_2,
        user1_name=user1,
        user2_name=user2,
    )
    st.write(f"### Total Películas (Desde Ene 1 hasta {today.strftime('%b %d')})")
    st.line_chart(df[[user1, user2]])

    st.subheader("Diagrama de Venn")
    fig = calculate_venn_diagram(
        diary_data_1,
        diary_data_2,
        user1_name=user1,
        user2_name=user2,
    )
    st.pyplot(fig)

    st.subheader("Top 10 en común")
    st.write("Las películas que ambos han visto, ordenadas por nota media")
    top_10_common = top_common_by_avg_rating(
        diary_data_1,
        diary_data_2,
        user1_name=user1,
        user2_name=user2,
    )

    if not top_10_common:
        st.write("No hay películas en común!")
    else:
        # Convert to DataFrame for a nice table
        df_top = pd.DataFrame(top_10_common)
        st.table(df_top)

    st.markdown("<hr class='solid'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='big-title'>Que no mueran tus ganas! La gloria cinematográfica depende de ello</div>",
        unsafe_allow_html=True,
    )
