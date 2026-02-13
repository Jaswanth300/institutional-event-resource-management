"""
Database initialization, schema creation, and seed data for the
Institutional Event Resource Management System.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "event_manager.db")


def get_db():
    """Return a new database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist and seed initial data."""
    conn = get_db()
    cursor = conn.cursor()

    # ── Users ───────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('coordinator','hod','dean','head','admin')),
            department TEXT DEFAULT ''
        )
    """)

    # ── Venues ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            capacity INTEGER NOT NULL,
            location TEXT DEFAULT ''
        )
    """)

    # ── Resources ───────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_quantity INTEGER NOT NULL,
            available_quantity INTEGER NOT NULL
        )
    """)

    # ── Events ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            expected_attendees INTEGER NOT NULL,
            venue_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_hod',
            current_approver_role TEXT DEFAULT 'hod',
            created_by INTEGER NOT NULL,
            rejection_reason TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (venue_id) REFERENCES venues(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # ── Event–Resource junction ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            quantity_requested INTEGER NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (resource_id) REFERENCES resources(id)
        )
    """)

    # ── Approvals log ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            approver_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('approved','rejected')),
            comment TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (approver_id) REFERENCES users(id)
        )
    """)

    # ── Notifications ───────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # ── Seed data (only if tables are empty) ────────────────
    if cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        default_pw = generate_password_hash("password123")
        users = [
            ("coordinator", default_pw, "Alice Coordinator", "coordinator", "Computer Science"),
            ("hod",         default_pw, "Bob HOD",           "hod",         "Computer Science"),
            ("dean",        default_pw, "Carol Dean",        "dean",        "Engineering"),
            ("head",        default_pw, "David Head",        "head",        "Institution"),
            ("admin",       default_pw, "Eve Admin",         "admin",       "ITC"),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password_hash, full_name, role, department) VALUES (?,?,?,?,?)",
            users,
        )

    if cursor.execute("SELECT COUNT(*) FROM venues").fetchone()[0] == 0:
        venues = [
            ("Main Auditorium", 500, "Block A, Ground Floor"),
            ("Seminar Hall 1",  100, "Block B, First Floor"),
            ("Conference Room",  30, "Block C, Second Floor"),
        ]
        cursor.executemany(
            "INSERT INTO venues (name, capacity, location) VALUES (?,?,?)", venues
        )

    if cursor.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
        resources = [
            ("Projector",       5,  5),
            ("Microphone",     10, 10),
            ("Laptop",          8,  8),
            ("Whiteboard",     15, 15),
        ]
        cursor.executemany(
            "INSERT INTO resources (name, total_quantity, available_quantity) VALUES (?,?,?)",
            resources,
        )

    conn.commit()
    conn.close()
    print("✔  Database initialized successfully.")


if __name__ == "__main__":
    init_db()
