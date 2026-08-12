"""
Manajemen akun pengguna sederhana berbasis file JSON.
Tiap pengguna punya username unik, password (di-hash), dan folder
config bot sendiri — supaya masing-masing bisa pasang token bot
mereka sendiri tanpa saling ganggu.
"""

import json
import os
import re
from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")
CONFIGS_DIR = os.path.join(DATA_DIR, "configs")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def _ensure_dirs():
    os.makedirs(CONFIGS_DIR, exist_ok=True)


def _load_users() -> dict:
    _ensure_dirs()
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    _ensure_dirs()
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username or ""))


def user_exists(username: str) -> bool:
    return username in _load_users()


def create_user(username: str, password: str) -> tuple[bool, str]:
    if not is_valid_username(username):
        return False, "Username 3-20 karakter, hanya huruf/angka/underscore."
    if len(password) < 6:
        return False, "Password minimal 6 karakter."
    users = _load_users()
    if username in users:
        return False, "Username sudah dipakai."
    users[username] = {"password_hash": generate_password_hash(password)}
    _save_users(users)
    _ensure_dirs()
    return True, "Akun berhasil dibuat."


def verify_user(username: str, password: str) -> bool:
    users = _load_users()
    entry = users.get(username)
    if not entry:
        return False
    return check_password_hash(entry["password_hash"], password)


def config_path_for(username: str) -> str:
    _ensure_dirs()
    return os.path.join(CONFIGS_DIR, f"{username}.json")
