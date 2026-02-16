def rating_to_stars(rating: int) -> str:
    """Convert a 0-10 rating to a star string.

    For instance: 10 -> "★★★★★", 9 -> "★★★★½", None -> "-"
    """
    if rating is None:
        return "-"

    stars_str = "★" * (rating // 2)
    if (rating % 2) == 1:
        stars_str += "½"
    return stars_str
