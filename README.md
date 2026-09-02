# ReportMyBizz

Paste a **public Google Business Profile link**, get back a real, data-backed
PDF audit report — Google Search rank across a geogrid, competitor comparison,
profile completeness, and reviews — styled in an elegant green & cream theme.

## What makes this different from a template

**No dummy data, anywhere.** Every number in the PDF traces back to a live
Google API response captured at generation time. Where genuine public data
does not exist for a metric (e.g. review response rate, exact suspension
risk — these require the profile *owner* to be logged in), the report
explicitly labels it "Not available via public API" instead of inventing a
plausible-looking number. See `core/scoring.py` for the fully transparent
scoring formula — nothing is a black box.

## What it fetches (real, live data)

| Report section | Source | Notes |
|---|---|---|
| Business name, rating, address, phone, website, categories | Google Places API — Place Details | Free tier |
| Search Rank (avg rank per keyword) | Google Places API — Nearby Search, run across a real NxN geogrid | Same method paid rank-trackers use |
| Competitors ranking above you | Byproduct of the geogrid sweep | Real place names & ranks |
| Grid map visuals | `staticmap` + free OpenStreetMap tiles | No Google Static Maps billing |
| Profile completeness checklist | Google Places API fields (name, category, address, phone, website, hours, photos, description) | Fields Google doesn't expose publicly are clearly marked, not guessed |
| Reviews / week estimate | Computed from the up-to-5 public reviews Google returns | Labeled as a small-sample estimate, not full history |
| Review response rate | **Not available** | Requires Business Profile owner login — no public API exposes this. Shown as "N/A" in the report, never fabricated. |
| Profile Score | Custom transparent formula (35% rank, 25% rating, 20% review volume, 20% completion) computed from the real data above | Documented in the PDF itself |

## Requirements

- Python 3.9+
- A **free** Google Maps Platform API key (see below)
- Internet access (to Google's API and OpenStreetMap tile servers)

## Setup

```bash
# 1. Unzip and enter the project
cd ReportMyBizz

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your free API key
cp .env.example .env
# open .env and paste your key into GOOGLE_MAPS_API_KEY=

# 5. Run
python app.py
```

Then open **http://127.0.0.1:5000** in your browser, paste a public Google
Business Profile / Maps link, and click **Generate Real Report**.

## Getting a free Google Maps API key (no cost to you)

1. Go to https://console.cloud.google.com/ and create a project (free).
2. Go to **APIs & Services → Library** and enable:
   - **Places API**
   - **Geocoding API**
3. Go to **APIs & Services → Credentials → Create Credentials → API Key**.
4. Copy the key into your `.env` file.
5. (Recommended) Under the key's restrictions, restrict it to the two APIs
   above so it can't be misused elsewhere.

Google's Maps Platform gives every account a recurring monthly usage credit
that comfortably covers **dozens of reports per month** for personal or
small-agency use before any charge would apply — see the "Cost" section
below for the exact math.

## What input link formats work

- Full Maps URL: `https://www.google.com/maps/place/Business+Name/@lat,lng,...`
- Shortened share link: `https://maps.app.goo.gl/xxxxxxxx`
- A CID-based link: `https://www.google.com/maps?cid=1234567890`
- A raw Place ID (starts with `ChIJ...`), if you already have one

The resolver (`core/place_resolver.py`) tries each of these strategies in
order and raises a clear error if none of them work — it will never
silently guess the wrong business.

## Cost — how this stays free

- **Grid size** defaults to 5x5 = 25 points, and keywords default to up to
  5 auto-derived categories → **≤125 Nearby Search calls per report**, plus
  a couple of Place Details / Find Place calls.
- Google's Places API "Nearby Search" and "Place Details" both draw from the
  same monthly Maps Platform usage credit. At typical Places API pricing,
  one full report uses a small fraction of that monthly credit — comfortably
  enough for casual or small-agency use without a charge.
- Map images use free OpenStreetMap tiles via the `staticmap` library — no
  Google Static Maps billing at all.
- If you want to reduce usage further, lower `GRID_SIZE` or `MAX_KEYWORDS`
  in `.env` / `config.py` (e.g. `GRID_SIZE=3` → 9 points instead of 25).

**You are responsible for monitoring your own Google Cloud billing/quota
dashboard** if you run this at high volume — set a budget alert in Google
Cloud Console as a safety net.

## Project structure

```
ReportMyBizz/
├── app.py                    # Flask web app (entry point)
├── config.py                 # All tunables (grid size, radius, colors)
├── requirements.txt
├── .env.example               # Copy to .env and add your API key
├── core/
│   ├── place_resolver.py     # Turns any GBP link into a Place ID
│   ├── place_details.py      # Fetches real Place Details from Google
│   ├── grid_utils.py         # Geogrid point generation math
│   ├── rank_tracker.py       # Runs the real Nearby Search rank sweep
│   ├── review_analyzer.py    # Real review stats + honest N/A labeling
│   ├── profile_auditor.py    # Real completeness checklist
│   ├── scoring.py            # Transparent, documented scoring formula
│   ├── map_renderer.py       # Grid map PNGs via free OSM tiles
│   └── report_builder.py     # Orchestrates the full pipeline + PDF
├── templates/
│   ├── index.html            # Web UI (green & cream theme)
│   └── report.html           # PDF template (xhtml2pdf-compatible HTML/CSS)
├── static/
│   └── style.css             # Green & cream theme for the web UI
└── output/                   # Generated PDFs land here (per-run folder)
```

## Known limitations (stated honestly, not hidden)

- **Rank accuracy**: Google's public Places API ranking is not guaranteed
  to be pixel-identical to what a human sees in the consumer Local Pack —
  Google doesn't publish that exact algorithm to any third party, paid or
  free. This is disclosed in the PDF footer.
- **Review sample size**: Google's public API caps review data at the 5
  most recent reviews. "Reviews/week" is estimated from that small sample
  and clearly labeled as such — it is not a full review-history metric.
- **Response rate / suspension risk / exact services list**: these require
  the Business Profile *owner* to be authenticated via the separate Google
  Business Profile API. There is no public workaround, so this tool marks
  them "Not available" rather than guessing.
- **Business types on Places API** are Google's own generic category tags,
  not the richer, owner-curated category list visible in the GBP dashboard —
  keyword derivation uses only what's genuinely public.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "No Google Maps API key configured" | `.env` missing or key not pasted in |
| "Could not resolve a Place ID" | Link format not recognized — try pasting the full (non-shortened) Maps URL, or the Place ID directly |
| Map images missing in PDF | OpenStreetMap tile servers were unreachable at generation time; all rank data is still real, only the visual is skipped |
| `REQUEST_DENIED` from Google | Places API / Geocoding API not enabled on your key, or billing not set up on the Google Cloud project (required even for free-tier usage) |

## License

Build it, modify it, use it for client work — it's yours.
