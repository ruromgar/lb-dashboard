import datetime
import logging
import random
from typing import Dict
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib_venn import venn2
from matplotlib_venn import venn2_circles
from streamlit import delta_generator

from src.letterboxd_manager import LetterboxdManager
from src.utils import rating_to_stars


logger = logging.getLogger(__name__)


class DeathRaceManager:
    def __init__(self, user1: str, user2: str):
        self.user1 = user1
        self.user2 = user2

        self.lbm1 = LetterboxdManager(user1)
        self.lbm2 = LetterboxdManager(user2)

    def calculate_accumulated_movies(self) -> pd.DataFrame:
        """Plot two lines showing each user's accumulated movie count from Jan 1 through today."""
        today = datetime.date.today()
        start_of_year = datetime.date(today.year, 1, 1)

        # --- 1) Filter each user's entries to [Jan1..today] ---
        filtered_1 = [
            e for e in self.lbm1.diary_entries if start_of_year <= e.entry_date <= today
        ]
        filtered_2 = [
            e for e in self.lbm2.diary_entries if start_of_year <= e.entry_date <= today
        ]

        # --- 2) Build daily watch counts for each user ---
        daily_counts_1: Dict[datetime.date, int] = {}
        for entry in filtered_1:
            daily_counts_1[entry.entry_date] = (
                daily_counts_1.get(entry.entry_date, 0) + 1
            )

        daily_counts_2: Dict[datetime.date, int] = {}
        for entry in filtered_2:
            daily_counts_2[entry.entry_date] = (
                daily_counts_2.get(entry.entry_date, 0) + 1
            )

        # --- 3) Create a date range from Jan 1 to today ---
        all_dates = pd.date_range(start=start_of_year, end=today)
        df = pd.DataFrame({"date": all_dates})
        df["date"] = pd.to_datetime(df["date"])  # ensure datetime
        df.set_index("date", inplace=True)

        # --- 4) Insert daily counts, then compute cumulative sums ---
        # Create a new column from a list comprehension
        df[self.user1] = [daily_counts_1.get(d.date(), 0) for d in df.index]
        df[self.user2] = [daily_counts_2.get(d.date(), 0) for d in df.index]

        # Now each column is a Series, so we can do cumsum() directly
        df[self.user1] = df[self.user1].cumsum()
        df[self.user2] = df[self.user2].cumsum()

        return df

    def plot_venn_diagram(self):
        """Create a Venn diagram for the unique set of movies (title + release_year) in each user's diary."""
        set1 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm1.diary_entries
        }
        set2 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm2.diary_entries
        }

        fig, ax = plt.subplots(figsize=(3, 3))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        # Create the venn diagram with custom colors and alpha
        v = venn2(
            [set1, set2],
            set_labels=(self.user1, self.user2),
            set_colors=("skyblue", "gold"),
            alpha=0.6,
            ax=ax,
        )

        # Add circle outlines
        venn2_circles(
            [set1, set2], linestyle="solid", ax=ax, linewidth=1, color="white"
        )

        # For each region ID, change text color to white and add a semi-transparent gray background
        region_ids = [
            "10",
            "01",
            "11",
        ]  # '10' -> only in user1, '01' -> only in user2, '11' -> intersection
        for rid in region_ids:
            lbl = v.get_label_by_id(rid)
            if lbl:
                lbl.set_color("white")
                lbl.set_bbox(dict(facecolor="gray", alpha=0.5, edgecolor="none"))
                lbl.set_fontsize(8)

        # Tweak the set label text properties
        if v.set_labels is not None:
            for label in v.set_labels:
                if label:  # might be None if there's no label
                    label.set_fontsize(8)
                    label.set_fontweight("bold")
                    label.set_color("white")

        # Remove the default axis
        ax.set_axis_off()

        st.pyplot(fig)

    def calculate_gap(self):
        gap = (
            self.lbm1.film_count.total - self.lbm2.film_count.total
        )  # how many films user1 leads by
        st.markdown(f"**Diferencia actual**: `{abs(gap)}`")

        # If user2 is behind but has a higher daily rate, estimate days to catch up
        if gap > 0 and self.lbm2.rate > self.lbm1.rate:
            daily_diff = self.lbm2.rate - self.lbm1.rate
            days_to_catch = gap / daily_diff
            st.success(
                f"{self.lbm2.user} va por detrás por {abs(gap)} películas, **pero** está remontando a una velocidad de ~{daily_diff:.2f} películas/día."
                f" La estimación es de **{days_to_catch:.1f} días** para alcanzar a {self.lbm1.user}!"
            )
        elif gap < 0 and self.lbm1.rate > self.lbm2.rate:
            # If user1 is behind but has a higher rate, user1 can catch up
            gap = abs(gap)
            daily_diff = self.lbm1.rate - self.lbm2.rate
            days_to_catch = gap / daily_diff
            st.success(
                f"{self.lbm1.user} va por detrás por {gap} películas, **pero** está remontando a una velocidad de ~{daily_diff:.2f} películas/día."
                f" La estimación es de **{days_to_catch:.1f} días** para alcanzar a {self.lbm2.user}!"
            )
        else:
            # If the leading user also has the higher rate, the gap will widen.
            # Or if the rates are exactly the same.
            if gap == 0:
                st.warning(
                    f"{self.lbm1.user} y {self.lbm2.user} están **empatados** en {datetime.date.today().year}!"
                )
            elif gap > 0 and self.lbm1.rate >= self.lbm2.rate:
                st.warning(
                    f"{self.lbm1.user} lleva {gap} películas de ventaja **y** va a más velocidad. La diferencia va a **aumentar!"
                )
            elif gap < 0 and self.lbm2.rate >= self.lbm1.rate:
                st.warning(
                    f"{self.lbm2.user} lleva {abs(gap)} películas de ventaja **y** va a más velocidad. La diferencia va a **aumentar!"
                )

        message = ""
        if self.lbm1.film_count.total - self.lbm2.film_count.total > 0:
            message = f"<h3 style='text-align:center;'> 🏆 <span class='winning'>{self.lbm1.user} va ganando!</span> 🏆</h3>"
        elif self.lbm1.film_count.total - self.lbm2.film_count.total < 0:
            message = f"<h3 style='text-align:center;'> 🏆 <span class='winning'>{self.lbm2.user} va ganando!</span> 🏆</h3>"
        else:
            message = "<h3 style='text-align:center;'>🤝 Empate! 🤝</h3>"

        st.markdown(message, unsafe_allow_html=True)

    def top_common_by_avg_rating(self):
        """Find films (title+year) that BOTH users have in their diary (rated or not). Compute each user's average rating, then the combined average.

        Return the top 10 sorted descending by combined average, with
        None considered lowest. Even if a film is unrated (avg=None), it
        still appears if it's in the intersection.
        """
        # 1) Build dictionaries tracking *all* watches, including unrated
        #    We'll store a list of numeric ratings if present (possibly empty).
        from collections import defaultdict

        user1_ratings: Dict[tuple, List[int]] = defaultdict(list)
        user1_watched: set = set()  # which keys user1 has watched at all

        for e in self.lbm1.diary_entries:
            key = (e.title.strip().lower(), e.release_year.strip())
            user1_watched.add(key)
            if e.rating is not None:
                user1_ratings[key].append(e.rating)

        user2_ratings: Dict[tuple, List[int]] = defaultdict(list)
        user2_watched: set = set()

        for e in self.lbm2.diary_entries:
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
            display_title = key[
                0
            ].title()  # "the wrong trousers" -> "The Wrong Trousers"
            display_year = key[1]

            common_items.append(
                {
                    "Título": display_title,
                    "Año": display_year,
                    f"Nota {self.user1}": int(avg2) if avg2 is not None else None,
                    f"Nota {self.user2}": int(avg1) if avg1 is not None else None,
                    "Nota media": f"{avg_both:.2f}" if avg_both is not None else None,
                }
            )

        # 4) Sort by combined_avg descending, treating None as very low
        #    (We can use -9999 or any sentinel for None)
        def sort_key(item):
            val = item["Nota media"]
            return val if val is not None else "-9999"

        common_items.sort(key=sort_key, reverse=True)
        return common_items[:10]

    def section_last_seen(self, lbm: LetterboxdManager):
        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{lbm.user}</span></span>',
            unsafe_allow_html=True,
        )

        for entry in lbm.diary_entries[:10]:
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

        st.metric(
            label="Películas en los últimos 7 días",
            value=lbm.weekly_film_count.this_week,
            delta=lbm.weekly_film_count.this_week - lbm.weekly_film_count.last_week,
            help="La diferencia es el número de películas vistas en los últimos 7 días comparado con las vistas en los 7 días anteriores",
        )

    def section_speed_and_estimate(
        self, lbm: LetterboxdManager, column: delta_generator.DeltaGenerator
    ):
        today = datetime.date.today()
        days_in_year = (
            366
            if (
                today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
            )
            else 365
        )
        projection = lbm.rate * days_in_year

        st.markdown(
            f'<span class="subsection">Participante: <span style="color: #2b7bba;">{lbm.user}</span></span>',
            unsafe_allow_html=True,
        )
        st.write("**Películas totales:**", lbm.film_count.total)
        st.write("**Películas Este Año:**", lbm.film_count.this_year)

        st.write(f"Racha actual: **{lbm.streak.current_streak}** días")
        st.write(f"Racha más larga: **{lbm.streak.longest_streak}** días")

        st.write("**Velocidad:**", f"{lbm.rate:.2f} pelis/día")
        column.metric(
            f"Proyección ({datetime.date.today().year})", f"{int(projection)}"
        )

        if lbm.highlights:
            st.info(f"Fun fact: {random.choice(lbm.highlights)}")

    def main(self):
        st.markdown(
            """
            <style>
            body {
                background: linear-gradient(to bottom right, #e8f9fd, #ffffff);
            }
            .big-title {
                font-size: 2em;
                font-weight: bold;
                color: #2b7bba;
                text-align: center;
                text-transform: uppercase;
            }
            .section-title {
                font-size: 1.8em;
                font-weight: bold;
                color: #2b7bba;
                text-align: center;
                text-decoration: underline;
                margin-bottom: 20px;
            }
            .subsection {
                font-size: 1.1em;
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
        st.markdown(
            '<div class="section-title">Últimas Pelis Vistas</div>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2, gap="large")
        with col1:
            self.section_last_seen(self.lbm1)
        with col2:
            self.section_last_seen(self.lbm2)

        message = ""
        if (
            self.lbm1.weekly_film_count.this_week
            > self.lbm2.weekly_film_count.this_week
        ):
            st.warning(f"{self.user1} va ganando los últimos 7 días! 🏆", icon="⚠️")
        elif (
            self.lbm2.weekly_film_count.this_week
            > self.lbm1.weekly_film_count.this_week
        ):
            st.warning(f"{self.user2} va ganando los últimos 7 días! 🏆", icon="⚠️")
        else:
            st.warning("Hay un empate en los últimos 7 días! 🤝", icon="⚠️")

        st.markdown(message, unsafe_allow_html=True)

        st.markdown(
            '<div class="section-title">📊 Algunas Métricas de Rendimiento 📊</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            self.section_speed_and_estimate(self.lbm1, col1)
        with col2:
            self.section_speed_and_estimate(self.lbm2, col2)

        self.calculate_gap()

        st.markdown(
            f'<div class="section-title">Total Películas (a {datetime.date.today().strftime("%b %d")})</div>',
            unsafe_allow_html=True,
        )
        df = self.calculate_accumulated_movies()
        st.line_chart(df[[self.lbm1.user, self.lbm2.user]], use_container_width=True)

        st.markdown(
            f'<div class="section-title">Diagrama de Venn</div>',
            unsafe_allow_html=True,
        )
        self.plot_venn_diagram()

        st.markdown(
            f'<div class="section-title">Top 10 Películas en Común</div>',
            unsafe_allow_html=True,
        )
        st.write("Las películas que ambos han visto, ordenadas por nota media")
        top_10_common = self.top_common_by_avg_rating()

        if not top_10_common:
            st.write("No hay películas en común!")
        else:
            # Convert to DataFrame for a nice table
            df_top = pd.DataFrame(top_10_common)
            st.table(df_top)

        st.markdown("<hr class='solid'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='big-title'>Que no mueran tus ganas! ¡La gloria cinematográfica depende de ello!</div>",
            unsafe_allow_html=True,
        )

        # 5) Share This Race
        # base_url = "https://my-streamlit-deployment.com"  # or st.secrets["some_url"]
        # share_url = f"{base_url}?user1={user1}&user2={user2}"

        # tweet_text = f"Check out this Letterboxd Death Race between {user1} and {user2}!"
        # twitter_url = f"https://twitter.com/intent/tweet?text={tweet_text}&url={share_url}"

        # st.markdown(f"[Share this link]({share_url})  |  [Tweet This]({twitter_url})")
