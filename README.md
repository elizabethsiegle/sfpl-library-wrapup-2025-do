### SFPL Library Wrapped 2025

Add a .env with your SFPL username and password and DigitalOcean MODEL_ACCESS_KEY ([get one here](https://docs.digitalocean.com/products/gradient-ai-platform/how-to/use-serverless-inference/#keys))
```bash
USERNAME=
PASSWORD=
MODEL_ACCESS_KEY=
```

To get your Goodreads data and Strava data:
- [Export Strava data here](https://www.strava.com/athlete/delete_your_account)

- [Export Goodreads data here](https://www.goodreads.com/review/import)

Save and replace the file paths in lines 22 and 23 in `library_app.py`.

Run `library_app` first to get your data via Playwright.

Then run the Streamlit app `library_streamlit_app.py`. You can [see my 2025 SFPL stats here hosted on DigitalOcean App platform]()