"""
Background job functions for APScheduler.
Each function runs inside a Flask application context pushed explicitly.
"""
import ftplib
import io
import csv
import secrets
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_org_ftp_schedule():
    """Scheduled FTP import: downloads sites.csv then users CSV using credentials from Organization."""
    from main import db, scheduler

    with scheduler.app.app_context():
        from flask import current_app
        from application.models import Organization, BulkUploadLog, User, Site
        from application.utils import decrypt_mail_password, hash_email
        from application.routes import (
            _process_sites_rows, _process_student_rows, _process_staff_rows,
            _process_courses_rows, _process_master_schedule_rows,
            _process_student_schedule_rows, _process_parents_rows, _format_skip_summary
        )
        from werkzeug.security import generate_password_hash

        org = db.session.get(Organization, 1)
        if not org or not org.ftp_schedule_enabled:
            return

        today = datetime.now(timezone.utc).date()
        if org.ftp_schedule_start_date and today < org.ftp_schedule_start_date:
            logger.info('Scheduled FTP import skipped: before start date (%s).', org.ftp_schedule_start_date)
            return
        if org.ftp_schedule_stop_date and today > org.ftp_schedule_stop_date:
            logger.info('Scheduled FTP import skipped: past stop date (%s).', org.ftp_schedule_stop_date)
            return

        # data_key decrypts FTP credentials (data at rest); secret_key hashes emails for
        # the User lookup index — deliberately different keys, see utils.py.
        data_key   = current_app.config['DATA_ENCRYPTION_KEY']
        secret_key = current_app.config['SECRET_KEY']
        ftp_host = decrypt_mail_password(org.ftp_host_enc or '', data_key)
        username = decrypt_mail_password(org.ftp_username_enc or '', data_key)
        password = decrypt_mail_password(org.ftp_password_enc or '', data_key)
        raw_path = org.ftp_path or ''
        if raw_path.lower().endswith('.csv'):
            import posixpath as _pp
            raw_path = _pp.dirname(raw_path)
        ftp_dir  = raw_path.rstrip('/')
        port     = org.ftp_port or 21
        use_tls  = bool(org.ftp_use_tls)

        if not all([ftp_host, username, ftp_dir]):
            logger.warning('Scheduled FTP import skipped: incomplete credentials in Organization.')
            return

        users_path              = f'{ftp_dir}/users.csv'
        sites_path              = f'{ftp_dir}/sites.csv'
        demographics_path       = f'{ftp_dir}/demographics.csv'
        staff_path              = f'{ftp_dir}/staff.csv'
        courses_path            = f'{ftp_dir}/courses.csv'
        master_schedule_path    = f'{ftp_dir}/master_schedule.csv'
        students_schedule_path  = f'{ftp_dir}/students_schedule.csv'
        parents_path            = f'{ftp_dir}/parents.csv'

        users_added   = users_updated = total_records = 0
        sites_added   = sites_updated = 0
        demographics_added = demographics_updated = demographics_skipped = demographics_total = 0
        staff_added = staff_updated = staff_total = 0
        courses_added = courses_updated = courses_total = 0
        master_added = master_updated = master_total = 0
        sched_enrolled = sched_dropped = sched_total = 0
        sched_skip_detail = None
        parents_added = parents_updated = parents_total = 0
        parents_skipped_missing_field = parents_skipped_no_student = []
        parents_skip_detail = None

        try:
            ftp = ftplib.FTP_TLS() if use_tls else ftplib.FTP()
            ftp.connect(ftp_host, port, timeout=30)
            ftp.login(username, password)
            if use_tls:
                ftp.prot_p()

            # --- sites.csv (optional) ---
            sites_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {sites_path}', sites_buf.write)
                sites_buf.seek(0)
                site_rows   = list(csv.DictReader(sites_buf.read().decode('utf-8').splitlines()))
                sites_added, sites_updated = _process_sites_rows(site_rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Sites] [Scheduled] sites.csv',
                    total_records=len(site_rows),
                    users_added=sites_added,
                    users_updated=sites_updated,
                    status='success'
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # sites.csv absent — skip

            # --- demographics.csv (optional) ---
            demo_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {demographics_path}', demo_buf.write)
                demo_buf.seek(0)
                demo_rows = list(csv.DictReader(demo_buf.read().decode('utf-8-sig').splitlines()))
                demographics_total = len(demo_rows)
                demographics_added, demographics_updated, demographics_skipped = _process_student_rows(demo_rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Demographics] [Scheduled] demographics.csv',
                    total_records=demographics_total,
                    users_added=demographics_added,
                    users_updated=demographics_updated,
                    status='success'
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # demographics.csv absent — skip

            # --- staff.csv (optional) ---
            staff_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {staff_path}', staff_buf.write)
                staff_buf.seek(0)
                staff_rows = list(csv.DictReader(staff_buf.read().decode('utf-8-sig').splitlines()))
                staff_total = len(staff_rows)
                staff_added, staff_updated = _process_staff_rows(staff_rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Staff] [Scheduled] staff.csv',
                    total_records=staff_total,
                    users_added=staff_added,
                    users_updated=staff_updated,
                    status='success'
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # staff.csv absent — skip

            # --- courses.csv (optional) ---
            courses_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {courses_path}', courses_buf.write)
                courses_buf.seek(0)
                courses_rows = list(csv.DictReader(courses_buf.read().decode('utf-8-sig').splitlines()))
                courses_total = len(courses_rows)
                courses_added, courses_updated = _process_courses_rows(courses_rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Courses] [Scheduled] courses.csv',
                    total_records=courses_total,
                    users_added=courses_added,
                    users_updated=courses_updated,
                    status='success'
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # courses.csv absent — skip

            # --- master_schedule.csv (optional) ---
            master_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {master_schedule_path}', master_buf.write)
                master_buf.seek(0)
                master_rows = list(csv.DictReader(master_buf.read().decode('utf-8-sig').splitlines()))
                master_total = len(master_rows)
                master_added, master_updated = _process_master_schedule_rows(master_rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Master Schedule] [Scheduled] master_schedule.csv',
                    total_records=master_total,
                    users_added=master_added,
                    users_updated=master_updated,
                    status='success'
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # master_schedule.csv absent — skip

            # --- students_schedule.csv (optional) ---
            sched_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {students_schedule_path}', sched_buf.write)
                sched_buf.seek(0)
                sched_rows = list(csv.DictReader(sched_buf.read().decode('utf-8-sig').splitlines()))
                sched_total = len(sched_rows)
                sched_enrolled, sched_dropped, sched_skip_no_student, sched_skip_no_course = _process_student_schedule_rows(sched_rows)
                sched_skip_parts = [
                    p for p in (
                        _format_skip_summary('student not found', sched_skip_no_student),
                        _format_skip_summary('section not found', sched_skip_no_course),
                    ) if p
                ]
                sched_skip_detail = ' '.join(sched_skip_parts) or None
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Student Schedule] [Scheduled] students_schedule.csv',
                    total_records=sched_total,
                    users_added=sched_enrolled,
                    users_updated=sched_dropped,
                    status='success',
                    error_message=sched_skip_detail
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # students_schedule.csv absent — skip

            # --- parents.csv (optional) ---
            parents_buf = io.BytesIO()
            try:
                ftp.retrbinary(f'RETR {parents_path}', parents_buf.write)
                parents_buf.seek(0)
                parents_rows = list(csv.DictReader(parents_buf.read().decode('utf-8-sig').splitlines()))
                parents_total = len(parents_rows)
                parents_added, parents_updated, parents_skipped_missing_field, parents_skipped_no_student = _process_parents_rows(parents_rows)
                parents_skip_parts = [
                    p for p in (
                        _format_skip_summary('missing a required field', parents_skipped_missing_field),
                        _format_skip_summary('student not found', parents_skipped_no_student),
                    ) if p
                ]
                parents_skip_detail = ' '.join(parents_skip_parts) or None
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename='[Parents] [Scheduled] parents.csv',
                    total_records=parents_total,
                    users_added=parents_added,
                    users_updated=parents_updated,
                    status='success',
                    error_message=parents_skip_detail
                ))
                db.session.commit()
            except ftplib.error_perm:
                pass  # parents.csv absent — skip

            # --- users.csv ---
            user_buf = io.BytesIO()
            ftp.retrbinary(f'RETR {users_path}', user_buf.write)
            ftp.quit()

            user_buf.seek(0)
            rows = list(csv.DictReader(user_buf.read().decode('UTF-8').splitlines()))
            total_records = len(rows)

            # First pass: validate all rows and collect emails
            csv_emails = set()
            for row in rows:
                if not all([row.get('first_name'), row.get('last_name'), row.get('email'),
                            row.get('role_id'), row.get('site_name'), row.get('rm_num')]):
                    raise ValueError('Some rows are missing required fields.')
                site = Site.query.filter_by(site_name=row['site_name']).first()
                if not site:
                    raise ValueError(f"Site '{row['site_name']}' not found.")
                csv_emails.add(row['email'].strip().lower())

            # Second pass: upsert users
            for row in rows:
                site = Site.query.filter_by(site_name=row['site_name']).first()
                existing = User.query.filter_by(email_hash=hash_email(row['email'].strip(), secret_key)).first()
                if existing:
                    existing.first_name  = row['first_name']
                    existing.middle_name = row.get('middle_name') or None
                    existing.last_name   = row['last_name']
                    existing.rm_num      = row.get('rm_num') or existing.rm_num
                    existing.role_id     = int(row['role_id'])
                    existing.site_id     = site.id
                    existing.status      = row.get('status') or 'Active'
                    users_updated += 1
                else:
                    db.session.add(User(
                        first_name=row['first_name'],
                        middle_name=row.get('middle_name'),
                        last_name=row['last_name'],
                        email=row['email'].strip(),
                        status=row.get('status', 'Active'),
                        password=generate_password_hash(secrets.token_urlsafe(16)),
                        must_change_password=True,
                        rm_num=row.get('rm_num'),
                        role_id=row['role_id'],
                        site_id=site.id
                    ))
                    users_added += 1

            # Third pass: deactivate users absent from the CSV
            sched_csv_hashes = {hash_email(e, secret_key) for e in csv_emails}
            for user in User.query.filter(User.status == 'Active').all():
                if user.email_hash not in sched_csv_hashes:
                    user.status = 'Inactive'

            db.session.commit()

            org.ftp_last_run_at     = datetime.now(timezone.utc)
            org.ftp_last_run_status = 'success'
            db.session.add(org)
            db.session.add(BulkUploadLog(
                filename='[FTP] [Scheduled] users.csv',
                total_records=total_records,
                users_added=users_added,
                users_updated=users_updated,
                status='success'
            ))
            db.session.commit()
            logger.info(
                'Scheduled FTP import: users +%d/~%d, sites +%d/~%d, demographics +%d/~%d (%d skipped), '
                'staff +%d/~%d, courses +%d/~%d, master schedule +%d/~%d, '
                'student schedule %d enrolled/%d dropped, parents +%d/~%d (%d skipped).',
                users_added, users_updated, sites_added, sites_updated,
                demographics_added, demographics_updated, demographics_skipped,
                staff_added, staff_updated, courses_added, courses_updated, master_added, master_updated,
                sched_enrolled, sched_dropped, parents_added, parents_updated,
                len(parents_skipped_missing_field) + len(parents_skipped_no_student)
            )

        except Exception as e:
            db.session.rollback()
            org.ftp_last_run_at     = datetime.now(timezone.utc)
            org.ftp_last_run_status = 'error'
            try:
                db.session.add(org)
                db.session.add(BulkUploadLog(
                    filename='[FTP] [Scheduled] users.csv',
                    total_records=total_records,
                    users_added=users_added,
                    users_updated=users_updated,
                    status='error',
                    # Not the raw exception: it can embed row data (names, emails, etc.) via the
                    # SQL/params repr, and this message is displayed in the Upload Log UI. Full
                    # details are in the log line below.
                    error_message='An unexpected error occurred during the scheduled FTP import. See server logs for details.'
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
            logger.error(f'Scheduled FTP import failed: {e}', exc_info=True)
