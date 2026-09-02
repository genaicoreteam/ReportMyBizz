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
from flask import Flask, render_template, request, send_file, flash, redirect, url_for

import config
from core.report_builder import build_report, ReportGenerationError
from core.place_resolver import PlaceResolutionError

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", api_key_set=bool(config.GOOGLE_MAPS_API_KEY))


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


@app.route("/download/<run_id>")
def download(run_id):
    pdf_path = os.path.join(config.OUTPUT_DIR, run_id, "ReportMyBizz_Report.pdf")
    if not os.path.exists(pdf_path):
        flash("Report not found -- please generate it again.", "error")
        return redirect(url_for("index"))
    return send_file(pdf_path, as_attachment=True,
                      download_name="ReportMyBizz_Report.pdf")


if __name__ == "__main__":
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    app.run(debug=True, port=5000)
