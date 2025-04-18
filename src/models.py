import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class FilmCount:
    total: int
    this_year: int


@dataclass
class WeeklyFilmCount:
    last_week: int
    this_week: int


@dataclass
class FilmStreak:
    current_streak: int = 0
    longest_streak: int = 0


@dataclass
class DiaryEntry:
    entry_date: datetime.date
    title: str
    release_year: str
    rating: Optional[int] = None
