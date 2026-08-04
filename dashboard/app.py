import os
import json
import time
from flask import Flask, render_template, request, jsonify, session, redirect
from functools import wraps
import firebase_admin
from firebase_admin import firestore
import requests
from dotenv import load_dotenv

# Load .env file from the parent directory
load_dotenv(dotenv_path="../.env")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "super_secret_kitapduy_key")
DASHBOARD_PIN = os.environ.get("DASHBOARD_PIN", "1216")

# Firebase Initialization
try:
    if not firebase_admin._apps:
        cred = firebase_admin.credentials.Certificate("../serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Firebase Init Error: {e}")
    db = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in') is not True:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    if not session.get('logged_in'):
        return render_template("login.html")
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    pin = data.get("pin")
    if pin == DASHBOARD_PIN:
        session['logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Geçersiz PIN"}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/status")
@login_required
def get_status():
    if not db:
        return jsonify({"error": "Firebase bağlanamadı"}), 500
        
    try:
        # Get live status
        status_ref = db.collection("active_jobs").document("github_worker").get()
        if status_ref.exists:
            status_data = status_ref.to_dict()
            
            # Check if it's dead (no updates for 10 minutes)
            last_update = status_data.get("last_update", 0)
            is_active = (time.time() - last_update) < 600
            status_data["is_active"] = is_active
            
            return jsonify(status_data)
        else:
            return jsonify({"status": "idle", "book_title": "-", "progress_pct": 0, "is_active": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trigger", methods=["POST"])
@login_required
def trigger_workflow():
    data = request.get_json()
    book_id = data.get("book_id", "auto")
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return jsonify({"success": False, "error": "GITHUB_TOKEN bulunamadı!"})
        
    repo = "semtinazizi2/KitapDuy_Bulut"
    url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
    headers = {
        "Accept": "application/vnd.github+json", 
        "Authorization": f"Bearer {token}", 
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {"ref": "main", "inputs": {"book_id": str(book_id)}}
    
    try:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code == 204:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": r.text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
