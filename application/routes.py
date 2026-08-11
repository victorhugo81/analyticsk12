from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, current_app, send_from_directory, jsonify, session, make_response
from flask_limiter.util import get_remote_address
from flask_login import login_user, login_required, logout_user, current_user
from flask_paginate import Pagination, get_page_args
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from .models import User, Role, Site, Notification, Organization, BulkUploadLog, AuditLog, Student, Teacher, Course, Parent, Absence, Incident, Grade, student_course, GraduationRequirement, StudentSubjectCredits, Intervention
from .forms import LoginForm, UserForm, RoleForm, SiteForm, NotificationForm, OrganizationForm, EmailConfigForm, StudentForm, TeacherForm, CourseForm, ParentForm, GraduationRequirementForm, InterventionForm
from .utils import validate_password, validate_file_upload, encrypt_mail_password, decrypt_mail_password, hash_email
from .email_utils import send_temp_password_email, send_password_updated_email
from main import db, login_manager, mail, limiter, scheduler
from flask_mail import Message
from datetime import datetime, timedelta, timezone
import time, os, re, csv, logging, secrets, ftplib, io, socket
from sqlalchemy.sql import func
from flask_caching import Cache
from sqlalchemy import case
from sqlalchemy.orm import joinedload

# Security-relevant events (auth failures, lockouts, forbidden-access attempts) — kept on
# its own logger name so these can be filtered/shipped separately from general app logs
# for incident-response visibility. Never logs passwords or password hashes.
security_logger = logging.getLogger('security')

# Cache configuration for storing database query results
# Using simple cache type with 2-hour expiration for assigned users query
cache = Cache(config={'CACHE_TYPE': 'simple'})

# Cached function to retrieve users with specific roles (1 and 2)
# This avoids repeated database queries for frequently accessed user data
@cache.cached(timeout=7200, key_prefix='assigned_users')
def get_assigned_users():
    """
    Retrieve all users with role IDs 1 or 2 from the database.
    Results are cached for 2 hours to improve performance.
    
    Returns:
        list: List of User objects with role_id 1 or 2
    """
    return User.query.filter(User.role_id.in_([1, 2])).all()


# Create a Blueprint for organizing routes
# This allows for modular application structure and route organization
routes_blueprint = Blueprint('routes', __name__)

@routes_blueprint.app_context_processor
def inject_active_notifications():
    try:
        notifications = Notification.query.filter_by(msg_status='Active').all()
    except Exception:
        notifications = []
    return dict(active_notifications=notifications)


@routes_blueprint.app_context_processor
def inject_org():
    try:
        org = db.session.get(Organization, 1)
    except Exception:
        org = None
    return dict(org=org)


@routes_blueprint.app_context_processor
def inject_global_school_year():
    try:
        school_years = [r[0] for r in
                        db.session.query(Student.schoolyr)
                        .filter(Student.schoolyr.isnot(None), Student.schoolyr != '')
                        .distinct().order_by(Student.schoolyr.desc()).all()]
        global_sites         = Site.query.order_by(Site.site_name).all()
        active_schoolyr      = session.get('active_schoolyr', '')
        active_status_filter = session.get('active_status_filter', 'active')
        active_site_filter   = session.get('active_site_filter', '')
        active_snap_date     = session.get('active_snap_date', '')
        active_site = next(
            (s.site_name for s in global_sites if str(s.id) == active_site_filter),
            ''
        )
    except Exception:
        school_years, global_sites                          = [], []
        active_schoolyr, active_status_filter               = '', 'active'
        active_site_filter, active_snap_date, active_site   = '', '', ''
    return dict(global_school_years=school_years, global_sites=global_sites,
                active_schoolyr=active_schoolyr, active_status_filter=active_status_filter,
                active_site_filter=active_site_filter, active_snap_date=active_snap_date,
                active_site=active_site)


@routes_blueprint.before_request
def set_session_defaults():
    """Set first-visit session defaults before any route reads them."""
    if not current_user.is_authenticated:
        return
    if 'active_schoolyr' not in session:
        try:
            row = db.session.query(Student.schoolyr)\
                    .filter(Student.schoolyr.isnot(None), Student.schoolyr != '')\
                    .distinct().order_by(Student.schoolyr.desc()).first()
            session['active_schoolyr'] = row[0] if row else ''
        except Exception:
            session['active_schoolyr'] = ''
    # Only Admin/District Administrator may view "all schools" (blank filter) or
    # a site outside their assignment. Everyone else is pinned to one of their
    # allowed_site_ids on every request, regardless of what a stale/shared
    # session value holds — this is what every dashboard route's
    # `session.get('active_site_filter', '')` read ultimately relies on.
    if not current_user.has_all_site_access:
        allowed = {str(i) for i in current_user.allowed_site_ids}
        if session.get('active_site_filter', '') not in allowed:
            session['active_site_filter'] = str(current_user.site_id)


@routes_blueprint.route('/set_school_year')
@login_required
def set_school_year():
    yr = request.args.get('yr', '').strip()
    if not yr:
        # Fall back to the most recent available year
        row = db.session.query(Student.schoolyr)\
                .filter(Student.schoolyr.isnot(None), Student.schoolyr != '')\
                .distinct().order_by(Student.schoolyr.desc()).first()
        yr = row[0] if row else ''
    session['active_schoolyr'] = yr
    return redirect(request.referrer or url_for('routes.index'))


@routes_blueprint.route('/set_site_filter')
@login_required
def set_site_filter():
    sf = request.args.get('sf', '').strip()
    if not current_user.has_all_site_access:
        allowed = {str(i) for i in current_user.allowed_site_ids}
        if sf not in allowed:
            sf = str(current_user.site_id)
    session['active_site_filter'] = sf
    return redirect(request.referrer or url_for('routes.index'))


@routes_blueprint.route('/set_snap_date')
@login_required
def set_snap_date():
    session['active_snap_date'] = request.args.get('d', '').strip()
    return redirect(request.referrer or url_for('routes.index'))


@routes_blueprint.route('/set_status_filter')
@login_required
def set_status_filter():
    sf = request.args.get('sf', 'active').strip()
    if sf not in ('active', 'inactive', 'all'):
        sf = 'active'
    session['active_status_filter'] = sf
    return redirect(request.referrer or url_for('routes.index'))


# *****************************************************************
#-------------------- Core Setup -------------------------
# -------------- Do not change this section --------------
# *****************************************************************


# ****************** Force Password Change Enforcement *************
@routes_blueprint.before_request
def enforce_password_change():
    """Redirect users with a temporary password to the set-password page before they can do anything else."""
    if current_user.is_authenticated and getattr(current_user, 'must_change_password', False):
        allowed = {'routes.set_password', 'routes.logout', 'static'}
        if request.endpoint not in allowed:
            return redirect(url_for('routes.set_password'))



# ****************** Set Password (temp password flow) *************
@routes_blueprint.route('/set-password', methods=['GET', 'POST'])
@login_required
def set_password():
    org = db.session.get(Organization, 1)
    organization_name = org.organization_name if org else 'AssistITk12'

    if request.method == 'POST':
        new_password     = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not new_password or not confirm_password:
            flash('Both fields are required.', 'danger')
            return render_template('change_password.html', organization_name=organization_name)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('change_password.html', organization_name=organization_name)

        is_valid, error_message = validate_password(new_password)
        if not is_valid:
            flash(error_message, 'danger')
            return render_template('change_password.html', organization_name=organization_name)

        current_user.password = generate_password_hash(new_password)
        current_user.must_change_password = False
        db.session.add(current_user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"set_password failed for user {current_user.id}: {e}", exc_info=True)
            flash('An error occurred while saving your password. Please try again.', 'danger')
            return render_template('change_password.html', organization_name=organization_name)
        flash('Password updated successfully. Welcome!', 'success')
        return redirect(url_for('routes.index'))

    return render_template('change_password.html', organization_name=organization_name)



# ****************** Login Setup *******************************
@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login user loader callback.
    Loads a user from the database for session management.
    
    Args:
        user_id (str): The user ID to load from database
        
    Returns:
        User: The User object for the specified ID
    """
    return db.session.get(User, int(user_id))

# ****************** Admin *******************************
def is_admin():
    """
    Check if the current user has admin privileges.
    Abort with 403 Forbidden if the user is not an admin.

    Delegates to User.is_admin (compares by role NAME, not role_id) so this
    stays correct even if role ids are ever reseeded/reordered — see
    User.is_admin/is_tech_role in models.py for the single source of truth.
    """
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)

def is_tech_role():
    """
    Check if the current user has a technical role.
    Abort with 403 Forbidden if the user is not in a tech role.

    Technical roles are District Administrator and School Administrator.
    Delegates to User.is_tech_role (name-based) for the same reason as
    is_admin() above.
    """
    if not current_user.is_authenticated or not current_user.is_tech_role:
        abort(403)

def require_site_access(site_id):
    """Abort 403 unless the current user has all-site access or is assigned to
    the given site.

    Detail pages (student/teacher/course/parent) look records up by numeric ID with no
    other scoping — without this, any authenticated user from any site could view any
    other site's records just by changing the ID in the URL. List pages already filter
    by the session's active-site selection; this is the same boundary enforced at the
    object level, which a URL can't bypass.
    """
    if current_user.has_all_site_access:
        return
    if site_id not in current_user.allowed_site_ids:
        abort(403)

def _clamp_site_filter(site_filter):
    """Only Admin/District Administrator may request another site's (or all
    sites' — blank) data via a site_filter URL param. Every other role is
    restricted to one of their allowed_site_ids, same rule the before_request
    hook enforces for the session-based filter — this covers the handful of
    list routes that read site_filter straight from the URL instead of session.
    """
    if current_user.has_all_site_access:
        return site_filter
    allowed = {str(i) for i in current_user.allowed_site_ids}
    return site_filter if site_filter in allowed else str(current_user.site_id)

# ****************** Forbidden Error Page *******************************
@routes_blueprint.app_errorhandler(403)
def forbidden_error(error):
    """
    Custom 403 error handler for the application.
    Renders a custom error page when access is forbidden.
    
    Args:
        error: The error that triggered this handler
        
    Returns:
        tuple: Rendered error template and 403 status code
    """
    security_logger.warning(
        'Forbidden (403): path=%s user_id=%s ip=%s',
        request.path,
        current_user.id if current_user.is_authenticated else 'anonymous',
        request.remote_addr,
    )
    return render_template('error.html'), 403


# ****************** Server Error Page *******************************
@routes_blueprint.app_errorhandler(500)
def server_error(error):
    """
    Custom 500 error handler.

    With DEBUG off (the correct state for anything serving real traffic — see
    create_app()'s production guards in main.py), Flask already withholds the stack
    trace from the response by default; this handler exists so the page shown for an
    unhandled exception looks intentional rather than a bare framework default, matching
    the existing custom 403 page. Flask logs the underlying exception server-side before
    this handler runs, so nothing here needs to re-log it.
    """
    return render_template('server_error.html'), 500


# A fixed, valid scrypt hash checked when no user matches the submitted email — computed
# once at import time, not per-request. Without this, a nonexistent-email login attempt
# returns almost instantly (no hash to check) while an existing-email attempt takes the
# full scrypt verification time, letting an attacker enumerate valid accounts purely by
# response timing even though the error message itself is identical either way.
_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


# ****************** Login Page *******************************
@routes_blueprint.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", key_func=get_remote_address)
def login():
    """
    Handle user login requests.

    GET: Display the login form
    POST: Process the login form submission

    Returns:
        Response: Rendered login template or redirect to index on successful login
    """
    # Fetch organization name for display on login page
    organization = db.session.get(Organization, 1)
    organization_name = organization.organization_name if organization else "AssistITk12"

    _MAX_ATTEMPTS = 5
    _LOCKOUT_MINUTES = 15

    form = LoginForm()
    if form.validate_on_submit():
        _key = current_app.config['SECRET_KEY']
        user = User.query.filter_by(email_hash=hash_email(form.email.data, _key)).first()

        # Check lockout before verifying the password
        if user and user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
            remaining = int((user.locked_until - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() // 60) + 1
            security_logger.warning(
                'Login attempt on locked account: user_id=%s ip=%s remaining_minutes=%d',
                user.id, request.remote_addr, remaining
            )
            flash(f'Account locked. Try again in {remaining} minute(s).', 'danger')
            return render_template('login.html', form=form, organization_name=organization_name)

        if not user:
            # No account matches — still run a hash comparison against a fixed dummy
            # hash so this branch takes roughly the same time as a real failed password
            # check below, rather than returning near-instantly. Its result is discarded;
            # this exists purely to equalize timing.
            check_password_hash(_DUMMY_PASSWORD_HASH, form.password.data)

        if user and check_password_hash(user.password, form.password.data):
            if user.status != 'Active':
                security_logger.warning(
                    'Login attempt on inactive account: user_id=%s ip=%s',
                    user.id, request.remote_addr
                )
                flash('Your account is inactive. Please contact your administrator.', 'danger')
            else:
                # Successful login — reset lockout counters
                user.failed_login_attempts = 0
                user.locked_until = None
                db.session.commit()
                session.clear()
                session.permanent = True  # enforce PERMANENT_SESSION_LIFETIME
                login_user(user)
                security_logger.info(
                    'Successful login: user_id=%s ip=%s', user.id, request.remote_addr
                )
                if user.must_change_password:
                    return redirect(url_for('routes.set_password'))
                return redirect(url_for('routes.index'))
        else:
            # Failed attempt — increment counter and lock if threshold reached
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= _MAX_ATTEMPTS:
                    user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=_LOCKOUT_MINUTES)
                    user.failed_login_attempts = 0
                    db.session.commit()
                    security_logger.warning(
                        'Account locked after %d failed attempts: user_id=%s ip=%s',
                        _MAX_ATTEMPTS, user.id, request.remote_addr
                    )
                    flash(f'Too many failed attempts. Account locked for {_LOCKOUT_MINUTES} minutes.', 'danger')
                    return render_template('login.html', form=form, organization_name=organization_name)
                db.session.commit()
                security_logger.info(
                    'Failed login (bad password): user_id=%s ip=%s attempt=%d/%d',
                    user.id, request.remote_addr, user.failed_login_attempts, _MAX_ATTEMPTS
                )
            else:
                security_logger.info(
                    'Failed login (no matching account): ip=%s', request.remote_addr
                )
            flash('Login failed. Please check your credentials.', 'danger')

    return render_template(
        'login.html',
        form=form,
        organization_name=organization_name
    )


# ****************** Logout *******************************
@routes_blueprint.route('/logout')
@login_required
def logout():
    """
    Log out the currently authenticated user.
    Redirects to the login page after logout.
    
    Returns:
        Response: Redirect to login page
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('routes.login'))



# ****************** Update Organization Page *******************************
@routes_blueprint.route('/organization', methods=['GET', 'POST'])
@login_required
def organization():
    is_admin()
    """
    Display and process organization settings form.
    
    GET: Display the organization settings form
    POST: Process the form submission to update organization details
    
    Returns:
        Response: Rendered organization template or redirect on successful update
    """
    # Map URL paths to readable page names for navigation
    page_names = {'/organization': 'Data Integration'}
    # Get current path for navigation highlighting
    current_path = request.path
    # Get page name for display in UI
    current_page_name = page_names.get(current_path, 'Unknown Page')
    
    # Hardcoding organization_id to 1
    # NOTE: This assumes a single organization in the system
    organization_id = 1
    organization = Organization.query.get_or_404(organization_id)
    
    # Initialize form with current organization data
    form = OrganizationForm(obj=organization)

    # Initialize email config form (pre-populate from DB, but never show password)
    email_form = EmailConfigForm(obj=organization)
    email_form.mail_password.data = ''

    if form.validate_on_submit():
        # Check for duplicate organization names (excluding the current one)
        existing_organization = Organization.query.filter(
            Organization.organization_name == form.organization_name.data,
            Organization.id != organization.id
        ).first()

        if existing_organization:
            flash('An organization with that name already exists.', 'danger')
            return render_template('organization.html', form=form, email_form=email_form, organization=organization)

        # Update organization with form data
        organization.organization_name   = form.organization_name.data
        organization.site_version        = form.site_version.data
        organization.current_school_year = form.current_school_year.data or None
        organization.first_school_day    = form.first_school_day.data or None
        organization.last_school_day     = form.last_school_day.data or None
        db.session.commit()  # Save changes to database

        flash('Organization updated successfully!', 'success')
        return redirect(url_for('routes.organization'))

    # For GET requests or invalid form submissions, display the form
    return render_template('organization.html',
                          form=form,
                          email_form=email_form,
                          organization=organization,
                          current_path=current_path,
                          current_page_name=current_page_name)

# *****************************************************************
#-------------------- END Core Setup ---------------------
# -------------- Do not change this section --------------
# *****************************************************************


# ****************** Email Configuration *******************************
@routes_blueprint.route('/email-config', methods=['POST'])
@login_required
def email_config():
    """
    Save Flask-Mail SMTP configuration from the organization settings page.
    Updates the Organization record and immediately applies settings to the running app.
    """
    is_admin()
    organization = Organization.query.get_or_404(1)
    email_form = EmailConfigForm()

    if email_form.validate_on_submit():
        organization.mail_server = email_form.mail_server.data or None
        organization.mail_port = email_form.mail_port.data or None
        organization.mail_use_tls = email_form.mail_use_tls.data
        organization.mail_use_ssl = email_form.mail_use_ssl.data
        organization.mail_username = email_form.mail_username.data or None
        if email_form.mail_password.data:
            organization.mail_password = encrypt_mail_password(
                email_form.mail_password.data, current_app.config['DATA_ENCRYPTION_KEY']
            )
        organization.mail_default_sender = email_form.mail_default_sender.data or None
        db.session.commit()

        # Apply updated settings to the running Flask-Mail instance
        current_app.config['MAIL_SERVER'] = organization.mail_server or 'localhost'
        current_app.config['MAIL_PORT'] = organization.mail_port or 587
        current_app.config['MAIL_USE_TLS'] = bool(organization.mail_use_tls)
        current_app.config['MAIL_USE_SSL'] = bool(organization.mail_use_ssl)
        current_app.config['MAIL_USERNAME'] = organization.mail_username
        current_app.config['MAIL_PASSWORD'] = decrypt_mail_password(
            organization.mail_password or '', current_app.config['DATA_ENCRYPTION_KEY']
        )
        current_app.config['MAIL_DEFAULT_SENDER'] = organization.mail_default_sender
        mail.init_app(current_app)

        flash('Email settings updated successfully!', 'success')
    else:
        for field, errors in email_form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')

    return redirect(url_for('routes.organization'))


# ****************** Test Email *******************************
@routes_blueprint.route('/email-config/test', methods=['POST'])
@login_required
def test_email():
    """
    Send a test email to verify the current Flask-Mail configuration.
    Returns JSON with success/error details.
    """
    is_admin()
    recipient = request.form.get('test_recipient', '').strip()
    if not recipient:
        return jsonify({'success': False, 'message': 'Recipient email is required.'}), 400

    try:
        msg = Message(
            subject='Test Email – AssistITK12',
            recipients=[recipient],
            body=(
                'This is a test email sent from AssistITK12.\n\n'
                'Your email configuration is working correctly.\n\n'
                '— AssistITK12 System'
            )
        )
        mail.send(msg)
        current_app.logger.info(f"Test email sent to {recipient} by user {current_user.id}")
        return jsonify({'success': True, 'message': f'Test email sent to {recipient}.'})
    except Exception as e:
        current_app.logger.error(f"Test email failed: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# *****************************************************************
#-------------------- Site Template Pages ---------------------
# *****************************************************************

# *********************************************************************
# ****************** Home Page *******************************
@routes_blueprint.route('/', methods=['GET', 'POST'])
@login_required
def index():
    org = db.session.get(Organization, 1)
    return render_template(
        'index.html',
        current_page_name='Site Home',
        org=org,
    )


# ****************** Card Visibility *******************************
@routes_blueprint.route('/organization/card-visibility', methods=['POST'])
@login_required
def card_visibility():
    is_admin()
    org = Organization.query.get_or_404(1)
    cards = ['demographics', 'absenteeism', 'discipline', 'swd',
             'registration', 'enrollment', 'attendance_rates', 'early_warning', 'calpads', 'graduation',
             'el_progress', 'equity_gaps']
    for card in cards:
        setattr(org, f'show_{card}', f'show_{card}' in request.form)

    org.grad_auto_calculate_credits = 'grad_auto_calculate_credits' in request.form

    db.session.commit()
    flash('Dashboard card visibility updated.', 'success')
    return redirect(url_for('routes.organization') + '#dashboard-cards')


# ***************************************************************
# ****************** Profile Page *******************************
@routes_blueprint.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
        # Mapping paths to page names
    page_names = {'/profile': 'My Profile'}
    # Get the current path
    current_path = request.path
    # Get the corresponding page name or default to "Unknown Page"
    current_page_name = page_names.get(current_path, 'Unknown Page')
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        # Verify current password first
        if not current_password or not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('profile.html', user=current_user, role=current_user.role,
                current_path=current_path, current_page_name=current_page_name)
        # Validate new passwords
        if not password or not confirm_password:
            flash('Both password fields are required.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
        else:
            # Validate password complexity
            is_valid, error_message = validate_password(password)
            if not is_valid:
                flash(error_message, 'danger')
                return render_template('profile.html', user=current_user, role=current_user.role,
                    current_path=current_path, current_page_name=current_page_name)

            # Password is valid, proceed with update
            current_user.password = generate_password_hash(password)
            current_user.must_change_password = False
            try:
                db.session.commit()
                flash('Password updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"profile password update failed for user {current_user.id}: {e}", exc_info=True)
                flash('An error occurred while updating your password. Please try again.', 'danger')
            return redirect(url_for('routes.profile'))
    role = current_user.role  # Assuming current_user has a 'role' attribute
    return render_template('profile.html', user=current_user, role=role,
        current_path=current_path, 
        current_page_name=current_page_name
    )



# *********************************************************************
# ****************** Users Management Page ****************************
@routes_blueprint.route('/users', methods=['GET'])
@login_required
def users():
    page_names = {'/users': 'Manage Users'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    
    # Ensure only admins and tech roles can access this route
    if not (current_user.is_admin or current_user.is_tech_role):
        abort(403)

    page, per_page, offset = get_page_args(page_parameter="page", per_page_parameter="per_page")
    search = request.args.get('search', '').strip()
    site_filter = request.args.get('site_filter', '').strip()
    role_filter = request.args.get('role_filter', '').strip()
    query = User.query
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
        )
    # Apply site filter
    if site_filter:
        query = query.filter(User.site_id == site_filter)
    # Apply role filter
    if role_filter:
        query = query.filter(User.role_id == role_filter)
    total = query.count()
    users = query.order_by(User.first_name.asc()).offset(offset).limit(per_page).all()
    # Fetch all sites and roles for the filter dropdowns
    sites = Site.query.order_by(Site.site_name.asc()).all()
    roles = Role.query.order_by(Role.role_name.asc()).all()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    return render_template(
        'users.html',
        users=users,
        pagination=pagination,
        per_page=per_page,
        total=total,
        current_path=current_path,
        current_page_name=current_page_name,
        sites=sites,
        roles=roles,
        search=search,
        site_filter=site_filter,
        role_filter=role_filter
    )


# ****************** Add User Page *******************************
@routes_blueprint.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    is_admin()  # Ensure only admins can access this route
    # Mapping paths to page names
    page_names = {'/add_user': 'Add User'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')

    form = UserForm()
    form.role_id.choices = [(role.id, role.role_name) for role in Role.query.all()]
    form.site_id.choices = [(site.id, site.site_name) for site in Site.query.all()]
    form.sites.choices = [(site.id, site.site_name) for site in Site.query.all()]
    if form.validate_on_submit():
        # Check if a user with the same email already exists
        _key = current_app.config['SECRET_KEY']
        existing_user = User.query.filter_by(email_hash=hash_email(form.email.data, _key)).first()
        if existing_user:
            flash('A user with this email already exists. Please use a different email.', 'danger')
            return render_template('add_user.html', form=form)
        # Validate password complexity
        password = form.password.data
        is_valid, error_message = validate_password(password)
        if not is_valid:
            flash(error_message, 'danger')
            return render_template('add_user.html', form=form)
        # Proceed with creating the new user
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            status=form.status.data,
            rm_num=form.rm_num.data,
            site_id=form.site_id.data,
            role_id=form.role_id.data,
            password=hashed_password
        )
        # Additional site assignments (e.g. a School Administrator covering
        # several campuses) — reachable only by Admin, since add_user() itself
        # is Admin-gated above.
        if form.sites.data:
            new_user.sites = Site.query.filter(Site.id.in_(form.sites.data)).all()
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('routes.users'))
    return render_template('add_user.html', form=form,current_path=current_path,
        current_page_name=current_page_name)




# ****************** Edit User Page *******************************
# ****************** Send Temporary Password (AJAX) *******************************
@routes_blueprint.route('/send_temp_password/<int:user_id>', methods=['POST'])
@login_required
def send_temp_password(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    user = User.query.get_or_404(user_id)
    temp_password = secrets.token_urlsafe(12)

    try:
        send_temp_password_email(user, temp_password)
    except Exception:
        return jsonify({'success': False, 'message': 'Failed to send email. Check your SMTP configuration.'}), 500

    user.password = generate_password_hash(temp_password)
    user.must_change_password = True
    db.session.commit()

    return jsonify({'success': True, 'message': f'Temporary password sent to {user.email}'})



@routes_blueprint.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Ensure only admins and tech roles can access this route
    if not (current_user.is_admin or current_user.is_tech_role):
        abort(403)
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    # Populate dynamic choices for role_id and site_id
    form.role_id.choices = [(role.id, role.role_name) for role in Role.query.all()]
    form.site_id.choices = [(site.id, site.site_name) for site in Site.query.all()]
    form.sites.choices = [(site.id, site.site_name) for site in Site.query.all()]
    if request.method == 'GET':
        # SelectMultipleField.process_data expects raw ids, not Site objects —
        # obj=user above can't populate this from the `sites` relationship.
        form.sites.data = [s.id for s in user.sites]
    if form.validate_on_submit():
        # Check if a user with the same email already exists
        _key = current_app.config['SECRET_KEY']
        existing_user = User.query.filter(
            User.email_hash == hash_email(form.email.data, _key),
            User.id != user.id
        ).first()
        if existing_user:
            flash('A user with this email already exists. Please use a different email.', 'danger')
            return render_template('edit_user.html', form=form, user=user)
        # Track changes to avoid unnecessary updates
        changes_made = False
        # Update user details only if there are changes
        if user.first_name != form.first_name.data:
            user.first_name = form.first_name.data
            changes_made = True
        if user.middle_name != form.middle_name.data:
            user.middle_name = form.middle_name.data
            changes_made = True
        if user.last_name != form.last_name.data:
            user.last_name = form.last_name.data
            changes_made = True
        if user.email != form.email.data:
            user.email = form.email.data
            changes_made = True
        if user.status != form.status.data:
            user.status = form.status.data
            changes_made = True
        if user.rm_num != form.rm_num.data:
            user.rm_num = form.rm_num.data
            changes_made = True
        if user.site_id != form.site_id.data:
            user.site_id = form.site_id.data
            changes_made = True
        if user.role_id != form.role_id.data:
            user.role_id = form.role_id.data
            changes_made = True
        # Only Admin/District Administrator may reassign which schools a user
        # can access — a School Administrator reaching this page via
        # is_tech_role can view/edit their own basic info but not grant
        # themselves (or anyone else) additional sites.
        if current_user.is_admin or current_user.is_district_admin:
            new_site_ids = set(form.sites.data or [])
            current_site_ids = {s.id for s in user.sites}
            if new_site_ids != current_site_ids:
                user.sites = Site.query.filter(Site.id.in_(new_site_ids)).all() if new_site_ids else []
                changes_made = True
        # Validate and update password only if provided
        password_changed = False
        if form.password.data:
            password = form.password.data
            is_valid, error_message = validate_password(password)
            if not is_valid:
                flash(error_message, 'danger')
                return render_template('edit_user.html', form=form, user=user)
            user.password = generate_password_hash(password)
            user.must_change_password = False
            changes_made = True
            password_changed = True
        # Commit changes only if any were made
        if changes_made:
            db.session.commit()
            if password_changed:
                send_password_updated_email(user)
            flash('User updated successfully!', 'success')
            return redirect(url_for('routes.users'))
        else:
            flash('No changes were made.', 'info')
    return render_template('edit_user.html', form=form, user=user)



# ****************** Delete User Page *******************************
@routes_blueprint.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    is_admin()  # Ensure only admins can access this route
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'warning')
    return redirect(url_for('routes.users'))


# ****************** Unlock User Account (Admin) *******************************
@routes_blueprint.route('/unlock_user/<int:user_id>', methods=['POST'])
@login_required
def unlock_user(user_id):
    is_admin()  # Ensure only admins can access this route
    user = User.query.get_or_404(user_id)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
    security_logger.info(
        'Account unlocked by admin: user_id=%s admin_id=%s ip=%s',
        user.id, current_user.id, request.remote_addr
    )
    flash(f'Account for {user.first_name} {user.last_name} has been unlocked.', 'success')
    return redirect(url_for('routes.users'))



SITE_REQUIRED = ['site_name', 'site_acronyms', 'site_cds', 'site_code', 'site_address', 'site_type']
DEMOGRAPHICS_REQUIRED = ['stu_id', 'site_id', 'grade', 'schoolyr']

_MAX_ROW_ERRORS_SHOWN = 20


def _row_missing_field_errors(rows, required_fields, start=2):
    """Return a 'Row N: missing ...' string for every row missing one of required_fields."""
    errors = []
    for i, row in enumerate(rows, start=start):
        missing = [f for f in required_fields if not row.get(f, '').strip()]
        if missing:
            errors.append(f"Row {i}: missing {', '.join(missing)}")
    return errors


def _raise_if_row_errors(errors, total_rows):
    if not errors:
        return
    shown = errors[:_MAX_ROW_ERRORS_SHOWN]
    msg = '; '.join(shown)
    if len(errors) > _MAX_ROW_ERRORS_SHOWN:
        msg += f'; ... and {len(errors) - _MAX_ROW_ERRORS_SHOWN} more'
    raise ValueError(f'{len(errors)} of {total_rows} rows have problems: {msg}')


def _format_skip_summary(label, row_numbers):
    """Build a 'N skipped: label (e.g. rows ...)' string, or None if row_numbers is empty."""
    if not row_numbers:
        return None
    shown = row_numbers[:_MAX_ROW_ERRORS_SHOWN]
    text = f"{len(row_numbers)} skipped: {label} (e.g. rows {', '.join(map(str, shown))}"
    if len(row_numbers) > _MAX_ROW_ERRORS_SHOWN:
        text += f', +{len(row_numbers) - _MAX_ROW_ERRORS_SHOWN} more'
    text += ')'
    return text


def _parse_date(s):
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _count_weekdays(start, end):
    """Number of Mon-Fri weekdays in [start, end] inclusive — closed-form instead of iterating
    one day at a time, which showed up as a real cost once this ran per-student across an entire
    school year for thousands of students (attendance/absenteeism rate calculations)."""
    if start > end:
        return 0
    days = (end - start).days + 1
    full_weeks, remainder = divmod(days, 7)
    count = full_weeks * 5
    w = start.weekday()
    for _ in range(remainder):
        if w < 5:
            count += 1
        w = (w + 1) % 7
    return count


_VALID_ETHNICITY = {'100','200','300','400','500','600','700','800','900'}

def _parse_ethnicity(s):
    """Return a valid CALPADS ethnicity code or None."""
    if not s or not s.strip():
        return None
    s = s.strip()
    return s if s in _VALID_ETHNICITY else None


def _parse_gradyr(s):
    """Return a 4-digit graduation year string, handling dates like '7/25/05' or plain years like '2025'."""
    if not s or not s.strip():
        return None
    s = s.strip()
    if len(s) == 4 and s.isdigit():
        return s
    parsed = _parse_date(s)
    if parsed:
        return str(parsed.year)
    # Last resort: grab the first 4-digit sequence
    import re as _re
    m = _re.search(r'\b(\d{4})\b', s)
    return m.group(1) if m else None


def _normalize_siteid(raw):
    """Strip non-digit characters so siteid and site_cds can be compared regardless of separators."""
    return re.sub(r'[^0-9]', '', (raw or '').strip())


def _process_student_rows(rows):
    """Upsert students from demographics CSV rows. Returns (added, updated, skipped)."""
    added = updated = skipped = 0

    # Use org's current_school_year as default when rows omit schoolyr
    org = db.session.get(Organization, 1)
    org_school_year = org.current_school_year if org else None

    # Fill missing schoolyr from org setting before required-field check
    for row in rows:
        if not row.get('schoolyr', '').strip() and org_school_year:
            row['schoolyr'] = org_school_year
    _raise_if_row_errors(_row_missing_field_errors(rows, DEMOGRAPHICS_REQUIRED), len(rows))

    # Build site_cds cache keyed by digits-only CDS string
    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    all_sites   = Site.query.all()
    site_cache  = {_normalize_siteid(s.site_cds): s.id for s in all_sites if s.site_cds}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    # Pre-fetch existing students by (student_id, schoolyr) for efficient upsert
    stuids = [row['stu_id'].strip() for row in rows if row.get('stu_id')]
    existing_by_pair = Student.query.filter(Student.student_id.in_(stuids)).all()
    existing_map = {(s.student_id, s.schoolyr): s for s in existing_by_pair}

    FRM_MAP = {'0': None, '': None, '1': 'F', '2': 'R', '3': 'P'}

    for row in rows:
        stuid   = row.get('stu_id', '').strip()
        siteid  = _normalize_siteid(row.get('site_id', ''))
        if not stuid or siteid not in site_cache:
            skipped += 1
            continue

        site_id = site_cache[siteid]

        frm_raw    = row.get('frmcode', '0').strip()
        frm_code   = FRM_MAP.get(frm_raw, frm_raw or None)
        dis_raw    = row.get('disability', '0').strip()
        disability = None if dis_raw in ('0', '') else dis_raw
        dwell_raw  = row.get('dwelling_type', '0').strip()
        dwelling   = None if dwell_raw in ('0', '') else 'U'
        migrant    = row.get('migrant', 'N').strip().upper() == 'Y'
        foster     = row.get('foster', 'N').strip().upper() == 'Y'
        sed504     = row.get('code_504', '0').strip() not in ('0', '')

        schoolyr = row.get('schoolyr', '').strip() or None
        key = (stuid, schoolyr)
        csv_first  = row.get('first_name',  '').strip()
        csv_middle = row.get('middle_name', '').strip()
        csv_last   = row.get('last_name',   '').strip()
        csv_email  = row.get('email',       '').strip()

        existing = existing_map.get(key)
        if existing:
            existing.ssid           = row.get('ssid', '').strip() or None
            if csv_first:
                existing.first_name = csv_first
            if csv_middle:
                existing.middle_name = csv_middle
            if csv_last:
                existing.last_name = csv_last
            if csv_email:
                existing.email = csv_email
            existing.grade          = row.get('grade', '').strip()
            existing.gender         = row.get('gender', '').strip() or None
            existing.date_of_birth  = _parse_date(row.get('birth_date'))
            existing.gradyr         = _parse_gradyr(row.get('gradyr', ''))
            existing.ethnicity      = _parse_ethnicity(row.get('race', ''))
            existing.frm_code       = frm_code
            existing.english_status = row.get('english_status', '').strip() or None
            existing.enter_date     = _parse_date(row.get('entry_date'))
            existing.exit_date      = _parse_date(row.get('exit_date'))
            existing.disability     = disability
            existing.dwelling       = dwelling
            existing.migrant        = migrant
            existing.foster         = foster
            existing.sed504         = sed504
            existing.site_id        = site_id
            updated += 1
        else:
            new_stu = Student(
                student_id    = stuid,
                ssid          = row.get('ssid', '').strip() or None,
                first_name    = csv_first,
                middle_name   = csv_middle or None,
                last_name     = csv_last,
                email         = csv_email or None,
                grade         = row.get('grade', '').strip(),
                gender        = row.get('gender', '').strip() or None,
                date_of_birth = _parse_date(row.get('birth_date')),
                gradyr        = _parse_gradyr(row.get('gradyr', '')),
                ethnicity     = _parse_ethnicity(row.get('race', '')),
                frm_code      = frm_code,
                english_status= row.get('english_status', '').strip() or None,
                enter_date    = _parse_date(row.get('entry_date')),
                exit_date     = _parse_date(row.get('exit_date')),
                disability    = disability,
                dwelling      = dwelling,
                migrant       = migrant,
                foster        = foster,
                sed504        = sed504,
                schoolyr      = schoolyr,
                site_id       = site_id,
            )
            db.session.add(new_stu)
            existing_map[key] = new_stu
            added += 1

    return added, updated, skipped

def _normalize_cds(raw):
    """Convert Excel scientific-notation CDS codes (e.g. '1.23457E+13') to integer strings."""
    raw = raw.strip()
    try:
        return str(int(float(raw)))
    except (ValueError, OverflowError):
        return raw


def _process_sites_rows(rows):
    """Upsert sites from a list of CSV dicts. Returns (added, updated). Raises ValueError on bad data."""
    added = updated = 0

    # sites.csv uses 'site_id' as the header for the CDS-style code
    for row in rows:
        if not row.get('site_cds', '').strip() and row.get('site_id', '').strip():
            row['site_cds'] = row['site_id']

    # Validate all rows first (no DB interaction)
    _raise_if_row_errors(_row_missing_field_errors(rows, SITE_REQUIRED), len(rows))

    # Pre-fetch all matching sites in one query to avoid mid-loop auto-flush
    names = [row['site_name'].strip() for row in rows]
    site_cache = {s.site_name: s for s in Site.query.filter(Site.site_name.in_(names)).all()}

    for row in rows:
        name = row['site_name'].strip()
        cds  = _normalize_cds(row['site_cds'])
        principal_first = row.get('prnfirstn', '').strip() or None
        principal_last  = row.get('prnlastn', '').strip() or None
        principal_email = row.get('email', '').strip() or None
        principal_phone = row.get('phone', '').strip() or None
        city  = row.get('sitecity', '').strip() or None
        state = row.get('sitestate', '').strip() or None
        zip_  = row.get('sitezip', '').strip() or None
        site = site_cache.get(name)
        if site:
            site.site_acronyms         = row['site_acronyms'].strip()
            site.site_cds              = cds
            site.site_code             = row['site_code'].strip()
            site.site_address          = row['site_address'].strip()
            site.site_type             = row['site_type'].strip()
            site.site_city             = city
            site.site_state            = state
            site.site_zip              = zip_
            site.principal_first_name  = principal_first
            site.principal_last_name   = principal_last
            site.principal_email       = principal_email
            site.principal_phone       = principal_phone
            updated += 1
        else:
            new_site = Site(
                site_name             = name,
                site_acronyms         = row['site_acronyms'].strip(),
                site_cds              = cds,
                site_code             = row['site_code'].strip(),
                site_address          = row['site_address'].strip(),
                site_type             = row['site_type'].strip(),
                site_city             = city,
                site_state            = state,
                site_zip              = zip_,
                principal_first_name  = principal_first,
                principal_last_name   = principal_last,
                principal_email       = principal_email,
                principal_phone       = principal_phone,
            )
            db.session.add(new_site)
            site_cache[name] = new_site  # prevent duplicate inserts if name appears twice in CSV
            added += 1
    return added, updated


STAFF_REQUIRED = ['site_id', 'employee_id', 'first_name', 'last_name']


def _process_staff_rows(rows):
    """Upsert teachers from staff.csv rows. Returns (added, updated). Raises ValueError on bad data."""
    added = updated = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, STAFF_REQUIRED), len(rows))

    # Build site_cds cache keyed by digits-only CDS string
    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    all_sites   = Site.query.all()
    site_cache  = {_normalize_siteid(s.site_cds): s.id for s in all_sites if s.site_cds}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    # Pre-fetch existing teachers by employee_id for efficient upsert
    employee_ids = [row['employee_id'].strip() for row in rows]
    existing_map = {t.employee_id: t for t in Teacher.query.filter(Teacher.employee_id.in_(employee_ids)).all()}

    for row in rows:
        employee_id = row['employee_id'].strip()
        site_id     = site_cache[_normalize_siteid(row['site_id'])]
        first_name  = row['first_name'].strip()
        middle_name = row.get('middle_name', '').strip() or None
        last_name   = row['last_name'].strip()
        email       = row.get('email', '').strip() or None

        existing = existing_map.get(employee_id)
        if existing:
            existing.first_name  = first_name
            existing.middle_name = middle_name
            existing.last_name   = last_name
            existing.email       = email
            existing.site_id     = site_id
            updated += 1
        else:
            new_teacher = Teacher(
                employee_id = employee_id,
                first_name  = first_name,
                middle_name = middle_name,
                last_name   = last_name,
                email       = email,
                site_id     = site_id,
            )
            db.session.add(new_teacher)
            existing_map[employee_id] = new_teacher  # prevent duplicate inserts if employee_id repeats in CSV
            added += 1
    return added, updated


def _parse_int(raw):
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _parse_float(raw):
    try:
        return float(str(raw).strip())
    except (ValueError, TypeError):
        return None


COURSES_REQUIRED = ['site_id', 'course_name', 'section_id']


def _course_site_cache():
    all_sites = Site.query.all()
    return {_normalize_siteid(s.site_cds): s.id for s in all_sites if s.site_cds}


def _existing_course_cache(rows, site_cache):
    keys = set()
    for row in rows:
        site_id = site_cache.get(_normalize_siteid(row.get('site_id', '')))
        section_id = row.get('section_id', '').strip()
        if site_id and section_id:
            keys.add((site_id, section_id))
    if not keys:
        return {}
    site_ids = {k[0] for k in keys}
    existing = Course.query.filter(Course.site_id.in_(site_ids), Course.section_id.isnot(None)).all()
    return {(c.site_id, c.section_id): c for c in existing}


def _process_courses_rows(rows):
    """Upsert course sections from courses.csv rows. Returns (added, updated). Raises ValueError on bad data."""
    added = updated = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, COURSES_REQUIRED), len(rows))

    site_cache = _course_site_cache()
    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    course_cache = _existing_course_cache(rows, site_cache)

    for row in rows:
        site_id    = site_cache[_normalize_siteid(row['site_id'])]
        section_id = row['section_id'].strip()
        key = (site_id, section_id)

        existing = course_cache.get(key)
        if existing:
            existing.course_name       = row['course_name'].strip()
            existing.course_catalog_id = row.get('course_id', '').strip() or None
            existing.college_dept      = row.get('college_dept', '').strip() or None
            existing.department        = row.get('deptartment', '').strip() or None
            existing.credits           = _parse_int(row.get('credits'))
            existing.max_students      = _parse_int(row.get('max_students'))
            existing.grade_level       = row.get('grade_level', '').strip() or existing.grade_level
            updated += 1
        else:
            new_course = Course(
                course_name       = row['course_name'].strip(),
                section_id        = section_id,
                course_catalog_id = row.get('course_id', '').strip() or None,
                college_dept      = row.get('college_dept', '').strip() or None,
                department        = row.get('deptartment', '').strip() or None,
                credits           = _parse_int(row.get('credits')),
                max_students      = _parse_int(row.get('max_students')),
                grade_level       = row.get('grade_level', '').strip() or None,
                site_id           = site_id,
            )
            db.session.add(new_course)
            course_cache[key] = new_course  # prevent duplicate inserts if section_id repeats in CSV
            added += 1
    return added, updated


MASTER_SCHEDULE_REQUIRED = ['site_id', 'section_id', 'course_name']


def _process_master_schedule_rows(rows):
    """Upsert course sections from master_schedule.csv rows. Returns (added, updated). Raises ValueError on bad data."""
    added = updated = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, MASTER_SCHEDULE_REQUIRED), len(rows))

    site_cache = _course_site_cache()
    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    staff_ids = {row['staff_id'].strip() for row in rows if row.get('staff_id', '').strip()}
    teacher_cache = {t.employee_id: t.id for t in Teacher.query.filter(Teacher.employee_id.in_(staff_ids)).all()}
    missing_staff = [sid for sid in staff_ids if sid not in teacher_cache]
    if missing_staff:
        raise ValueError(f"Staff employee ID(s) not found in the system: {', '.join(missing_staff)}")

    course_cache = _existing_course_cache(rows, site_cache)

    for row in rows:
        site_id    = site_cache[_normalize_siteid(row['site_id'])]
        section_id = row['section_id'].strip()
        key = (site_id, section_id)
        staff_id = row.get('staff_id', '').strip()
        teacher_id = teacher_cache.get(staff_id)

        existing = course_cache.get(key)
        if existing:
            existing.course_name = row['course_name'].strip()
            existing.period      = row.get('period', '').strip() or None
            existing.term_code   = row.get('term_code', '').strip() or None
            existing.grade_level = row.get('grade_level', '').strip() or existing.grade_level
            if teacher_id:
                existing.teacher_id = teacher_id
            updated += 1
        else:
            new_course = Course(
                course_name = row['course_name'].strip(),
                section_id  = section_id,
                period      = row.get('period', '').strip() or None,
                term_code   = row.get('term_code', '').strip() or None,
                grade_level = row.get('grade_level', '').strip() or None,
                teacher_id  = teacher_id,
                site_id     = site_id,
            )
            db.session.add(new_course)
            course_cache[key] = new_course  # prevent duplicate inserts if section_id repeats in CSV
            added += 1
    return added, updated


STUDENT_SCHEDULE_REQUIRED = ['stu_id', 'section_id', 'schoolyr']


def _process_student_schedule_rows(rows):
    """Enroll/drop students in course sections from students_schedule.csv rows.

    The section's site is taken from the row's own `site_id` column (CDS code,
    same matching as courses.csv/master_schedule.csv) when present; otherwise it
    falls back to the matched student's own site (looked up by stu_id + schoolyr).
    The explicit column is needed because section_id is not unique across sites —
    a student can be scheduled into a section hosted at a different site (e.g. a
    cyber/independent-study program) than their demographics.csv site.

    A drop sets `leave_date` on the existing enrollment row rather than deleting
    it, so course history survives (visible via Student.courses / Course.students).
    Student.active_courses / Course.active_students expose only rows still open
    (leave_date IS NULL) for enrollment-count purposes elsewhere in the app.

    Returns (enrolled, dropped, skipped_no_student, skipped_no_course), where the
    last two are lists of 1-indexed row numbers. Raises ValueError on bad data.
    """
    enrolled = dropped = 0
    skipped_no_student = []
    skipped_no_course = []

    _raise_if_row_errors(_row_missing_field_errors(rows, STUDENT_SCHEDULE_REQUIRED), len(rows))

    stu_ids = {row['stu_id'].strip() for row in rows if row.get('stu_id')}
    schoolyrs = {row['schoolyr'].strip() for row in rows if row.get('schoolyr')}
    students = Student.query.filter(Student.student_id.in_(stu_ids), Student.schoolyr.in_(schoolyrs)).all()
    student_cache = {(s.student_id, s.schoolyr): s for s in students}

    site_cache = _course_site_cache()
    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id', '').strip()}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    site_ids = {s.site_id for s in students} | {site_cache[sid] for sid in raw_siteids}
    courses = (Course.query.filter(Course.site_id.in_(site_ids), Course.section_id.isnot(None)).all()
               if site_ids else [])
    course_cache = {(c.site_id, c.section_id): c for c in courses}

    student_ids = {s.id for s in students}
    course_ids  = {c.id for c in courses}
    existing_active = {}
    if student_ids and course_ids:
        existing_rows = db.session.execute(
            student_course.select().where(
                student_course.c.student_id.in_(student_ids),
                student_course.c.course_id.in_(course_ids),
            )
        ).all()
        existing_active = {(r.student_id, r.course_id): (r.leave_date is None) for r in existing_rows}

    for i, row in enumerate(rows, start=2):
        section_id = row['section_id'].strip()
        stu_id     = row['stu_id'].strip()
        schoolyr   = row['schoolyr'].strip()
        leave_date_str = row.get('leave_date', '').strip()
        row_site   = row.get('site_id', '').strip()

        student = student_cache.get((stu_id, schoolyr))
        if not student:
            skipped_no_student.append(i)
            continue

        target_site_id = site_cache[_normalize_siteid(row_site)] if row_site else student.site_id
        course = course_cache.get((target_site_id, section_id))
        if not course:
            skipped_no_course.append(i)
            continue

        key = (student.id, course.id)
        is_active  = existing_active.get(key)
        start_date = _parse_date(row.get('start_date'))
        leave_date = _parse_date(leave_date_str) if leave_date_str else None

        if leave_date:
            if is_active:
                db.session.execute(
                    student_course.update()
                    .where(student_course.c.student_id == student.id, student_course.c.course_id == course.id)
                    .values(leave_date=leave_date)
                )
                existing_active[key] = False
                dropped += 1
            elif is_active is None:
                # Row was never seen as active before (e.g. the student enrolled
                # and left before any prior upload) — still record it as history
                # instead of silently dropping it, so it shows up (as Inactive)
                # on the student's course list.
                db.session.execute(
                    student_course.insert().values(
                        student_id=student.id, course_id=course.id,
                        start_date=start_date, leave_date=leave_date,
                    )
                )
                existing_active[key] = False
        else:
            if is_active is None:
                db.session.execute(
                    student_course.insert().values(
                        student_id=student.id, course_id=course.id,
                        start_date=start_date, leave_date=None,
                    )
                )
                existing_active[key] = True
                enrolled += 1
            elif is_active is False:
                db.session.execute(
                    student_course.update()
                    .where(student_course.c.student_id == student.id, student_course.c.course_id == course.id)
                    .values(leave_date=None, start_date=start_date)
                )
                existing_active[key] = True
                enrolled += 1
            elif start_date:
                # Already actively enrolled — not a new enrollment, but backfill
                # start_date if this row has one and the stored row is missing it
                # (e.g. re-uploading after start_date support was added).
                db.session.execute(
                    student_course.update()
                    .where(student_course.c.student_id == student.id, student_course.c.course_id == course.id,
                           student_course.c.start_date.is_(None))
                    .values(start_date=start_date)
                )

    return enrolled, dropped, skipped_no_student, skipped_no_course


PARENTS_REQUIRED = ['first_name', 'last_name', 'relationship', 'stu_id']


ABSENCES_REQUIRED = ['stu_id', 'site_id', 'abs_date', 'schoolyr']


INCIDENTS_REQUIRED = ['stu_id', 'site_id', 'incident_id', 'incident_date', 'schoolyr']


def _process_absence_rows(rows):
    """Insert absence records from absences.csv. Returns (added, skipped)."""
    added = skipped = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, ABSENCES_REQUIRED), len(rows))

    # Site cache keyed by digits-only CDS
    all_sites  = Site.query.all()
    site_cache = {_normalize_siteid(s.site_cds): s.id for s in all_sites if s.site_cds}

    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    # Build stu_id → ssid lookup across all relevant school years
    school_years = {row.get('schoolyr', '').strip() for row in rows if row.get('schoolyr', '').strip()}
    stu_ids      = {row['stu_id'].strip() for row in rows if row.get('stu_id')}
    student_rows = (Student.query
                    .with_entities(Student.student_id, Student.ssid, Student.schoolyr)
                    .filter(Student.student_id.in_(stu_ids))
                    .all())
    # prefer ssid; fall back to student_id string so the absence still links
    ssid_map = {}
    for s in student_rows:
        ssid_map[(s.student_id, s.schoolyr)] = s.ssid or s.student_id

    # Build dedup set of existing absences: (site_id, ssid, abs_date, bell_period)
    site_ids_in_file = {site_cache[_normalize_siteid(r['site_id'])] for r in rows if r.get('site_id')}
    existing = db.session.query(
        Absence.site_id, Absence.ssid, Absence.abs_date, Absence.bell_period
    ).filter(Absence.site_id.in_(site_ids_in_file)).all()
    existing_set = {(r.site_id, r.ssid, r.abs_date, r.bell_period) for r in existing}

    for row in rows:
        site_norm = _normalize_siteid(row.get('site_id', ''))
        if not row.get('stu_id') or site_norm not in site_cache:
            skipped += 1
            continue

        site_id  = site_cache[site_norm]
        schoolyr = row.get('schoolyr', '').strip() or None
        stu_id   = row['stu_id'].strip()
        ssid     = ssid_map.get((stu_id, schoolyr)) or stu_id
        abs_date = _parse_date(row.get('abs_date'))
        period   = row.get('period', '').strip() or None

        if not abs_date:
            skipped += 1
            continue

        dedup_key = (site_id, ssid, abs_date, period)
        if dedup_key in existing_set:
            skipped += 1
            continue

        db.session.add(Absence(
            site_id    = site_id,
            ssid       = ssid,
            grade      = row.get('grade', '').strip() or None,
            abs_date   = abs_date,
            abs_desc   = row.get('abs_desc', '').strip() or None,
            bell_period= period,
            school_yr  = schoolyr,
        ))
        existing_set.add(dedup_key)
        added += 1

    return added, skipped


def _process_incident_rows(rows):
    """Insert behavioral incident records from behavioral_incidents.csv. Returns (added, skipped)."""
    added = skipped = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, INCIDENTS_REQUIRED), len(rows))

    # Site cache keyed by digits-only CDS
    all_sites  = Site.query.all()
    site_cache = {_normalize_siteid(s.site_cds): s for s in all_sites if s.site_cds}

    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    # Build stu_id → ssid lookup across all relevant school years
    stu_ids      = {row['stu_id'].strip() for row in rows if row.get('stu_id')}
    student_rows = (Student.query
                    .with_entities(Student.student_id, Student.ssid, Student.schoolyr)
                    .filter(Student.student_id.in_(stu_ids))
                    .all())
    # prefer ssid; fall back to student_id string so the incident still links
    ssid_map = {}
    for s in student_rows:
        ssid_map[(s.student_id, s.schoolyr)] = s.ssid or s.student_id

    # Dedup against existing incidents by incident_id
    existing_ids = {
        i.incident_id for i in
        db.session.query(Incident.incident_id).filter(Incident.incident_id.isnot(None)).all()
    }

    for row in rows:
        site_norm = _normalize_siteid(row.get('site_id', ''))
        if not row.get('stu_id') or site_norm not in site_cache:
            skipped += 1
            continue

        site_obj      = site_cache[site_norm]
        schoolyr      = row.get('schoolyr', '').strip() or None
        stu_id        = row['stu_id'].strip()
        sisid         = ssid_map.get((stu_id, schoolyr)) or stu_id
        incident_id   = row.get('incident_id', '').strip() or None
        incident_date = _parse_date(row.get('incident_date'))

        if not incident_date:
            skipped += 1
            continue

        if incident_id and incident_id in existing_ids:
            skipped += 1
            continue

        suspended_days = None
        raw_susp = row.get('suspension_days', '').strip()
        if raw_susp:
            try:
                suspended_days = float(raw_susp)
            except ValueError:
                suspended_days = None

        minor_flag = row.get('minor_incident', '').strip()
        major_flag = row.get('major_incident', '').strip()
        minor = 'Minor Incident' if minor_flag and minor_flag != '0' else None
        major = 'Major Incident' if major_flag and major_flag != '0' else None

        db.session.add(Incident(
            sisid         = sisid,
            site          = site_obj.site_acronyms,
            cds_code      = site_obj.site_cds,
            incident_id   = incident_id,
            incident_date = incident_date,
            schoolyr      = schoolyr,
            incident_time = row.get('incident_time', '').strip() or None,
            day_of_week   = incident_date.strftime('%A'),
            major         = major,
            minor         = minor,
            suspended_days= suspended_days,
        ))
        if incident_id:
            existing_ids.add(incident_id)
        added += 1

    return added, skipped


GRADES_REQUIRED = ['stu_id', 'site_id', 'section_id', 'term_code', 'course_yr']

_GRADE_TERM_TYPE = {'S': 'Semester', 'Q': 'Quarter', 'T': 'Trimester', 'M': 'Marking Period', 'Y': 'Full Year'}


def _parse_course_schoolyr(raw):
    """Convert a 4-digit ending calendar year (e.g. '2025') to 'YYYY-YYYY' school year format."""
    s = (raw or '').strip()
    if len(s) == 4 and s.isdigit():
        yr = int(s)
        return f"{yr - 1}-{yr}"
    return s or None


def _process_grades_rows(rows):
    """Insert or update student course grade records from grades.csv. Returns (added, updated, skipped)."""
    added = updated = skipped = 0

    _raise_if_row_errors(_row_missing_field_errors(rows, GRADES_REQUIRED), len(rows))

    # Site cache keyed by digits-only CDS
    all_sites  = Site.query.all()
    site_cache = {_normalize_siteid(s.site_cds): s for s in all_sites if s.site_cds}

    raw_siteids = {_normalize_siteid(row['site_id']) for row in rows if row.get('site_id')}
    missing_sites = [sid for sid in raw_siteids if sid not in site_cache]
    if missing_sites:
        raise ValueError(f"Site CDS code(s) not found in the system: {', '.join(missing_sites)}")

    # Match existing grade records by (student, section, term, school year) — update in place if found
    stu_ids  = {row['stu_id'].strip() for row in rows if row.get('stu_id')}
    existing = Grade.query.filter(Grade.grades_stuid.in_(stu_ids)).all()
    existing_map = {(g.grades_stuid, g.grades_coursenum, g.grades_term, g.grades_courseyr): g for g in existing}

    for row in rows:
        site_norm = _normalize_siteid(row.get('site_id', ''))
        if not row.get('stu_id') or site_norm not in site_cache:
            skipped += 1
            continue

        site_obj = site_cache[site_norm]
        stu_id   = row['stu_id'].strip()
        section  = row.get('section_id', '').strip() or None
        term     = row.get('term_code', '').strip() or None
        schoolyr = _parse_course_schoolyr(row.get('course_yr'))
        grade_type = _GRADE_TERM_TYPE.get((term or '')[-1:].upper())

        dedup_key = (stu_id, section, term, schoolyr)
        existing_grade = existing_map.get(dedup_key)
        if existing_grade:
            existing_grade.grades_schoolid  = site_obj.site_cds
            existing_grade.grades_grade     = row.get('mark', '').strip() or None
            existing_grade.grades_type      = grade_type
            existing_grade.grades_credatt   = _parse_float(row.get('credit_attempted'))
            existing_grade.grades_credcomp  = _parse_float(row.get('creadit_completed'))
            existing_grade.grades_currgrade = row.get('course_grade', '').strip() or None
            updated += 1
            continue

        new_grade = Grade(
            grades_stuid     = stu_id,
            grades_schoolid  = site_obj.site_cds,
            grades_coursenum = section,
            grades_courseyr  = schoolyr,
            grades_term      = term,
            grades_grade     = row.get('mark', '').strip() or None,
            grades_type      = grade_type,
            grades_credatt   = _parse_float(row.get('credit_attempted')),
            grades_credcomp  = _parse_float(row.get('creadit_completed')),
            grades_currgrade = row.get('course_grade', '').strip() or None,
        )
        db.session.add(new_grade)
        existing_map[dedup_key] = new_grade
        added += 1

    return added, updated, skipped


def _process_parents_rows(rows):
    """Upsert parents from parents.csv rows and link them to matching students (by stu_id, across all
    school years). Upserts on email when present, otherwise always inserts. Rows missing a required
    field or whose stu_id doesn't match a student are skipped rather than aborting the whole file.

    Returns (added, updated, skipped_missing_field, skipped_no_student), where the last two are lists
    of 1-indexed row numbers.
    """
    from collections import defaultdict

    added = updated = 0
    skipped_missing_field = []
    skipped_no_student = []

    stu_ids = {row['stu_id'].strip() for row in rows if row.get('stu_id', '').strip()}
    student_map = defaultdict(list)
    for s in Student.query.filter(Student.student_id.in_(stu_ids)).all():
        student_map[s.student_id].append(s)

    emails = {row['email'].strip().lower() for row in rows if row.get('email', '').strip()}
    existing_by_email = {
        p.email.strip().lower(): p for p in Parent.query.filter(Parent.email.isnot(None)).all()
        if p.email.strip().lower() in emails
    }

    for i, row in enumerate(rows, start=2):
        if any(not row.get(f, '').strip() for f in PARENTS_REQUIRED):
            skipped_missing_field.append(i)
            continue

        stu_id = row['stu_id'].strip()
        matched_students = student_map.get(stu_id, [])
        if not matched_students:
            skipped_no_student.append(i)
            continue

        email = row.get('email', '').strip() or None
        email_key = email.lower() if email else None

        existing = existing_by_email.get(email_key) if email_key else None
        if existing:
            existing.first_name   = row['first_name'].strip()
            existing.middle_name  = row.get('middle_name', '').strip() or None
            existing.last_name    = row['last_name'].strip()
            existing.relationship = row['relationship'].strip()
            existing.phone        = row.get('phone', '').strip() or None
            parent = existing
            updated += 1
        else:
            parent = Parent(
                first_name=row['first_name'].strip(),
                middle_name=row.get('middle_name', '').strip() or None,
                last_name=row['last_name'].strip(),
                relationship=row['relationship'].strip(),
                email=email,
                phone=row.get('phone', '').strip() or None,
            )
            db.session.add(parent)
            if email_key:
                existing_by_email[email_key] = parent
            added += 1

        for student in matched_students:
            if student not in parent.students:
                parent.students.append(student)

    return added, updated, skipped_missing_field, skipped_no_student


# ****************** Upload Users Page *******************************
@routes_blueprint.route('/bulk-data-upload', methods=['GET'])
@login_required
def upload_users():
    is_admin()
    log_page  = request.args.get('log_page', 1, type=int)
    per_page  = 10
    user_logs = BulkUploadLog.query.order_by(
        BulkUploadLog.uploaded_at.desc()
    ).paginate(page=log_page, per_page=per_page, error_out=False)
    org  = db.session.get(Organization, 1)
    ftp_host_plain     = ''
    ftp_username_plain = ''
    schedule_time = ''
    if org:
        key = current_app.config['DATA_ENCRYPTION_KEY']
        ftp_host_plain     = decrypt_mail_password(org.ftp_host_enc or '', key)
        ftp_username_plain = decrypt_mail_password(org.ftp_username_enc or '', key)
        if org.ftp_schedule_hour is not None:
            schedule_time = f"{org.ftp_schedule_hour:02d}:{org.ftp_schedule_minute or 0:02d}"
    return render_template('bulk_upload_data.html',
                           user_logs=user_logs,
                           org=org,
                           ftp_host_plain=ftp_host_plain,
                           ftp_username_plain=ftp_username_plain,
                           ftp_schedule_time=schedule_time,
                           current_page_name='Bulk Data Upload')


# ****************** Import Bulk Users *******************************
@routes_blueprint.route('/bulk-upload-users', methods=['POST'])
@login_required
def bulk_upload_users():
    is_admin()

    files = request.files.getlist('csvFile')
    files = [f for f in files if f and f.filename]
    if not files:
        flash('No file selected.', 'danger')
        return redirect(url_for('routes.upload_users'))

    for f in files:
        if not f.filename.lower().endswith('.csv'):
            flash(f'Invalid file: {f.filename}. Only .csv files are accepted.', 'danger')
            return redirect(url_for('routes.upload_users'))

    # Process sites → staff → demographics → absences → courses/master schedule → student schedules/parents → users
    def _sort_key(f):
        n = f.filename.lower()
        if n in ('sites.csv', 'site.csv'):               return 0
        if n == 'staff.csv':                              return 1
        if n == 'demographics.csv':                       return 2
        if n == 'absences.csv':                           return 3
        if n == 'behavioral_incidents.csv':               return 3
        if n in ('courses.csv', 'master_schedule.csv'):   return 4
        if n == 'grades.csv':                             return 5
        if n in ('students_schedule.csv', 'parents.csv'): return 5
        return 6
    files.sort(key=_sort_key)

    flash_messages = []
    grad_recompute_needed = False

    for file in files:
        filename = secure_filename(file.filename)
        is_sites            = filename.lower() in ('sites.csv', 'site.csv')
        is_demographics      = filename.lower() == 'demographics.csv'
        is_staff             = filename.lower() == 'staff.csv'
        is_absences          = filename.lower() == 'absences.csv'
        is_incidents          = filename.lower() == 'behavioral_incidents.csv'
        is_grades             = filename.lower() == 'grades.csv'
        is_courses           = filename.lower() == 'courses.csv'
        is_master_schedule   = filename.lower() == 'master_schedule.csv'
        is_student_schedule  = filename.lower() == 'students_schedule.csv'
        is_parents           = filename.lower() == 'parents.csv'
        is_users             = filename.lower() == 'users.csv'
        log_tag = (
            '[Sites] ' if is_sites else
            '[Demographics] ' if is_demographics else
            '[Staff] ' if is_staff else
            '[Absences] ' if is_absences else
            '[Incidents] ' if is_incidents else
            '[Grades] ' if is_grades else
            '[Courses] ' if is_courses else
            '[Master Schedule] ' if is_master_schedule else
            '[Student Schedule] ' if is_student_schedule else
            '[Parents] ' if is_parents else ''
        )
        added = updated = total = 0

        try:
            if not (is_sites or is_demographics or is_staff or is_absences or is_incidents or is_grades
                    or is_courses or is_master_schedule or is_student_schedule or is_parents or is_users):
                raise ValueError(
                    f"'{filename}' is not a supported upload type. "
                    "Supported files: sites.csv, demographics.csv, staff.csv, absences.csv, "
                    "behavioral_incidents.csv, courses.csv, master_schedule.csv, students_schedule.csv, "
                    "parents.csv, grades.csv, users.csv."
                )

            raw = file.stream.read()
            try:
                stream = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                stream = raw.decode('latin-1')
            rows = list(csv.DictReader(stream.splitlines()))
            total = len(rows)

            if is_sites:
                added, updated = _process_sites_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Sites] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                flash_messages.append(f'Sites: {added} added, {updated} updated.')
            elif is_demographics:
                added, updated, skipped = _process_student_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Demographics] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                msg = f'Demographics: {added} added, {updated} updated.'
                if skipped:
                    msg += f' {skipped} skipped.'
                flash_messages.append(msg)
            elif is_absences:
                added, skipped = _process_absence_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Absences] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=0,
                    status='success'
                ))
                db.session.commit()
                msg = f'Absences: {added} added.'
                if skipped:
                    msg += f' {skipped} skipped (duplicates or missing date).'
                flash_messages.append(msg)
            elif is_incidents:
                added, skipped = _process_incident_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Incidents] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=0,
                    status='success'
                ))
                db.session.commit()
                msg = f'Behavioral Incidents: {added} added.'
                if skipped:
                    msg += f' {skipped} skipped (duplicates or missing date).'
                flash_messages.append(msg)
            elif is_staff:
                added, updated = _process_staff_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Staff] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                flash_messages.append(f'Staff: {added} added, {updated} updated.')
            elif is_courses:
                added, updated = _process_courses_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Courses] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                grad_recompute_needed = True
                flash_messages.append(f'Courses: {added} added, {updated} updated.')
            elif is_master_schedule:
                added, updated = _process_master_schedule_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Master Schedule] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                grad_recompute_needed = True
                flash_messages.append(f'Master Schedule: {added} added, {updated} updated.')
            elif is_student_schedule:
                enrolled, dropped, skipped_no_student, skipped_no_course = _process_student_schedule_rows(rows)
                skip_parts = [
                    p for p in (
                        _format_skip_summary('student not found', skipped_no_student),
                        _format_skip_summary('section not found', skipped_no_course),
                    ) if p
                ]
                skip_detail = ' '.join(skip_parts) or None
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Student Schedule] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=enrolled,
                    users_updated=dropped,
                    status='success',
                    error_message=skip_detail
                ))
                db.session.commit()
                msg = f'Student Schedule: {enrolled} enrolled, {dropped} dropped.'
                if skip_detail:
                    msg += ' ' + skip_detail
                flash_messages.append(msg)
            elif is_parents:
                added, updated, skipped_missing_field, skipped_no_student = _process_parents_rows(rows)
                skip_parts = [
                    p for p in (
                        _format_skip_summary('missing a required field', skipped_missing_field),
                        _format_skip_summary('student not found', skipped_no_student),
                    ) if p
                ]
                skip_detail = ' '.join(skip_parts) or None
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Parents] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success',
                    error_message=skip_detail
                ))
                db.session.commit()
                msg = f'Parents: {added} added, {updated} updated.'
                if skip_detail:
                    msg += ' ' + skip_detail
                flash_messages.append(msg)
            elif is_grades:
                added, updated, skipped = _process_grades_rows(rows)
                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=f'[Grades] {filename}',
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                grad_recompute_needed = True
                msg = f'Grades: {added} added, {updated} updated.'
                if skipped:
                    msg += f' {skipped} skipped (unknown site or missing student ID).'
                flash_messages.append(msg)
            else:
                # Build site lookup cache and validate all rows, collecting every problem row
                USERS_REQUIRED = ('first_name', 'last_name', 'email', 'role_id', 'site_name', 'rm_num')
                csv_emails = set()
                site_cache = {}
                row_errors = []
                for i, row in enumerate(rows, start=2):
                    missing = [f for f in USERS_REQUIRED if not row.get(f, '').strip()]
                    if missing:
                        row_errors.append(f"Row {i}: missing {', '.join(missing)}")
                        continue
                    name = row['site_name'].strip()
                    if name not in site_cache:
                        site = Site.query.filter_by(site_name=name).first()
                        site_cache[name] = site.id if site else None
                        if not site:
                            row_errors.append(f"Row {i}: site '{name}' not found")
                    if site_cache[name] is None:
                        continue
                    csv_emails.add(row['email'].strip())
                _raise_if_row_errors(row_errors, len(rows))

                # Upsert users
                _bulk_key = current_app.config['SECRET_KEY']
                for row in rows:
                    site_id = site_cache[row['site_name'].strip()]
                    existing_user = User.query.filter_by(email_hash=hash_email(row['email'].strip(), _bulk_key)).first()
                    if existing_user:
                        existing_user.first_name  = row['first_name']
                        existing_user.middle_name = row.get('middle_name') or None
                        existing_user.last_name   = row['last_name']
                        existing_user.rm_num      = row.get('rm_num') or existing_user.rm_num
                        existing_user.role_id     = int(row['role_id'])
                        existing_user.site_id     = site_id
                        existing_user.status      = row.get('status') or 'Active'
                        updated += 1
                    else:
                        db.session.add(User(
                            first_name=row['first_name'],
                            middle_name=row.get('middle_name') or None,
                            last_name=row['last_name'],
                            email=row['email'].strip(),
                            status=row.get('status') or 'Active',
                            password=generate_password_hash(secrets.token_urlsafe(16)),
                            must_change_password=True,
                            rm_num=row.get('rm_num') or None,
                            role_id=int(row['role_id']),
                            site_id=site_id
                        ))
                        added += 1

                # Flush pending inserts/updates, then deactivate absent users
                db.session.flush()
                csv_email_hashes = {hash_email(e, _bulk_key) for e in csv_emails}
                deactivated = User.query.filter(
                    User.status == 'Active',
                    ~User.email_hash.in_(csv_email_hashes)
                ).update({'status': 'Inactive'}, synchronize_session=False)

                db.session.commit()
                db.session.add(BulkUploadLog(
                    filename=filename,
                    uploaded_by_id=current_user.id,
                    total_records=total,
                    users_added=added,
                    users_updated=updated,
                    status='success'
                ))
                db.session.commit()
                msg = f'Users: {added} added, {updated} updated.'
                if deactivated:
                    msg += f' {deactivated} marked Inactive (not in file).'
                flash_messages.append(msg)

        except ValueError as e:
            db.session.rollback()
            db.session.add(BulkUploadLog(
                filename=f'{log_tag}{filename}',
                uploaded_by_id=current_user.id,
                total_records=total,
                users_added=added,
                users_updated=updated,
                status='error',
                error_message=str(e)
            ))
            db.session.commit()
            flash(f'Error processing {filename}: {e}', 'danger')
            return redirect(url_for('routes.upload_users'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Bulk upload failed for {filename}: {e}", exc_info=True)
            db.session.add(BulkUploadLog(
                filename=f'{log_tag}{filename}',
                uploaded_by_id=current_user.id,
                total_records=total,
                users_added=added,
                users_updated=updated,
                status='error',
                # Not the raw exception: it can embed row data (names, emails, etc.) via the
                # SQL/params repr, and this message is displayed in the Upload Log UI. Full
                # details are in the server log above.
                error_message='An unexpected error occurred while processing this file. See server logs for details.'
            ))
            db.session.commit()
            flash(f'An unexpected error occurred while processing {filename}.', 'danger')
            return redirect(url_for('routes.upload_users'))

    if grad_recompute_needed:
        _recompute_grad_subject_credits()

    if flash_messages:
        flash(' | '.join(flash_messages), 'success')

    return redirect(url_for('routes.upload_users'))


# ****************** FTP Bulk Upload Users *******************************
@routes_blueprint.route('/ftp-settings/save', methods=['POST'])
@login_required
def ftp_save_settings():
    """Save FTP credentials and schedule settings into the Organization record."""
    is_admin()
    org = Organization.query.get_or_404(1)
    key = current_app.config['DATA_ENCRYPTION_KEY']

    # --- Credentials ---
    raw_host = re.sub(r'^ftps?://', '', request.form.get('ftp_host', '').strip(), flags=re.IGNORECASE)
    username = request.form.get('ftp_username', '').strip()
    password = request.form.get('ftp_password', '').strip()
    if raw_host:
        org.ftp_host_enc = encrypt_mail_password(raw_host, key)
    if username:
        org.ftp_username_enc = encrypt_mail_password(username, key)
    if password:
        org.ftp_password_enc = encrypt_mail_password(password, key)
    org.ftp_port    = int(request.form.get('ftp_port') or 21)
    org.ftp_path    = request.form.get('ftp_path', '').strip() or None
    org.ftp_use_tls = request.form.get('ftp_use_tls') == 'on'

    # --- Schedule ---
    schedule_enabled = request.form.get('ftp_schedule_enabled') == 'on'
    org.ftp_schedule_enabled = schedule_enabled
    if schedule_enabled:
        schedule_time = (request.form.get('ftp_schedule_time') or '00:00').strip()
        try:
            hour, minute = map(int, schedule_time.split(':'))
        except ValueError:
            hour, minute = 0, 0
        days_list = request.form.getlist('ftp_schedule_days')
        all_days  = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
        org.ftp_schedule_hour   = hour
        org.ftp_schedule_minute = minute
        org.ftp_schedule_days   = '*' if not days_list or set(days_list) >= all_days else ','.join(days_list)

    from datetime import date as _date
    for attr, field in [('ftp_schedule_start_date', 'ftp_schedule_start_date'),
                        ('ftp_schedule_stop_date',  'ftp_schedule_stop_date')]:
        raw = request.form.get(field, '').strip()
        try:
            setattr(org, attr, _date.fromisoformat(raw) if raw else None)
        except ValueError:
            setattr(org, attr, None)

    db.session.add(org)
    db.session.commit()

    # Sync APScheduler job (non-fatal if scheduler unavailable)
    try:
        from application.scheduled_jobs import run_org_ftp_schedule
        if schedule_enabled and org.ftp_schedule_hour is not None:
            scheduler.add_job(
                id='org_ftp_schedule',
                func=run_org_ftp_schedule,
                trigger='cron',
                day_of_week=org.ftp_schedule_days,
                hour=org.ftp_schedule_hour,
                minute=org.ftp_schedule_minute,
                replace_existing=True
            )
        else:
            try:
                scheduler.remove_job('org_ftp_schedule')
            except Exception:
                pass
    except Exception:
        pass

    if schedule_enabled:
        flash('FTP settings and schedule saved.', 'success')
    else:
        flash('FTP settings saved. Schedule disabled.', 'success')

    return redirect(url_for('routes.upload_users') + '?tab=ftp')


@routes_blueprint.route('/ftp-upload-users', methods=['POST'])
@login_required
def ftp_bulk_upload_users():
    is_admin()

    ftp_host     = re.sub(r'^ftps?://', '', request.form.get('ftp_host', '').strip(), flags=re.IGNORECASE)
    ftp_port     = request.form.get('ftp_port', '21').strip()
    ftp_username = request.form.get('ftp_username', '').strip()
    ftp_path     = request.form.get('ftp_path', '').strip()
    use_tls      = request.form.get('ftp_use_tls') == 'on'
    ftp_password = request.form.get('ftp_password', '').strip()

    # data_key decrypts FTP credentials (data at rest); secret_key hashes emails for the
    # User lookup index further down in this function — deliberately different keys, see
    # utils.py. Declared unconditionally since secret_key is needed below regardless of
    # whether `org` has saved FTP credentials to fall back to.
    data_key   = current_app.config['DATA_ENCRYPTION_KEY']
    secret_key = current_app.config['SECRET_KEY']

    # Fall back to saved org credentials (decrypt) if form fields are blank
    org = db.session.get(Organization, 1)
    if org:
        if not ftp_host and org.ftp_host_enc:
            ftp_host = decrypt_mail_password(org.ftp_host_enc, data_key)
        if not ftp_username and org.ftp_username_enc:
            ftp_username = decrypt_mail_password(org.ftp_username_enc, data_key)
        if not ftp_password and org.ftp_password_enc:
            ftp_password = decrypt_mail_password(org.ftp_password_enc, data_key)
        ftp_path = ftp_path or (org.ftp_path or '')
        ftp_port = ftp_port or str(org.ftp_port or 21)
        use_tls  = use_tls  or bool(org.ftp_use_tls)

    if not all([ftp_host, ftp_username, ftp_path]):
        flash('FTP host, username, and remote directory are required.', 'danger')
        return redirect(url_for('routes.upload_users') + '?tab=ftp')

    try:
        port = int(ftp_port)
    except ValueError:
        flash('FTP port must be a valid number.', 'danger')
        return redirect(url_for('routes.upload_users') + '?tab=ftp')

    # Normalise: if the stored path still has a .csv filename (old format), strip it
    if ftp_path.lower().endswith('.csv'):
        import posixpath as _pp
        ftp_path = _pp.dirname(ftp_path)
    ftp_dir = ftp_path.rstrip('/')
    users_path              = f'{ftp_dir}/users.csv'
    sites_path              = f'{ftp_dir}/sites.csv'
    demographics_path       = f'{ftp_dir}/demographics.csv'
    staff_path               = f'{ftp_dir}/staff.csv'
    courses_path             = f'{ftp_dir}/courses.csv'
    master_schedule_path     = f'{ftp_dir}/master_schedule.csv'
    students_schedule_path   = f'{ftp_dir}/students_schedule.csv'
    parents_path             = f'{ftp_dir}/parents.csv'

    users_added = users_updated = users_deactivated = total_records = 0
    sites_added = sites_updated = sites_total = 0
    demographics_added = demographics_updated = demographics_skipped = demographics_total = 0
    staff_added = staff_updated = staff_total = 0
    courses_added = courses_updated = courses_total = 0
    master_added = master_updated = master_total = 0
    sched_enrolled = sched_dropped = sched_total = 0
    sched_skip_detail = None
    parents_added = parents_updated = parents_total = 0
    parents_skip_detail = None
    grad_recompute_needed = False

    try:
        ftp = ftplib.FTP_TLS() if use_tls else ftplib.FTP()
        ftp.connect(ftp_host, port, timeout=30)
        ftp.login(ftp_username, ftp_password)
        if use_tls:
            ftp.prot_p()

        # --- Download and process sites.csv first ---
        sites_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {sites_path}', sites_buf.write)
            sites_buf.seek(0)
            _sites_raw = sites_buf.read()
            try:
                _sites_text = _sites_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _sites_text = _sites_raw.decode('latin-1')
            site_rows   = list(csv.DictReader(_sites_text.splitlines()))
            sites_total = len(site_rows)
            sites_added, sites_updated = _process_sites_rows(site_rows)
            db.session.commit()
            db.session.add(BulkUploadLog(
                filename='[FTP Sites] sites.csv',
                uploaded_by_id=current_user.id,
                total_records=sites_total,
                users_added=sites_added,
                users_updated=sites_updated,
                status='success'
            ))
            db.session.commit()
        except ftplib.error_perm:
            pass  # sites.csv not found on server — skip silently

        # --- Download and process demographics.csv (optional) ---
        demo_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {demographics_path}', demo_buf.write)
            demo_buf.seek(0)
            _demo_raw = demo_buf.read()
            try:
                _demo_text = _demo_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _demo_text = _demo_raw.decode('latin-1')
            demo_rows = list(csv.DictReader(_demo_text.splitlines()))
            demographics_total = len(demo_rows)
            demographics_added, demographics_updated, demographics_skipped = _process_student_rows(demo_rows)
            db.session.commit()
            db.session.add(BulkUploadLog(
                filename='[FTP Demographics] demographics.csv',
                uploaded_by_id=current_user.id,
                total_records=demographics_total,
                users_added=demographics_added,
                users_updated=demographics_updated,
                status='success'
            ))
            db.session.commit()
        except ftplib.error_perm:
            pass  # demographics.csv not found on server — skip silently

        # --- Download and process staff.csv (optional) ---
        staff_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {staff_path}', staff_buf.write)
            staff_buf.seek(0)
            _staff_raw = staff_buf.read()
            try:
                _staff_text = _staff_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _staff_text = _staff_raw.decode('latin-1')
            staff_rows = list(csv.DictReader(_staff_text.splitlines()))
            staff_total = len(staff_rows)
            staff_added, staff_updated = _process_staff_rows(staff_rows)
            db.session.commit()
            db.session.add(BulkUploadLog(
                filename='[FTP Staff] staff.csv',
                uploaded_by_id=current_user.id,
                total_records=staff_total,
                users_added=staff_added,
                users_updated=staff_updated,
                status='success'
            ))
            db.session.commit()
        except ftplib.error_perm:
            pass  # staff.csv not found on server — skip silently

        # --- Download and process courses.csv (optional) ---
        courses_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {courses_path}', courses_buf.write)
            courses_buf.seek(0)
            _courses_raw = courses_buf.read()
            try:
                _courses_text = _courses_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _courses_text = _courses_raw.decode('latin-1')
            courses_rows = list(csv.DictReader(_courses_text.splitlines()))
            courses_total = len(courses_rows)
            courses_added, courses_updated = _process_courses_rows(courses_rows)
            db.session.commit()
            db.session.add(BulkUploadLog(
                filename='[FTP Courses] courses.csv',
                uploaded_by_id=current_user.id,
                total_records=courses_total,
                users_added=courses_added,
                users_updated=courses_updated,
                status='success'
            ))
            db.session.commit()
            grad_recompute_needed = True
        except ftplib.error_perm:
            pass  # courses.csv not found on server — skip silently

        # --- Download and process master_schedule.csv (optional) ---
        master_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {master_schedule_path}', master_buf.write)
            master_buf.seek(0)
            _master_raw = master_buf.read()
            try:
                _master_text = _master_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _master_text = _master_raw.decode('latin-1')
            master_rows = list(csv.DictReader(_master_text.splitlines()))
            master_total = len(master_rows)
            master_added, master_updated = _process_master_schedule_rows(master_rows)
            db.session.commit()
            db.session.add(BulkUploadLog(
                filename='[FTP Master Schedule] master_schedule.csv',
                uploaded_by_id=current_user.id,
                total_records=master_total,
                users_added=master_added,
                users_updated=master_updated,
                status='success'
            ))
            db.session.commit()
            grad_recompute_needed = True
        except ftplib.error_perm:
            pass  # master_schedule.csv not found on server — skip silently

        # courses.csv / master_schedule.csv can change how a course maps to a subject area,
        # so the Graduation Status summary table needs a refresh if either one landed.
        if grad_recompute_needed:
            _recompute_grad_subject_credits()

        # --- Download and process students_schedule.csv (optional) ---
        sched_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {students_schedule_path}', sched_buf.write)
            sched_buf.seek(0)
            _sched_raw = sched_buf.read()
            try:
                _sched_text = _sched_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _sched_text = _sched_raw.decode('latin-1')
            sched_rows = list(csv.DictReader(_sched_text.splitlines()))
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
                filename='[FTP Student Schedule] students_schedule.csv',
                uploaded_by_id=current_user.id,
                total_records=sched_total,
                users_added=sched_enrolled,
                users_updated=sched_dropped,
                status='success',
                error_message=sched_skip_detail
            ))
            db.session.commit()
        except ftplib.error_perm:
            pass  # students_schedule.csv not found on server — skip silently

        # --- Download and process parents.csv (optional) ---
        parents_buf = io.BytesIO()
        try:
            ftp.retrbinary(f'RETR {parents_path}', parents_buf.write)
            parents_buf.seek(0)
            _parents_raw = parents_buf.read()
            try:
                _parents_text = _parents_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _parents_text = _parents_raw.decode('latin-1')
            parents_rows = list(csv.DictReader(_parents_text.splitlines()))
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
                filename='[FTP Parents] parents.csv',
                uploaded_by_id=current_user.id,
                total_records=parents_total,
                users_added=parents_added,
                users_updated=parents_updated,
                status='success',
                error_message=parents_skip_detail
            ))
            db.session.commit()
        except ftplib.error_perm:
            pass  # parents.csv not found on server — skip silently

        # --- Download and process users.csv ---
        users_found = True
        try:
            user_buf = io.BytesIO()
            ftp.retrbinary(f'RETR {users_path}', user_buf.write)
        except ftplib.error_perm:
            users_found = False  # users.csv not found on server — skip silently

        ftp.quit()

        if users_found:
            user_buf.seek(0)
            _user_raw = user_buf.read()
            try:
                _user_text = _user_raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                _user_text = _user_raw.decode('latin-1')
            rows = list(csv.DictReader(_user_text.splitlines()))
            total_records = len(rows)

            # First pass: validate all rows and collect emails
            csv_emails = set()
            for row in rows:
                if not all([row.get('first_name'), row.get('last_name'), row.get('email'),
                            row.get('role_id'), row.get('site_name'), row.get('rm_num')]):
                    raise ValueError('Some rows in the CSV file are missing required fields.')
                site = Site.query.filter_by(site_name=row['site_name']).first()
                if not site:
                    raise ValueError(f"Site '{row['site_name']}' not found. Please verify the CSV file.")
                csv_emails.add(row['email'].strip().lower())

            # Second pass: upsert users
            for row in rows:
                site = Site.query.filter_by(site_name=row['site_name']).first()
                existing_user = User.query.filter_by(email_hash=hash_email(row['email'].strip(), secret_key)).first()
                if existing_user:
                    existing_user.first_name  = row['first_name']
                    existing_user.middle_name = row.get('middle_name') or None
                    existing_user.last_name   = row['last_name']
                    existing_user.rm_num      = row.get('rm_num') or existing_user.rm_num
                    existing_user.role_id     = int(row['role_id'])
                    existing_user.site_id     = site.id
                    existing_user.status      = row.get('status') or 'Active'
                    users_updated += 1
                else:
                    db.session.add(User(
                        first_name=row['first_name'],
                        middle_name=row.get('middle_name', None),
                        last_name=row['last_name'],
                        email=row['email'].strip(),
                        status=row.get('status', 'Active'),
                        password=generate_password_hash(secrets.token_urlsafe(16)),
                        must_change_password=True,
                        rm_num=row.get('rm_num', None),
                        role_id=row['role_id'],
                        site_id=site.id
                    ))
                    users_added += 1

            # Third pass: deactivate users absent from the CSV
            ftp_csv_hashes = {hash_email(e, secret_key) for e in csv_emails}
            for user in User.query.filter(User.status == 'Active').all():
                if user.email_hash not in ftp_csv_hashes:
                    user.status = 'Inactive'
                    users_deactivated += 1

            db.session.commit()

            db.session.add(BulkUploadLog(
                filename='[FTP] users.csv',
                uploaded_by_id=current_user.id,
                total_records=total_records,
                users_added=users_added,
                users_updated=users_updated,
                status='success'
            ))
            db.session.commit()

        if users_found:
            msg = f'FTP import successful: {users_added} users added, {users_updated} updated.'
            if users_deactivated:
                msg += f' {users_deactivated} marked Inactive (not in file).'
        else:
            msg = 'FTP import successful.'
        if sites_total:
            msg += f' Sites: {sites_added} added, {sites_updated} updated.'
        if demographics_total:
            demo_msg = f' Demographics: {demographics_added} added, {demographics_updated} updated.'
            if demographics_skipped:
                demo_msg += f' {demographics_skipped} skipped.'
            msg += demo_msg
        if staff_total:
            msg += f' Staff: {staff_added} added, {staff_updated} updated.'
        if courses_total:
            msg += f' Courses: {courses_added} added, {courses_updated} updated.'
        if master_total:
            msg += f' Master Schedule: {master_added} added, {master_updated} updated.'
        if sched_total:
            sched_msg = f' Student Schedule: {sched_enrolled} enrolled, {sched_dropped} dropped.'
            if sched_skip_detail:
                sched_msg += ' ' + sched_skip_detail
            msg += sched_msg
        if parents_total:
            parents_msg = f' Parents: {parents_added} added, {parents_updated} updated.'
            if parents_skip_detail:
                parents_msg += ' ' + parents_skip_detail
            msg += parents_msg
        flash(msg, 'success')

    except (ftplib.Error, OSError, EOFError, UnicodeDecodeError, ValueError) as e:
        db.session.rollback()
        if isinstance(e, socket.gaierror):
            friendly = f"Cannot reach FTP host '{ftp_host}'. Check that the hostname is correct and the server is reachable."
        elif isinstance(e, ConnectionRefusedError):
            friendly = f"Connection refused by '{ftp_host}:{port}'. Check the port number and that the FTP service is running."
        elif isinstance(e, TimeoutError):
            friendly = f"Connection to '{ftp_host}' timed out. The server may be down or blocked by a firewall."
        elif isinstance(e, ftplib.error_perm):
            msg_lower = str(e)
            if any(code in msg_lower for code in ('530', '331', '332')):
                friendly = 'FTP login failed. Check your username and password.'
            else:
                friendly = f'FTP error: {e}'
        else:
            friendly = str(e)
        try:
            db.session.add(BulkUploadLog(
                filename='[FTP] users.csv',
                uploaded_by_id=current_user.id,
                total_records=total_records,
                users_added=users_added,
                users_updated=users_updated,
                status='error',
                error_message=friendly
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash(friendly, 'danger')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'FTP bulk upload unexpected error: {e}', exc_info=True)
        flash('An unexpected error occurred during the FTP import.', 'danger')

    return redirect(url_for('routes.upload_users'))


# ****************** Bulk Upload Sites (CSV) *******************************
@routes_blueprint.route('/bulk-upload-sites', methods=['POST'])
@login_required
def bulk_upload_sites():
    is_admin()

    if 'csvFile' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('routes.upload_users') + '?tab=sites')

    file = request.files['csvFile']
    if not file or file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('routes.upload_users') + '?tab=sites')

    if not file.filename.lower().endswith('.csv'):
        flash('Invalid file format. Please upload a CSV file.', 'danger')
        return redirect(url_for('routes.upload_users') + '?tab=sites')

    sites_added = sites_updated = total_records = 0
    filename = secure_filename(file.filename)

    try:
        stream = file.read().decode('utf-8')
        rows = list(csv.DictReader(stream.splitlines()))
        total_records = len(rows)
        if total_records == 0:
            flash('The CSV file is empty.', 'warning')
            return redirect(url_for('routes.upload_users') + '?tab=sites')

        sites_added, sites_updated = _process_sites_rows(rows)
        db.session.commit()

        db.session.add(BulkUploadLog(
            filename=f'[Sites] {filename}',
            uploaded_by_id=current_user.id,
            total_records=total_records,
            users_added=sites_added,
            users_updated=sites_updated,
            status='success'
        ))
        db.session.commit()
        flash(f'Sites import successful: {sites_added} added, {sites_updated} updated.', 'success')

    except UnicodeDecodeError as e:
        db.session.rollback()
        current_app.logger.error(f"Sites CSV encoding error for {filename}: {e}", exc_info=True)
        db.session.add(BulkUploadLog(
            filename=f'[Sites] {filename}',
            uploaded_by_id=current_user.id,
            total_records=total_records,
            users_added=sites_added,
            users_updated=sites_updated,
            status='error',
            error_message=str(e)
        ))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash('Sites import failed: file encoding not supported. Please save the CSV as UTF-8.', 'danger')

    except ValueError as e:
        db.session.rollback()
        db.session.add(BulkUploadLog(
            filename=f'[Sites] {filename}',
            uploaded_by_id=current_user.id,
            total_records=total_records,
            users_added=sites_added,
            users_updated=sites_updated,
            status='error',
            error_message=str(e)
        ))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash(f'Sites import failed: {e}', 'danger')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Bulk upload sites unexpected error: {e}', exc_info=True)
        flash('An unexpected error occurred during the sites import.', 'danger')

    return redirect(url_for('routes.upload_users') + '?tab=sites')


# *********************************************************************
# ****************** Role Management Page *******************************
@routes_blueprint.route('/roles')
@login_required
def roles():
        # Mapping paths to page names
    page_names = {'/roles': 'Manage User Roles'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    # Get the page number and per_page from the query parameters, default to 10 for per_page
    page, per_page, offset = get_page_args(page_parameter="page", per_page_parameter="per_page")
    # Query the users
    total = Role.query.count()
    roles = Role.query.order_by(Role.id.asc()).offset(offset).limit(per_page).all()    
    # Set up pagination with Bootstrap 5 styling
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    return render_template('roles.html', roles=roles, pagination=pagination, per_page=per_page, total=total, 
        current_path=current_path, 
        current_page_name=current_page_name
    )

# ****************** Add New Role Page *******************************
@routes_blueprint.route('/add_role', methods=['GET', 'POST'])
@login_required
def add_role():
            # Mapping paths to page names
    page_names = {'/add_role': 'New Role'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    form = RoleForm()
    if form.validate_on_submit():
        # Check if a role with the same name already exists
        existing_role = Role.query.filter_by(role_name=form.role_name.data).first()
        if existing_role:
            flash('This role already exists.', 'danger')
            return render_template('add_role.html', form=form)  # Re-render form with the error message
        # Create and add the new role
        new_role = Role(
            role_name=form.role_name.data
        )
        db.session.add(new_role)
        db.session.commit()
        flash('Role added successfully!', 'success')
        return redirect(url_for('routes.roles'))
    return render_template('add_role.html', form=form,
        current_path=current_path, 
        current_page_name=current_page_name)

# ****************** Edit Role Page *******************************
@routes_blueprint.route('/edit_role/<int:role_id>', methods=['GET', 'POST'])
@login_required
def edit_role(role_id):
    is_admin()  # Ensure only admins can access this route
    
    # Restrict editing roles with IDs 1, 2, 3, 4, 5
    if role_id in {1, 2, 3, 4, 5}:
        flash('You are not allowed to edit this role.', 'danger')
        return redirect(url_for('routes.roles'))

    role = Role.query.get_or_404(role_id)
    form = RoleForm(obj=role)
    if form.validate_on_submit():
        # Check for duplicate entries
        existing_role = Role.query.filter(Role.role_name == form.role_name.data, Role.id != role.id).first()
        if existing_role:
            flash('This role already exists.', 'danger')
            return render_template('add_role.html', form=form)  # Re-render form with the error message
        # Check if there are any changes to the form
        if (
            role.role_name == form.role_name.data
        ):
            flash('No changes were made.', 'info')
            return render_template('edit_role.html', form=form, role=role)
        role.role_name = form.role_name.data
        db.session.commit()
        flash('Role updated successfully!', 'success')
        return redirect(url_for('routes.roles'))
    return render_template('edit_role.html', form=form, role=role)


# ****************** Delete Role Page *******************************
@routes_blueprint.route('/delete_role/<int:role_id>', methods=['POST'])
@login_required
def delete_role(role_id):
    is_admin()  # Ensure only admins can access this route

    # Restrict deleting roles with IDs 1, 2, 3, 4, 5
    if role_id in {1, 2, 3, 4, 5}:
        flash('You are not allowed to delete this role.', 'danger')
        return redirect(url_for('routes.roles'))
    
    role = Role.query.get_or_404(role_id)
    db.session.delete(role)
    db.session.commit()
    flash('Role deleted successfully!', 'warning')
    return redirect(url_for('routes.roles'))


# *********************************************************************
# ****************** Site Management Page *******************************
@routes_blueprint.route('/sites', methods=['GET'])
@login_required
def sites():
        # Mapping paths to page names
    page_names = {'/sites': 'Manage Sites'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    # Get the page number and per_page from the query parameters, default to 10 for per_page
    page, per_page, offset = get_page_args(page_parameter="page", per_page_parameter="per_page")
    # Query the users
    total = Site.query.count()
    sites = Site.query.order_by(Site.id.asc()).offset(offset).limit(per_page).all()
    # Set up pagination with Bootstrap 5 styling
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    return render_template('sites.html', sites=sites, pagination=pagination, per_page=per_page, total=total, 
        current_path=current_path, 
        current_page_name=current_page_name
    )

# ****************** Add New Site Page *******************************
@routes_blueprint.route('/add_site', methods=['GET', 'POST'])
@login_required
def add_site():
            # Mapping paths to page names
    page_names = {'/add_site': 'New Site'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    form = SiteForm()
    if form.validate_on_submit():
        # Check if a role with the same name already exists
        existing_site = Site.query.filter_by(site_cds=form.site_cds.data).first()
        if existing_site:
            flash('This site already exists.', 'danger')
            return render_template('add_site.html', form=form)  # Re-render form with the error message
        new_site = Site(
            site_name=form.site_name.data,
            site_acronyms=form.site_acronyms.data,
            site_code=form.site_code.data,
            site_cds=form.site_cds.data,
            site_address=form.site_address.data,
            site_type=form.site_type.data,
            site_city=form.site_city.data,
            site_state=form.site_state.data,
            site_zip=form.site_zip.data,
            principal_first_name=form.principal_first_name.data,
            principal_last_name=form.principal_last_name.data,
            principal_email=form.principal_email.data,
            principal_phone=form.principal_phone.data,
        )
        db.session.add(new_site)
        db.session.commit()
        flash('Site added successfully!', 'success')
        return redirect(url_for('routes.sites'))
    # Pass None for site to differentiate between add and edit
    return render_template('add_site.html', form=form,
        current_path=current_path, 
        current_page_name=current_page_name
    )


# ****************** Edit Site Page *******************************
@routes_blueprint.route('/edit_site/<int:site_id>', methods=['GET', 'POST'])
@login_required
def edit_site(site_id):
    is_admin()  # Ensure only admins can access this route
    site = Site.query.get_or_404(site_id)
    form = SiteForm(obj=site)
    if form.validate_on_submit():
        # Check if a role with the same name already exists
        existing_site = Site.query.filter(Site.site_cds == form.site_cds.data, Site.id != site.id).first()
        if existing_site:
            flash('This site already exists.', 'danger')
            return render_template('add_site.html', form=form)  # Re-render form with the error message
        # Check if there are any changes to the form
        if (
            site.site_name == form.site_name.data and
            site.site_acronyms == form.site_acronyms.data and
            site.site_code == form.site_code.data and
            site.site_cds == form.site_cds.data and
            site.site_address == form.site_address.data and
            site.site_type == form.site_type.data and
            site.site_city == form.site_city.data and
            site.site_state == form.site_state.data and
            site.site_zip == form.site_zip.data and
            site.principal_first_name == form.principal_first_name.data and
            site.principal_last_name == form.principal_last_name.data and
            site.principal_email == form.principal_email.data and
            site.principal_phone == form.principal_phone.data
        ):
            flash('No changes were made.', 'info')
            return render_template('edit_site.html', form=form, site=site)
        site.site_name = form.site_name.data
        site.site_acronyms = form.site_acronyms.data
        site.site_code = form.site_code.data
        site.site_cds = form.site_cds.data
        site.site_address = form.site_address.data
        site.site_type = form.site_type.data
        site.site_city = form.site_city.data
        site.site_state = form.site_state.data
        site.site_zip = form.site_zip.data
        site.principal_first_name = form.principal_first_name.data
        site.principal_last_name = form.principal_last_name.data
        site.principal_email = form.principal_email.data
        site.principal_phone = form.principal_phone.data
        db.session.commit()
        flash('Site updated successfully!', 'success')
        return redirect(url_for('routes.sites'))
    return render_template('edit_site.html', form=form, site=site)

# ****************** Delete Site Page *******************************
@routes_blueprint.route('/delete_site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    is_admin()  # Ensure only admins can access this route
    site = Site.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    flash('Site deleted successfully!', 'warning')
    return redirect(url_for('routes.sites'))


# *********************************************************************
# ****************** Notification Management Page *********************
@routes_blueprint.route('/notifications', methods=['GET'])
@login_required
def notifications():
        # Mapping paths to page names
    page_names = {'/notifications': 'Manage Notifications'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    # Get the page number and per_page from the query parameters, default to 10 for per_page
    page, per_page, offset = get_page_args(page_parameter="page", per_page_parameter="per_page")
    # Query the users
    total = Notification.query.count()
    notifications = Notification.query.offset(offset).limit(per_page).all()
    # Set up pagination with Bootstrap 5 styling
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    return render_template('notifications.html', notifications=notifications, pagination=pagination, per_page=per_page, total=total, 
        current_path=current_path, 
        current_page_name=current_page_name
    )

# ****************** Add New Notification *********************
@routes_blueprint.route('/add_notification', methods=['GET', 'POST'])
@login_required
def add_notification():
    page_names = {'/add_notification': 'New Notification'}
    current_path = request.path
    current_page_name = page_names.get(current_path, 'Unknown Page')
    is_admin()  # Ensure only admins can access this route
    form = NotificationForm()
    if form.validate_on_submit():
        # Check if a notification with the same name already exists
        existing_notification = Notification.query.filter_by(msg_name=form.msg_name.data).first()
        if existing_notification:
            flash('This notification name already exists.', 'danger')
            return render_template('add_notification.html', form=form)  # Re-render form with the error message
        new_notification = Notification(
            msg_name=form.msg_name.data,
            msg_content=form.msg_content.data,
            msg_status="Inactive"
        )
        db.session.add(new_notification)
        db.session.commit()
        flash('Notification added successfully!', 'success')
        return redirect(url_for('routes.notifications'))
    # Pass None for notification to differentiate between add and edit
    return render_template('add_notification.html', form=form,
        current_path=current_path, 
        current_page_name=current_page_name
    )


# ****************** Edit Notification Page *********************
@routes_blueprint.route('/edit_notification/<int:notification_id>', methods=['GET', 'POST'])
@login_required
def edit_notification(notification_id):
    is_admin()  # Ensure only admins can access this route
    notification = Notification.query.get_or_404(notification_id)
    form = NotificationForm(obj=notification)

    if request.method == 'POST':
        # Capture original values before any mutation
        orig_name    = notification.msg_name
        orig_content = notification.msg_content
        orig_status  = notification.msg_status

        # Determine new status from checkbox
        new_status = 'Active' if request.form.get('msg_status') else 'Inactive'

        # Check for duplicate notification name
        existing_notification = Notification.query.filter(
            Notification.msg_name == form.msg_name.data,
            Notification.id != notification.id
        ).first()
        if existing_notification:
            flash('This notification name already exists.', 'danger')
            return render_template('edit_notification.html', form=form, notification=notification)

        # Check if no changes were made
        if (
            orig_name    == form.msg_name.data and
            orig_content == form.msg_content.data and
            orig_status  == new_status
        ):
            flash('No changes were made.', 'info')
            return render_template('edit_notification.html', form=form, notification=notification)

        # Enforce only one active notification
        if new_status == 'Active':
            active_notification = Notification.query.filter_by(msg_status='Active').first()
            if active_notification and active_notification.id != notification.id:
                flash('Only one notification can be active at a time. Please deactivate the current notification before activating a new one. ', 'danger')
                return render_template('edit_notification.html', form=form, notification=notification)

        # Update and save changes
        notification.msg_name    = form.msg_name.data
        notification.msg_content = form.msg_content.data
        notification.msg_status  = new_status
        db.session.commit()
        flash('Notification updated successfully!', 'success')
        return redirect(url_for('routes.notifications'))

    return render_template('edit_notification.html', form=form, notification=notification)



# ****************** Toggle Notification Status *********************
@routes_blueprint.route('/toggle_notification/<int:notification_id>', methods=['POST'])
@login_required
def toggle_notification(notification_id):
    is_admin()
    notification = Notification.query.get_or_404(notification_id)
    if notification.msg_status == 'Active':
        notification.msg_status = 'Inactive'
    else:
        # Deactivate all others first, then activate this one
        Notification.query.filter(Notification.id != notification_id).update({'msg_status': 'Inactive'})
        notification.msg_status = 'Active'
    db.session.commit()
    return redirect(url_for('routes.notifications'))


# ****************** Delete Notification Page *********************
@routes_blueprint.route('/delete_notification/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    is_admin()  # Ensure only admins can access this route
    notification = Notification.query.get_or_404(notification_id)
    db.session.delete(notification)
    db.session.commit()
    flash('Notification deleted successfully!', 'warning')
    return redirect(url_for('routes.notifications'))


_GRADE_LIST = ['TK', 'KN', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']


# =============================================================================
# STUDENTS
# =============================================================================

@routes_blueprint.route('/students', methods=['GET'])
@login_required
def students():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search          = request.args.get('search', '').strip()
    _url_site       = request.args.get('site_filter', '').strip()
    site_filter     = _url_site if _url_site else session.get('active_site_filter', '')
    site_filter     = _clamp_site_filter(site_filter)
    grade_filter    = request.args.get('grade_filter', '').strip()
    subgroups       = [s.strip() for s in request.args.getlist('subgroup') if s.strip()]
    english_status  = [s.strip() for s in request.args.getlist('english_status') if s.strip()]
    gender_filters  = [s.strip() for s in request.args.getlist('gender') if s.strip()]
    status_filter   = session.get('active_status_filter', 'active')
    schoolyr_filter = session.get('active_schoolyr', '')
    today           = datetime.now().date()

    _SUBGROUP_LABELS = {
        'homeless':           'Homeless / Dwelling',
        'frm':                'Free / Reduced Meal',
        'swd':                'Students with Disability',
        'no_ssid':            'Missing SSID',
        'foster':             'Foster Youth',
        'migrant':            'Migrant',
        'sed504':             '504 Plan',
        'no_english_status':  'Missing English Status',
    }

    query = Student.query
    if status_filter == 'active':
        query = query.filter(
            db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
            db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
        )
    elif status_filter == 'inactive':
        query = query.filter(
            Student.exit_date.isnot(None),
            Student.exit_date < today,
        )
    if search:
        query = query.filter(
            db.or_(Student.first_name.ilike(f'%{search}%'),
                   Student.last_name.ilike(f'%{search}%'),
                   Student.student_id.ilike(f'%{search}%'))
        )
    if site_filter:
        query = query.filter(Student.site_id == site_filter)
    if grade_filter:
        query = query.filter(Student.grade == grade_filter)
    if subgroups:
        _sg_conditions = {
            'homeless':          db.and_(Student.dwelling.isnot(None), Student.dwelling != ''),
            'frm':               Student.frm_code.in_(['F', 'R']),
            'swd':               db.and_(Student.disability.isnot(None), Student.disability != ''),
            'foster':            Student.foster == True,
            'migrant':           Student.migrant == True,
            'sed504':            Student.sed504 == True,
            'no_ssid':           db.or_(Student.ssid.is_(None), Student.ssid == ''),
            'no_english_status': db.or_(Student.english_status.is_(None), Student.english_status == ''),
        }
        conditions = [_sg_conditions[sg] for sg in subgroups if sg in _sg_conditions]
        if conditions:
            query = query.filter(db.and_(*conditions))
    ethnicity_filter = request.args.get('ethnicity', '').strip()
    if english_status:
        query = query.filter(Student.english_status.in_(english_status))
    if ethnicity_filter:
        query = query.filter(Student.ethnicity == ethnicity_filter)
    if gender_filters:
        query = query.filter(Student.gender.in_(gender_filters))
    if schoolyr_filter:
        query = query.filter(Student.schoolyr == schoolyr_filter)

    subgroup_label = ' + '.join(_SUBGROUP_LABELS[sg] for sg in subgroups if sg in _SUBGROUP_LABELS)
    if english_status:
        subgroup_label = (subgroup_label + ' · ' if subgroup_label else '') + 'English Status: ' + ', '.join(english_status)

    total      = query.count()
    students_q = query.order_by(Student.last_name.asc(), Student.first_name.asc()).offset(offset).limit(per_page).all()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    sites = Site.query.order_by(Site.site_name.asc()).all()

    return render_template('students.html',
        students=students_q, pagination=pagination, per_page=per_page,
        total=total, sites=sites, grades=_GRADE_LIST,
        current_page_name='Students',
        subgroups=subgroups, english_status=english_status, gender_filters=gender_filters, subgroup_label=subgroup_label,
        schoolyr_filter=schoolyr_filter)


@routes_blueprint.route('/students/export/csv')
@login_required
def students_export_csv():
    import csv, io
    search          = request.args.get('search', '').strip()
    # session['active_site_filter'] is already restricted to one of the user's
    # allowed_site_ids by the before_request hook — only Admin/District
    # Administrator can export another site's (or all sites') data.
    site_filter     = session.get('active_site_filter', '')
    grade_filter    = request.args.get('grade_filter', '').strip()
    subgroups       = [s.strip() for s in request.args.getlist('subgroup') if s.strip()]
    english_status  = request.args.get('english_status', '').strip()
    status_filter   = session.get('active_status_filter', 'active')
    schoolyr_filter = session.get('active_schoolyr', '')
    today           = datetime.now().date()

    query = Student.query
    if status_filter == 'active':
        query = query.filter(
            db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
            db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
        )
    elif status_filter == 'inactive':
        query = query.filter(Student.exit_date.isnot(None), Student.exit_date < today)
    if search:
        query = query.filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.student_id.ilike(f'%{search}%'),
        ))
    if site_filter:
        query = query.filter(Student.site_id == site_filter)
    if grade_filter:
        query = query.filter(Student.grade == grade_filter)
    if subgroups:
        _sg = {
            'homeless':          db.and_(Student.dwelling.isnot(None), Student.dwelling != ''),
            'frm':               Student.frm_code.in_(['F', 'R']),
            'swd':               db.and_(Student.disability.isnot(None), Student.disability != ''),
            'foster':            Student.foster == True,
            'migrant':           Student.migrant == True,
            'sed504':            Student.sed504 == True,
            'no_ssid':           db.or_(Student.ssid.is_(None), Student.ssid == ''),
            'no_english_status': db.or_(Student.english_status.is_(None), Student.english_status == ''),
        }
        conditions = [_sg[s] for s in subgroups if s in _sg]
        if conditions:
            query = query.filter(db.and_(*conditions))
    if english_status:
        query = query.filter(Student.english_status == english_status)
    if schoolyr_filter:
        query = query.filter(Student.schoolyr == schoolyr_filter)

    _eth = {'100':'Native American','200':'Asian','300':'Pacific Islander','400':'Filipino',
            '500':'Hispanic/Latino','600':'African American','700':'White','900':'Two or More Races'}
    _gen = {'M':'Male','F':'Female','X':'Non-Binary','U':'Unknown'}
    _frm = {'F':'Free','R':'Reduced','P':'Paid'}
    _el  = {'EO':'English Only','EL':'English Learner','IFEP':'IFEP','RFEP':'RFEP','TBD':'TBD'}

    rows = query.order_by(Student.last_name, Student.first_name).all()
    out  = io.StringIO()
    w    = csv.writer(out)
    w.writerow(['Last Name','First Name','Middle Name','Student ID','SSID','Grade','Gender',
                'Date of Birth','Grad Year','Ethnicity','English Status','FRM','Disability',
                'Foster','Migrant','Homeless','504 Plan','Site','School Year','Status'])
    for s in rows:
        w.writerow([
            s.last_name, s.first_name, s.middle_name or '',
            s.student_id, s.ssid or '', s.grade,
            _gen.get(s.gender, s.gender or ''),
            s.date_of_birth or '', s.gradyr or '',
            _eth.get(s.ethnicity, s.ethnicity or ''),
            _el.get(s.english_status, s.english_status or ''),
            _frm.get(s.frm_code, s.frm_code or ''),
            s.disability or '',
            'Yes' if s.foster  else 'No',
            'Yes' if s.migrant else 'No',
            'Yes' if s.dwelling else 'No',
            'Yes' if s.sed504  else 'No',
            s.site.site_name, s.schoolyr or '', s.status,
        ])
    db.session.add(AuditLog(
        user_id=current_user.id,
        action='student_export_csv',
        detail=f"site={site_filter or 'all'}; search={search!r}; subgroups={subgroups}; "
               f"grade={grade_filter or 'all'}; english_status={english_status or 'all'}; "
               f"status={status_filter}; schoolyr={schoolyr_filter or 'all'}",
        record_count=len(rows),
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=students_export.csv'
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return resp


@routes_blueprint.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    return redirect(url_for('routes.students'))


@routes_blueprint.route('/student/<int:student_id>', methods=['GET'])
@login_required
def student_details(student_id):
    student = Student.query.get_or_404(student_id)
    require_site_access(student.site_id)
    student_absences = (Absence.query
                               .filter(Absence.ssid == student.ssid)
                               .order_by(Absence.school_yr.desc(), Absence.abs_date.desc())
                               .all()) if student.ssid else []
    student_incidents = (Incident.query
                                 .filter(Incident.sisid == student.ssid)
                                 .order_by(Incident.incident_date.desc())
                                 .all()) if student.ssid else []
    student_grade_records = (Grade.query
                                   .filter(Grade.grades_stuid == student.student_id)
                                   .order_by(Grade.grades_courseyr.desc(), Grade.grades_term, Grade.grades_coursenum)
                                   .all())
    student_interventions = (Intervention.query
                                   .filter(Intervention.student_id == student.id)
                                   .order_by((Intervention.status == 'Active').desc(), Intervention.start_date.desc())
                                   .all())
    active_intervention_count = sum(1 for iv in student_interventions if iv.status == 'Active')
    course_dates = {
        r.course_id: (r.start_date, r.leave_date)
        for r in db.session.execute(
            student_course.select().where(student_course.c.student_id == student.id)
        ).all()
    }

    # Look up each grade record's real course (by site + section_id) so the Grades tab can show
    # the course name alongside the raw section id, not just the section id twice.
    pairs = {(r.grades_schoolid, r.grades_coursenum)
             for r in student_grade_records if r.grades_schoolid and r.grades_coursenum}
    course_map = {}
    if pairs:
        site_cds_set = {p[0] for p in pairs}
        for course, site_cds in (db.session.query(Course, Site.site_cds)
                                  .join(Site, Course.site_id == Site.id)
                                  .filter(Site.site_cds.in_(site_cds_set)).all()):
            course_map[(site_cds, course.section_id)] = course
    grade_course_names = {
        gr.id: course_map[(gr.grades_schoolid, gr.grades_coursenum)].course_name
        for gr in student_grade_records
        if (gr.grades_schoolid, gr.grades_coursenum) in course_map
    }

    org = db.session.get(Organization, 1)
    show_graduation_tab = bool(org and org.show_graduation and student.grade in _GRAD_HS_GRADES)
    grad_subject_rows = []
    grad_totals = None
    if show_graduation_tab:
        from collections import defaultdict

        requirements = _load_grad_requirements()

        completed = defaultdict(float)
        for gr in student_grade_records:
            course = course_map.get((gr.grades_schoolid, gr.grades_coursenum))
            subject = _grad_subject_for_course(course.department if course else None,
                                                course.course_name if course else None, requirements)
            completed[subject] += float(gr.grades_credcomp or 0)

        # In-progress: currently-active enrollments for the active school year with no grade posted yet
        yr_filter = session.get('active_schoolyr', '')
        graded_sections = {(gr.grades_schoolid, gr.grades_coursenum)
                            for gr in student_grade_records if gr.grades_courseyr == yr_filter}
        in_progress = defaultdict(float)
        for course in student.active_courses:
            if (course.site.site_cds, course.section_id) in graded_sections:
                continue
            subject = _grad_subject_for_course(course.department, course.course_name, requirements)
            in_progress[subject] += float(course.credits or 0)

        tot_req = tot_comp = tot_prog = tot_rem = 0.0
        for req in requirements:
            required = float(req.credits_required or 0)
            comp = completed.get(req.subject_name, 0.0)
            prog = in_progress.get(req.subject_name, 0.0)
            rem  = max(required - comp - prog, 0.0)
            pct  = round(min(comp / required, 1.0) * 100, 1) if required else 0.0
            grad_subject_rows.append({
                'subject': req.subject_name, 'required': required, 'completed': round(comp, 2),
                'in_progress': round(prog, 2), 'remaining': round(rem, 2), 'pct': pct,
            })
            tot_req += required; tot_comp += comp; tot_prog += prog; tot_rem += rem
        grad_totals = {
            'required': round(tot_req, 2), 'completed': round(tot_comp, 2),
            'in_progress': round(tot_prog, 2), 'remaining': round(tot_rem, 2),
        }

    return render_template('student_details.html', student=student,
                           student_absences=student_absences,
                           student_incidents=student_incidents,
                           student_interventions=student_interventions,
                           active_intervention_count=active_intervention_count,
                           student_grade_records=student_grade_records,
                           grade_course_names=grade_course_names,
                           course_dates=course_dates,
                           show_graduation_tab=show_graduation_tab,
                           grad_subject_rows=grad_subject_rows,
                           grad_totals=grad_totals,
                           current_page_name=f'{student.first_name} {student.last_name}')


# =============================================================================
# STUDENT GRADES
# =============================================================================

@routes_blueprint.route('/student-grades', methods=['GET'])
@login_required
def student_grades():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search        = request.args.get('search', '').strip()
    site_filter   = session.get('active_site_filter', '')
    schoolyr      = session.get('active_schoolyr', '') or '2025-2026'
    term_filter   = request.args.get('term', '').strip()
    grade_filter  = request.args.get('grade_letter', '').strip()
    course_filter = request.args.get('course', '').strip()

    query = (db.session.query(Grade, Student)
             .join(Student, Student.student_id == Grade.grades_stuid)
             .filter(Grade.grades_courseyr == schoolyr))

    if search:
        query = query.filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.student_id.ilike(f'%{search}%'),
        ))
    if site_filter:
        query = query.filter(Student.site_id == site_filter)
    if term_filter:
        query = query.filter(Grade.grades_term == term_filter)
    if grade_filter:
        query = query.filter(Grade.grades_grade == grade_filter)
    if course_filter:
        query = query.filter(Grade.grades_coursenum == course_filter)

    total   = query.count()
    results = (query.order_by(Student.last_name, Student.first_name, Grade.grades_coursenum, Grade.grades_term)
               .offset(offset).limit(per_page).all())
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')

    terms   = [r[0] for r in db.session.query(Grade.grades_term).filter_by(grades_courseyr=schoolyr).distinct().order_by(Grade.grades_term).all()]
    courses = [r[0] for r in db.session.query(Grade.grades_coursenum).filter_by(grades_courseyr=schoolyr).distinct().order_by(Grade.grades_coursenum).all()]

    return render_template('student_grades.html',
        results=results, pagination=pagination, per_page=per_page,
        total=total, terms=terms, courses=courses,
        term_filter=term_filter, grade_filter=grade_filter, course_filter=course_filter,
        current_page_name='Student Grades',
    )


# =============================================================================
# DEMOGRAPHICS DASHBOARD
# =============================================================================

@routes_blueprint.route('/demographics')
@login_required
def demographics():

    site_filter   = session.get('active_site_filter', '')
    yr_filter     = session.get('active_schoolyr', '')
    status_filter = session.get('active_status_filter', 'active')
    snap_date_str = session.get('active_snap_date', '')

    # Parse snapshot date
    snap_date = None
    if snap_date_str:
        try:
            snap_date = datetime.strptime(snap_date_str, '%Y-%m-%d').date()
        except ValueError:
            snap_date_str = ''

    # Reference date: snapshot date if provided, otherwise today.
    ref_date = snap_date or datetime.now().date()

    def _date_filter(q):
        if status_filter == 'active':
            return q.filter(
                db.or_(Student.enter_date.is_(None), Student.enter_date <= ref_date),
                db.or_(Student.exit_date.is_(None),  Student.exit_date  >= ref_date),
            )
        elif status_filter == 'inactive':
            return q.filter(
                Student.exit_date.isnot(None),
                Student.exit_date < ref_date,
            )
        # 'all' — no date-based status restriction
        return q

    base = _date_filter(Student.query)
    if site_filter:
        base = base.filter(Student.site_id == site_filter)
    if yr_filter:
        base = base.filter(Student.schoolyr == yr_filter)

    def agg(col):
        q = _date_filter(db.session.query(col, func.count(Student.id)))
        if site_filter:
            q = q.filter(Student.site_id == site_filter)
        if yr_filter:
            q = q.filter(Student.schoolyr == yr_filter)
        return q.group_by(col).all()

    total = base.count()

    # KPI counts
    eo_count      = base.filter_by(english_status='EO').count()
    el_count      = base.filter_by(english_status='EL').count()
    ifep_count    = base.filter_by(english_status='IFEP').count()
    rfep_count    = base.filter_by(english_status='RFEP').count()
    homeless_count = base.filter(Student.dwelling.isnot(None), Student.dwelling != '').count()
    tbd_count      = base.filter(db.or_(Student.ssid.is_(None), Student.ssid == '')).count()
    frm_count     = base.filter(Student.frm_code.in_(['F', 'R'])).count()
    swd_count     = base.filter(Student.disability.isnot(None), Student.disability != '').count()
    foster_count  = base.filter_by(foster=True).count()
    migrant_count = base.filter_by(migrant=True).count()
    sed504_count  = base.filter_by(sed504=True).count()

    # Ethnicity
    _eth_map = {
        '100': 'Native American', '200': 'Asian', '300': 'Pacific Islander',
        '400': 'Filipino', '500': 'Hispanic/Latino', '600': 'African American',
        '700': 'White', '900': 'Two or More Races',
    }
    eth_rows = agg(Student.ethnicity)
    ethnicity_table_data = [
        (r[0] or '', _eth_map.get(r[0], r[0] or 'Unknown'), r[1]) for r in
        sorted(eth_rows, key=lambda x: x[1], reverse=True)
    ]

    # Gender
    _gen_map = {'M': 'Male', 'F': 'Female', 'X': 'Non-Binary', 'U': 'Unknown'}
    gen_rows      = agg(Student.gender)
    gender_labels = [_gen_map.get(r[0], r[0] or 'Unknown') for r in gen_rows]
    gender_counts = [r[1] for r in gen_rows]

    # Grade (ordered)
    _grade_order = ['TK', 'KN', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
    grade_dict   = {r[0]: r[1] for r in agg(Student.grade)}
    _g_labels    = [g for g in _grade_order if g in grade_dict]
    grade_labels = _g_labels
    grade_counts = [grade_dict[g] for g in _g_labels]

    # Enrollment by site — respects year & date filters but ignores site filter
    site_q = _date_filter(
        db.session.query(Site.id, Site.site_acronyms, func.count(Student.id))
        .join(Student, Site.id == Student.site_id)
    )
    if yr_filter:
        site_q = site_q.filter(Student.schoolyr == yr_filter)
    site_table_data = site_q.group_by(Site.id, Site.site_acronyms).order_by(Site.site_acronyms).all()
    site_grand_total = sum(r[2] for r in site_table_data)

    return render_template('dashboard/demographics.html',
        current_page_name='Demographics',
        snap_date_str=snap_date_str,
        total=total, eo_count=eo_count, el_count=el_count, ifep_count=ifep_count, rfep_count=rfep_count,
        homeless_count=homeless_count, tbd_count=tbd_count, frm_count=frm_count, swd_count=swd_count,
        foster_count=foster_count, migrant_count=migrant_count, sed504_count=sed504_count,
        ethnicity_table_data=ethnicity_table_data,
        gender_labels=gender_labels, gender_counts=gender_counts,
        grade_labels=grade_labels, grade_counts=grade_counts,
        site_table_data=site_table_data, site_grand_total=site_grand_total,
    )


# =============================================================================
# ENROLLMENT DASHBOARD
# =============================================================================

@routes_blueprint.route('/enrollment')
@login_required
def enrollment():
    from datetime import date as _date

    site_filter   = session.get('active_site_filter', '')
    yr_filter     = session.get('active_schoolyr', '')
    status_filter = session.get('active_status_filter', 'active')
    snap_date_str = session.get('active_snap_date', '')

    snap_date = None
    if snap_date_str:
        try:
            snap_date = datetime.strptime(snap_date_str, '%Y-%m-%d').date()
        except ValueError:
            snap_date_str = ''

    ref_date = snap_date or _date.today()

    def _status_filter(q):
        if status_filter == 'active':
            return q.filter(
                db.or_(Student.enter_date.is_(None), Student.enter_date <= ref_date),
                db.or_(Student.exit_date.is_(None),  Student.exit_date  >= ref_date),
            )
        elif status_filter == 'inactive':
            return q.filter(
                Student.exit_date.isnot(None),
                Student.exit_date < ref_date,
            )
        return q

    base = _status_filter(Student.query)
    if site_filter:
        base = base.filter(Student.site_id == site_filter)
    if yr_filter:
        base = base.filter(Student.schoolyr == yr_filter)

    total = base.count()

    # Teacher-to-student ratio
    teacher_q = Teacher.query.filter_by(status='Active')
    if site_filter:
        teacher_q = teacher_q.filter(Teacher.site_id == site_filter)
    teacher_count = teacher_q.count()
    teacher_ratio = f"1:{round(total / teacher_count)}" if teacher_count else '—'

    # Max students per course
    course_enrollment_q = (
        db.session.query(Course.id, func.count(Student.id).label('cnt'))
        .join(Course.active_students)
        .filter(Course.status == 'Active')
    )
    if site_filter:
        course_enrollment_q = course_enrollment_q.filter(Course.site_id == site_filter)
    course_counts = course_enrollment_q.group_by(Course.id).all()
    max_students_per_course = max((r.cnt for r in course_counts), default=0)

    # Subgroup KPIs
    el_count      = base.filter(Student.english_status == 'EL').count()
    frm_count     = base.filter(Student.frm_code.in_(['F', 'R'])).count()
    homeless_count = base.filter(Student.dwelling.isnot(None), Student.dwelling != '').count()
    swd_count     = base.filter(Student.disability.isnot(None), Student.disability != '').count()
    foster_count  = base.filter_by(foster=True).count()
    migrant_count = base.filter_by(migrant=True).count()
    sed504_count  = base.filter_by(sed504=True).count()

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    subgroup_data = [
        ('English Learner',        el_count,      pct(el_count)),
        ('Free / Reduced Meal',    frm_count,     pct(frm_count)),
        ('Students w/ Disability', swd_count,     pct(swd_count)),
        ('Homeless',               homeless_count, pct(homeless_count)),
        ('Foster',                 foster_count,  pct(foster_count)),
        ('Migrant',                migrant_count, pct(migrant_count)),
        ('504 Plan',               sed504_count,  pct(sed504_count)),
    ]

    # Year-over-year enrollment — active students as of June 30 of each year, no session filters
    import re as _re
    def _yr_end(yr_str):
        m = _re.match(r'\d{4}-(\d{4})', yr_str)
        end_yr = int(m.group(1)) if m else _date.today().year
        return min(_date(end_yr, 6, 30), _date.today())

    all_yrs = sorted(set(
        r[0] for r in db.session.query(Student.schoolyr)
        .filter(Student.schoolyr.isnot(None), Student.schoolyr != '').all()
    ))
    yoy_rows = []
    for yr in all_yrs:
        yr_ref = _yr_end(yr)
        cnt = (Student.query
               .filter(Student.schoolyr == yr)
               .filter(db.or_(Student.exit_date.is_(None), Student.exit_date >= yr_ref))
               .count())
        yoy_rows.append((yr, cnt))

    yoy_labels = [r[0] for r in yoy_rows]
    yoy_counts = [r[1] for r in yoy_rows]

    # Determine previous school year
    prev_yr = None
    yoy_change = None
    yoy_change_pct = None
    if len(yoy_rows) >= 2 and yr_filter:
        yoy_dict = {r[0]: r[1] for r in yoy_rows}
        if yr_filter in yoy_dict:
            yrs = sorted(yoy_dict.keys())
            idx = yrs.index(yr_filter)
            if idx > 0:
                prev_yr    = yrs[idx - 1]
                prev_total = yoy_dict[prev_yr]
                yoy_change = total - prev_total
                yoy_change_pct = round(yoy_change / prev_total * 100, 1) if prev_total else None

    # Grade breakdown
    _grade_order = ['TK', 'KN', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
    grade_dict = {r[0]: r[1] for r in
                  base.with_entities(Student.grade, func.count(Student.id)).group_by(Student.grade).all()}

    prev_grade_dict = {}
    if prev_yr:
        prev_grade_q = (db.session.query(Student.grade, func.count(Student.id))
                        .filter(Student.schoolyr == prev_yr))
        if site_filter:
            prev_grade_q = prev_grade_q.filter(Student.site_id == site_filter)
        prev_grade_dict = {r[0]: r[1] for r in prev_grade_q.group_by(Student.grade).all()}

    grade_keys = [g for g in _grade_order if g in grade_dict]
    grade_table_data = [
        (g, grade_dict[g], grade_dict[g] - prev_grade_dict.get(g, grade_dict[g]))
        for g in grade_keys
    ]

    # Ethnicity breakdown
    _eth_map = {
        '100': 'Native American', '200': 'Asian', '300': 'Pacific Islander',
        '400': 'Filipino', '500': 'Hispanic/Latino', '600': 'African American',
        '700': 'White', '900': 'Two or More Races',
    }
    eth_rows = (base.with_entities(Student.ethnicity, func.count(Student.id))
                .group_by(Student.ethnicity).all())
    ethnicity_table_data = sorted(
        [(_eth_map.get(r[0], r[0] or 'Unknown'), r[1], pct(r[1])) for r in eth_rows],
        key=lambda x: x[1], reverse=True
    )

    # Enrollment by site — current year
    site_base = _status_filter(
        db.session.query(Site.site_acronyms, func.count(Student.id))
        .join(Student, Site.id == Student.site_id)
    )
    if yr_filter:
        site_base = site_base.filter(Student.schoolyr == yr_filter)
    curr_site_rows = site_base.group_by(Site.id, Site.site_acronyms).order_by(Site.site_acronyms).all()

    # Previous year enrollment by site (no status filter for historical data)
    prev_site_dict = {}
    if prev_yr:
        prev_site_q = (db.session.query(Site.site_acronyms, func.count(Student.id))
                       .join(Student, Site.id == Student.site_id)
                       .filter(Student.schoolyr == prev_yr)
                       .group_by(Site.id, Site.site_acronyms).all())
        prev_site_dict = {r[0]: r[1] for r in prev_site_q}

    # Build site table: (acronym, current_count, change)
    site_table_data = [
        (acronym, cnt, cnt - prev_site_dict.get(acronym, cnt))
        for acronym, cnt in curr_site_rows
    ]

    return render_template('dashboard/enrollment.html',
        current_page_name='Enrollment',
        total=total, el_count=el_count, frm_count=frm_count,
        teacher_ratio=teacher_ratio, max_students_per_course=max_students_per_course,
        yoy_change=yoy_change, yoy_change_pct=yoy_change_pct,
        subgroup_data=subgroup_data,
        grade_table_data=grade_table_data,
        ethnicity_table_data=ethnicity_table_data,
        site_table_data=site_table_data,
        yoy_labels=yoy_labels, yoy_counts=yoy_counts,
        yr_filter=yr_filter,
    )


# =============================================================================
# EARLY WARNING SYSTEM
# =============================================================================

@routes_blueprint.route('/early-warning')
@login_required
def early_warning():
    schoolyr     = session.get('active_schoolyr', '') or '2025-2026'
    site_filter  = session.get('active_site_filter', '')
    risk_filter  = request.args.get('risk_filter',  '').strip()
    grade_filter = request.args.get('grade_filter', '').strip()
    today        = datetime.now().date()
    page, per_page, _ = get_page_args(page_parameter='page', per_page_parameter='per_page')

    # Base student query — active students only
    sq = Student.query.filter(
        db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
        db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
        Student.schoolyr == schoolyr,
    )
    if site_filter:
        sq = sq.filter(Student.site_id == site_filter)
    if grade_filter:
        sq = sq.filter(Student.grade == grade_filter)
    students = sq.all()

    # Pre-aggregate absences and incidents by SSID
    abs_counts = dict(
        db.session.query(Absence.ssid, func.count(Absence.id))
        .filter(Absence.school_yr == schoolyr)
        .group_by(Absence.ssid).all()
    )
    inc_counts = dict(
        db.session.query(Incident.sisid, func.count(Incident.id))
        .filter(Incident.schoolyr == schoolyr)
        .group_by(Incident.sisid).all()
    )
    # F-grade count by student_id (not just a yes/no flag — feeds the composite score below)
    f_counts = dict(
        db.session.query(Grade.grades_stuid, func.count(Grade.id))
        .filter(Grade.grades_courseyr == schoolyr, Grade.grades_grade == 'F')
        .group_by(Grade.grades_stuid).all()
    )
    # Active (open) interventions already in place for these students — so staff can see who's
    # already being supported instead of re-flagging the same student from scratch.
    active_iv_counts = dict(
        db.session.query(Intervention.student_id, func.count(Intervention.id))
        .filter(Intervention.student_id.in_([s.id for s in students]), Intervention.status == 'Active')
        .group_by(Intervention.student_id).all()
    ) if students else {}

    # Build EWS rows
    _ABS_THRESHOLD     = 10
    _INC_THRESHOLD     = 3
    _CHRONIC_THRESHOLD = 18
    _F_CAP             = 3     # 3+ F's in the year scores as maximally severe on the academic component

    # Composite risk score (0-100): each component is scaled 0-100 against a "severe" cap, then
    # combined with fixed weights — attendance and academics matter twice as much as a single
    # behavior incident count, since those two are stronger predictors of not graduating on time.
    # This replaces the old "count how many of 3 boolean flags are tripped" bucketing, which
    # couldn't distinguish a student with 10 absences from one with 40.
    _RISK_WEIGHTS = {'attendance': 0.4, 'academic': 0.4, 'behavior': 0.2}

    def _scale(value, cap):
        return round(max(0.0, min(100.0, value / cap * 100)), 1) if cap > 0 else 0.0

    ews_rows = []
    for s in students:
        absences  = abs_counts.get(s.ssid or '', 0)
        incidents = inc_counts.get(s.ssid or '', 0)
        f_count   = f_counts.get(s.student_id, 0)
        has_f     = f_count > 0

        att_flag  = absences  >= _ABS_THRESHOLD
        beh_flag  = incidents >= _INC_THRESHOLD
        grd_flag  = has_f

        att_score = _scale(absences,  _ABS_THRESHOLD * 1.5)
        beh_score = _scale(incidents, _INC_THRESHOLD * 1.5)
        acd_score = _scale(f_count,   _F_CAP)
        risk_score = round(
            att_score * _RISK_WEIGHTS['attendance'] +
            acd_score * _RISK_WEIGHTS['academic'] +
            beh_score * _RISK_WEIGHTS['behavior'], 1
        )

        if risk_score >= 67:
            risk = 'high'
        elif risk_score >= 34:
            risk = 'medium'
        else:
            risk = 'on_track'

        site_obj = db.session.get(Site, s.site_id)
        ews_rows.append({
            'student':   s,
            'site_name': site_obj.site_name if site_obj else '',
            'absences':  absences,
            'incidents': incidents,
            'f_count':   f_count,
            'has_f':     has_f,
            'att_flag':  att_flag,
            'beh_flag':  beh_flag,
            'grd_flag':  grd_flag,
            'risk':      risk,
            'risk_score': risk_score,
            'open_interventions': active_iv_counts.get(s.id, 0),
        })

    chronic_count = sum(1 for r in ews_rows if r['absences'] >= _CHRONIC_THRESHOLD)

    if risk_filter == 'chronic':
        ews_rows = [r for r in ews_rows if r['absences'] >= _CHRONIC_THRESHOLD]
    elif risk_filter:
        ews_rows = [r for r in ews_rows if r['risk'] == risk_filter]

    ews_rows.sort(key=lambda r: (-r['risk_score'], r['student'].last_name))

    high_count     = sum(1 for r in ews_rows if r['risk'] == 'high')
    medium_count   = sum(1 for r in ews_rows if r['risk'] == 'medium')
    on_track_count = sum(1 for r in ews_rows if r['risk'] == 'on_track')
    total          = len(ews_rows)

    offset     = (page - 1) * per_page
    ews_page   = ews_rows[offset: offset + per_page]
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')

    return render_template('early_warning.html',
        ews_rows=ews_page,
        high_count=high_count,
        medium_count=medium_count,
        chronic_count=chronic_count,
        on_track_count=on_track_count,
        total=total,
        per_page=per_page,
        pagination=pagination,
        risk_filter=risk_filter,
        grade_filter=grade_filter,
        grades=_GRADE_LIST,
        current_page_name='Early Warning System',
    )


# =============================================================================
# INTERVENTIONS (MTSS / RTI TRACKING)
# =============================================================================

_INTERVENTION_TIERS      = ['Tier 1', 'Tier 2', 'Tier 3']
_INTERVENTION_CATEGORIES = ['Attendance', 'Behavior', 'Academic']


@routes_blueprint.route('/interventions', methods=['GET'])
@login_required
def interventions():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search           = request.args.get('search', '').strip()
    tier_filter      = request.args.get('tier_filter', '').strip()
    category_filter  = request.args.get('category_filter', '').strip()
    status_filter    = request.args.get('status_filter', '').strip()
    site_filter      = session.get('active_site_filter', '')

    query = Intervention.query.join(Student, Intervention.student_id == Student.id)
    if search:
        query = query.filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.student_id.ilike(f'%{search}%'),
        ))
    if tier_filter:
        query = query.filter(Intervention.tier == tier_filter)
    if category_filter:
        query = query.filter(Intervention.category == category_filter)
    if status_filter:
        query = query.filter(Intervention.status == status_filter)
    if site_filter:
        query = query.filter(Student.site_id == site_filter)

    total = query.count()
    rows = (query.order_by((Intervention.status == 'Active').desc(), Intervention.start_date.desc())
                 .offset(offset).limit(per_page).all())
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')

    active_count = Intervention.query.filter(Intervention.status == 'Active').count()

    return render_template('interventions.html',
        rows=rows, pagination=pagination, per_page=per_page, total=total,
        active_count=active_count,
        search=search, tier_filter=tier_filter, category_filter=category_filter, status_filter=status_filter,
        tiers=_INTERVENTION_TIERS, categories=_INTERVENTION_CATEGORIES,
        current_page_name='Interventions')


@routes_blueprint.route('/interventions/add/<int:student_id>', methods=['GET', 'POST'])
@login_required
def add_intervention(student_id):
    student = Student.query.get_or_404(student_id)
    form = InterventionForm()
    if form.validate_on_submit():
        db.session.add(Intervention(
            student_id=student.id,
            tier=form.tier.data,
            category=form.category.data,
            description=form.description.data.strip(),
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data,
            outcome=form.outcome.data or None,
            notes=form.notes.data.strip() if form.notes.data else None,
            created_by_id=current_user.id,
        ))
        db.session.commit()
        flash('Intervention logged successfully!', 'success')
        return redirect(url_for('routes.student_details', student_id=student.id) + '#pane-interventions')
    return render_template('add_intervention.html', form=form, student=student)


@routes_blueprint.route('/interventions/edit/<int:intervention_id>', methods=['GET', 'POST'])
@login_required
def edit_intervention(intervention_id):
    intervention = Intervention.query.get_or_404(intervention_id)
    form = InterventionForm(obj=intervention)
    if form.validate_on_submit():
        intervention.tier        = form.tier.data
        intervention.category    = form.category.data
        intervention.description = form.description.data.strip()
        intervention.start_date  = form.start_date.data
        intervention.end_date    = form.end_date.data
        intervention.status      = form.status.data
        intervention.outcome     = form.outcome.data or None
        intervention.notes       = form.notes.data.strip() if form.notes.data else None
        db.session.commit()
        flash('Intervention updated successfully!', 'success')
        return redirect(url_for('routes.student_details', student_id=intervention.student_id) + '#pane-interventions')
    return render_template('edit_intervention.html', form=form, intervention=intervention, student=intervention.student)


@routes_blueprint.route('/interventions/delete/<int:intervention_id>', methods=['POST'])
@login_required
def delete_intervention(intervention_id):
    intervention = Intervention.query.get_or_404(intervention_id)
    student_id = intervention.student_id
    db.session.delete(intervention)
    db.session.commit()
    flash('Intervention deleted successfully!', 'warning')
    return redirect(url_for('routes.student_details', student_id=student_id) + '#pane-interventions')


# =============================================================================
# GRADUATION STATUS DASHBOARD
# =============================================================================

_GRAD_HS_GRADES = ['9', '10', '11', '12']
_GRAD_GRADE_IDX = {'9': 1, '10': 2, '11': 3, '12': 4}
_GRAD_STATUS_ORDER = ['Credit Deficient', 'Behind', 'On Track', 'Graduated']


def _grad_expected_fraction(grade, start_grade, end_grade):
    """How much of a subject's credits should typically be done by now, based on the grade
    span it's normally taken in — not a blanket 1/4-per-year split of the whole requirement.
    E.g. Algebra I ('9'-'9') is expected 100% done by 9th grade; CTE ('12'-'12') is expected
    0% done until senior year; Social Science ('10'-'12') ramps up starting sophomore year."""
    g = _GRAD_GRADE_IDX.get(grade)
    s = _GRAD_GRADE_IDX.get(start_grade) or 1
    e = _GRAD_GRADE_IDX.get(end_grade) or 4
    if g is None:
        return 1.0
    if g < s:
        return 0.0
    if g >= e:
        return 1.0
    return (g - s + 1) / (e - s + 1)


def _grad_classify(subject_rows):
    """Classify using the subject area furthest behind its own grade-paced target — not just
    total credits — so a student can't be marked 'Graduated'/'On Track' by stacking Electives
    while missing a required subject like English or Algebra I. `subject_rows` entries carry
    a precomputed 'expected' credit amount (required * grade-span-aware pace)."""
    if all(r['completed'] >= r['required'] for r in subject_rows if r['required'] > 0):
        return 'Graduated'

    ratios = []
    for r in subject_rows:
        if r['required'] <= 0 or r['completed'] >= r['required']:
            continue
        if r['expected'] <= 0:
            continue  # not due yet — doesn't count against the student
        ratios.append(r['completed'] / r['expected'])
    worst_ratio = min(ratios) if ratios else 1.0

    if worst_ratio >= 1.0:
        return 'On Track'
    elif worst_ratio >= 0.75:
        return 'Behind'
    return 'Credit Deficient'


def _load_grad_requirements():
    """Admin-configured subject-area rows for the Graduation tab, in display/matching order."""
    return GraduationRequirement.query.order_by(GraduationRequirement.sort_order, GraduationRequirement.id).all()


def _grad_subject_for_course(department, course_name, requirements):
    """Match a course to a subject-area row: department (if set) must match, name must
    contain a keyword (if set) and must not contain an exclude-keyword (if set).
    Falls back to whichever row is marked as the catch-all."""
    dept = (department or '').strip()
    name = (course_name or '').upper()
    catch_all = None
    for req in requirements:
        if req.is_catch_all:
            catch_all = catch_all or req
            continue
        if req.department_list and dept not in req.department_list:
            continue
        if req.keyword_list and not any(kw.upper() in name for kw in req.keyword_list):
            continue
        if req.exclude_keyword_list and any(kw.upper() in name for kw in req.exclude_keyword_list):
            continue
        return req.subject_name
    return catch_all.subject_name if catch_all else None


_GRAD_UNCLASSIFIED_SUBJECT = 'Unclassified'


def _recompute_grad_subject_credits():
    """Rebuild the StudentSubjectCredits summary table from the raw Grade + Course data.

    This does the same per-course subject classification the dashboard used to do live on every
    page view, but runs it once here instead — call it after grades.csv uploads, course data
    changes (department/course_name drive subject matching), or GraduationRequirement edits,
    all of which can change how a grade's credits get bucketed into a subject area.
    """
    from collections import defaultdict

    requirements = _load_grad_requirements()

    grade_records = (
        Grade.query
        .with_entities(Grade.grades_stuid, Grade.grades_schoolid, Grade.grades_coursenum, Grade.grades_credcomp)
        .all()
    )

    pairs = {(r.grades_schoolid, r.grades_coursenum) for r in grade_records if r.grades_schoolid and r.grades_coursenum}
    course_map = {}
    if pairs:
        site_cds_set = {p[0] for p in pairs}
        for course, site_cds in (db.session.query(Course, Site.site_cds)
                                  .join(Site, Course.site_id == Site.id)
                                  .filter(Site.site_cds.in_(site_cds_set)).all()):
            course_map[(site_cds, course.section_id)] = course

    course_subject_map = {
        key: (_grad_subject_for_course(course.department, course.course_name, requirements) or _GRAD_UNCLASSIFIED_SUBJECT)
        for key, course in course_map.items()
    }
    no_course_subject = _grad_subject_for_course(None, None, requirements) or _GRAD_UNCLASSIFIED_SUBJECT

    totals = defaultdict(float)
    for r in grade_records:
        subject = course_subject_map.get((r.grades_schoolid, r.grades_coursenum), no_course_subject)
        totals[(r.grades_stuid, subject)] += float(r.grades_credcomp or 0)

    existing = {(row.student_id, row.subject_name): row for row in StudentSubjectCredits.query.all()}
    seen = set()
    for (stuid, subject), credits in totals.items():
        seen.add((stuid, subject))
        row = existing.get((stuid, subject))
        if row:
            row.credits = round(credits, 2)
        else:
            db.session.add(StudentSubjectCredits(student_id=stuid, subject_name=subject, credits=round(credits, 2)))

    # Drop rows that no longer have any matching grade data (subject renamed/deleted, grades removed)
    for key, row in existing.items():
        if key not in seen:
            db.session.delete(row)

    db.session.commit()


# ****************** Graduation Settings (subject-area requirements) *******************************
@routes_blueprint.route('/graduation-settings')
@login_required
def graduation_settings():
    is_admin()
    requirements = _load_grad_requirements()
    total_credits = sum(float(r.credits_required or 0) for r in requirements)
    return render_template('graduation_settings.html',
        requirements=requirements, total_credits=round(total_credits, 2),
        current_page_name='Graduation Settings')


@routes_blueprint.route('/graduation-settings/add', methods=['GET', 'POST'])
@login_required
def add_graduation_requirement():
    is_admin()
    form = GraduationRequirementForm()
    if form.validate_on_submit():
        existing = GraduationRequirement.query.filter_by(subject_name=form.subject_name.data.strip()).first()
        if existing:
            flash('A subject area with this name already exists.', 'danger')
            return render_template('add_graduation_requirement.html', form=form)
        db.session.add(GraduationRequirement(
            subject_name=form.subject_name.data.strip(),
            credits_required=form.credits_required.data,
            departments=form.departments.data.strip() or None,
            name_keywords=form.name_keywords.data.strip() or None,
            name_exclude_keywords=form.name_exclude_keywords.data.strip() or None,
            is_catch_all=form.is_catch_all.data,
            sort_order=form.sort_order.data or 0,
            start_grade=form.start_grade.data,
            end_grade=form.end_grade.data,
        ))
        db.session.commit()
        _recompute_grad_subject_credits()
        flash('Subject area added successfully!', 'success')
        return redirect(url_for('routes.graduation_settings'))
    return render_template('add_graduation_requirement.html', form=form)


@routes_blueprint.route('/graduation-settings/edit/<int:req_id>', methods=['GET', 'POST'])
@login_required
def edit_graduation_requirement(req_id):
    is_admin()
    requirement = GraduationRequirement.query.get_or_404(req_id)
    form = GraduationRequirementForm(obj=requirement)
    if form.validate_on_submit():
        existing = GraduationRequirement.query.filter(
            GraduationRequirement.subject_name == form.subject_name.data.strip(),
            GraduationRequirement.id != requirement.id,
        ).first()
        if existing:
            flash('A subject area with this name already exists.', 'danger')
            return render_template('edit_graduation_requirement.html', form=form, requirement=requirement)
        requirement.subject_name = form.subject_name.data.strip()
        requirement.credits_required = form.credits_required.data
        requirement.departments = form.departments.data.strip() or None
        requirement.name_keywords = form.name_keywords.data.strip() or None
        requirement.name_exclude_keywords = form.name_exclude_keywords.data.strip() or None
        requirement.is_catch_all = form.is_catch_all.data
        requirement.sort_order = form.sort_order.data or 0
        requirement.start_grade = form.start_grade.data
        requirement.end_grade = form.end_grade.data
        db.session.commit()
        _recompute_grad_subject_credits()
        flash('Subject area updated successfully!', 'success')
        return redirect(url_for('routes.graduation_settings'))
    return render_template('edit_graduation_requirement.html', form=form, requirement=requirement)


@routes_blueprint.route('/graduation-settings/delete/<int:req_id>', methods=['POST'])
@login_required
def delete_graduation_requirement(req_id):
    is_admin()
    requirement = GraduationRequirement.query.get_or_404(req_id)
    db.session.delete(requirement)
    db.session.commit()
    _recompute_grad_subject_credits()
    flash('Subject area deleted successfully!', 'warning')
    return redirect(url_for('routes.graduation_settings'))


@routes_blueprint.route('/graduation-status')
@login_required
def graduation_status():
    from collections import defaultdict

    yr_filter     = session.get('active_schoolyr', '')
    site_filter   = session.get('active_site_filter', '')
    status_filter = request.args.get('status_filter', '').strip()
    grade_filter  = request.args.get('grade_filter', '').strip()
    today         = datetime.now().date()
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')

    org = db.session.get(Organization, 1)
    requirements  = _load_grad_requirements()
    subj_required = {r.subject_name: float(r.credits_required or 0) for r in requirements}
    if org and org.grad_auto_calculate_credits:
        required = sum(subj_required.values()) or 220.0
    else:
        required = float(org.grad_credits_required) if org and org.grad_credits_required else 220.0

    # Pre-index requirements by subject name so per-student rows can look up start/end grade
    requirements_by_subject = {r.subject_name: r for r in requirements}

    # Base student query — active HS students only
    sq = Student.query.filter(
        db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
        db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
        Student.grade.in_(_GRAD_HS_GRADES),
    )
    if yr_filter:
        sq = sq.filter(Student.schoolyr == yr_filter)
    if site_filter:
        sq = sq.filter(Student.site_id == site_filter)
    if grade_filter:
        sq = sq.filter(Student.grade == grade_filter)
    students = sq.all()

    # Completed credits per student, broken down by subject area, across all school years on record.
    # Read from the StudentSubjectCredits summary table (kept in sync by _recompute_grad_subject_credits,
    # called after grades.csv/courses.csv/master_schedule.csv uploads and GraduationRequirement edits)
    # instead of re-summing the raw Grade table here — that table can run into the hundreds of
    # thousands of rows for a district's full grade history, and doing that work on every single
    # dashboard view was what made this page slow to load.
    student_ids = [s.student_id for s in students]
    credit_rows = (
        StudentSubjectCredits.query
        .filter(StudentSubjectCredits.student_id.in_(student_ids))
        .with_entities(StudentSubjectCredits.student_id, StudentSubjectCredits.subject_name, StudentSubjectCredits.credits)
        .all()
    ) if student_ids else []

    student_subject_completed = defaultdict(lambda: defaultdict(float))
    for stuid, subject, credits in credit_rows:
        student_subject_completed[stuid][subject] += float(credits or 0)

    site_names = {s.id: s.site_name for s in Site.query.with_entities(Site.id, Site.site_name).all()}

    rows = []
    grade_status_counts = defaultdict(lambda: defaultdict(int))
    for s in students:
        completed_by_subject = student_subject_completed.get(s.student_id, {})
        subject_rows = []
        for name, req_credits in subj_required.items():
            req_row = requirements_by_subject.get(name)
            fraction = _grad_expected_fraction(s.grade, req_row.start_grade, req_row.end_grade) if req_row else 1.0
            subject_rows.append({
                'name': name,
                'required': req_credits,
                'completed': completed_by_subject.get(name, 0.0),
                'expected': req_credits * fraction,
            })
        credits  = sum(r['completed'] for r in subject_rows)
        missing  = [r['name'] for r in subject_rows if r['completed'] < r['required']]
        expected = sum(r['expected'] for r in subject_rows)
        status   = _grad_classify(subject_rows)
        grade_status_counts[s.grade][status] += 1
        rows.append({
            'student':         s,
            'site_name':       site_names.get(s.site_id, ''),
            'credits':         round(credits, 1),
            'expected':        round(expected, 1),
            'pct':             round(min(credits / required, 1.0) * 100, 1) if required else 0.0,
            'status':          status,
            'missing_subjects': missing,
        })

    status_counts = defaultdict(int)
    for r in rows:
        status_counts[r['status']] += 1

    if status_filter:
        rows = [r for r in rows if r['status'] == status_filter]

    rows.sort(key=lambda r: r['pct'])

    total      = len(rows)
    rows_page  = rows[offset: offset + per_page]
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')

    on_track_pct = round(
        (status_counts['On Track'] + status_counts['Graduated']) / len(students) * 100, 1
    ) if students else 0.0

    status_labels   = _GRAD_STATUS_ORDER
    status_data     = [status_counts.get(st, 0) for st in _GRAD_STATUS_ORDER]
    grade_labels    = _GRAD_HS_GRADES
    grade_datasets  = {
        st: [grade_status_counts[g].get(st, 0) for g in _GRAD_HS_GRADES]
        for st in _GRAD_STATUS_ORDER
    }

    # Cohort Progression — the CA Dashboard's cohort Graduation Rate concept, tracking the
    # oldest 9th-grade cohort with data on hand forward year by year. Becomes a true 4-year
    # graduation rate automatically once a 4th year of demographics.csv is uploaded.
    earliest_yr = db.session.query(func.min(Student.schoolyr)).filter(Student.grade == '9').scalar()
    cohort = _cohort_progression(earliest_yr) if earliest_yr else None

    return render_template('dashboard/graduation.html',
        current_page_name='Graduation Status',
        total=total,
        total_students=len(students),
        credits_required=required,
        status_counts=status_counts,
        on_track_pct=on_track_pct,
        status_filter=status_filter,
        grade_filter=grade_filter,
        grades=_GRAD_HS_GRADES,
        rows=rows_page,
        per_page=per_page,
        pagination=pagination,
        status_labels=status_labels,
        status_data=status_data,
        grade_labels=grade_labels,
        grade_datasets=grade_datasets,
        cohort=cohort,
    )


# =============================================================================
# ENROLLMENT K-6 AVAILABILITY
# =============================================================================

@routes_blueprint.route('/enrollment-k6')
@login_required
def enrollment_k6():
    _grade_order = ['TK', 'KN', '1', '2', '3', '4', '5', '6']

    yr_filter = session.get('active_schoolyr', '')

    # Only elementary grades (TK–6) that have at least one active course
    all_grades = sorted(
        set(c.grade_level for c in Course.query.filter_by(status='Active').all()
            if c.grade_level in _grade_order),
        key=lambda g: _grade_order.index(g)
    )

    grade_filter = request.args.get('grade', all_grades[0] if all_grades else '')

    sites = Site.query.order_by(Site.site_name).all()

    _sdc_keywords = ('special', 'sped', 'sdc', 'resource')

    def _inst(teacher):
        dept = (teacher.department or '').lower()
        return 'SDC' if any(k in dept for k in _sdc_keywords) else 'S'

    site_data = []
    summary_rows = []
    grand_total = 0

    for site in sites:
        courses = (Course.query
                   .filter_by(status='Active', site_id=site.id, grade_level=grade_filter)
                   .outerjoin(Teacher, Course.teacher_id == Teacher.id)
                   .order_by(Teacher.last_name, Course.period)
                   .all())
        if not courses:
            continue

        rows = []
        site_total = 0
        for course in courses:
            teacher  = course.teacher
            enrolled = len(course.active_students)
            capacity = course.max_students or 0
            if not teacher and enrolled == 0:
                continue
            rows.append({
                'teacher':    f'{teacher.last_name}, {teacher.first_name}' if teacher else 'Unassigned',
                'teacher_id': teacher.id if teacher else None,
                'inst':       _inst(teacher) if teacher else 'S',
                'section_id': course.section_id or '—',
                'course_id':  course.id,
                'grade':      course.grade_level,
                'totals':     enrolled,
                'capacity':   capacity,
                'available':  capacity - enrolled,
            })
            site_total += enrolled

        if not rows:
            continue

        site_available = sum(r['available'] for r in rows)
        site_data.append({
            'site_name': site.site_name,
            'rows':      rows,
            'total':     site_total,
            'available': site_available,
        })

    total_available = sum(s['available'] for s in site_data)
    total_enrolled  = sum(s['total']     for s in site_data)
    total_capacity  = sum(
        r['capacity'] for s in site_data for r in s['rows']
    )

    return render_template('dashboard/enrollment_k6.html',
        current_page_name='Enrollment K-6',
        all_grades=all_grades,
        grade_filter=grade_filter,
        site_data=site_data,
        total_available=total_available,
        total_enrolled=total_enrolled,
        total_capacity=total_capacity,
    )


# =============================================================================
# ENROLLMENT MS AVAILABILITY
# =============================================================================

@routes_blueprint.route('/enrollment-ms')
@login_required
def enrollment_ms():
    _grade_order = ['7', '8']

    yr_filter = session.get('active_schoolyr', '')

    all_grades = sorted(
        set(c.grade_level for c in Course.query.filter_by(status='Active').all()
            if c.grade_level in _grade_order),
        key=lambda g: _grade_order.index(g)
    )

    grade_filter = request.args.get('grade', all_grades[0] if all_grades else '')

    sites = Site.query.order_by(Site.site_name).all()

    _sdc_keywords = ('special', 'sped', 'sdc', 'resource')

    def _inst(teacher):
        dept = (teacher.department or '').lower()
        return 'SDC' if any(k in dept for k in _sdc_keywords) else 'S'

    site_data = []

    for site in sites:
        courses = (Course.query
                   .filter_by(status='Active', site_id=site.id, grade_level=grade_filter)
                   .outerjoin(Teacher, Course.teacher_id == Teacher.id)
                   .order_by(Teacher.last_name, Course.period)
                   .all())
        if not courses:
            continue

        rows = []
        site_total = 0
        for course in courses:
            teacher  = course.teacher
            enrolled = len(course.active_students)
            capacity = course.max_students or 0
            if not teacher and enrolled == 0:
                continue
            rows.append({
                'teacher':    f'{teacher.last_name}, {teacher.first_name}' if teacher else 'Unassigned',
                'teacher_id': teacher.id if teacher else None,
                'inst':       _inst(teacher) if teacher else 'S',
                'section_id': course.section_id or '—',
                'course_id':  course.id,
                'grade':      course.grade_level,
                'totals':     enrolled,
                'capacity':   capacity,
                'available':  capacity - enrolled,
            })
            site_total += enrolled

        if not rows:
            continue

        site_available = sum(r['available'] for r in rows)
        site_data.append({
            'site_name': site.site_name,
            'rows':      rows,
            'total':     site_total,
            'available': site_available,
        })

    total_available = sum(s['available'] for s in site_data)
    total_enrolled  = sum(s['total']     for s in site_data)
    total_capacity  = sum(r['capacity'] for s in site_data for r in s['rows'])

    return render_template('dashboard/enrollment_ms.html',
        current_page_name='Enrollment MS',
        all_grades=all_grades,
        grade_filter=grade_filter,
        site_data=site_data,
        total_available=total_available,
        total_enrolled=total_enrolled,
        total_capacity=total_capacity,
    )


# =============================================================================
# ENROLLMENT HS AVAILABILITY
# =============================================================================

@routes_blueprint.route('/enrollment-hs')
@login_required
def enrollment_hs():
    _grade_order = ['9', '10', '11', '12']

    yr_filter = session.get('active_schoolyr', '')

    all_grades = sorted(
        set(c.grade_level for c in Course.query.filter_by(status='Active').all()
            if c.grade_level in _grade_order),
        key=lambda g: _grade_order.index(g)
    )

    grade_filter = request.args.get('grade', all_grades[0] if all_grades else '')

    sites = Site.query.order_by(Site.site_name).all()

    _sdc_keywords = ('special', 'sped', 'sdc', 'resource')

    def _inst(teacher):
        dept = (teacher.department or '').lower()
        return 'SDC' if any(k in dept for k in _sdc_keywords) else 'S'

    site_data = []

    for site in sites:
        courses = (Course.query
                   .filter_by(status='Active', site_id=site.id, grade_level=grade_filter)
                   .outerjoin(Teacher, Course.teacher_id == Teacher.id)
                   .order_by(Teacher.last_name, Course.period)
                   .all())
        if not courses:
            continue

        rows = []
        site_total = 0
        for course in courses:
            teacher  = course.teacher
            enrolled = len(course.active_students)
            capacity = course.max_students or 0
            if not teacher and enrolled == 0:
                continue
            rows.append({
                'teacher':    f'{teacher.last_name}, {teacher.first_name}' if teacher else 'Unassigned',
                'teacher_id': teacher.id if teacher else None,
                'inst':       _inst(teacher) if teacher else 'S',
                'section_id': course.section_id or '—',
                'course_id':  course.id,
                'grade':      course.grade_level,
                'totals':     enrolled,
                'capacity':   capacity,
                'available':  capacity - enrolled,
            })
            site_total += enrolled

        if not rows:
            continue

        site_available = sum(r['available'] for r in rows)
        site_data.append({
            'site_name': site.site_name,
            'rows':      rows,
            'total':     site_total,
            'available': site_available,
        })

    total_available = sum(s['available'] for s in site_data)
    total_enrolled  = sum(s['total']     for s in site_data)
    total_capacity  = sum(r['capacity'] for s in site_data for r in s['rows'])

    return render_template('dashboard/enrollment_hs.html',
        current_page_name='Enrollment HS',
        all_grades=all_grades,
        grade_filter=grade_filter,
        site_data=site_data,
        total_available=total_available,
        total_enrolled=total_enrolled,
        total_capacity=total_capacity,
    )


# =============================================================================
# SWD DASHBOARD
# =============================================================================

@routes_blueprint.route('/swd')
@login_required
def swd_dashboard():

    site_filter   = session.get('active_site_filter', '')
    yr_filter     = session.get('active_schoolyr', '')
    status_filter = session.get('active_status_filter', 'active')
    snap_date_str = session.get('active_snap_date', '')

    snap_date = None
    if snap_date_str:
        try:
            snap_date = datetime.strptime(snap_date_str, '%Y-%m-%d').date()
        except ValueError:
            snap_date_str = ''

    ref_date = snap_date or datetime.now().date()

    def _date_filter(q):
        if status_filter == 'active':
            return q.filter(
                db.or_(Student.enter_date.is_(None), Student.enter_date <= ref_date),
                db.or_(Student.exit_date.is_(None),  Student.exit_date  >= ref_date),
            )
        elif status_filter == 'inactive':
            return q.filter(Student.exit_date.isnot(None), Student.exit_date < ref_date)
        return q

    # Total enrollment (for % context)
    enrollment_base = _date_filter(Student.query)
    if site_filter:
        enrollment_base = enrollment_base.filter(Student.site_id == site_filter)
    if yr_filter:
        enrollment_base = enrollment_base.filter(Student.schoolyr == yr_filter)
    total_enrollment = enrollment_base.count()

    # SWD base — all above filters + must have a disability code
    base = enrollment_base.filter(Student.disability.isnot(None), Student.disability != '')
    total_swd = base.count()

    # KPI counts — all scoped to SWD students
    sed504_count    = base.filter_by(sed504=True).count()
    el_count        = base.filter_by(english_status='EL').count()
    homeless_count  = base.filter(Student.dwelling.isnot(None), Student.dwelling != '').count()
    frm_count       = base.filter(Student.frm_code.in_(['F', 'R'])).count()
    foster_count    = base.filter_by(foster=True).count()
    migrant_count   = base.filter_by(migrant=True).count()

    def agg(col):
        q = _date_filter(db.session.query(col, func.count(Student.id)))
        q = q.filter(Student.disability.isnot(None), Student.disability != '')
        if site_filter:
            q = q.filter(Student.site_id == site_filter)
        if yr_filter:
            q = q.filter(Student.schoolyr == yr_filter)
        return q.group_by(col).all()

    # Disability breakdown (sorted by count desc)
    _dis_map = {
        'AU':  'Autism',              'DB':  'Deaf-Blindness',
        'DD':  'Developmental Delay', 'ED':  'Emotional Disturbance',
        'HH':  'Hard of Hearing',     'ID':  'Intellectual Disability',
        'MD':  'Multiple Disabilities','OHI': 'Other Health Impairment',
        'OI':  'Orthopedic Impairment','SLD': 'Specific Learning Disability',
        'SLI': 'Speech/Language',     'TBI': 'Traumatic Brain Injury',
        'VI':  'Visual Impairment',
    }
    dis_rows = agg(Student.disability)
    dis_rows_sorted = sorted(dis_rows, key=lambda x: x[1], reverse=True)
    disability_labels = [_dis_map.get(r[0], r[0] or 'Unknown') for r in dis_rows_sorted]
    disability_counts = [r[1] for r in dis_rows_sorted]

    # Grade breakdown
    _grade_order = ['TK','KN','1','2','3','4','5','6','7','8','9','10','11','12']
    grade_dict   = {r[0]: r[1] for r in agg(Student.grade)}
    _g_labels    = [g for g in _grade_order if g in grade_dict]
    grade_labels = _g_labels
    grade_counts = [grade_dict[g] for g in _g_labels]

    # Gender breakdown
    _gen_map = {'M': 'Male', 'F': 'Female', 'X': 'Non-Binary', 'U': 'Unknown'}
    gen_rows      = agg(Student.gender)
    gender_labels = [_gen_map.get(r[0], r[0] or 'Unknown') for r in gen_rows]
    gender_counts = [r[1] for r in gen_rows]

    # Ethnicity table
    _eth_map = {
        '100': 'Native American', '200': 'Asian', '300': 'Pacific Islander',
        '400': 'Filipino', '500': 'Hispanic/Latino', '600': 'African American',
        '700': 'White', '900': 'Two or More Races',
    }
    eth_rows = agg(Student.ethnicity)
    ethnicity_table_data = [
        (r[0] or '', _eth_map.get(r[0], r[0] or 'Unknown'), r[1]) for r in
        sorted(eth_rows, key=lambda x: x[1], reverse=True)
    ]

    # Site table (SWD by site, ignores site filter)
    site_q = _date_filter(
        db.session.query(Site.id, Site.site_acronyms, func.count(Student.id))
        .join(Student, Site.id == Student.site_id)
    ).filter(Student.disability.isnot(None), Student.disability != '')
    if yr_filter:
        site_q = site_q.filter(Student.schoolyr == yr_filter)
    site_table_data  = site_q.group_by(Site.id, Site.site_acronyms).order_by(Site.site_acronyms).all()
    site_grand_total = sum(r[2] for r in site_table_data)

    return render_template('dashboard/swd.html',
        current_page_name='SWD',
        snap_date_str=snap_date_str,
        total=total_swd, total_swd=total_swd, total_enrollment=total_enrollment,
        sed504_count=sed504_count, el_count=el_count,
        homeless_count=homeless_count, frm_count=frm_count,
        foster_count=foster_count, migrant_count=migrant_count,
        disability_labels=disability_labels, disability_counts=disability_counts,
        grade_labels=grade_labels, grade_counts=grade_counts,
        gender_labels=gender_labels, gender_counts=gender_counts,
        ethnicity_table_data=ethnicity_table_data,
        site_table_data=site_table_data, site_grand_total=site_grand_total,
    )


# =============================================================================
# ENGLISH LEARNER PROGRESS DASHBOARD
# =============================================================================

@routes_blueprint.route('/el-progress')
@login_required
def el_progress_dashboard():

    site_filter   = session.get('active_site_filter', '')
    yr_filter     = session.get('active_schoolyr', '')
    status_filter = session.get('active_status_filter', 'active')
    snap_date_str = session.get('active_snap_date', '')

    snap_date = None
    if snap_date_str:
        try:
            snap_date = datetime.strptime(snap_date_str, '%Y-%m-%d').date()
        except ValueError:
            snap_date_str = ''
    ref_date = snap_date or datetime.now().date()

    def _date_filter(q):
        if status_filter == 'active':
            return q.filter(
                db.or_(Student.enter_date.is_(None), Student.enter_date <= ref_date),
                db.or_(Student.exit_date.is_(None),  Student.exit_date  >= ref_date),
            )
        elif status_filter == 'inactive':
            return q.filter(Student.exit_date.isnot(None), Student.exit_date < ref_date)
        return q

    enrollment_base = _date_filter(Student.query)
    if site_filter:
        enrollment_base = enrollment_base.filter(Student.site_id == site_filter)
    if yr_filter:
        enrollment_base = enrollment_base.filter(Student.schoolyr == yr_filter)
    total_enrollment = enrollment_base.count()

    # Language-status KPI counts. english_status codes per forms.py _ENGLISH_STATUS_CHOICES:
    # EO=English Only, IFEP=Initially Fluent, EL=English Learner, RFEP=Reclassified Fluent, TBD=pending.
    eo_count      = enrollment_base.filter(Student.english_status == 'EO').count()
    el_count      = enrollment_base.filter(Student.english_status == 'EL').count()
    ifep_count    = enrollment_base.filter(Student.english_status == 'IFEP').count()
    rfep_count    = enrollment_base.filter(Student.english_status == 'RFEP').count()
    tbd_count     = enrollment_base.filter(Student.english_status == 'TBD').count()
    missing_count = enrollment_base.filter(
        db.or_(Student.english_status.is_(None), Student.english_status == '')
    ).count()

    # Reclassification rate: RFEP as a share of everyone who has ever been through the EL pipeline.
    # Note: there's no field tracking *when* a student became EL or was reclassified, so this is a
    # point-in-time ratio, not a cohort/time-to-reclassify metric — that would need a schema change.
    ever_el_pool = el_count + rfep_count
    reclass_rate = round(rfep_count / ever_el_pool * 100, 1) if ever_el_pool else 0.0

    el_base = enrollment_base.filter(Student.english_status == 'EL')

    # EL by grade
    def agg_el(col):
        q = _date_filter(db.session.query(col, func.count(Student.id))).filter(Student.english_status == 'EL')
        if site_filter:
            q = q.filter(Student.site_id == site_filter)
        if yr_filter:
            q = q.filter(Student.schoolyr == yr_filter)
        return q.group_by(col).all()

    _grade_order = ['TK', 'KN', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
    grade_dict   = {r[0]: r[1] for r in agg_el(Student.grade)}
    _g_labels    = [g for g in _grade_order if g in grade_dict]
    grade_labels = _g_labels
    grade_counts = [grade_dict[g] for g in _g_labels]

    # Language status distribution (donut)
    status_labels = ['EL', 'RFEP', 'IFEP', 'EO', 'TBD', 'Missing']
    status_counts = [el_count, rfep_count, ifep_count, eo_count, tbd_count, missing_count]

    # EL + RFEP by site, with a per-site reclassification rate
    el_by_site   = dict(_date_filter(
        db.session.query(Site.id, func.count(Student.id)).join(Student, Site.id == Student.site_id)
    ).filter(Student.english_status == 'EL').group_by(Site.id).all())
    rfep_by_site = dict(_date_filter(
        db.session.query(Site.id, func.count(Student.id)).join(Student, Site.id == Student.site_id)
    ).filter(Student.english_status == 'RFEP').group_by(Site.id).all())
    site_names = {s.id: s.site_name for s in Site.query.with_entities(Site.id, Site.site_name).all()}

    site_table_data = []
    for site_id in set(el_by_site) | set(rfep_by_site):
        el_n, rfep_n = el_by_site.get(site_id, 0), rfep_by_site.get(site_id, 0)
        pool = el_n + rfep_n
        site_table_data.append((
            site_id, site_names.get(site_id, ''), el_n, rfep_n,
            round(rfep_n / pool * 100, 1) if pool else 0.0
        ))
    site_table_data.sort(key=lambda r: r[1])
    el_site_grand_total = sum(r[2] for r in site_table_data)

    # Academic support signals for currently-EL students — chronic absenteeism and F-grade rate,
    # the same underlying data Early Warning uses, narrowed to the EL population. Ellevation-style
    # "is the EL program working" signal, not just a headcount.
    schoolyr = yr_filter or '2025-2026'
    el_ssids      = {s.ssid for s in el_base.with_entities(Student.ssid).all() if s.ssid}
    el_student_ids = {s.student_id for s in el_base.with_entities(Student.student_id).all()}

    chronic_el = 0
    if el_ssids:
        abs_counts = dict(
            db.session.query(Absence.ssid, func.count(Absence.id))
            .filter(Absence.ssid.in_(el_ssids), Absence.school_yr == schoolyr)
            .group_by(Absence.ssid).all()
        )
        chronic_el = sum(1 for c in abs_counts.values() if c >= 18)

    f_el = 0
    if el_student_ids:
        f_el = (db.session.query(Grade.grades_stuid)
                .filter(Grade.grades_stuid.in_(el_student_ids),
                        Grade.grades_courseyr == schoolyr, Grade.grades_grade == 'F')
                .distinct().count())

    return render_template('dashboard/el_progress.html',
        current_page_name='English Learner Progress',
        total_enrollment=total_enrollment,
        el_count=el_count, rfep_count=rfep_count, ifep_count=ifep_count,
        eo_count=eo_count, tbd_count=tbd_count, missing_count=missing_count,
        reclass_rate=reclass_rate,
        chronic_el=chronic_el, f_el=f_el, schoolyr=schoolyr,
        grade_labels=grade_labels, grade_counts=grade_counts,
        status_labels=status_labels, status_counts=status_counts,
        site_table_data=site_table_data, el_site_grand_total=el_site_grand_total,
    )


# =============================================================================
# ACCOUNTABILITY-STYLE RATE INDICATORS
# (shared helpers for Chronic Absenteeism Rate, Suspension Rate, Cohort Progression —
# modeled on, not a certified match for, the CA School Dashboard's five-level status +
# year-over-year change methodology. Adjust _RATE_STATUS_BANDS if you need these to line
# up with a specific official cut-score table.)
# =============================================================================

_RATE_STATUS_BANDS = [
    (5.0,          'Very Low',  'blue',   '#1d4ed8'),
    (10.0,         'Low',       'green',  '#16a34a'),
    (16.5,         'Medium',    'yellow', '#ca8a04'),
    (24.5,         'High',      'orange', '#ea580c'),
    (float('inf'), 'Very High', 'red',    '#dc2626'),
]


def _rate_status(pct):
    """Bucket a percentage into a 5-level status band. Returns a dict with label/key/color."""
    for cutoff, label, key, color in _RATE_STATUS_BANDS:
        if pct < cutoff:
            return {'label': label, 'key': key, 'color': color}
    return {'label': 'Very High', 'key': 'red', 'color': '#dc2626'}


def _rate_change(current, prior):
    """Year-over-year change direction for a rate where LOWER is better (absenteeism,
    suspensions) — 'increased' is the unfavorable direction. Returns None fields if there's
    no prior-year figure to compare against."""
    if prior is None or current is None:
        return {'direction': None, 'label': 'No prior-year data', 'delta': None}
    delta = round(current - prior, 1)
    if abs(delta) < 0.5:
        direction, label = 'maintained', 'Maintained'
    elif delta > 0:
        direction, label = 'increased', 'Increased'
    else:
        direction, label = 'declined', 'Declined'
    return {'direction': direction, 'label': label, 'delta': delta}


def _prior_schoolyr(yr):
    """'2024-2025' -> '2023-2024'. Returns None if yr isn't in that format."""
    try:
        start, end = yr.split('-')
        return f'{int(start) - 1}-{int(end) - 1}'
    except (ValueError, AttributeError):
        return None


def _site_rate_rows(site_names, site_flagged, site_total):
    """Build sorted [{'site_name','pct','count','total','status'}, ...] rows, status precomputed
    via _rate_status() so templates never have to re-derive the band cut points themselves."""
    rows = []
    for sid, total in site_total.items():
        flagged = site_flagged.get(sid, 0)
        pct = round(flagged / total * 100, 1) if total else 0.0
        rows.append({
            'site_name': site_names.get(sid, ''), 'pct': pct,
            'count': flagged, 'total': total, 'status': _rate_status(pct),
        })
    rows.sort(key=lambda r: r['pct'], reverse=True)
    return rows


def _next_schoolyr(yr):
    """'2024-2025' -> '2025-2026'. Returns None if yr isn't in that format."""
    try:
        start, end = yr.split('-')
        return f'{int(start) + 1}-{int(end) + 1}'
    except (ValueError, AttributeError):
        return None


def _cohort_progression(entry_yr):
    """Track a 9th-grade entering cohort forward year by year, checking how many are still
    enrolled in the district at each step. This is the CA Dashboard's cohort Graduation Rate
    concept (% of a 9th-grade cohort that graduates 4 years later) — but a true 4-year outcome
    needs 4 full years of demographics.csv on hand. With fewer years loaded, this safely reports
    partial progression ("N of 4 years tracked") instead of a misleading graduation-rate number;
    it becomes the real thing automatically once a 4th year of data is uploaded.
    """
    _EXPECTED_GRADE_BY_STEP = ['9', '10', '11', '12']

    cohort_ids = {
        s.student_id for s in
        Student.query.filter(Student.schoolyr == entry_yr, Student.grade == '9')
        .with_entities(Student.student_id).all()
    }
    cohort_size = len(cohort_ids)
    if not cohort_size:
        return None

    steps = []
    yr = entry_yr
    for i, expected_grade in enumerate(_EXPECTED_GRADE_BY_STEP):
        if i > 0:
            yr = _next_schoolyr(yr)
        if not yr:
            break
        rows = (Student.query.filter(Student.schoolyr == yr, Student.student_id.in_(cohort_ids))
                .with_entities(Student.student_id, Student.grade).all())
        if not rows:
            break  # no data uploaded yet for this year — stop rather than report a false 0%
        present_ids  = {r.student_id for r in rows}
        on_grade_ids = {r.student_id for r in rows if r.grade == expected_grade}
        steps.append({
            'schoolyr': yr, 'expected_grade': expected_grade,
            'present': len(present_ids), 'on_grade': len(on_grade_ids),
            'present_pct': round(len(present_ids) / cohort_size * 100, 1),
        })

    return {
        'entry_yr': entry_yr, 'cohort_size': cohort_size, 'steps': steps,
        'years_tracked': len(steps), 'complete': len(steps) == 4,
    }


def _chronic_absenteeism_rate(schoolyr, site_filter=None, extra_filter=None):
    """Chronic absenteeism rate (% of students absent >=10% of their own enrolled days) for a
    completed school year — a full-year retrospective figure, not a live snapshot, so it's
    comparable year over year regardless of today's date or the active/inactive session filter.
    `extra_filter` narrows to a subgroup (e.g. Student.disability.isnot(None)) — used by the
    Equity Gaps dashboard to compute the same rate for a student group vs. the whole district.
    Returns (chronic_pct, chronic_count, total_students, site_rows); site_rows is a list of
    dicts (see _site_rate_rows) sorted by rate descending.
    """
    from collections import defaultdict
    from datetime import date as _date, timedelta

    if not schoolyr or '-' not in schoolyr:
        return None, 0, 0, []

    start_year   = int(schoolyr.split('-')[0])
    school_start = _date(start_year, 8, 25)
    school_end   = _date(start_year + 1, 6, 10)

    student_q = Student.query.filter(Student.schoolyr == schoolyr)
    if site_filter:
        student_q = student_q.filter(Student.site_id == site_filter)
    if extra_filter is not None:
        student_q = student_q.filter(extra_filter)
    students = student_q.with_entities(
        Student.ssid, Student.site_id, Student.enter_date, Student.exit_date
    ).all()
    if not students:
        return None, 0, 0, []

    # Filtering Absence directly by (school_yr, site_id) — both columns it already has —
    # is far cheaper than passing the whole district's ssid set as a giant IN(...) clause.
    # Any ssid not in `students` below is simply never looked up, so extra rows here (e.g.
    # when `extra_filter` narrows to a subgroup) don't affect correctness.
    abs_q = Absence.query.filter(Absence.school_yr == schoolyr)
    if site_filter:
        abs_q = abs_q.filter(Absence.site_id == site_filter)
    abs_counts = dict(
        abs_q.with_entities(Absence.ssid, func.count(Absence.id))
        .group_by(Absence.ssid).all()
    )

    site_names = {s.id: s.site_name for s in Site.query.with_entities(Site.id, Site.site_name).all()}
    site_chronic = defaultdict(int)
    site_total   = defaultdict(int)
    chronic_count = 0

    for s in students:
        site_total[s.site_id] += 1
        if not s.ssid:
            continue
        eff_start = max(s.enter_date, school_start) if s.enter_date else school_start
        eff_end   = min(s.exit_date,  school_end)   if s.exit_date  else school_end
        if eff_start > eff_end:
            continue
        enrolled_days = _count_weekdays(eff_start, eff_end)
        if not enrolled_days:
            continue
        if abs_counts.get(s.ssid, 0) / enrolled_days * 100 >= 10:
            chronic_count += 1
            site_chronic[s.site_id] += 1

    total_students = len(students)
    chronic_pct = round(chronic_count / total_students * 100, 1) if total_students else 0.0
    site_rows = _site_rate_rows(site_names, site_chronic, site_total)
    return chronic_pct, chronic_count, total_students, site_rows


def _suspension_rate(schoolyr, site_filter=None, extra_filter=None):
    """Suspension rate (% of enrolled students with at least one suspension day) for a
    completed school year. `extra_filter` narrows to a subgroup — see _chronic_absenteeism_rate.
    Returns (rate_pct, suspended_count, total_students, site_rows);
    site_rows is a list of dicts (see _site_rate_rows) sorted by rate descending.
    """
    from collections import defaultdict

    if not schoolyr or '-' not in schoolyr:
        return None, 0, 0, []

    student_q = Student.query.filter(Student.schoolyr == schoolyr)
    if site_filter:
        student_q = student_q.filter(Student.site_id == site_filter)
    if extra_filter is not None:
        student_q = student_q.filter(extra_filter)
    students = student_q.with_entities(Student.ssid, Student.site_id).all()
    if not students:
        return None, 0, 0, []

    ssids = {s.ssid for s in students if s.ssid}
    suspended_ssids = set()
    if ssids:
        suspended_ssids = {
            r[0] for r in db.session.query(Incident.sisid)
            .filter(Incident.sisid.in_(ssids), Incident.schoolyr == schoolyr,
                    Incident.suspended_days.isnot(None), Incident.suspended_days > 0)
            .distinct().all()
        }

    site_names = {s.id: s.site_name for s in Site.query.with_entities(Site.id, Site.site_name).all()}
    site_susp = defaultdict(int)
    site_total = defaultdict(int)
    suspended_count = 0

    for s in students:
        site_total[s.site_id] += 1
        if s.ssid and s.ssid in suspended_ssids:
            suspended_count += 1
            site_susp[s.site_id] += 1

    total_students = len(students)
    rate_pct = round(suspended_count / total_students * 100, 1) if total_students else 0.0
    site_rows = _site_rate_rows(site_names, site_susp, site_total)
    return rate_pct, suspended_count, total_students, site_rows


# Student groups compared on the Equity Gaps dashboard — the CA Dashboard's core idea of
# surfacing performance gaps between groups per indicator, rather than only a district average.
_EQUITY_SUBGROUPS = [
    ('swd',      'Students with Disabilities', lambda s: bool(s.disability)),
    ('el',       'English Learners',           lambda s: s.english_status == 'EL'),
    ('frm',      'Low Income (FRM)',           lambda s: s.frm_code in ('F', 'R')),
    ('foster',   'Foster Youth',               lambda s: bool(s.foster)),
    ('homeless', 'Homeless',                   lambda s: bool(s.dwelling)),
]

_EQUITY_ETHNICITY_MAP = {
    '100': 'Native American', '200': 'Asian', '300': 'Pacific Islander',
    '400': 'Filipino', '500': 'Hispanic/Latino', '600': 'African American',
    '700': 'White', '900': 'Two or More Races',
}


def _equity_gap_rows(schoolyr, site_filter=None):
    """For each key student group, compute Chronic Absenteeism Rate and Suspension Rate
    against the whole-district baseline, with the gap in percentage points. A positive gap
    means the group's rate is worse (higher) than the district average for that indicator.

    Deliberately NOT built on top of _chronic_absenteeism_rate()/_suspension_rate() called once
    per subgroup — that re-fetches absence/incident data and re-walks each student's enrolled-days
    window from scratch per call (6 subgroups x 2 indicators = 12 calls), which measured at ~8.5s.
    This does one query pass and classifies every student once, then slices the same in-memory
    result per subgroup — same page, ~10x faster.
    """
    from datetime import date as _date, timedelta

    if not schoolyr or '-' not in schoolyr:
        return [], [], None, None

    start_year   = int(schoolyr.split('-')[0])
    school_start = _date(start_year, 8, 25)
    school_end   = _date(start_year + 1, 6, 10)

    student_q = Student.query.filter(Student.schoolyr == schoolyr)
    if site_filter:
        student_q = student_q.filter(Student.site_id == site_filter)
    students = student_q.with_entities(
        Student.ssid, Student.enter_date, Student.exit_date,
        Student.disability, Student.english_status, Student.frm_code, Student.foster, Student.dwelling,
        Student.ethnicity
    ).all()
    if not students:
        return [], [], None, None

    ssids = {s.ssid for s in students if s.ssid}
    abs_counts = dict(
        db.session.query(Absence.ssid, func.count(Absence.id))
        .filter(Absence.ssid.in_(ssids), Absence.school_yr == schoolyr)
        .group_by(Absence.ssid).all()
    ) if ssids else {}
    suspended_ssids = set()
    if ssids:
        suspended_ssids = {
            r[0] for r in db.session.query(Incident.sisid)
            .filter(Incident.sisid.in_(ssids), Incident.schoolyr == schoolyr,
                    Incident.suspended_days.isnot(None), Incident.suspended_days > 0)
            .distinct().all()
        }

    def _is_chronic(s):
        if not s.ssid:
            return False
        eff_start = max(s.enter_date, school_start) if s.enter_date else school_start
        eff_end   = min(s.exit_date,  school_end)   if s.exit_date  else school_end
        if eff_start > eff_end:
            return False
        enrolled_days = _count_weekdays(eff_start, eff_end)
        return bool(enrolled_days) and abs_counts.get(s.ssid, 0) / enrolled_days * 100 >= 10

    flags = [{'chronic': _is_chronic(s), 'suspended': bool(s.ssid and s.ssid in suspended_ssids)} for s in students]

    total = len(students)
    baseline_ca = round(sum(f['chronic']   for f in flags) / total * 100, 1) if total else 0.0
    baseline_sr = round(sum(f['suspended'] for f in flags) / total * 100, 1) if total else 0.0

    def _gap(pct, baseline):
        return round(pct - baseline, 1) if pct is not None and baseline is not None else None

    rows = []
    for key, label, in_group in _EQUITY_SUBGROUPS:
        group_idx = [i for i, s in enumerate(students) if in_group(s)]
        group_size = len(group_idx)
        if group_size:
            ca_pct = round(sum(flags[i]['chronic']   for i in group_idx) / group_size * 100, 1)
            sr_pct = round(sum(flags[i]['suspended'] for i in group_idx) / group_size * 100, 1)
        else:
            ca_pct = sr_pct = None
        rows.append({
            'key': key, 'label': label, 'group_size': group_size,
            'chronic_absenteeism': {'pct': ca_pct, 'gap': _gap(ca_pct, baseline_ca)},
            'suspension_rate':     {'pct': sr_pct, 'gap': _gap(sr_pct, baseline_sr)},
        })

    # Race/Ethnicity — same single-pass data, just sliced a different way. Only codes actually
    # present in the data get a row, sorted by group size descending like the other ethnicity
    # tables elsewhere in the app.
    ethnicity_rows = []
    present_codes = sorted(
        {s.ethnicity for s in students if s.ethnicity},
        key=lambda code: sum(1 for s in students if s.ethnicity == code),
        reverse=True,
    )
    for code in present_codes:
        group_idx = [i for i, s in enumerate(students) if s.ethnicity == code]
        group_size = len(group_idx)
        ca_pct = round(sum(flags[i]['chronic']   for i in group_idx) / group_size * 100, 1)
        sr_pct = round(sum(flags[i]['suspended'] for i in group_idx) / group_size * 100, 1)
        ethnicity_rows.append({
            'key': code, 'label': _EQUITY_ETHNICITY_MAP.get(code, code), 'group_size': group_size,
            'chronic_absenteeism': {'pct': ca_pct, 'gap': _gap(ca_pct, baseline_ca)},
            'suspension_rate':     {'pct': sr_pct, 'gap': _gap(sr_pct, baseline_sr)},
        })

    return rows, ethnicity_rows, baseline_ca, baseline_sr


# =============================================================================
# EQUITY GAPS DASHBOARD
# =============================================================================

@routes_blueprint.route('/equity-gaps')
@login_required
def equity_gaps_dashboard():
    yr_filter   = session.get('active_schoolyr', '')
    site_filter = session.get('active_site_filter', '')
    org = db.session.get(Organization, 1)
    indicator_yr = yr_filter or (org.current_school_year if org else None)

    rows, ethnicity_rows, baseline_ca, baseline_sr = ([], [], None, None)
    if indicator_yr:
        rows, ethnicity_rows, baseline_ca, baseline_sr = _equity_gap_rows(indicator_yr, site_filter)

    return render_template('dashboard/equity_gaps.html',
        current_page_name='Equity Gaps',
        indicator_yr=indicator_yr,
        rows=rows,
        ethnicity_rows=ethnicity_rows,
        baseline_ca=baseline_ca,
        baseline_sr=baseline_sr,
    )


# =============================================================================
# ABSENTEEISM DASHBOARD
# =============================================================================

@routes_blueprint.route('/absenteeism')
@login_required
def absenteeism():
    import calendar

    site_filter   = session.get('active_site_filter', '')
    yr_filter     = session.get('active_schoolyr', '')
    snap_date_str = session.get('active_snap_date', '')

    snap_date = None
    if snap_date_str:
        try:
            snap_date = datetime.strptime(snap_date_str, '%Y-%m-%d').date()
        except ValueError:
            snap_date_str = ''

    def base_q():
        q = Absence.query.filter(Absence.abs_date.isnot(None))
        if site_filter:
            q = q.filter(Absence.site_id == site_filter)
        if yr_filter:
            q = q.filter(Absence.school_yr == yr_filter)
        if snap_date:
            q = q.filter(Absence.abs_date <= snap_date)
        return q

    total_absences = base_q().count()

    # Enrolled students for Absenteeism rate
    from datetime import date as _date
    today = _date.today()
    student_base = Student.query
    status_filter = session.get('active_status_filter', 'active')
    if status_filter == 'active':
        student_base = student_base.filter(
            db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
            db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
        )
    if site_filter:
        student_base = student_base.filter(Student.site_id == site_filter)
    if yr_filter:
        student_base = student_base.filter(Student.schoolyr == yr_filter)
    total_students = student_base.count()
    avg_absences_per_student = round(total_absences / total_students, 1) if total_students else 0.0

    # School days elapsed (approx: weekdays since Aug 25 of the start year)
    if yr_filter and '-' in yr_filter:
        start_year = int(yr_filter.split('-')[0])
    else:
        start_year = today.year if today.month >= 8 else today.year - 1
    school_start = _date(start_year, 8, 25)
    ref_end      = today if today <= _date(start_year + 1, 6, 10) else _date(start_year + 1, 6, 10)
    school_days  = max(_count_weekdays(school_start, ref_end), 1)

    total_possible  = total_students * school_days
    absence_rate    = round(total_absences / total_possible * 100, 1) if total_possible else 0.0

    # Chronic absenteeism — per student (ssid), classified against each student's own
    # enrolled days (not a blanket school_days figure), matching /absences' methodology
    # exactly so the KPI counts here match what clicking through shows.
    ssid_rows = (base_q()
                 .with_entities(Absence.ssid, func.count(Absence.id).label('cnt'))
                 .group_by(Absence.ssid).all())

    _abs_ssids = {r.ssid for r in ssid_rows if r.ssid}
    _stu_enroll = {}
    if _abs_ssids:
        _stu_enroll = {
            s.ssid: s for s in Student.query
                .with_entities(Student.ssid, Student.enter_date, Student.exit_date)
                .filter(Student.ssid.in_(_abs_ssids)).all()
        }

    def _enrolled_days(s):
        eff_start = max(s.enter_date, school_start) if s.enter_date else school_start
        eff_end   = min(s.exit_date,  ref_end)      if s.exit_date  else ref_end
        return _count_weekdays(eff_start, eff_end)

    borderline_count = chronic_count = severe_count = 0
    for r in ssid_rows:
        stu = _stu_enroll.get(r.ssid)
        if not stu:
            continue
        enrolled = _enrolled_days(stu)
        if not enrolled:
            continue
        pct = r.cnt / enrolled * 100
        if pct >= 25:
            severe_count += 1
        elif pct >= 10:
            chronic_count += 1
        elif pct > 7:
            borderline_count += 1

    chronic_students = chronic_count + severe_count
    chronic_pct      = round(chronic_students / total_students * 100, 1) if total_students else 0.0

    # Every breakdown below used to fetch one row per absence (all_abs, hundreds of thousands
    # of rows district-wide) and group it in Python. Grouping in SQL instead means the DB
    # transfers a few dozen aggregate rows per chart instead of the whole absence table.
    from collections import defaultdict

    # Absences per month
    month_rows = (base_q()
                  .with_entities(func.month(Absence.abs_date).label('m'), func.count(Absence.id).label('cnt'))
                  .group_by('m').all())
    month_dict = {r.m: r.cnt for r in month_rows if r.m}
    _month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    month_labels = [_month_names[m-1] for m in sorted(month_dict)]
    month_counts = [month_dict[m] for m in sorted(month_dict)]

    # Absences per grade
    grade_rows = (base_q()
                  .with_entities(Absence.grade, func.count(Absence.id).label('cnt'))
                  .group_by(Absence.grade).all())
    grade_dict = defaultdict(int)
    for r in grade_rows:
        grade_dict[r.grade or 'N/A'] += r.cnt
    _grade_order = ['TK','KN','1','2','3','4','5','6','7','8','9','10','11','12','N/A']
    grade_sorted = sorted(grade_dict.items(), key=lambda x: _grade_order.index(x[0]) if x[0] in _grade_order else len(_grade_order))
    grade_labels = [g for g, _ in grade_sorted]
    grade_counts = [c for _, c in grade_sorted]
    grade_pcts   = [round(c / total_absences * 100, 1) if total_absences else 0
                                for _, c in grade_sorted]

    # Absences per ethnicity — reuses ssid_rows (already fetched above, one row per student
    # with an absence) instead of a fresh pass over every absence row, joined in Python via
    # ssid → Student lookup since Absence.ssid isn't an FK.
    _eth_map = {'100':'Native American','200':'Asian','300':'Pacific Islander',
                '400':'Filipino','500':'Hispanic/Latino','600':'African American',
                '700':'White','900':'Two or More Races'}
    ssid_eth = {s.ssid: s.ethnicity for s in
                Student.query.with_entities(Student.ssid, Student.ethnicity)
                .filter(Student.ssid.in_(_abs_ssids)).all()} if _abs_ssids else {}
    eth_dict = defaultdict(int)
    for r in ssid_rows:
        eth = ssid_eth.get(r.ssid, None)
        eth_dict[_eth_map.get(eth, 'Unknown')] += r.cnt
    ethnicity_data = sorted(
        [(label, cnt, round(cnt / total_absences * 100, 1) if total_absences else 0)
         for label, cnt in eth_dict.items()],
        key=lambda x: x[1], reverse=True
    )

    # Most absences in a day — direct SQL GROUP BY so filters are always applied
    top_days = (base_q()
                .with_entities(Absence.abs_date, func.count(Absence.id).label('cnt'))
                .group_by(Absence.abs_date)
                .order_by(func.count(Absence.id).desc())
                .limit(10)
                .all())

    # Totals by site
    site_abs_rows = (base_q()
                      .with_entities(Absence.site_id, func.count(Absence.id).label('cnt'))
                      .group_by(Absence.site_id).all())
    site_total_abs = {r.site_id: r.cnt for r in site_abs_rows}
    sites_all = Site.query.order_by(Site.site_name).all()
    # One grouped query for every site's enrolled-student count, instead of a separate
    # .count() query per site (was N+1 across every site in the district).
    site_student_counts = dict(
        student_base.with_entities(Student.site_id, func.count(Student.id))
        .group_by(Student.site_id).all()
    )
    site_table = []
    for s in sites_all:
        if s.id not in site_total_abs:
            continue
        sp  = max(site_student_counts.get(s.id, 0) * school_days, 1)
        att = round(site_total_abs[s.id] / sp * 100, 1)
        site_table.append((s.site_acronyms, site_total_abs[s.id], att))

    # Absences by day of week — MySQL WEEKDAY() returns 0=Mon..6=Sun, same convention as
    # Python's date.weekday(), so no remapping is needed on the way out.
    _dow_names = {0:'Monday',1:'Tuesday',2:'Wednesday',3:'Thursday',4:'Friday',5:'Saturday',6:'Sunday'}
    dow_rows = (base_q()
                .with_entities(func.weekday(Absence.abs_date).label('dow'), func.count(Absence.id).label('cnt'))
                .group_by('dow').all())
    dow_dict = {r.dow: r.cnt for r in dow_rows if r.dow is not None}
    weekday_keys = sorted(k for k in dow_dict if k < 5)  # Mon–Fri only
    dow_labels  = [_dow_names[k] for k in weekday_keys]
    dow_counts  = [dow_dict[k] for k in weekday_keys]

    # Chronic Absenteeism Rate indicator — a full-year retrospective figure (not filtered by
    # snap_date/active-status) so this year's rate and last year's rate are computed the same
    # way and are genuinely comparable, mirroring how the CA School Dashboard publishes rates.
    indicator_yr = yr_filter or (Organization.query.get(1).current_school_year if Organization.query.get(1) else None)
    ca_pct, ca_count, ca_total, ca_site_rows = _chronic_absenteeism_rate(indicator_yr, site_filter)
    ca_prior_pct = None
    if indicator_yr:
        prior_yr = _prior_schoolyr(indicator_yr)
        if prior_yr:
            ca_prior_pct = _chronic_absenteeism_rate(prior_yr, site_filter)[0]
    ca_status = _rate_status(ca_pct) if ca_pct is not None else None
    ca_change = _rate_change(ca_pct, ca_prior_pct)

    return render_template('dashboard/absenteeism.html',
        current_page_name='Absenteeism',
        total_absences=total_absences, total_students=total_students,
        avg_absences_per_student=avg_absences_per_student,
        absence_rate=absence_rate, chronic_pct=chronic_pct, chronic_students=chronic_students,
        borderline_count=borderline_count, chronic_count=chronic_count, severe_count=severe_count,
        month_labels=month_labels, month_counts=month_counts,
        grade_labels=grade_labels, grade_counts=grade_counts, grade_pcts=grade_pcts,
        ethnicity_data=ethnicity_data,
        top_days=top_days,
        site_table=site_table,
        dow_labels=dow_labels, dow_counts=dow_counts,
        indicator_yr=indicator_yr, ca_pct=ca_pct, ca_count=ca_count, ca_total=ca_total,
        ca_site_rows=ca_site_rows, ca_status=ca_status, ca_change=ca_change,
    )


@routes_blueprint.route('/attendance-rates')
@login_required
def attendance_rates():
    from collections import defaultdict
    from datetime import timedelta, date as _date

    yr_filter   = session.get('active_schoolyr', '')
    site_filter = session.get('active_site_filter', '')
    today       = _date.today()

    # School days elapsed
    if yr_filter and '-' in yr_filter:
        start_year = int(yr_filter.split('-')[0])
    else:
        start_year = today.year if today.month >= 8 else today.year - 1
    school_start = _date(start_year, 8, 25)
    ref_end      = today if today <= _date(start_year + 1, 6, 10) else _date(start_year + 1, 6, 10)
    school_days  = max(_count_weekdays(school_start, ref_end), 1)

    # Absence counts per SSID
    abs_q = Absence.query
    if yr_filter:
        abs_q = abs_q.filter(Absence.school_yr == yr_filter)
    if site_filter:
        site_obj = Site.query.get(site_filter)
        if site_obj:
            abs_q = abs_q.filter(Absence.site_id == site_obj.id)
    ssid_abs = defaultdict(int)
    for a in abs_q.with_entities(Absence.ssid, func.count(Absence.id)).group_by(Absence.ssid).all():
        if a[0]:
            ssid_abs[a[0]] = a[1]

    # Build per-course data
    _grade_order = ['TK', 'KN', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
    courses_q = Course.query.filter_by(status='Active').options(joinedload(Course.teacher))
    if site_filter:
        courses_q = courses_q.filter(Course.site_id == site_filter)
    courses_list = courses_q.order_by(Course.grade_level, Course.course_name).all()

    # One lightweight (course_id, ssid) query for every active enrollment district-wide,
    # instead of accessing course.active_students per course — that was a separate query
    # per course (1000+ courses meant 1000+ extra round trips) and loaded full Student rows
    # (name, dates, etc.) when only ssid is actually used below.
    course_ids = [c.id for c in courses_list]
    course_ssids = defaultdict(list)
    if course_ids:
        enroll_rows = (
            db.session.query(student_course.c.course_id, Student.ssid)
            .join(Student, Student.id == student_course.c.student_id)
            .filter(student_course.c.course_id.in_(course_ids),
                    student_course.c.leave_date.is_(None))
            .all()
        )
        for course_id, ssid in enroll_rows:
            course_ssids[course_id].append(ssid)

    grades_data = defaultdict(list)
    for course in courses_list:
        grade       = course.grade_level or 'N/A'
        enrolled    = course_ssids.get(course.id, [])
        n_enrolled  = len(enrolled)
        if n_enrolled == 0:
            continue
        absences    = sum(ssid_abs.get(ssid, 0) for ssid in enrolled if ssid)
        possible    = n_enrolled * school_days
        att_pct     = round((possible - absences) / possible * 100, 1) if possible else 100.0
        grades_data[grade].append({
            'teacher':     f'{course.teacher.last_name}, {course.teacher.first_name}' if course.teacher else 'Unassigned',
            'teacher_id':  course.teacher.id if course.teacher else None,
            'course_name': course.course_name,
            'section_id':  course.section_id,
            'course_id':   course.id,
            'enrolled':    n_enrolled,
            'absences':    absences,
            'att_pct':     att_pct,
        })

    sorted_grades = sorted(grades_data.keys(),
                           key=lambda g: _grade_order.index(g) if g in _grade_order else 99)

    # KPI summary
    all_rows       = [r for rows in grades_data.values() for r in rows]
    enrolled_q = Student.query.filter(
        db.or_(Student.enter_date.is_(None), Student.enter_date <= today),
        db.or_(Student.exit_date.is_(None),  Student.exit_date  >= today),
    )
    if yr_filter:
        enrolled_q = enrolled_q.filter(Student.schoolyr == yr_filter)
    if site_filter:
        enrolled_q = enrolled_q.filter(Student.site_id == site_filter)
    total_enrolled = enrolled_q.count()
    total_absences = sum(r['absences'] for r in all_rows)
    possible_all   = total_enrolled * school_days
    overall_att    = round((possible_all - total_absences) / possible_all * 100, 1) if possible_all else 100.0
    # Best grade
    grade_avgs  = {g: round(sum(r['att_pct'] for r in rows) / len(rows), 1)
                   for g, rows in grades_data.items() if rows}
    best_grade  = max(grade_avgs, key=grade_avgs.get) if grade_avgs else '—'

    # Best course
    best_course = max(all_rows, key=lambda r: r['att_pct']) if all_rows else None

    return render_template('dashboard/attendance_rates.html',
        current_page_name='Attendance Rates',
        overall_att=overall_att, total_enrolled=total_enrolled,
        best_course=best_course,
        best_grade=best_grade, best_grade_att=grade_avgs.get(best_grade, 0),
        grades_data=grades_data, sorted_grades=sorted_grades,
        school_days=school_days,
    )


@routes_blueprint.route('/absences', methods=['GET'])
@login_required
def absences():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search         = request.args.get('search', '').strip()
    grade_filter   = request.args.get('grade_filter', '').strip()
    stu_status     = request.args.get('stu_status', '').strip()
    abs_types      = request.args.getlist('abs_type')
    subgroups      = [s.strip() for s in request.args.getlist('subgroup') if s.strip()]
    english_status = [s.strip() for s in request.args.getlist('english_status') if s.strip()]
    gender_filters = [s.strip() for s in request.args.getlist('gender') if s.strip()]
    site_filter    = session.get('active_site_filter', '')
    yr_filter      = session.get('active_schoolyr', '')

    query = Absence.query
    if site_filter:
        query = query.filter(Absence.site_id == site_filter)
    if yr_filter:
        query = query.filter(Absence.school_yr == yr_filter)
    if grade_filter:
        query = query.filter(Absence.grade == grade_filter)
    if abs_types:
        query = query.filter(Absence.abs_desc.in_(abs_types))
    if search:
        name_ssids = db.session.query(Student.ssid).filter(
            db.or_(
                Student.first_name.ilike(f'%{search}%'),
                Student.last_name.ilike(f'%{search}%'),
            ),
            Student.ssid.isnot(None), Student.ssid != ''
        ).subquery()
        query = query.filter(
            db.or_(
                Absence.ssid.ilike(f'%{search}%'),
                Absence.abs_desc.ilike(f'%{search}%'),
                Absence.ssid.in_(name_ssids),
            )
        )

    # Demographic filters — resolve matching SSIDs via Student table
    if subgroups or english_status or gender_filters:
        stu_q = Student.query.with_entities(Student.ssid).filter(Student.ssid.isnot(None), Student.ssid != '')
        if english_status:
            stu_q = stu_q.filter(Student.english_status.in_(english_status))
        if gender_filters:
            stu_q = stu_q.filter(Student.gender.in_(gender_filters))
        if subgroups:
            _sg = {
                'homeless': db.and_(Student.dwelling.isnot(None), Student.dwelling != ''),
                'frm':      Student.frm_code.in_(['F', 'R']),
                'swd':      db.and_(Student.disability.isnot(None), Student.disability != ''),
                'foster':   Student.foster == True,
                'migrant':  Student.migrant == True,
                'sed504':   Student.sed504 == True,
            }
            conds = [_sg[sg] for sg in subgroups if sg in _sg]
            if conds:
                stu_q = stu_q.filter(db.and_(*conds))
        matching_ssids = [r[0] for r in stu_q.all()]
        query = query.filter(Absence.ssid.in_(matching_ssids))

    total      = query.count()
    absences_q = query.order_by(Absence.school_yr.desc(), Absence.site_id.asc()).offset(offset).limit(per_page).all()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    grades     = _GRADE_LIST

    # Build ssid → full name and ssid → student.id lookups for the current page
    page_ssids = {a.ssid for a in absences_q if a.ssid}
    if page_ssids:
        stu_rows = (Student.query
                           .with_entities(Student.ssid, Student.id, Student.first_name,
                                          Student.last_name, Student.student_id)
                           .filter(Student.ssid.in_(page_ssids)).all())
        ssid_names   = {s.ssid: f"{s.last_name}, {s.first_name}" for s in stu_rows}
        ssid_ids     = {s.ssid: s.id for s in stu_rows}
        ssid_stu_ids = {s.ssid: s.student_id for s in stu_rows}
    else:
        ssid_names   = {}
        ssid_ids     = {}
        ssid_stu_ids = {}

    # Build site_id → site_name lookup
    site_id_names = {s.id: s.site_name for s in Site.query.with_entities(Site.id, Site.site_name).all()}

    # Student totals — same filters, grouped by ssid, sorted by total desc
    totals_q = (
        query.with_entities(Absence.ssid, func.count(Absence.id).label('total'))
        .group_by(Absence.ssid)
        .order_by(func.count(Absence.id).desc())
        .all()
    )
    all_ssids = {r.ssid for r in totals_q if r.ssid}
    if all_ssids:
        stu_info_rows = (Student.query
                         .with_entities(Student.ssid, Student.id, Student.first_name,
                                        Student.last_name, Student.grade, Student.site_id,
                                        Student.enter_date, Student.exit_date, Student.student_id)
                         .filter(Student.ssid.in_(all_ssids)).all())
        stu_info = {s.ssid: s for s in stu_info_rows}
    else:
        stu_info = {}

    # School year window for enrolled days calculation
    from datetime import date as _date
    _today = datetime.now().date()
    if yr_filter and '-' in yr_filter:
        _yr_start = int(yr_filter.split('-')[0])
    else:
        _yr_start = _today.year if _today.month >= 8 else _today.year - 1
    _school_start = _date(_yr_start, 8, 25)
    _school_end   = min(_today, _date(_yr_start + 1, 6, 10))

    def _enrolled_days(s):
        eff_start = max(s.enter_date, _school_start) if s.enter_date else _school_start
        eff_end   = min(s.exit_date,  _school_end)   if s.exit_date  else _school_end
        return _count_weekdays(eff_start, eff_end)

    def _standing(total, enrolled):
        if not isinstance(enrolled, int) or enrolled == 0:
            return 'good'
        pct = total / enrolled * 100
        if pct >= 10:
            return 'chronic'
        if pct > 7:
            return 'danger'
        return 'good'

    all_student_totals = []
    for r in totals_q:
        enrolled = _enrolled_days(stu_info[r.ssid]) if r.ssid in stu_info else '—'
        if isinstance(enrolled, int) and enrolled > 0:
            abs_pct = round(r.total / enrolled * 100, 1)
        else:
            abs_pct = None
        standing = _standing(r.total, enrolled)
        all_student_totals.append({
            'ssid':         r.ssid,
            'total':        r.total,
            'name':         f"{stu_info[r.ssid].last_name}, {stu_info[r.ssid].first_name}" if r.ssid in stu_info else '—',
            'student_id':   stu_info[r.ssid].id if r.ssid in stu_info else None,
            'stu_num':      stu_info[r.ssid].student_id if r.ssid in stu_info else '—',
            'grade':        stu_info[r.ssid].grade if r.ssid in stu_info else '—',
            'site':         site_id_names.get(stu_info[r.ssid].site_id, '—') if r.ssid in stu_info else '—',
            'enrolled_days': enrolled,
            'abs_pct':      abs_pct,
            'standing':     standing,
        })

    if stu_status == 'severe':
        all_student_totals = [
            r for r in all_student_totals
            if isinstance(r['enrolled_days'], int) and r['enrolled_days'] > 0
            and (r['total'] / r['enrolled_days'] * 100) >= 25
        ]
    elif stu_status:
        all_student_totals = [r for r in all_student_totals if r['standing'] == stu_status]

    stu_page, stu_per_page, _ = get_page_args(page_parameter='stu_page', per_page_parameter='stu_per_page')
    stu_total      = len(all_student_totals)
    stu_offset     = (stu_page - 1) * stu_per_page
    student_totals = all_student_totals[stu_offset: stu_offset + stu_per_page]
    stu_pagination = Pagination(page=stu_page, per_page=stu_per_page, total=stu_total, css_framework='bootstrap5')

    return render_template('absences.html',
        absences=absences_q, pagination=pagination, per_page=per_page,
        total=total, grades=grades,
        grade_filter=grade_filter, abs_types=abs_types,
        subgroups=subgroups, english_status=english_status, gender_filters=gender_filters,
        ssid_names=ssid_names, ssid_ids=ssid_ids, ssid_stu_ids=ssid_stu_ids,
        site_id_names=site_id_names,
        student_totals=student_totals, stu_total=stu_total,
        stu_per_page=stu_per_page, stu_pagination=stu_pagination,
        stu_status=stu_status,
        current_page_name='Absences')


# =============================================================================
# DISCIPLINE DASHBOARD
# =============================================================================

@routes_blueprint.route('/discipline')
@login_required
def discipline_dashboard():
    from collections import defaultdict

    yr_filter   = session.get('active_schoolyr', '')
    site_filter = session.get('active_site_filter', '')

    base = Incident.query
    if yr_filter:
        base = base.filter(Incident.schoolyr == yr_filter)
    if site_filter:
        site_obj = Site.query.get(site_filter)
        if site_obj:
            base = base.filter(Incident.site == site_obj.site_acronyms)

    all_inc = base.all()

    total_incidents = len(all_inc)
    major_count     = sum(1 for i in all_inc if i.major)
    minor_count     = sum(1 for i in all_inc if i.minor)
    total_susp_days = sum(i.suspended_days or 0 for i in all_inc)

    # Student lookup: ssid → (gender, grade)
    students_all = Student.query.with_entities(Student.ssid, Student.gender, Student.grade).filter(Student.ssid.isnot(None)).all()
    ssid_gender  = {s.ssid: s.gender for s in students_all}
    ssid_grade   = {s.ssid: s.grade  for s in students_all}

    # Incident rate per 100 enrolled students
    enrolled_q = Student.query.filter(
        db.or_(Student.enter_date.is_(None), Student.enter_date <= datetime.now().date()),
        db.or_(Student.exit_date.is_(None),  Student.exit_date  >= datetime.now().date()),
    )
    if site_filter:
        enrolled_q = enrolled_q.filter(Student.site_id == site_filter)
    total_enrolled  = enrolled_q.count() or 1
    incident_rate   = round(total_incidents / total_enrolled * 100, 1)

    # By month
    month_dict = defaultdict(int)
    _mon_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    for i in all_inc:
        if i.incident_date:
            month_dict[i.incident_date.month] += 1
    month_labels = [_mon_names[m-1] for m in sorted(month_dict)]
    month_counts = [month_dict[m] for m in sorted(month_dict)]

    # By site (bar chart)
    site_dict  = defaultdict(int)
    for i in all_inc:
        site_dict[i.site or 'Unknown'] += 1
    site_items  = sorted(site_dict.items(), key=lambda x: x[1], reverse=True)
    site_labels = [s for s, _ in site_items]
    site_counts = [c for _, c in site_items]

    # Top infractions
    infraction_dict = defaultdict(int)
    for i in all_inc:
        label = i.major or i.minor
        if label:
            infraction_dict[label] += 1
    top_infractions   = sorted(infraction_dict.items(), key=lambda x: x[1], reverse=True)[:8]
    infraction_labels = [k for k, _ in top_infractions]
    infraction_counts = [v for _, v in top_infractions]

    # By day of week
    dow_order = ['Monday','Tuesday','Wednesday','Thursday','Friday']
    dow_dict  = defaultdict(int)
    for i in all_inc:
        if i.day_of_week and i.day_of_week in dow_order:
            dow_dict[i.day_of_week] += 1
    dow_labels = dow_order
    dow_counts = [dow_dict[d] for d in dow_order]

    # By gender
    _gen_map   = {'M': 'Male', 'F': 'Female', 'X': 'Non-Binary', 'U': 'Unknown'}
    gender_dict = defaultdict(int)
    for i in all_inc:
        g = ssid_gender.get(i.sisid, 'Unknown') if i.sisid else 'Unknown'
        gender_dict[_gen_map.get(g, 'Unknown')] += 1
    gender_labels = list(gender_dict.keys())
    gender_counts = list(gender_dict.values())

    # By grade
    _grade_order = ['TK','KN','1','2','3','4','5','6','7','8','9','10','11','12']
    grade_dict   = defaultdict(int)
    for i in all_inc:
        gr = ssid_grade.get(i.sisid, 'N/A') if i.sisid else 'N/A'
        grade_dict[gr] += 1
    grade_sorted  = sorted(grade_dict.items(), key=lambda x: _grade_order.index(x[0]) if x[0] in _grade_order else 99)
    grade_labels  = [g for g, _ in grade_sorted]
    grade_counts  = [c for _, c in grade_sorted]

    # Site table
    site_table = defaultdict(lambda: {'major': 0, 'minor': 0, 'susp': 0.0})
    for i in all_inc:
        s = i.site or 'Unknown'
        if i.major:   site_table[s]['major'] += 1
        elif i.minor: site_table[s]['minor'] += 1
        site_table[s]['susp'] += i.suspended_days or 0
    site_table_data = sorted(site_table.items(), key=lambda x: x[1]['major'] + x[1]['minor'], reverse=True)

    # Suspension Rate indicator — full-year retrospective figure, comparable year over year
    # the same way the Chronic Absenteeism Rate indicator is on the Absenteeism dashboard.
    indicator_yr = yr_filter or (Organization.query.get(1).current_school_year if Organization.query.get(1) else None)
    sr_pct, sr_count, sr_total, sr_site_rows = _suspension_rate(indicator_yr, site_filter)
    sr_prior_pct = None
    if indicator_yr:
        prior_yr = _prior_schoolyr(indicator_yr)
        if prior_yr:
            sr_prior_pct = _suspension_rate(prior_yr, site_filter)[0]
    sr_status = _rate_status(sr_pct) if sr_pct is not None else None
    sr_change = _rate_change(sr_pct, sr_prior_pct)

    return render_template('dashboard/discipline.html',
        current_page_name='Discipline',
        total_incidents=total_incidents, major_count=major_count,
        minor_count=minor_count, total_susp_days=total_susp_days,
        incident_rate=incident_rate,
        month_labels=month_labels, month_counts=month_counts,
        site_labels=site_labels, site_counts=site_counts,
        infraction_labels=infraction_labels, infraction_counts=infraction_counts,
        dow_labels=dow_labels, dow_counts=dow_counts,
        gender_labels=gender_labels, gender_counts=gender_counts,
        grade_labels=grade_labels, grade_counts=grade_counts,
        site_table_data=site_table_data,
        indicator_yr=indicator_yr, sr_pct=sr_pct, sr_count=sr_count, sr_total=sr_total,
        sr_site_rows=sr_site_rows, sr_status=sr_status, sr_change=sr_change,
    )


# =============================================================================
# INCIDENTS
# =============================================================================

@routes_blueprint.route('/incidents', methods=['GET'])
@login_required
def incidents():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search      = request.args.get('search', '').strip()
    site_filter = request.args.get('site_filter', '').strip()
    if not current_user.has_all_site_access:
        # Incident.site stores the site acronym string, not the numeric site_id
        # every other table uses — _clamp_site_filter doesn't apply here.
        allowed_acronyms = {
            s.site_acronyms for s in Site.query.filter(Site.id.in_(current_user.allowed_site_ids)).all()
        }
        if site_filter not in allowed_acronyms:
            site_filter = current_user.site.site_acronyms
    type_filter = request.args.get('type_filter', '').strip()
    yr_filter   = request.args.get('schoolyr', '').strip() or session.get('active_schoolyr', '')

    query = Incident.query
    if search:
        query = query.filter(db.or_(
            Incident.sisid.ilike(f'%{search}%'),
            Incident.incident_id.ilike(f'%{search}%'),
            Incident.major.ilike(f'%{search}%'),
            Incident.minor.ilike(f'%{search}%'),
        ))
    if site_filter:
        query = query.filter(Incident.site == site_filter)
    if type_filter == 'major':
        query = query.filter(Incident.major.isnot(None), Incident.major != '')
    elif type_filter == 'minor':
        query = query.filter(Incident.minor.isnot(None), Incident.minor != '')
    if yr_filter:
        query = query.filter(Incident.schoolyr == yr_filter)

    total       = query.count()
    incidents_q = query.order_by(Incident.incident_date.desc()).offset(offset).limit(per_page).all()
    pagination  = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    sites       = sorted({i.site for i in Incident.query.with_entities(Incident.site).distinct() if i.site})
    ssid_to_id  = {s.ssid: s.id for s in Student.query.with_entities(Student.ssid, Student.id).filter(Student.ssid.isnot(None)).all()}

    return render_template('incidents.html',
        incidents=incidents_q, pagination=pagination, per_page=per_page,
        total=total, sites=sites, site_filter=site_filter,
        type_filter=type_filter, yr_filter=yr_filter,
        ssid_to_id=ssid_to_id,
        current_page_name='Incidents')


# =============================================================================
# TEACHERS
# =============================================================================

@routes_blueprint.route('/teachers', methods=['GET'])
@login_required
def teachers():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search      = request.args.get('search', '').strip()
    site_filter = _clamp_site_filter(request.args.get('site_filter', '').strip())
    dept_filter = request.args.get('dept_filter', '').strip()

    query = Teacher.query
    if search:
        query = query.filter(
            db.or_(Teacher.first_name.ilike(f'%{search}%'),
                   Teacher.last_name.ilike(f'%{search}%'),
                   Teacher.employee_id.ilike(f'%{search}%'))
        )
    if site_filter:
        query = query.filter(Teacher.site_id == site_filter)
    if dept_filter:
        query = query.filter(Teacher.department == dept_filter)

    total      = query.count()
    teachers_q = query.order_by(Teacher.last_name.asc(), Teacher.first_name.asc()).offset(offset).limit(per_page).all()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    sites      = Site.query.order_by(Site.site_name.asc()).all()
    departments = sorted({t.department for t in Teacher.query.all() if t.department})

    return render_template('teachers.html',
        teachers=teachers_q, pagination=pagination, per_page=per_page,
        sites=sites, departments=departments, dept_filter=dept_filter,
        site_filter=site_filter,
        current_page_name='Teachers')


@routes_blueprint.route('/add_teacher', methods=['GET', 'POST'])
@login_required
def add_teacher():
    return redirect(url_for('routes.teachers'))


@routes_blueprint.route('/teacher/<int:teacher_id>', methods=['GET'])
@login_required
def teacher_details(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    require_site_access(teacher.site_id)
    # Flat, deduplicated list of students across all teacher's courses
    seen = set()
    teacher_students = []
    for course in teacher.courses:
        for student in course.students:
            if student.id not in seen:
                seen.add(student.id)
                teacher_students.append((student, course))
    teacher_students.sort(key=lambda x: (x[0].last_name, x[0].first_name))

    course_ids = {course.id for _, course in teacher_students}
    student_dates = {
        (r.student_id, r.course_id): (r.start_date, r.leave_date)
        for r in db.session.execute(
            student_course.select().where(student_course.c.course_id.in_(course_ids))
        ).all()
    } if course_ids else {}
    active_student_count = sum(
        1 for student, course in teacher_students
        if student_dates.get((student.id, course.id), (None, None))[1] is None
    )

    return render_template('teacher_details.html', teacher=teacher,
                           teacher_students=teacher_students,
                           student_dates=student_dates,
                           active_student_count=active_student_count,
                           current_page_name=f'{teacher.first_name} {teacher.last_name}')


@routes_blueprint.route('/edit_teacher/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def edit_teacher(teacher_id):
    is_admin()
    teacher = Teacher.query.get_or_404(teacher_id)
    form = TeacherForm(obj=teacher)
    form.site_id.choices = [(s.id, s.site_name) for s in Site.query.order_by(Site.site_name).all()]

    if form.validate_on_submit():
        conflict = Teacher.query.filter(
            Teacher.employee_id == form.employee_id.data.strip(),
            Teacher.id != teacher.id
        ).first()
        if conflict:
            flash('A teacher with this Employee ID already exists.', 'danger')
            return render_template('add_teacher.html', form=form, current_page_name='Edit Teacher')
        teacher.first_name  = form.first_name.data
        teacher.middle_name = form.middle_name.data or None
        teacher.last_name   = form.last_name.data
        teacher.employee_id = form.employee_id.data.strip()
        teacher.email       = form.email.data or None
        teacher.department  = form.department.data or None
        teacher.site_id     = form.site_id.data
        teacher.status      = form.status.data
        db.session.commit()
        flash('Teacher updated successfully!', 'success')
        return redirect(url_for('routes.teacher_details', teacher_id=teacher.id))

    return render_template('add_teacher.html', form=form, current_page_name='Edit Teacher')


@routes_blueprint.route('/delete_teacher/<int:teacher_id>', methods=['POST'])
@login_required
def delete_teacher(teacher_id):
    is_admin()
    teacher = Teacher.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    flash('Teacher deleted successfully!', 'warning')
    return redirect(url_for('routes.teachers'))


# =============================================================================
# COURSES
# =============================================================================

@routes_blueprint.route('/courses', methods=['GET'])
@login_required
def courses():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search       = request.args.get('search', '').strip()
    site_filter  = _clamp_site_filter(request.args.get('site_filter', '').strip())
    grade_filter = request.args.get('grade_filter', '').strip()
    dept_filter  = request.args.get('dept_filter', '').strip()

    query = Course.query.outerjoin(Teacher, Course.teacher_id == Teacher.id)
    if search:
        query = query.filter(
            db.or_(Course.course_name.ilike(f'%{search}%'),
                   Course.section_id.ilike(f'%{search}%'))
        )
    if site_filter:
        query = query.filter(Course.site_id == site_filter)
    if grade_filter:
        query = query.filter(Course.grade_level == grade_filter)
    if dept_filter:
        query = query.filter(Course.department == dept_filter)

    total       = query.count()
    courses_q   = query.order_by(Course.course_name.asc()).offset(offset).limit(per_page).all()
    pagination  = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')
    sites       = Site.query.order_by(Site.site_name.asc()).all()
    departments = sorted({c.department for c in Course.query.all() if c.department})

    return render_template('courses.html',
        courses=courses_q, pagination=pagination, per_page=per_page,
        sites=sites, grades=_GRADE_LIST, departments=departments,
        dept_filter=dept_filter, site_filter=site_filter, current_page_name='Courses')


@routes_blueprint.route('/add_course', methods=['GET', 'POST'])
@login_required
def add_course():
    return redirect(url_for('routes.courses'))


@routes_blueprint.route('/course/<int:course_id>', methods=['GET'])
@login_required
def course_details(course_id):
    course = Course.query.get_or_404(course_id)
    require_site_access(course.site_id)
    student_dates = {
        r.student_id: (r.start_date, r.leave_date)
        for r in db.session.execute(
            student_course.select().where(student_course.c.course_id == course.id)
        ).all()
    }
    return render_template('course_details.html', course=course,
                           student_dates=student_dates,
                           current_page_name=course.course_name)


@routes_blueprint.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    is_admin()
    course = Course.query.get_or_404(course_id)
    form = CourseForm(obj=course)
    form.teacher_id.choices = [
        (t.id, f'{t.last_name}, {t.first_name}')
        for t in Teacher.query.order_by(Teacher.last_name).all()
    ]
    form.site_id.choices = [(s.id, s.site_name) for s in Site.query.order_by(Site.site_name).all()]

    if form.validate_on_submit():
        conflict = Course.query.filter(
            Course.course_code == form.course_code.data.strip().upper(),
            Course.id != course.id
        ).first()
        if conflict:
            flash('A course with this code already exists.', 'danger')
            return render_template('add_course.html', form=form, current_page_name='Edit Course')
        course.course_name   = form.course_name.data
        course.course_code   = form.course_code.data.strip().upper()
        course.grade_level   = form.grade_level.data or None
        course.period        = form.period.data or None
        course.description   = form.description.data or None
        course.max_students  = form.max_students.data or None
        course.status        = form.status.data
        course.teacher_id    = form.teacher_id.data
        course.site_id       = form.site_id.data
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('routes.course_details', course_id=course.id))

    return render_template('add_course.html', form=form, current_page_name='Edit Course')


@routes_blueprint.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    is_admin()
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'warning')
    return redirect(url_for('routes.courses'))


# =============================================================================
# PARENTS
# =============================================================================

@routes_blueprint.route('/parents', methods=['GET'])
@login_required
def parents():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    search = request.args.get('search', '').strip()

    query = Parent.query
    if search:
        query = query.filter(
            db.or_(Parent.first_name.ilike(f'%{search}%'),
                   Parent.last_name.ilike(f'%{search}%'),
                   Parent.email.ilike(f'%{search}%'))
        )

    total      = query.count()
    parents_q  = query.order_by(Parent.last_name.asc(), Parent.first_name.asc()).offset(offset).limit(per_page).all()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap5')

    return render_template('parents.html',
        parents=parents_q, pagination=pagination, per_page=per_page,
        current_page_name='Parents')


@routes_blueprint.route('/add_parent', methods=['GET', 'POST'])
@login_required
def add_parent():
    return redirect(url_for('routes.parents'))


@routes_blueprint.route('/parent/<int:parent_id>', methods=['GET'])
@login_required
def parent_details(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    # Parent has no site_id of its own — it's in scope for a site if at least one of
    # the parent's linked students is enrolled there (siblings can span sites).
    if not current_user.has_all_site_access and not any(
        s.site_id in current_user.allowed_site_ids for s in parent.students
    ):
        abort(403)
    return render_template('parent_details.html', parent=parent,
                           current_page_name=f'{parent.first_name} {parent.last_name}')


@routes_blueprint.route('/edit_parent/<int:parent_id>', methods=['GET', 'POST'])
@login_required
def edit_parent(parent_id):
    is_admin()
    parent = Parent.query.get_or_404(parent_id)
    form = ParentForm(obj=parent)
    form.student_ids.choices = [
        (s.id, f'{s.last_name}, {s.first_name} ({s.student_id})')
        for s in Student.query.order_by(Student.last_name).all()
    ]

    if request.method == 'GET':
        form.student_ids.data = [s.id for s in parent.students]

    if form.validate_on_submit():
        parent.first_name   = form.first_name.data
        parent.middle_name  = form.middle_name.data or None
        parent.last_name    = form.last_name.data
        parent.relationship = form.relationship.data
        parent.email        = form.email.data or None
        parent.phone        = form.phone.data or None
        parent.status       = form.status.data
        parent.students     = Student.query.filter(Student.id.in_(form.student_ids.data or [])).all()
        db.session.commit()
        flash('Parent updated successfully!', 'success')
        return redirect(url_for('routes.parent_details', parent_id=parent.id))

    return render_template('add_parent.html', form=form, current_page_name='Edit Parent')


@routes_blueprint.route('/delete_parent/<int:parent_id>', methods=['POST'])
@login_required
def delete_parent(parent_id):
    is_admin()
    parent = Parent.query.get_or_404(parent_id)
    db.session.delete(parent)
    db.session.commit()
    flash('Parent deleted successfully!', 'warning')
    return redirect(url_for('routes.parents'))


# =============================================================================
# CALPADS COMPLIANCE
# =============================================================================

@routes_blueprint.route('/calpads')
@login_required
def calpads_compliance():
    schoolyr    = session.get('active_schoolyr', '') or '2025-2026'
    site_filter = session.get('active_site_filter', '')

    VALID_ETHNICITY = {'100', '200', '300', '400', '500', '600', '700', '800', '900'}
    VALID_GENDER    = {'M', 'F', 'N', 'X'}

    base = Student.query.filter(Student.schoolyr == schoolyr)
    if site_filter:
        base = base.filter(Student.site_id == site_filter)

    total_students = base.count()

    def run_check(q):
        rows = q.order_by(Student.last_name, Student.first_name).all()
        return len(rows), rows

    # Identity & Demographics
    ssid_count,    ssid_stu    = run_check(base.filter(db.or_(Student.ssid.is_(None),       Student.ssid == '')))
    ssid_fmt_count, ssid_fmt_stu = run_check(base.filter(
        Student.ssid.isnot(None), Student.ssid != '', ~Student.ssid.op('REGEXP')('^[0-9]{10}$')
    ))
    dob_count,     dob_stu     = run_check(base.filter(Student.date_of_birth.is_(None)))
    gnd_m_count,   gnd_m_stu   = run_check(base.filter(db.or_(Student.gender.is_(None),     Student.gender == '')))
    gnd_i_count,   gnd_i_stu   = run_check(base.filter(Student.gender.isnot(None), Student.gender != '', ~Student.gender.in_(list(VALID_GENDER))))
    eth_m_count,   eth_m_stu   = run_check(base.filter(db.or_(Student.ethnicity.is_(None),  Student.ethnicity == '')))
    eth_i_count,   eth_i_stu   = run_check(base.filter(Student.ethnicity.isnot(None), Student.ethnicity != '', ~Student.ethnicity.in_(list(VALID_ETHNICITY))))

    # Enrollment
    enter_count,   enter_stu   = run_check(base.filter(Student.enter_date.is_(None)))
    exit_x_count,  exit_x_stu  = run_check(base.filter(Student.exit_date.isnot(None), Student.enter_date.isnot(None), Student.exit_date < Student.enter_date))

    # Program Flags
    swd_count,     swd_stu     = run_check(base.filter(Student.sed504 == True, db.or_(Student.disability.is_(None), Student.disability == '')))
    el_count,      el_stu      = run_check(base.filter(db.or_(Student.english_status.is_(None), Student.english_status == '')))

    # Attendance — a student can never legitimately be absent more days than there were
    # school days in the year; more recorded absence rows than that is a data-integrity
    # red flag (duplicate import, wrong school year on the row, bad date range), not a
    # real attendance pattern, and CALPADS SIRS submissions can reject on it.
    from datetime import date as _date
    total_school_days = None
    if schoolyr and '-' in schoolyr:
        _start_year = int(schoolyr.split('-')[0])
        total_school_days = max(_count_weekdays(_date(_start_year, 8, 25), _date(_start_year + 1, 6, 10)), 1)

    over_days_count, over_days_stu = 0, []
    if total_school_days:
        abs_per_ssid = (
            db.session.query(Absence.ssid.label('ssid'), func.count(Absence.id).label('abs_cnt'))
            .filter(Absence.school_yr == schoolyr)
            .group_by(Absence.ssid).subquery()
        )
        over_days_count, over_days_stu = run_check(
            base.join(abs_per_ssid, abs_per_ssid.c.ssid == Student.ssid)
                .filter(abs_per_ssid.c.abs_cnt > total_school_days)
        )

    checks = {
        'identity': [
            {'id': 'missing_ssid',      'label': 'Missing SSID',             'submission': 'All Submissions', 'severity': 'critical',
             'desc': 'State Student ID is required for all CALPADS submissions.',
             'count': ssid_count,   'students': ssid_stu,   'students_url': url_for('routes.students', subgroup='no_ssid')},
            {'id': 'invalid_ssid_format', 'label': 'Invalid SSID Format',   'submission': 'All Submissions', 'severity': 'warning',
             'desc': 'SSID must be exactly 10 digits per CALPADS specification.',
             'count': ssid_fmt_count, 'students': ssid_fmt_stu, 'students_url': None},
            {'id': 'missing_dob',       'label': 'Missing Date of Birth',    'submission': 'SDEM / CENR',     'severity': 'critical',
             'desc': 'Date of birth is required for SDEM and all enrollment records.',
             'count': dob_count,    'students': dob_stu,    'students_url': None},
            {'id': 'missing_gender',    'label': 'Missing Gender',           'submission': 'SDEM',            'severity': 'critical',
             'desc': 'Gender code is required for student demographic reporting.',
             'count': gnd_m_count,  'students': gnd_m_stu,  'students_url': None},
            {'id': 'invalid_gender',    'label': 'Invalid Gender Code',      'submission': 'SDEM',            'severity': 'warning',
             'desc': 'Gender must be one of: M, F, N, X per CALPADS specification.',
             'count': gnd_i_count,  'students': gnd_i_stu,  'students_url': None},
            {'id': 'missing_ethnicity', 'label': 'Missing Ethnicity',        'submission': 'SDEM',            'severity': 'critical',
             'desc': 'Ethnicity code is required for student demographic reporting.',
             'count': eth_m_count,  'students': eth_m_stu,  'students_url': None},
            {'id': 'invalid_ethnicity', 'label': 'Invalid Ethnicity Code',   'submission': 'SDEM',            'severity': 'warning',
             'desc': 'Ethnicity must be a valid 3-digit CALPADS code (100–900).',
             'count': eth_i_count,  'students': eth_i_stu,  'students_url': None},
        ],
        'enrollment': [
            {'id': 'missing_enter_date',  'label': 'Missing Enrollment Date',       'submission': 'CENR / SENR', 'severity': 'critical',
             'desc': 'Enter date is required for all enrollment reporting.',
             'count': enter_count,  'students': enter_stu,  'students_url': None},
            {'id': 'exit_before_enter',   'label': 'Exit Date Before Enrollment',   'submission': 'CENR / SENR', 'severity': 'critical',
             'desc': 'Exit date cannot be earlier than the enrollment date.',
             'count': exit_x_count, 'students': exit_x_stu, 'students_url': None},
        ],
        'programs': [
            {'id': 'swd_no_disability',   'label': '504/SWD Flag Without Disability Code', 'submission': 'SPRG', 'severity': 'warning',
             'desc': 'Students flagged as SWD/504 must have a disability code for SPRG reporting.',
             'count': swd_count,    'students': swd_stu,    'students_url': url_for('routes.students', subgroup='sed504')},
            {'id': 'missing_el_status',   'label': 'Missing English Language Status',       'submission': 'SELA', 'severity': 'warning',
             'desc': 'All students must have an English Language Acquisition status (EL, IFEP, RFEP, EO).',
             'count': el_count,     'students': el_stu,     'students_url': None},
        ],
        'attendance': [
            {'id': 'absences_exceed_school_days', 'label': 'Absences Exceed Total School Days', 'submission': 'SIRS', 'severity': 'critical',
             'desc': f'A student cannot be absent more days than the {total_school_days} school days in {schoolyr}.' if total_school_days
                     else 'A student cannot be absent more days than there are school days in the year.',
             'count': over_days_count, 'students': over_days_stu, 'students_url': None},
        ],
    }

    total_critical = sum(c['count'] for g in checks.values() for c in g if c['severity'] == 'critical')
    total_warning  = sum(c['count'] for g in checks.values() for c in g if c['severity'] == 'warning')

    # Count distinct students with at least one flag, not summed check counts,
    # since one student can trip multiple checks at once.
    flagged_ids = {s.id for g in checks.values() for c in g for s in c['students']}
    if total_students:
        pct_clean = round((total_students - len(flagged_ids)) / total_students * 100, 1)
        if flagged_ids and pct_clean >= 100:
            pct_clean = 99.9
    else:
        pct_clean = 100.0

    return render_template('dashboard/calpads.html',
        checks=checks,
        total_students=total_students,
        total_critical=total_critical,
        total_warning=total_warning,
        pct_clean=pct_clean,
        current_page_name='CALPADS Compliance',
    )


