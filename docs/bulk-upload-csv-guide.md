---
title: "Bulk CSV Import Guide"
description: "Column reference, formatting rules, and templates for every CSV file AnalyticsK12 accepts in Organization → Bulk Upload."
---

# Bulk CSV Import Guide

AnalyticsK12 loads district data — sites, staff, students, attendance, discipline, courses, schedules, grades, parents, and system users — through CSV files uploaded on the **Organization → Bulk Upload** page. This guide documents every file the importer accepts: what columns it needs, what values are valid, and how records are matched and updated.

## How the import works

- **Admin only.** Bulk upload is restricted to Admin accounts.
- **Upload several files at once.** Drop multiple CSVs in one go — the importer sorts and processes them in dependency order automatically, regardless of the order you dropped them in:

  1. `sites.csv` (or `site.csv`)
  2. `staff.csv`
  3. `demographics.csv`
  4. `absences.csv` and `behavioral_incidents.csv`
  5. `courses.csv` and `master_schedule.csv`
  6. `grades.csv`, `students_schedule.csv`, and `parents.csv`
  7. `users.csv`

  This order matters: sites must exist before staff/students that reference them, students must exist before their absences/grades/schedules, and courses must exist before students can be scheduled into them.
- **Filenames are matched exactly** (case-insensitive) — `sites.csv`, `demographics.csv`, `absences.csv`, `behavioral_incidents.csv`, `staff.csv`, `courses.csv`, `master_schedule.csv`, `students_schedule.csv`, `parents.csv`, `grades.csv`, `users.csv`. A file with any other name is rejected with an error.
- **Encoding:** UTF-8 (with or without a BOM) is tried first; files that aren't valid UTF-8 fall back to Latin-1 (Windows-1252-compatible). Excel's "CSV UTF-8" and "CSV" export formats both work.
- **Upsert, not append.** Every file updates a matching existing record if one is found, and creates a new one otherwise — see each file's "Matched by" note below for what counts as a match. Re-uploading the same file is safe.
- **A missing value in a required column, on any row, aborts that entire file** with an error message listing the problem rows (up to a shown limit) — no partial file is committed. So does a **site/course/staff reference that can't be found** (e.g. a CDS code not in the system, or a `master_schedule.csv` `staff_id` that doesn't match any `employee_id`). This applies to every file type, including `absences.csv` and `behavioral_incidents.csv`.
- Within `absences.csv` and `behavioral_incidents.csv` specifically, a row that has all its required columns filled in but an **unparseable or logically invalid date**, or turns out to be a **duplicate**, is silently skipped and counted rather than aborting the file — see those sections below.
- **Every upload is logged** (added/updated/skipped counts, uploader, timestamp, and any error) and visible in the Upload Log on the same page.
- Column-reference templates matching every table below are downloadable directly from the Bulk Upload page.

---

## Quick reference

| File | Required columns | Matched by (upsert key) |
|---|---|---|
| `sites.csv` | `site_name`, `site_acronyms`, `site_cds`, `site_code`, `site_address`, `site_type` | `site_name` |
| `staff.csv` | `site_id`, `employee_id`, `first_name`, `last_name` | `employee_id` |
| `demographics.csv` | `stu_id`, `site_id`, `grade`, `schoolyr` | `stu_id` + `schoolyr` |
| `absences.csv` | `stu_id`, `site_id`, `abs_date`, `schoolyr` | not upserted — inserts only, deduplicated |
| `behavioral_incidents.csv` | `stu_id`, `site_id`, `incident_id`, `incident_date`, `schoolyr` | `incident_id` (deduplicated, not upserted) |
| `courses.csv` | `site_id`, `course_name`, `section_id` | `site_id` + `section_id` |
| `master_schedule.csv` | `site_id`, `section_id`, `course_name` | `site_id` + `section_id` |
| `students_schedule.csv` | `stu_id`, `section_id`, `schoolyr` | `stu_id` + `section_id`; see note below |
| `parents.csv` | `first_name`, `last_name`, `relationship`, `stu_id` | `email` (if present), else always inserted |
| `grades.csv` | `stu_id`, `site_id`, `section_id`, `term_code`, `course_yr` | `stu_id` + `section_id` + `term_code` + `course_yr` |
| `users.csv` | `first_name`, `last_name`, `email`, `role_id`, `site_name`, `rm_num` | `email` |

**A note on `site_id` columns:** in every file except `sites.csv` itself, the `site_id` column is actually the school's **CDS code** (California-style), not a database ID. It's matched against each site's stored CDS code with all non-digit separators stripped, so `67-67399-5136971` and `67_67399_5136971` and `6767399 5136971` are all treated as the same site. The site must already exist (via `sites.csv` or the Sites admin page) before you can reference it here.

---

## sites.csv

| Column | Required | Notes |
|---|---|---|
| `site_id` | one of `site_id`/`site_cds` | The CDS code. If `site_cds` is blank, `site_id` is used as the CDS code instead — the two are interchangeable in this file only. |
| `site_acronyms` | Yes | Short code used elsewhere in the app (e.g. Incidents are tagged by acronym, not site ID). |
| `site_name` | Yes | The upsert key — a second row with the same `site_name` updates the existing site rather than creating a duplicate. |
| `site_address` | Yes | |
| `site_type` | Yes | Free text, e.g. `Elementary`, `Middle`, `High`, `K-8`, `District Office`. |
| `site_code` | Yes | |
| `sitecity` | No | |
| `sitestate` | No | Two-letter state code. |
| `sitezip` | No | |
| `prnfirstn` | No | Principal's first name. |
| `prnlastn` | No | Principal's last name. |
| `email` | No | Principal's email — stored encrypted at rest. |
| `phone` | No | Principal's phone — stored encrypted at rest. |

**Example**

```csv
site_id,site_acronyms,site_name,site_address,sitecity,sitestate,sitezip,prnfirstn,prnlastn,email,phone,site_type,site_code
67-67399-5136971,RHS,Roosevelt High School,400 Roosevelt Dr.,Springfield,CA,95000,Angela,Reyes,a.reyes@school.edu,555-100-2000,High,RHS004
```

---

## staff.csv

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `employee_id` | Yes | The upsert key. Must be unique per staff member. |
| `first_name` | Yes | |
| `middle_name` | No | |
| `last_name` | Yes | |
| `email` | No | Stored encrypted at rest. |

---

## demographics.csv

The core student enrollment file — one row per student **per school year**. The same `stu_id` can and should appear in multiple years' files (or repeated within one file across school years) as separate records.

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `stu_id` | Yes | District-local student ID. Combined with `schoolyr`, this is the upsert key — the same student can have one record per year. |
| `ssid` | No | Statewide Student ID (CALPADS). Stored encrypted at rest. |
| `first_name` | Yes | |
| `middle_name` | No | |
| `last_name` | Yes | |
| `email` | No | Student email — stored encrypted at rest. |
| `grade` | Yes | e.g. `TK`, `KN`, `1`–`12`. |
| `gender` | No | `M`, `F`, `X` (Non-Binary), or `U` (Unknown). |
| `birth_date` | No | `MM/DD/YYYY`, `MM/DD/YY`, or `YYYY-MM-DD`. |
| `gradyr` | No | Expected graduation year. Accepts a plain 4-digit year, or a date (the year is extracted), e.g. `7/25/05` → `2005`. |
| `race` | No | CALPADS ethnicity code: `100` (Native American/Alaska Native), `200` (Asian), `300` (Pacific Islander), `400` (Filipino), `500` (Hispanic/Latino), `600` (African American), `700` (White), `900` (Two or More Races). Any other value is dropped (stored as blank), not rejected. |
| `frmcode` | No | Free/Reduced Meal status: `1` = Free, `2` = Reduced, `3` = Paid, `0` or blank = none. |
| `english_status` | No | `EO` (English Only), `IFEP` (Initially Fluent English Proficient), `EL` (English Learner), `RFEP` (Reclassified Fluent English Proficient), or `TBD`. |
| `entry_date` | No | Same date formats as `birth_date`. |
| `exit_date` | No | Same date formats as `birth_date`. Leave blank for a currently-enrolled student. |
| `disability` | No | An IEP/504 disability code (e.g. `SLD`, `OHI`, `AU`), or `0`/blank for none. Whatever value you send is stored as-is (no validation against a fixed list). |
| `dwelling_type` | No | **Important:** any non-zero, non-blank value here marks the student as homeless and is stored generically — the specific housing sub-type is not preserved from this column. Use `0` or leave blank for "not homeless." |
| `migrant` | No | `Y` or `N` (case-insensitive). Anything other than `Y` is treated as `N`. |
| `foster` | No | `Y` or `N`, same rule as `migrant`. |
| `code_504` | No | `0` or blank = no 504 plan; any other value = has a 504 plan. |
| `schoolyr` | Yes* | `YYYY-YYYY`, e.g. `2025-2026`. *If omitted, defaults to the district's configured "Current School Year" (Organization settings) — only truly optional if that default is set. |

**Example**

```csv
site_id,stu_id,ssid,first_name,middle_name,last_name,email,grade,gender,birth_date,gradyr,race,frmcode,english_status,entry_date,exit_date,disability,dwelling_type,migrant,foster,code_504,schoolyr
67-67399-5136971,S1001,1000000001,Sofia,,Ramirez,,9,F,4/3/2010,2029,500,1,EO,8/12/2025,,,0,N,N,0,2025-2026
```

---

## absences.csv

Inserts attendance/absence records. **Not** upserted — re-uploading the same file is still safe because rows are deduplicated by `(site, student, date, period)`, but there's no "update an existing absence" behavior; a changed row in a re-upload is treated as a new, different record unless the date/period also match.

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `stu_id` | Yes | Resolved to the student's SSID via `(stu_id, schoolyr)`; if the student has no SSID on file, `stu_id` itself is used as the link value instead. |
| `abs_date` | Yes | Same date formats as demographics. Rows with an unparseable or missing date are skipped. |
| `schoolyr` | Yes | `YYYY-YYYY`. |
| `period` | No | Bell/period identifier, e.g. `1st`. Part of the dedup key — two rows for the same student/date but different periods are both kept. |
| `abs_desc` | No | Free-text absence type/reason (e.g. `Unexcused`, `Excused`, `Medical`). Used to power the Absences list filter and dashboard breakdowns. |
| `grade` | No | Student's grade at the time of the absence. |

---

## behavioral_incidents.csv

Inserts discipline incident records, deduplicated by `incident_id` — an `incident_id` already on file is skipped, not updated.

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `stu_id` | Yes | Same SSID resolution as `absences.csv`. |
| `incident_id` | Yes | Unique ID from your SIS. This is the dedup key. |
| `incident_date` | Yes | Same date formats as demographics. Rows with an unparseable or missing date are skipped. |
| `schoolyr` | Yes | `YYYY-YYYY`. |
| `incident_time` | No | Free text, e.g. `09:30`. |
| `suspension_days` | No | A number (decimals allowed, e.g. `1.5`). Non-numeric values are ignored. |
| `minor_incident` | No | A **numeric flag**, not free text — any non-zero value marks this row as a minor incident. There's no column for a free-text infraction description. |
| `major_incident` | No | Same numeric-flag rule as `minor_incident`, for major incidents. A row can be flagged as both. |

---

## courses.csv

Creates or updates course **sections**. A section is unique per `(site_id, section_id)`.

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `course_name` | Yes | |
| `section_id` | Yes | Combined with the site, this is the upsert key. |
| `course_id` | No | Your SIS's course catalog ID (stored separately from `section_id`). |
| `college_dept` | No | |
| `deptartment` | No | **Note the spelling** — this is the actual column name the importer reads. Feeds the Graduation Requirements subject-matching logic (see Graduation Settings). |
| `credits` | No | Whole number. |
| `max_students` | No | Whole number. |
| `grade_level` | No | e.g. `9`. If left blank on a re-upload of an existing section, the previous value is kept rather than cleared. |

---

## master_schedule.csv

Also creates/updates sections (same `(site_id, section_id)` upsert key as `courses.csv`) but assigns the teacher and period — use this instead of/alongside `courses.csv` when your SIS separates "course catalog" data from "who teaches which section, when."

| Column | Required | Notes |
|---|---|---|
| `site_id` | Yes | CDS code — see note above. |
| `section_id` | Yes | |
| `course_name` | Yes | |
| `period` | No | e.g. `1st`, `2nd`. |
| `term_code` | No | e.g. `1S`, `FY`. |
| `staff_id` | No | Must match an existing `staff.csv` `employee_id` — if it doesn't, the whole file is rejected with an error naming the missing ID(s). |
| `grade_level` | No | Same "blank keeps previous value" behavior as `courses.csv`. |

---

## students_schedule.csv

Enrolls or drops students from course sections.

| Column | Required | Notes |
|---|---|---|
| `stu_id` | Yes | Matched to a student via `(stu_id, schoolyr)`. |
| `section_id` | Yes | |
| `schoolyr` | Yes | `YYYY-YYYY`. |
| `site_id` | No | CDS code. **Only needed if the section is hosted at a different site than the student's own demographics site** (e.g. a cyber/independent-study program) — a `section_id` isn't unique across the whole district, only within a site, so this disambiguates which site's section to enroll into. If left blank, the student's own site is assumed. |
| `start_date` | No | Same date formats as demographics. |
| `leave_date` | No | Leave blank to enroll/keep enrolled. Set a date to drop the student from that section — this doesn't delete the enrollment, it closes it, so course history remains visible on the student's record. |

---

## parents.csv

Adds or updates parent/guardian contacts and links them to one or more students. Rows are **not** upserted by student — the upsert key is `email` (if a row has no email, a new parent record is always created, even if the name matches an existing one).

| Column | Required | Notes |
|---|---|---|
| `first_name` | Yes | |
| `middle_name` | No | |
| `last_name` | Yes | |
| `relationship` | Yes | Free text, e.g. `Mother`, `Father`, `Guardian`. |
| `email` | No | Stored encrypted at rest. If present and it matches an existing parent's email, that parent record is updated (name/relationship/phone) instead of creating a duplicate. |
| `phone` | No | Stored encrypted at rest. |
| `stu_id` | Yes | Links this parent to the student. A row that doesn't match any known student is skipped, not an error. To link one parent to multiple children, repeat the same parent's info on multiple rows, one per `stu_id` — each row's SSID/child link is looked up across **all** school years on file for that `stu_id`, not just the currently active one. |

---

## grades.csv

Adds or updates a student's course grade record for a specific term. This is what feeds the Grades tab, Graduation Status dashboard, and Early Warning's academic-risk signal.

| Column | Required | Notes |
|---|---|---|
| `stu_id` | Yes | District-local student ID (not SSID). |
| `site_id` | Yes | CDS code — see note above. |
| `section_id` | Yes | Should match a `courses.csv`/`master_schedule.csv` section for the course name to display correctly, though it isn't strictly validated against one. |
| `term_code` | Yes | The **trailing letter** determines the term type shown in the app: `...S` = Semester, `...Q` = Quarter, `...T` = Trimester, `...M` = Marking Period, `...Y` = Full Year (e.g. `1S`, `2Q`, `FY`). |
| `course_grade` | No | The student's grade **level** at the time of the course (e.g. `9`), not the letter grade. |
| `mark` | No | The letter/numeric grade received, e.g. `A`, `B+`, `F`. |
| `credit_attempted` | No | Number. |
| `creadit_completed` | No | **Note the spelling** — this is the actual column name the importer reads. |
| `course_yr` | Yes | A single 4-digit **ending** calendar year, e.g. `2025` for the 2024–2025 school year (converted automatically). |

Re-uploading a row with the same `stu_id` + `section_id` + `term_code` + `course_yr` updates that existing grade record rather than creating a duplicate — safe to re-upload a corrected file.

---

## users.csv

Adds, updates, and **deactivates** AnalyticsK12 login accounts. This file behaves differently from the others: it's treated as the **full roster** for each upload — any existing Active user whose email isn't in the file gets automatically marked Inactive.

| Column | Required | Notes |
|---|---|---|
| `first_name` | Yes | |
| `middle_name` | No | |
| `last_name` | Yes | |
| `email` | Yes | The upsert key (matched case-insensitively). Stored encrypted at rest. |
| `role_id` | Yes | Numeric ID of an existing Role — check **Settings → Roles** for your district's exact IDs (a fresh install seeds `1`=Admin, `2`=District Administrator, `3`=School Administrator, `4`=Teacher, `5`=Staff, but don't assume these are fixed if roles have been renamed/reordered). |
| `site_name` | Yes | Must be an **exact, case-sensitive match** to an existing site's name (not a CDS code, unlike every other file). A row with no matching site aborts the whole import. |
| `rm_num` | Yes | Room number, or any short identifier your district uses — required but not otherwise validated. |
| `status` | No | `Active` or `Inactive`. Defaults to `Active` for a new user. |

A brand-new user is created with a random temporary password and `must_change_password` set, so they're forced to set their own password the first time they log in — the CSV never carries a real password.

---

## Downloadable templates

Column-reference template files matching every table above are available for download directly on the **Organization → Bulk Upload** page.
