"""
Streamlit app for SFPL 2025 wrap-up.

Data is fetched in-memory via `library_data.get_library_and_goodreads()`
and stored in `st.session_state`. No CSV files are read or written.
"""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from library_data import get_library_and_goodreads

# Load environment
load_dotenv()

st.set_page_config(page_title="SFPL 2025 Wrap-up", page_icon="📚", layout="centered")

st.title("SF Public Library 2025 Wrap-up")
st.caption("Fetches data in-memory; no CSVs required.")

# Fetch controls (in-memory, no files)
# One button loads everything and caches it in session_state
# Returned objects: lib_df, wrapup_text, gr_stats_obj, gr_books_df, workout_stats, stats_json
st.subheader("Data")
if st.button("See Lizzie's 2025 library, Goodreads, and Strava data"):
	# Fetch all artifacts in-memory via library_app.sfpl_2025
	lib_df, wrapup_text, gr_stats_obj, gr_books_df, workout_stats, stats_json = get_library_and_goodreads()
	st.session_state["lib_df"] = lib_df
	st.session_state["wrapup_text"] = wrapup_text
	st.session_state["gr_stats_obj"] = gr_stats_obj
	st.session_state["gr_books_df"] = gr_books_df
	st.session_state["workout_stats"] = workout_stats
	st.session_state["stats_json"] = stats_json
if "lib_df" not in st.session_state:
	st.info("Click the button above to load data from SFPL + Goodreads (no CSVs).")

st.subheader("Books Lizzie checked out of the library in 2025")
# Read from session_state; don't hit disk
# If empty, we'll prompt the user to fetch
lib_df = st.session_state.get("lib_df", pd.DataFrame())
if isinstance(lib_df, pd.DataFrame) and not lib_df.empty:
	# Trim to key columns if present for a cleaner view
	cols = [c for c in ["title", "author", "rating"] if c in lib_df.columns]
	lib_df = lib_df[cols] if cols else lib_df
	st.dataframe(lib_df)

	st.subheader("Goodreads: Summary Stats")
	# Prefer computing tidy summary from the 2025 Goodreads books to avoid duplicates
	gr_books_df_for_stats = st.session_state.get("gr_books_df", pd.DataFrame())
	if isinstance(gr_books_df_for_stats, pd.DataFrame) and not gr_books_df_for_stats.empty:
		try:
			df = gr_books_df_for_stats.copy()
			# Only 2025 reads
			df["_date"] = pd.to_datetime(df.get("Date Read", pd.Series([])), errors="coerce")
			df = df.dropna(subset=["_date"]) 
			df = df[df["_date"].dt.year == 2025]
			# Normalize columns that vary in casing
			title_col = "Title" if "Title" in df.columns else None
			author_col = "Author" if "Author" in df.columns else ("author" if "author" in df.columns else None)
			rating_col = "My Rating" if "My Rating" in df.columns else None
			# Deduplicate by title to avoid repeats and compute simple aggregates
			if title_col:
				df = df.drop_duplicates(subset=[title_col])
			total_books = int(len(df))
			avg_rating = float(pd.to_numeric(df[rating_col], errors="coerce").mean()) if rating_col else 0.0
			top_authors = (
				df[author_col].value_counts().head(5).to_dict() if author_col else {}
			)
			monthly_counts = (
				df.assign(month=df["_date"].dt.month)
				.groupby("month", as_index=False)
				.size()
				.rename(columns={"size": "books"})
			)
			summary = {
				"total_books_2025": total_books,
				"avg_rating": round(avg_rating, 2) if avg_rating else None,
				"top_authors_5": top_authors,
			}
			st.json(summary)
			# Small monthly chart for quick glance with axis titles
			if not monthly_counts.empty:
				import altair as alt
				mc_chart = (
					alt.Chart(monthly_counts)
					.mark_bar(color="#1E88E5")
					.encode(
						x=alt.X("month:O", title="Month"),
						y=alt.Y("books:Q", title="Books Read")
					)
				)
				st.altair_chart(mc_chart, width='stretch')
		except Exception as e:
			st.warning(f"Could not compute Goodreads summary: {e}")
	else:
		# Fallback to whatever object was returned, if present
		gr_stats_obj = st.session_state.get("gr_stats_obj")
		if gr_stats_obj is not None:
			try:
				st.dataframe(pd.DataFrame(gr_stats_obj))
			except Exception:
				pass

	# Charts: read vs not read ratio based on rating == 'NR'
	# Simple indicator of how many checkouts were actually finished
	st.markdown("**Read vs. Not Read (Library checkouts)**")
	if "rating" in lib_df.columns:
		read_mask = lib_df["rating"].astype(str).str.upper() != "NR"
		counts = pd.DataFrame({
			"status": ["Read", "Not Read"],
			"count": [int(read_mask.sum()), int((~read_mask).sum())]
		})
		# Altair bar chart with axis titles
		import altair as alt
		read_chart = (
			alt.Chart(counts)
			.mark_bar(color="#4C78A8")
			.encode(
				x=alt.X("status:N", title="Status"),
				y=alt.Y("count:Q", title="Count")
			)
		)
		st.altair_chart(read_chart, use_container_width=True)
		st.caption(f"Read: {int(read_mask.sum())} • Not Read: {int((~read_mask).sum())}")

		# Share of read books
		total = len(lib_df)
		share_read = (read_mask.sum() / total * 100.0) if total else 0.0
		st.metric("Share of library checkouts actually read", f"{share_read:.1f}%")

		# Top authors by count among read
		# Quick leaderboard for finished books
		# Shows which authors you completed most
		if "author" in lib_df.columns:
			st.markdown("**Top Authors (Read)**")
			top_authors = lib_df.loc[read_mask, "author"].value_counts().head(10)
			# Altair bar chart with axis titles
			import altair as alt
			top_authors_df = top_authors.reset_index()
			top_authors_df.columns = ["author", "count"]
			auth_chart = (
				alt.Chart(top_authors_df)
				.mark_bar(color="#9C27B0")
				.encode(
					x=alt.X("author:N", title="Author"),
					y=alt.Y("count:Q", title="Read Count")
				)
			)
			st.altair_chart(auth_chart, use_container_width=True)
else:
	st.info("No library books yet. Click Fetch above.")

st.subheader("Wrap-up")
content = st.session_state.get("wrapup_text")
if isinstance(content, str) and content:
	st.markdown(content)
else:
	st.info("No wrap-up text yet. Click Fetch above.")



st.divider()
st.subheader("Goodreads: 2025 Reads")
gr_books_df = st.session_state.get("gr_books_df", pd.DataFrame())
if isinstance(gr_books_df, pd.DataFrame) and not gr_books_df.empty:
	st.dataframe(gr_books_df)
	# Ratings distribution
	# Basic histogram, tolerant to non-numeric cells
	# We coerce to float and skip failures silently
	if "My Rating" in gr_books_df.columns:
		st.markdown("**Ratings Distribution (Goodreads)**")
		ratings = gr_books_df["My Rating"].dropna()
		try:
			ratings = ratings.astype(float)
			if not ratings.empty:
				hist = ratings.value_counts().sort_index()
				import altair as alt
				ratings_df = hist.reset_index()
				ratings_df.columns = ["rating", "count"]
				ratings_chart = (
					alt.Chart(ratings_df)
					.mark_bar(color="#2E7D32")
					.encode(
						x=alt.X("rating:Q", title="Rating"),
						y=alt.Y("count:Q", title="Count")
					)
				)
				st.altair_chart(ratings_chart, use_container_width=True)
		except Exception:
			pass

	# Books read per month (Goodreads Date Read) with interactive selection
	# Click a bar to filter; dots show titles with jitter to reduce overlap
	# Axis uses numeric month domain 1..12 with custom labelExpr to render Jan–Dec
	if "Date Read" in gr_books_df.columns:
		st.markdown("**Books Read per Month (Goodreads 2025)**")
		try:
			import altair as alt
			df_month = gr_books_df.copy()
			df_month["_date"] = pd.to_datetime(df_month["Date Read"], errors="coerce")
			df_month = df_month.dropna(subset=["_date"]) 
			df_month["month"] = df_month["_date"].dt.month
			df_month["month_name"] = df_month["month"].map(lambda m: pd.Timestamp(year=2025, month=int(m), day=1).strftime('%b'))
			df_month = df_month[df_month["_date"].dt.year == 2025]

			counts = df_month.groupby(["month","month_name"], as_index=False).size()
			counts.rename(columns={"size":"count"}, inplace=True)
			month_domain = list(range(1,13))
			# Render month numbers (1..12) as short names via Vega labelExpr
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
			# Bar chart of monthly counts; selection controls linked titles below
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
			# Add count labels on bars for quick reading
			labels = bar.mark_text(align="center", baseline="bottom", dy=-4, color="#1F2937", font="Inter", fontSize=12).encode(text=alt.Text("count:Q"))

			author_col = None
			if "author" in df_month.columns:
				author_col = "author"
			elif "Author" in df_month.columns:
				author_col = "Author"
			if author_col:
				df_month["__author"] = df_month[author_col]

			base_cols = ["month","month_name","Title","My Rating"]
			if "__author" in df_month.columns:
				titles_source = df_month[base_cols + ["__author"]]
				tooltip_fields = ["Title", "__author", "My Rating", "month_name"]
			else:
				titles_source = df_month[base_cols]
				tooltip_fields = ["Title", "My Rating", "month_name"]
			# Jitter points horizontally to reduce overlap; hover to see details
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
			# Use container width to adapt to different screen sizes
			st.altair_chart(composed, width='stretch')
			st.caption("Tip: Click a bar to filter. Hover dots to see full titles.")
		except Exception as e:
			st.warning(f"Could not compute interactive books per month: {e}")
else:
	st.info("No Goodreads books yet. Click Fetch above.")

			
st.divider()
st.subheader("Strava: 2025 Workouts")
# Display workout stats similarly to books: totals and by month/type if available
workout_stats = st.session_state.get("workout_stats", {})
if isinstance(workout_stats, dict) and workout_stats:
	try:
		ws_df = pd.DataFrame([workout_stats])
		st.dataframe(ws_df)
	except Exception:
		pass

	# Optional charts if common fields exist
	# Example: total workouts, by sport type, by month
	try:
		# By sport type
		if "by_type" in workout_stats and isinstance(workout_stats["by_type"], dict):
			st.markdown("**Workouts by Type**")
			by_type_df = pd.DataFrame(list(workout_stats["by_type"].items()), columns=["type","count"])
			import altair as alt
			by_type_chart = (
				alt.Chart(by_type_df)
				.mark_bar(color="#546E7A")
				.encode(
					x=alt.X("type:N", title="Activity Type"),
					y=alt.Y("count:Q", title="Workouts")
				)
			)
			st.altair_chart(by_type_chart, use_container_width=True)
		# By month
		if "by_month" in workout_stats and isinstance(workout_stats["by_month"], dict):
			st.markdown("**Workouts per Month (2025)**")
			by_month = pd.DataFrame(list(workout_stats["by_month"].items()), columns=["month","count"])
			# Ensure months numeric and ordered 1..12
			by_month["month"] = pd.to_numeric(by_month["month"], errors="coerce")
			by_month = by_month.dropna().sort_values("month")
			import altair as alt
			bym_chart = (
				alt.Chart(by_month)
				.mark_bar(color="#00897B")
				.encode(
					x=alt.X("month:O", title="Month"),
					y=alt.Y("count:Q", title="Workouts")
				)
			)
			st.altair_chart(bym_chart, use_container_width=True)
		# Totals: workouts, distance, time
		st.markdown("**Totals**")
		# Align keys to strava_helpers.compute_workout_stats output
		by_type_counts = workout_stats.get("by_type_counts", {}) if isinstance(workout_stats.get("by_type_counts", {}), dict) else {}
		total_workouts = int(workout_stats.get("workout_count", 0) or 0)
		# Fallback: sum by_type_counts if workout_count missing or zero
		if total_workouts == 0 and by_type_counts:
			total_workouts = int(sum((v or 0) for v in by_type_counts.values()))
		avg_speed_mph = float(workout_stats.get("avg_speed_mph", 0) or 0)
		# Use precomputed total time hours from helper
		total_time_hours = float(workout_stats.get("total_time_hours", 0) or 0)
		col1, col2, col3 = st.columns(3)
		with col1:
			st.metric("Total Workouts", f"{total_workouts}")
		with col2:
			st.metric("Total Distance (miles)", f"{total_distance:.1f}")
		with col3:
			st.metric("Total Time (hours)", f"{total_time_hours:.1f}")
	except Exception:
		pass
else:
	st.info("No Strava data yet. Click Fetch above.")

st.divider()
st.subheader("How active vs. how much I read (2025)")
# Build a dual-axis monthly line chart: left=workouts, right=books
try:
	import altair as alt
	# Goodreads monthly counts
	gr_books_df = st.session_state.get("gr_books_df", pd.DataFrame())
	books_month_counts = pd.DataFrame()
	if isinstance(gr_books_df, pd.DataFrame) and not gr_books_df.empty and "Date Read" in gr_books_df.columns:
		dfm = gr_books_df.copy()
		dfm["_date"] = pd.to_datetime(dfm["Date Read"], errors="coerce")
		dfm = dfm.dropna(subset=["_date"]) 
		dfm = dfm[dfm["_date"].dt.year == 2025]
		dfm["month"] = dfm["_date"].dt.month
		books_month_counts = dfm.groupby("month", as_index=False).size().rename(columns={"size":"books"})

	# Workouts monthly counts from workout_stats.by_month
	workout_stats = st.session_state.get("workout_stats", {})
	workouts_month_counts = pd.DataFrame()
	by_month = workout_stats.get("by_month", {}) if isinstance(workout_stats, dict) else {}
	if isinstance(by_month, dict) and by_month:
		workouts_month_counts = pd.DataFrame(list(by_month.items()), columns=["month","workouts"]).sort_values("month")

	# Merge on month 1..12
	month_domain = list(range(1,13))
	base = pd.DataFrame({"month": month_domain})
	merged = base.merge(books_month_counts, on="month", how="left").merge(workouts_month_counts, on="month", how="left")
	merged["books"] = merged["books"].fillna(0).astype(int)
	merged["workouts"] = merged["workouts"].fillna(0).astype(int)

	# Label months
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

	chart_data = merged
	left = (
		alt.Chart(chart_data)
		.mark_line(color="#4C78A8", point=True)
		.encode(
			x=alt.X("month:O", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=month_label_expr), title="Month"),
			y=alt.Y("workouts:Q", title="Workouts")
		)
	)
	right = (
		alt.Chart(chart_data)
		.mark_line(color="#F59E0B", point=True)
		.encode(
			x=alt.X("month:O", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=month_label_expr), title="Month"),
			y=alt.Y("books:Q", title="Books Read")
		)
	)
	layered = alt.layer(left, right).resolve_scale(y="independent").properties(width=700, height=300)
	st.altair_chart(layered, use_container_width=True)
except Exception as e:
	st.warning(f"Could not build dual-axis chart: {e}")


st.divider()
st.caption("Data is loaded in-memory via library_app.sfpl_2025 and shared through session state. No CSVs.")

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
