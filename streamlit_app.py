from src.auth import check_authentication
from src.death_race_manager import DeathRaceManager


if __name__ == "__main__":
    if check_authentication():
        drm = DeathRaceManager("unnonueve", "garciamorales", feminine2=True)
        drm.main()
