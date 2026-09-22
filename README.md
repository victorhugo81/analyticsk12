# AnalyticsK12

![AnalyticsK12 Logo](https://apps.zavistar.com/wp-content/uploads/2026/08/logo.png) 

AnalyticsK12 is a K-12 school district analytics platform built with Flask and MySQL. It centralizes student demographics, attendance, discipline, grades and graduation progress, English Learner status, MTSS interventions, staffing, and family contact data across multiple school sites, and surfaces it through role-based dashboards and data quality tools.

[AnalyticsK12.com](https://AnalyticsK12.com) 

![AnalyticsK12 Analytics Home](https://apps.zavistar.com/wp-content/uploads/2026/08/analyticsk12-dashboard-scaled.png) 
![AnalyticsK12 Sample Dashboard](https://apps.zavistar.com/wp-content/uploads/2026/08/analyticsk12-demog-dash-scaled.png) 

---

## Features

- **Multi-site analytics dashboards** — Demographics, SWD, English Learner Progress, Absenteeism, Discipline, Enrollment (K–6, Middle, High School), Graduation Status, Equity Gaps, and Early Warning dashboards with Chart.js visualizations and PDF/print export.
- **Graduation tracking** — Configurable subject-area credit requirements (English, Math, etc., with department/keyword-based course matching and admin-defined grade spans, e.g. Algebra I due by 9th grade vs. Social Science phased in from 10th–12th), and a Graduation Status dashboard showing every high schooler's on-track/behind/credit-deficient standing against those requirements — status reflects whichever subject is furthest behind its own pace, not just a total-credits count. Sites can be flagged as a Continuation track with lower per-subject (and total) credit targets than Standard sites.
- **Equity Gaps dashboard** — Chronic absenteeism and suspension rate gaps for key student subgroups (SWD, EL, FRM, foster, homeless) measured against the district baseline.
- **English Learner Progress** — Language proficiency status breakdown (EL/RFEP/IFEP/EO/TBD), reclassification rate, and chronic-absence/failing-grade signals narrowed to the EL population.
- **Early Warning System with MTSS tracking** — A weighted, continuous 0–100 risk score (not just a flag count) combining attendance, academics, and behavior, plus built-in Tier 1/2/3 intervention logging so staff can record what's been tried for an at-risk student and whether it worked.
- **CALPADS Compliance** — 10 automated data quality checks across identity, enrollment, and program submission types with per-student drill-down.
- **Student management** — Paginated list with multi-filter subgroup support (homeless, FRM, SWD, foster, migrant, 504, EL status, gender). Student detail pages include demographics, grades, graduation progress, absences, incidents, interventions, courses, and linked parents.
- **Per-school-year student records** — The same student ID can have separate enrollment records per school year. All dashboards and lists are scoped to the active school year session filter.
- **Bulk CSV import** — Upload `sites.csv`, `demographics.csv`, `absences.csv`, `behavioral_incidents.csv`, `grades.csv`, `staff.csv`, `courses.csv`, `master_schedule.csv`, `students_schedule.csv`, `parents.csv`, and `users.csv` individually or together. Files are processed in dependency order automatically, with a processing modal and result summary shown for large uploads.
- **FTP integration** — Configure an FTP server and schedule automatic imports with per-day-of-week scheduling, start/stop dates, and last-run status tracking.
- **Organization settings** — Configure organization name, logo, SMTP email, FTP connection, academic calendar (current school year, first/last school day), graduation credit requirements, and dashboard card visibility.
- **Role-based access control** — Admin, District Administrator, School Administrator, Teacher, and Staff roles with route-level enforcement. Only Admin and District Administrator can view data across every school; School Administrator can be assigned to more than one campus by an Admin/District Administrator, everyone else is scoped to their own site.
- **Encrypted PII and credentials** — Email addresses (users, students, teachers, parents), phone numbers (parents, site principals), student statewide IDs (SSID), SMTP passwords, and FTP credentials all stored encrypted using Fernet symmetric encryption.
- **Login security** — Rate limiting, account lockout after repeated failures, admin-initiated account unlock, forced password change on first login, minimum 12-character complexity requirement.
- **Session-based global filters** — School year, site, snap date, and student status filters persist across all pages for the session.
- **Upload log** — Every bulk import is logged with added/updated counts, uploader, timestamp, and error details.

---

## Application Stack

- **Python 3.13+**
- **Flask 3.x** with Flask-Login, Flask-WTF, Flask-Migrate, Flask-Mail, Flask-Limiter, APScheduler
- **MySQL** via PyMySQL / SQLAlchemy
- **Bootstrap 5** + Material Dashboard UI
- See `pyproject.toml` for the complete dependency list

---

## Installation

### Prerequisites

- [Git](https://git-scm.com/downloads/)
- [uv — Python package manager](https://docs.astral.sh/uv/getting-started/installation/)
- [Python 3.13+](https://docs.astral.sh/uv/concepts/python-versions/)
- [MySQL Server](https://dev.mysql.com/doc/mysql-getting-started/en/)

### Step 1: Clone the repository

```bash
git clone https://github.com/victorhugo81/analyticsk12
cd analyticsk12
```

### Step 2: Set up the virtual environment

```bash
uv venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### Step 3: Install dependencies

```bash
uv sync
```

### Step 4: Configure the database

```bash
cd installation
python create_env.py   # interactive — creates .env with SECRET_KEY and DATABASE_URL
```

> **Important:** Never commit `.env` to version control.

Example `.env`:
```
SECRET_KEY=your_secure_random_key_here
DATABASE_URL=mysql+pymysql://username:password@localhost/analyticsk12
```

### Step 5: Apply database migrations

```bash
cd ..
flask --app main.py db upgrade
```

### Step 6: Seed initial data

```bash
python installation/seed_data.py           # roles, default site, admin user, default graduation requirements
python installation/seed_academic_data.py  # demo sites, students, staff, absences, incidents, grades
```

### Step 7: Start the development server

```bash
flask --app "main:create_app('development')" run
```

> **Important:** Don't run `flask --app main.py run` (without the factory argument) — the Flask CLI then calls `create_app()` with no argument, which falls back to `ProductionConfig` and marks the session cookie `Secure`. Browsers silently discard `Secure` cookies over plain `http://localhost`, so every session-based feature (School Year/Site/Status filters, login itself) will appear broken.

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and log in with the admin credentials created during seeding.

---

## Bulk CSV Import

Navigate to **Organization → Bulk Upload**. Drop one or more supported CSV files onto the upload zone. Files are processed in dependency order automatically (sites → staff → demographics → absences/incidents → courses → schedules/parents/grades → users), with a processing modal shown while large files are still uploading and a result modal summarizing what was added/updated/skipped once it's done.

| File | Purpose |
|---|---|
| `sites.csv` | Add or update school sites |
| `demographics.csv` | Add or update student enrollment records (one record per student per school year) |
| `absences.csv` | Insert absence/attendance records (deduplicates by site + student + date + period) |
| `behavioral_incidents.csv` | Insert discipline incident records (deduplicates by incident ID) |
| `staff.csv` | Add or update teachers/staff |
| `courses.csv` | Add or update course sections |
| `master_schedule.csv` | Assign teachers and periods to existing course sections |
| `students_schedule.csv` | Enroll or drop students from course sections |
| `parents.csv` | Add or update parent/guardian contacts and link to students |
| `grades.csv` | Add or update student course grade records; feeds the Grades tab, Graduation Status dashboard, and Early Warning's academic risk signal |
| `users.csv` | Add or update system user accounts |

Download column-reference templates from the upload page. All files accept UTF-8 or Windows (latin-1) encoding.

Graduation Status also depends on **Graduation Settings** (Organization → Graduation Settings), where you define subject-area credit requirements (e.g. "English: 40 credits"), how courses map to them by department and/or course-name keywords, and the grade span each subject is normally completed across (e.g. Algebra I by 9th grade, Social Science phased in from 10th–12th).

---

## Security

- Login rate limiting (Flask-Limiter) and account lockout after repeated failures
- CSRF protection on all forms (Flask-WTF)
- Passwords hashed with scrypt; minimum 12-character complexity enforced
- PII encrypted at rest (Fernet), never stored in plaintext: user/student/teacher/parent email addresses, parent/site-principal phone numbers, and student statewide IDs (SSID). SSIDs additionally use a deterministic HMAC blind index so dashboards can still join/group/filter by student across tables without ever decrypting.
- SMTP and FTP passwords encrypted at rest
- Forced password change on first login for bulk-created users
- Security headers applied via `after_request` in `main.py`
- Site-scoped data access — non-Admin/District-Administrator roles can only view or export students, teachers, courses, and incidents at the school(s) they're assigned to, enforced server-side (not just hidden in the UI)
- Bulk student-data exports (`/students/export/csv`) are recorded in an audit log (who, when, filters used, record count) for FERPA accountability

---

## Production Deployment

```bash
uv add gunicorn
gunicorn -w 4 "main:create_app('production')"
```

> Always pass `'production'` explicitly — `create_app()` with no argument now falls back
> to `ProductionConfig` as well (see `config.py`), but don't rely on that fallback alone;
> an explicit argument is the difference between "safe by default" and "safe on purpose."

Recommended `.env` additions for production:

```
RATELIMIT_STORAGE_URI=redis://localhost:6379/0
```

> Use Redis for the rate limiter in production — the default in-memory storage resets on every restart and does not scale across workers.

---

## Project Structure

```
analyticsk12/
├── application/
│   ├── models.py              # SQLAlchemy models
│   ├── forms.py               # Flask-WTF form classes
│   ├── routes.py              # All routes (~5800+ lines, single blueprint)
│   ├── utils.py               # Encryption, hashing helpers
│   ├── scheduled_jobs.py      # APScheduler FTP import job
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css      # Site-wide design system (colors, spacing, buttons, forms, tables)
│   │   │   └── dashboards.css
│   │   ├── download/          # CSV upload templates
│   │   └── js/
│   └── templates/
│       ├── includes/
│       │   ├── nav.html
│       │   └── footer.html
│       ├── base.html
│       ├── index.html
│       ├── bulk_upload_data.html
│       ├── organization.html
│       ├── student_details.html
│       ├── dashboard/         # Demographics, SWD, EL Progress, discipline, absenteeism, graduation, enrollment, calpads
│       ├── early_warning.html, interventions.html  # Early Warning + MTSS intervention tracking
│       └── ...
├── migrations/
│   └── versions/
├── installation/
│   ├── create_env.py
│   ├── seed_data.py
│   └── seed_academic_data.py
├── sample_files/              # Sample CSV files for testing imports
├── main.py
├── config.py
├── pyproject.toml
└── uv.lock
```

---

## License

AnalyticsK12 is licensed under the GNU General Public License v3. See the LICENSE file for details.

## Contact

For questions or suggestions, open an issue on GitHub or contact contact@victorhugosolis.com.
