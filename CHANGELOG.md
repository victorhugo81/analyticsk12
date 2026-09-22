# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2026.2.2] - 2026-09-22

### Security
- Encrypted additional PII fields at rest (`cryptography.fernet`, same scheme as the existing `User.email`): `Parent.email`/`phone`, `Student.email`/`ssid`, `Teacher.email`, `Site.principal_email`/`principal_phone`. `Student.ssid` (and `Absence.ssid`, the only link between those two tables since `Absence` has no FK to `Student`) additionally get a deterministic HMAC blind-index column (`ssid_hash`) so every dashboard that joins/groups/filters on SSID (Absences, Early Warning, EL Progress, Equity Gaps, Attendance Rates, CALPADS, Discipline) keeps working without ever decrypting at the SQL level. `Incident.sisid` is deliberately left unencrypted — it's a denormalized join-key copy, not a system of record for the SSID.
- Removed partial-SSID text search from the Absences list and partial-email search from the Parents list — ciphertext can't be matched with SQL `LIKE`, matching the limitation `/users` already had searching by name only (not email).
- Moved the CALPADS "SSID format" compliance check (must be 10 digits) from a SQL `REGEXP` filter to a Python-side check, since that also can't run against an encrypted column.
- Fixed a regression where `login_manager.login_message` was no longer suppressed, causing the default "Please log in to access this page." flash message to reappear on the login screen.

## [2026.2.1] - 2026-09-21

### Fixed
- Global session filters (School Year, Site, Snap Date, Status) could appear to silently reset on every request when the dev server was started with `flask --app main.py run` — that invocation defaults to `ProductionConfig`, which marks the session cookie `Secure`, so browsers discard it on plain `http://localhost`. Documented the corrected dev run command (`flask --app "main:create_app('development')" run`) in CLAUDE.md.
- Student Details page ignored the global School Year filter — its URL is pinned to one specific year's database row (`Student` is unique per `(student_id, schoolyr)`), so changing the filter while viewing a student reloaded the exact same row. It now follows the filter to that same student's record for the selected year when one exists.
- Parent Details page listed a linked child once per school year they had a record in, instead of once, since bulk parent-student linking is created per year's `Student` row. "Linked Students" now shows each child exactly once, preferring their record for the active School Year filter.
- Graduation Status dashboard showed a flat `0 / 220` credits for every student because no `GraduationRequirement` subject-area rows existed in the database. Seeded a standard 8-row/220-credit default set (English, Algebra I, Mathematics, Science, Social Science, Physical Education, Visual/Performing Arts & World Language, Electives) and added the same seeding to `installation/seed_academic_data.py` so fresh installs aren't left with an empty requirements table.
- Cleaned up a residual 233-row `course_grade` inconsistency in `sample_files/2024-25/grades.csv` (stale grade-level tags left over from an earlier student grade-progression correction across the 3-year sample dataset).

## [2026.2.0] - 2026-09-19

### Added
- Mobile/tablet navigation now uses the same sidebar as desktop instead of a separate, incomplete mobile menu (the old one was missing Incidents, Interventions, Absences, and Student Grades links). The sidebar slides in from off-screen via the existing hamburger toggle.
- Hamburger menu icon morphs into an X while the mobile sidebar is open.
- Global filters (School Year, Site, Students, As of Date) are now a collapsible accordion on mobile/tablet, collapsed by default; still always expanded on desktop.
- Centered logo above the filters on mobile/tablet, since the sidebar's own logo is hidden below the desktop breakpoint there.
- Visible borders added to all buttons and input/select fields, with border colors meeting WCAG 1.4.11 non-text contrast (3:1 minimum).

### Changed
- Sidebar background changed to the brand navy color instead of white.
- Sidebar category headings ("Dashboards", "Academic", "Settings") switched to a dedicated `.navbar-heading` style so they're visible against the navy background.
- About modal redesigned with a circular icon badge, a version pill, and a separate copyright line; header title is visually hidden (icon-only close button), matching the reference design.
- Filters toggle and mobile menu toggle moved into a single row with matching alignment; filters toggle made smaller.
- Darkened the warning/accent color so white text on it meets the 4.5:1 contrast minimum (previously 3.64:1).
- Removed a stray `mx-3` class from the shared page header across all pages (had no visual effect; the layout already overrides it).

### Fixed
- "Add Subject Area" and other longer button labels no longer get clipped — the button now sizes to its content instead of a fixed width.
- Cancel button ("reset-button-box") no longer renders white text on a white background at rest.
- About modal's icon image no longer renders oversized inside its circular badge.

## [2026.1.2] - 2026-08-16
Added
About modal, opened by clicking the footer copyright notice, showing the app name, description, version, and copyright year.
Changed
Sidebar logo is now centered.
About modal's version number is now read from this changelog at runtime instead of being hardcoded in the template.

## [2026.1.1] - 2026-04-26

### Changed
- UI redesign: migrated stylesheet to a CSS custom-property design system (color palette, shadow scale, border-radius scale, spacing scale, transition tokens).
- Switched body font to Inter via Google Fonts for a modern, neutral appearance.
- Login page: increased "Sign In" heading size and weight; adjusted login panel layout to `flex-direction: column` with `align-items: stretch` for better vertical alignment.

## [2026.1.0] - 2026-04-12

### Added
- Production startup guards that raise `RuntimeError` on launch if `SECRET_KEY` or `RATELIMIT_STORAGE_URI` are misconfigured, preventing silent security issues.
- `ProxyFix` WSGI middleware so rate limiting and logging see the real client IP when the app runs behind Nginx or Apache.
- `_is_mail_configured()` guard in email utilities — all outbound email functions now silently skip sending if no SMTP credentials are saved in the database, preventing startup errors on fresh installs.
- `SQLALCHEMY_POOL_RECYCLE = 3600` to recycle MySQL connections before the server-side idle timeout (~8 h).
- `MAX_CONTENT_LENGTH = 16 MB` cap on request bodies to prevent denial-of-service via large file uploads.
- `PERMANENT_SESSION_LIFETIME = 8 hours` so sessions expire after inactivity.
- `testing` config entry in the config dictionary for use by the test suite.

### Changed
- Bulk data upload route renamed from `/upload-users` to `/bulk-data-upload` and page title updated to "Bulk Data Upload".
- Bulk upload log view simplified to a single unified log (previously split into user and site logs).
- All `Model.query.get()` calls replaced with `db.session.get()` (SQLAlchemy 2.0 style) throughout `main.py`.
- All `datetime.utcnow` references in models replaced with a timezone-aware `_utcnow()` helper to resolve deprecation warnings.
- FTP error handling: fixed variable shadowing bug in `error_perm` handler where `msg_lower` was assigned but the original `str(e)` was searched instead.
- Removed redundant `page_names` dict in `edit_ticket` — page name is now set directly.
- Production config guards moved from `ProductionConfig.__init__` into `create_app()` so they apply at runtime, not at import time.

### Fixed
- Suppressed Flask-Login's default "Please log in to access this page." flash message on login redirects by setting `login_manager.login_message = ""`.

### Dependencies
- Updated: `click` 8.3.1 → 8.3.2, `cryptography` 46.0.5 → 46.0.7, `flask` 3.1.2 → 3.1.3, `greenlet` 3.3.1 → 3.4.0, `python-dotenv` 1.2.1 → 1.2.2, `sqlalchemy` 2.0.46 → 2.0.49, `tzdata` 2025.3 → 2026.1, `werkzeug` 3.1.5 → 3.1.8, `wrapt` 2.1.1 → 2.1.2.

## [2026.0.0] - 2025-05-18

### Added
- First production release.
- User authentication with login/logout and temporary password flow.
- Models for users, roles, sites, tickets, notifications, and organizations.
- CRUD routes and forms for all models.
- Role-based access control (Admin, Specialist, Technician).
- Account lockout after repeated failed login attempts.
- Ticket system with attachments, comments, escalation, and email notifications.
- Bulk user and site import via CSV upload and FTP.
- FTP scheduling with configurable cron-style triggers.
- Email notification system for ticket events (created, updated, escalated, commented).
- Organization-level SMTP configuration stored in the database.
- Rate limiting on authentication endpoints.
- Security headers (CSP, X-Frame-Options, HSTS, etc.) applied to all responses.
- Base HTML templates and includes (nav, footer).
- Static files structure: CSS, JS, images, uploads.


## [2026.0.0] - 2025-04-27

### Added
 - update mobile resolution for dashboard
---