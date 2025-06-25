from flask import Flask, render_template, request, send_file
import pandas as pd
from utils.overlap_calc import compute_overlap_dataframe  # Your script as a function
import io
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, get_flashed_messages

app = Flask(__name__)

# Location dictionary for dropdowns
LOCATIONS = {
    "Delhi": (28.6139, 77.2090),
    "Maine": (43.6591, -70.2568),
    "Texas": (30.2672, -97.7431),
    "Illinois": (41.8781, -87.6298),
    "Mexico": (19.4326, -99.1332),
    "Bangalore": (12.9716, 77.5946),
    "United_Kingdom": (51.5072, -0.1276),
    "New_Zealand": (-41.2865, 174.7762),
    "Saskatchewan": (50.4452, -104.6189),
    "Perth_Australia": (-31.9505, 115.8605),
    "Toronto_Ontario": (43.651070, -79.347015),
    "Tokyo_Japan": (35.6895, 139.6917),
    "Sao_Paulo_Brazil": (-23.5505, -46.6333)
}
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        loc1 = request.form["loc1"]
        loc2 = request.form["loc2"]
        start = request.form["start_date"]
        end = request.form["end_date"]

        lat1, lon1 = LOCATIONS[loc1]
        lat2, lon2 = LOCATIONS[loc2]
        if start > end:
            flash("🚫 Start date cannot be later than End date!", "error")
            return redirect(url_for("index"))

        df, filename = compute_overlap_dataframe(loc1, lat1, lon1, loc2, lat2, lon2, start, end)
        table_html = df.to_html(index=False, classes="styled-table")

        return render_template("index.html", locations=LOCATIONS.keys(), table=table_html, filename=filename)

    return render_template("index.html", locations=LOCATIONS.keys())

@app.route("/download/<filename>")
def download(filename):
    path = f"generated_files/{filename}"
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
