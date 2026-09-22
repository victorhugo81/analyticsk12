from main import db  # Import db from main.py where it's initialized
from flask_login import UserMixin
from datetime import datetime, timezone
from functools import cached_property
from sqlalchemy import and_


def _utcnow():
    """Return current UTC time as a naive datetime (compatible with legacy DateTime columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    organization_name = db.Column(db.String(100), nullable=False)
    site_version = db.Column(db.String(100), nullable=False)
    organization_logo = db.Column(db.String(100), nullable=True)
    # Flask-Mail configuration
    mail_server = db.Column(db.String(255), nullable=True)
    mail_port = db.Column(db.Integer, nullable=True)
    mail_use_tls = db.Column(db.Boolean, default=False, nullable=True)
    mail_use_ssl = db.Column(db.Boolean, default=False, nullable=True)
    mail_username = db.Column(db.String(255), nullable=True)
    mail_password = db.Column(db.String(255), nullable=True)
    mail_default_sender = db.Column(db.String(255), nullable=True)
    # FTP configuration (host, username, password stored encrypted)
    ftp_host_enc = db.Column(db.String(512), nullable=True)
    ftp_port = db.Column(db.Integer, default=21, nullable=True)
    ftp_username_enc = db.Column(db.String(512), nullable=True)
    ftp_password_enc = db.Column(db.String(512), nullable=True)
    ftp_path = db.Column(db.String(512), nullable=True)
    ftp_use_tls = db.Column(db.Boolean, default=False, nullable=True)
    # FTP schedule
    ftp_schedule_enabled = db.Column(db.Boolean, default=False, nullable=True)
    ftp_schedule_hour    = db.Column(db.Integer, nullable=True)
    ftp_schedule_minute  = db.Column(db.Integer, default=0, nullable=True)
    ftp_schedule_days    = db.Column(db.String(50), default='*', nullable=True)  # '*' or 'mon,tue,...'
    ftp_last_run_at      = db.Column(db.DateTime, nullable=True)
    ftp_last_run_status  = db.Column(db.String(20), nullable=True)
    ftp_schedule_start_date = db.Column(db.Date, nullable=True)
    ftp_schedule_stop_date  = db.Column(db.Date, nullable=True)
    # Academic calendar
    current_school_year = db.Column(db.String(9),  nullable=True)   # e.g. 2024-2025
    first_school_day    = db.Column(db.Date,        nullable=True)
    last_school_day     = db.Column(db.Date,        nullable=True)
    # Dashboard card visibility
    show_demographics     = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_absenteeism      = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_discipline       = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_swd              = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_registration     = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_enrollment       = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_attendance_rates = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_early_warning    = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_calpads          = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_graduation       = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_el_progress      = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    show_equity_gaps      = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    # Credits required to graduate — used by the Graduation Status dashboard
    grad_credits_required = db.Column(db.Integer, default=220, nullable=True, server_default='220')
    # Manual fallback total for 'continuation' track sites (Site.grad_track). NULL falls back
    # to grad_credits_required — only needed if a district wants a different fixed total.
    grad_credits_required_continuation = db.Column(db.Integer, nullable=True)
    # When True, the Graduation Status dashboard sums GraduationRequirement.credits_required
    # instead of using the fixed grad_credits_required value.
    grad_auto_calculate_credits = db.Column(db.Boolean, default=True, nullable=False, server_default='1')


class Grade(db.Model):
    __tablename__ = 'grade'
    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grades_stuid      = db.Column(db.String(50),  nullable=False, index=True)
    grades_schoolid   = db.Column(db.String(100), nullable=True)
    grades_coursenum  = db.Column(db.String(50),  nullable=True)
    grades_teacherid  = db.Column(db.String(50),  nullable=True)
    grades_courseyr   = db.Column(db.String(20),  nullable=True)
    grades_term       = db.Column(db.String(20),  nullable=True)
    grades_grade      = db.Column(db.String(5),   nullable=True)
    grades_mark       = db.Column(db.Numeric(5, 2), nullable=True)
    grades_type       = db.Column(db.String(20),  nullable=True)
    grades_credatt    = db.Column(db.Numeric(5, 2), nullable=True)
    grades_credcomp   = db.Column(db.Numeric(5, 2), nullable=True)
    grades_currgrade  = db.Column(db.String(5),   nullable=True)


class GraduationRequirement(db.Model):
    """A subject-area credit requirement shown on a student's Graduation tab.

    `departments` / `name_keywords` / `name_exclude_keywords` are comma-separated
    lists used to bucket a Course into this subject area: the course's `department`
    must be one of `departments` (if set), its `course_name` must contain one of
    `name_keywords` (if set), and must NOT contain any of `name_exclude_keywords`.
    A course that matches no non-catch-all row falls into whichever row has
    `is_catch_all=True`.
    """
    __tablename__ = 'graduation_requirement'
    id                     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_name           = db.Column(db.String(100), unique=True, nullable=False)
    credits_required       = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    # Credits required for this subject at a 'continuation' track site (Site.grad_track).
    # NULL means "same as credits_required" — a subject doesn't need an explicit override
    # unless a district's continuation program actually reduces it.
    credits_required_continuation = db.Column(db.Numeric(6, 2), nullable=True)
    departments            = db.Column(db.Text, nullable=True)
    name_keywords          = db.Column(db.Text, nullable=True)
    name_exclude_keywords  = db.Column(db.Text, nullable=True)
    is_catch_all           = db.Column(db.Boolean, default=False, nullable=False)
    sort_order             = db.Column(db.Integer, default=0, nullable=False)
    # HS grade span this subject is typically completed across (e.g. Algebra I is '9'-'9',
    # done entirely freshman year; Social Science is '10'-'12', starting sophomore year).
    # Drives how much of credits_required is "expected by now" for a given grade level —
    # not just an even 1/4-per-year split of the whole 4-year requirement.
    start_grade            = db.Column(db.String(2), default='9', nullable=False, server_default='9')
    end_grade              = db.Column(db.String(2), default='12', nullable=False, server_default='12')

    @staticmethod
    def _split(csv):
        return [p.strip() for p in (csv or '').split(',') if p.strip()]

    # cached_property (not property): these are read in a hot loop when matching courses to
    # subjects, and re-splitting the same comma string on every access showed up as a real cost
    # at scale. Safe to cache since these fields don't change within a request/object lifetime.
    @cached_property
    def department_list(self):
        return self._split(self.departments)

    @cached_property
    def keyword_list(self):
        return self._split(self.name_keywords)

    @cached_property
    def exclude_keyword_list(self):
        return self._split(self.name_exclude_keywords)


class StudentSubjectCredits(db.Model):
    """Pre-aggregated completed credits per student per subject area.

    The Graduation Status dashboard used to re-sum the raw `Grade` table (which can run into the
    hundreds of thousands of rows for a district's full grade history) on every single page view —
    that was the whole page's load time. This table holds the already-summed result instead, kept
    in sync by `_recompute_grad_subject_credits()` whenever grades.csv is uploaded or the
    GraduationRequirement subject definitions change, so dashboard reads are a small indexed query.
    `subject_name` uses the sentinel 'Unclassified' rather than NULL for courses that don't match
    any subject row, since MySQL treats NULL as distinct from itself under a unique constraint.
    """
    __tablename__ = 'student_subject_credits'
    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_name', name='uq_student_subject'),
    )
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id   = db.Column(db.String(50), nullable=False, index=True)
    subject_name = db.Column(db.String(100), nullable=False)
    credits      = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    updated_at   = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    msg_name = db.Column(db.String(100), unique=True, nullable=False)
    msg_content = db.Column(db.String(255), nullable=False)
    msg_status = db.Column(db.String(10), nullable=False)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=False)
    email_enc  = db.Column(db.Text, nullable=False)
    email_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    status = db.Column(db.String(120), nullable=False)

    @property
    def email(self):
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.email_enc or '', current_app.config['DATA_ENCRYPTION_KEY'])

    @email.setter
    def email(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password, hash_email
        # email_enc (data at rest) and email_hash (lookup index) are deliberately keyed
        # differently — see utils.py.
        self.email_enc = encrypt_mail_password(value or '', current_app.config['DATA_ENCRYPTION_KEY'])
        self.email_hash = hash_email(value or '', current_app.config['SECRET_KEY'])
    password = db.Column(db.String(255), nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    rm_num = db.Column(db.String(45), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), nullable=False)
    # Extra sites beyond the required "primary" site_id above — see user_site.
    sites = db.relationship('Site', secondary='user_site', backref=db.backref('assigned_users', lazy=True))

    def get_full_name(self):
        return f"{self.first_name} {self.middle_name or ''} {self.last_name}".strip()

    @property
    def is_admin(self):
        return self.role and self.role.role_name.lower() == "admin"

    @property
    def is_district_admin(self):
        return self.role and self.role.role_name.lower() == "district administrator"

    @property
    def is_school_admin(self):
        return self.role and self.role.role_name.lower() == "school administrator"

    @property
    def is_tech_role(self):
        return self.role and self.role.role_name.lower() in ["district administrator", "school administrator"]

    @property
    def has_all_site_access(self):
        """Admin and District Administrator can view/select any site, or all sites
        (a blank site filter) at once — every other role is restricted to
        allowed_site_ids."""
        return bool(self.is_admin or self.is_district_admin)

    @property
    def allowed_site_ids(self):
        """Site IDs this user may view: their primary site plus any extra sites
        assigned via `sites` (e.g. a School Administrator covering several
        campuses). Irrelevant for has_all_site_access users, who aren't
        restricted to this set."""
        ids = {self.site_id}
        ids.update(s.id for s in self.sites)
        return ids

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > _utcnow())


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy=True)


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    site_name = db.Column(db.String(100), nullable=False, unique=True)
    site_acronyms = db.Column(db.String(36), nullable=False)
    site_cds = db.Column(db.String(100), nullable=False)
    site_code = db.Column(db.String(100), nullable=False)
    site_address = db.Column(db.String(100), nullable=False)
    site_type = db.Column(db.String(100), nullable=False)
    # Which GraduationRequirement credit targets apply to students at this site —
    # 'standard' or 'continuation' (continuation schools typically require fewer credits).
    # See GraduationRequirement.credits_required_continuation.
    grad_track = db.Column(db.String(20), nullable=False, default='standard', server_default='standard')
    site_city = db.Column(db.String(50), nullable=True)
    site_state = db.Column(db.String(2), nullable=True)
    site_zip = db.Column(db.String(10), nullable=True)
    principal_first_name = db.Column(db.String(50), nullable=True)
    principal_last_name = db.Column(db.String(50), nullable=True)
    # Encrypted at rest — same scheme as Student.email/Teacher.email/Parent.email.
    principal_email_enc = db.Column(db.Text, nullable=True)
    principal_phone_enc = db.Column(db.Text, nullable=True)
    users = db.relationship('User', backref='site', lazy=True)

    @property
    def principal_email(self):
        if not self.principal_email_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.principal_email_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @principal_email.setter
    def principal_email(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.principal_email_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None

    @property
    def principal_phone(self):
        if not self.principal_phone_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.principal_phone_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @principal_phone.setter
    def principal_phone(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.principal_phone_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None


# Association tables for many-to-many relationships
user_site = db.Table('user_site',
    # Extra site assignments beyond User.site_id (the required "primary" site) —
    # e.g. a School Administrator overseeing several campuses. See
    # User.sites / User.allowed_site_ids.
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('site_id', db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), primary_key=True),
)

student_course = db.Table('student_course',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), primary_key=True),
    db.Column('course_id',  db.Integer, db.ForeignKey('course.id',  ondelete='CASCADE'), primary_key=True),
    db.Column('start_date', db.Date, nullable=True),
    db.Column('leave_date', db.Date, nullable=True),
    # The (student_id, course_id) primary key doesn't help queries filtering by course_id
    # alone (e.g. "which students are in these courses") since course_id isn't the leading
    # column — this covers that access pattern, used by the Attendance Rates dashboard.
    db.Index('ix_student_course_course_leave', 'course_id', 'leave_date'),
)

student_parent = db.Table('student_parent',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), primary_key=True),
    db.Column('parent_id',  db.Integer, db.ForeignKey('parent.id',  ondelete='CASCADE'), primary_key=True)
)


class Student(db.Model):
    __table_args__ = (
        db.UniqueConstraint('student_id', 'schoolyr', name='uq_student_schoolyr'),
    )
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name    = db.Column(db.String(50), nullable=False)
    middle_name   = db.Column(db.String(50), nullable=True)
    last_name     = db.Column(db.String(50), nullable=False)
    student_id    = db.Column(db.String(20), nullable=False)
    # Encrypted at rest (statewide student ID — treated as sensitive, distinct from the
    # district-local student_id above). ssid_hash is a deterministic HMAC blind index
    # (see utils.hash_ssid) so SQL can still JOIN/GROUP BY/filter on it without decrypting —
    # Absence.ssid_hash mirrors this for the Student<->Absence join, since Absence has no FK.
    ssid_enc      = db.Column(db.Text, nullable=True)
    ssid_hash     = db.Column(db.String(64), nullable=True, index=True)
    cds_code      = db.Column(db.String(14), nullable=True)
    grade         = db.Column(db.String(5),  nullable=False)
    gender        = db.Column(db.String(1),  nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gradyr        = db.Column(db.String(4),  nullable=True)
    ethnicity     = db.Column(db.String(3),  nullable=True)
    frm_code      = db.Column(db.String(1),  nullable=True)
    english_status = db.Column(db.String(10), nullable=True)
    enter_date    = db.Column(db.Date, nullable=True)
    exit_date     = db.Column(db.Date, nullable=True)
    disability    = db.Column(db.String(20), nullable=True)
    dwelling      = db.Column(db.String(2),  nullable=True)
    migrant       = db.Column(db.Boolean, nullable=True, default=False)
    schoolyr      = db.Column(db.String(9),  nullable=True)
    foster        = db.Column(db.Boolean, nullable=True, default=False)
    sed504        = db.Column(db.Boolean, nullable=True, default=False)
    # Encrypted at rest (cryptography.fernet, DATA_ENCRYPTION_KEY) — same scheme as
    # User.email/Parent.email. Not used in any ilike()/filter() anywhere in routes.py,
    # so unlike Parent.email this didn't require dropping anything from a search feature.
    email_enc     = db.Column(db.Text, nullable=True)
    site_id       = db.Column(db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), nullable=False)
    site          = db.relationship('Site', backref=db.backref('students', lazy=True))

    @property
    def email(self):
        if not self.email_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.email_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @email.setter
    def email(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.email_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None

    @property
    def ssid(self):
        if not self.ssid_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.ssid_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @ssid.setter
    def ssid(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password, hash_ssid
        if value:
            self.ssid_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY'])
            self.ssid_hash = hash_ssid(value, current_app.config['SECRET_KEY'])
        else:
            self.ssid_enc = None
            self.ssid_hash = None

    # `courses` (via backref on Course.students) includes every course ever taken,
    # active or dropped. active_courses excludes dropped enrollments (leave_date set).
    active_courses = db.relationship(
        'Course', secondary=student_course,
        primaryjoin='Student.id == student_course.c.student_id',
        secondaryjoin='and_(Course.id == student_course.c.course_id, student_course.c.leave_date.is_(None))',
        viewonly=True,
    )

    @property
    def is_active(self):
        from datetime import date
        today = date.today()
        enter_ok = self.enter_date is None or self.enter_date <= today
        exit_ok  = self.exit_date  is None or self.exit_date  >= today
        return enter_ok and exit_ok

    @property
    def status(self):
        return 'Active' if self.is_active else 'Inactive'

    @status.setter
    def status(self, value):
        pass  # computed — assignment silently ignored for backward compat


class Absence(db.Model):
    # Absenteeism/Attendance Rates dashboards filter by school_yr (almost always) and site_id
    # (often) on every query, then GROUP BY ssid — without this, each was a full table scan
    # over the whole multi-year absence table (hundreds of thousands of rows district-wide).
    __table_args__ = (
        db.Index('ix_absence_schoolyr_site', 'school_yr', 'site_id'),
        # The single most repeated query shape on these dashboards is "WHERE school_yr = ?
        # GROUP BY ssid" (called 3x per Absenteeism page load alone) — this composite lets
        # MySQL satisfy both the filter and the grouping from one index instead of filtering
        # via ix_absence_schoolyr_site and then filesorting for the GROUP BY.
        db.Index('ix_absence_schoolyr_ssid', 'school_yr', 'ssid_hash'),
    )
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    site_id     = db.Column(db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), nullable=False)
    # Encrypted at rest, same scheme as Student.ssid — ssid_hash is the deterministic
    # blind index used for the Student<->Absence join (no FK between them) and every
    # dashboard's GROUP BY ssid. See utils.hash_ssid.
    ssid_enc    = db.Column(db.Text, nullable=True)
    ssid_hash   = db.Column(db.String(64), nullable=True, index=True)
    grade       = db.Column(db.String(5),  nullable=True)
    abs_date    = db.Column(db.Date,         nullable=True)
    abs_desc    = db.Column(db.String(200), nullable=True)
    bell_period = db.Column(db.String(20),  nullable=True)
    school_yr   = db.Column(db.String(9),   nullable=True)
    site        = db.relationship('Site', backref=db.backref('absences', lazy=True))

    @property
    def ssid(self):
        if not self.ssid_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.ssid_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @ssid.setter
    def ssid(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password, hash_ssid
        if value:
            self.ssid_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY'])
            self.ssid_hash = hash_ssid(value, current_app.config['SECRET_KEY'])
        else:
            self.ssid_enc = None
            self.ssid_hash = None


class Incident(db.Model):
    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sisid          = db.Column(db.String(20),  nullable=True)
    site           = db.Column(db.String(100), nullable=True)
    cds_code       = db.Column(db.String(14),  nullable=True)
    incident_id    = db.Column(db.String(30),  nullable=True)
    incident_date  = db.Column(db.Date,         nullable=True)
    schoolyr       = db.Column(db.String(9),   nullable=True)
    incident_time  = db.Column(db.String(10),  nullable=True)
    day_of_week    = db.Column(db.String(10),  nullable=True)
    major          = db.Column(db.String(100), nullable=True)
    minor          = db.Column(db.String(100), nullable=True)
    suspended_days = db.Column(db.Float,        nullable=True)


class Intervention(db.Model):
    """A logged MTSS/RTI support action for a student — e.g. a Tier 2 attendance check-in plan,
    a behavior contract, or academic tutoring — so staff have a record of what's been tried for
    an at-risk student (see Early Warning) and whether it worked. Created from the Early Warning
    dashboard or from a student's detail page.
    """
    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id    = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False, index=True)
    student       = db.relationship('Student', backref=db.backref('interventions', lazy=True))
    tier          = db.Column(db.String(10), nullable=False, default='Tier 1')
    category      = db.Column(db.String(20), nullable=False)  # Attendance / Behavior / Academic
    description   = db.Column(db.Text, nullable=False)
    start_date    = db.Column(db.Date, nullable=False)
    end_date      = db.Column(db.Date, nullable=True)
    status        = db.Column(db.String(20), nullable=False, default='Active')  # Active / Completed / Discontinued
    outcome       = db.Column(db.String(20), nullable=True)  # Improved / No Change / Worsened — set when closed
    notes         = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_by    = db.relationship('User', foreign_keys=[created_by_id])
    created_at    = db.Column(db.DateTime, default=_utcnow, nullable=False)


class Teacher(db.Model):
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name  = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)
    last_name   = db.Column(db.String(50), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    # Encrypted at rest — same scheme as Student.email/Parent.email.
    email_enc   = db.Column(db.Text, nullable=True)
    department  = db.Column(db.String(100), nullable=True)
    status      = db.Column(db.String(20), nullable=False, default='Active')
    site_id     = db.Column(db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), nullable=False)
    site        = db.relationship('Site', backref=db.backref('teachers', lazy=True))

    @property
    def email(self):
        if not self.email_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.email_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @email.setter
    def email(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.email_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None


class Course(db.Model):
    __table_args__ = (
        db.UniqueConstraint('site_id', 'section_id', name='uq_course_site_section'),
    )
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_name = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(20), nullable=True)
    grade_level = db.Column(db.String(5),  nullable=True)
    period      = db.Column(db.String(20), nullable=True)
    description  = db.Column(db.Text, nullable=True)
    max_students = db.Column(db.Integer, nullable=True)
    status       = db.Column(db.String(20), nullable=False, default='Active')
    section_id   = db.Column(db.String(50), nullable=True)
    course_catalog_id = db.Column(db.String(20), nullable=True)
    college_dept = db.Column(db.String(100), nullable=True)
    department   = db.Column(db.String(100), nullable=True)
    credits      = db.Column(db.Integer, nullable=True)
    term_code    = db.Column(db.String(10), nullable=True)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('teacher.id', ondelete='SET NULL'), nullable=True)
    site_id     = db.Column(db.Integer, db.ForeignKey('site.id', ondelete='CASCADE'), nullable=False)
    teacher     = db.relationship('Teacher', backref=db.backref('courses', lazy=True))
    site        = db.relationship('Site', backref=db.backref('courses', lazy=True))
    students    = db.relationship('Student', secondary=student_course,
                                  backref=db.backref('courses', lazy=True))
    # `students` includes every student ever enrolled, active or dropped.
    # active_students excludes dropped enrollments (leave_date set).
    active_students = db.relationship(
        'Student', secondary=student_course,
        primaryjoin='Course.id == student_course.c.course_id',
        secondaryjoin='and_(Student.id == student_course.c.student_id, student_course.c.leave_date.is_(None))',
        viewonly=True,
    )


class Parent(db.Model):
    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name   = db.Column(db.String(50), nullable=False)
    middle_name  = db.Column(db.String(50), nullable=True)
    last_name    = db.Column(db.String(50), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)
    # PII at rest — encrypted the same way as User.email (cryptography.fernet, keyed by
    # DATA_ENCRYPTION_KEY). No hash/index column like User.email_hash: Parent.email was
    # never unique and nothing does an exact DB-side lookup on it, only a Python-side
    # dict build in _process_parents_rows() — see there. This does mean the parents list
    # search can no longer ilike() against email (ciphertext isn't searchable that way);
    # it's dropped from that search, matching /users' own email-less search for the same reason.
    email_enc    = db.Column(db.Text, nullable=True)
    phone_enc    = db.Column(db.Text, nullable=True)
    status       = db.Column(db.String(20), nullable=False, default='Active')
    students     = db.relationship('Student', secondary=student_parent,
                                   backref=db.backref('parents', lazy=True))

    @property
    def email(self):
        if not self.email_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.email_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @email.setter
    def email(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.email_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None

    @property
    def phone(self):
        if not self.phone_enc:
            return None
        from flask import current_app
        from application.utils import decrypt_mail_password
        return decrypt_mail_password(self.phone_enc, current_app.config['DATA_ENCRYPTION_KEY']) or None

    @phone.setter
    def phone(self, value):
        from flask import current_app
        from application.utils import encrypt_mail_password
        self.phone_enc = encrypt_mail_password(value, current_app.config['DATA_ENCRYPTION_KEY']) if value else None


class BulkUploadLog(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    total_records = db.Column(db.Integer, default=0)
    users_added = db.Column(db.Integer, default=0)
    users_updated = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='success')
    error_message = db.Column(db.Text, nullable=True)

    uploader = db.relationship('User', foreign_keys=[uploaded_by_id])


class AuditLog(db.Model):
    """Records access to bulk/exportable student data for FERPA accountability.

    user_id is nullable so a log row survives user deletion (ondelete SET NULL) —
    losing the audit trail when an account is removed would defeat its purpose.
    """
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    action      = db.Column(db.String(50), nullable=False)
    detail      = db.Column(db.String(255), nullable=True)
    record_count = db.Column(db.Integer, nullable=True)
    ip_address  = db.Column(db.String(45), nullable=True)
    created_at  = db.Column(db.DateTime, default=_utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])
