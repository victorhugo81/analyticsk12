# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Is

**AnalyticsK12** is a K-12 school district analytics platform. It manages student demographics, attendance (absences), discipline (incidents), grades/graduation progress, English Learner status, MTSS interventions, staffing (teachers, courses), and family contacts (parents) across multiple school sites. It includes role-based access control, bulk CSV import, encrypted credentials, and session-based global filters (school year, site, snap date, student status).

---

## Running the App

```bash
# Run dev server
uv run flask --app main.py run

# Or activate the venv and use flask directly
source .venv/bin/activate
flask --app main.py run
```

Dependencies are managed with `uv`. To add or sync packages:
```bash
uv sync
uv add <package>
```

---

## Database

MySQL via PyMySQL. Connection string is in `.env` as `DATABASE_URL`.

```bash
# Apply all pending migrations
flask --app main.py db upgrade

# Generate a new migration after model changes
flask --app main.py db migrate -m "description"

# Check current migration version
flask --app main.py db current
```

Migration files live in `migrations/versions/`. After adding or changing a model, always run `migrate` then `upgrade`.

---

## Seeding Data

```bash
# 1. Create MySQL DB and write .env (interactive)
python installation/create_env.py

# 2. Seed roles, default site, admin user (interactive)
python installation/seed_data.py

# 3. Seed academic demo data (sites, students, teachers, courses, parents, absences, incidents, grades)
python installation/seed_academic_data.py
```

---

## Architecture

### App Factory

`main.py` contains `create_app(config_name)`. It initializes Flask extensions (SQLAlchemy, Flask-Login, CSRF, Flask-Mail, Flask-Limiter, APScheduler), registers the single blueprint, applies security headers, and wires database-stored SMTP config from the `Organization` model.

### Single Blueprint

All routes live in `application/routes.py` under one blueprint (`routes_blueprint`). The file is large (~5800+ lines) and organized into labeled sections:

- **Auth** — login, logout, set-password, account lockout (`unlock_user()` lets an Admin clear `failed_login_attempts`/`locked_until` for another user — `/unlock_user/<id>`, gated by `is_admin()`)
- **Users / Roles / Sites / Notifications / Organization** — admin management, incl. dashboard **Card Visibility** (`card_visibility()` — toggles `Organization.show_*` flags off a `cards` list, no per-card branching needed). Roles: `Admin`, `District Administrator`, `School Administrator`, `Teacher`, `Staff` (seeded in `installation/seed_data.py` — see Role-Based Site Access below for what each can see)
- **Global session filters** — `/set_school_year`, `/set_site_filter`, `/set_snap_date`, `/set_status_filter` (store to session, redirect back)
- **Context processor** — injects `active_schoolyr`, `active_site_filter`, `active_snap_date`, `active_status_filter`, `global_sites`, `global_school_years` into every template
- **Students** — list (paginated, multi-filter), detail (`student_details.html` — tabbed: Courses, Absences, Incidents, Interventions, Grades, Graduation, Parents, Other), edit, export CSV (`/students/export/csv`)
- **Demographics dashboard** — `/demographics` (charts + tables)
- **SWD dashboard** — `/swd`
- **English Learner Progress dashboard** — `/el-progress` — language status (EL/RFEP/IFEP/EO/TBD) counts, reclassification rate, EL-narrowed chronic-absence/F-grade signals, by-site breakdown
- **Absences** — `/absences/dashboard`, `/absences` (list)
- **Discipline dashboard** — `/discipline`
- **Incidents** — `/incidents` (list)
- **Interventions (MTSS/RTI)** — `/interventions` (list, filterable by tier/category/status), `/interventions/add/<student_id>`, `/interventions/edit/<id>`, `/interventions/delete/<id>` — always created in the context of a specific student (no bare "add" page; student_id comes from the URL, not a form field)
- **Early Warning System** — `/early-warning` — composite 0–100 risk score (see below), not just a flag count
- **Graduation Status dashboard** — `/graduation-status` — HS (grades 9–12) credit-completion vs. requirement, reads from the `StudentSubjectCredits` cache table (see Models). Status (Graduated/On Track/Behind/Credit Deficient) is driven by whichever subject area is furthest behind its own grade-paced target, not a blanket total-credits check — see `_grad_classify()`/`_grad_expected_fraction()` in Key Conventions.
- **Graduation Settings** — `/graduation-settings` (+ add/edit/delete) — admin CRUD for `GraduationRequirement` subject-area rows
- **Equity Gaps dashboard** — `/equity-gaps` — chronic-absenteeism and suspension rate gaps for key student subgroups (SWD, EL, FRM, foster, homeless) against the district baseline, computed by `_equity_gap_rows()`
- **Student Grades list** — `/student-grades` — flat filterable grade-record listing
- **Teachers / Courses / Parents** — list + detail + edit
- **CALPADS Compliance** — `/calpads` (10 data quality checks in 3 groups)
- **Enrollment sub-pages** — `/enrollment`, `/enrollment/k6`, `/enrollment/ms`, `/enrollment/hs`
- **Bulk Upload** — `/bulk-data-upload` (manual CSV + FTP scheduled import)

### Models (`application/models.py`)

Key models and their notable fields:

| Model | Notes |
|---|---|
| `Student` | `status` is a computed `@property` from `enter_date`/`exit_date` — there is no `status` column in DB. Unique constraint is on `(student_id, schoolyr)`, **not** `student_id` alone — the same student can have one record per school year. `english_status` codes (`EO`/`IFEP`/`EL`/`RFEP`/`TBD`) are defined once in `forms.py` `_ENGLISH_STATUS_CHOICES` — no time-of-reclassification field exists. |
| `User` | Email stored encrypted (`cryptography.fernet`); password hashed with scrypt. `site_id` is the required "primary" site; `sites` is a `user_site` many-to-many for *extra* site assignments (e.g. a School Administrator covering several campuses) — see Role-Based Site Access below. `is_admin`/`is_district_admin`/`is_school_admin`/`is_tech_role`/`has_all_site_access` are all computed from `role.role_name` (never `role_id`, and never hardcode a role's numeric id — see Key Conventions). `is_locked` reflects `locked_until`/`failed_login_attempts` (set by the login-lockout logic; cleared by `unlock_user()`). |
| `AuditLog` | Records who exported/accessed bulk student PII (currently: `/students/export/csv`) — `user_id`, `action`, `detail` (filters used), `record_count`, `ip_address`, `created_at`. Exists for FERPA accountability (who accessed/disclosed a student's education record), not general app logging — don't repurpose it for unrelated events. |
| `Organization` | Stores SMTP, FTP config (encrypted), academic calendar (`current_school_year`, `first_school_day`, `last_school_day`), `show_*` dashboard-card-visibility booleans (config overrides `app.config` at startup), and `grad_auto_calculate_credits` (when `True`, the Graduation Status total-credits-required figure is summed live from `GraduationRequirement` rows instead of the fixed `grad_credits_required` fallback) |
| `Absence` | Linked to student via `ssid` string (not FK), site via `site_id` FK. No `abs_abbr` column. Indexed on `ssid`, `(school_yr, site_id)`, and `(school_yr, ssid)` — the table is 270K+ rows district-wide and every dashboard query filters by `school_yr` then groups by `ssid` or `site_id`, so these were a real perf fix, not routine. |
| `Incident` | Linked to student via `sisid` string (not FK); `site` is stored as the site acronym string |
| `Grade` | One row per student/course/term grade record (from `grades.csv`). `grades_stuid` matches `Student.student_id` (string, not FK) — the same student can have many rows across years. |
| `GraduationRequirement` | Admin-configured subject-area credit requirements (e.g. "English" needs 40 credits). `department_list`/`keyword_list`/`exclude_keyword_list` are `@cached_property` (not `@property`) — they're read in a hot loop matching courses to subjects, so re-parsing the comma string on every access was a measured perf issue. `start_grade`/`end_grade` (e.g. Algebra I is `'9'`–`'9'`, Social Science is `'10'`–`'12'`) control how much of `credits_required` is "expected by now" per grade level — a freshman isn't dinged for not yet touching a 12th-grade-only subject. Exactly one row should have `is_catch_all=True`; rows are matched in `sort_order` order, so a specific row (e.g. Algebra I) must sort before the broader row it's carved out of (e.g. Mathematics). |
| `StudentSubjectCredits` | **Cache table**, not source of truth — pre-summed completed credits per `(student_id, subject_name)`. Exists because re-summing the raw `Grade` table (hundreds of thousands of rows district-wide) on every Graduation Status page view took 13+ seconds. Rebuilt by `_recompute_grad_subject_credits()` in `routes.py` — call it after any `grades.csv`/`courses.csv`/`master_schedule.csv` upload or `GraduationRequirement` CRUD, since course department/name changes affect subject classification too. Uses sentinel `'Unclassified'` instead of `NULL` for unmatched courses (MySQL treats `NULL != NULL` under a unique constraint). |
| `Intervention` | MTSS/RTI support record (`tier`: Tier 1/2/3, `category`: Attendance/Behavior/Academic). FK to `Student.id` (not a string ID like Absence/Incident) since it's created via app forms, not CSV import. |
| `Site` | Has `site_name`, `site_acronyms`, `site_cds`, `site_city`, `site_state`, `site_zip`, and principal contact fields (`principal_first_name`, `principal_last_name`, `principal_email`, `principal_phone`) |

### Global Session Filters

The context processor reads these four session keys and injects them into every template:
- `active_schoolyr` — school year string (e.g. `"2025-2026"`)
- `active_site_filter` — site ID as string
- `active_snap_date` — ISO date string for enrollment-as-of queries
- `active_status_filter` — `"active"` | `"inactive"` | `"all"`

Routes that support site filtering from the URL (e.g. dashboard table links) check `request.args.get('site_filter')` first, then fall back to session.

### Role-Based Site Access

Only `Admin`/`District Administrator` (`User.has_all_site_access`) may view "all sites" (a blank filter) or a site outside their own assignment. Every other role — `School Administrator`, `Teacher`, `Staff` — is restricted to `User.allowed_site_ids` (their primary `site_id` plus any extra sites in `User.sites`; a School Administrator is the one role routinely assigned more than one). This is enforced at several layers, all in `routes.py`, and a new route/query touching `site_id` should go through one of these rather than inventing a new check:

- **`set_session_defaults()`** (a `before_request` hook) clamps `session['active_site_filter']` to an allowed value on *every* request — this is what every dashboard route's `session.get('active_site_filter', '')` read ultimately relies on, with no per-route code needed.
- **`_clamp_site_filter(site_filter)`** — for the handful of list routes that read `site_filter` straight from a URL param instead of session (`/students`, `/teachers`, `/courses`; `/students/export/csv` relies on the session value, already clamped by the hook above).
- **`require_site_access(site_id)`** — 403s detail pages (student/teacher/course/parent) that look up a record by numeric ID with no other scoping.
- **`/incidents`** is a special case: `Incident.site` stores the site **acronym** string, not the numeric `site_id` every other table uses, so it clamps against `{Site.site_acronyms for site in allowed_site_ids}` instead of calling `_clamp_site_filter()`.
- **`/set_site_filter`** rejects a restricted user's attempt to select a disallowed site at the source, so the session never even briefly holds it.

Templates mirror this: the nav bar's global Site picker and the local "Filter By Site" dropdowns (Students/Incidents/Teachers/Courses) render one of three ways — full district picker (`has_all_site_access`), a picker scoped to just `current_user.sites` (multi-site users), or a fixed read-only site-name label (single-site users) — so a restricted user is never shown a control that would silently do nothing.

`/users` (system/account administration) is deliberately **not** part of this — it's gated separately (`is_admin()`/`is_tech_role()`) and its own site filter is just a local list-narrowing control, not exposure of student data.

### Student Subgroup Filtering

`/students` supports multi-select subgroup filtering via repeated `?subgroup=` URL params (`getlist`). The route applies **AND** logic across all selected subgroups. Supported values: `homeless`, `frm`, `swd`, `foster`, `migrant`, `sed504`, `no_ssid`.

English status and gender use single-value URL params (`english_status`, `gender`).

### Templates

- `application/templates/base.html` — main layout; includes `includes/nav.html` and `includes/footer.html`. Flash messages render in `#alert-container` as `.alert.border-radius-lg` (distinguishes them from org-wide `.warning-message-box` notification banners, which share the `.alert` class but not `.border-radius-lg`).
- `application/templates/includes/nav.html` — sidebar nav + top navbar with global filter bar + mobile menu (kept in sync manually — not every desktop nav-item has a mobile-menu/breadcrumb counterpart, e.g. Incidents/Interventions don't)
- `application/templates/includes/footer.html` — loads Bootstrap JS **after** `{% block content %}` in document order, so any page script that calls `bootstrap.*` synchronously at top level (not inside a later event callback) must be wrapped in a `DOMContentLoaded` listener or it'll throw `bootstrap is undefined`
- `application/templates/dashboard/` — analytics dashboards (demographics, swd, el_progress, discipline, absenteeism, graduation, enrollment_*, calpads)
- `application/templates/early_warning.html`, `interventions.html`, `add_intervention.html`, `edit_intervention.html` — MTSS tracking pages
- Shared delete-confirmation modal (`#deleteConfirmModal`, defined once in `base.html`) — triggered via `data-bs-toggle="modal" data-bs-target="#deleteConfirmModal"` + `data-confirm-message="..."` + `data-form-id="..."` on the delete button; the actual `<form>` (with its own `csrf_token` hidden input) lives elsewhere on the page and gets `.submit()`-ed by `footer.html`'s modal controller script. Don't build one-off delete modals — use this pattern.
- Chart rendering uses Chart.js loaded from `static/js/plugins/chartjs.min.js`
- Print/PDF export uses a `printDashboard()` JS function that swaps canvas elements for images and applies a zoom factor

### CSS / Print

- `application/static/css/style.css` is the site-wide design system: CSS custom properties on `:root` for color (`--bs-main-color-primary` is the fixed brand navy — don't reintroduce the old pink/gradient template defaults), spacing (`--space-1`…`--space-8`), radius, and shadow scales. **No gradients** — every `bg-gradient-*`/`.btn-*` fill is a flat color; if you add a new button/badge variant, follow that pattern rather than `linear-gradient(...)`. Interactive element borders (inputs, selects, buttons) must use `--input-color-border` (`#75808F`, ~4:1 contrast), **not** the plain `--color-border` (`#E3E7EE`, ~1.2:1) — the latter is for decorative dividers only and fails WCAG 1.4.11 as a control boundary. The shared page-header pattern (`.card-header.mt-n4 > .bg-gradient-main.border-radius-lg` or `.bg-gradient-main.custom-title-card`, used on ~45 pages) is styled once at the CSS layer — don't add page-specific header CSS, the existing selectors already cascade everywhere.
- `application/static/css/dashboards.css` contains shared dashboard styles including `.demo-kpi`, `.chart-card`, `.chart-wrap` and `@media print` rules for all dashboards.
- Filled buttons like `.btn:not([class*=btn-outline-])` get `color:#fff` forced by a global rule — a new light-background button variant needs to be compounded with `.btn` (e.g. `.btn.my-variant`, not `.btn-variant` alone) to out-specificity that rule, or its text silently renders white-on-white. `.btn-light`, `.btn-white`, and `.reset-button-box` already do this.
- The sidebar (`#sidenav-main` in `nav.html`) fills with brand navy (`.bg-gradient-main`), not white — a new category heading must use the `.navbar-heading` class (white, 600 weight), **not** `text-dark`/`text-xxs` utilities, which assume a light background and render near-invisible on navy. `application/static/img/` has two logo variants: `logo.png` (navy mark, for light backgrounds) and `logo-dark.png` (white mark, despite the name — it's the one used ON dark backgrounds like the sidebar).

---

## Bulk CSV Upload

All CSV imports go through `bulk_upload_users()` in `routes.py`. Files are detected by filename and processed in dependency order:

| Order | Filename | Processor | Required columns |
|---|---|---|---|
| 0 | `sites.csv` / `site.csv` | `_process_sites_rows` | `site_name`, `site_acronyms`, `site_cds`, `site_code`, `site_address`, `site_type` |
| 1 | `staff.csv` | `_process_staff_rows` | `site_id`, `employee_id`, `first_name`, `last_name` |
| 2 | `demographics.csv` | `_process_student_rows` | `stu_id`, `site_id`, `grade`, `schoolyr` |
| 3 | `absences.csv` | `_process_absence_rows` | `stu_id`, `site_id`, `abs_date`, `schoolyr` |
| 3 | `behavioral_incidents.csv` | `_process_incident_rows` | `stu_id`, `site_id`, `incident_id`, `incident_date`, `schoolyr` |
| 4 | `courses.csv` / `master_schedule.csv` | `_process_courses_rows` / `_process_master_schedule_rows` | varies |
| 5 | `students_schedule.csv` / `parents.csv` / `grades.csv` | `_process_student_schedule_rows` / `_process_parents_rows` / `_process_grades_rows` | varies |
| 6 | `users.csv` | inline in route | `first_name`, `last_name`, `email`, `role_id`, `site_name`, `rm_num` |

**`demographics.csv` notes:**
- `site_id` matches `Site.site_cds` with all non-digit separators stripped (so `67_67399_5136971` and `67-67399-5136971` both match).
- Upsert key is `(stu_id, schoolyr)` — the same student ID can appear in multiple school years as separate records.
- `schoolyr` defaults to `Organization.current_school_year` if omitted.
- `race` must be a valid CALPADS code (`100`–`900`); invalid values are stored as `None`.
- `gradyr` handles date-formatted values (e.g. `7/25/05`) by extracting the year (`2005`).
- Encoding: tries `utf-8-sig` first, falls back to `latin-1`.

**`absences.csv` notes:**
- `stu_id` is resolved to the student's `ssid` via `(stu_id, schoolyr)` lookup; falls back to storing `stu_id` if no SSID exists.
- Deduplicates by `(site_id, ssid, abs_date, bell_period)` — re-uploading the same file is safe.

**`behavioral_incidents.csv` notes:**
- Same `site_id`/`stu_id` resolution as `absences.csv`. Dedupes by `incident_id`.
- `minor_incident`/`major_incident` are numeric flag columns (not text) — a non-zero value sets `Incident.minor`/`Incident.major` to a fixed label string; the CSV has no free-text infraction description column.

**`grades.csv` notes:**
- Upsert key is `(stu_id, section_id, term_code, course_yr)`.
- `course_yr` is a single 4-digit **ending** calendar year (e.g. `2025`), converted to the app's `"YYYY-YYYY"` school-year format (`2024-2025`) via `_parse_course_schoolyr()`.
- `term_code`'s trailing letter (`S`/`Q`/`T`/`M`/`Y`) sets `Grade.grades_type` (Semester/Quarter/Trimester/Marking Period/Full Year) via `_GRADE_TERM_TYPE`.
- After processing, `bulk_upload_users()` sets a `grad_recompute_needed` flag and calls `_recompute_grad_subject_credits()` **once** after the whole upload batch finishes (not once per file) — see `StudentSubjectCredits` in Models.

Download templates live in `application/static/download/`.

---

## Key Conventions

- **`site_filter` parameter**: In the students route, URL param `site_filter` overrides session. In all other routes it comes from session only. Regardless of source, the effective value is always restricted per-user — see Role-Based Site Access above; don't read `session['active_site_filter']` or `request.args['site_filter']` directly in a new route without clamping it.
- **Role checks compare by name, never by `role_id`**: `is_admin()`/`is_tech_role()` in `routes.py` delegate to `User.is_admin`/`User.is_tech_role` (compare `role.role_name`, e.g. `"admin"`), not to a hardcoded `role_id` integer. `installation/seed_data.py` happens to seed `Admin` as id `1`, but nothing in the app should assume that — a reseed/reorder that changes ids would silently swap who has access with a numeric check, with no error. This already broke once (a role rename desynced a stale `role_id in [2, 3]` check from the name-based property it duplicated) — always add new role checks as a `User` property keyed on `role_name`.
- **Ethnicity codes**: Stored as 3-digit strings (`'500'` = Hispanic/Latino, `'600'` = African American, etc.). The `ethnicity_table_data` variable is always a list of `(code, label, count)` tuples.
- **Add pages removed**: `add_student`, `add_teacher`, `add_course`, `add_parent` routes redirect to their list pages — the templates were intentionally deleted. `Intervention` follows a similar contextual-add pattern deliberately: there's no bare "add intervention" page, only `/interventions/add/<student_id>` reached from Early Warning or a student's detail page.
- **`student.status`**: Never filter with `Student.status == 'Active'` in SQL — it's a Python property. Use `enter_date`/`exit_date` conditions instead.
- **Student records are per school year**: `Student.student_id` is not globally unique. The composite unique constraint is `(student_id, schoolyr)`. Always scope student queries by `active_schoolyr` session filter.
- **Upload size limit**: `MAX_CONTENT_LENGTH = 100 MB` (set in `config.py`) to accommodate large absence exports.
- **`StudentSubjectCredits` is a cache, not source of truth**: if you add a new way to change `Grade`, `Course` department/name, or `GraduationRequirement` data, call `_recompute_grad_subject_credits()` afterward or the Graduation Status dashboard will silently show stale numbers. It's already wired into the grades/courses/master_schedule upload branches and the Graduation Settings CRUD routes — check there first before assuming a new call site is needed.
- **Early Warning risk score**: a weighted 0–100 composite (Attendance 40% + Academic 40%/F-grade count + Behavior 20%/incident count), each component linearly scaled against `threshold * 1.5`, not a count of tripped boolean flags. Buckets: High ≥67, Medium 34–66, On Track <34. The three boolean flags (`att_flag`/`beh_flag`/`grd_flag`) still exist for the per-column icons in the table but no longer drive the risk bucket.
- **Graduation Status classification**: `_grad_classify()` finds the subject area furthest behind its own grade-paced target (`_grad_expected_fraction()`, driven by each `GraduationRequirement.start_grade`/`end_grade`) and buckets on that, not on whether total credits earned meet total credits required. A student can't be "On Track" by stacking Electives while a required subject like English or Algebra I is behind.
- **FTP sync treats every file as optional**: `ftp_bulk_upload_users()` tries `sites.csv`, `demographics.csv`, `absences.csv`, `behavioral_incidents.csv`, `staff.csv`, `courses.csv`, `master_schedule.csv`, `students_schedule.csv`, `parents.csv`, and `users.csv` in turn; a missing file (`ftplib.error_perm`, e.g. FTP 550) is caught and that file is skipped, not treated as a fatal error for the whole sync. If you add a new file to this list, wrap its `retrbinary` call the same way or one missing file will abort every other file's import. `grades.csv` is notably **not** in this list — the FTP sync has no grades support at all yet, only the manual multi-file upload does.
- **Bootstrap JS loads after page content**: `footer.html` (with `bootstrap.min.js`) is included after `{% block content %}` in `base.html`'s document order, so a page's own inline `<script>` runs *before* Bootstrap is defined. Any code that calls `bootstrap.*` immediately on page load (not inside a click/submit handler, which naturally runs later) must be wrapped in `document.addEventListener('DOMContentLoaded', ...)`.
