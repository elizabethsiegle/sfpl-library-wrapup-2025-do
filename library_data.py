import asyncio
from typing import Tuple
import pandas as pd

# Reuse the existing scraper/function
from library_app import sfpl_2025

def get_library_and_goodreads() -> Tuple[pd.DataFrame, str, object, pd.DataFrame, dict, str]:
    """Fetch library + Goodreads + Strava artifacts without filesystem I/O.
    Returns: (lib_df, wrapup_text, goodreads_book_stats, goodreads_books_this_year, workout_stats, stats_json)
    """
    result = asyncio.run(sfpl_2025())
    # Safely unpack with backward compatibility
    lib_df = result[0] if isinstance(result, (list, tuple)) and len(result) > 0 else pd.DataFrame()
    content = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else ""
    goodreads_book_stats = result[2] if isinstance(result, (list, tuple)) and len(result) > 2 else {}
    goodreads_books_this_year = result[3] if isinstance(result, (list, tuple)) and len(result) > 3 else pd.DataFrame()
    workout_stats = result[4] if isinstance(result, (list, tuple)) and len(result) > 4 else {}
    stats_json = result[5] if isinstance(result, (list, tuple)) and len(result) > 5 else "{}"
    return lib_df, content, goodreads_book_stats, goodreads_books_this_year, workout_stats, stats_json
