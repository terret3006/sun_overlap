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


from datetime import datetime
import pandas as pd
from openpyxl.styles import Alignment
from io import BytesIO
from openpyxl import load_workbook

def compute_overlap_dataframe(loc1, lat1, lon1, loc2, lat2, lon2, start_str, end_str):
    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    loc1_clean = loc1.replace(" ", "_")
    loc2_clean = loc2.replace(" ", "_")
    date_range_str = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"

    # Get sun data for both locations
    df1 = get_sun_data(lat1, lon1, start_date, end_date, f"{loc1_clean}_A")
    df2 = get_sun_data(lat2, lon2, start_date, end_date, f"{loc2_clean}_B")

    # Merge on date
    df = pd.merge(df1, df2, on="Date")

    # Compute overlaps
    df[["Overlap Instance 1 (min)", "Overlap Instance 2 (min)", "Total Overlap (min)"]] = df.apply(
        lambda row: calculate_overlap(row, f"{loc1_clean}_A", f"{loc2_clean}_B"),
        axis=1,
        result_type="expand"
    )

    # Only return the DataFrame and filename (no saving here)
    filename = f"Sun_Overlap_{loc1_clean}_and_{loc2_clean}_{date_range_str}.xlsx"
    return df, None, filename  # second value is unused in this design
from timezonefinder import TimezoneFinder
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

WEATHERAPI_KEY = "aa555203c4814255ad1154017251102"
tf = TimezoneFinder()

def to_utc(date_str, time_str, lat, lon):
    if not time_str or "No" in time_str:
        return None
    try:
        local_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
        timezone_str = tf.timezone_at(lat=lat, lng=lon)
        if timezone_str is None:
            return None
        local_zone = pytz.timezone(timezone_str)
        local_dt = local_zone.localize(local_time)
        return local_dt.astimezone(pytz.utc)
    except Exception as e:
        print(f"[❌] to_utc conversion failed for {time_str} on {date_str}: {e}")
        return None

def get_moon_data(lat, lon, start_date, end_date, location_name):
    dates = pd.date_range(start=start_date, end=end_date)
    records = []

    for i, date in enumerate(dates):
        url = "https://api.weatherapi.com/v1/astronomy.json"
        params = {
            "key": WEATHERAPI_KEY,
            "q": f"{lat},{lon}",
            "dt": date.strftime("%Y-%m-%d")
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            astro = data["astronomy"]["astro"]

            moonrise = astro.get("moonrise", "").strip()
            moonset = astro.get("moonset", "").strip()
            moonrise_source_date = date
            adjusted = False

            # Check next day if moonrise is missing
            if "No" in moonrise and i + 1 < len(dates):
                next_day = dates[i + 1]
                next_url = "https://api.weatherapi.com/v1/astronomy.json"
                next_params = {
                    "key": WEATHERAPI_KEY,
                    "q": f"{lat},{lon}",
                    "dt": next_day.strftime("%Y-%m-%d")
                }
                next_resp = requests.get(next_url, params=next_params)
                next_resp.raise_for_status()
                next_data = next_resp.json()
                next_moonrise = next_data["astronomy"]["astro"].get("moonrise", "").strip()

                if next_moonrise and "No" not in next_moonrise:
                    next_moonrise_dt = to_utc(next_day.strftime("%Y-%m-%d"), next_moonrise, lat, lon)
                    if next_moonrise_dt:
                        local_zone = pytz.timezone(tf.timezone_at(lat=lat, lng=lon))
                        local_time = next_moonrise_dt.astimezone(local_zone)
                        if local_time.hour < 3:
                            moonrise = next_moonrise
                            moonrise_source_date = next_day
                            adjusted = True

            moonrise_utc = to_utc(moonrise_source_date.strftime("%Y-%m-%d"), moonrise, lat, lon)
            moonset_utc = to_utc(date.strftime("%Y-%m-%d"), moonset, lat, lon)

            if moonrise_utc and moonset_utc and moonset_utc < moonrise_utc:
                moonset_utc += timedelta(days=1)

            records.append({
                "Date": date.strftime("%Y-%m-%d"),
                f"{location_name}_Moonrise": moonrise + (" *" if adjusted else ""),
                f"{location_name}_Moonset": moonset,
                f"{location_name}_Moonrise_UTC": moonrise_utc,
                f"{location_name}_Moonset_UTC": moonset_utc,
            })

        except Exception as e:
            print(f"[❌] WeatherAPI error for {location_name} on {date.date()}: {e}")
            continue

    return pd.DataFrame(records)

def calculate_moon_overlap(row, loc1, loc2):
    rise1 = row.get(f"{loc1}_Moonrise_UTC")
    set1 = row.get(f"{loc1}_Moonset_UTC")
    rise2 = row.get(f"{loc2}_Moonrise_UTC")
    set2 = row.get(f"{loc2}_Moonset_UTC")

    if None in (rise1, set1, rise2, set2):
        return 0, 0, 0

    instance1_start = max(rise1, rise2)
    instance1_end = min(set1, set2)

    instance1 = max(0, (instance1_end - instance1_start).total_seconds() / 60)

    # Instance 2 logic: Check if one location's moonrise/set overlaps with next day's of the other
    instance2 = 0
    if rise1 < set2 < set1 and rise2 > set1:
        # edge case where second location's moon is still up after loc1 moon has set
        extra_overlap = min(set2, rise2 + timedelta(hours=12)) - set1
        instance2 = max(0, extra_overlap.total_seconds() / 60)

    total_overlap = instance1 + instance2
    return round(instance1), round(instance2), round(total_overlap)

def compute_moon_overlap_dataframe(loc1, lat1, lon1, loc2, lat2, lon2, start_str, end_str):
    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    loc1_clean = loc1.replace(" ", "_")
    loc2_clean = loc2.replace(" ", "_")
    date_range_str = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"

    df1 = get_moon_data(lat1, lon1, start_date, end_date, loc1_clean + "_A")
    df2 = get_moon_data(lat2, lon2, start_date, end_date, loc2_clean + "_B")

    df = pd.merge(df1, df2, on="Date")

    df[["Overlap Instance 1 (min)", "Overlap Instance 2 (min)", "Total Overlap (min)"]] = df.apply(
        lambda row: calculate_moon_overlap(row, loc1_clean + "_A", loc2_clean + "_B"),
        axis=1,
        result_type="expand"
    )

    filename = f"Moon_Overlap_{loc1_clean}_and_{loc2_clean}_{date_range_str}.xlsx"
    return df, None, filename
