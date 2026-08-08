from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, FieldList, FormField, BooleanField, RadioField, DateTimeField, IntegerField, DateField, SelectMultipleField, DecimalField
from wtforms.validators import DataRequired, Email, Length, Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed
from datetime import datetime

class LoginForm(FlaskForm):
    email = StringField('Email:', validators=[DataRequired(), Email()])
    password = PasswordField('Password:', validators=[DataRequired()])
    submit = SubmitField('Login')


class UserForm(FlaskForm):
    first_name = StringField('First Name:', validators=[DataRequired()])
    middle_name = StringField('Middle Name:', validators=[Optional()])
    last_name = StringField('Last Name:', validators=[DataRequired()])
    email = StringField('Email:', validators=[DataRequired(), Email()])
    role_id = SelectField('Role:', coerce=int, choices=[], validators=[DataRequired()])
    site_id = SelectField('Site:', coerce=int, choices=[], validators=[DataRequired()])
    rm_num = StringField('Room:', validators=[Optional()])
    status = SelectField('Status:',
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        validators=[DataRequired()]    )
    password = PasswordField('New Password:', validators=[Optional(), Length(min=12)])
    submit = SubmitField('Save User')


class RoleForm(FlaskForm):
    role_name = StringField('Role Name:', validators=[DataRequired()])
    submit = SubmitField('Save Role')


class GraduationRequirementForm(FlaskForm):
    subject_name = StringField('Subject Area:', validators=[DataRequired(), Length(max=100)])
    credits_required = DecimalField('Credits Required:', places=2, validators=[DataRequired()])
    departments = StringField('Matching Departments:', validators=[Optional()])
    name_keywords = StringField('Include if Course Name Contains:', validators=[Optional()])
    name_exclude_keywords = StringField('Exclude if Course Name Contains:', validators=[Optional()])
    is_catch_all = BooleanField('Use as Catch-All for Unmapped Courses', validators=[Optional()])
    sort_order = IntegerField('Sort Order:', validators=[Optional()], default=0)
    start_grade = SelectField('Typically Starts Grade:', choices=[('9', '9th'), ('10', '10th'), ('11', '11th'), ('12', '12th')], default='9', validators=[DataRequired()])
    end_grade = SelectField('Should Be Complete By Grade:', choices=[('9', '9th'), ('10', '10th'), ('11', '11th'), ('12', '12th')], default='12', validators=[DataRequired()])
    submit = SubmitField('Save Subject Area')


class InterventionForm(FlaskForm):
    tier = SelectField('Tier:',
        choices=[('Tier 1', 'Tier 1 — Universal'), ('Tier 2', 'Tier 2 — Targeted'), ('Tier 3', 'Tier 3 — Intensive')],
        default='Tier 2', validators=[DataRequired()])
    category = SelectField('Category:',
        choices=[('Attendance', 'Attendance'), ('Behavior', 'Behavior'), ('Academic', 'Academic')],
        validators=[DataRequired()])
    description = TextAreaField('Intervention:', validators=[DataRequired(), Length(max=2000)])
    start_date = DateField('Start Date:', validators=[DataRequired()])
    end_date = DateField('End Date:', validators=[Optional()])
    status = SelectField('Status:',
        choices=[('Active', 'Active'), ('Completed', 'Completed'), ('Discontinued', 'Discontinued')],
        default='Active', validators=[DataRequired()])
    outcome = SelectField('Outcome:',
        choices=[('', '--- Not yet determined ---'), ('Improved', 'Improved'), ('No Change', 'No Change'), ('Worsened', 'Worsened')],
        validators=[Optional()])
    notes = TextAreaField('Notes:', validators=[Optional(), Length(max=2000)])
    submit = SubmitField('Save Intervention')


class SiteForm(FlaskForm):
    site_name = StringField('Site Name:', validators=[DataRequired()])
    site_acronyms = StringField('Site Acronym:', validators=[DataRequired()])
    site_code = StringField('Site Code:', validators=[DataRequired()])
    site_cds = StringField('CDS Code:', validators=[DataRequired()])
    site_address = StringField('Site Address:', validators=[DataRequired()])
    site_type = StringField('Site Type:', validators=[DataRequired()])
    site_city = StringField('City:', validators=[Optional()])
    site_state = StringField('State:', validators=[Optional()])
    site_zip = StringField('Zip:', validators=[Optional()])
    principal_first_name = StringField('Principal First Name:', validators=[Optional()])
    principal_last_name = StringField('Principal Last Name:', validators=[Optional()])
    principal_email = StringField('Principal Email:', validators=[Optional(), Email()])
    principal_phone = StringField('Principal Phone:', validators=[Optional()])
    submit = SubmitField('Save Site')


class NotificationForm(FlaskForm):
    msg_name = StringField('Message Name:', validators=[DataRequired()])
    msg_content = TextAreaField('Message:', validators=[DataRequired()])
    msg_status = RadioField('Status', choices=[('active', 'Active'), ('inactive', 'Inactive')], default='inactive', validators=[DataRequired()])
    submit = SubmitField('Save Notification Message')


class OrganizationForm(FlaskForm):
    organization_name   = StringField('Organization Name', validators=[DataRequired()])
    site_version        = StringField('Site Version', validators=[DataRequired()])
    current_school_year = StringField('Current School Year', validators=[Optional()])
    first_school_day    = DateField('First Day of School', validators=[Optional()])
    last_school_day     = DateField('Last Day of School',  validators=[Optional()])
    submit = SubmitField('Save Settings')


_GRADE_CHOICES = [
    ('', '--- Select Grade ---'),
    ('TK', 'Transitional Kindergarten'),
    ('KN', 'Kindergarten'),
    ('1', 'Grade 1'), ('2', 'Grade 2'), ('3', 'Grade 3'),
    ('4', 'Grade 4'), ('5', 'Grade 5'), ('6', 'Grade 6'),
    ('7', 'Grade 7'), ('8', 'Grade 8'), ('9', 'Grade 9'),
    ('10', 'Grade 10'), ('11', 'Grade 11'), ('12', 'Grade 12'),
]

_STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive')]

_GENDER_CHOICES = [
    ('', '--- Select ---'),
    ('M', 'Male'), ('F', 'Female'), ('X', 'Non-Binary'), ('U', 'Unknown'),
]

_ETHNICITY_CHOICES = [
    ('', '--- Select ---'),
    ('100', 'Native American or Alaska Native'),
    ('200', 'Asian'),
    ('300', 'Pacific Islander'),
    ('400', 'Filipino'),
    ('500', 'Hispanic or Latino'),
    ('600', 'African American'),
    ('700', 'White'),
    ('900', 'Two or More Races'),
]

_FRM_CHOICES = [
    ('', '--- Select ---'),
    ('F', 'Free'), ('R', 'Reduced'), ('P', 'Paid'),
]

_ENGLISH_STATUS_CHOICES = [
    ('', '--- Select ---'),
    ('EO', 'English Only (EO)'),
    ('IFEP', 'Initially Fluent English Proficient (IFEP)'),
    ('EL', 'English Learner (EL)'),
    ('RFEP', 'Reclassified Fluent English Proficient (RFEP)'),
    ('TBD', 'To Be Determined'),
]

_DISABILITY_CHOICES = [
    ('', '--- None ---'),
    ('AU', 'Autism (AU)'),
    ('DB', 'Deaf-Blindness (DB)'),
    ('DD', 'Developmental Delay (DD)'),
    ('ED', 'Emotional Disturbance (ED)'),
    ('HH', 'Hard of Hearing (HH)'),
    ('ID', 'Intellectual Disability (ID)'),
    ('MD', 'Multiple Disabilities (MD)'),
    ('OHI', 'Other Health Impairment (OHI)'),
    ('OI', 'Orthopedic Impairment (OI)'),
    ('SLD', 'Specific Learning Disability (SLD)'),
    ('SLI', 'Speech or Language Impairment (SLI)'),
    ('TBI', 'Traumatic Brain Injury (TBI)'),
    ('VI', 'Visual Impairment (VI)'),
]

_DWELLING_CHOICES = [
    ('', '--- Select ---'),
    ('H', 'Home'),
    ('S', 'Shelter'),
    ('D', 'Doubled-Up'),
    ('M', 'Motel/Hotel'),
    ('U', 'Unsheltered'),
    ('O', 'Other'),
]


class StudentForm(FlaskForm):
    first_name     = StringField('First Name:', validators=[DataRequired()])
    middle_name    = StringField('Middle Name:', validators=[Optional()])
    last_name      = StringField('Last Name:', validators=[DataRequired()])
    student_id     = StringField('Student ID:', validators=[DataRequired()])
    ssid           = StringField('SSID:', validators=[Optional()])
    cds_code       = StringField('CDS Code:', validators=[Optional()])
    grade          = SelectField('Grade:', choices=_GRADE_CHOICES, validators=[DataRequired()])
    gender         = SelectField('Gender:', choices=_GENDER_CHOICES, validators=[Optional()])
    date_of_birth  = DateField('Date of Birth:', validators=[Optional()], format='%Y-%m-%d')
    gradyr         = StringField('Graduation Year:', validators=[Optional()])
    ethnicity      = SelectField('Ethnicity:', choices=_ETHNICITY_CHOICES, validators=[Optional()])
    frm_code       = SelectField('FRM Code:', choices=_FRM_CHOICES, validators=[Optional()])
    english_status = SelectField('English Status:', choices=_ENGLISH_STATUS_CHOICES, validators=[Optional()])
    enter_date     = DateField('Enter Date:', validators=[Optional()], format='%Y-%m-%d')
    exit_date      = DateField('Exit Date:', validators=[Optional()], format='%Y-%m-%d')
    disability     = SelectField('Disability:', choices=_DISABILITY_CHOICES, validators=[Optional()])
    dwelling       = SelectField('Dwelling:', choices=_DWELLING_CHOICES, validators=[Optional()])
    migrant        = BooleanField('Migrant')
    schoolyr       = StringField('School Year:', validators=[Optional()])
    foster         = BooleanField('Foster Youth')
    sed504         = BooleanField('504 Plan')
    email          = StringField('Email:', validators=[Optional(), Email()])
    site_id        = SelectField('Site:', coerce=int, choices=[], validators=[DataRequired()])
    submit         = SubmitField('Save Student')


class TeacherForm(FlaskForm):
    first_name  = StringField('First Name:', validators=[DataRequired()])
    middle_name = StringField('Middle Name:', validators=[Optional()])
    last_name   = StringField('Last Name:', validators=[DataRequired()])
    employee_id = StringField('Employee ID:', validators=[DataRequired()])
    email       = StringField('Email:', validators=[Optional(), Email()])
    department  = StringField('Department:', validators=[Optional()])
    site_id     = SelectField('Site:', coerce=int, choices=[], validators=[DataRequired()])
    status      = SelectField('Status:', choices=_STATUS_CHOICES, validators=[DataRequired()])
    submit      = SubmitField('Save Teacher')


class CourseForm(FlaskForm):
    course_name = StringField('Course Name:', validators=[DataRequired()])
    course_code = StringField('Course Code:', validators=[DataRequired()])
    grade_level = SelectField('Grade Level:', choices=_GRADE_CHOICES, validators=[Optional()])
    period      = StringField('Period:', validators=[Optional()])
    description  = TextAreaField('Description:', validators=[Optional()])
    max_students = IntegerField('Max Students:', validators=[Optional()])
    status       = SelectField('Status:', choices=_STATUS_CHOICES, validators=[DataRequired()])
    teacher_id  = SelectField('Teacher:', coerce=int, choices=[], validators=[DataRequired()])
    site_id     = SelectField('Site:', coerce=int, choices=[], validators=[DataRequired()])
    submit      = SubmitField('Save Course')


class ParentForm(FlaskForm):
    first_name   = StringField('First Name:', validators=[DataRequired()])
    middle_name  = StringField('Middle Name:', validators=[Optional()])
    last_name    = StringField('Last Name:', validators=[DataRequired()])
    relationship = SelectField('Relationship:', choices=[
        ('Mother', 'Mother'), ('Father', 'Father'),
        ('Guardian', 'Guardian'), ('Grandparent', 'Grandparent'), ('Other', 'Other'),
    ], validators=[DataRequired()])
    email       = StringField('Email:', validators=[Optional(), Email()])
    phone       = StringField('Phone:', validators=[Optional()])
    status      = SelectField('Status:', choices=_STATUS_CHOICES, validators=[DataRequired()])
    student_ids = SelectMultipleField('Linked Students:', coerce=int, choices=[], validators=[Optional()])
    submit      = SubmitField('Save Parent')


class EmailConfigForm(FlaskForm):
    mail_server = StringField('SMTP Server', validators=[Optional()])
    mail_port = IntegerField('SMTP Port', validators=[Optional()])
    mail_use_tls = BooleanField('Use TLS (STARTTLS)')
    mail_use_ssl = BooleanField('Use SSL')
    mail_username = StringField('Username / Email', validators=[Optional()])
    mail_password = PasswordField('Password', validators=[Optional()])
    mail_default_sender = StringField('Default Sender Email', validators=[Optional(), Email()])
    submit_email = SubmitField('Save Email Settings')

