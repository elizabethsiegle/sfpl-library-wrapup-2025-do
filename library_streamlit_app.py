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
if st.button("Fetch latest library + Goodreads data"):
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
	gr_stats_obj = st.session_state.get("gr_stats_obj")
	if gr_stats_obj is not None:
		try:
			gr_stats_df = pd.DataFrame(gr_stats_obj)
			st.dataframe(gr_stats_df)
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
		# Minimal bar chart; could switch to Altair for labels/colors
		st.bar_chart(counts.set_index("status"))
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
			st.bar_chart(top_authors)
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
				st.bar_chart(hist)
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
			st.bar_chart(by_type_df.set_index("type"))
		# By month
		if "by_month" in workout_stats and isinstance(workout_stats["by_month"], dict):
			st.markdown("**Workouts per Month (2025)**")
			by_month = pd.DataFrame(list(workout_stats["by_month"].items()), columns=["month","count"])
			# Ensure months numeric and ordered 1..12
			by_month["month"] = pd.to_numeric(by_month["month"], errors="coerce")
			by_month = by_month.dropna().sort_values("month")
			st.bar_chart(by_month.set_index("month"))
		# Totals like distance or time
		if "total_distance_km" in workout_stats or "total_time_hours" in workout_stats:
			st.markdown("**Totals**")
			total_distance = float(workout_stats.get("total_distance_km", 0) or 0)
			total_time = float(workout_stats.get("total_time_hours", 0) or 0)
			col1, col2 = st.columns(2)
			with col1:
				st.metric("Total Distance (km)", f"{total_distance:.1f}")
			with col2:
				st.metric("Total Time (hours)", f"{total_time:.1f}")
	except Exception:
		pass
else:
	st.info("No Strava data yet. Click Fetch above.")

st.divider()
st.subheader("How active vs. how much I read (2025)")
# Build a dual-axis monthly line chart: left=workouts, right=books
try:
	import altair as alt
	# Workouts by month from stats (expects keys as 1..12 or month names)
	wstats = st.session_state.get("workout_stats", {}) or {}
	by_month_w = wstats.get("by_month", {}) if isinstance(wstats, dict) else {}
	w_month_df = pd.DataFrame(list(by_month_w.items()), columns=["month","workouts"]) if by_month_w else pd.DataFrame(columns=["month","workouts"])
	# Normalize month to numeric 1..12
	def _month_to_num(m):
		try:
			return int(m)
		except Exception:
			try:
				return pd.to_datetime(str(m), format="%b").month
			except Exception:
				return None
	if not w_month_df.empty:
		w_month_df["month"] = w_month_df["month"].map(_month_to_num)
		w_month_df = w_month_df.dropna().astype({"month": int})

	# Books by month from Goodreads
	gr_books_df = st.session_state.get("gr_books_df", pd.DataFrame())
	b_month_df = pd.DataFrame(columns=["month","books"])
	if isinstance(gr_books_df, pd.DataFrame) and not gr_books_df.empty and "Date Read" in gr_books_df.columns:
		_dfb = gr_books_df.copy()
		_dfb["_date"] = pd.to_datetime(_dfb["Date Read"], errors="coerce")
		_dfb = _dfb.dropna(subset=["_date"]) 
		_dfb = _dfb[_dfb["_date"].dt.year == 2025]
		_dfb["month"] = _dfb["_date"].dt.month
		b_month_df = _dfb.groupby("month", as_index=False).size().rename(columns={"size":"books"})

	# Merge into common month series 1..12
	months = pd.DataFrame({"month": list(range(1,13))})
	merged = months.merge(w_month_df, on="month", how="left").merge(b_month_df, on="month", how="left")
	merged["workouts"] = merged["workouts"].fillna(0)
	merged["books"] = merged["books"].fillna(0)

	# Month label for axis
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

	base = alt.Chart(merged).encode(x=alt.X("month:O", scale=alt.Scale(domain=list(range(1,13))), axis=alt.Axis(title="Month", labelExpr=month_label_expr)))
	workouts_line = base.mark_line(color="#4C78A8", strokeWidth=2).encode(y=alt.Y("workouts:Q", axis=alt.Axis(title="Workouts", orient="left")))
	books_line = base.mark_line(color="#F59E0B", strokeWidth=2).encode(y=alt.Y("books:Q", axis=alt.Axis(title="Books Read", orient="right")))
	chart = alt.layer(workouts_line, books_line).resolve_scale(y="independent").properties(height=320)
	st.altair_chart(chart, width='stretch')
	st.caption("Left axis: workouts • Right axis: books read")
except Exception as e:
	st.info(f"Multi-axis chart unavailable: {e}")

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
