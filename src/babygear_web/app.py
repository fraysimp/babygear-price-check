"""Flask application for BabyGear Price Calculator."""

import json
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, render_template

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "babygear.db"
DEFAULT_METRO = "boston_ma"

app = Flask(__name__)
app.config["DB_PATH"] = str(DEFAULT_DB_PATH)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_landing_tables(db: sqlite3.Connection):
    db.execute(
        """CREATE TABLE IF NOT EXISTS email_signups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            source TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            properties TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    db.commit()


# ---------- Pages ----------

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/app")
def index():
    return render_template("index.html")


# ---------- API ----------

@app.route("/api/categories")
def api_categories():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT category FROM listings WHERE metro_area = ? ORDER BY category",
        (DEFAULT_METRO,),
    ).fetchall()
    db.close()
    return jsonify([r["category"] for r in rows])


@app.route("/api/brands")
def api_brands():
    category = request.args.get("category", "")
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT brand FROM listings "
        "WHERE category = ? AND metro_area = ? AND brand IS NOT NULL ORDER BY brand",
        (category, DEFAULT_METRO),
    ).fetchall()
    db.close()
    return jsonify([r["brand"] for r in rows])


@app.route("/api/models")
def api_models():
    category = request.args.get("category", "")
    brand = request.args.get("brand", "")
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT model FROM listings "
        "WHERE category = ? AND brand = ? AND metro_area = ? AND model IS NOT NULL ORDER BY model",
        (category, brand, DEFAULT_METRO),
    ).fetchall()
    db.close()
    return jsonify([r["model"] for r in rows])


@app.route("/api/estimate")
def api_estimate():
    category = request.args.get("category", "")
    brand = request.args.get("brand", "")
    model = request.args.get("model", "")
    condition = request.args.get("condition", "")

    db = get_db()

    # Build query with progressive relaxation
    params = [DEFAULT_METRO]
    clauses = ["metro_area = ?", "price_cents IS NOT NULL"]

    if category:
        clauses.append("category = ?")
        params.append(category)
    if brand:
        clauses.append("brand = ?")
        params.append(brand)
    if model:
        clauses.append("model = ?")
        params.append(model)

    where = " AND ".join(clauses)
    rows = db.execute(
        f"SELECT price_cents, condition, title, url, listing_date, platform "
        f"FROM listings WHERE {where} ORDER BY scraped_at DESC LIMIT 200",
        params,
    ).fetchall()

    if not rows:
        db.close()
        return jsonify({"error": "No matching listings found. Try broadening your search."}), 404

    prices = [r["price_cents"] for r in rows]

    # Apply condition adjustment factor
    condition_factors = {
        "new": 1.15,
        "like_new": 1.0,
        "good": 0.85,
        "fair": 0.70,
        "poor": 0.55,
    }
    factor = condition_factors.get(condition, 1.0)

    median = statistics.median(prices)
    estimated = round(median * factor)
    low = round(min(prices) * factor)
    high = round(max(prices) * factor)

    try:
        stdev = statistics.stdev(prices) if len(prices) > 1 else 0
    except statistics.StatisticsError:
        stdev = 0

    comparables = []
    for r in rows[:8]:
        comparables.append({
            "title": r["title"],
            "price": r["price_cents"],
            "condition": r["condition"],
            "url": r["url"],
            "listing_date": r["listing_date"],
            "platform": r["platform"],
        })

    db.close()

    return jsonify({
        "estimated_value": estimated,
        "price_range": {"low": low, "median": round(median * factor), "high": high},
        "sample_size": len(prices),
        "condition_applied": condition or "any",
        "condition_factor": factor,
        "comparables": comparables,
        "metro_area": DEFAULT_METRO,
    })


@app.route("/api/deal-check", methods=["POST"])
def api_deal_check():
    data = request.get_json(force=True)
    asking_price = data.get("asking_price_cents")
    category = data.get("category", "")
    brand = data.get("brand", "")
    model = data.get("model", "")
    condition = data.get("condition", "")

    if not asking_price:
        return jsonify({"error": "asking_price_cents is required"}), 400

    db = get_db()
    params = [DEFAULT_METRO]
    clauses = ["metro_area = ?", "price_cents IS NOT NULL"]
    if category:
        clauses.append("category = ?")
        params.append(category)
    if brand:
        clauses.append("brand = ?")
        params.append(brand)
    if model:
        clauses.append("model = ?")
        params.append(model)

    where = " AND ".join(clauses)
    rows = db.execute(
        f"SELECT price_cents FROM listings WHERE {where}", params
    ).fetchall()
    db.close()

    if not rows:
        return jsonify({"error": "Not enough data to evaluate this deal."}), 404

    prices = [r["price_cents"] for r in rows]
    condition_factors = {
        "new": 1.15, "like_new": 1.0, "good": 0.85, "fair": 0.70, "poor": 0.55,
    }
    factor = condition_factors.get(condition, 1.0)
    median = statistics.median(prices) * factor

    ratio = asking_price / median if median else 1.0

    if ratio <= 0.75:
        verdict = "great_deal"
        label = "Great Deal!"
        explanation = f"This is priced {round((1 - ratio) * 100)}% below the typical market price."
    elif ratio <= 0.95:
        verdict = "good_deal"
        label = "Good Deal"
        explanation = f"This is priced {round((1 - ratio) * 100)}% below the typical market price."
    elif ratio <= 1.10:
        verdict = "fair"
        label = "Fair Price"
        explanation = "This is right around the typical market price."
    else:
        verdict = "overpriced"
        label = "Overpriced"
        explanation = f"This is priced {round((ratio - 1) * 100)}% above the typical market price."

    return jsonify({
        "verdict": verdict,
        "label": label,
        "explanation": explanation,
        "asking_price": asking_price,
        "market_median": round(median),
        "ratio": round(ratio, 2),
        "sample_size": len(prices),
    })


@app.route("/api/alerts", methods=["POST"])
def api_alerts():
    data = request.get_json(force=True)
    email = data.get("email", "").strip()
    category = data.get("category", "")
    brand = data.get("brand", "")
    target_price = data.get("target_price_cents")

    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    # Store in a simple alerts table
    db = get_db()
    db.execute(
        """CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            target_price_cents INTEGER,
            metro_area TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            active INTEGER NOT NULL DEFAULT 1
        )"""
    )
    db.execute(
        "INSERT INTO price_alerts (email, category, brand, target_price_cents, metro_area) VALUES (?, ?, ?, ?, ?)",
        (email, category, brand, target_price, DEFAULT_METRO),
    )
    db.commit()
    db.close()

    return jsonify({"success": True, "message": "Price alert created! We'll email you when we find a match."})


# ---------- Landing page endpoints ----------

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    source = data.get("source", "landing")

    if not email or "@" not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    db = get_db()
    _ensure_landing_tables(db)
    try:
        db.execute(
            "INSERT INTO email_signups (email, source) VALUES (?, ?)",
            (email, source),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"success": True, "message": "You're already on the list!"})
    db.close()
    return jsonify({"success": True, "message": "You're on the list! We'll be in touch soon."})


@app.route("/api/analytics/event", methods=["POST"])
def api_analytics_event():
    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"ok": True})  # silently accept malformed beacons

    event = data.get("event", "unknown")
    properties = json.dumps({k: v for k, v in data.items() if k != "event"})

    db = get_db()
    _ensure_landing_tables(db)
    db.execute(
        "INSERT INTO analytics_events (event, properties) VALUES (?, ?)",
        (event, properties),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, host="0.0.0.0", port=port)
