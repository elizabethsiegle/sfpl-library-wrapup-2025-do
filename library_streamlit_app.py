import asyncio
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Load environment
load_dotenv()

st.set_page_config(page_title="SFPL 2025 Wrap-up", page_icon="📚", layout="centered")

st.title("SF Public Library 2025 Wrap-up")
st.caption("Displaying previously scraped data from library_app.py")

# Load artifacts saved by library_app.py
library_books_path = os.path.join(os.getcwd(), "library_books_2025.csv")
wrapup_path = os.path.join(os.getcwd(), "wrapup_2025.txt")
goodreads_data_path = os.path.join(os.getcwd(), "goodreads_books_2025.csv")
goodreads_stats_path = os.path.join(os.getcwd(), "goodreads_book_stats_2025.csv")

st.subheader("Books Lizzie checked out of the library in 2025")
if os.path.exists(library_books_path):
	try:
		lib_df = pd.read_csv(library_books_path)
		# Ensure only title/author columns
		cols = [c for c in ["title", "author", "rating"] if c in lib_df.columns]
		lib_df = lib_df[cols] if cols else lib_df
		st.dataframe(lib_df)
		st.subheader("Goodreads: Summary Stats")
		if os.path.exists(goodreads_stats_path):
			gr_stats_df = pd.read_csv(goodreads_stats_path)
			st.dataframe(gr_stats_df)

		# Charts: read vs not read ratio based on rating == 'NR'
		st.markdown("**Read vs. Not Read (Library checkouts)**")
		if "rating" in lib_df.columns:
			read_mask = lib_df["rating"].astype(str).str.upper() != "NR"
			counts = pd.DataFrame({
				"status": ["Read", "Not Read"],
				"count": [int(read_mask.sum()), int((~read_mask).sum())]
			})
			st.bar_chart(counts.set_index("status"))
			st.caption(f"Read: {int(read_mask.sum())} • Not Read: {int((~read_mask).sum())}")

			# Share of read books
			total = len(lib_df)
			share_read = (read_mask.sum() / total * 100.0) if total else 0.0
			st.metric("Share of library checkouts actually read", f"{share_read:.1f}%")

			# Top authors by count among read
			if "author" in lib_df.columns:
				st.markdown("**Top Authors (Read)**")
				top_authors = lib_df.loc[read_mask, "author"].value_counts().head(10)
				st.bar_chart(top_authors)
	except Exception as e:
		st.error(f"Failed to read library_books_2025.csv: {e}")
else:
	st.info("library_books_2025.csv not found. Run library_app.py to generate it.")

st.subheader("Wrap-up")
if os.path.exists(wrapup_path):
	try:
		with open(wrapup_path, "r") as f:
			content = f.read()
		st.markdown(content)
	except Exception as e:
		st.error(f"Failed to read wrapup_2025.txt: {e}")
else:
	st.info("wrapup_2025.txt not found. Run library_app.py to generate it.")



st.divider()
st.subheader("Goodreads: 2025 Reads")
if os.path.exists(goodreads_data_path):
	try:
		gr_books_df = pd.read_csv(goodreads_data_path)
		st.dataframe(gr_books_df)
		# Ratings distribution
		if "My Rating" in gr_books_df.columns:
			st.markdown("**Ratings Distribution (Goodreads)**")
			ratings = gr_books_df["My Rating"].dropna().astype(float)
			if not ratings.empty:
				hist = ratings.value_counts().sort_index()
				st.bar_chart(hist)

		# Books read per month (Goodreads Date Read) with interactive selection
		if "Date Read" in gr_books_df.columns:
			st.markdown("**Books Read per Month (Goodreads 2025)**")
			try:
				import altair as alt
				df_month = gr_books_df.copy()
				df_month["_date"] = pd.to_datetime(df_month["Date Read"], errors="coerce")
				df_month = df_month.dropna(subset=["_date"]) 
				df_month["month"] = df_month["_date"].dt.month
				df_month["month_name"] = df_month["month"].map(lambda m: pd.Timestamp(year=2025, month=int(m), day=1).strftime('%b'))
				# only 2025
				df_month = df_month[df_month["_date"].dt.year == 2025]

				# Add spacing before this chart
				st.write("")
				st.write("")

				# Aggregate counts per month and enforce Jan..Dec order
				counts = df_month.groupby(["month","month_name"], as_index=False).size()
				counts.rename(columns={"size":"count"}, inplace=True)
				# Helper: month labels via axis labelExpr
				month_domain = list(range(1,13))
				month_label_expr = (
					"datum.value==1?'Jan':"
					"datum.value==2?'Feb':"
					"datum.value==3?'Mar':"
					"datum.value==4?'Apr':"
					"datum.value==5?'May':"
					"datum.value==6?'Jun':"
					"datum.value==7?'Jul':"
					"datum.value==8?'Aug':"
					"datum.value==9?'Sep':"
					"datum.value==10?'Oct':"
					"datum.value==11?'Nov':'Dec'"
				)

				sel = alt.selection_point(fields=["month"], bind="legend")
				# Sort strictly by numeric month and render human labels via axis
				bar = (
					alt.Chart(counts)
					.mark_bar(color="#4C78A8")
					.encode(
						x=alt.X(
							"month:O",
							title="Month",
							sort="ascending",
							scale=alt.Scale(domain=month_domain),
							axis=alt.Axis(labelExpr=month_label_expr)
						),
						y=alt.Y("count:Q", title="Books Read"),
						color=alt.condition(sel, alt.value("#4C78A8"), alt.value("#D3D3D3"))
					)
					.add_params(sel)
				)
				labels = bar.mark_text(align="center", baseline="bottom", dy=-4, color="#1F2937", font="Inter", fontSize=12).encode(text=alt.Text("count:Q"))

				# Normalize author column casing if present
				author_col = None
				if "author" in df_month.columns:
					author_col = "author"
				elif "Author" in df_month.columns:
					author_col = "Author"
				if author_col:
					df_month["__author"] = df_month[author_col]

				# Linked list of titles: use points with tooltips to avoid text overlap
				base_cols = ["month","month_name","Title","My Rating"]
				if "__author" in df_month.columns:
					titles_source = df_month[base_cols + ["__author"]]
					tooltip_fields = ["Title", "__author", "My Rating", "month_name"]
				else:
					titles_source = df_month[base_cols]
					tooltip_fields = ["Title", "My Rating", "month_name"]
				# Add horizontal jitter to reduce overlap of points
				titles = (
					alt.Chart(titles_source)
					.transform_filter(sel)
					.transform_calculate(jitter='(random() - 0.5) * 0.8')
					.mark_circle(size=48, opacity=0.85, color="#F59E0B")
					.encode(
						y=alt.Y("Title:N", sort=None, title=None),
						x=alt.X(
							"month:O",
							title=None,
							sort="ascending",
							scale=alt.Scale(domain=month_domain),
							axis=alt.Axis(labelExpr=month_label_expr)
						),
						xOffset=alt.XOffset("jitter:Q"),
						tooltip=tooltip_fields
					)
					.properties(height=400)
				)

				composed = alt.vconcat(bar + labels, titles).resolve_scale(y="independent").properties(bounds="flush")
				st.altair_chart(composed, width='stretch')
				st.caption("Tip: Click a bar to filter. Hover dots to see full titles.")
			except Exception as e:
				st.warning(f"Could not compute interactive books per month: {e}")
	except Exception as e:
		st.error(f"Failed to read goodreads_books_2025.csv: {e}")
else:
	st.info("goodreads_books_2025.csv not found. Run library_app.py to generate it.")

			

st.divider()
st.caption("Artifacts are loaded from library_app.py outputs: library_books_2025.csv, goodreads_books_2025.csv, goodreads_book_stats_2025.csv, and wrapup_2025.txt.")

# Custom sticky footer
st.markdown("""
<style>
			.footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #0e1117;
        color: white;
        text-align: center;
        padding: 10px 0;
        border-top: 1px solid #262730;
        z-index: 1000;
        font-size: 14px;
    }
    
    .footer a {
        color: #ff6b6b;
        text-decoration: none;
        font-weight: 500;
    }
    
    .footer a:hover {
        color: #ff5252;
        text-decoration: underline;
    }
</style>
<div class="footer">
    made with <3 in sf | <a href="-https://github.com/elizabethsiegle/sfpl-library-wrapup-2025-do" target="_blank">View on GitHub</a>
</div>
""", unsafe_allow_html=True)
