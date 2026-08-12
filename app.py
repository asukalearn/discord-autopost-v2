import json
import os
import secrets
from collections import deque
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import users as userstore
from bot_runner import BotRunner

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DEFAULT_CONFIG = {
    "tokens": [],
    "message": "",
    "channels": [],
    "notify_webhook_url": "",
    "embed_title": "📢 Laporan Pengiriman",
    "embed_description": "Channel: {channel}\nStatus: {status}",
    "embed_color": "#5EEAD4",
    "embed_footer": "Autopost Bot",
    "embed_thumbnail_url": "",
    "is_bot_token": False,
}

runners = {}
logs_by_user = {}

def get_logs(username):
    if username not in logs_by_user:
        logs_by_user[username] = deque(maxlen=200)
    return logs_by_user[username]

def get_runner(username):
    if username not in runners:
        runners[username] = BotRunner(lambda msg, u=username: get_logs(u).append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        ))
    return runners[username]

def load_config(username):
    path = userstore.config_path_for(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)

def save_config(username, cfg):
    with open(userstore.config_path_for(username), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if password != confirm:
            error = "Konfirmasi password tidak cocok."
        else:
            ok, msg = userstore.create_user(username, password)
            if ok:
                session["username"] = username
                return redirect(url_for("index"))
            error = msg
    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if userstore.verify_user(username, password):
            session["username"] = username
            return redirect(url_for("index"))
        error = "Username atau password salah."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    username = session["username"]
    cfg = load_config(username)
    safe_cfg = dict(cfg)
    safe_cfg["tokens"] = ["*" * 8 if t else "" for t in cfg.get("tokens", [])]
    return render_template("index.html", config=safe_cfg, username=username)

@app.route("/api/config", methods=["POST"])
@login_required
def api_config():
    username = session["username"]
    data = request.get_json(force=True)

    raw_tokens = data.get("tokens", "").strip()
    tokens = [t.strip() for t in raw_tokens.splitlines() if t.strip()]

    raw_channels = data.get("channels", "").strip()
    channels = []
    for line in raw_channels.splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) == 2:
            try:
                ch_id = int(parts[0].strip())
                delay = int(parts[1].strip())
                if delay <= 0:
                    return jsonify({"ok": False, "message": "Delay harus > 0"}), 400
                channels.append([ch_id, delay])
            except ValueError:
                return jsonify({"ok": False, "message": f"Format salah: {line}"}), 400
        else:
            return jsonify({"ok": False, "message": f"Baris tidak valid: {line}"}), 400

    message = data.get("message", "").strip()
    webhook_url = data.get("notify_webhook_url", "").strip()
    embed_title = data.get("embed_title", "").strip() or DEFAULT_CONFIG["embed_title"]
    embed_description = data.get("embed_description", "").strip() or DEFAULT_CONFIG["embed_description"]
    embed_color = data.get("embed_color", "").strip() or DEFAULT_CONFIG["embed_color"]
    embed_footer = data.get("embed_footer", "").strip()
    embed_thumbnail = data.get("embed_thumbnail_url", "").strip()
    is_bot_token = data.get("is_bot_token", False)

    cfg = {
        "tokens": tokens,
        "message": message,
        "channels": channels,
        "notify_webhook_url": webhook_url,
        "embed_title": embed_title,
        "embed_description": embed_description,
        "embed_color": embed_color,
        "embed_footer": embed_footer,
        "embed_thumbnail_url": embed_thumbnail,
        "is_bot_token": is_bot_token,
    }
    save_config(username, cfg)
    get_logs(username).append(f"[{datetime.now().strftime('%H:%M:%S')}] Konfigurasi disimpan.")
    return jsonify({"ok": True, "message": "Konfigurasi tersimpan."})

@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    username = session["username"]
    cfg = load_config(username)
    if not cfg.get("tokens"):
        return jsonify({"ok": False, "message": "Token bot belum diisi."}), 400
    if not cfg.get("message"):
        return jsonify({"ok": False, "message": "Pesan belum diisi."}), 400
    if not cfg.get("channels"):
        return jsonify({"ok": False, "message": "Channel tujuan belum diisi."}), 400

    embed_config = {
        "title": cfg.get("embed_title", ""),
        "description": cfg.get("embed_description", ""),
        "color": cfg.get("embed_color", ""),
        "footer": cfg.get("embed_footer", ""),
        "thumbnail_url": cfg.get("embed_thumbnail_url", ""),
    }
    ok, msg = get_runner(username).start(
        tokens=cfg["tokens"],
        message=cfg["message"],
        channels=cfg["channels"],
        webhook_url=cfg.get("notify_webhook_url", ""),
        embed_config=embed_config,
        is_bot_token=cfg.get("is_bot_token", False),
    )
    get_logs(username).append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    username = session["username"]
    ok, msg = get_runner(username).stop()
    get_logs(username).append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/status")
@login_required
def api_status():
    username = session["username"]
    return jsonify({"running": get_runner(username).running, "logs": list(get_logs(username))})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)