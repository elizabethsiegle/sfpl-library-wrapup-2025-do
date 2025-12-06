import pandas as pd

def clean_books_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    # Normalize expected columns if present
    for col in [
        "Date Read",
        "Original Publication Year",
        "My Rating",
        "Number of Pages",
        "Exclusive Shelf",
    ]:
        if col in out.columns:
            if col == "Date Read":
                out[col] = pd.to_datetime(out[col], errors="coerce")
            elif col in ["Original Publication Year", "My Rating", "Number of Pages"]:
                out[col] = pd.to_numeric(out[col], errors="coerce")
            elif col == "Exclusive Shelf":
                out[col] = out[col].astype(str)
    # Keep reasonable subset if present
    keep = [c for c in [
        "Title",
        "Author",
        "Date Read",
        "Original Publication Year",
        "My Rating",
        "Number of Pages",
        "Exclusive Shelf",
    ] if c in out.columns]
    return out[keep] if keep else out


def compute_book_stats(books_df: pd.DataFrame | None) -> dict:
    if books_df is None or not isinstance(books_df, pd.DataFrame) or books_df.empty:
        return {
            "avg_my_rating": 0.0,
            "total_pages": 0,
            "longest_book_title": None,
            "longest_book_pages": 0,
            "top_authors": [],
        }

    df = books_df.copy()
    # Ratings
    avg_rating = pd.to_numeric(df.get("My Rating", pd.Series(dtype=float)), errors="coerce").dropna()
    avg_my_rating = float(avg_rating.mean()) if len(avg_rating) else 0.0

    # Pages
    pages = pd.to_numeric(df.get("Number of Pages", pd.Series(dtype=float)), errors="coerce").fillna(0)
    total_pages = int(pages.sum())

    # Longest book
    longest_idx = pages.idxmax() if len(pages) else None
    if longest_idx is not None and longest_idx in df.index:
        longest_book_title = str(df.loc[longest_idx].get("Title", "")) or None
        longest_book_pages = int(pages.loc[longest_idx])
    else:
        longest_book_title = None
        longest_book_pages = 0

    # Top authors
    authors = df.get("Author")
    if authors is not None:
        top_auth = (
            authors.dropna().astype(str).value_counts().head(5).index.tolist()
        )
    else:
        top_auth = []

    return {
        "avg_my_rating": avg_my_rating,
        "total_pages": total_pages,
        "longest_book_title": longest_book_title,
        "longest_book_pages": longest_book_pages,
        "top_authors": top_auth,
    }
