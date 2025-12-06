import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import json
import os
import pandas as pd
import requests

from library_goodreads_helpers import clean_books_df, compute_book_stats
from strava_helpers import clean_workouts_df, compute_workout_stats

# Load .env file
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
MODEL_ACCESS_KEY = os.getenv("MODEL_ACCESS_KEY")

def _normalize_title(s: str) -> str:
    """Normalize titles to improve matching between SFPL and Goodreads.
    - lowercases
    - strips whitespace
    - removes content in parentheses/brackets
    - truncates at common subtitle separators (":", "-", "—")
    - removes punctuation
    - collapses multiple spaces
    """
    # Short and robust: strip noise so titles align across sources
    if not isinstance(s, str):
        s = str(s or "")
    t = s.strip().lower()
    # remove bracketed content
    import re
    t = re.sub(r"\s*[\[(].*?[\])]\s*", " ", t)
    # cut at subtitle separators
    for sep in (":", " - ", "-", " — ", "—"):
        if sep in t:
            t = t.split(sep, 1)[0]
    # remove punctuation
    t = re.sub(r"[\.,;!?'\"]", " ", t)
    # collapse spaces
    t = re.sub(r"\s+", " ", t).strip()
    return t

async def sfpl_2025():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(60000) 

        print("1. Navigating to the direct login URL.")
        await page.goto("https://sfpl.bibliocommons.com/user/login")
        
        print("2. Filling username via explicit XPath.")
        await page.locator('xpath=/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/div[2]/input').fill(USERNAME)

        print("3. Filling password via explicit XPath.")
        await page.locator('xpath=/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/div[3]/input').fill(PASSWORD)

        print("4. Clicking 'Log In' button via explicit XPath")
        await page.locator('xpath=/html/body/div[2]/div[2]/main/div/div[2]/div[1]/div/div[2]/div[1]/form/p[2]/input').click()

        print("5. Waiting for navigation after login.")
        await page.wait_for_load_state('networkidle')

        print("6. Navigating to Recently Returned page.")
        await page.goto("https://sfpl.bibliocommons.com/v2/recentlyreturned?page=1")

        # Scrape 2025 books across webpages until a 2024 item is found
        BOOK_ITEM_SELECTOR = ".cp-batch-actions-list-item"
        NEXT_BUTTON_XPATH = "/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]/section/nav/ul[1]/li[9]/a"

        library_books_2025 = []
        page_index = 1
        while True:
            print(f"7.{page_index} Waiting for book items on page {page_index}.")
            # Wait for the list container to appear; be tolerant to slow loads
            await page.wait_for_selector(BOOK_ITEM_SELECTOR, state="visible", timeout=15000)
            # Count items and iterate
            items_locator = page.locator(BOOK_ITEM_SELECTOR)
            count = await items_locator.count()
            # If count is zero, try to enumerate via full XPath index loop
            if count == 0:
                print("No items via CSS; attempting XPath enumeration.")
                # Try up to 100 entries; stop when an index doesn't exist for a while
                stop_due_to_2024 = False

                # There are 50 books per page; enumerate those indices directly
                for idx in range(1, 51):
                    # Construct the container XPath for each item index
                    container_xpath = f"/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]/div/div[2]/div[{idx}]"
                    loc = page.locator(f"xpath={container_xpath}")

                    await loc.wait_for(state="visible", timeout=1000)

                    text = await loc.inner_text()
                    # Print the title if found
                    try:
                        title_xpath = container_xpath + "/label/span[2]/span"
                        title_text = await page.locator(f"xpath={title_xpath}").inner_text()
                        print(f"Title: {title_text}")
                    except Exception:
                        pass
                    # Year parsing
                    year = None
                    lower = text.lower()
                    if "checked out on" in lower:
                        try:
                            i2 = lower.index("checked out on")
                            snippet = text[i2:i2+64]
                            if "2025" in snippet:
                                year = 2025
                            elif "2024" in snippet:
                                year = 2024
                        except Exception:
                            year = None
                    if year == 2024:
                        stop_due_to_2024 = True
                        print("Encountered a 2024 item; stopping.")
                        break
                    if year == 2025:
                        # Try to extract author
                        try:
                            author_xpath = container_xpath + "//span[contains(@class,'author-link')]"
                            author_text = await page.locator(f"xpath={author_xpath}").inner_text()
                        except Exception:
                            author_text = None
                        library_books_2025.append({
                            "title": title_text if 'title_text' in locals() else "(unknown title)",
                            "author": author_text or "(unknown author)",
                            "raw": text.strip()
                        })
                if stop_due_to_2024:
                    break
                # Next page when enumerating via XPath
                try:
                    print("Clicking next page chevron…")
                    await page.locator(f"xpath={NEXT_BUTTON_XPATH}").click()
                    await page.wait_for_load_state('networkidle')
                    page_index += 1
                    continue
                except Exception:
                    print("No next page button found; finishing.")
                    break

            print(f"Found {count} items on page {page_index}.")

            stop_due_to_2024 = False
            for i in range(count):
                item = items_locator.nth(i)
                text = await item.inner_text()
                # Print the title if available
                try:
                    title_text = await item.locator("css=h2.cp-title .title-content").inner_text()
                    print(f"Title: {title_text}")
                except Exception:
                    pass
                # Very simple parsing: look for "Checked out on:" and read the year
                year = None
                lower = text.lower()
                if "checked out on" in lower:
                    # extract substring after it
                    try:
                        idx = lower.index("checked out on")
                        snippet = text[idx: idx + 64]
                        # Expect formats like: Checked out on: Nov 10, 2025
                        if "2025" in snippet:
                            year = 2025
                        elif "2024" in snippet:
                            year = 2024
                    except Exception:
                        year = None

                if year == 2024:
                    stop_due_to_2024 = True
                    print("Encountered a 2024 item; stopping.")
                    break
                if year == 2025:
                    # Try to extract title and author from within the item
                    try:
                        title = await item.locator("css=h2.cp-title .title-content").inner_text()
                    except Exception:
                        title = None
                    try:
                        author = await item.locator("css=.cp-by-author-block .author-link").inner_text()
                    except Exception:
                        author = None
                    
                    library_books_2025.append({
                        "title": title or "(unknown title)",
                        "author": author or "(unknown author)",
                        "raw": text.strip()
                    })

            if stop_due_to_2024:
                break

            # Go to next page, if available
            try:
                print("Clicking next page arrow button...")
                await page.locator(f"xpath={NEXT_BUTTON_XPATH}").click()
                await page.wait_for_load_state('networkidle')
                page_index += 1
            except Exception:
                print("No next page button found; finishing up!")
                break

        print(f"Collected {len(library_books_2025)} books from 2025:")
        
        # Convert to DataFrame
        lib_df = pd.DataFrame(library_books_2025)[["title", "author"]]
        print('lib_df', lib_df)
        url = "https://inference.do-ai.run/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MODEL_ACCESS_KEY}"
        }
        messages = [{"role": "system", "content": "You are an expert librarian advocate who loves books and economics. You must only output what is asked of you, do not return reasoning_content. Just have fun and advocate for libraries and tell people how much money they saved this year based on how many books they checked out from the library."},
            {"role": "user", "content": (
            "Generate a brief year-end wrap-up paragraph for the user based on their reading. There's data from SF Public Library and Goodreads. Tell them how many books they checked out, some highlights, and estimate how much money they saved by going to the library. Estimate 1 book costs $23. "
            "Use the exact numeric stats provided (do not make up numbers, books, or authors). "
            "Write in a funny, friendly, engaging tone. Do not return any reasoning_content at all\n\n"
            f"Library books checked out this year: {lib_df}"
        )}]
        payload = {"model": "llama3.3-70b-instruct", "messages": messages, "temperature": 0.2, "max_tokens": 500}

        response = requests.post(url, headers=headers, json=payload)
        
        # Get Goodreads data from csv
        # Note: we clean and then filter to just the 2025 'read' shelf
        gr_path = os.path.expanduser('~/Desktop/demos/goodreads-and-strava-wrapup/data_csvs/goodreads_library_export.csv')
        print('Reading Goodreads CSV from', gr_path)
        goodreads_data = pd.read_csv(gr_path)
        goodreads_books_clean = clean_books_df(goodreads_data)
        print('books_clean', goodreads_books_clean)

        # Get Strava data from csv
        strava_path = os.path.expanduser('~/Desktop/demos/goodreads-and-strava-wrapup/data_csvs/activities.csv')
        print('Reading Strava CSV from', strava_path)
        strava_data = pd.read_csv(strava_path)
        strava_workouts_clean = clean_workouts_df(strava_data)
        print('strava_workouts_clean', strava_workouts_clean)
        
        
        # Filter Goodreads to 2025 reads; be tolerant of missing columns
        if isinstance(goodreads_books_clean, pd.DataFrame) and len(goodreads_books_clean):
            date_col = 'Date Read' if 'Date Read' in goodreads_books_clean.columns else None
            shelf_col = 'Exclusive Shelf' if 'Exclusive Shelf' in goodreads_books_clean.columns else None
            if date_col:
                date_str = goodreads_books_clean[date_col].astype(str)
                mask_2025 = date_str.str.contains('2025', na=False)
            else:
                mask_2025 = pd.Series([False] * len(goodreads_books_clean))
            if shelf_col:
                shelf_mask = goodreads_books_clean[shelf_col].astype(str).str.lower().eq('read')
            else:
                shelf_mask = pd.Series([True] * len(goodreads_books_clean))
            goodreads_books_this_year = goodreads_books_clean[mask_2025 & shelf_mask].copy()
            print('goodreads_books_this_year', goodreads_books_this_year)
        else:
            goodreads_books_this_year = pd.DataFrame()
        goodreads_book_stats = compute_book_stats(goodreads_books_this_year)
        print(f"Filtered to {len(goodreads_books_this_year)} books checked out in 2025.")
        print('goodreads_books_this_year', goodreads_books_this_year)
        print('goodreads_book_stats ', goodreads_book_stats)

        # Strava: tidy then filter to 2025 workouts for stats
        tidy_strava = clean_workouts_df(strava_data)
        workouts_this_year = (
            tidy_strava[tidy_strava['Activity Date'].dt.year == 2025].copy()
        )
        print('workouts_this_year', workouts_this_year)
        workout_stats = compute_workout_stats(workouts_this_year)
        print('workout_stats', workout_stats)
       
           

        # Serialize workout stats for quick embedding/transport
        stats_json = json.dumps({**workout_stats})
        print('stats_json', stats_json)

        # Merge Goodreads ratings into the library DataFrame by matching titles
        try:
            print('Attempting Goodreads ratings merge…')
            if not goodreads_books_this_year.empty and 'Title' in goodreads_books_this_year.columns:
                gr = goodreads_books_this_year[['Title', 'My Rating']].copy()
                # Normalize titles and try exact key match first
                gr['__key'] = gr['Title'].map(_normalize_title)
                lib_df['__key'] = lib_df['title'].map(_normalize_title)
                rating_map = gr.set_index('__key')['My Rating']
                lib_df['rating'] = lib_df['__key'].map(rating_map)

                # Quick fuzzy fallback for remaining NaNs (helps near-matches)
                try:
                    import difflib
                    gr_keys = list(gr['__key'].dropna().unique())

                    def _fuzzy_lookup(k: str):
                        # Return closest Goodreads key if similarity is high
                        if not isinstance(k, str) or not k:
                            return None
                        match = difflib.get_close_matches(k, gr_keys, n=1, cutoff=0.9)
                        return rating_map.get(match[0]) if match else None

                    na_mask = lib_df['rating'].isna()
                    if na_mask.any():
                        lib_df.loc[na_mask, 'rating'] = lib_df.loc[na_mask, '__key'].map(_fuzzy_lookup)
                except Exception:
                    pass
                # If still NaN after all matching, mark as "NR" (No Rating)
                lib_df['rating'] = lib_df['rating'].fillna('NR')
                # report match quality
                matched = (lib_df['rating'] != 'NR').sum()
                total = len(lib_df)
                print(f'Ratings matched: {matched}/{total}')
                # show examples of unmatched for debugging
                if matched < total:
                    unmatched = lib_df[lib_df['rating'] == 'NR'][['title']].head(5)
                    print('Unmatched sample (first 5):')
                    print(unmatched)
                lib_df = lib_df.drop(columns=['__key'])
                print('New lib_df with ratings:')
                print(lib_df)
            else:
                print('Skipping ratings merge: no 2025 Goodreads titles available.')
        except Exception as e:
            print('Could not merge Goodreads ratings:', e)

        try:
            data = response.json()
            library_money_saved_llm_content = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
            print('content', library_money_saved_llm_content)
            # Return all artifacts in-memory, including Strava and detailed workouts
            return (
                lib_df,
                library_money_saved_llm_content,
                goodreads_book_stats,
                goodreads_books_this_year,
                workout_stats,
                stats_json,
                workouts_this_year,
            )
        except Exception as e:
            print(f"Error parsing response: {e}\nRaw: {response.text[:1000]}")
            return (
                lib_df,
                "",
                goodreads_book_stats,
                goodreads_books_this_year,
                workout_stats,
                stats_json,
                workouts_this_year,
            )
        
        
       
if __name__ == "__main__":
    # Run and capture all artifacts
    result = asyncio.run(sfpl_2025())
    lib_df, content, goodreads_book_stats, goodreads_books_this_year, workout_stats, stats_json, workouts_this_year = result
   

    # Save artifacts
    try:
        if isinstance(lib_df, pd.DataFrame) and not lib_df.empty:
            lib_df.to_csv("library_books_2025.csv", index=False)
        if isinstance(goodreads_books_this_year, pd.DataFrame) and not goodreads_books_this_year.empty:
            goodreads_books_this_year.to_csv("goodreads_books_2025.csv", index=False)
        # Persist stats to CSV (flatten to rows)
        try:
            if isinstance(goodreads_book_stats, pd.DataFrame):
                goodreads_book_stats.to_csv("goodreads_book_stats_2025.csv", index=False)
            elif isinstance(goodreads_book_stats, dict):
                pd.DataFrame([goodreads_book_stats]).to_csv("goodreads_book_stats_2025.csv", index=False)
            elif hasattr(goodreads_book_stats, 'to_dict'):
                pd.DataFrame([goodreads_book_stats.to_dict()]).to_csv("goodreads_book_stats_2025.csv", index=False)
        except Exception:
            pass
        # Save wrap-up text
        if isinstance(content, str):
            with open("wrapup_2025.txt", "w") as f:
                f.write(content)
        # Save Strava stats JSON for optional offline use
        try:
            if isinstance(stats_json, str) and stats_json:
                with open("strava_workout_stats_2025.json", "w") as f:
                    f.write(stats_json)
        except Exception:
            pass
    except Exception:
        pass