"""
app.py
ReportMyBizz -- paste a public Google Business Profile link, get a real,
data-backed PDF audit report back. No dummy data: every number traces to
a live Google API call (see core/report_builder.py).

Run:
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import traceback
import googlemaps
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify

import config
from core.report_builder import build_report, ReportGenerationError
from core.place_resolver import PlaceResolutionError, autocomplete_predictions

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", api_key_set=bool(config.GOOGLE_MAPS_API_KEY))


@app.route("/api/places/autocomplete", methods=["GET"])
def places_autocomplete():
    """Type-ahead used by the business-name dropdown on the home page.
    Proxied server-side so the Maps API key never reaches the browser."""
    query = request.args.get("q", "")
    session_token = request.args.get("session", None)

    if not config.GOOGLE_MAPS_API_KEY or len(query.strip()) < 3:
        return jsonify({"predictions": []})

    gmaps_client = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)
    predictions = autocomplete_predictions(query, gmaps_client, session_token)
    return jsonify({"predictions": predictions})


@app.route("/generate", methods=["POST"])
def generate():
    link = request.form.get("gbp_link", "").strip()
    if not link:
        flash("Please paste a public Google Business Profile link.", "error")
        return redirect(url_for("index"))

    try:
        context = build_report(link)
    except PlaceResolutionError as e:
        flash(f"Could not identify that business: {e}", "error")
        return redirect(url_for("index"))
    except ReportGenerationError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))
    except Exception as e:
        traceback.print_exc()
        flash(f"Unexpected error while generating the report: {e}", "error")
        return redirect(url_for("index"))

    return render_template("index.html",
                            api_key_set=bool(config.GOOGLE_MAPS_API_KEY),
                            result=context)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
