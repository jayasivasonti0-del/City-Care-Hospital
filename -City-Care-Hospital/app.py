import os
import sqlite3
import datetime

from flask import (
    Flask,
    request,
    render_template_string,
    redirect,
    url_for,
    session,
    flash
)
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

# Use an environment variable for the secret key.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key-before-production"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "hospital.db")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# DATABASE INITIALIZATION AND MIGRATION
# --------------------------------------------------

def init_db():
    with get_db() as conn:

        # Create users table if it does not exist.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'Patient',
                specialization TEXT DEFAULT 'N/A'
            )
        """)

        # Create appointments table if it does not exist.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (doctor_id) REFERENCES users(id)
            )
        """)

        # IMPORTANT:
        # Migrate existing databases that were created
        # without the specialization column.

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "specialization" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN specialization TEXT DEFAULT 'N/A'
            """)

        if "role" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN role TEXT DEFAULT 'Patient'
            """)

        # Ensure existing NULL values have sensible defaults.
        conn.execute("""
            UPDATE users
            SET specialization = 'N/A'
            WHERE specialization IS NULL
        """)

        conn.execute("""
            UPDATE users
            SET role = 'Patient'
            WHERE role IS NULL
        """)

        # Default accounts.
        # These accounts are created only if their usernames
        # do not already exist.

        default_users = [
            (
                "Dev",
                "dev@123",
                "Admin",
                "System Administrator"
            ),
            (
                "dr_smith",
                "smith@123",
                "Doctor",
                "General Physician"
            ),
            (
                "dr_adams",
                "adams@123",
                "Doctor",
                "Cardiologist"
            ),
            (
                "ravi",
                "ravi@123",
                "Patient",
                "N/A"
            ),
            (
                "raju",
                "raju@123",
                "Patient",
                "N/A"
            ),
            (
                "ramu",
                "ramu@123",
                "Patient",
                "N/A"
            ),
            (
                "yash",
                "yash@123",
                "Patient",
                "N/A"
            )
        ]

        for username, password, role, specialization in default_users:

            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            ).fetchone()

            if existing is None:
                conn.execute("""
                    INSERT INTO users
                    (username, password, role, specialization)
                    VALUES (?, ?, ?, ?)
                """, (
                    username,
                    generate_password_hash(password),
                    role,
                    specialization
                ))

        conn.commit()


# Initialize the database.
init_db()


# --------------------------------------------------
# BASE HTML TEMPLATE
# --------------------------------------------------

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>City Care Hospital</title>

    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
        rel="stylesheet"
    >
</head>

<body class="bg-light">

<nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
    <div class="container">

        <a class="navbar-brand fw-bold" href="/">
            🏥 City Care Hospital
        </a>

        <div>
            {% if session.get('user_id') %}

                {% if session.get('role') == 'Admin' %}
                    <a href="/admin/users"
                       class="btn btn-outline-light btn-sm me-2">
                        Manage Users
                    </a>
                {% endif %}

                <a href="/appointments"
                   class="btn btn-outline-light btn-sm me-2">
                    Appointments
                </a>

                <span class="navbar-text text-white me-3">
                    Welcome, {{ session.get('username') }}
                    ({{ session.get('role') }})
                </span>

                <a href="/logout"
                   class="btn btn-outline-light btn-sm">
                    Logout
                </a>

            {% else %}

                <a href="/login"
                   class="btn btn-outline-light btn-sm">
                    Login
                </a>

                <a href="/register"
                   class="btn btn-light btn-sm ms-2">
                    Register
                </a>

            {% endif %}
        </div>

    </div>
</nav>

<div class="container">

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show"
                     role="alert">

                    {{ message }}

                    <button type="button"
                            class="btn-close"
                            data-bs-dismiss="alert"
                            aria-label="Close">
                    </button>

                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}

</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

</body>
</html>
"""


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

INDEX_HTML = BASE_HTML.replace(
    "{% block content %}{% endblock %}",
    """
    <div class="p-5 mb-4 bg-white rounded-3 shadow-sm text-center">

        <h1 class="display-5 fw-bold text-primary">
            Hospital Management System
        </h1>

        <p class="fs-4">
            Secure Patient, Doctor & Staff Portal
        </p>

        {% if not session.get('user_id') %}

            <a class="btn btn-primary btn-lg" href="/login">
                Login to Access Dashboard
            </a>

        {% else %}

            <div class="alert alert-success">
                You are logged in as
                <strong>{{ session.get('username') }}</strong>
                ({{ session.get('role') }}).
            </div>

            <a href="/appointments"
               class="btn btn-success btn-lg">
                Go to Appointments Dashboard
            </a>

        {% endif %}

    </div>
    """
)


# --------------------------------------------------
# LOGIN PAGE
# --------------------------------------------------

LOGIN_HTML = BASE_HTML.replace(
    "{% block content %}{% endblock %}",
    """
    <div class="row justify-content-center">
        <div class="col-md-5">

            <div class="card shadow-sm">

                <div class="card-header bg-primary text-white">
                    <h4>Login</h4>
                </div>

                <div class="card-body">

                    <form method="POST" action="/login">

                        <div class="mb-3">
                            <label class="form-label">Username</label>

                            <input type="text"
                                   name="username"
                                   class="form-control"
                                   autocomplete="username"
                                   required>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">Password</label>

                            <input type="password"
                                   name="password"
                                   class="form-control"
                                   autocomplete="current-password"
                                   required>
                        </div>

                        <button type="submit"
                                class="btn btn-primary w-100">
                            Login
                        </button>

                    </form>

                </div>
            </div>

        </div>
    </div>
    """
)


# --------------------------------------------------
# REGISTRATION PAGE
# --------------------------------------------------

REGISTER_HTML = BASE_HTML.replace(
    "{% block content %}{% endblock %}",
    """
    <div class="row justify-content-center">
        <div class="col-md-5">

            <div class="card shadow-sm">

                <div class="card-header bg-success text-white">
                    <h4>Register Patient Account</h4>
                </div>

                <div class="card-body">

                    <form method="POST" action="/register">

                        <div class="mb-3">
                            <label class="form-label">Username</label>

                            <input type="text"
                                   name="username"
                                   class="form-control"
                                   minlength="3"
                                   maxlength="50"
                                   autocomplete="username"
                                   required>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">Password</label>

                            <input type="password"
                                   name="password"
                                   class="form-control"
                                   minlength="8"
                                   autocomplete="new-password"
                                   required>
                        </div>

                        <button type="submit"
                                class="btn btn-success w-100">
                            Register
                        </button>

                    </form>

                </div>
            </div>

        </div>
    </div>
    """
)


# --------------------------------------------------
# APPOINTMENTS PAGE
# --------------------------------------------------

APPOINTMENTS_HTML = BASE_HTML.replace(
    "{% block content %}{% endblock %}",
    """
    <div class="row">

        {% if session.get('role') == 'Patient' %}

        <div class="col-md-4">

            <div class="card shadow-sm mb-4">

                <div class="card-header bg-primary text-white">
                    <h5>Book Doctor Appointment</h5>
                </div>

                <div class="card-body">

                    <form method="POST" action="/appointments">

                        <div class="mb-3">
                            <label class="form-label">
                                Select Doctor
                            </label>

                            <select name="doctor_id"
                                    class="form-select"
                                    required>

                                {% for doc in doctors %}
                                    <option value="{{ doc.id }}">
                                        Dr. {{ doc.username }}
                                        ({{ doc.specialization }})
                                    </option>
                                {% endfor %}

                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">
                                Appointment Date
                            </label>

                            <input type="date"
                                   name="appointment_date"
                                   class="form-control"
                                   min="{{ min_date }}"
                                   max="{{ max_date }}"
                                   required>

                            <div class="form-text">
                                Appointments can be booked for the next
                                30 days. Maximum 3 bookings per doctor per day.
                            </div>
                        </div>

                        <button type="submit"
                                class="btn btn-primary w-100">
                            Request Booking
                        </button>

                    </form>

                </div>
            </div>

        </div>

        <div class="col-md-8">

        {% else %}

        <div class="col-md-12">

        {% endif %}

            <div class="card shadow-sm">

                <div class="card-header bg-secondary text-white">
                    <h5>
                        {% if session.get('role') in ['Admin', 'Doctor'] %}
                            Appointments Management Panel
                        {% else %}
                            Your Scheduled Appointments
                        {% endif %}
                    </h5>
                </div>

                <div class="card-body table-responsive">

                    <table class="table table-hover align-middle">

                        <thead>
                            <tr>
                                <th>#</th>

                                {% if session.get('role') in ['Admin', 'Doctor'] %}
                                    <th>Patient</th>
                                {% endif %}

                                <th>Doctor</th>
                                <th>Date</th>
                                <th>Status</th>

                                {% if session.get('role') in ['Admin', 'Doctor'] %}
                                    <th>Action</th>
                                {% endif %}
                            </tr>
                        </thead>

                        <tbody>

                            {% for appt in appointments %}

                            <tr>
                                <td>{{ appt.id }}</td>

                                {% if session.get('role') in ['Admin', 'Doctor'] %}
                                    <td>{{ appt.patient_name }}</td>
                                {% endif %}

                                <td>
                                    Dr. {{ appt.doctor_name }}
                                    ({{ appt.specialization }})
                                </td>

                                <td>{{ appt.appointment_date }}</td>

                                <td>
                                    {% if appt.status == 'Approved' %}
                                        <span class="badge bg-success">
                                            Approved
                                        </span>
                                    {% elif appt.status == 'Rejected' %}
                                        <span class="badge bg-danger">
                                            Rejected
                                        </span>
                                    {% else %}
                                        <span class="badge bg-warning text-dark">
                                            Pending
                                        </span>
                                    {% endif %}
                                </td>

                                {% if session.get('role') in ['Admin', 'Doctor'] %}

                                <td>
                                    {% if appt.status == 'Pending' %}

                                        <form method="POST"
                                              action="/appointment/{{ appt.id }}/approve"
                                              class="d-inline">

                                            <button type="submit"
                                                    class="btn btn-sm btn-success">
                                                Approve
                                            </button>

                                        </form>

                                        <form method="POST"
                                              action="/appointment/{{ appt.id }}/reject"
                                              class="d-inline">

                                            <button type="submit"
                                                    class="btn btn-sm btn-danger">
                                                Reject
                                            </button>

                                        </form>

                                    {% else %}

                                        <span class="text-muted">
                                            Processed
                                        </span>

                                    {% endif %}
                                </td>

                                {% endif %}

                            </tr>

                            {% else %}

                            <tr>
                                <td colspan="6"
                                    class="text-center text-muted">
                                    No appointments found.
                                </td>
                            </tr>

                            {% endfor %}

                        </tbody>

                    </table>

                </div>
            </div>

        </div>
    </div>
    """
)


# --------------------------------------------------
# ADMIN USER MANAGEMENT PAGE
# --------------------------------------------------

ADMIN_USERS_HTML = BASE_HTML.replace(
    "{% block content %}{% endblock %}",
    """
    <div class="row">

        <div class="col-md-4">

            <div class="card shadow-sm mb-4">

                <div class="card-header bg-dark text-white">
                    <h5>Add New User / Doctor</h5>
                </div>

                <div class="card-body">

                    <form method="POST" action="/admin/users/add">

                        <div class="mb-3">
                            <label class="form-label">Username</label>

                            <input type="text"
                                   name="username"
                                   class="form-control"
                                   minlength="3"
                                   maxlength="50"
                                   required>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">Password</label>

                            <input type="password"
                                   name="password"
                                   class="form-control"
                                   minlength="8"
                                   required>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">Role</label>

                            <select name="role" class="form-select" required>
                                <option value="Patient">Patient</option>
                                <option value="Doctor">Doctor</option>
                                <option value="Admin">Admin</option>
                            </select>
                        </div>

                        <div class="mb-3">
                            <label class="form-label">
                                Specialization
                            </label>

                            <input type="text"
                                   name="specialization"
                                   class="form-control"
                                   value="General Physician">
                        </div>

                        <button type="submit"
                                class="btn btn-dark w-100">
                            Create User
                        </button>

                    </form>

                </div>
            </div>

        </div>

        <div class="col-md-8">

            <div class="card shadow-sm">

                <div class="card-header bg-secondary text-white">
                    <h5>System Users Management</h5>
                </div>

                <div class="card-body table-responsive">

                    <table class="table table-hover align-middle">

                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Username</th>
                                <th>Role & Specialization</th>
                                <th>Action</th>
                            </tr>
                        </thead>

                        <tbody>

                            {% for user in users %}

                            <tr>
                                <td>{{ user.id }}</td>
                                <td><strong>{{ user.username }}</strong></td>

                                <td>
                                    <form method="POST"
                                          action="/admin/users/update/{{ user.id }}">

                                        <select name="role"
                                                class="form-select form-select-sm mb-2"
                                                required>

                                            <option value="Patient"
                                                {% if user.role == 'Patient' %}selected{% endif %}>
                                                Patient
                                            </option>

                                            <option value="Doctor"
                                                {% if user.role == 'Doctor' %}selected{% endif %}>
                                                Doctor
                                            </option>

                                            <option value="Admin"
                                                {% if user.role == 'Admin' %}selected{% endif %}>
                                                Admin
                                            </option>

                                        </select>

                                        <input type="text"
                                               name="specialization"
                                               value="{{ user.specialization }}"
                                               class="form-control form-control-sm mb-2"
                                               placeholder="Specialization">

                                        <button type="submit"
                                                class="btn btn-sm btn-outline-primary">
                                            Save
                                        </button>

                                    </form>
                                </td>

                                <td>
                                    {% if user.id != session.get('user_id') %}

                                        <form method="POST"
                                              action="/admin/users/delete/{{ user.id }}"
                                              onsubmit="return confirm('Delete this user?')">

                                            <button type="submit"
                                                    class="btn btn-sm btn-outline-danger">
                                                Delete
                                            </button>

                                        </form>

                                    {% else %}

                                        <span class="text-muted small">
                                            Current user
                                        </span>

                                    {% endif %}
                                </td>
                            </tr>

                            {% endfor %}

                        </tbody>

                    </table>

                </div>
            </div>

        </div>

    </div>
    """
)


# --------------------------------------------------
# HOME ROUTE
# --------------------------------------------------

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


# --------------------------------------------------
# REGISTRATION ROUTE
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        raw_password = request.form.get("password", "")

        if len(username) < 3 or len(username) > 50:
            flash("Username must contain 3 to 50 characters.", "danger")
            return render_template_string(REGISTER_HTML)

        if len(raw_password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template_string(REGISTER_HTML)

        password = generate_password_hash(raw_password)

        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO users
                    (username, password, role, specialization)
                    VALUES (?, ?, 'Patient', 'N/A')
                """, (username, password))

                conn.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")

    return render_template_string(REGISTER_HTML)


# --------------------------------------------------
# LOGIN ROUTE
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute("""
                SELECT * FROM users WHERE username = ?
            """, (username,)).fetchone()

        if user and check_password_hash(user["password"], password):

            # Clear previous session data before login.
            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            flash("Logged in successfully!", "success")

            return redirect(url_for("index"))

        flash("Invalid username or password.", "danger")

    return render_template_string(LOGIN_HTML)


# --------------------------------------------------
# APPOINTMENTS ROUTE
# --------------------------------------------------

@app.route("/appointments", methods=["GET", "POST"])
def appointments():

    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    today = datetime.date.today()
    max_date = today + datetime.timedelta(days=30)

    today_str = today.isoformat()
    max_date_str = max_date.isoformat()

    if request.method == "POST":

        if session.get("role") != "Patient":
            flash("Only patients can book appointments.", "danger")
            return redirect(url_for("appointments"))

        doctor_id_raw = request.form.get("doctor_id", "")
        appointment_date = request.form.get("appointment_date", "")

        # Validate doctor ID.
        try:
            doctor_id = int(doctor_id_raw)
        except (ValueError, TypeError):
            flash("Invalid doctor selected.", "danger")
            return redirect(url_for("appointments"))

        # Validate the date format.
        try:
            parsed_date = datetime.date.fromisoformat(appointment_date)
        except (ValueError, TypeError):
            flash("Please select a valid appointment date.", "danger")
            return redirect(url_for("appointments"))

        # Restrict booking to today through the next 30 days.
        if parsed_date < today or parsed_date > max_date:
            flash(
                "Appointment date must be within the next 30 days.",
                "danger"
            )
            return redirect(url_for("appointments"))

        with get_db() as conn:

            # Ensure the selected user is actually a doctor.
            doctor = conn.execute("""
                SELECT id FROM users
                WHERE id = ? AND role = 'Doctor'
            """, (doctor_id,)).fetchone()

            if doctor is None:
                flash("Selected doctor does not exist.", "danger")
                return redirect(url_for("appointments"))

            # Count all non-rejected bookings for the doctor and date.
            existing_count = conn.execute("""
                SELECT COUNT(*) AS cnt
                FROM appointments
                WHERE doctor_id = ?
                  AND appointment_date = ?
                  AND status != 'Rejected'
            """, (doctor_id, appointment_date)).fetchone()["cnt"]

            if existing_count >= 3:

                flash(
                    "This doctor is fully booked on the selected date. "
                    "Maximum 3 appointments per day.",
                    "danger"
                )

            else:

                conn.execute("""
                    INSERT INTO appointments
                    (user_id, doctor_id, appointment_date, status)
                    VALUES (?, ?, ?, 'Pending')
                """, (
                    session["user_id"],
                    doctor_id,
                    appointment_date
                ))

                conn.commit()

                flash(
                    "Appointment requested successfully! "
                    "Status: Pending approval.",
                    "success"
                )

        return redirect(url_for("appointments"))

    # Retrieve doctors and appointments.
    with get_db() as conn:

        doctors = conn.execute("""
            SELECT id, username, specialization
            FROM users
            WHERE role = 'Doctor'
            ORDER BY username
        """).fetchall()

        if session.get("role") == "Admin":

            user_appointments = conn.execute("""
                SELECT
                    a.*,
                    p.username AS patient_name,
                    d.username AS doctor_name,
                    d.specialization
                FROM appointments a
                JOIN users p ON a.user_id = p.id
                JOIN users d ON a.doctor_id = d.id
                ORDER BY a.appointment_date DESC, a.id DESC
            """).fetchall()

        elif session.get("role") == "Doctor":

            user_appointments = conn.execute("""
                SELECT
                    a.*,
                    p.username AS patient_name,
                    d.username AS doctor_name,
                    d.specialization
                FROM appointments a
                JOIN users p ON a.user_id = p.id
                JOIN users d ON a.doctor_id = d.id
                WHERE a.doctor_id = ?
                ORDER BY a.appointment_date DESC, a.id DESC
            """, (session["user_id"],)).fetchall()

        else:

            user_appointments = conn.execute("""
                SELECT
                    a.*,
                    d.username AS doctor_name,
                    d.specialization
                FROM appointments a
                JOIN users d ON a.doctor_id = d.id
                WHERE a.user_id = ?
                ORDER BY a.appointment_date DESC, a.id DESC
            """, (session["user_id"],)).fetchall()

    return render_template_string(
        APPOINTMENTS_HTML,
        appointments=user_appointments,
        doctors=doctors,
        min_date=today_str,
        max_date=max_date_str
    )


# --------------------------------------------------
# APPOINTMENT APPROVAL ROUTE
# --------------------------------------------------

@app.route(
    "/appointment/<int:appt_id>/approve",
    methods=["POST"]
)
def approve_appointment(appt_id):

    if session.get("role") not in ["Admin", "Doctor"]:
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    with get_db() as conn:

        if session.get("role") == "Doctor":

            result = conn.execute("""
                UPDATE appointments
                SET status = 'Approved'
                WHERE id = ?
                  AND doctor_id = ?
                  AND status = 'Pending'
            """, (appt_id, session["user_id"]))

        else:

            result = conn.execute("""
                UPDATE appointments
                SET status = 'Approved'
                WHERE id = ?
                  AND status = 'Pending'
            """, (appt_id,))

        conn.commit()

        if result.rowcount == 0:
            flash(
                "Appointment not found, already processed, "
                "or not assigned to you.",
                "warning"
            )
        else:
            flash("Appointment approved successfully.", "success")

    return redirect(url_for("appointments"))


# --------------------------------------------------
# APPOINTMENT REJECTION ROUTE
# --------------------------------------------------

@app.route(
    "/appointment/<int:appt_id>/reject",
    methods=["POST"]
)
def reject_appointment(appt_id):

    if session.get("role") not in ["Admin", "Doctor"]:
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    with get_db() as conn:

        if session.get("role") == "Doctor":

            result = conn.execute("""
                UPDATE appointments
                SET status = 'Rejected'
                WHERE id = ?
                  AND doctor_id = ?
                  AND status = 'Pending'
            """, (appt_id, session["user_id"]))

        else:

            result = conn.execute("""
                UPDATE appointments
                SET status = 'Rejected'
                WHERE id = ?
                  AND status = 'Pending'
            """, (appt_id,))

        conn.commit()

        if result.rowcount == 0:
            flash(
                "Appointment not found, already processed, "
                "or not assigned to you.",
                "warning"
            )
        else:
            flash("Appointment rejected.", "info")

    return redirect(url_for("appointments"))


# --------------------------------------------------
# ADMIN USER MANAGEMENT
# --------------------------------------------------

@app.route("/admin/users")
def admin_users():

    if session.get("role") != "Admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    with get_db() as conn:
        users = conn.execute("""
            SELECT id, username, role, specialization
            FROM users
            ORDER BY id
        """).fetchall()

    return render_template_string(
        ADMIN_USERS_HTML,
        users=users
    )


# --------------------------------------------------
# ADMIN: ADD USER
# --------------------------------------------------

@app.route("/admin/users/add", methods=["POST"])
def admin_add_user():

    if session.get("role") != "Admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    username = request.form.get("username", "").strip()
    raw_password = request.form.get("password", "")
    role = request.form.get("role", "")
    specialization = request.form.get(
        "specialization", "General Physician"
    ).strip()

    if len(username) < 3 or len(username) > 50:
        flash("Username must contain 3 to 50 characters.", "danger")
        return redirect(url_for("admin_users"))

    if len(raw_password) < 8:
        flash("Password must contain at least 8 characters.", "danger")
        return redirect(url_for("admin_users"))

    if role not in ["Patient", "Doctor", "Admin"]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_users"))

    if role != "Doctor":
        specialization = "N/A"
    elif not specialization:
        specialization = "General Physician"

    password = generate_password_hash(raw_password)

    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO users
                (username, password, role, specialization)
                VALUES (?, ?, ?, ?)
            """, (
                username,
                password,
                role,
                specialization
            ))

            conn.commit()

        flash(
            f"User {username} created successfully.",
            "success"
        )

    except sqlite3.IntegrityError:
        flash("Username already exists.", "danger")

    return redirect(url_for("admin_users"))


# --------------------------------------------------
# ADMIN: UPDATE USER ROLE
# --------------------------------------------------

@app.route(
    "/admin/users/update/<int:user_id>",
    methods=["POST"]
)
def admin_update_user(user_id):

    if session.get("role") != "Admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    new_role = request.form.get("role", "")
    new_spec = request.form.get(
        "specialization", "N/A"
    ).strip()

    if new_role not in ["Patient", "Doctor", "Admin"]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin_users"))

    # Prevent changing the current administrator's own role.
    if user_id == session.get("user_id") and new_role != "Admin":
        flash(
            "You cannot remove your own administrator role.",
            "danger"
        )
        return redirect(url_for("admin_users"))

    if new_role != "Doctor":
        new_spec = "N/A"
    elif not new_spec:
        new_spec = "General Physician"

    with get_db() as conn:

        result = conn.execute("""
            UPDATE users
            SET role = ?, specialization = ?
            WHERE id = ?
        """, (new_role, new_spec, user_id))

        conn.commit()

    if result.rowcount == 0:
        flash("User not found.", "warning")
    else:
        flash(
            "User role and details updated successfully.",
            "success"
        )

    return redirect(url_for("admin_users"))


# --------------------------------------------------
# ADMIN: DELETE USER
# --------------------------------------------------

@app.route(
    "/admin/users/delete/<int:user_id>",
    methods=["POST"]
)
def admin_delete_user(user_id):

    if session.get("role") != "Admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin_users"))

    with get_db() as conn:

        user = conn.execute("""
            SELECT id FROM users WHERE id = ?
        """, (user_id,)).fetchone()

        if user is None:
            flash("User not found.", "warning")
            return redirect(url_for("admin_users"))

        # Preserve appointment records instead of deleting users
        # referenced by existing appointments.
        appointment_count = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM appointments
            WHERE user_id = ? OR doctor_id = ?
        """, (user_id, user_id)).fetchone()["cnt"]

        if appointment_count > 0:
            flash(
                "Cannot delete this user because appointment records "
                "are associated with the account. Change the user's "
                "role instead.",
                "danger"
            )
            return redirect(url_for("admin_users"))

        conn.execute("""
            DELETE FROM users WHERE id = ?
        """, (user_id,))

        conn.commit()

    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully.", "info")

    return redirect(url_for("index"))


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=3000,
        debug=False
    )
