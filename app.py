"""
Institutional Event Resource Management System
Main Flask application – routes, authentication, business logic.
"""

from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = "event-mgr-secret-key-change-in-production"

# ────────────────────────── Helpers ──────────────────────────

APPROVAL_FLOW = {
    "pending_hod":  {"role": "hod",  "next": "pending_dean"},
    "pending_dean": {"role": "dean", "next": "pending_head"},
    "pending_head": {"role": "head", "next": "approved"},
}

ROLE_LABELS = {
    "coordinator": "Event Coordinator",
    "hod": "Head of Department",
    "dean": "Dean",
    "head": "Institutional Head",
    "admin": "Admin / ITC",
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.user is None or g.user["role"] not in roles:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated
    return decorator


@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        db.close()


@app.context_processor
def inject_globals():
    return dict(current_user=g.user, role_labels=ROLE_LABELS)


# ────────────────────────── Auth ─────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ────────────────────────── Dashboard ────────────────────────

@app.route("/")
@login_required
def dashboard():
    db = get_db()
    role = g.user["role"]
    events = []

    if role == "coordinator":
        events = db.execute(
            "SELECT e.*, v.name AS venue_name FROM events e "
            "JOIN venues v ON e.venue_id = v.id "
            "WHERE e.created_by = ? ORDER BY e.created_at DESC",
            (g.user["id"],),
        ).fetchall()

    elif role in ("hod", "dean", "head"):
        status_key = f"pending_{role}"
        events = db.execute(
            "SELECT e.*, v.name AS venue_name, u.full_name AS creator_name FROM events e "
            "JOIN venues v ON e.venue_id = v.id "
            "JOIN users u ON e.created_by = u.id "
            "WHERE e.status = ? ORDER BY e.created_at DESC",
            (status_key,),
        ).fetchall()

    elif role == "admin":
        events = db.execute(
            "SELECT e.*, v.name AS venue_name, u.full_name AS creator_name FROM events e "
            "JOIN venues v ON e.venue_id = v.id "
            "JOIN users u ON e.created_by = u.id "
            "ORDER BY e.created_at DESC"
        ).fetchall()

    # Stats
    stats = {
        "total": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "approved": db.execute("SELECT COUNT(*) FROM events WHERE status='approved'").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM events WHERE status LIKE 'pending_%'").fetchone()[0],
        "rejected": db.execute("SELECT COUNT(*) FROM events WHERE status='rejected'").fetchone()[0],
        "completed": db.execute("SELECT COUNT(*) FROM events WHERE status='completed'").fetchone()[0],
    }

    # Notifications
    notifications = db.execute(
        "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT 10",
        (g.user["id"],),
    ).fetchall()

    db.close()
    return render_template("dashboard.html", events=events, stats=stats, notifications=notifications)


# ────────────────────────── Event CRUD ───────────────────────

@app.route("/events/new", methods=["GET", "POST"])
@login_required
@role_required("coordinator")
def new_event():
    db = get_db()
    venues = db.execute("SELECT * FROM venues ORDER BY name").fetchall()
    resources = db.execute("SELECT * FROM resources ORDER BY name").fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_date = request.form.get("event_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        expected_attendees = int(request.form.get("expected_attendees", 0))
        venue_id = int(request.form.get("venue_id", 0))

        # Validate basics
        if not all([title, event_date, start_time, end_time, venue_id]):
            flash("Please fill in all required fields.", "error")
            db.close()
            return render_template("new_event.html", venues=venues, resources=resources)

        # Venue capacity check
        venue = db.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if not venue:
            flash("Selected venue does not exist.", "error")
            db.close()
            return render_template("new_event.html", venues=venues, resources=resources)

        if expected_attendees > venue["capacity"]:
            flash(
                f"Venue '{venue['name']}' has a capacity of {venue['capacity']} "
                f"but you requested {expected_attendees} attendees. "
                f"Please choose a larger venue or reduce attendees.",
                "error",
            )
            db.close()
            return render_template("new_event.html", venues=venues, resources=resources)

        # Venue time-slot conflict check
        conflict = db.execute(
            "SELECT * FROM events WHERE venue_id = ? AND event_date = ? "
            "AND status NOT IN ('rejected', 'completed') "
            "AND NOT (end_time <= ? OR start_time >= ?)",
            (venue_id, event_date, start_time, end_time),
        ).fetchone()
        if conflict:
            flash(
                f"Venue '{venue['name']}' is already booked on {event_date} "
                f"from {conflict['start_time']} to {conflict['end_time']} "
                f"for event '{conflict['title']}'. Please choose a different time slot or venue.",
                "error",
            )
            db.close()
            return render_template("new_event.html", venues=venues, resources=resources)

        # Resource validation
        resource_requests = []
        for res in resources:
            qty = int(request.form.get(f"resource_{res['id']}", 0))
            if qty > 0:
                if qty > res["available_quantity"]:
                    flash(
                        f"Resource '{res['name']}' has only {res['available_quantity']} "
                        f"units available but you requested {qty}.",
                        "error",
                    )
                    db.close()
                    return render_template("new_event.html", venues=venues, resources=resources)
                resource_requests.append((res["id"], qty))

        # All checks passed – create event
        cursor = db.execute(
            "INSERT INTO events (title, description, event_date, start_time, end_time, "
            "expected_attendees, venue_id, status, current_approver_role, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_hod', 'hod', ?)",
            (title, description, event_date, start_time, end_time,
             expected_attendees, venue_id, g.user["id"]),
        )
        event_id = cursor.lastrowid

        # Reserve resources (deduct available qty)
        for res_id, qty in resource_requests:
            db.execute(
                "INSERT INTO event_resources (event_id, resource_id, quantity_requested) VALUES (?, ?, ?)",
                (event_id, res_id, qty),
            )
            db.execute(
                "UPDATE resources SET available_quantity = available_quantity - ? WHERE id = ?",
                (qty, res_id),
            )

        # Notify HOD
        hod = db.execute("SELECT id FROM users WHERE role = 'hod' LIMIT 1").fetchone()
        if hod:
            db.execute(
                "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
                (hod["id"], f"New event '{title}' requires your approval."),
            )

        db.commit()
        db.close()
        flash("Event request submitted successfully! Awaiting HOD approval.", "success")
        return redirect(url_for("dashboard"))

    db.close()
    return render_template("new_event.html", venues=venues, resources=resources)


@app.route("/events/<int:event_id>")
@login_required
def event_detail(event_id):
    db = get_db()
    event = db.execute(
        "SELECT e.*, v.name AS venue_name, v.capacity AS venue_capacity, "
        "v.location AS venue_location, u.full_name AS creator_name, u.department "
        "FROM events e "
        "JOIN venues v ON e.venue_id = v.id "
        "JOIN users u ON e.created_by = u.id "
        "WHERE e.id = ?",
        (event_id,),
    ).fetchone()
    if not event:
        db.close()
        abort(404)

    resources = db.execute(
        "SELECT er.quantity_requested, r.name AS resource_name "
        "FROM event_resources er JOIN resources r ON er.resource_id = r.id "
        "WHERE er.event_id = ?",
        (event_id,),
    ).fetchall()

    approval_log = db.execute(
        "SELECT a.*, u.full_name AS approver_name FROM approvals a "
        "JOIN users u ON a.approver_id = u.id "
        "WHERE a.event_id = ? ORDER BY a.created_at",
        (event_id,),
    ).fetchall()

    db.close()

    can_approve = False
    if g.user["role"] in ("hod", "dean", "head"):
        expected_status = f"pending_{g.user['role']}"
        if event["status"] == expected_status:
            can_approve = True

    can_complete = (
        g.user["role"] == "coordinator"
        and event["created_by"] == g.user["id"]
        and event["status"] == "approved"
    )

    return render_template(
        "event_detail.html",
        event=event,
        resources=resources,
        approval_log=approval_log,
        can_approve=can_approve,
        can_complete=can_complete,
    )


@app.route("/events/<int:event_id>/approve", methods=["POST"])
@login_required
@role_required("hod", "dean", "head")
def approve_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        db.close()
        abort(404)

    expected_status = f"pending_{g.user['role']}"
    if event["status"] != expected_status:
        flash("You are not the current approver for this event.", "error")
        db.close()
        return redirect(url_for("event_detail", event_id=event_id))

    comment = request.form.get("comment", "").strip()
    flow = APPROVAL_FLOW[event["status"]]
    next_status = flow["next"]
    next_role = APPROVAL_FLOW.get(next_status, {}).get("role", "")

    # Log approval
    db.execute(
        "INSERT INTO approvals (event_id, approver_id, role, action, comment) VALUES (?, ?, ?, 'approved', ?)",
        (event_id, g.user["id"], g.user["role"], comment),
    )

    # Advance status
    db.execute(
        "UPDATE events SET status = ?, current_approver_role = ? WHERE id = ?",
        (next_status, next_role, event_id),
    )

    # Notify next approver or coordinator
    if next_status == "approved":
        # Notify coordinator – fully approved
        db.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
            (event["created_by"], f"Your event '{event['title']}' has been fully approved!"),
        )
    else:
        next_user = db.execute("SELECT id FROM users WHERE role = ? LIMIT 1", (next_role,)).fetchone()
        if next_user:
            db.execute(
                "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
                (next_user["id"], f"Event '{event['title']}' requires your approval."),
            )

    db.commit()
    db.close()
    flash(f"Event approved! Status advanced to '{next_status.replace('_', ' ').title()}'.", "success")
    return redirect(url_for("dashboard"))


@app.route("/events/<int:event_id>/reject", methods=["POST"])
@login_required
@role_required("hod", "dean", "head")
def reject_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        db.close()
        abort(404)

    expected_status = f"pending_{g.user['role']}"
    if event["status"] != expected_status:
        flash("You are not the current approver for this event.", "error")
        db.close()
        return redirect(url_for("event_detail", event_id=event_id))

    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("Please provide a reason for rejection.", "error")
        db.close()
        return redirect(url_for("event_detail", event_id=event_id))

    # Log rejection
    db.execute(
        "INSERT INTO approvals (event_id, approver_id, role, action, comment) VALUES (?, ?, ?, 'rejected', ?)",
        (event_id, g.user["id"], g.user["role"], reason),
    )

    # Update event status
    db.execute(
        "UPDATE events SET status = 'rejected', rejection_reason = ?, current_approver_role = '' WHERE id = ?",
        (reason, event_id),
    )

    # Release reserved resources
    reserved = db.execute(
        "SELECT resource_id, quantity_requested FROM event_resources WHERE event_id = ?",
        (event_id,),
    ).fetchall()
    for r in reserved:
        db.execute(
            "UPDATE resources SET available_quantity = available_quantity + ? WHERE id = ?",
            (r["quantity_requested"], r["resource_id"]),
        )

    # Notify coordinator
    db.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (event["created_by"],
         f"Your event '{event['title']}' was rejected by {ROLE_LABELS[g.user['role']]}. Reason: {reason}"),
    )

    db.commit()
    db.close()
    flash("Event has been rejected.", "info")
    return redirect(url_for("dashboard"))


@app.route("/events/<int:event_id>/complete", methods=["POST"])
@login_required
@role_required("coordinator")
def complete_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        db.close()
        abort(404)

    if event["status"] != "approved" or event["created_by"] != g.user["id"]:
        flash("You cannot complete this event.", "error")
        db.close()
        return redirect(url_for("event_detail", event_id=event_id))

    # Mark completed
    db.execute("UPDATE events SET status = 'completed', current_approver_role = '' WHERE id = ?", (event_id,))

    # Release resources
    reserved = db.execute(
        "SELECT resource_id, quantity_requested FROM event_resources WHERE event_id = ?",
        (event_id,),
    ).fetchall()
    for r in reserved:
        db.execute(
            "UPDATE resources SET available_quantity = available_quantity + ? WHERE id = ?",
            (r["quantity_requested"], r["resource_id"]),
        )

    db.commit()
    db.close()
    flash("Event marked as completed. All resources have been released.", "success")
    return redirect(url_for("dashboard"))


# ────────────────────── Notifications ────────────────────────

@app.route("/notifications/read/<int:notif_id>", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, g.user["id"]))
    db.commit()
    db.close()
    return redirect(url_for("dashboard"))


# ────────────────────── Admin pages ──────────────────────────

@app.route("/admin/venues", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_venues():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        capacity = int(request.form.get("capacity", 0))
        location = request.form.get("location", "").strip()
        if name and capacity > 0:
            try:
                db.execute("INSERT INTO venues (name, capacity, location) VALUES (?, ?, ?)",
                           (name, capacity, location))
                db.commit()
                flash(f"Venue '{name}' added successfully.", "success")
            except Exception:
                flash("A venue with that name already exists.", "error")
        else:
            flash("Name and capacity are required.", "error")

    venues = db.execute("SELECT * FROM venues ORDER BY name").fetchall()
    db.close()
    return render_template("manage_venues.html", venues=venues)


@app.route("/admin/resources", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_resources():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        total_qty = int(request.form.get("total_quantity", 0))
        if name and total_qty > 0:
            try:
                db.execute(
                    "INSERT INTO resources (name, total_quantity, available_quantity) VALUES (?, ?, ?)",
                    (name, total_qty, total_qty),
                )
                db.commit()
                flash(f"Resource '{name}' added successfully.", "success")
            except Exception:
                flash("A resource with that name already exists.", "error")
        else:
            flash("Name and quantity are required.", "error")

    resources = db.execute("SELECT * FROM resources ORDER BY name").fetchall()
    db.close()
    return render_template("manage_resources.html", resources=resources)


@app.route("/admin/events")
@login_required
@role_required("admin")
def admin_all_events():
    db = get_db()
    events = db.execute(
        "SELECT e.*, v.name AS venue_name, u.full_name AS creator_name FROM events e "
        "JOIN venues v ON e.venue_id = v.id "
        "JOIN users u ON e.created_by = u.id "
        "ORDER BY e.created_at DESC"
    ).fetchall()
    db.close()
    return render_template("all_events.html", events=events)


# ────────────────────────── Main ─────────────────────────────

import os

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

