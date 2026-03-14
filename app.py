"""
Student Learning Hub - CS 361

Flask backend with in-memory task storage, plus integration with external
microservices over JSON/HTTP:

- User Registration (port 5001)
- Progress/Streak (port 5004)
- Statistics/Analytics (port 5005)
- User Preferences (port 5006)
"""

import uuid

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify

app = Flask(__name__)
app.secret_key = "cs361-student-hub-secret"

# In-memory task list: list of dicts with id, name, snippet, category
tasks = []

# Base URLs for external microservices
REGISTRATION_SERVICE_URL = "http://127.0.0.1:5001"
PROGRESS_SERVICE_URL = "http://127.0.0.1:5004"
STATS_SERVICE_URL = "http://127.0.0.1:5005"
PREFS_SERVICE_URL = "http://127.0.0.1:5006"


def get_task_by_id(task_id):
    """Return task dict or None."""
    for t in tasks:
        if t["id"] == task_id:
            return t
    return None


@app.context_processor
def inject_theme():
    """Make current theme available in all templates (for dark/light UI)."""
    theme = session.get("theme")
    if theme is None:
        # First visit this session: load from preferences microservice so saved theme applies
        try:
            username = session.get("username") or "default_user"
            resp = requests.get(f"{PREFS_SERVICE_URL}/preferences/{username}", timeout=2)
            if resp.ok:
                data = resp.json()
                if data.get("success"):
                    prefs = data.get("preferences") or {}
                    theme = prefs.get("theme", "light")
                    session["theme"] = theme
                    session["items_per_page"] = str(prefs.get("items_per_page", "25"))
        except requests.RequestException:
            pass
        if theme is None:
            theme = "light"
    return {"theme": theme}


@app.route("/")
def index():
    """Main menu."""
    # Optionally, fetch streak info for a default user for display.
    streak_info = None
    try:
        resp = requests.get(
            f"{PROGRESS_SERVICE_URL}/streak/default_user",
            params={"activity_type": "task_completion"},
            timeout=3,
        )
        data = resp.json()
        if data.get("success"):
            streak_info = data
    except requests.RequestException:
        streak_info = None
    return render_template("index.html", streak_info=streak_info)


@app.route("/register", methods=["GET", "POST"])
def register_page():
    """
    Registration page that submits through the User Registration microservice
    and displays feedback via flash messages.
    """
    if request.method == "GET":
        return render_template("register.html")
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    email = (request.form.get("email") or "").strip()
    try:
        resp = requests.post(
            f"{REGISTRATION_SERVICE_URL}/api/register",
            json={"username": username, "password": password, "email": email},
            timeout=5,
        )
        data = resp.json()
        if data.get("success"):
            flash(f"Account created for {data.get('username', username)}. You can sign in now.", "success")
            return redirect(url_for("login_page"))
        flash(data.get("error", "Registration failed."), "error")
        return render_template("register.html", username=username, email=email)
    except requests.RequestException:
        flash("User registration service is unavailable.", "error")
        return render_template("register.html", username=username, email=email)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """
    Sign-in page that authenticates via the User Registration microservice
    and displays feedback via flash messages.
    """
    if request.method == "GET":
        return render_template("login.html")
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    try:
        resp = requests.post(
            f"{REGISTRATION_SERVICE_URL}/api/login",
            json={"username": username, "password": password},
            timeout=5,
        )
        data = resp.json()
        if data.get("success"):
            session["user_id"] = data.get("user_id")
            session["username"] = data.get("username", username)
            flash(f"Signed in as {session['username']}.", "success")
            return redirect(url_for("index"))
        flash(data.get("error", "Invalid username or password."), "error")
        return render_template("login.html", username=username)
    except requests.RequestException:
        flash("User registration service is unavailable.", "error")
        return render_template("login.html", username=username)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear session and redirect to home."""
    session.pop("user_id", None)
    session.pop("username", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


def _current_username():
    """Username for preferences: logged-in user or default_user."""
    return session.get("username") or "default_user"


@app.route("/stats")
def stats_page():
    """
    Task statistics dashboard via the Statistics/Analytics microservice.
    Sends current in-memory tasks to the service and displays totals and category breakdown.
    """
    stats_data = None
    error = None
    try:
        resp = requests.post(
            f"{STATS_SERVICE_URL}/stats",
            json={
                "data": tasks,
                "group_by": "category",
                "numeric_fields": [],
            },
            timeout=3,
        )
        data = resp.json()
        if data.get("success"):
            stats_data = data.get("stats")
        else:
            error = data.get("error", "Failed to compute stats.")
    except requests.RequestException:
        error = "Statistics service is unavailable."

    return render_template("stats.html", stats=stats_data, error=error)


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """
    User settings via the User Preferences microservice.
    GET: show form with current preferences.
    POST: save theme and items_per_page.
    """
    username = _current_username()
    defaults = {"theme": "light", "items_per_page": "25"}

    if request.method == "GET":
        prefs = dict(defaults)
        try:
            resp = requests.get(
                f"{PREFS_SERVICE_URL}/preferences/{username}",
                timeout=3,
            )
            data = resp.json()
            if data.get("success"):
                saved = data.get("preferences") or {}
                prefs = {**defaults, **saved}
                session["theme"] = prefs.get("theme", "light")
                session["items_per_page"] = str(prefs.get("items_per_page", "25"))
        except requests.RequestException:
            pass
        return render_template("settings.html", preferences=prefs)

    # POST: update preferences
    theme = (request.form.get("theme") or "light").strip()
    items_per_page = (request.form.get("items_per_page") or "25").strip()
    try:
        resp = requests.put(
            f"{PREFS_SERVICE_URL}/preferences/{username}",
            json={"preferences": {"theme": theme, "items_per_page": items_per_page}},
            timeout=3,
        )
        data = resp.json()
        if data.get("success"):
            session["theme"] = theme
            session["items_per_page"] = items_per_page
            flash("Settings saved.", "success")
            return redirect(url_for("settings_page"))
        flash(data.get("error", "Failed to save settings."), "error")
    except requests.RequestException:
        flash("Preferences service is unavailable.", "error")
    return redirect(url_for("settings_page"))


@app.route("/tasks")
def task_list():
    """View task list with TIP (IH#1)."""
    return render_template("task_list.html", tasks=tasks)


@app.route("/add", methods=["GET", "POST"])
def add_task_step1():
    """
    Add Task - Step 1: Name and Snippet (IH#2 Cost/Sequence).
    """
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        snippet = (request.form.get("snippet") or "").strip()
        # Input validation: task name must not be empty (Reliability)
        if not name:
            flash("Task name is required and cannot be empty.", "error")
            return render_template("add_task_step1.html")
        session["add_name"] = name
        session["add_snippet"] = snippet
        return redirect(url_for("add_task_step2"))
    return render_template("add_task_step1.html")


@app.route("/add/step2", methods=["GET", "POST"])
def add_task_step2():
    """
    Add Task - Step 2: Category (IH#2 Cost/Sequence).
    """
    if request.method == "GET":
        if "add_name" not in session:
            flash("Please complete Step 1 first (name and snippet).", "error")
            return redirect(url_for("add_task_step1"))
    if request.method == "POST":
        if "add_name" not in session:
            flash("Session expired. Please start from Step 1.", "error")
            return redirect(url_for("add_task_step1"))
        category = (request.form.get("category") or "General").strip() or "General"
        task = {
            "id": str(uuid.uuid4()),
            "name": session["add_name"],
            "snippet": session["add_snippet"],
            "category": category,
        }
        tasks.append(task)
        # Log a task-completion activity to the Progress/Streak microservice
        # for a demo "default_user".
        try:
            requests.post(
                f"{PROGRESS_SERVICE_URL}/log",
                json={
                    "user_id": "default_user",
                    "activity_type": "task_completion",
                },
                timeout=3,
            )
        except requests.RequestException:
            # Do not block task creation if the streak service is offline.
            pass
        session.pop("add_name", None)
        session.pop("add_snippet", None)
        flash(f"Task \"{task['name']}\" added successfully.", "success")
        return redirect(url_for("task_list"))
    return render_template(
        "add_task_step2.html",
        name=session.get("add_name", ""),
        snippet=session.get("add_snippet", ""),
    )


@app.route("/delete/<task_id>", methods=["GET", "POST"])
def delete_task(task_id):
    """
    Delete task with confirmation (IH#8 Safety Net).
    GET: show confirmation "Are you sure you want to delete [Task Name]? (y/n)"
    POST: perform delete after user confirms.
    """
    task = get_task_by_id(task_id)
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for("task_list"))
    if request.method == "POST":
        confirm = (request.form.get("confirm") or "").strip().lower()
        if confirm in ("y", "yes"):
            tasks.remove(task)
            flash(f"Task \"{task['name']}\" has been deleted.", "success")
            return redirect(url_for("task_list"))
        # User chose no or invalid
        flash("Delete cancelled.", "info")
        return redirect(url_for("task_list"))
    return render_template("delete_confirm.html", task=task)


@app.post("/api/demo/register")
def demo_register():
    """
    Example integration: forward registration to the User Registration microservice.
    Body: { "username", "password", "email?" }
    """
    payload = request.get_json(silent=True) or request.form or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()
    try:
        resp = requests.post(
            f"{REGISTRATION_SERVICE_URL}/api/register",
            json={"username": username, "password": password, "email": email},
            timeout=5,
        )
        data = resp.json()
        if not request.is_json:
            if data.get("success"):
                flash(f"Registration successful for {data.get('username')} via microservice.", "success")
            else:
                flash(f"Registration failed: {data.get('error')}", "error")
            return redirect(url_for("index"))
        return jsonify(data), resp.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "User registration service is unavailable."}), 503


@app.post("/api/demo/login")
def demo_login():
    """
    Example integration: forward login to the User Registration microservice.
    Body: { "username", "password" }
    """
    payload = request.get_json(silent=True) or request.form or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    try:
        resp = requests.post(
            f"{REGISTRATION_SERVICE_URL}/api/login",
            json={"username": username, "password": password},
            timeout=5,
        )
        data = resp.json()
        if not request.is_json:
            if data.get("success"):
                flash(f"Signed in as {data.get('username')} via microservice.", "success")
            else:
                flash(f"Login failed: {data.get('error')}", "error")
            return redirect(url_for("index"))
        return jsonify(data), resp.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "User registration service is unavailable."}), 503


if __name__ == "__main__":
    # Run the main program on its own port so that
    # it can talk to the user registration and progress microservices.
    app.run(debug=True, port=5003)
