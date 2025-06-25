# === overlap_calc.py ===
import requests
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Alignment
import os

def get_sun_data(lat, lon, start_date, end_date, location_name):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "sunrise,sunset",
        "timezone": "UTC",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame({
    "Date": data["daily"]["time"],
    f"{location_name.replace(' ', '_')}_Sunrise_UTC": data["daily"]["sunrise"],
    f"{location_name.replace(' ', '_')}_Sunset_UTC": data["daily"]["sunset"]
})


def calculate_overlap(row, loc1, loc2):
    fmt = "%Y-%m-%dT%H:%M"
    loc1_clean = loc1.replace(" ", "_")
    loc2_clean = loc2.replace(" ", "_")

    # Special case: same location (return total daylight only)
    if loc1_clean == loc2_clean:
        sunrise = datetime.strptime(row[f"{loc1_clean}_Sunrise_UTC"], fmt)
        sunset = datetime.strptime(row[f"{loc1_clean}_Sunset_UTC"], fmt)
        duration = (sunset - sunrise).total_seconds() / 60
        return round(duration), 0, round(duration)

    a_sunrise = datetime.strptime(row[f"{loc1_clean}_Sunrise_UTC"], fmt)
    a_sunset = datetime.strptime(row[f"{loc1_clean}_Sunset_UTC"], fmt)
    b_sunrise = datetime.strptime(row[f"{loc2_clean}_Sunrise_UTC"], fmt)
    b_sunset = datetime.strptime(row[f"{loc2_clean}_Sunset_UTC"], fmt)

    instance1_start = max(a_sunrise, b_sunrise)
    instance1_end = min(a_sunset, b_sunset)
    instance1 = max(0, (instance1_end - instance1_start).total_seconds() / 60)

    a_sunrise_next = a_sunrise + timedelta(days=1)
    a_sunset_next = a_sunset + timedelta(days=1)
    instance2a = max(0, (min(a_sunset_next, b_sunset) - max(a_sunrise_next, b_sunrise)).total_seconds() / 60)

    b_sunrise_next = b_sunrise + timedelta(days=1)
    b_sunset_next = b_sunset + timedelta(days=1)
    instance2b = max(0, (min(b_sunset_next, a_sunset) - max(b_sunrise_next, a_sunrise)).total_seconds() / 60)

    instance2 = max(instance2a, instance2b)
    total_overlap = instance1 + instance2

    return round(instance1), round(instance2), round(total_overlap)


def compute_overlap_dataframe(loc1, lat1, lon1, loc2, lat2, lon2, start_str, end_str):
    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    loc1_clean = loc1.replace(" ", "_")
    loc2_clean = loc2.replace(" ", "_")

    # Add suffixes to differentiate even if loc1 == loc2
    df1 = get_sun_data(lat1, lon1, start_date, end_date, f"{loc1_clean}_A")
    df2 = get_sun_data(lat2, lon2, start_date, end_date, f"{loc2_clean}_B")

    df = pd.merge(df1, df2, on="Date")

    df[["Overlap Instance 1 (min)", "Overlap Instance 2 (min)", "Total Overlap (min)"]] = df.apply(
        lambda row: calculate_overlap(row, f"{loc1_clean}_A", f"{loc2_clean}_B"), axis=1, result_type="expand")

    filename = f"Sun_Overlap_{loc1_clean}_{loc2_clean}_{start_date.year}.xlsx"
    filepath = os.path.join("generated_files", filename)
    os.makedirs("generated_files", exist_ok=True)
    df.to_excel(filepath, index=False)

    # Apply Excel styling
    wb = load_workbook(filepath)
    ws = wb.active
    for col in ws.columns:
        max_len = max(len(str(cell.value)) for cell in col if cell.value)
        for cell in col:
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.column_dimensions[col[0].column_letter].width = max_len + 2
    wb.save(filepath)

    return df, filename
