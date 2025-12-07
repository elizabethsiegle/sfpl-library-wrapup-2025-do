import pandas as pd
from typing import Dict, Any, List

# --- Constants ---

CORE_COLUMNS = [
    'Activity ID', 'Activity Date', 'Activity Name', 'Activity Type',
    'Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
    'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
    'Calories', 'Relative Effort', 'Filename'
]

NUMERIC_COLUMNS = [
    'Elapsed Time', 'Moving Time', 'Distance', 'Average Speed', 'Max Speed',
    'Elevation Gain', 'Elevation Loss', 'Average Heart Rate', 'Max Heart Rate',
    'Calories', 'Relative Effort'
]

# Regex patterns for activity categorization
ACTIVITY_PATTERNS = {
    'Tennis': r"\btennis\b|\bhit\b|\bhitting\b|\bhit session\b",
    'Basketball': r"\bbasketball\b|\bbball\b|\bpickup\b",
    'Volleyball': r"\bvolleyball\b|\bvball\b",
    'Pickleball': r"\bpickleball\b|\bpickle\b|\bpb\b"
}

KM_TO_MILES = 0.621371


# --- Helper Functions ---

def _convert_to_miles(series: pd.Series) -> float:
    """Helper to safely convert a KM series to a scalar Miles float."""
    if series.empty:
        return 0.0
    return float(pd.to_numeric(series, errors='coerce').mean() * KM_TO_MILES)


# --- Main Logic ---

def clean_workouts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Select relevant columns, parse types, and return a tidy workouts DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame()

    # 1. Filter Columns
    keep = [c for c in CORE_COLUMNS if c in df.columns]
    tidy = df[keep].copy()

    # 2. Parse Dates
    if 'Activity Date' in tidy.columns:
        tidy['Activity Date'] = pd.to_datetime(
            tidy['Activity Date'], format='%b %d, %Y, %I:%M:%S %p', errors='coerce'
        )
        tidy = tidy.dropna(subset=['Activity Date'])

    # 3. Numeric Conversion
    for col in NUMERIC_COLUMNS:
        if col in tidy.columns:
            tidy[col] = pd.to_numeric(tidy[col], errors='coerce')

    # 4. Re-categorize generic workouts
    if 'Activity Name' in tidy.columns:
        if 'Activity Type' not in tidy.columns:
            tidy['Activity Type'] = 'Workout'

        name_lower = tidy['Activity Name'].astype(str).str.lower()
        
        # Identify generic types we want to override
        is_generic = tidy['Activity Type'].astype(str).str.lower().isin(['workout', 'other', '']) | tidy['Activity Type'].isna()

        for new_type, pattern in ACTIVITY_PATTERNS.items():
            matches_pattern = name_lower.str.contains(pattern, na=False, regex=True)
            tidy.loc[is_generic & matches_pattern, 'Activity Type'] = new_type

    return tidy


def compute_workout_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute useful aggregates for a year of workouts."""
    defaults = {
        'workout_count': 0, 'total_time_hours': 0.0, 'by_type_counts': {},
        'by_type_distance_miles': {}, 'avg_distance_miles': 0.0, 'avg_speed_mph': 0.0,
        'max_speed_mph': 0.0, 'total_elev_gain_m': 0.0, 'avg_heart_rate': 0.0,
        'max_heart_rate': 0.0, 'total_calories': 0.0
    }

    if df is None or df.empty:
        return defaults

    # Basic Counts
    workout_count = len(df)
    by_type_counts = df['Activity Type'].value_counts(dropna=False).to_dict() if 'Activity Type' in df.columns else {}

    # Distance & Speed Stats (KM -> Miles)
    avg_distance_miles = _convert_to_miles(df.get('Distance', pd.Series(dtype=float)))
    avg_speed_mph = _convert_to_miles(df.get('Average Speed', pd.Series(dtype=float)))
    
    # Max speed requires a slightly different safe handling than the helper provides (max vs mean)
    max_speed_kmh = pd.to_numeric(df.get('Max Speed', pd.Series(dtype=float)), errors='coerce')
    max_speed_mph = float(max_speed_kmh.max() * KM_TO_MILES) if not max_speed_kmh.empty else 0.0

    # Physical Stats
    total_elev_gain_m = float(df.get('Elevation Gain', pd.Series(dtype=float)).sum())
    avg_heart_rate = float(df.get('Average Heart Rate', pd.Series(dtype=float)).mean())
    max_heart_rate = float(df.get('Max Heart Rate', pd.Series(dtype=float)).max())
    total_calories = float(df.get('Calories', pd.Series(dtype=float)).sum())

    # Time Calculation (Prefer Moving, fallback to Elapsed)
    moving = df.get('Moving Time', pd.Series(dtype=float)).sum()
    elapsed = df.get('Elapsed Time', pd.Series(dtype=float)).sum()
    total_time_sec = moving if moving > 0 else elapsed
    total_time_hours = total_time_sec / 3600.0

    # Distance by Type
    by_type_distance_miles = {}
    if 'Activity Type' in df.columns and 'Distance' in df.columns:
        temp_df = df[['Activity Type', 'Distance']].copy()
        temp_df['Distance'] = pd.to_numeric(temp_df['Distance'], errors='coerce') * KM_TO_MILES
        by_type_distance_miles = temp_df.groupby('Activity Type')['Distance'].sum().round(2).to_dict()

    return {
        'workout_count': int(workout_count),
        'by_type_counts': by_type_counts,
        'by_type_distance_miles': by_type_distance_miles,
        'avg_distance_miles': round(avg_distance_miles, 2),
        'avg_speed_mph': round(avg_speed_mph, 2),
        'max_speed_mph': round(max_speed_mph, 2),
        'total_elev_gain_m': round(total_elev_gain_m, 0),
        'avg_heart_rate': round(0.0 if pd.isna(avg_heart_rate) else avg_heart_rate, 1),
        'max_heart_rate': round(0.0 if pd.isna(max_heart_rate) else max_heart_rate, 0),
        'total_calories': round(total_calories, 0),
        'total_time_hours': round(total_time_hours, 1),
    }


def compute_activities_per_month_by_type(df: pd.DataFrame) -> Dict[str, Dict[int, int]]:
    """Return counts of activities per type for each month (1..12)."""
    if df is None or df.empty or 'Activity Date' not in df.columns:
        return {}

    # Prepare data
    df = df.copy()
    df['month'] = pd.to_datetime(df['Activity Date'], errors='coerce').dt.month
    
    if 'Activity Type' not in df.columns:
        df['Activity Type'] = 'Unknown'
    else:
        df['Activity Type'] = df['Activity Type'].fillna('Unknown').astype(str)

    # Group by Type and Month
    # Result: Series with MultiIndex (Activity Type, month) -> count
    grouped = df.groupby(['Activity Type', 'month']).size()

    # Format result structure
    result = {}
    unique_types = df['Activity Type'].unique()
    
    for act_type in unique_types:
        result[act_type] = {m: 0 for m in range(1, 13)}
        # Fill in actual counts where they exist
        if act_type in grouped:
            for month, count in grouped[act_type].items():
                result[act_type][int(month)] = int(count)

    return result