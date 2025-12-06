import pandas as pd


def clean_workouts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Select relevant columns, parse types, and return a tidy workouts DataFrame.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame()

    core_cols = [
        'Activity ID', 'Activity Date', 'Activity Name', 'Activity Type',
        'Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
        'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
        'Calories', 'Relative Effort', 'Filename'
    ]

    keep = [c for c in core_cols if c in df.columns]
    tidy = df[keep].copy()

    if 'Activity Date' in tidy.columns:
        tidy['Activity Date'] = pd.to_datetime(
            tidy['Activity Date'], format='%b %d, %Y, %I:%M:%S %p', errors='coerce'
        )
        tidy = tidy.dropna(subset=['Activity Date'])

    for col in ['Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
                'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
                'Calories', 'Relative Effort']:
        if col in tidy.columns:
            tidy[col] = pd.to_numeric(tidy[col], errors='coerce')

    # Re-categorize generic workouts based on Activity Name keywords
    if 'Activity Name' in tidy.columns:
        name_lower = tidy['Activity Name'].astype(str).str.lower()
        # Keyword aliases (word-boundary where meaningful)
        tennis_pat = r"\btennis\b|\bhit\b|\bhitting\b|\bhit session\b"
        basketball_pat = r"\bbasketball\b|\bbball\b|\bpickup\b"
        volleyball_pat = r"\bvolleyball\b|\bvball\b"
        pickleball_pat = r"\bpickleball\b|\bpickle\b|\bpb\b"

        is_tennis = name_lower.str.contains(tennis_pat, na=False, regex=True)
        is_basketball = name_lower.str.contains(basketball_pat, na=False, regex=True)
        is_volleyball = name_lower.str.contains(volleyball_pat, na=False, regex=True)
        is_pickleball = name_lower.str.contains(pickleball_pat, na=False, regex=True)
        # Initialize Activity Type if missing
        if 'Activity Type' not in tidy.columns:
            tidy['Activity Type'] = pd.Series(['Workout'] * len(tidy))
        # Only override when original type is generic 'Workout' or missing
        generic = tidy['Activity Type'].astype(str).str.lower().isin(['workout', 'other', '']) | tidy['Activity Type'].isna()
        tidy.loc[generic & is_tennis, 'Activity Type'] = 'Tennis'
        tidy.loc[generic & is_basketball, 'Activity Type'] = 'Basketball'
        tidy.loc[generic & is_volleyball, 'Activity Type'] = 'Volleyball'
        tidy.loc[generic & is_pickleball, 'Activity Type'] = 'Pickleball'

    return tidy


def compute_workout_stats(df: pd.DataFrame) -> dict:
    """Compute useful aggregates for a year of workouts.

    Returns a dict with totals and highlights to feed an LLM.
    """
    if df is None or len(df) == 0:
        return {
            'workout_count': 0,
            'total_distance_miles': 0.0,
            'avg_distance_miles': 0.0,
            'longest_distance_miles': 0.0,
            'longest_activity_name': None,
            'avg_speed_mph': 0.0,
            'max_speed_mph': 0.0,
            'total_elev_gain_m': 0.0,
            'avg_heart_rate': 0.0,
            'max_heart_rate': 0.0,
            'total_calories': 0.0,
            'by_type_counts': {},
            'by_type_distance_miles': {},
        }

    workout_count = len(df)
    by_type_counts = df['Activity Type'].value_counts(dropna=False).to_dict() if 'Activity Type' in df.columns else {}

    dist = df['Distance'] if 'Distance' in df.columns else pd.Series(dtype=float)
    # Convert kilometers to miles
    km_series = pd.to_numeric(dist, errors='coerce') if len(dist) else pd.Series(dtype=float)
    total_distance_miles = float(km_series.sum() * 0.621371) if len(km_series) else 0.0
    avg_distance_miles = float(km_series.mean() * 0.621371) if len(km_series) else 0.0
    longest_distance_miles = float(km_series.max() * 0.621371) if len(km_series) else 0.0
    longest_idx = pd.to_numeric(dist, errors='coerce').idxmax() if len(dist) else None
    longest_activity_name = df.loc[longest_idx, 'Activity Name'] if longest_idx is not None and 'Activity Name' in df.columns else None

    # Convert km/h to mph
    avg_speed_kmh_series = pd.to_numeric(df['Average Speed'], errors='coerce') if 'Average Speed' in df.columns else pd.Series(dtype=float)
    max_speed_kmh_series = pd.to_numeric(df['Max Speed'], errors='coerce') if 'Max Speed' in df.columns else pd.Series(dtype=float)
    avg_speed_mph = float(avg_speed_kmh_series.mean() * 0.621371) if len(avg_speed_kmh_series) else 0.0
    max_speed_mph = float(max_speed_kmh_series.max() * 0.621371) if len(max_speed_kmh_series) else 0.0

    total_elev_gain_m = float(pd.to_numeric(df['Elevation Gain'], errors='coerce').sum()) if 'Elevation Gain' in df.columns else 0.0

    avg_heart_rate = float(pd.to_numeric(df['Average Heart Rate'], errors='coerce').mean()) if 'Average Heart Rate' in df.columns else 0.0
    max_heart_rate = float(pd.to_numeric(df['Max Heart Rate'], errors='coerce').max()) if 'Max Heart Rate' in df.columns else 0.0

    total_calories = float(pd.to_numeric(df['Calories'], errors='coerce').sum()) if 'Calories' in df.columns else 0.0

    if 'Activity Type' in df.columns and 'Distance' in df.columns:
        by_type_distance_miles = (
            df[['Activity Type', 'Distance']]
            .assign(Distance=pd.to_numeric(df['Distance'], errors='coerce') * 0.621371)
            .groupby('Activity Type', dropna=False)['Distance']
            .sum()
            .round(2)
            .to_dict()
        )
    else:
        by_type_distance_miles = {}

    return {
        'workout_count': int(workout_count),
        'total_distance_miles': round(total_distance_miles, 2),
        'avg_distance_miles': round(avg_distance_miles, 2),
        'longest_distance_miles': round(longest_distance_miles, 2),
        'longest_activity_name': longest_activity_name,
        'avg_speed_mph': round(avg_speed_mph, 2),
        'max_speed_mph': round(max_speed_mph, 2),
        'total_elev_gain_m': round(total_elev_gain_m, 0),
        'avg_heart_rate': round(avg_heart_rate, 1),
        'max_heart_rate': round(max_heart_rate, 0),
        'total_calories': round(total_calories, 0),
        'by_type_counts': by_type_counts,
        'by_type_distance_miles': by_type_distance_miles,
    }