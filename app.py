from flask import Flask, render_template, render_template_string, request, redirect, session, flash
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
import traceback
import re
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
load_dotenv()

app = Flask(__name__)
# secret can be provided via .env (recommended)
app.secret_key = os.getenv("SECRET_KEY", "secret123")

# ---------------- EMAIL FUNCTION ----------------
def send_email(to_email, subject, message):
    sender_email = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_PASS")

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    if not sender_email or not app_password:
        print("Email credentials not configured; skipping send_email")
        return False

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        print("Email sent ✅ to", to_email)
        return True
    except Exception as e:
        print("Email error:", e)
        traceback.print_exc()
        return False

def create_admin():
    from werkzeug.security import generate_password_hash
    conn = sqlite3.connect("database.db")

    admin = conn.execute(
        "SELECT * FROM users WHERE role='admin'"
    ).fetchone()

    if not admin:
        conn.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (?, ?, ?, ?, ?)",
            ("Admin", "admin@gmail.com", generate_password_hash("admin123"), "admin", 1)
        )
        conn.commit()
        print("✅ Admin Created")

    conn.close()
def notify_applicants_of_job(job_id, subject, message):
    """Send an email notification to all applicants of a job."""
    conn = sqlite3.connect("database.db")
    rows = conn.execute(
        "SELECT email FROM applications WHERE job_id=?",
        (job_id,)
    ).fetchall()

    for r in rows:
        if not r or not r[0]:
            continue

        email = r[0]

        # store notification
        cur = conn.cursor()
        # attempt immediate send; mark delivered if successful
        sent = send_email(email, subject, message)
        delivered_flag = 1 if sent else 0

        cur.execute(
            "INSERT INTO notifications (email, subject, message, delivered) VALUES (?, ?, ?, ?)",
            (email, subject, message, delivered_flag)
        )
        conn.commit()

    conn.close()

# ---------------- FOLDER ----------------
if not os.path.exists("static/resumes"):
    os.makedirs("static/resumes")

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        skills TEXT,
        experience TEXT,
        approved INTEGER DEFAULT 1
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        location TEXT,
        salary TEXT,
        description TEXT
    )
    """)

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT 'Open'")
    except:
        pass

    conn.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        email TEXT,
        name TEXT,
        phone TEXT,
        resume TEXT,
        status TEXT DEFAULT 'Pending'
    )
    """)

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_date TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_time TEXT")
    except:
        pass
    # 🔥 JOB EXTRA FIELDS
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN skills TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN experience TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN deadline TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN openings INTEGER")
    except:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN resume TEXT")
    except:
        pass
    # 🔥 ADD PROFILE COLUMNS
    try:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN education TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN location TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN about TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN resume TEXT")
    except:
        pass
    # 🔥 ADD INTERVIEW COLUMNS
    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_date TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_time TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_link TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN interviewer TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE applications ADD COLUMN notes TEXT")
    except:
        pass
    # 🔥 ADD USER_ID IN APPLICATIONS
    try:
        conn.execute("ALTER TABLE applications ADD COLUMN user_id INTEGER")
    except:
        pass

    # 🔥 ADD USER_ID IN NOTIFICATIONS
    try:
        conn.execute("ALTER TABLE notifications ADD COLUMN user_id INTEGER")
    except:
        pass
    # 🔥 ADD NEW JOB FIELDS (RUNS ONLY ONCE)

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN skills TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN experience TEXT")
    except:
        pass

    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN employer_email TEXT;")
    except:
        pass
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN posted_by TEXT;")
    except:
        pass
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        subject TEXT,
        message TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        delivered INTEGER DEFAULT 0,
        read INTEGER DEFAULT 0
    )
    """)

    conn.close()

init_db()
create_admin()
# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = sqlite3.connect("database.db")

        email = request.form["email"]
        password = request.form["password"]

        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if user:
            from werkzeug.security import check_password_hash

            # 🔐 password check
            if not check_password_hash(user[3], password):
                return render_template("login.html", error="Invalid Password ❌")

            # 🔥 approval check
            if user[4] == "employer" and user[7] == 0:
                return render_template("login.html", error="❌ Wait for Admin Approval")

            session["user"] = user[2]
            session["role"] = user[4]

            if user[4] == "admin":
                return redirect("/admin-dashboard")
            else:
                return redirect("/dashboard")

        else:
            return render_template("login.html", error="Invalid Email ❌")

    return render_template("login.html")
@app.route('/approve-employer/<int:id>')
def approve_employer(id):
    if session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    conn.execute("UPDATE users SET approved=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

    flash("Employer Approved ✅")
    return redirect("/admin-dashboard")
def extract_resume_text(path):
    text = ""

    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    text += content + " "
    except Exception as e:
        print("Resume Error:", e)

    return text.lower()
# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        conn = sqlite3.connect("database.db")

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"].lower()

        # check existing user
        existing = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            return render_template("register.html", error="Account already exists ⚠️")

        # 🔐 hash password
        from werkzeug.security import generate_password_hash
        hashed_password = generate_password_hash(password)

        # 🔥 employer needs approval
        approved = 1
        if role == "employer":
            approved = 0

        conn.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (?, ?, ?, ?, ?)",
            (name, email, hashed_password, role, approved)
        )

        conn.commit()
        conn.close()

        if role == "employer":
            return render_template("login.html", error="⏳ Wait for Admin Approval")

        return redirect("/login")

    return render_template("register.html", error=error)
# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    role = session["role"]
    user_email = session["user"]

    if role == "employer":
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        shortlisted = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status='Shortlisted'"
        ).fetchone()[0]

        conn.close()

        return render_template("dashboard_employer.html",
                               total_jobs=total_jobs,
                               total_applications=total_apps,
                               shortlisted=shortlisted)

    else:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

        apps = conn.execute(
            "SELECT status FROM applications WHERE email=?",
            (user_email,)
        ).fetchall()

        total_apps = len(apps)
        shortlisted = len([a for a in apps if a[0] == "Shortlisted"])

        conn.close()

        return render_template("dashboard_user.html",
                               total_jobs=total_jobs,
                               my_applications=total_apps,
                               shortlisted=shortlisted)

# ---------------- POST JOB ----------------
@app.route("/post-job", methods=["GET", "POST"])
def post_job():
    if session.get("role") != "employer":
        return redirect("/login")

    if request.method == "POST":

        # ✅ GET DATA SAFELY
        title = request.form.get("title")
        company = request.form.get("company")
        location = request.form.get("location")
        salary = request.form.get("salary")
        description = request.form.get("description")

        skills = request.form.get("skills")
        experience = request.form.get("experience")
        job_type = request.form.get("job_type")

        deadline = request.form.get("deadline")
        openings = request.form.get("openings")

        # ✅ BASIC VALIDATION
        if not title or not company or not skills:
            flash("Please fill required fields ❌")
            return redirect("/post-job")

        conn = sqlite3.connect("database.db")

        try:
            conn.execute("""
INSERT INTO jobs 
(title, company, location, salary, description, skills, experience, job_type, deadline, openings, employer_email)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    request.form["title"],
    request.form["company"],   # company name
    request.form["location"],
    request.form["salary"],
    request.form["description"],
    request.form["skills"],
    request.form["experience"],
    request.form["job_type"],
    request.form["deadline"],
    request.form["openings"],
    session["user"]            # 🔥 IMPORTANT
))

            conn.commit()
            flash("Job Posted Successfully ✅")

        except Exception as e:
            print("ERROR:", e)
            flash("Something went wrong ❌")

        finally:
            conn.close()

        return redirect("/dashboard")

    return render_template("post_job.html")
# ---------------- VIEW JOBS ----------------
@app.route("/view-jobs", methods=["GET", "POST"])
def view_jobs():
    conn = sqlite3.connect("database.db")

    search = request.form.get("search")
    location = request.form.get("location")
    min_salary = request.form.get("salary")

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if search:
        query += " AND title LIKE ?"
        params.append('%' + search + '%')

    if location:
        query += " AND location LIKE ?"
        params.append('%' + location + '%')

    if min_salary:
        query += " AND salary >= ?"
        params.append(min_salary)

    jobs = conn.execute(query, params).fetchall()

    applied_jobs = []

    if "user" in session:
        applied = conn.execute(
            "SELECT job_id FROM applications WHERE email=?",
            (session["user"],)
        ).fetchall()

        applied_jobs = [a[0] for a in applied]

    conn.close()

    return render_template("view_jobs.html",
                           jobs=jobs,
                           applied_jobs=applied_jobs)

def calculate_match(user_skills, job_description):
    user_set = set(user_skills.lower().split(","))
    job_set = set(job_description.lower().split())

    if len(job_set) == 0:
        return 0

    match = len(user_set & job_set) / len(job_set)
    return round(match * 100, 2)
@app.route("/chart-data")
def chart_data():
    conn = sqlite3.connect("database.db")

    jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    conn.close()

    return {
        "jobs": jobs,
        "applications": apps,
        "users": users
    }
# ---------------- VIEW APPLICANTS ----------------
@app.route("/view-applicants/<int:job_id>")
def view_applicants(job_id):

    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    data = conn.execute("""
        SELECT 
            applications.id,
            applications.name,
            applications.email,
            applications.phone,
            applications.resume,
            applications.status,
            applications.interview_date,
            applications.interview_time,
            applications.interview_link,

            users.skills,
            users.experience,
            users.education,

            jobs.title,
            jobs.description,
            jobs.skills as job_skills,
            jobs.experience as job_exp

        FROM applications
        JOIN users ON applications.email = users.email
        JOIN jobs ON applications.job_id = jobs.id
        WHERE jobs.id=?
        ORDER BY applications.id DESC
    """, (job_id,)).fetchall()

    result = []

    for app in data:

        # 🔥 RESUME TEXT
        resume_text = ""
        if app["resume"]:
            try:
                import pdfplumber
                path = "static/resumes/" + app["resume"]

                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        resume_text += page.extract_text() or ""
            except:
                pass

        # 🔥 PROFILE TEXT
        profile_text = (
            (app["skills"] or "") + " " +
            (app["experience"] or "") + " " +
            (app["education"] or "")
        )

        # 🔥 JOB TEXT
        job_text = (app["title"] + " " + app["description"] + " " + (app["job_skills"] or "")).lower()
        candidate_text = (profile_text + " " + resume_text).lower()

        # 🔥 SIMPLE SCORE (WORKING 100%)
        score = 0
        if candidate_text.strip():
            match = sum(1 for word in job_text.split() if word in candidate_text)
            score = round((match / len(job_text.split())) * 100, 2)

        result.append({
            "id": app["id"],
            "name": app["name"],
            "email": app["email"],
            "phone": app["phone"],
            "resume": app["resume"],
            "status": app["status"] or "Applied",
            "score": score,
            "interview_date": app["interview_date"],
            "interview_time": app["interview_time"],
            "interview_link": app["interview_link"]
        })

    conn.close()

    return render_template("view_applicants.html", apps=result)

@app.route("/all-applications")
def all_applications():
    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # 🔥 FILTERS
    search = request.args.get("search")
    status = request.args.get("status")
    job = request.args.get("job")

    query = """
        SELECT 
            applications.id,
            applications.name,
            applications.email,
            applications.resume,
            applications.status,

            users.skills,
            users.experience,
            users.education,

            jobs.id as job_id,
            jobs.title,
            jobs.skills as job_skills,
            jobs.description,
            jobs.experience as job_experience

        FROM applications
        JOIN jobs ON applications.job_id = jobs.id
        JOIN users ON applications.email = users.email

        WHERE jobs.employer_email = ?
    """

    params = [session["user"]]   # ✅ FIXED

    # 🔍 SEARCH
    if search:
        query += " AND (applications.name LIKE ? OR applications.email LIKE ?)"
        params.extend(['%' + search + '%', '%' + search + '%'])

    # 📌 STATUS
    if status:
        query += " AND applications.status = ?"
        params.append(status)

    # 💼 JOB FILTER
    if job:
        query += " AND jobs.title = ?"
        params.append(job)

    query += " ORDER BY applications.id DESC"

    data = conn.execute(query, params).fetchall()

    result = []

    for app in data:

        # 🔥 RESUME TEXT
        resume_text = ""
        if app["resume"]:
            try:
                resume_text = extract_resume_text("static/resumes/" + app["resume"])
            except:
                pass

        # 🔥 CORRECT DATA STRUCTURE
        job_data = {
            "title": app["title"],
            "skills": app["job_skills"],
            "experience": app["job_experience"],
            "description": app["description"]
        }

        user_data = {
            "skills": app["skills"],
            "experience": app["experience"],
            "education": app["education"]
        }

        score = calculate_match_score(job_data, user_data, resume_text)

        result.append({
            "id": app["id"],
            "name": app["name"],
            "email": app["email"],
            "resume": app["resume"],
            "status": app["status"],
            "job": app["title"],
            "score": score
        })

    # 🔥 JOB LIST FOR FILTER
    jobs = conn.execute("""
        SELECT DISTINCT title FROM jobs
        WHERE employer_email = ?
    """, (session["user"],)).fetchall()

    job_list = [j["title"] for j in jobs]

    conn.close()

    return render_template("all_applications.html", apps=result, jobs=job_list)
def update_job_status(job_id):
        # only employers or admins can change job status
        if session.get('role') not in ('employer', 'admin'):
                return redirect('/login')

        conn = sqlite3.connect('database.db')

        if request.method == 'POST':
                new_status = request.form.get('status')
                if not new_status:
                        conn.close()
                        flash('Status is required')
                        return redirect(request.referrer or '/view-jobs')

                conn.execute('UPDATE jobs SET status=? WHERE id=?', (new_status, job_id))
                conn.commit()

                # notify applicants
                notify_applicants_of_job(
                        job_id,
                        f"Job status updated: {new_status}",
                        f"The job you applied for has been updated to '{new_status}'."
                )

                conn.close()
                flash('Job status updated and applicants notified ✅')
                return redirect('/view-jobs')

        # GET -> simple inline form
        job = conn.execute('SELECT title, status FROM jobs WHERE id=?', (job_id,)).fetchone()
        conn.close()

        if not job:
                return redirect('/view-jobs')

        return render_template_string('''
                <!doctype html>
                <html>
                <head>
                    <title>Update Job Status</title>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                </head>
                <body class="p-4">
                    <div class="container">
                        <h3>Update status for: {{ job[0] }}</h3>
                        <form method="post">
                            <div class="mb-3">
                                <label class="form-label">Status</label>
                                <select name="status" class="form-select">
                                    <option {% if job[1]=='Open' %}selected{% endif %}>Open</option>
                                    <option {% if job[1]=='Closed' %}selected{% endif %}>Closed</option>
                                    <option {% if job[1]=='Paused' %}selected{% endif %}>Paused</option>
                                </select>
                            </div>
                            <button class="btn btn-primary">Update & Notify</button>
                            <a href="/view-jobs" class="btn btn-link">Cancel</a>
                        </form>
                    </div>
                </body>
                </html>
        ''', job=job)

@app.route("/edit-job/<int:id>")
def edit_job(id):
    return "Edit page coming..."

@app.route("/delete-job/<int:id>")
def delete_job(id):
    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM jobs WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/view-jobs")
# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin-dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = sqlite3.connect('database.db')

    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_jobs = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
    total_apps = conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0]
    shortlisted = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='Shortlisted'"
    ).fetchone()[0]

    users = conn.execute('SELECT * FROM users').fetchall()
    jobs = conn.execute('SELECT * FROM jobs').fetchall()

    # 🔥 pending employers
    pending_employers = conn.execute(
        "SELECT * FROM users WHERE role='employer' AND approved=0"
    ).fetchall()

    conn.close()

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_jobs=total_jobs,
                           total_apps=total_apps,
                           shortlisted=shortlisted,
                           users=users,
                           jobs=jobs,
                           pending_employers=pending_employers)
# ---------------- APPLY ----------------
import os, uuid
from werkzeug.utils import secure_filename

@app.route('/apply/<int:id>', methods=['POST'])
def apply(id):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    user_email = session["user"]

    # ✅ CHECK IF ALREADY APPLIED
    existing = cursor.execute("""
        SELECT * FROM applications 
        WHERE email=? AND job_id=?
    """, (user_email, id)).fetchone()

    if existing:
        conn.close()
        return render_template('applied.html', message="⚠️ You already applied for this job!")

    # ✅ FORM DATA
    name = request.form['name']
    phone = request.form['phone']
    file = request.files['resume']

    # ✅ FILE SAVE
    filename = secure_filename(file.filename)

    if not filename:
        filename = f"{uuid.uuid4().hex}.pdf"
    else:
        filename = f"{uuid.uuid4().hex}_{filename}"

    save_path = os.path.join("static/resumes", filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)

    # ✅ INSERT APPLICATION
    cursor.execute("""
        INSERT INTO applications (job_id, email, name, phone, resume, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (id, user_email, name, phone, filename, "Applied"))

    conn.commit()

    # 🔥 🔔 FIXED NOTIFICATION (NO EMAIL DEPENDENCY)
    try:
        conn.execute("""
            INSERT INTO notifications (email, subject, message, created_at, read)
            VALUES (?, ?, ?, datetime('now'), 0)
        """, (
            user_email,
            "Application Submitted",
            f"You applied successfully for job ID {id}"
        ))
        conn.commit()
    except Exception as e:
        print("Notification Error:", e)

    conn.close()

    return render_template('applied.html', message="✅ Applied Successfully!")
# ---------------- SHORTLIST ----------------
@app.route("/shortlist/<int:id>")
def shortlist(id):
    conn = sqlite3.connect("database.db")

    user = conn.execute(
        "SELECT email FROM applications WHERE id=?",
        (id,)
    ).fetchone()


    conn.execute("UPDATE applications SET status='Shortlisted' WHERE id=?", (id,))
    conn.commit()

    sent = send_email(user[0], "Shortlisted 🎉", "Congratulations! You have been shortlisted.")
    try:
        conn.execute(
            "INSERT INTO notifications (email, subject, message, delivered) VALUES (?, ?, ?, ?)",
            (user[0], "Shortlisted 🎉", "Congratulations! You have been shortlisted.", 1 if sent else 0)
        )
        conn.commit()
    except Exception:
        pass

    conn.close()
    return redirect(request.referrer)

# ---------------- REJECT ----------------
@app.route("/reject/<int:id>")
def reject(id):
    conn = sqlite3.connect("database.db")

    user = conn.execute(
        "SELECT email FROM applications WHERE id=?",
        (id,)
    ).fetchone()

    conn.execute("UPDATE applications SET status='Rejected' WHERE id=?", (id,))
    conn.commit()

    sent = send_email(user[0], "Application Update", "Sorry, you were not selected.")
    try:
        conn.execute(
            "INSERT INTO notifications (email, subject, message, delivered) VALUES (?, ?, ?, ?)",
            (user[0], "Application Update", "Sorry, you were not selected.", 1 if sent else 0)
        )
        conn.commit()
    except Exception:
        pass

    conn.close()
    return redirect(request.referrer)
@app.route("/admin/jobs")
def admin_jobs():

    if session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    jobs = conn.execute("""
        SELECT 
            jobs.*,
            COUNT(applications.id) as total_applicants
        FROM jobs
        LEFT JOIN applications 
        ON jobs.id = applications.job_id
        GROUP BY jobs.id
        ORDER BY jobs.id DESC
    """).fetchall()

    conn.close()

    return render_template("admin_jobs.html", jobs=jobs)
@app.route("/admin/edit-job/<int:id>", methods=["GET", "POST"])
def admin_edit_job(id):

    if session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    if request.method == "POST":

        conn.execute("""
            UPDATE jobs SET
            title=?, company=?, location=?, salary=?, description=?,
            skills=?, experience=?, job_type=?, deadline=?, openings=?
            WHERE id=?
        """, (
            request.form["title"],
            request.form["company"],
            request.form["location"],
            request.form["salary"],
            request.form["description"],
            request.form["skills"],
            request.form["experience"],
            request.form["job_type"],
            request.form["deadline"],
            request.form["openings"],
            id
        ))

        conn.commit()
        conn.close()

        return redirect("/admin/jobs")

    job = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
    conn.close()

    return render_template("admin_edit_job.html", job=job)
@app.route("/admin/delete-job/<int:id>")
def admin_delete_job(id):

    if session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    conn.execute("DELETE FROM jobs WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin/jobs")
# ---------------- SCHEDULE ----------------
@app.route("/schedule/<int:id>", methods=["GET", "POST"])
def schedule(id):
    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    if request.method == "POST":
        date = request.form["date"]
        time = request.form["time"]
        link = request.form["link"]
        interviewer = request.form["interviewer"]
        notes = request.form["notes"]

        # get email + job
        data = conn.execute("""
            SELECT applications.email, jobs.title
            FROM applications
            JOIN jobs ON applications.job_id = jobs.id
            WHERE applications.id=?
        """, (id,)).fetchone()

        conn.execute("""
            UPDATE applications
            SET interview_date=?, interview_time=?, 
                interview_link=?, interviewer=?, notes=?, 
                status='Interview Scheduled'
            WHERE id=?
        """, (date, time, link, interviewer, notes, id))

        conn.commit()
        conn.close()

        # 🔔 notify
        create_notification(
            data[0],
            "Interview Scheduled",
            f"Interview for '{data[1]}' on {date} at {time}. Link: {link}"
        )

        return redirect("/all-applications")

    conn.close()
    return render_template("schedule.html", id=id)
@app.route("/employer/jobs")
def employer_jobs():

    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    jobs = conn.execute("""
        SELECT 
            jobs.*,
            COUNT(applications.id) as total_applicants
        FROM jobs
        LEFT JOIN applications 
        ON jobs.id = applications.job_id
        WHERE jobs.employer_email = ?
        GROUP BY jobs.id
        ORDER BY jobs.id DESC
    """, (session["user"],)).fetchall()

    conn.close()

    return render_template("employer_jobs.html", jobs=jobs)
@app.route("/employer/delete-job/<int:id>")
def delete_job_employer(id):

    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    conn.execute("DELETE FROM jobs WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/employer/jobs")
@app.route("/employer/edit-job/<int:id>", methods=["GET", "POST"])
@app.route("/employer/edit-job/<int:id>", methods=["GET", "POST"])
def employer_edit_job(id):

    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    if request.method == "POST":

        conn.execute("""
            UPDATE jobs SET
            title=?, company=?, location=?, salary=?, description=?,
            skills=?, experience=?, job_type=?, deadline=?, openings=?
            WHERE id=? AND employer_email=?
        """, (
            request.form["title"],
            request.form["company"],
            request.form["location"],
            request.form["salary"],
            request.form["description"],
            request.form["skills"],
            request.form["experience"],
            request.form["job_type"],
            request.form["deadline"],
            request.form["openings"],
            id,
            session["user"]
        ))

        conn.commit()
        conn.close()

        return redirect("/employer/jobs")

    job = conn.execute("""
        SELECT * FROM jobs 
        WHERE id=? AND employer_email=?
    """, (id, session["user"])).fetchone()

    conn.close()

    return render_template("employer_edit_job.html", job=job)
@app.route("/view-profile/<int:id>")
def view_profile(id):
    if session.get("role") != "employer":
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    data = conn.execute("""
        SELECT applications.*, users.skills, users.experience
        FROM applications
        LEFT JOIN users ON applications.email = users.email
        WHERE applications.id=?
    """, (id,)).fetchone()

    conn.close()

    return render_template("profile_view.html", data=data)

# ---------------- MY APPLICATIONS ----------------
@app.route("/my-applications")
def my_applications():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    jobs = conn.execute("""
        SELECT 
            jobs.title,
            jobs.company,
            jobs.location,
            applications.id,
            applications.status,
            applications.interview_date,
            applications.interview_time,
            applications.interview_link
        FROM applications
        JOIN jobs ON applications.job_id = jobs.id
        WHERE applications.email=?
        ORDER BY applications.id DESC
    """, (session["user"],)).fetchall()

    conn.close()

    return render_template("my_applications.html", jobs=jobs)
import os
from werkzeug.utils import secure_filename

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # ✅ VERY IMPORTANT

    # ================= UPDATE =================
    if request.method == "POST":

        phone = request.form.get("phone")
        skills = request.form.get("skills")
        experience = request.form.get("experience")
        education = request.form.get("education")
        location = request.form.get("location")
        about = request.form.get("about")

        resume_file = request.files.get("resume")

        if resume_file and resume_file.filename != "":
            filename = resume_file.filename
            resume_file.save("static/resumes/" + filename)

            conn.execute("""
                UPDATE users 
                SET phone=?, skills=?, experience=?, education=?, location=?, about=?, resume=?
                WHERE email=?
            """, (phone, skills, experience, education, location, about, filename, session["user"]))

        else:
            conn.execute("""
                UPDATE users 
                SET phone=?, skills=?, experience=?, education=?, location=?, about=?
                WHERE email=?
            """, (phone, skills, experience, education, location, about, session["user"]))

        conn.commit()

    # ================= FETCH =================
    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()

    conn.close()

    return render_template("profile.html", user=user)
@app.route("/update-status/<int:id>", methods=["POST"])
def update_status(id):
    if session.get("role") != "employer":
        return redirect("/login")

    new_status = request.form.get("status")

    conn = sqlite3.connect("database.db")

    # ✅ FIXED QUERY
    data = conn.execute("""
        SELECT applications.email, jobs.title
        FROM applications
        JOIN jobs ON applications.job_id = jobs.id
        WHERE applications.id=?
    """, (id,)).fetchone()

    conn.execute(
        "UPDATE applications SET status=? WHERE id=?",
        (new_status, id)
    )

    conn.commit()
    conn.close()

    # 🔔 notification
    if data:
        create_notification(
            data[0],
            "Application Update",
            f"Your application for '{data[1]}' is now {new_status}"
        )

    return redirect(request.referrer or "/all-applications")
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------


@app.route('/debug-send-email')
def debug_send_email():
    """Debug route: call /debug-send-email?to=you@domain to send a test email.
       Only intended for development/testing on localhost."""
    to = request.args.get('to')
    if not to:
        return "Provide ?to=you@domain.com", 400

    ok = send_email(to, "Test Email from JobPortal", "This is a test message from your JobPortal instance.")
    if ok:
        return f"Sent test email to {to}"
    else:
        return f"Failed to send test email to {to}. Check server logs and .env settings.", 500


@app.route('/admin/notifications')
def admin_notifications():
        if session.get('role') != 'admin':
                return redirect('/login')

        conn = sqlite3.connect('database.db')
        rows = conn.execute('SELECT id, email, subject, message, created_at, delivered FROM notifications ORDER BY created_at DESC LIMIT 200').fetchall()
        conn.close()

        return render_template_string('''
        <!doctype html>
        <html>
        <head>
            <title>Notifications</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="p-4">
            <div class="container">
                <h3>Notifications (most recent)</h3>
                <table class="table table-sm table-striped">
                    <thead><tr><th>ID</th><th>Email</th><th>Subject</th><th>Message</th><th>At</th><th>Delivered</th><th></th></tr></thead>
                    <tbody>
                    {% for r in rows %}
                        <tr>
                            <td>{{ r[0] }}</td>
                            <td>{{ r[1] }}</td>
                            <td>{{ r[2] }}</td>
                            <td style="max-width:400px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r[3] }}</td>
                            <td>{{ r[4] }}</td>
                            <td>{% if r[5]==1 %}✅{% else %}❌{% endif %}</td>
                            <td><a href="/admin/resend/{{ r[0] }}" class="btn btn-sm btn-primary">Resend</a></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
                <a href="/admin/notifications" class="btn btn-link">Refresh</a>
            </div>
        </body>
        </html>
        ''', rows=rows)

def create_notification(email, subject, message):
    conn = sqlite3.connect("database.db")

    conn.execute(
        "INSERT INTO notifications (email, subject, message) VALUES (?, ?, ?)",
        (email, subject, message)
    )

    conn.commit()
    conn.close()
@app.route('/admin/resend/<int:nid>')
def admin_resend(nid):
        if session.get('role') != 'admin':
                return redirect('/login')

        conn = sqlite3.connect('database.db')
        row = conn.execute('SELECT email, subject, message FROM notifications WHERE id=?', (nid,)).fetchone()
        if not row:
                conn.close()
                flash('Notification not found')
                return redirect('/admin/notifications')

        email, subject, message = row[0], row[1], row[2]
        sent = send_email(email, subject, message)
        if sent:
                conn.execute('UPDATE notifications SET delivered=1 WHERE id=?', (nid,))
                conn.commit()
                flash('Resent successfully')
        else:
                flash('Resend failed — check logs')

        conn.close()
        return redirect('/admin/notifications')


@app.route("/notifications")
def notifications():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    rows = conn.execute("""
        SELECT * FROM notifications 
        WHERE email=? 
        ORDER BY id DESC
    """, (session["user"],)).fetchall()

    conn.close()

    return render_template("notifications.html", rows=rows)


@app.route('/notifications/mark/<int:nid>')
def notifications_mark(nid):
    if 'user' not in session:
        return redirect('/login')

    user_email = session['user']
    conn = sqlite3.connect('database.db')
    # ensure the notification belongs to the user
    row = conn.execute('SELECT email FROM notifications WHERE id=?', (nid,)).fetchone()
    if not row or row[0] != user_email:
        conn.close()
        flash('Notification not found')
        return redirect('/notifications')

    conn.execute('UPDATE notifications SET read=1 WHERE id=?', (nid,))
    conn.commit()
    conn.close()
    return redirect('/notifications')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def calculate_match_score(job, user, resume_text):

    # 🔥 JOB DATA
    job_title = job["title"] or ""
    job_desc = job["description"] or ""
    job_skills = job["skills"] or ""
    job_exp = job["experience"] or ""

    # 🔥 USER DATA
    user_skills = user["skills"] or ""
    user_exp = user["experience"] or ""
    user_edu = user["education"] or ""

    # =========================
    # 1. SKILLS MATCH (40%)
    # =========================
    job_skill_list = [s.strip().lower() for s in job_skills.split(",") if s.strip()]
    user_skill_text = user_skills.lower()

    matched = sum(1 for skill in job_skill_list if skill in user_skill_text)
    skill_score = matched / len(job_skill_list) if job_skill_list else 0

    # =========================
    # 2. TEXT MATCH (30%)
    # =========================
    job_text = (job_title + " " + job_desc).lower()
    candidate_text = (user_skills + " " + user_exp + " " + user_edu + " " + resume_text).lower()

    if not candidate_text.strip():
        return 0

    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([job_text, candidate_text])
    text_score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]

    # =========================
    # 3. EXPERIENCE MATCH (20%)
    # =========================
    job_exp_num = int(re.findall(r'\d+', job_exp)[0]) if re.findall(r'\d+', job_exp) else 0
    user_exp_num = int(re.findall(r'\d+', user_exp)[0]) if re.findall(r'\d+', user_exp) else 0

    if user_exp_num >= job_exp_num:
        exp_score = 1
    else:
        exp_score = user_exp_num / job_exp_num if job_exp_num else 0

    # =========================
    # 4. TITLE MATCH (10%)
    # =========================
    title_score = 1 if job_title.lower() in candidate_text else 0

    # =========================
    # FINAL SCORE
    # =========================
    final_score = (
        (skill_score * 0.4) +
        (text_score * 0.3) +
        (exp_score * 0.2) +
        (title_score * 0.1)
    )

    return round(final_score * 100, 2)
@app.context_processor
def inject_unread_count():
    # inject unread notification count for logged-in user
    if 'user' in session:
        conn = sqlite3.connect('database.db')
        c = conn.execute('SELECT COUNT(*) FROM notifications WHERE email=? AND read=0', (session['user'],)).fetchone()[0]
        conn.close()
        return dict(unread_notifications=c)
    return dict(unread_notifications=0)


if __name__ == "__main__":
    app.run(debug=True)
