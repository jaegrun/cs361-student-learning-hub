"""
Student Learning Hub - CS 361 Milestone #1
Flask backend with in-memory task storage.
"""

import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "cs361-student-hub-secret"

# In-memory task list: list of dicts with id, name, snippet, category
tasks = []


def get_task_by_id(task_id):
    """Return task dict or None."""
    for t in tasks:
        if t["id"] == task_id:
            return t
    return None


@app.route("/")
def index():
    """Main menu."""
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
