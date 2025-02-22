import datetime
import logging
import os
from collections import Counter
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FilmCount:
    total: int
    this_year: int


@dataclass
class DiaryEntry:
    month: str
    day: str
    title: str


def to_date(month_str: str, day_str: str, year: int = None) -> datetime.date:
    """Convert month/day to a datetime.date, defaulting to current year if none provided."""
    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    if year is None:
        year = datetime.date.today().year
    m = month_map.get(month_str, 1)
    d = int(day_str)
    return datetime.date(year, m, d)


def films_in_last_n_days(entries: list[DiaryEntry], n: int = 3) -> int:
    """Return how many diary entries occurred in the last n days."""
    threshold = datetime.date.today() - datetime.timedelta(days=n)
    count = 0
    for e in entries:
        entry_date = to_date(e.month, e.day)
        if entry_date >= threshold:
            count += 1
    return count


def fetch_raw_data(user: str) -> str:
    # local_data = f"response{user}.html"
    # if os.path.exists(local_data):
    #     with open(local_data) as f:
    #         return f.read()

    url = f"https://letterboxd.com/{user}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
    }
    response = requests.get(url, headers=headers)
    # with open(f"response{user}.html", "w") as f:
    #     f.write(response.text)
    return response.text


def extract_total_and_ytd(content: str) -> FilmCount:
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


def extract_diary_entries(content: str) -> list[DiaryEntry]:
    soup = BeautifulSoup(content, "html.parser")

    all_diary_entries = []
    diary_list = soup.find("ul", class_="diarylist")
    if not diary_list:
        return all_diary_entries

    month_blocks = diary_list.find_all("li", class_="listitem")
    for block in month_blocks:
        month_elem = block.find("h3", class_="month")
        month_name = month_elem.get_text(strip=True) if month_elem else "Unknown"

        entrylist = block.find("dl", class_="entrylist")
        if not entrylist:
            continue

        days = entrylist.find_all("dt", class_="day")
        titles = entrylist.find_all("dd", class_="title")

        for dt, dd in zip(days, titles):
            day_text = dt.get_text(strip=True)
            title_link = dd.find("a")
            film_title = title_link.get_text(strip=True) if title_link else ""

            all_diary_entries.append(
                DiaryEntry(month=month_name, day=day_text, title=film_title)
            )

    return all_diary_entries


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
        '<div class="big-title">🎬 Letterboxd Death Race Dashboard 🎬</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Welcome to the **ultimate** cinematic showdown! Two intrepid movie-watchers, neck and neck in a thrilling competition!"
    )

    user1 = os.getenv("LB_USER_1", "unnonueve")
    user2 = os.getenv("LB_USER_2", "garciamorales")
    data1 = fetch_raw_data(user1)
    data2 = fetch_raw_data(user2)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            f'<span class="subsection">Competitor: <span style="color: #2b7bba;">{user1}</span></span>',
            unsafe_allow_html=True,
        )

        film_data_1 = extract_total_and_ytd(data1)
        diary_data_1 = extract_diary_entries(data1)

        st.write("**Total Films:**", film_data_1.total)
        st.write("### Last Diary Entries")
        st.markdown("<ul>", unsafe_allow_html=True)
        for entry in diary_data_1:
            st.markdown(
                f"<li>{entry.month} {entry.day}: <em>{entry.title}</em></li>",
                unsafe_allow_html=True,
            )
        st.markdown("</ul>", unsafe_allow_html=True)

        last_n_days_count_1 = films_in_last_n_days(diary_data_1, 7)
        st.metric(
            "Films in Last 7 Days", last_n_days_count_1, delta=+last_n_days_count_1
        )
    with col2:
        st.markdown(
            f'<span class="subsection">Competitor: <span style="color: #2b7bba;">{user2}</span></span>',
            unsafe_allow_html=True,
        )

        film_data_2 = extract_total_and_ytd(data2)
        diary_data_2 = extract_diary_entries(data2)

        st.write("**Total Films:**", film_data_2.total)
        st.write("### Last Diary Entries")
        st.markdown("<ul>", unsafe_allow_html=True)
        for entry in diary_data_2:
            st.markdown(
                f"<li>{entry.month} {entry.day}: <em>{entry.title}</em></li>",
                unsafe_allow_html=True,
            )
        st.markdown("</ul>", unsafe_allow_html=True)

        last_n_days_count_2 = films_in_last_n_days(diary_data_2, 7)
        st.metric(
            "Films in Last 7 Days", last_n_days_count_2, delta=+last_n_days_count_2
        )

    message = ""
    if last_n_days_count_1 > last_n_days_count_2:
        st.warning(f"{user1} is winning the race in the last 7 days! 🏆", icon="⚠️")
    elif last_n_days_count_2 > last_n_days_count_1:
        st.warning(f"{user2} is winning the race in the last 7 days! 🏆", icon="⚠️")
    else:
        st.warning("It's a tie in the last 7 days! 🤝", icon="⚠️")

    st.markdown(message, unsafe_allow_html=True)
    st.markdown("<hr class='solid'>", unsafe_allow_html=True)

    st.write("### 📊 Performance Metrics 📊")
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
            f'<span class="subsection">Competitor: <span style="color: #2b7bba;">{user1}</span></span>',
            unsafe_allow_html=True,
        )
        st.write("**Films This Year:**", film_data_1.this_year)
        st.write("**Approximate Daily Rates:**", f"{rate1:.2f} films/day")
        col1.metric(f"Projected Total ({datetime.date.today().year})", f"{int(proj1)}")
    with col2:
        st.markdown(
            f'<span class="subsection">Competitor: <span style="color: #2b7bba;">{user2}</span></span>',
            unsafe_allow_html=True,
        )
        st.write("**Films This Year:**", film_data_2.this_year)
        st.write("**Approximate Daily Rates:**", f"{rate2:.2f} films/day")
        col2.metric(f"Projected Total ({datetime.date.today().year})", f"{int(proj2)}")

    # Determine the YTD gap and see if a catch-up is possible
    gap = film_data_1.total - film_data_2.total  # how many films user1 leads by
    st.markdown(f"**Current gap**: `{abs(gap)}`")

    # If user2 is behind but has a higher daily rate, estimate days to catch up
    if gap > 0 and rate2 > rate1:
        daily_diff = rate2 - rate1
        days_to_catch = gap / daily_diff
        st.success(
            f"{user2} is behind by {gap} films, **but** is catching up at a rate of ~{daily_diff:.2f} additional films/day."
            f" Estimated **{days_to_catch:.1f} days** to catch up!"
        )
    elif gap < 0 and rate1 > rate2:
        # If user1 is behind but has a higher rate, user1 can catch up
        gap = abs(gap)
        daily_diff = rate1 - rate2
        days_to_catch = gap / daily_diff
        st.success(
            f"{user1} is behind by {gap} films, but is catching up at {daily_diff:.2f} additional films/day. "
            f"**{days_to_catch:.1f} days** to close the gap!"
        )
    else:
        # If the leading user also has the higher rate, the gap will widen.
        # Or if the rates are exactly the same.
        if gap == 0:
            st.info("They're currently **tied** YTD!")
        elif gap > 0 and rate1 >= rate2:
            st.warning(
                f"{user1} leads by {gap} films **and** has the same or higher daily rate. The gap will likely **increase**!"
            )
        elif gap < 0 and rate2 >= rate1:
            st.warning(
                f"{user2} leads by {abs(gap)} films **and** has the same or higher daily rate. The gap will likely grow!"
            )

    message = ""
    if film_data_1.total - film_data_2.total > 0:
        message = (
            f"<h3> 🏆 <span class='winning'>{user1} is winning the race!</span> 🏆</h3>"
        )
    elif film_data_1.total - film_data_2.total < 0:
        message = (
            f"<h3> 🏆 <span class='winning'>{user2} is winning the race!</span> 🏆</h3>"
        )
    else:
        message = "<h3>🤝It's a tie! 🤝</h3>"

    st.markdown(message, unsafe_allow_html=True)
    st.markdown("<hr class='solid'>", unsafe_allow_html=True)

    # Last Days Chart
    freq_user1 = Counter(to_date(e.month, e.day) for e in diary_data_1)
    freq_user2 = Counter(to_date(e.month, e.day) for e in diary_data_2)
    all_dates = sorted(set(freq_user1.keys()) | set(freq_user2.keys()))

    chart_data = {"date": [], user1: [], user2: []}

    for d in all_dates:
        chart_data["date"].append(d)
        chart_data[user1].append(freq_user1[d])
        chart_data[user2].append(freq_user2[d])

    df = pd.DataFrame(chart_data)
    df.set_index("date", inplace=True)

    st.divider()
    st.markdown("### 📅 Film Watch Frequency Over Last Days 📅")
    st.bar_chart(df, use_container_width=True)

    st.markdown(
        "<span class='strong'>Keep an eye on these stats—your cinematic glory depends on it!</span>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
