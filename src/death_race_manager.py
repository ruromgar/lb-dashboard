import datetime
import logging
import random
from collections import Counter
from collections import defaultdict
from typing import Dict
from typing import List
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib_venn import venn2
from matplotlib_venn import venn2_circles
from streamlit import delta_generator

from src.letterboxd_manager import LetterboxdManager
from src.utils import rating_to_stars


logger = logging.getLogger(__name__)

# -- Color palette --
BG_DARK = "#14181C"
BG_CARD = "#1B2028"
GOLD = "#E2B616"
GREEN = "#00C030"
CORAL = "#E85D50"
TEXT_LIGHT = "#D8DEE4"
TEXT_MUTED = "#99AABB"
CHART_USER1 = "#00C030"
CHART_USER2 = "#E2B616"


class DeathRaceManager:
    def __init__(
        self,
        user1: str,
        user2: str,
        feminine1: bool = False,
        feminine2: bool = False,
        cache_dir: Optional[str] = None,
    ):
        self.user1 = user1
        self.user2 = user2

        self.lbm1 = LetterboxdManager(user1, feminine=feminine1, cache_dir=cache_dir)
        self.lbm2 = LetterboxdManager(user2, feminine=feminine2, cache_dir=cache_dir)

    # ------------------------------------------------------------------ #
    #  CSS Theme
    # ------------------------------------------------------------------ #
    def _inject_css(self):
        """Inject dark cinema theme CSS."""
        st.markdown(
            f"""
            <style>
            /* -- Global overrides -- */
            .stApp {{
                background-color: {BG_DARK};
                color: {TEXT_LIGHT};
            }}

            .big-title {{
                font-size: 2.2em;
                font-weight: 800;
                text-align: center;
                text-transform: uppercase;
                letter-spacing: 2px;
                background: linear-gradient(135deg, {GOLD}, #F5D060);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.2em;
            }}

            .section-title {{
                font-size: 1.6em;
                font-weight: 700;
                text-align: center;
                margin-top: 1.5em;
                margin-bottom: 0.8em;
                padding-bottom: 0.3em;
                background: linear-gradient(135deg, {GOLD}, #F5D060);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                border-bottom: 2px solid {GOLD}40;
            }}

            .subsection {{
                font-size: 1.1em;
                color: {GOLD};
                font-weight: 600;
            }}

            .winning {{
                color: {GREEN};
                font-weight: bold;
            }}

            .losing {{
                color: {CORAL};
                font-weight: bold;
            }}

            hr.solid {{
                border: 1px solid {GOLD}30;
            }}

            /* Narrator block */
            .narrator {{
                background: linear-gradient(135deg, {BG_CARD}, #232B35);
                border-left: 4px solid {GOLD};
                border-radius: 8px;
                padding: 1.2em 1.5em;
                margin: 1em 0;
                font-style: italic;
                font-size: 1.15em;
                color: {TEXT_LIGHT};
                line-height: 1.6;
            }}

            /* Film entry cards */
            .film-card {{
                background: {BG_CARD};
                border: 1px solid #2A3440;
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 8px;
                transition: border-color 0.2s;
            }}
            .film-card:hover {{
                border-color: {GOLD}60;
            }}
            .film-date {{
                color: {TEXT_MUTED};
                font-size: 0.85em;
                margin-bottom: 2px;
            }}
            .film-title {{
                color: {TEXT_LIGHT};
                font-weight: 600;
            }}
            .film-rating {{
                color: {GOLD};
                font-weight: bold;
                float: right;
            }}
            .film-badges {{
                margin-top: 3px;
            }}
            .film-badge {{
                display: inline-block;
                font-size: 0.7em;
                padding: 1px 6px;
                border-radius: 4px;
                margin-right: 4px;
            }}
            .badge-liked {{
                background: {CORAL}30;
                color: {CORAL};
            }}
            .badge-rewatch {{
                background: {GREEN}30;
                color: {GREEN};
            }}

            /* Taste labels */
            .taste-badge {{
                display: inline-block;
                background: {GOLD}20;
                color: {GOLD};
                border: 1px solid {GOLD}40;
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 0.8em;
                margin: 2px 3px;
                font-weight: 600;
            }}

            /* Compatibility score */
            .compat-score {{
                font-size: 3em;
                font-weight: 800;
                text-align: center;
                background: linear-gradient(135deg, {GOLD}, {GREEN});
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .compat-label {{
                text-align: center;
                font-size: 1.2em;
                color: {TEXT_MUTED};
                margin-top: -0.5em;
            }}

            /* Avatar styling */
            .avatar-container {{
                text-align: center;
                margin-bottom: 0.5em;
            }}
            .avatar-container img {{
                border-radius: 50%;
                border: 3px solid {GOLD};
                width: 80px;
                height: 80px;
                object-fit: cover;
            }}
            .avatar-name {{
                font-size: 1.3em;
                font-weight: 700;
                color: {TEXT_LIGHT};
                margin-top: 0.3em;
            }}

            /* Milestone alert */
            .milestone {{
                background: linear-gradient(135deg, {GOLD}15, {GREEN}15);
                border: 1px solid {GOLD}40;
                border-radius: 8px;
                padding: 0.8em 1.2em;
                text-align: center;
                margin: 0.5em 0;
                color: {GOLD};
                font-weight: 600;
            }}

            /* Common films table styling */
            .common-film-card {{
                background: {BG_CARD};
                border: 1px solid #2A3440;
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 6px;
            }}
            .common-film-title {{
                font-weight: 600;
                color: {TEXT_LIGHT};
            }}
            .common-film-ratings {{
                color: {TEXT_MUTED};
                font-size: 0.9em;
                margin-top: 3px;
            }}
            .common-film-avg {{
                color: {GOLD};
                font-weight: bold;
                float: right;
                font-size: 1.1em;
            }}

            /* Favourites */
            .fav-list {{
                color: {TEXT_MUTED};
                font-size: 0.85em;
                margin-top: 0.3em;
            }}

            /* Busiest day callout */
            .busiest-day {{
                background: {BG_CARD};
                border: 1px solid {GOLD}30;
                border-radius: 8px;
                padding: 8px 14px;
                text-align: center;
                color: {TEXT_MUTED};
                font-size: 0.9em;
                margin-top: 0.5em;
            }}
            .busiest-day strong {{
                color: {GOLD};
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------ #
    #  Race Narrator
    # ------------------------------------------------------------------ #
    def _get_narrator_text(self) -> str:
        """Generate a cinematic narrator blurb based on the race state."""
        gap = self.lbm1.film_count.this_year - self.lbm2.film_count.this_year
        abs_gap = abs(gap)
        leader = self.user1 if gap > 0 else self.user2
        trailer = self.user2 if gap > 0 else self.user1
        leader_rate = self.lbm1.rate if gap > 0 else self.lbm2.rate
        trailer_rate = self.lbm2.rate if gap > 0 else self.lbm1.rate

        if gap == 0:
            templates = [
                f"Empate absoluto. {self.user1} y {self.user2} van codo con codo, "
                "como dos pistoleros en un duelo a mediodia. El proximo movimiento lo decide todo.",
                f"Ni un milimetro de ventaja. {self.user1} y {self.user2} avanzan sincronizados, "
                "como dos relojes que marcan la misma hora. La tension es insoportable.",
            ]
        elif abs_gap <= 3:
            templates = [
                f"Se respira la tension. Solo {abs_gap} {'pelicula separa' if abs_gap == 1 else 'peliculas separan'} "
                f"a {leader} de {trailer}. Esto se decide en un fin de semana.",
                f"Cuello con cuello. {leader} lidera por {abs_gap}, pero {trailer} "
                "le pisa los talones. Un maraton nocturno podria cambiar la historia.",
            ]
        elif abs_gap <= 10:
            comeback = trailer_rate > leader_rate
            if comeback:
                templates = [
                    f"{leader} mantiene una ventaja de {abs_gap} peliculas, pero atencion: "
                    f"{trailer} ha pisado el acelerador. La remontada esta en marcha.",
                    f"Parece comodo para {leader} con {abs_gap} de ventaja... pero las "
                    f"estadisticas no mienten: {trailer} va mas rapido. Se acerca la tormenta.",
                ]
            else:
                templates = [
                    f"{leader} domina con {abs_gap} peliculas de ventaja y no afloja el ritmo. "
                    f"{trailer} necesita un milagro cinefilo.",
                    f"Con {abs_gap} peliculas de margen, {leader} controla la carrera. "
                    f"Pero en este deporte, una semana lo cambia todo.",
                ]
        else:
            templates = [
                f"{leader} ha abierto una brecha de {abs_gap} peliculas. "
                f"A este ritmo, {trailer} necesitaria vivir dentro de un cine para recortar.",
                f"Dominio aplastante. {leader} vuela con {abs_gap} peliculas de ventaja. "
                f"{trailer}, si estas leyendo esto... la carrera aun no ha terminado.",
            ]

        return random.choice(templates)

    # ------------------------------------------------------------------ #
    #  User Avatar + Labels header
    # ------------------------------------------------------------------ #
    def _render_user_header(self, lbm: LetterboxdManager):
        """Render avatar, name, taste labels, and favourites for a user."""
        avatar_html = ""
        if lbm.profile.avatar_url:
            avatar_html = f'<img src="{lbm.profile.avatar_url}" alt="{lbm.user}">'

        labels_html = ""
        for label in lbm.taste_labels:
            labels_html += f'<span class="taste-badge">{label}</span>'

        fav_html = ""
        if lbm.profile.favourite_films:
            films_str = " / ".join(lbm.profile.favourite_films[:4])
            fav_html = f'<div class="fav-list">Favoritas: {films_str}</div>'

        html = f"""
        <div class="avatar-container">
            {avatar_html}
            <div class="avatar-name">{lbm.user}</div>
            <div>{labels_html}</div>
            {fav_html}
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    # ------------------------------------------------------------------ #
    #  Milestone Alerts
    # ------------------------------------------------------------------ #
    def _check_milestones(self, lbm: LetterboxdManager):
        """Show celebratory message if near a milestone."""
        total = lbm.film_count.total
        # Check proximity to next milestone (multiples of 50)
        next_milestone = ((total // 50) + 1) * 50
        distance = next_milestone - total
        if distance <= 5:
            st.markdown(
                f'<div class="milestone">'
                f"A solo {distance} {'pelicula' if distance == 1 else 'peliculas'} "
                f"de las {next_milestone}!</div>",
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------ #
    #  Existing data methods (enhanced)
    # ------------------------------------------------------------------ #
    def calculate_accumulated_movies(self) -> pd.DataFrame:
        """Build a DataFrame of accumulated movie counts from Jan 1 through today."""
        today = datetime.date.today()
        start_of_year = datetime.date(today.year, 1, 1)

        filtered_1 = [
            e for e in self.lbm1.diary_entries if start_of_year <= e.entry_date <= today
        ]
        filtered_2 = [
            e for e in self.lbm2.diary_entries if start_of_year <= e.entry_date <= today
        ]

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

        all_dates = pd.date_range(start=start_of_year, end=today)
        df = pd.DataFrame({"date": all_dates})
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        df[self.user1] = [daily_counts_1.get(d.date(), 0) for d in df.index]
        df[self.user2] = [daily_counts_2.get(d.date(), 0) for d in df.index]

        # Account for films logged without diary entries
        offset_1 = max(0, self.lbm1.film_count.this_year - len(filtered_1))
        offset_2 = max(0, self.lbm2.film_count.this_year - len(filtered_2))

        df[self.user1] = df[self.user1].cumsum() + offset_1
        df[self.user2] = df[self.user2].cumsum() + offset_2

        return df

    def plot_venn_diagram(self):
        """Create a Venn diagram for shared films between users."""
        set1 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm1.diary_entries
        }
        set2 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm2.diary_entries
        }

        fig, ax = plt.subplots(figsize=(3, 3))
        fig.patch.set_facecolor(BG_DARK)
        ax.set_facecolor(BG_DARK)

        v = venn2(
            [set1, set2],
            set_labels=(self.user1, self.user2),
            set_colors=(GREEN, GOLD),
            alpha=0.5,
            ax=ax,
        )

        venn2_circles(
            [set1, set2], linestyle="solid", ax=ax, linewidth=1, color=TEXT_MUTED
        )

        region_ids = ["10", "01", "11"]
        for rid in region_ids:
            lbl = v.get_label_by_id(rid)
            if lbl:
                lbl.set_color(TEXT_LIGHT)
                lbl.set_bbox(dict(facecolor=BG_CARD, alpha=0.7, edgecolor="none"))
                lbl.set_fontsize(8)

        if v.set_labels is not None:
            for label in v.set_labels:
                if label:
                    label.set_fontsize(8)
                    label.set_fontweight("bold")
                    label.set_color(TEXT_LIGHT)

        ax.set_axis_off()
        st.pyplot(fig)

    def calculate_gap(self):
        gap = self.lbm1.film_count.total - self.lbm2.film_count.total

        st.markdown(f"**Diferencia actual**: `{abs(gap)}`")

        if gap > 0 and self.lbm2.rate > self.lbm1.rate:
            daily_diff = self.lbm2.rate - self.lbm1.rate
            days_to_catch = gap / daily_diff
            st.success(
                f"{self.lbm2.user} va por detras por {abs(gap)} peliculas, **pero** esta remontando a una velocidad de ~{daily_diff:.2f} peliculas/dia."
                f" La estimacion es de **{days_to_catch:.1f} dias** para alcanzar a {self.lbm1.user}!"
            )
        elif gap < 0 and self.lbm1.rate > self.lbm2.rate:
            gap = abs(gap)
            daily_diff = self.lbm1.rate - self.lbm2.rate
            days_to_catch = gap / daily_diff
            st.success(
                f"{self.lbm1.user} va por detras por {gap} peliculas, **pero** esta remontando a una velocidad de ~{daily_diff:.2f} peliculas/dia."
                f" La estimacion es de **{days_to_catch:.1f} dias** para alcanzar a {self.lbm2.user}!"
            )
        else:
            if gap == 0:
                st.warning(
                    f"{self.lbm1.user} y {self.lbm2.user} estan **empatados** en {datetime.date.today().year}!"
                )
            elif gap > 0 and self.lbm1.rate >= self.lbm2.rate:
                st.warning(
                    f"{self.lbm1.user} lleva {gap} peliculas de ventaja **y** va a mas velocidad. La diferencia va a **aumentar!**"
                )
            elif gap < 0 and self.lbm2.rate >= self.lbm1.rate:
                st.warning(
                    f"{self.lbm2.user} lleva {abs(gap)} peliculas de ventaja **y** va a mas velocidad. La diferencia va a **aumentar!**"
                )

        message = ""
        if self.lbm1.film_count.total - self.lbm2.film_count.total > 0:
            message = f"<h3 style='text-align:center;'><span class='winning'>{self.lbm1.user} va ganando!</span></h3>"
        elif self.lbm1.film_count.total - self.lbm2.film_count.total < 0:
            message = f"<h3 style='text-align:center;'><span class='winning'>{self.lbm2.user} va ganando!</span></h3>"
        else:
            message = "<h3 style='text-align:center;'>Empate!</h3>"

        st.markdown(message, unsafe_allow_html=True)

    def top_common_by_avg_rating(self):
        """Find films both users watched and compute combined average rating."""
        user1_ratings: Dict[tuple, List[int]] = defaultdict(list)
        user1_watched: set = set()

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

        common_keys = user1_watched & user2_watched

        common_items = []
        for key in common_keys:
            r1_list = user1_ratings.get(key, [])
            avg1 = (sum(r1_list) / len(r1_list)) if r1_list else None

            r2_list = user2_ratings.get(key, [])
            avg2 = (sum(r2_list) / len(r2_list)) if r2_list else None

            if avg1 is None and avg2 is None:
                avg_both = None
            elif avg1 is None:
                avg_both = avg2
            elif avg2 is None:
                avg_both = avg1
            else:
                avg_both = (avg1 + avg2) / 2

            display_title = key[0].title()
            display_year = key[1]

            common_items.append(
                {
                    "title": display_title,
                    "year": display_year,
                    "rating1": avg1,
                    "rating2": avg2,
                    "avg": avg_both,
                }
            )

        def sort_key(item):
            val = item["avg"]
            return val if val is not None else -9999

        common_items.sort(key=sort_key, reverse=True)
        return common_items[:10]

    # ------------------------------------------------------------------ #
    #  New Sections
    # ------------------------------------------------------------------ #
    def section_last_seen(self, lbm: LetterboxdManager):
        for entry in lbm.diary_entries[:10]:
            date_str = entry.entry_date.strftime("%b %d")
            rating_str = (
                rating_to_stars(entry.rating) if entry.rating is not None else "-"
            )

            badges = ""
            if entry.liked:
                badges += '<span class="film-badge badge-liked">Liked</span>'
            if entry.is_rewatch:
                badges += '<span class="film-badge badge-rewatch">Rewatch</span>'

            badges_div = f'<div class="film-badges">{badges}</div>' if badges else ""

            html_block = f"""
            <div class="film-card">
                <div class="film-date">{date_str}</div>
                <div>
                    <span class="film-title">{entry.title} ({entry.release_year})</span>
                    <span class="film-rating">{rating_str}</span>
                </div>
                {badges_div}
            </div>
            """
            st.markdown(html_block, unsafe_allow_html=True)

        st.metric(
            label="Peliculas en los ultimos 7 dias",
            value=lbm.weekly_film_count.this_week,
            delta=lbm.weekly_film_count.this_week - lbm.weekly_film_count.last_week,
            help="La diferencia es el numero de peliculas vistas en los ultimos 7 dias comparado con las vistas en los 7 dias anteriores",
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

        st.write("**Peliculas totales:**", lbm.film_count.total)
        st.write("**Peliculas Este Ano:**", lbm.film_count.this_year)

        st.write(f"Racha actual: **{lbm.streak.current_streak}** dias")
        st.write(f"Racha mas larga: **{lbm.streak.longest_streak}** dias")

        st.write("**Velocidad:**", f"{lbm.rate:.2f} pelis/dia")
        column.metric(
            f"Proyeccion ({datetime.date.today().year})", f"{int(projection)}"
        )

        # Busiest day
        if lbm.busiest_day:
            date, count = lbm.busiest_day
            st.markdown(
                f'<div class="busiest-day">Dia mas intenso: '
                f"<strong>{date.strftime('%b %d')}</strong> con "
                f"<strong>{count} peliculas</strong></div>",
                unsafe_allow_html=True,
            )

        # Milestone check
        self._check_milestones(lbm)

        if lbm.highlights:
            st.info(f"Fun fact: {random.choice(lbm.highlights)}")

    # ------------------------------------------------------------------ #
    #  New Charts
    # ------------------------------------------------------------------ #
    def _apply_dark_style(self, fig, ax):
        """Apply dark theme to a matplotlib figure."""
        fig.patch.set_facecolor(BG_DARK)
        ax.set_facecolor(BG_CARD)
        ax.tick_params(colors=TEXT_MUTED, which="both")
        ax.xaxis.label.set_color(TEXT_MUTED)
        ax.yaxis.label.set_color(TEXT_MUTED)
        ax.title.set_color(TEXT_LIGHT)
        for spine in ax.spines.values():
            spine.set_color(TEXT_MUTED + "40")

    def plot_decade_distribution(self):
        """Plot films per decade for each user as a grouped bar chart."""

        def get_decades(entries: list) -> Counter:
            decades: Counter = Counter()
            for e in entries:
                if e.release_year.isdigit():
                    decade = (int(e.release_year) // 10) * 10
                    decades[decade] += 1
            return decades

        d1 = get_decades(self.lbm1.diary_entries)
        d2 = get_decades(self.lbm2.diary_entries)

        all_decades = sorted(set(d1.keys()) | set(d2.keys()))
        if not all_decades:
            return

        vals1 = [d1.get(d, 0) for d in all_decades]
        vals2 = [d2.get(d, 0) for d in all_decades]
        labels = [f"{d}s" for d in all_decades]

        x = np.arange(len(all_decades))
        width = 0.35

        fig, ax = plt.subplots(figsize=(8, 4))
        self._apply_dark_style(fig, ax)

        ax.bar(
            x - width / 2, vals1, width, label=self.user1, color=CHART_USER1, alpha=0.8
        )
        ax.bar(
            x + width / 2, vals2, width, label=self.user2, color=CHART_USER2, alpha=0.8
        )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel("Peliculas")
        ax.legend(facecolor=BG_CARD, edgecolor=TEXT_MUTED, labelcolor=TEXT_LIGHT)
        fig.tight_layout()

        st.pyplot(fig)

    def plot_rating_distribution(self):
        """Overlaid histogram of ratings for each user."""
        ratings1 = [e.rating for e in self.lbm1.diary_entries if e.rating is not None]
        ratings2 = [e.rating for e in self.lbm2.diary_entries if e.rating is not None]

        if not ratings1 and not ratings2:
            return

        fig, ax = plt.subplots(figsize=(8, 4))
        self._apply_dark_style(fig, ax)

        bins = np.arange(0.5, 11.5, 1)
        if ratings1:
            ax.hist(
                ratings1,
                bins=bins,
                alpha=0.6,
                label=self.user1,
                color=CHART_USER1,
                edgecolor=CHART_USER1,
            )
        if ratings2:
            ax.hist(
                ratings2,
                bins=bins,
                alpha=0.6,
                label=self.user2,
                color=CHART_USER2,
                edgecolor=CHART_USER2,
            )

        ax.set_xticks(range(1, 11))
        ax.set_xticklabels([rating_to_stars(i) for i in range(1, 11)], fontsize=7)
        ax.set_ylabel("Peliculas")
        ax.legend(facecolor=BG_CARD, edgecolor=TEXT_MUTED, labelcolor=TEXT_LIGHT)
        fig.tight_layout()

        st.pyplot(fig)

    def plot_weekday_activity(self):
        """Plot diary entries per day of week as a grouped bar chart."""

        def get_weekday_counts(entries: list) -> Counter:
            counts: Counter = Counter()
            for e in entries:
                counts[e.entry_date.weekday()] += 1
            return counts

        w1 = get_weekday_counts(self.lbm1.diary_entries)
        w2 = get_weekday_counts(self.lbm2.diary_entries)

        days = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        vals1 = [w1.get(i, 0) for i in range(7)]
        vals2 = [w2.get(i, 0) for i in range(7)]

        x = np.arange(7)
        width = 0.35

        fig, ax = plt.subplots(figsize=(8, 4))
        self._apply_dark_style(fig, ax)

        ax.bar(
            x - width / 2, vals1, width, label=self.user1, color=CHART_USER1, alpha=0.8
        )
        ax.bar(
            x + width / 2, vals2, width, label=self.user2, color=CHART_USER2, alpha=0.8
        )

        ax.set_xticks(x)
        ax.set_xticklabels(days)
        ax.set_ylabel("Peliculas")
        ax.legend(facecolor=BG_CARD, edgecolor=TEXT_MUTED, labelcolor=TEXT_LIGHT)
        fig.tight_layout()

        st.pyplot(fig)

    # ------------------------------------------------------------------ #
    #  Compatibility Score
    # ------------------------------------------------------------------ #
    def calculate_compatibility(self) -> float:
        """Calculate a film compatibility percentage between both users."""
        set1 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm1.diary_entries
        }
        set2 = {
            (e.title.strip().lower(), e.release_year.strip())
            for e in self.lbm2.diary_entries
        }

        intersection = set1 & set2
        union = set1 | set2

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # Rating similarity for common rated films
        r1_map: Dict[tuple, float] = {}
        for e in self.lbm1.diary_entries:
            if e.rating is not None:
                key = (e.title.strip().lower(), e.release_year.strip())
                r1_map[key] = e.rating

        r2_map: Dict[tuple, float] = {}
        for e in self.lbm2.diary_entries:
            if e.rating is not None:
                key = (e.title.strip().lower(), e.release_year.strip())
                r2_map[key] = e.rating

        common_rated = set(r1_map.keys()) & set(r2_map.keys())
        if common_rated:
            avg_diff = sum(abs(r1_map[k] - r2_map[k]) for k in common_rated) / len(
                common_rated
            )
            rating_similarity = 1 - (avg_diff / 10)
        else:
            rating_similarity = 0.5

        return (jaccard * 0.4 + rating_similarity * 0.6) * 100

    def _get_compatibility_label(self, score: float) -> str:
        """Return a fun label for the compatibility score."""
        if score >= 80:
            return "Almas gemelas"
        elif score >= 60:
            return "Buenos amigos"
        elif score >= 40:
            return "Conocidos"
        else:
            return "Mundos paralelos"

    # ------------------------------------------------------------------ #
    #  Enhanced Common Films
    # ------------------------------------------------------------------ #
    def section_common_films(self):
        """Render common films as styled cards."""
        top_10 = self.top_common_by_avg_rating()

        if not top_10:
            st.write("No hay peliculas en comun!")
            return

        for item in top_10:
            r1_str = (
                rating_to_stars(int(item["rating1"]))
                if item["rating1"] is not None
                else "-"
            )
            r2_str = (
                rating_to_stars(int(item["rating2"]))
                if item["rating2"] is not None
                else "-"
            )
            avg_str = (
                rating_to_stars(int(round(item["avg"])))
                if item["avg"] is not None
                else "-"
            )

            html = f"""
            <div class="common-film-card">
                <span class="common-film-avg">{avg_str}</span>
                <div class="common-film-title">{item["title"]} ({item["year"]})</div>
                <div class="common-film-ratings">
                    {self.user1}: {r1_str} &nbsp;&bull;&nbsp; {self.user2}: {r2_str}
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

    # ------------------------------------------------------------------ #
    #  Main
    # ------------------------------------------------------------------ #
    def main(self):
        self._inject_css()

        # -- Title & Narrator --
        st.markdown(
            '<div class="big-title">Letterboxd: la competicion definitiva</div>',
            unsafe_allow_html=True,
        )

        narrator_text = self._get_narrator_text()
        st.markdown(
            f'<div class="narrator">{narrator_text}</div>',
            unsafe_allow_html=True,
        )

        # -- User Headers with Avatars --
        col1, col2 = st.columns(2, gap="large")
        with col1:
            self._render_user_header(self.lbm1)
        with col2:
            self._render_user_header(self.lbm2)

        # -- Last Seen Films --
        st.markdown(
            '<div class="section-title">Ultimas Pelis Vistas</div>',
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
            message = f"**{self.user1}** va ganando los ultimos 7 dias!"
        elif (
            self.lbm2.weekly_film_count.this_week
            > self.lbm1.weekly_film_count.this_week
        ):
            message = f"**{self.user2}** va ganando los ultimos 7 dias!"
        else:
            message = "Hay un empate en los ultimos 7 dias!"

        st.info(message)

        # -- Performance Metrics --
        st.markdown(
            '<div class="section-title">Metricas de Rendimiento</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            self._render_user_header(self.lbm1)
            self.section_speed_and_estimate(self.lbm1, col1)
        with col2:
            self._render_user_header(self.lbm2)
            self.section_speed_and_estimate(self.lbm2, col2)

        self.calculate_gap()

        # -- Compatibility Score --
        st.markdown(
            '<div class="section-title">Compatibilidad Cinefila</div>',
            unsafe_allow_html=True,
        )
        compat = self.calculate_compatibility()
        label = self._get_compatibility_label(compat)
        st.markdown(
            f'<div class="compat-score">{compat:.0f}%</div>'
            f'<div class="compat-label">{label}</div>',
            unsafe_allow_html=True,
        )

        # -- Accumulated Movies Chart --
        st.markdown(
            f'<div class="section-title">Total Peliculas ({datetime.date.today().strftime("%b %d")})</div>',
            unsafe_allow_html=True,
        )
        df = self.calculate_accumulated_movies()
        st.line_chart(df[[self.lbm1.user, self.lbm2.user]], use_container_width=True)

        # -- New Charts --
        st.markdown(
            '<div class="section-title">Distribucion por Decada</div>',
            unsafe_allow_html=True,
        )
        self.plot_decade_distribution()

        st.markdown(
            '<div class="section-title">Distribucion de Notas</div>',
            unsafe_allow_html=True,
        )
        self.plot_rating_distribution()

        st.markdown(
            '<div class="section-title">Actividad por Dia de la Semana</div>',
            unsafe_allow_html=True,
        )
        self.plot_weekday_activity()

        # -- Venn Diagram --
        st.markdown(
            '<div class="section-title">Diagrama de Venn</div>',
            unsafe_allow_html=True,
        )
        self.plot_venn_diagram()

        # -- Common Films --
        st.markdown(
            '<div class="section-title">Top 10 Peliculas en Comun</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="text-align:center; color:{TEXT_MUTED};">Las peliculas que ambos han visto, ordenadas por nota media</p>',
            unsafe_allow_html=True,
        )
        self.section_common_films()

        # -- Footer --
        st.markdown("<hr class='solid'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='big-title'>Que no mueran tus ganas! La gloria cinematografica depende de ello!</div>",
            unsafe_allow_html=True,
        )
