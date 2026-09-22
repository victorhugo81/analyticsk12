# seed_data.py
import os
from getpass import getpass
from dotenv import load_dotenv

# Adjust these imports if installation/ is not a package or outside PYTHONPATH
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import create_app, db
from application.models import Organization, User, Role, Site, GraduationRequirement

from werkzeug.security import generate_password_hash
from sqlalchemy.exc import SQLAlchemyError






# Standard subject-area credit requirements for the Graduation Status dashboard
# (Settings > Graduation Settings). Sums to the 220-credit default (Organization.
# grad_credits_required). Algebra I is sorted before Mathematics since it's a
# carve-out of that department (name_keywords narrows it to Algebra courses only;
# the broader Mathematics row catches everything else in that department).
GRADUATION_REQUIREMENTS = [
    dict(subject_name='English',      credits_required=40, departments='English',
         sort_order=10, start_grade='9',  end_grade='12'),
    dict(subject_name='Algebra I',     credits_required=10, departments='Mathematics',
         name_keywords='Algebra', sort_order=20, start_grade='9',  end_grade='9'),
    dict(subject_name='Mathematics',   credits_required=20, departments='Mathematics',
         sort_order=30, start_grade='9',  end_grade='12'),
    dict(subject_name='Science',       credits_required=30, departments='Life Science,Physical Science',
         sort_order=40, start_grade='9',  end_grade='12'),
    dict(subject_name='Social Science', credits_required=30, departments='Social Science',
         sort_order=50, start_grade='10', end_grade='12'),
    dict(subject_name='Physical Education', credits_required=20, departments='Physical Education',
         sort_order=60, start_grade='9',  end_grade='10'),
    dict(subject_name='Visual/Performing Arts & World Language', credits_required=10,
         departments='Art,Music,Foreign Language', sort_order=70, start_grade='9', end_grade='12'),
    dict(subject_name='Electives', credits_required=60, is_catch_all=True,
         sort_order=999, start_grade='9', end_grade='12'),
]

# Load environment variables
load_dotenv()
app = create_app()

admin_email = input("Enter admin email (e.g., admin@yourdomain.edu): ")
admin_password = getpass("Enter admin password (min 10 chars, letters, digits, symbol): ")
admin_first_name = input("Enter admin first name (default: Admin): ") or "Admin"
admin_last_name = input("Enter admin last name (default: User): ") or "User"

with app.app_context():
    try:
        db.create_all()
        
        # --- Organization ---
        school_district_name = os.getenv('DEFAULT_ORGANIZATION_NAME') or 'Default Organization'
        organization = db.session.get(Organization, 1)

        if organization:
            organization.organization_name = school_district_name
            organization.site_version = '1.0'
            print("Organization updated.")
        else:
            organization = Organization(id=1, organization_name=school_district_name, site_version='1.0')
            db.session.add(organization)
            print("Organization created.")

        # --- Roles ---
        roles = [
            ('1', 'Admin'),
            ('2', 'District Administrator'),
            ('3', 'School Administrator'),
            ('4', 'Teacher'),
            ('5', 'Staff')
        ]
        for role_id, role_name in roles:
            if not Role.query.filter_by(role_name=role_name).first():
                db.session.add(Role(id=int(role_id), role_name=role_name))
                print(f"Role added: {role_name}")
            else:
                print(f"Role already exists: {role_name}")

        # --- Site ---
        site_data = {
            'id': 1,
            'site_name': 'District Office',
            'site_cds': '99-99999-9999999',
            'site_code': '012345',
            'site_address': '1234 Main St.',
            'site_type': 'District Office',
            'site_acronyms': 'DO'
        }
        existing_site = Site.query.filter_by(site_cds=site_data['site_cds']).first()
        if existing_site:
            for key, value in site_data.items():
                setattr(existing_site, key, value)
            print("Site updated.")
        else:
            db.session.add(Site(**site_data))
            print("Site created.")

        # --- Graduation Requirements ---
        for r in GRADUATION_REQUIREMENTS:
            if not GraduationRequirement.query.filter_by(subject_name=r['subject_name']).first():
                db.session.add(GraduationRequirement(**r))
                print(f"Graduation requirement added: {r['subject_name']}")
            else:
                print(f"Graduation requirement already exists: {r['subject_name']}")

        # --- Admin User ---
        user = User.query.filter_by(email=admin_email).first()
        if user:
            user.first_name = admin_first_name
            user.last_name = admin_last_name
            user.password = generate_password_hash(admin_password)
            print("Admin user updated.")
        else:
            db.session.add(User(
                first_name=admin_first_name,
                middle_name='',
                last_name=admin_last_name,
                email=admin_email,
                password=generate_password_hash(admin_password),
                status='Active',
                rm_num='999',
                site_id=1,
                role_id=1
            ))
            print("Admin user created.")


        db.session.commit()
        print("All data seeded successfully.")

    except SQLAlchemyError as err:
        db.session.rollback()
        print(f"SQLAlchemy Error: {err}")
