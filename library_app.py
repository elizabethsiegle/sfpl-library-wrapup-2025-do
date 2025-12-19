import asyncio
import difflib
import json
import os
import re
import pandas as pd
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv

from library_goodreads_helpers import clean_books_df, compute_book_stats
from strava_helpers import clean_workouts_df, compute_workout_stats

# --- CONFIGURATION & CONSTANTS ---
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
MODEL_ACCESS_KEY = os.getenv("MODEL_ACCESS_KEY")

# Hardcoded paths for CSV files from Goodreads and Strava
GOODREADS_PATH = os.path.expanduser('~/Desktop/demos/goodreads-and-strava-wrapup/data_csvs/goodreads_library_export.csv')
STRAVA_PATH = os.path.expanduser('~/Desktop/demos/goodreads-and-strava-wrapup/data_csvs/activities.csv')

# API Config
LLM_URL = "https://inference.do-ai.run/v1/chat/completions"
LLM_MODEL = "llama3.3-70b-instruct"

# Scraping Selectors (Preserved exactly to ensure stability)
BOOK_ITEM_SELECTOR = ".cp-batch-actions-list-item"
NEXT_BUTTON_XPATH = "/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]/section/nav/ul[1]/li[9]/a"
LOGIN_USER_XPATH = '/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/div[2]/input'
LOGIN_PASS_XPATH = '/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/div[3]/input'
LOGIN_BTN_XPATH = '/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/p[2]/input'


# text x data helpers

def _normalize_title(s: str) -> str:
    """Normalize titles to improve matching between SFPL and Goodreads."""
    if not isinstance(s, str):
        s = str(s or "")
    t = s.strip().lower()
    # Remove bracketed content
    t = re.sub(r"\s*[\[(].*?[\])]\s*", " ", t)
    # Cut at subtitle separators
    for sep in (":", " - ", "-", " — ", "—"):
        if sep in t:
            t = t.split(sep, 1)[0]
    # Remove punctuation and collapse spaces
    t = re.sub(r"[\.,;!?'\"]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def get_goodreads_data():
    """Loads, cleans, and filters Goodreads data for 2025."""
    print(f'Reading Goodreads CSV from {GOODREADS_PATH}')
    try:
        df = pd.read_csv(GOODREADS_PATH)
        cleaned = clean_books_df(df)
        
        if isinstance(cleaned, pd.DataFrame) and not cleaned.empty:
            # Create masks for Date and Shelf
            date_col = 'Date Read' if 'Date Read' in cleaned.columns else None
            shelf_col = 'Exclusive Shelf' if 'Exclusive Shelf' in cleaned.columns else None
            
            mask_2025 = (cleaned[date_col].astype(str).str.contains('2025', na=False)) if date_col else pd.Series([False] * len(cleaned))
            shelf_mask = (cleaned[shelf_col].astype(str).str.lower().eq('read')) if shelf_col else pd.Series([True] * len(cleaned))
            
            filtered_df = cleaned[mask_2025 & shelf_mask].copy()
            stats = compute_book_stats(filtered_df)
            return filtered_df, stats
    except Exception as e:
        print(f"Error processing Goodreads data: {e}")
    
    return pd.DataFrame(), {}

def get_strava_data():
    """Loads and processes Strava workout data for 2025."""
    print(f'Reading Strava CSV from {STRAVA_PATH}')
    try:
        df = pd.read_csv(STRAVA_PATH)
        cleaned = clean_workouts_df(df)
        workouts_2025 = cleaned[cleaned['Activity Date'].dt.year == 2025].copy()
        
        stats = compute_workout_stats(workouts_2025)
        
        # Calculate monthly stats
        by_month = {}
        by_month_by_type = {}

        if 'Activity Date' in workouts_2025.columns:
            w = workouts_2025.copy()
            w['month'] = w['Activity Date'].dt.month
            type_col = 'Activity Type' if 'Activity Type' in w.columns else None

            if type_col:
                grouped = w.groupby(['month', type_col], as_index=False).size().rename(columns={'size': 'count'})
                for _, row in grouped.iterrows():
                    m = int(row['month'])
                    t = str(row[type_col])
                    c = int(row['count'])
                    by_month_by_type.setdefault(m, {})
                    by_month_by_type[m][t] = by_month_by_type[m].get(t, 0) + c
                # Sum totals based on type breakdown
                by_month = {m: int(sum((v or 0) for v in type_counts.values())) for m, type_counts in by_month_by_type.items()}
            else:
                # Fallback to simple counts
                by_month = {int(k): int(v) for k, v in w['month'].value_counts().sort_index().to_dict().items()}
        
        stats['by_month'] = by_month
        stats['by_month_by_type'] = by_month_by_type
        
        return workouts_2025, stats
    except Exception as e:
        print(f"Error processing Strava data: {e}")
        return pd.DataFrame(), {}

def merge_ratings(lib_df, gr_df):
    """Merges Goodreads ratings into the Library DataFrame using fuzzy matching."""
    try:
        print('Attempting Goodreads ratings merge…')
        if not gr_df.empty and 'Title' in gr_df.columns:
            gr = gr_df[['Title', 'My Rating']].copy()
            gr['__key'] = gr['Title'].map(_normalize_title)
            lib_df['__key'] = lib_df['title'].map(_normalize_title)
            
            rating_map = gr.set_index('__key')['My Rating']
            lib_df['rating'] = lib_df['__key'].map(rating_map)
            
            # Fuzzy fallback for missing ratings
            gr_keys = list(gr['__key'].dropna().unique())
            
            def _fuzzy_lookup(k):
                if not isinstance(k, str) or not k: return None
                match = difflib.get_close_matches(k, gr_keys, n=1, cutoff=0.9)
                return rating_map.get(match[0]) if match else None

            na_mask = lib_df['rating'].isna()
            if na_mask.any():
                lib_df.loc[na_mask, 'rating'] = lib_df.loc[na_mask, '__key'].map(_fuzzy_lookup)
            
            lib_df['rating'] = lib_df['rating'].fillna('NR')
            print(f"Ratings matched: {(lib_df['rating'] != 'NR').sum()}/{len(lib_df)}")
            lib_df = lib_df.drop(columns=['__key'])
        else:
            print('Skipping ratings merge: no 2025 Goodreads titles available.')
    except Exception as e:
        print('Could not merge Goodreads ratings:', e)
    return lib_df


# scraping logic

async def scrape_sfpl_books(page):
    """Scrapes 2025 books from SFPL Recently Returned page."""
    library_books = []
    page_index = 1
    
    while True:
        print(f"7.{page_index} Waiting for book items on page {page_index}.")
        try:
            await page.wait_for_selector(BOOK_ITEM_SELECTOR, state="visible", timeout=15000)
        except Exception:
            pass # Continue to count check
            
        items_locator = page.locator(BOOK_ITEM_SELECTOR)
        count = await items_locator.count()

        # Standard CSS Selector
        print(f"Found {count} items via CSS on page {page_index}.")
        stop_loop = False
        for i in range(count):
            item = items_locator.nth(i)
            text = await item.inner_text()
            
            # Year Check
            year = None
            lower_text = text.lower()
            if "checked out on" in lower_text:
                snippet = text[lower_text.index("checked out on"):].split('\n')[0][:64]
                if "2025" in snippet: year = 2025
                elif "2024" in snippet: year = 2024
            
            if year == 2024:
                stop_loop = True; break
            
            if year == 2025:
                try: title = await item.locator("css=h2.cp-title .title-content").inner_text()
                except: title = "(unknown title)"
                
                try: author = await item.locator("css=.cp-by-author-block .author-link").inner_text()
                except: author = "(unknown author)"
                
                print(f"Found: {title}")
                library_books.append({"title": title, "author": author})

        if stop_loop: break

        # Standard Pagination
        try:
            await page.locator(f"xpath={NEXT_BUTTON_XPATH}").click()
            await page.wait_for_load_state('networkidle')
            page_index += 1
        except:
            print("No next page button found; finishing up!")
            break
            
    return pd.DataFrame(library_books)[["title", "author"]] if library_books else pd.DataFrame(columns=["title", "author"])


# LLM call

def generate_llm_wrapup(lib_df, workout_stats):
    """Calls external LLM to generate summary."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MODEL_ACCESS_KEY}"
    }
    messages = [
        {"role": "system", "content": "You are an expert librarian and workout advocate who loves books, exercise, and economics. You must only output what is asked of you, do not return reasoning_content. Just have fun and advocate for libraries, being outside, and tell people how much money they saved this year based on how many books they checked out from the library."},
        {"role": "user", "content": (
            "Generate a brief year-end wrap-up paragraph for the user based on their reading and Strava activities in the tone of Spotify wrapped. It should be funny and accurate. There's data from SF Public Library and Goodreads and Strava. "
            "Tell them how many books they checked out, some highlights, and estimate how much money they saved by going to the library. Estimate 1 book costs $23. "
            "Use the exact numeric stats provided (do not make up numbers, books, or authors). "
            "Write in a funny, friendly, engaging tone. Do not return any reasoning_content at all\n\n"
            f"Library books checked out this year: {lib_df}"
            f"\n\nWorkouts this year: {workout_stats}."
        )}
    ]
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 500}
    
    try:
        response = requests.post(LLM_URL, headers=headers, json=payload)
        data = response.json()
        return (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return ""


# main orchestrator

async def sfpl_2025():
    """Main async execution flow."""
    # 1. Fetch Library Data
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(60000)

        # Login
        await page.goto("https://sfpl.bibliocommons.com/user/login")
        await page.locator(f'xpath={LOGIN_USER_XPATH}').fill(USERNAME)
        await page.locator(f'xpath={LOGIN_PASS_XPATH}').fill(PASSWORD)
        await page.locator(f'xpath={LOGIN_BTN_XPATH}').click()
        await page.wait_for_load_state('networkidle')

        # Navigate and Scrape
        await page.goto("https://sfpl.bibliocommons.com/v2/recentlyreturned?page=1")
        lib_df = await scrape_sfpl_books(page)
        print(f"Total 2025 Library Books Found: {len(lib_df)}")

    # 2. Fetch Local CSV Data
    gr_df, gr_stats = get_goodreads_data()
    workout_df, workout_stats = get_strava_data()
    
    stats_json = json.dumps(workout_stats)
    
    # 3. Generate Content
    llm_content = generate_llm_wrapup(lib_df, workout_stats=workout_stats)
    
    # 4. Merge Data
    lib_df = merge_ratings(lib_df, gr_df)
    
    return lib_df, llm_content, gr_stats, gr_df, workout_stats, stats_json, workout_df

if __name__ == "__main__":
    # Execute Async Flow
    result = asyncio.run(sfpl_2025())
    lib_df, content, gr_stats, gr_df, workout_stats, stats_json, workout_df = result

    # Save Artifacts
    if isinstance(lib_df, pd.DataFrame) and not lib_df.empty:
        lib_df.to_csv("library_books_2025.csv", index=False)
    
    if isinstance(gr_df, pd.DataFrame) and not gr_df.empty:
        gr_df.to_csv("goodreads_books_2025.csv", index=False)
        
    if isinstance(content, str) and content:
        with open("wrapup_2025.txt", "w") as f:
            f.write(content)
            
    if isinstance(stats_json, str) and stats_json:
        with open("strava_workout_stats_2025.json", "w") as f:
            f.write(stats_json)

    # Save Stats (handling various formats)
    try:
        if isinstance(gr_stats, pd.DataFrame):
            gr_stats.to_csv("goodreads_book_stats_2025.csv", index=False)
        elif isinstance(gr_stats, dict):
            pd.DataFrame([gr_stats]).to_csv("goodreads_book_stats_2025.csv", index=False)
    except Exception:
        pass