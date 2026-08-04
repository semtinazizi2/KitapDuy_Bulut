import os
import json
import sqlite3
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from functools import wraps
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "super_secret_kitapduy_key")
DASHBOARD_PIN = os.environ.get("DASHBOARD_PIN", "1216")
TELEMETRY_TOKEN = os.environ.get("TELEMETRY_TOKEN", "super_secret_kitapduy_token") # Used by GitHub actions
DB_PATH = "dashboard.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Active Jobs Table
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id TEXT PRIMARY KEY, book_id TEXT, book_title TEXT, current_chunk INTEGER, total_chunks INTEGER, progress_pct REAL, voice TEXT, latest_audio_url TEXT, last_update REAL)''')
    
    # Queue Table
    c.execute('''CREATE TABLE IF NOT EXISTS queue
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT UNIQUE, added_at REAL, status TEXT)''')
                 
    # Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, message TEXT)''')
                 
    # API Health Table
    c.execute('''CREATE TABLE IF NOT EXISTS api_health
                 (key_index INTEGER PRIMARY KEY, status TEXT, error_count INTEGER, last_used REAL)''')
                 
    # Stats Table
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (key TEXT PRIMARY KEY, value INTEGER)''')
    
    conn.commit()
    conn.close()

init_db()

# --- AUTH DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token or token != f"Bearer {TELEMETRY_TOKEN}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin")
        if pin == DASHBOARD_PIN:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Hatalı Şifre!")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html")

# --- FRONTEND API (Read) ---
@app.route("/api/dashboard_data")
@login_required
def dashboard_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get active job
    c.execute("SELECT * FROM jobs WHERE id='github_worker'")
    job = c.fetchone()
    
    # Get logs (last 50)
    c.execute("SELECT id, timestamp, message FROM logs ORDER BY id DESC LIMIT 50")
    logs = [{"id": r["id"], "time": datetime.fromtimestamp(r["timestamp"]).strftime("%H:%M:%S"), "msg": r["message"]} for r in c.fetchall()]
    logs.reverse()
    
    # Get queue
    c.execute("SELECT book_id, status FROM queue ORDER BY id ASC")
    queue = [{"book_id": r["book_id"], "status": r["status"]} for r in c.fetchall()]
    
    # Get API Health
    c.execute("SELECT key_index, status, error_count FROM api_health ORDER BY key_index ASC")
    api_health = [{"index": r["key_index"], "status": r["status"], "errors": r["error_count"]} for r in c.fetchall()]
    
    # Get Stats
    c.execute("SELECT key, value FROM stats")
    stats = {r["key"]: r["value"] for r in c.fetchall()}
    
    conn.close()
    
    return jsonify({
        "job": dict(job) if job else None,
        "logs": logs,
        "queue": queue,
        "api_health": api_health,
        "stats": stats
    })

# --- QUEUE MANAGEMENT (Frontend) ---
@app.route("/api/queue/add", methods=["POST"])
@login_required
def add_queue():
    book_id = request.json.get("book_id")
    if not book_id:
        return jsonify({"error": "Missing book_id"}), 400
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO queue (book_id, added_at, status) VALUES (?, ?, ?)", (str(book_id).strip(), time.time(), "pending"))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already in queue
    finally:
        conn.close()
    return jsonify({"success": True})

@app.route("/api/trigger", methods=["POST"])
@login_required
def trigger_workflow():
    book_id = request.json.get("book_id", "auto")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return jsonify({"success": False, "error": "GITHUB_TOKEN ayarlanmamış."}), 500

    repo = "semtinazizi2/KitapDuy_Bulut"
    url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {
        "ref": "main",
        "inputs": {"book_id": str(book_id)}
    }

    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 204:
            return jsonify({"success": True, "message": "Robot Uyandırıldı!"})
        else:
            return jsonify({"success": False, "error": f"Hata {r.status_code}: {r.text}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- TELEMETRY API (Used by GitHub Actions) ---
@app.route("/api/telemetry/job", methods=["POST"])
@token_required
def update_job():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO jobs (id, book_id, book_title, current_chunk, total_chunks, progress_pct, voice, latest_audio_url, last_update)
                 VALUES ('github_worker', ?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(id) DO UPDATE SET
                 book_id=excluded.book_id, book_title=excluded.book_title, current_chunk=excluded.current_chunk, 
                 total_chunks=excluded.total_chunks, progress_pct=excluded.progress_pct, voice=excluded.voice,
                 latest_audio_url=COALESCE(excluded.latest_audio_url, jobs.latest_audio_url),
                 last_update=excluded.last_update''',
              (data.get("book_id"), data.get("book_title"), data.get("current_chunk"), data.get("total_chunks"), 
               data.get("progress_pct"), data.get("voice"), data.get("latest_audio_url"), time.time()))
               
    # Update global stats
    if data.get("current_chunk"):
        c.execute("INSERT INTO stats (key, value) VALUES ('total_chunks_processed', 1) ON CONFLICT(key) DO UPDATE SET value=value+1")
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/telemetry/log", methods=["POST"])
@token_required
def add_log():
    msg = request.json.get("message")
    if msg:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO logs (timestamp, message) VALUES (?, ?)", (time.time(), msg))
        # Keep only last 200 logs
        c.execute("DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 200)")
        conn.commit()
        conn.close()
    return jsonify({"success": True})

@app.route("/api/telemetry/api_health", methods=["POST"])
@token_required
def update_api_health():
    index = request.json.get("index")
    status = request.json.get("status") # "ok", "error", "429"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if status == "error" or status == "429":
        c.execute("INSERT INTO api_health (key_index, status, error_count, last_used) VALUES (?, ?, 1, ?) ON CONFLICT(key_index) DO UPDATE SET status=excluded.status, error_count=error_count+1, last_used=excluded.last_used", (index, status, time.time()))
    else:
        c.execute("INSERT INTO api_health (key_index, status, error_count, last_used) VALUES (?, ?, 0, ?) ON CONFLICT(key_index) DO UPDATE SET status=excluded.status, last_used=excluded.last_used", (index, status, time.time()))
        
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/telemetry/queue/pop", methods=["POST"])
@token_required
def pop_queue():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, book_id FROM queue WHERE status='pending' ORDER BY added_at ASC LIMIT 1")
    row = c.fetchone()
    if row:
        c.execute("UPDATE queue SET status='processing' WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        return jsonify({"book_id": row["book_id"]})
    conn.close()
    return jsonify({"book_id": None}) # Queue is empty

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
