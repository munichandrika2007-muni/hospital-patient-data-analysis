import os, sqlite3, csv, io
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-for-deployment")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "hospital.db"))
DEPARTMENTS = ["General Medicine", "Cardiology", "Orthopedics", "Pediatrics", "Neurology", "Emergency", "ICU"]
VISIT_TYPES = ["General Check-up", "Follow-up", "Consultation", "Outpatient", "Inpatient", "Emergency Visit", "Diagnostic Visit"]

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
          patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_name TEXT NOT NULL,
          age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 120),
          gender TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS visits (
          visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_id INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
          department TEXT NOT NULL,
          visit_date TEXT NOT NULL,
          visit_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Registered',
          notes TEXT DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if count == 0:
            samples = [
                ("Aarav Demo", 24, "Male"), ("Ananya Demo", 31, "Female"),
                ("Kiran Demo", 46, "Male"), ("Meera Demo", 12, "Female"),
                ("Ravi Demo", 58, "Male"), ("Divya Demo", 37, "Female"),
                ("Sample Patient 7", 8, "Not specified"), ("Sample Patient 8", 67, "Male")
            ]
            con.executemany("INSERT INTO patients(patient_name,age,gender) VALUES(?,?,?)", samples)
            pids = [r[0] for r in con.execute("SELECT patient_id FROM patients").fetchall()]
            today = date.today()
            demo_visits = []
            for i in range(36):
                pid = pids[i % len(pids)]
                month_offset = i % 6
                # Valid dates spread across recent months
                from datetime import timedelta
                d = today - timedelta(days=(i * 7) % 170)
                demo_visits.append((pid, DEPARTMENTS[i % len(DEPARTMENTS)], d.isoformat(),
                                    VISIT_TYPES[i % len(VISIT_TYPES)], "Completed" if i % 3 else "Registered", "Synthetic demo record"))
            con.executemany("INSERT INTO visits(patient_id,department,visit_date,visit_type,status,notes) VALUES(?,?,?,?,?,?)", demo_visits)

@app.route("/")
def dashboard():
    with connect() as con:
        patients = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        visits = con.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        today_count = con.execute("SELECT COUNT(*) FROM visits WHERE visit_date=?", (date.today().isoformat(),)).fetchone()[0]
        departments = con.execute("SELECT COUNT(DISTINCT department) FROM visits").fetchone()[0]
        monthly = con.execute("""SELECT substr(visit_date,1,7) month, COUNT(*) total
                                 FROM visits GROUP BY month ORDER BY month""").fetchall()
        dept = con.execute("""SELECT department, COUNT(*) total FROM visits
                              GROUP BY department ORDER BY total DESC""").fetchall()
        types = con.execute("""SELECT visit_type, COUNT(*) total FROM visits
                               GROUP BY visit_type ORDER BY total DESC""").fetchall()
        ages = con.execute("""SELECT CASE
            WHEN age < 13 THEN '0–12'
            WHEN age < 20 THEN '13–19'
            WHEN age < 36 THEN '20–35'
            WHEN age < 61 THEN '36–60'
            ELSE '61+' END age_band, COUNT(*) total
            FROM patients GROUP BY age_band
            ORDER BY CASE age_band WHEN '0–12' THEN 1 WHEN '13–19' THEN 2 WHEN '20–35' THEN 3 WHEN '36–60' THEN 4 ELSE 5 END""").fetchall()
        recent = con.execute("""SELECT v.visit_id, p.patient_name, v.department, v.visit_date, v.visit_type, v.status
            FROM visits v JOIN patients p ON p.patient_id=v.patient_id ORDER BY v.visit_date DESC, v.visit_id DESC LIMIT 7""").fetchall()
    return render_template("dashboard.html", patients=patients, visits=visits, today_count=today_count,
        departments=departments, monthly=[dict(x) for x in monthly], dept=[dict(x) for x in dept],
        types=[dict(x) for x in types], ages=[dict(x) for x in ages], recent=recent)

@app.route("/patients")
def patients_page():
    q = request.args.get("q", "").strip()
    with connect() as con:
        rows = con.execute("""SELECT p.*, (SELECT COUNT(*) FROM visits v WHERE v.patient_id=p.patient_id) visit_count
            FROM patients p WHERE (?='' OR CAST(p.patient_id AS TEXT) LIKE ? OR p.patient_name LIKE ?)
            ORDER BY p.patient_id DESC""", (q, f"%{q}%", f"%{q}%")).fetchall()
    return render_template("patients.html", patients=rows, q=q)

@app.route("/patients/add", methods=["GET", "POST"])
def add_patient():
    if request.method == "POST":
        name = request.form.get("patient_name", "").strip()
        gender = request.form.get("gender", "Not specified")
        try:
            age = int(request.form.get("age", ""))
            if not name or not 0 <= age <= 120:
                raise ValueError()
        except ValueError:
            flash("Enter a name and an age between 0 and 120.", "error")
            return render_template("patient_form.html", patient=None)
        with connect() as con:
            cur = con.execute("INSERT INTO patients(patient_name,age,gender) VALUES(?,?,?)", (name, age, gender))
            patient_id = cur.lastrowid
        flash(f"Patient #{patient_id} added. Add a visit record when needed.", "success")
        return redirect(url_for("add_visit", patient_id=patient_id))
    return render_template("patient_form.html", patient=None)

@app.route("/visits")
def visits_page():
    q = request.args.get("q", "").strip()
    with connect() as con:
        visits = con.execute("""SELECT v.*, p.patient_name FROM visits v JOIN patients p ON p.patient_id=v.patient_id
            WHERE (?='' OR p.patient_name LIKE ? OR CAST(v.patient_id AS TEXT) LIKE ? OR v.department LIKE ?)
            ORDER BY v.visit_date DESC, v.visit_id DESC""", (q, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    return render_template("visits.html", visits=visits, q=q)

@app.route("/visits/add", methods=["GET", "POST"])
def add_visit():
    patient_id = request.args.get("patient_id", type=int)
    with connect() as con:
        patients = con.execute("SELECT patient_id, patient_name FROM patients ORDER BY patient_name").fetchall()
    if request.method == "POST":
        try:
            pid = int(request.form["patient_id"])
            department = request.form["department"]
            visit_date = request.form["visit_date"]
            visit_type = request.form["visit_type"]
            status = request.form["status"]
            if department not in DEPARTMENTS or visit_type not in VISIT_TYPES:
                raise ValueError()
            date.fromisoformat(visit_date)
            with connect() as con:
                con.execute("""INSERT INTO visits(patient_id,department,visit_date,visit_type,status,notes)
                    VALUES(?,?,?,?,?,?)""", (pid, department, visit_date, visit_type, status, request.form.get("notes","").strip()))
            flash("Visit record added.", "success")
            return redirect(url_for("visits_page"))
        except (ValueError, KeyError, sqlite3.IntegrityError):
            flash("Please check the visit details and try again.", "error")
    return render_template("visit_form.html", patients=patients, departments=DEPARTMENTS, visit_types=VISIT_TYPES,
                           patient_id=patient_id, today=date.today().isoformat())

@app.route("/visits/<int:visit_id>/delete", methods=["POST"])
def delete_visit(visit_id):
    with connect() as con:
        con.execute("DELETE FROM visits WHERE visit_id=?", (visit_id,))
    flash("Visit record deleted.", "success")
    return redirect(url_for("visits_page"))

@app.route("/patients/<int:patient_id>")
def patient_history(patient_id):
    with connect() as con:
        patient = con.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        history = con.execute("SELECT * FROM visits WHERE patient_id=? ORDER BY visit_date DESC", (patient_id,)).fetchall()
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_page"))
    return render_template("history.html", patient=patient, visits=history)

@app.route("/reports")
def reports():
    with connect() as con:
        dept = con.execute("SELECT department, COUNT(*) total FROM visits GROUP BY department ORDER BY total DESC").fetchall()
        monthly = con.execute("SELECT substr(visit_date,1,7) month, COUNT(*) total FROM visits GROUP BY month ORDER BY month").fetchall()
        age = con.execute("""SELECT CASE WHEN age<13 THEN '0–12' WHEN age<20 THEN '13–19'
            WHEN age<36 THEN '20–35' WHEN age<61 THEN '36–60' ELSE '61+' END age_band, COUNT(*) total
            FROM patients GROUP BY age_band ORDER BY age_band""").fetchall()
    return render_template("reports.html", dept=dept, monthly=monthly, age=age)

@app.route("/reports/visits.csv")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["visit_id","patient_id","patient_name","department","visit_date","visit_type","status"])
    with connect() as con:
        rows = con.execute("""SELECT v.visit_id, p.patient_id, p.patient_name, v.department, v.visit_date, v.visit_type, v.status
            FROM visits v JOIN patients p ON p.patient_id=v.patient_id ORDER BY v.visit_date DESC""").fetchall()
        writer.writerows([tuple(r) for r in rows])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=hospital_visits_report.csv"})

@app.route("/upload", methods=["GET","POST"])
def upload_csv():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Choose a CSV file.", "error")
            return redirect(url_for("upload_csv"))
        try:
            reader = csv.DictReader(io.StringIO(file.stream.read().decode("utf-8-sig")))
            needed = {"patient_name","age","gender"}
            if not reader.fieldnames or not needed.issubset(set(reader.fieldnames)):
                raise ValueError("CSV must contain patient_name, age, gender columns.")
            added = 0
            with connect() as con:
                for row in reader:
                    name = (row.get("patient_name") or "").strip()
                    age = int(row.get("age", ""))
                    gender = (row.get("gender") or "Not specified").strip()
                    if not name or not 0 <= age <= 120:
                        continue
                    con.execute("INSERT INTO patients(patient_name,age,gender) VALUES(?,?,?)", (name,age,gender))
                    added += 1
            flash(f"Imported {added} synthetic patient records.", "success")
        except Exception as exc:
            flash(f"Could not import file: {exc}", "error")
        return redirect(url_for("upload_csv"))
    return render_template("upload.html")

@app.route("/health")
def health():
    return {"status":"ok", "database":"connected"}

init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
