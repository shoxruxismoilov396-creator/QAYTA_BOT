import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "qayta.db")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY muhit o'zgaruvchisini sozlang.")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD muhit o'zgaruvchisini sozlang.")

STATUSES = ["Yangi", "Qabul qilindi", "Jarayonda", "Yakunlandi", "Bekor qilindi"]

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Login yoki parol noto'g'ri.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if search:
        like = f"%{search}%"
        query += """ AND (CAST(id AS TEXT) LIKE ? OR username LIKE ?
                    OR item_type LIKE ? OR phone LIKE ? OR address LIKE ?)"""
        params.extend([like, like, like, like, like])
    if status in STATUSES:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT 300"

    with get_db() as conn:
        orders = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        new_count = conn.execute("SELECT COUNT(*) FROM orders WHERE status='Yangi'").fetchone()[0]
        progress_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status IN ('Qabul qilindi','Jarayonda')"
        ).fetchone()[0]
        done_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status='Yakunlandi'"
        ).fetchone()[0]

    return render_template(
        "dashboard.html", orders=orders, statuses=STATUSES,
        selected_status=status, search=search, total=total,
        new_count=new_count, progress_count=progress_count, done_count=done_count
    )

@app.route("/order/<int:order_id>/status", methods=["POST"])
@login_required
def update_status(order_id):
    new_status = request.form.get("status", "")
    if new_status not in STATUSES:
        abort(400)
    with get_db() as conn:
        cur = conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        if cur.rowcount == 0:
            abort(404)
        conn.commit()
    flash(f"Buyurtma №{order_id} holati yangilandi.", "success")
    return redirect(url_for("dashboard", q=request.args.get("q", ""), status=request.args.get("filter", "")))

if __name__ == "__main__":
    # Production serverda waitress/gunicorn ishlating; Flask debug rejimini yoqmang.
    app.run(host="127.0.0.1", port=5000, debug=False)
