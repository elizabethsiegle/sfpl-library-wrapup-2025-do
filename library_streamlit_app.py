"""
Streamlit app for SFPL 2025 wrap-up.
Data is fetched in-memory via `library_data.get_library_and_goodreads()`
and stored in `st.session_state`. No CSV files are read or written.
"""

import streamlit as st
import pandas as pd
import altair as alt
from dotenv import load_dotenv
from library_data import get_library_and_goodreads

# --- CONSTANTS & CONFIG ---
PAGE_TITLE = "SFPL 2025 Wrap-up"
PAGE_ICON = "📚"
LAYOUT = "centered"

# Vega-Lite expression to map month numbers 1-12 to Jan-Dec
MONTH_LABEL_EXPR = (
    "datum.value==1?'Jan':datum.value==2?'Feb':datum.value==3?'Mar':"
    "datum.value==4?'Apr':datum.value==5?'May':datum.value==6?'Jun':"
    "datum.value==7?'Jul':datum.value==8?'Aug':datum.value==9?'Sep':"
    "datum.value==10?'Oct':datum.value==11?'Nov':'Dec'"
)

# Strava Activity Colors
ACTIVITY_ORDER = ["Run", "Ride", "Swim", "Walk", "Hike", "Tennis", "Basketball", "Volleyball", "Pickleball", "Strength", "Yoga"]
ACTIVITY_COLORS = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", 
    "#EECA3B", "#B279A2", "#FF9DA6", "#9C755F", "#76B7B2", "#59A14F"
]

# --- SETUP ---
load_dotenv()
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

# --- HELPER FUNCTIONS: DATA PROCESSING ---

def fetch_data():
    """Fetches data and populates session state."""
    lib_df, wrapup_text, gr_stats_obj, gr_books_df, workout_stats, stats_json = get_library_and_goodreads()
    st.session_state.update({
        "lib_df": lib_df,
        "wrapup_text": wrapup_text,
        "gr_stats_obj": gr_stats_obj,
        "gr_books_df": gr_books_df,
        "workout_stats": workout_stats,
        "stats_json": stats_json
    })

def clean_goodreads_data(df):
    """Preprocesses Goodreads dataframe for 2025."""
    if df.empty: return df
    
    df = df.copy()
    df["_date"] = pd.to_datetime(df.get("Date Read", pd.Series([])), errors="coerce")
    df = df.dropna(subset=["_date"])
    df = df[df["_date"].dt.year == 2025]
    
    # Normalize Columns
    if "Title" not in df.columns and "title" in df.columns: df["Title"] = df["title"]
    if "Author" not in df.columns and "author" in df.columns: df["Author"] = df["author"]
    if "My Rating" not in df.columns and "rating" in df.columns: df["My Rating"] = df["rating"]
    
    return df

# --- HELPER FUNCTIONS: CHARTS ---

def chart_monthly_counts(data, x_col, y_col, color="#1E88E5", title="Counts"):
    return alt.Chart(data).mark_bar(color=color).encode(
        x=alt.X(f"{x_col}:O", title="Month"),
        y=alt.Y(f"{y_col}:Q", title=title)
    )

def chart_read_status(counts_df):
    return alt.Chart(counts_df).mark_bar(color="#4C78A8").encode(
        x=alt.X("status:N", title="Status"),
        y=alt.Y("count:Q", title="Count")
    )

def chart_top_authors(authors_df):
    return alt.Chart(authors_df).mark_bar(color="#9C27B0").encode(
        x=alt.X("author:N", title="Author"),
        y=alt.Y("count:Q", title="Read Count")
    )

# --- RENDER SECTIONS ---

def render_header():
    st.title("2025 SF Public Library x Goodreads x Strava 2025 Wrapped")

    if st.button("See Lizzie's 2025 library, Goodreads, and Strava data"):
        fetch_data()
        

def render_library_section():
    st.subheader("Books Lizzie checked out of the library in 2025")
    lib_df = st.session_state.get("lib_df", pd.DataFrame())

    if isinstance(lib_df, pd.DataFrame) and not lib_df.empty:
        # 1. Table
        cols = [c for c in ["title", "author", "rating"] if c in lib_df.columns]
        st.dataframe(lib_df[cols] if cols else lib_df)

        # 2. Goodreads Summary Logic
        st.subheader("Goodreads: Summary Stats")
        gr_df = st.session_state.get("gr_books_df", pd.DataFrame())
        
        try:
            cleaned_gr = clean_goodreads_data(gr_df)
            if not cleaned_gr.empty:
                # Deduplicate for stats
                stats_df = cleaned_gr.drop_duplicates(subset=["Title"])
                
                # Metrics
                total_books = len(stats_df)
                rating_col = "My Rating"
                avg_rating = pd.to_numeric(stats_df[rating_col], errors="coerce").mean() if rating_col in stats_df else 0.0
                author_col = "Author"
                top_authors = stats_df[author_col].value_counts().head(5).to_dict() if author_col in stats_df else {}

                st.json({
                    "total_books_2025": total_books,
                    "avg_rating": round(avg_rating, 2) if avg_rating else None,
                    "top_authors_5": top_authors,
                })

                # Simple Monthly Chart
                monthly_counts = (
                    cleaned_gr.assign(month=cleaned_gr["_date"].dt.month)
                    .groupby("month", as_index=False)
                    .size()
                    .rename(columns={"size": "books"})
                )
                st.altair_chart(
                    chart_monthly_counts(monthly_counts, "month", "books", "#1E88E5", "Books Read"), 
                    width='stretch'
                )
            else:
                # Fallback to pre-calculated stats object if dataframe calc fails
                gr_stats_obj = st.session_state.get("gr_stats_obj")
                if gr_stats_obj: st.dataframe(pd.DataFrame(gr_stats_obj))

        except Exception as e:
            st.warning(f"Could not compute Goodreads summary: {e}")

        # 3. Read vs Not Read Charts
        st.markdown("**Read vs. Not Read (Library checkouts)**")
        if "rating" in lib_df.columns:
            read_mask = lib_df["rating"].astype(str).str.upper() != "NR"
            counts = pd.DataFrame({
                "status": ["Read", "Not Read"],
                "count": [int(read_mask.sum()), int((~read_mask).sum())]
            })
            
            st.altair_chart(chart_read_status(counts), width='stretch')
            st.caption(f"Read: {int(read_mask.sum())} • Not Read: {int((~read_mask).sum())}")
            
            share_read = (read_mask.sum() / len(lib_df) * 100.0) if len(lib_df) else 0.0
            st.metric("Share of library checkouts actually read", f"{share_read:.1f}%")

            # Top Authors (Read)
            if "author" in lib_df.columns:
                st.markdown("**Top Authors (Read)**")
                top_auth = lib_df.loc[read_mask, "author"].value_counts().head(10).reset_index()
                top_auth.columns = ["author", "count"]
                st.altair_chart(chart_top_authors(top_auth), use_container_width=True)
    else:
        st.info("No library books yet. Click Fetch above.")

def render_wrapup_text():
    st.subheader("Wrap-up")
    content = st.session_state.get("wrapup_text")
    if content:
        st.markdown(content)
    else:
        st.info("No wrap-up text yet. Click Fetch above.")

def render_goodreads_visuals():
    st.divider()
    st.subheader("Goodreads: 2025 Reads")
    gr_books_df = st.session_state.get("gr_books_df", pd.DataFrame())

    if isinstance(gr_books_df, pd.DataFrame) and not gr_books_df.empty:
        st.dataframe(gr_books_df)

        # 1. Ratings Distribution
        if "My Rating" in gr_books_df.columns:
            st.markdown("**Ratings Distribution (Goodreads)**")
            try:
                ratings = gr_books_df["My Rating"].dropna().astype(float)
                if not ratings.empty:
                    hist = ratings.value_counts().sort_index().reset_index()
                    hist.columns = ["rating", "count"]
                    ratings_chart = alt.Chart(hist).mark_bar(color="#2E7D32").encode(
                        x=alt.X("rating:Q", title="Rating"),
                        y=alt.Y("count:Q", title="Count")
                    )
                    st.altair_chart(ratings_chart, container='stretch')
            except Exception:
                pass

        # 2. Interactive Monthly Chart
        if "Date Read" in gr_books_df.columns:
            st.markdown("**Books Read per Month (Goodreads 2025)**")
            try:
                # Prepare data
                df_month = clean_goodreads_data(gr_books_df)
                df_month["month"] = df_month["_date"].dt.month
                df_month["month_name"] = df_month["month"].map(lambda m: pd.Timestamp(2025, int(m), 1).strftime('%b'))
                
                counts = df_month.groupby(["month", "month_name"], as_index=False).size().rename(columns={"size": "count"})
                month_domain = list(range(1, 13))

                sel = alt.selection_point(fields=["month"], bind="legend")

                # Bar Chart
                bar = alt.Chart(counts).mark_bar(color="#4C78A8").encode(
                    x=alt.X("month:O", title="Month", sort="ascending", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=MONTH_LABEL_EXPR)),
                    y=alt.Y("count:Q", title="Books Read"),
                    color=alt.condition(sel, alt.value("#4C78A8"), alt.value("#D3D3D3"))
                ).add_params(sel)

                labels = bar.mark_text(align="center", baseline="bottom", dy=-4, color="#1F2937", font="Inter", fontSize=12).encode(text=alt.Text("count:Q"))

                # Jitter Plot
                author_col = "Author" if "Author" in df_month.columns else ("author" if "author" in df_month.columns else None)
                if author_col: df_month["__author"] = df_month[author_col]
                
                tooltip_fields = ["Title", "My Rating", "month_name"]
                if "__author" in df_month.columns: tooltip_fields.append("__author")

                titles = alt.Chart(df_month).transform_filter(sel).transform_calculate(
                    jitter='(random() - 0.5) * 0.8'
                ).mark_circle(size=48, opacity=0.85, color="#F59E0B").encode(
                    y=alt.Y("Title:N", sort=None, title=None),
                    x=alt.X("month:O", title=None, sort="ascending", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=MONTH_LABEL_EXPR)),
                    xOffset=alt.XOffset("jitter:Q"),
                    tooltip=tooltip_fields
                ).properties(height=400)

                composed = alt.vconcat(bar + labels, titles).resolve_scale(y="independent").properties(bounds="flush")
                st.altair_chart(composed, width='stretch')
                st.caption("Tip: Click a bar to filter. Hover dots to see full titles.")

            except Exception as e:
                st.warning(f"Could not compute interactive books per month: {e}")
    else:
        st.info("No Goodreads books yet. Click Fetch above.")

def render_strava_section():
    st.divider()
    st.subheader("Strava: 2025 Workouts")
    workout_stats = st.session_state.get("workout_stats", {})
    
    if isinstance(workout_stats, dict) and workout_stats:
        try:
            st.dataframe(pd.DataFrame([workout_stats]))
        except Exception: 
            pass

        try:
            # 1. By Type Chart
            if "by_type" in workout_stats and isinstance(workout_stats["by_type"], dict):
                st.markdown("**Workouts by Type**")
                by_type_df = pd.DataFrame(list(workout_stats["by_type"].items()), columns=["type", "count"])
                chart = alt.Chart(by_type_df).mark_bar(color="#546E7A").encode(
                    x=alt.X("type:N", title="Activity Type"),
                    y=alt.Y("count:Q", title="Workouts")
                )
                st.altair_chart(chart, width='stretch')

            # 2. Stacked Monthly Chart
            by_month_by_type = workout_stats.get("by_month_by_type", {})
            if by_month_by_type:
                st.markdown("**Workouts per Month by Type (Stacked)**")
                rows = []
                for m, type_counts in by_month_by_type.items():
                    for t, c in (type_counts or {}).items():
                        rows.append({"month": int(m), "type": str(t), "count": int(c)})
                
                stack_df = pd.DataFrame(rows)
                if not stack_df.empty:
                    stack_df = stack_df.sort_values(["month", "type"])
                    month_domain = list(range(1, 13))
                    
                    stack_chart = alt.Chart(stack_df).mark_bar().encode(
                        x=alt.X("month:O", title="Month", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=MONTH_LABEL_EXPR)),
                        y=alt.Y("count:Q", title="Workouts"),
                        color=alt.Color("type:N", title="Activity Type", scale=alt.Scale(domain=ACTIVITY_ORDER, range=ACTIVITY_COLORS), sort=ACTIVITY_ORDER),
                        tooltip=["month", "type", "count"]
                    )
                    
                    # Totals overlay
                    totals_df = stack_df.groupby('month', as_index=False)['count'].sum().rename(columns={'count': 'total'})
                    labels = alt.Chart(totals_df).mark_text(align='center', baseline='bottom', dy=-4, color='#1F2937', font='Inter', fontSize=12).encode(
                        x=alt.X("month:O", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=MONTH_LABEL_EXPR)),
                        y=alt.Y("total:Q"),
                        text=alt.Text("total:Q")
                    )
                    st.altair_chart(stack_chart + labels, width='stretch')

            # 3. Totals
            st.markdown("**Totals**")
            by_type_counts = workout_stats.get("by_type_counts", {}) or {}
            total_workouts = int(workout_stats.get("workout_count", 0) or 0)
            if total_workouts == 0 and by_type_counts:
                total_workouts = int(sum((v or 0) for v in by_type_counts.values()))
            
            total_time_hours = float(workout_stats.get("total_time_hours", 0) or 0)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Workouts", f"{total_workouts}")
            c2.metric("Total Time (hours)", f"{total_time_hours:.1f}")

        except Exception as e:
            st.error(f"Error rendering Strava visuals: {e}")
    else:
        st.info("No Strava data yet. Click Fetch above.")

def render_comparison_chart():
    st.divider()
    st.subheader("How active vs. how much I read (2025)")
    
    try:
        # Get Book Counts
        gr_df = clean_goodreads_data(st.session_state.get("gr_books_df", pd.DataFrame()))
        books_counts = pd.DataFrame()
        if not gr_df.empty:
            gr_df["month"] = gr_df["_date"].dt.month
            books_counts = gr_df.groupby("month", as_index=False).size().rename(columns={"size": "books"})

        # Get Workout Counts
        workout_stats = st.session_state.get("workout_stats", {})
        workout_counts = pd.DataFrame()
        by_month = workout_stats.get("by_month", {})
        if by_month:
            workout_counts = pd.DataFrame(list(by_month.items()), columns=["month", "workouts"]).sort_values("month")

        # Merge
        month_domain = list(range(1, 13))
        merged = pd.DataFrame({"month": month_domain})
        merged = merged.merge(books_counts, on="month", how="left").merge(workout_counts, on="month", how="left")
        merged = merged.fillna(0)

        # Plot
        base_x = alt.X("month:O", scale=alt.Scale(domain=month_domain), axis=alt.Axis(labelExpr=MONTH_LABEL_EXPR), title="Month")
        left = alt.Chart(merged).mark_line(color="#4C78A8", point=True).encode(x=base_x, y=alt.Y("workouts:Q", title="Workouts"))
        right = alt.Chart(merged).mark_line(color="#F59E0B", point=True).encode(x=base_x, y=alt.Y("books:Q", title="Books Read"))
        
        layered = alt.layer(left, right).resolve_scale(y="independent").properties(width=700, height=300)
        st.altair_chart(layered, width='stretch')

    except Exception as e:
        st.warning(f"Could not build dual-axis chart: {e}")

def render_footer():
    st.markdown("""
    <style>
        .footer {
            position: fixed; left: 0; bottom: 0; width: 100%;
            background-color: #0e1117; color: white;
            text-align: center; padding: 10px 0;
            border-top: 1px solid #262730; z-index: 1000; font-size: 14px;
        }
        .footer a { color: #ff6b6b; text-decoration: none; font-weight: 500; }
        .footer a:hover { color: #ff5252; text-decoration: underline; }
    </style>
    <div class="footer">
        made with <3 in sf | <a href="-https://github.com/elizabethsiegle/sfpl-library-wrapup-2025-do" target="_blank">View on GitHub</a>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN APP FLOW ---

def main():
    render_header()
    
    # Only render content if data exists
    if "lib_df" in st.session_state:
        render_library_section()
        render_wrapup_text()
        render_goodreads_visuals()
        render_strava_section()
        render_comparison_chart()
        
    render_footer()

if __name__ == "__main__":
    main()