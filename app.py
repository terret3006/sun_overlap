from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import pandas as pd
from flask import session
import base64
from io import BytesIO
from utils.overlap_calc import compute_overlap_dataframe
app = Flask(__name__)
app.secret_key = "afmjbegfjub3"  
import requests 
from datetime import timedelta
from datetime import datetime, timedelta
import re
from flask import jsonify
app.permanent_session_lifetime = timedelta(minutes=100)

import uuid

app = Flask(__name__)
app.secret_key = "your_secret_key"
temp_cache = {}  



@app.route("/api/date-range")
def get_api_date_range():
    test_url = "https://api.open-meteo.com/v1/forecast"
    today = datetime.utcnow().date()
    params = {
        "latitude": 0, 
        "longitude": 0,
        "daily": "sunrise,sunset",
        "timezone": "UTC",
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today + timedelta(days=20)).strftime("%Y-%m-%d")
    }

    try:
        response = requests.get(test_url, params=params)
        if response.status_code == 400:
            error_msg = response.json().get("reason", "")
            match = re.search(r"from (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", error_msg)
            if match:
                min_date = match.group(1)
                max_date = match.group(2)
                print(f"[✔] Open-Meteo date range detected: {min_date} to {max_date}")
                return jsonify({
                    "min_date": min_date,
                    "max_date": max_date
                })
    except Exception as e:
        print("[❌] Error detecting API range:", e)

    print("[⚠️] Using fallback date range due to failure.")
    return jsonify({
        "min_date": "2016-01-01",
        "max_date": (today + timedelta(days=7)).strftime("%Y-%m-%d")
    })



@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # print(request.form)
        try:
            lat1 = float(request.form["loc1_lat"])
            lon1 = float(request.form["loc1_lon"])
            lat2 = float(request.form["loc2_lat"])
            lon2 = float(request.form["loc2_lon"])
            start = request.form["start_date"]
            end = request.form["end_date"]

            if start > end:
                flash("🚫 Start date cannot be later than End date!", "error")
                return redirect(url_for("index"))

            loc1 = request.form.get("loc1_name", "Location_1")
            loc2 = request.form.get("loc2_name", "Location_2")

            # Compute overlap and get DataFrame + filename (not Excel content here)
            df, _, filename = compute_overlap_dataframe(loc1, lat1, lon1, loc2, lat2, lon2, start, end)
            table_html = df.to_html(index=False, classes="styled-table")

            # Create unique token to associate download with this DF
            token = str(uuid.uuid4())
            temp_cache[token] = {
                "df": df,
                "filename": filename
            }

            return render_template(
                "index.html",
                table=table_html,
                download_token=token,
                loc1_name=loc1,
                loc2_name=loc2,
                start_date=start,
                end_date=end,
                loc1_lat=lat1,
                loc1_lon=lon1,
                loc2_lat=lat2,
                loc2_lon=lon2
            )
        except Exception as e:
            flash(f"❌ Error: {e}", "error")
            return redirect(url_for("index"))

    return render_template("index.html")

@app.route("/reset")
def reset():
    session.clear()
    temp_cache.clear()
    return redirect(url_for("index"))


from flask import send_file
from io import BytesIO
import pandas as pd
from openpyxl.styles import Alignment
from openpyxl import load_workbook


@app.route("/download/<token>")
def download(token):
    if token not in temp_cache:
        flash("⚠️ No Excel data available to download.")
        return redirect(url_for("index"))

    data = temp_cache.pop(token)
    df = data["df"]
    filename = data["filename"]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
        ws = writer.book.active

        # Styling
        for col in ws.columns:
            max_len = max(len(str(cell.value)) for cell in col if cell.value)
            for cell in col:
                cell.alignment = Alignment(horizontal='center', vertical='center')
            ws.column_dimensions[col[0].column_letter].width = max_len + 2

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
