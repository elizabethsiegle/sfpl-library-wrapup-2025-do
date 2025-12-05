import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import streamlit as st
import os
import pandas as pd
import requests

# Load .env file
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
MODEL_ACCESS_KEY = os.getenv("MODEL_ACCESS_KEY")

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

        # --- Scrape 2025 books across pages until a 2024 item is found ---
        BOOK_ITEM_SELECTOR = ".cp-batch-actions-list-item"
        NEXT_BUTTON_XPATH = "/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]/section/nav/ul[1]/li[9]/a"

        books_2025 = []
        page_index = 1
        while True:
            print(f"7.{page_index} Waiting for book items on page {page_index}.")
            # Wait for the list container to appear; be tolerant to slow loads
            try:
                await page.wait_for_selector(BOOK_ITEM_SELECTOR, state="attached", timeout=15000)
                await page.wait_for_selector(BOOK_ITEM_SELECTOR, state="visible", timeout=15000)
            except Exception:
                # Fallback to explicit XPath if CSS doesn't resolve in time
                print("CSS selector not found promptly; using explicit XPath fallback.")
                await page.wait_for_selector("xpath=/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]", timeout=20000)

            # Count items and iterate
            items_locator = page.locator(BOOK_ITEM_SELECTOR)
            count = await items_locator.count()
            # If count is zero, try to enumerate via full XPath index loop
            if count == 0:
                print("No items via CSS; attempting XPath enumeration.")
                # Try up to 100 entries; stop when an index doesn't exist for a while
                stop_due_to_2024 = False
                empty_streak = 0
                # There are 50 books per page; enumerate those indices directly
                for idx in range(1, 51):
                    # Construct the container XPath for each item index
                    container_xpath = f"/html/body/div[1]/div/div/main/div/div/div[2]/div/div/div/div[3]/div/div[2]/div/div[2]/div[{idx}]"
                    loc = page.locator(f"xpath={container_xpath}")
                    try:
                        await loc.wait_for(state="visible", timeout=1000)
                    except Exception:
                        empty_streak += 1
                        if empty_streak >= 5:
                            break
                        continue
                    empty_streak = 0
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
                        books_2025.append({
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
                    # Fallback: use the visible text
                    try:
                        title = await item.locator("css=h2.cp-title .title-content").inner_text()
                    except Exception:
                        title = None
                    try:
                        author = await item.locator("css=.cp-by-author-block .author-link").inner_text()
                    except Exception:
                        author = None
                    books_2025.append({
                        "title": title or "(unknown title)",
                        "author": author or "(unknown author)",
                        "raw": text.strip()
                    })

            if stop_due_to_2024:
                break

            # Go to next page, if available
            try:
                print("Clicking next page chevron…")
                await page.locator(f"xpath={NEXT_BUTTON_XPATH}").click()
                await page.wait_for_load_state('networkidle')
                page_index += 1
            except Exception:
                print("No next page button found; finishing.")
                break

        print(f"Collected {len(books_2025)} books from 2025:")
        # Convert to DataFrame for downstream use
        df = pd.DataFrame(books_2025)[["title", "author"]]
        print('df ', df)


        url = "https://inference.do-ai.run/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MODEL_ACCESS_KEY}"
        }
        messages = [{"role": "system", "content": "You are an expert librarian advocate who loves books and economics. Output only what is asked of you, do not reason. Just have fun and advocate for libraries and tell people how much money they saved this year based on how many books they checked out from the library."},
            {"role": "user", "content": (
            "Generate a brief 2025 year-end wrap-up for the user based on their SF Public Library data. Tell them how many books they checked out, some highlights, and estimate how much money they saved by going to the library. Estimate 1 book costs $23. "
            "Use the exact numeric stats provided (do not make up numbers, books, or authors). "
            "Write in a funny, friendly, engaging tone.\n\n"
            f"Library books checked out this year {df}"
        )}]
        payload = {"model": "openai-gpt-oss-20b", "messages": messages, "temperature": 0.2, "max_tokens": 500}

        response = requests.post(url, headers=headers, json=payload)
        try:
            data = response.json()
            print('data', data)
            content = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
            print('content', content)
        except Exception as e:
            print(f"Error parsing response: {e}\nRaw: {response.text[:1000]}")
        
       
if __name__ == "__main__":
    asyncio.run(sfpl_2025())