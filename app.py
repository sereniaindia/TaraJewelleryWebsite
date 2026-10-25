from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "tara_jewellery_secret_2026"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov"}
DB_PATH = "database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                company_name TEXT DEFAULT 'Tara Jewellery',
                hero_title TEXT DEFAULT 'Shine Everyday with Tara',
                hero_subtitle TEXT DEFAULT 'Trendy imitation jewellery for every mood, every outfit, every day.',
                logo TEXT DEFAULT '',
                admin_pass TEXT DEFAULT '',
                whatsapp TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hero_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                media_type TEXT DEFAULT 'image',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        # Insert default settings if empty
        row = conn.execute("SELECT id FROM settings WHERE id=1").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO settings (id, admin_pass) VALUES (1, ?)",
                (generate_password_hash("admin123"),)
            )

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_settings():
    with get_db() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        return dict(row) if row else {}

def get_hero_media():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM hero_media WHERE is_active=1 ORDER BY sort_order, id"
        ).fetchall()
        return [dict(r) for r in rows]

def check_admin(password):
    s = get_settings()
    stored = s.get("admin_pass") or ""
    if not stored:
        return password == "admin123"
    try:
        return check_password_hash(stored, password)
    except Exception:
        return password == "admin123"

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template(
        "index.html",
        settings=get_settings(),
        hero_media=get_hero_media()
    )

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        action = request.form.get("action")

        # Login
        if action == "login":
            if check_admin(request.form.get("password", "")):
                session["admin"] = True
                flash("Logged in successfully", "success")
            else:
                flash("Wrong password", "error")
            return redirect(url_for("admin"))

        # Logout
        if action == "logout":
            session.pop("admin", None)
            return redirect(url_for("admin"))

        # Require login for other actions
        if not session.get("admin"):
            flash("Please login first", "error")
            return redirect(url_for("admin"))

        # Update hero text
        if action == "update_text":
            with get_db() as conn:
                conn.execute(
                    "UPDATE settings SET hero_title=?, hero_subtitle=? WHERE id=1",
                    (request.form.get("hero_title", ""), request.form.get("hero_subtitle", ""))
                )
            flash("Hero text updated", "success")
            return redirect(url_for("admin"))

        # Upload media
        if action == "upload":
            file = request.files.get("media")
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Avoid overwrite
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
                    filename = f"{base}_{counter}{ext}"
                    counter += 1
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                media_type = "video" if ext.lower() in (".mp4", ".webm", ".mov") else "image"
                with get_db() as conn:
                    max_order = conn.execute("SELECT COALESCE(MAX(sort_order),0) FROM hero_media").fetchone()[0]
                    conn.execute(
                        "INSERT INTO hero_media (filename, media_type, sort_order) VALUES (?,?,?)",
                        (filename, media_type, max_order + 1)
                    )
                flash("Media uploaded", "success")
            else:
                flash("Invalid file type", "error")
            return redirect(url_for("admin"))

        # Delete media
        if action == "delete":
            media_id = request.form.get("id")
            with get_db() as conn:
                row = conn.execute("SELECT filename FROM hero_media WHERE id=?", (media_id,)).fetchone()
                if row:
                    path = os.path.join(UPLOAD_FOLDER, row["filename"])
                    if os.path.exists(path):
                        os.remove(path)
                    conn.execute("DELETE FROM hero_media WHERE id=?", (media_id,))
            flash("Media deleted", "success")
            return redirect(url_for("admin"))

        # Toggle active
        if action == "toggle":
            media_id = request.form.get("id")
            with get_db() as conn:
                conn.execute(
                    "UPDATE hero_media SET is_active = 1 - is_active WHERE id=?",
                    (media_id,)
                )
            flash("Status updated", "success")
            return redirect(url_for("admin"))

        # Change password
        if action == "change_pass":
            new_pass = request.form.get("new_password", "").strip()
            if len(new_pass) >= 4:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE settings SET admin_pass=? WHERE id=1",
                        (generate_password_hash(new_pass),)
                    )
                flash("Password changed", "success")
            else:
                flash("Password too short (min 4 chars)", "error")
            return redirect(url_for("admin"))

    # GET
    media_list = []
    if session.get("admin"):
        with get_db() as conn:
            media_list = [dict(r) for r in conn.execute(
                "SELECT * FROM hero_media ORDER BY sort_order, id"
            ).fetchall()]

    return render_template(
        "admin.html",
        settings=get_settings(),
        media_list=media_list,
        logged_in=session.get("admin", False)
    )

@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
