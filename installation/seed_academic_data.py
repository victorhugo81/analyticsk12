"""
Seed academic data: sites, teachers, students, courses, parents.
Run from the project root:
    python installation/seed_academic_data.py
"""
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date
from main import create_app, db
from application.models import Site, Student, Teacher, Course, Parent, Absence, Incident, Grade, GraduationRequirement
from sqlalchemy.exc import SQLAlchemyError

app = create_app()

# ---------------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------------

SITES = [
    dict(site_name='Lincoln Elementary',      site_cds='19647330100001', site_code='LE001',  site_address='100 Lincoln Ave.',      site_type='Elementary', site_acronyms='LE'),
    dict(site_name='Washington Elementary',   site_cds='19647330100002', site_code='WE002',  site_address='200 Washington Blvd.',  site_type='Elementary', site_acronyms='WE'),
    dict(site_name='Jefferson Middle School', site_cds='19647330100003', site_code='JMS003', site_address='300 Jefferson St.',     site_type='Middle',     site_acronyms='JMS'),
    dict(site_name='Roosevelt High School',   site_cds='19647330100004', site_code='RHS004', site_address='400 Roosevelt Dr.',     site_type='High',       site_acronyms='RHS'),
    dict(site_name='Kennedy Elementary',      site_cds='19647330100005', site_code='KE005',  site_address='500 Kennedy Ct.',       site_type='Elementary', site_acronyms='KE'),
    dict(site_name='Madison Middle School',   site_cds='19647330100006', site_code='MMS006', site_address='600 Madison Ave.',      site_type='Middle',     site_acronyms='MMS'),
    dict(site_name='Adams High School',       site_cds='19647330100007', site_code='AHS007', site_address='700 Adams Blvd.',       site_type='High',       site_acronyms='AHS'),
    dict(site_name='Chavez Elementary',       site_cds='19647330100008', site_code='CHE008', site_address='800 Chavez Way.',       site_type='Elementary', site_acronyms='CHE'),
    dict(site_name='Fremont K-8 Academy',     site_cds='19647330100009', site_code='FKA009', site_address='900 Fremont Pkwy.',     site_type='K-8',        site_acronyms='FKA'),
]

TEACHERS = [
    # Lincoln Elementary
    dict(first_name='Maria',    last_name='Garcia',    employee_id='T001', email='m.garcia@school.edu',     department='Elementary', site_code='LE001'),
    dict(first_name='James',    last_name='Wilson',    employee_id='T002', email='j.wilson@school.edu',     department='Elementary', site_code='LE001'),
    dict(first_name='Sarah',    last_name='Johnson',   employee_id='T003', email='s.johnson@school.edu',    department='Elementary', site_code='LE001'),
    # Washington Elementary
    dict(first_name='Robert',   last_name='Martinez',  employee_id='T004', email='r.martinez@school.edu',   department='Elementary', site_code='WE002'),
    dict(first_name='Emily',    last_name='Chen',      employee_id='T005', email='e.chen@school.edu',       department='Elementary', site_code='WE002'),
    dict(first_name='David',    last_name='Thompson',  employee_id='T006', email='d.thompson@school.edu',   department='Elementary', site_code='WE002'),
    # Jefferson Middle School
    dict(first_name='Lisa',     last_name='Nguyen',    employee_id='T007', email='l.nguyen@school.edu',     department='Science', site_code='JMS003'),
    dict(first_name='Kevin',    last_name='Park',      employee_id='T008', email='k.park@school.edu',       department='English', site_code='JMS003'),
    dict(first_name='Amanda',   last_name='Rivera',    employee_id='T009', email='a.rivera@school.edu',     department='Mathematics', site_code='JMS003'),
    # Roosevelt High School
    dict(first_name='Thomas',   last_name='Baker',     employee_id='T010', email='t.baker@school.edu',      department='Mathematics', site_code='RHS004'),
    dict(first_name='Jessica',  last_name='Hall',      employee_id='T011', email='j.hall@school.edu',       department='English', site_code='RHS004'),
    dict(first_name='Carlos',   last_name='Gonzalez',  employee_id='T012', email='c.gonzalez@school.edu',   department='Science', site_code='RHS004'),
    dict(first_name='Michelle', last_name='Scott',     employee_id='T013', email='m.scott@school.edu',      department='History', site_code='RHS004'),
    # Kennedy Elementary
    dict(first_name='Angela',   last_name='Reyes',     employee_id='T014', email='a.reyes@school.edu',       department='Elementary', site_code='KE005'),
    dict(first_name='Brian',    last_name='Owens',     employee_id='T015', email='b.owens@school.edu',       department='Elementary', site_code='KE005'),
    dict(first_name='Carmen',   last_name='Vega',      employee_id='T016', email='c.vega@school.edu',        department='Elementary', site_code='KE005'),
    # Madison Middle School
    dict(first_name='Derek',    last_name='Stone',     employee_id='T017', email='d.stone@school.edu',       department='Science', site_code='MMS006'),
    dict(first_name='Fiona',    last_name='Walsh',     employee_id='T018', email='f.walsh@school.edu',       department='English', site_code='MMS006'),
    dict(first_name='George',   last_name='Pham',      employee_id='T019', email='g.pham@school.edu',        department='Mathematics', site_code='MMS006'),
    # Adams High School
    dict(first_name='Helen',    last_name='Moore',     employee_id='T020', email='h.moore@school.edu',       department='Mathematics', site_code='AHS007'),
    dict(first_name='Ivan',     last_name='Russo',     employee_id='T021', email='i.russo@school.edu',       department='English', site_code='AHS007'),
    dict(first_name='Julia',    last_name='Odom',      employee_id='T022', email='j.odom@school.edu',        department='Science', site_code='AHS007'),
    # Chavez Elementary
    dict(first_name='Kenneth',  last_name='Flores',    employee_id='T023', email='k.flores@school.edu',      department='Elementary', site_code='CHE008'),
    dict(first_name='Laura',    last_name='Diaz',      employee_id='T024', email='l.diaz@school.edu',        department='Elementary', site_code='CHE008'),
    dict(first_name='Mario',    last_name='Escobar',   employee_id='T025', email='m.escobar@school.edu',     department='Elementary', site_code='CHE008'),
    # Fremont K-8 Academy
    dict(first_name='Nina',     last_name='Cheng',     employee_id='T026', email='n.cheng@school.edu',       department='Humanities', site_code='FKA009'),
    dict(first_name='Oscar',    last_name='Delgado',   employee_id='T027', email='o.delgado@school.edu',     department='Mathematics', site_code='FKA009'),
    dict(first_name='Paula',    last_name='Yuen',      employee_id='T028', email='p.yuen@school.edu',        department='Science', site_code='FKA009'),
]

# Standard subject-area credit requirements for the Graduation Status dashboard
# (Settings > Graduation Settings). Sums to the district's 220-credit target.
# Algebra I is sorted before Mathematics since it's a carve-out of that department
# (name_keywords narrows it to just Algebra courses; the broader Mathematics row
# catches everything else in that department).
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

_SC  = '2025-2026'
_PY  = '2024-2025'
_LE  = '19647330100001'
_WE  = '19647330100002'
_JMS = '19647330100003'
_RHS = '19647330100004'
_KE  = '19647330100005'
_MMS = '19647330100006'
_AHS = '19647330100007'
_CHE = '19647330100008'
_FKA = '19647330100009'

STUDENTS = [
    # ── Lincoln Elementary ──────────────────────────────────────────────────
    dict(first_name='Sofia',     last_name='Ramirez',    student_id='S1001', ssid='', cds_code=_LE,  grade='TK', gender='F', date_of_birth=date(2020, 4,  3),  gradyr='2038', ethnicity='500', frm_code='F', english_status='EO',   enter_date=date(2026, 5, 10), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Mateo',     last_name='Torres',     student_id='S1002', ssid='1000000002', cds_code=_LE,  grade='KN',  gender='M', date_of_birth=date(2019, 9, 14),  gradyr='2037', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Aisha',     last_name='Williams',   student_id='S1003', ssid='1000000003', cds_code=_LE,  grade='1',  gender='F', date_of_birth=date(2018, 6, 22),  gradyr='2036', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True, sed504=False,   site_code='LE001'),
    dict(first_name='Ethan',     last_name='Kim',        student_id='S1004', ssid='1000000004', cds_code=_LE,  grade='1',  gender='M', date_of_birth=date(2018, 11, 5),  gradyr='2036', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Luna',      last_name='Flores',     student_id='S1005', ssid='1000000005', cds_code=_LE,  grade='2',  gender='F', date_of_birth=date(2017, 2, 18),  gradyr='2035', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True,  schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Marcus',    last_name='Johnson',    student_id='S1006', ssid='1000000006', cds_code=_LE,  grade='2',  gender='M', date_of_birth=date(2017, 8, 30),  gradyr='2035', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='D', migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Zoe',       last_name='Patel',      student_id='S1007', ssid='1000000007', cds_code=_LE,  grade='3',  gender='F', date_of_birth=date(2016, 5, 11),  gradyr='2034', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2026, 1, 16), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Carlos',    last_name='Mendoza',    student_id='S1008', ssid='1000000008', cds_code=_LE,  grade='3',  gender='M', date_of_birth=date(2016, 10, 7),  gradyr='2034', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLI', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Emma',      last_name='Davis',      student_id='S1009', ssid='1000000009', cds_code=_LE,  grade='4',  gender='F', date_of_birth=date(2015, 3, 25),  gradyr='2033', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2026, 2, 17), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True,   site_code='LE001'),
    dict(first_name='Jaylen',    last_name='Brown',      student_id='S1010', ssid='1000000010', cds_code=_LE,  grade='4',  gender='M', date_of_birth=date(2015, 7, 19),  gradyr='2033', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    dict(first_name='Priya',     last_name='Sharma',     student_id='S1011', ssid='1000000011', cds_code=_LE,  grade='5',  gender='F', date_of_birth=date(2014, 1,  8),  gradyr='2032', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=date(2026, 5, 10), disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True,   site_code='LE001'),
    dict(first_name='Diego',     last_name='Herrera',    student_id='S1012', ssid='', cds_code=_LE,  grade='6',  gender='X', date_of_birth=date(2013, 6, 14),  gradyr='2031', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2018, 8, 20), disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='LE001'),
    # ── Washington Elementary ────────────────────────────────────────────────
    dict(first_name='Abby',      last_name='Nelson',     student_id='S1013', ssid='1000000013', cds_code=_WE,  grade='TK', gender='F', date_of_birth=date(2020, 7, 21),  gradyr='2038', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=date(2026, 1, 15),  disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='WE002'),
    dict(first_name='Ryan',      last_name='Chen',       student_id='S1014', ssid='1000000014', cds_code=_WE,  grade='KN',  gender='M', date_of_birth=date(2019, 3,  9),  gradyr='2037', ethnicity='200', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Amara',     last_name='Okafor',     student_id='S1015', ssid='1000000015', cds_code=_WE,  grade='1',  gender='F', date_of_birth=date(2018, 10, 17), gradyr='2036', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Jake',      last_name='Wilson',     student_id='S1016', ssid='1000000016', cds_code=_WE,  grade='1',  gender='M', date_of_birth=date(2018, 4,  2),  gradyr='2036', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Valentina', last_name='Cruz',       student_id='S1017', ssid='1000000017', cds_code=_WE,  grade='2',  gender='F', date_of_birth=date(2017, 12, 28), gradyr='2035', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True,  schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Liam',      last_name='Murphy',     student_id='S1018', ssid='1000000018', cds_code=_WE,  grade='2',  gender='M', date_of_birth=date(2017, 5, 16),  gradyr='2035', ethnicity='700', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Keisha',    last_name='Robinson',   student_id='S1019', ssid='1000000019', cds_code=_WE,  grade='3',  gender='F', date_of_birth=date(2016, 8,  4),  gradyr='2034', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='DD',  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Alex',      last_name='Nguyen',     student_id='S1020', ssid='1000000020', cds_code=_WE,  grade='3',  gender='M', date_of_birth=date(2016, 1, 23),  gradyr='2034', ethnicity='400', frm_code='F', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Lily',      last_name='Thompson',   student_id='S1021', ssid='1000000021', cds_code=_WE,  grade='4',  gender='F', date_of_birth=date(2015, 9, 12),  gradyr='2033', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Darius',    last_name='Jackson',    student_id='S1022', ssid='1000000022', cds_code=_WE,  grade='4',  gender='M', date_of_birth=date(2015, 4,  7),  gradyr='2033', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False,   site_code='WE002'),
    dict(first_name='Camila',    last_name='Morales',    student_id='S1023', ssid='1000000023', cds_code=_WE,  grade='5',  gender='F', date_of_birth=date(2014, 11, 30), gradyr='2032', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='D',  migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='WE002'),
    dict(first_name='Noah',      last_name='Anderson',   student_id='S1024', ssid='1000000024', cds_code=_WE,  grade='6',  gender='M', date_of_birth=date(2013, 2, 19),  gradyr='2031', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True,   site_code='WE002'),
    # ── Jefferson Middle School ──────────────────────────────────────────────
    dict(first_name='Jasmine',   last_name='Lee',        student_id='S1025', ssid='1000000025', cds_code=_JMS, grade='7',  gender='F', date_of_birth=date(2012, 8, 16),  gradyr='2030', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True, sed504=False,   site_code='JMS003'),
    dict(first_name='Malik',     last_name='Thompson',   student_id='S1026', ssid='1000000026', cds_code=_JMS, grade='7',  gender='M', date_of_birth=date(2012, 3,  4),  gradyr='2030', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=date(2026, 3, 21),  disability='SLD', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='JMS003'),
    dict(first_name='Isabella',  last_name='Santos',     student_id='S1027', ssid='1000000027', cds_code=_JMS, grade='7',  gender='F', date_of_birth=date(2012, 11, 27), gradyr='2030', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Tyler',     last_name='Harris',     student_id='S1028', ssid='1000000028', cds_code=_JMS, grade='7',  gender='M', date_of_birth=date(2012, 6, 13),  gradyr='2030', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Yuki',      last_name='Tanaka',     student_id='S1029', ssid='1000000029', cds_code=_JMS, grade='8',  gender='F', date_of_birth=date(2011, 4,  9),  gradyr='2029', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Andre',     last_name='Williams',   student_id='S1030', ssid='1000000030', cds_code=_JMS, grade='8',  gender='M', date_of_birth=date(2011, 10, 22), gradyr='2029', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=True,  schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Sofia',     last_name='Castro',     student_id='S1031', ssid='1000000031', cds_code=_JMS, grade='8',  gender='F', date_of_birth=date(2011, 1, 15),  gradyr='2029', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Ethan',     last_name='Parker',     student_id='S1032', ssid='1000000032', cds_code=_JMS, grade='8',  gender='M', date_of_birth=date(2011, 7, 31),  gradyr='2029', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 14), exit_date=None, disability='OHI', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True,   site_code='JMS003'),
    dict(first_name='Aaliyah',   last_name='Brooks',     student_id='S1033', ssid='1000000033', cds_code=_JMS, grade='8',  gender='F', date_of_birth=date(2011, 5,  6),  gradyr='2029', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    dict(first_name='Marco',     last_name='Rodriguez',  student_id='S1034', ssid='1000000034', cds_code=_JMS, grade='7',  gender='M', date_of_birth=date(2012, 9, 20),  gradyr='2030', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='S',  migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='JMS003'),
    # ── Roosevelt High School ────────────────────────────────────────────────
    dict(first_name='Hannah',    last_name='Mitchell',   student_id='S1035', ssid='1000000035', cds_code=_RHS, grade='9',  gender='F', date_of_birth=date(2010, 6,  3),  gradyr='2028', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Jordan',    last_name='Evans',      student_id='S1036', ssid='1000000036', cds_code=_RHS, grade='9',  gender='M', date_of_birth=date(2010, 12, 17), gradyr='2028', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Maya',      last_name='Patel',      student_id='S1037', ssid='1000000037', cds_code=_RHS, grade='9',  gender='F', date_of_birth=date(2010, 3, 28),  gradyr='2028', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLD', dwelling=None, migrant=True, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Isaiah',    last_name='Turner',     student_id='S1038', ssid='1000000038', cds_code=_RHS, grade='10', gender='M', date_of_birth=date(2009, 9, 11),  gradyr='2027', ethnicity='600', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='S', migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Elena',     last_name='Vasquez',    student_id='S1039', ssid='1000000039', cds_code=_RHS, grade='10', gender='F', date_of_birth=date(2009, 5, 24),  gradyr='2027', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Caleb',     last_name='Wright',     student_id='S1040', ssid='1000000040', cds_code=_RHS, grade='10', gender='M', date_of_birth=date(2009, 1,  7),  gradyr='2027', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Destiny',   last_name='Jenkins',    student_id='S1041', ssid='1000000041', cds_code=_RHS, grade='11', gender='F', date_of_birth=date(2008, 7, 15),  gradyr='2026', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False,   site_code='RHS004'),
    dict(first_name='Nathan',    last_name='Kim',        student_id='S1042', ssid='1000000042', cds_code=_RHS, grade='11', gender='M', date_of_birth=date(2008, 2, 26),  gradyr='2026', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Brianna',   last_name='Foster',     student_id='S1043', ssid='1000000043', cds_code=_RHS, grade='11', gender='F', date_of_birth=date(2008, 10, 8),  gradyr='2026', ethnicity='700', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True,   site_code='RHS004'),
    dict(first_name='Xavier',    last_name='Washington', student_id='S1044', ssid='1000000044', cds_code=_RHS, grade='12', gender='M', date_of_birth=date(2007, 4, 19),  gradyr='2025', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 19), exit_date=None, disability='ED',  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False,   site_code='RHS004'),
    dict(first_name='Alicia',    last_name='Reyes',      student_id='S1045', ssid='1000000045', cds_code=_RHS, grade='12', gender='F', date_of_birth=date(2007, 11, 30), gradyr='2025', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 19), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='RHS004'),
    # ── Kennedy Elementary ───────────────────────────────────────────────────
    dict(first_name='Rosa',      last_name='Gutierrez',  student_id='S1046', ssid='1000000046', cds_code=_KE,  grade='TK', gender='F', date_of_birth=date(2020,  9,  5), gradyr='2038', ethnicity='500', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Owen',      last_name='Clark',      student_id='S1047', ssid='1000000047', cds_code=_KE,  grade='KN',  gender='M', date_of_birth=date(2019,  6, 12), gradyr='2037', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Nadia',     last_name='Hassan',     student_id='S1048', ssid='1000000048', cds_code=_KE,  grade='1',  gender='F', date_of_birth=date(2018,  3, 28), gradyr='2036', ethnicity='600', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Derek',     last_name='Chow',       student_id='S1049', ssid='1000000049', cds_code=_KE,  grade='1',  gender='M', date_of_birth=date(2018,  7,  4), gradyr='2036', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Esme',      last_name='Rivera',     student_id='S1050', ssid='1000000050', cds_code=_KE,  grade='2',  gender='F', date_of_birth=date(2017, 11, 19), gradyr='2035', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Tobias',    last_name='Young',      student_id='S1051', ssid='1000000051', cds_code=_KE,  grade='3',  gender='M', date_of_birth=date(2016,  4,  7), gradyr='2034', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 15), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Nia',       last_name='Cooper',     student_id='S1052', ssid='1000000052', cds_code=_KE,  grade='3',  gender='F', date_of_birth=date(2016, 10, 22), gradyr='2034', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 15), exit_date=None, disability='SLD', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Hector',    last_name='Ruiz',       student_id='S1053', ssid='1000000053', cds_code=_KE,  grade='4',  gender='M', date_of_birth=date(2015,  2, 14), gradyr='2033', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Amber',     last_name='Nguyen',     student_id='S1054', ssid='1000000054', cds_code=_KE,  grade='4',  gender='F', date_of_birth=date(2015,  8, 31), gradyr='2033', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True, site_code='KE005'),
    dict(first_name='Leo',       last_name='Petrov',     student_id='S1055', ssid='1000000055', cds_code=_KE,  grade='5',  gender='M', date_of_birth=date(2014,  5,  3), gradyr='2032', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Faith',     last_name='Coleman',    student_id='S1056', ssid='1000000056', cds_code=_KE,  grade='5',  gender='F', date_of_birth=date(2014, 12, 16), gradyr='2032', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False, site_code='KE005'),
    dict(first_name='Alan',      last_name='Santos',     student_id='S1057', ssid='1000000057', cds_code=_KE,  grade='6',  gender='M', date_of_birth=date(2013,  8,  9), gradyr='2031', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='D',  migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    # ── Madison Middle School ────────────────────────────────────────────────
    dict(first_name='Brooke',    last_name='Harrison',   student_id='S1058', ssid='1000000058', cds_code=_MMS, grade='7',  gender='F', date_of_birth=date(2012,  7,  4), gradyr='2030', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Kwame',     last_name='Asante',     student_id='S1059', ssid='1000000059', cds_code=_MMS, grade='7',  gender='M', date_of_birth=date(2012,  1, 19), gradyr='2030', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None,  disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Mei Lin',   last_name='Zhang',      student_id='S1060', ssid='1000000060', cds_code=_MMS, grade='7',  gender='F', date_of_birth=date(2012,  5, 30), gradyr='2030', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Gabriel',   last_name='Navarro',    student_id='S1061', ssid='1000000061', cds_code=_MMS, grade='7',  gender='M', date_of_birth=date(2012,  9, 15), gradyr='2030', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Tessa',     last_name='Hoffman',    student_id='S1062', ssid='1000000062', cds_code=_MMS, grade='8',  gender='F', date_of_birth=date(2011,  3, 22), gradyr='2029', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Deon',      last_name='Bradley',    student_id='S1063', ssid='1000000063', cds_code=_MMS, grade='8',  gender='M', date_of_birth=date(2011, 11,  8), gradyr='2029', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLD', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Samira',    last_name='Khalil',     student_id='S1064', ssid='1000000064', cds_code=_MMS, grade='8',  gender='F', date_of_birth=date(2011,  6,  1), gradyr='2029', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='M', migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Justin',    last_name='Price',      student_id='S1065', ssid='1000000065', cds_code=_MMS, grade='8',  gender='M', date_of_birth=date(2011,  8, 25), gradyr='2029', ethnicity='700', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='OHI', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Yolanda',   last_name='Fuentes',    student_id='S1066', ssid='1000000066', cds_code=_MMS, grade='7',  gender='F', date_of_birth=date(2012,  4, 10), gradyr='2030', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Tomas',     last_name='Iwata',      student_id='S1067', ssid='1000000067', cds_code=_MMS, grade='8',  gender='M', date_of_birth=date(2011, 12, 14), gradyr='2029', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='MMS006'),
    dict(first_name='Destiny',   last_name='Monroe',     student_id='S1068', ssid='1000000068', cds_code=_MMS, grade='7',  gender='F', date_of_birth=date(2012,  2, 27), gradyr='2030', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False, site_code='MMS006'),
    dict(first_name='Bryce',     last_name='McCann',     student_id='S1069', ssid='1000000069', cds_code=_MMS, grade='8',  gender='M', date_of_birth=date(2011, 10,  6), gradyr='2029', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True, site_code='MMS006'),
    # ── Adams High School ────────────────────────────────────────────────────
    dict(first_name='Cecilia',   last_name='Marquez',    student_id='S1070', ssid='1000000070', cds_code=_AHS, grade='9',  gender='F', date_of_birth=date(2010,  5, 11), gradyr='2028', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Dustin',    last_name='Owens',      student_id='S1071', ssid='1000000071', cds_code=_AHS, grade='9',  gender='M', date_of_birth=date(2010,  2,  3), gradyr='2028', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Kira',      last_name='Solomon',    student_id='S1072', ssid='1000000072', cds_code=_AHS, grade='10', gender='F', date_of_birth=date(2009,  8, 17), gradyr='2027', ethnicity='600', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Paulo',     last_name='Ferreira',   student_id='S1073', ssid='1000000073', cds_code=_AHS, grade='10', gender='M', date_of_birth=date(2009,  4, 28), gradyr='2027', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Allison',   last_name='Reed',       student_id='S1074', ssid='1000000074', cds_code=_AHS, grade='11', gender='F', date_of_birth=date(2008, 11,  9), gradyr='2026', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True, site_code='AHS007'),
    dict(first_name='Derrick',   last_name='Hawkins',    student_id='S1075', ssid='1000000075', cds_code=_AHS, grade='11', gender='M', date_of_birth=date(2008,  6, 23), gradyr='2026', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='ED',  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Naomi',     last_name='Ishida',     student_id='S1076', ssid='1000000076', cds_code=_AHS, grade='11', gender='F', date_of_birth=date(2008,  3,  5), gradyr='2026', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Brandon',   last_name='Cole',       student_id='S1077', ssid='1000000077', cds_code=_AHS, grade='12', gender='M', date_of_birth=date(2007, 10, 18), gradyr='2025', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Xiomara',   last_name='Delgado',    student_id='S1078', ssid='1000000078', cds_code=_AHS, grade='12', gender='F', date_of_birth=date(2007,  7, 31), gradyr='2025', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='S',  migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Jared',     last_name='Flynn',      student_id='S1079', ssid='1000000079', cds_code=_AHS, grade='9',  gender='M', date_of_birth=date(2010, 11, 24), gradyr='2028', ethnicity='700', frm_code='R', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    dict(first_name='Layla',     last_name='Freeman',    student_id='S1080', ssid='1000000080', cds_code=_AHS, grade='10', gender='F', date_of_birth=date(2009,  1, 16), gradyr='2027', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False, site_code='AHS007'),
    dict(first_name='Marcus',    last_name='Tran',       student_id='S1081', ssid='1000000081', cds_code=_AHS, grade='12', gender='M', date_of_birth=date(2007,  4,  7), gradyr='2025', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 15), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='AHS007'),
    # ── Chavez Elementary ────────────────────────────────────────────────────
    dict(first_name='Rosa',      last_name='Jimenez',    student_id='S1082', ssid='1000000082', cds_code=_CHE, grade='TK', gender='F', date_of_birth=date(2020, 10, 13), gradyr='2038', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='D', migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Samuel',    last_name='Brooks',     student_id='S1083', ssid='1000000083', cds_code=_CHE, grade='KN',  gender='M', date_of_birth=date(2019,  5,  7), gradyr='2037', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Chloe',     last_name='Yamamoto',   student_id='S1084', ssid='1000000084', cds_code=_CHE, grade='1',  gender='F', date_of_birth=date(2018,  2, 21), gradyr='2036', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Victor',    last_name='Restrepo',   student_id='S1085', ssid='1000000085', cds_code=_CHE, grade='1',  gender='M', date_of_birth=date(2018,  8, 16), gradyr='2036', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True,  schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Penelope',  last_name='Stone',      student_id='S1086', ssid='1000000086', cds_code=_CHE, grade='2',  gender='F', date_of_birth=date(2017,  4,  3), gradyr='2035', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Jabari',    last_name='Hunt',       student_id='S1087', ssid='1000000087', cds_code=_CHE, grade='3',  gender='M', date_of_birth=date(2016,  9, 26), gradyr='2034', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLI', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Marisol',   last_name='DeLeon',     student_id='S1088', ssid='1000000088', cds_code=_CHE, grade='3',  gender='F', date_of_birth=date(2016, 12,  4), gradyr='2034', ethnicity='500', frm_code='R', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Connor',    last_name='Walsh',      student_id='S1089', ssid='1000000089', cds_code=_CHE, grade='4',  gender='M', date_of_birth=date(2015,  6, 18), gradyr='2033', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Amina',     last_name='Diallo',     student_id='S1090', ssid='1000000090', cds_code=_CHE, grade='4',  gender='F', date_of_birth=date(2015,  3,  9), gradyr='2033', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Felix',     last_name='Romero',     student_id='S1091', ssid='1000000091', cds_code=_CHE, grade='5',  gender='M', date_of_birth=date(2014,  7, 27), gradyr='2032', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Trinity',   last_name='Harris',     student_id='S1092', ssid='1000000092', cds_code=_CHE, grade='5',  gender='F', date_of_birth=date(2014, 10,  1), gradyr='2032', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True,  sed504=False, site_code='CHE008'),
    dict(first_name='Lucas',     last_name='Bergmann',   student_id='S1093', ssid='1000000093', cds_code=_CHE, grade='6',  gender='M', date_of_birth=date(2013,  1, 30), gradyr='2031', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True, site_code='CHE008'),
    # ── Fremont K-8 Academy ──────────────────────────────────────────────────
    dict(first_name='Zara',      last_name='Ahmed',      student_id='S1094', ssid='1000000094', cds_code=_FKA, grade='KN',  gender='F', date_of_birth=date(2019,  4, 14), gradyr='2037', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=True, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Patrick',   last_name='OBrien',     student_id='S1095', ssid='1000000095', cds_code=_FKA, grade='1',  gender='M', date_of_birth=date(2018,  9, 29), gradyr='2036', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Bianca',    last_name='Esposito',   student_id='S1096', ssid='1000000096', cds_code=_FKA, grade='2',  gender='F', date_of_birth=date(2017,  6, 11), gradyr='2035', ethnicity='500', frm_code='R', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Miles',     last_name='Jefferson',  student_id='S1097', ssid='1000000097', cds_code=_FKA, grade='3',  gender='M', date_of_birth=date(2016,  2,  8), gradyr='2034', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Serena',    last_name='Huang',      student_id='S1098', ssid='1000000098', cds_code=_FKA, grade='4',  gender='F', date_of_birth=date(2015, 11, 23), gradyr='2033', ethnicity='200', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Eduardo',   last_name='Salinas',    student_id='S1099', ssid='1000000099', cds_code=_FKA, grade='5',  gender='M', date_of_birth=date(2014,  8,  5), gradyr='2032', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling='D',  migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Grace',     last_name='Osei',       student_id='S1100', ssid='1000000100', cds_code=_FKA, grade='6',  gender='F', date_of_birth=date(2013,  5, 17), gradyr='2031', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2026, 4, 19), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Luca',      last_name='Marchetti',  student_id='S1101', ssid='1000000101', cds_code=_FKA, grade='7',  gender='M', date_of_birth=date(2012, 11,  2), gradyr='2030', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=True, sed504=False, site_code='FKA009'),
    dict(first_name='Fatima',    last_name='Bello',      student_id='S1102', ssid='1000000102', cds_code=_FKA, grade='7',  gender='F', date_of_birth=date(2012,  8, 20), gradyr='2030', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLD', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Santiago',  last_name='Vega',       student_id='S1103', ssid='1000000103', cds_code=_FKA, grade='8',  gender='M', date_of_birth=date(2011,  3, 13), gradyr='2029', ethnicity='500', frm_code='R', english_status='RFEP', enter_date=date(2025, 8, 14), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Hana',      last_name='Kobayashi',  student_id='S1104', ssid='1000000104', cds_code=_FKA, grade='8',  gender='F', date_of_birth=date(2011,  9,  6), gradyr='2029', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Owen',      last_name='Larsen',     student_id='S1105', ssid='1000000105', cds_code=_FKA, grade='8',  gender='M', date_of_birth=date(2011,  6, 28), gradyr='2029', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None,  dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    # ── Additional Grade 2 ──────────────────────────────────────────────────
    dict(first_name='Destiny',   last_name='Williams',   student_id='S1106', ssid='1000000106', cds_code=_LE,  grade='2',  gender='F', date_of_birth=date(2017,  3, 14), gradyr='2035', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='LE001'),
    dict(first_name='Marco',     last_name='Reyes',      student_id='S1107', ssid='1000000107', cds_code=_WE,  grade='2',  gender='M', date_of_birth=date(2017,  7, 22), gradyr='2035', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='WE002'),
    dict(first_name='Naomi',     last_name='Greene',     student_id='S1108', ssid='1000000108', cds_code=_CHE, grade='2',  gender='F', date_of_birth=date(2017, 11,  5), gradyr='2035', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    # ── Additional Grade 4 ──────────────────────────────────────────────────
    dict(first_name='Javier',    last_name='Lopez',      student_id='S1109', ssid='1000000109', cds_code=_KE,  grade='4',  gender='M', date_of_birth=date(2015,  4, 18), gradyr='2033', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Ava',       last_name='Patterson',  student_id='S1110', ssid='1000000110', cds_code=_LE,  grade='4',  gender='F', date_of_birth=date(2015,  9, 27), gradyr='2033', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='LE001'),
    dict(first_name='Dominic',   last_name='Foster',     student_id='S1111', ssid='1000000111', cds_code=_WE,  grade='4',  gender='M', date_of_birth=date(2015,  1,  9), gradyr='2033', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='WE002'),
    # ── Additional Grade 6 ──────────────────────────────────────────────────
    dict(first_name='Aaliyah',   last_name='Simmons',    student_id='S1112', ssid='1000000112', cds_code=_KE,  grade='6',  gender='F', date_of_birth=date(2013,  6, 30), gradyr='2031', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Rafael',    last_name='Ortega',     student_id='S1113', ssid='1000000113', cds_code=_CHE, grade='6',  gender='M', date_of_birth=date(2013,  2, 14), gradyr='2031', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    dict(first_name='Nina',      last_name='Blackwell',  student_id='S1114', ssid='1000000114', cds_code=_FKA, grade='6',  gender='F', date_of_birth=date(2013, 10, 22), gradyr='2031', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    # ── Additional Grade 2 ──────────────────────────────────────────────────
    dict(first_name='Isaac',     last_name='Moreno',     student_id='S1115', ssid='1000000115', cds_code=_FKA, grade='2',  gender='M', date_of_birth=date(2017,  3, 20), gradyr='2035', ethnicity='500', frm_code='F', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Amelia',    last_name='Jackson',    student_id='S1116', ssid='1000000116', cds_code=_KE,  grade='2',  gender='F', date_of_birth=date(2017,  8,  7), gradyr='2035', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='KE005'),
    dict(first_name='Caleb',     last_name='Ortiz',      student_id='S1117', ssid='1000000117', cds_code=_CHE, grade='2',  gender='M', date_of_birth=date(2017,  5, 30), gradyr='2035', ethnicity='500', frm_code='R', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
    # ── Additional Grade 4 ──────────────────────────────────────────────────
    dict(first_name='Thomas',    last_name='Nguyen',     student_id='S1118', ssid='1000000118', cds_code=_FKA, grade='4',  gender='M', date_of_birth=date(2015,  5, 11), gradyr='2033', ethnicity='200', frm_code='P', english_status='IFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='FKA009'),
    dict(first_name='Olivia',    last_name='Barnes',     student_id='S1119', ssid='1000000119', cds_code=_CHE, grade='4',  gender='F', date_of_birth=date(2015, 10, 29), gradyr='2033', ethnicity='700', frm_code='P', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=True, site_code='CHE008'),
    dict(first_name='Isaiah',    last_name='Grant',      student_id='S1120', ssid='1000000120', cds_code=_LE,  grade='4',  gender='M', date_of_birth=date(2015,  2, 23), gradyr='2033', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability='SLD', dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='LE001'),
    # ── Additional Grade 6 ──────────────────────────────────────────────────
    dict(first_name='Jordan',    last_name='Castillo',   student_id='S1121', ssid='1000000121', cds_code=_LE,  grade='6',  gender='F', date_of_birth=date(2013,  3,  8), gradyr='2031', ethnicity='500', frm_code='F', english_status='RFEP', enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='LE001'),
    dict(first_name='Tyler',     last_name='Washington', student_id='S1122', ssid='1000000122', cds_code=_WE,  grade='6',  gender='M', date_of_birth=date(2013,  7, 15), gradyr='2031', ethnicity='600', frm_code='F', english_status='EO',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling=None, migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='WE002'),
    dict(first_name='Brianna',   last_name='Chavez',     student_id='S1123', ssid='1000000123', cds_code=_CHE, grade='6',  gender='F', date_of_birth=date(2013, 11,  1), gradyr='2031', ethnicity='500', frm_code='R', english_status='EL',   enter_date=date(2025, 8, 12), exit_date=None, disability=None, dwelling='D',  migrant=False, schoolyr=_SC, foster=False, sed504=False, site_code='CHE008'),
]

# Auto-generate student emails from first/last name
for _s in STUDENTS:
    fn = _s['first_name'].lower().replace(' ', '')
    ln = _s['last_name'].lower().replace(' ', '')
    _s['email'] = f"{fn}.{ln}@student.edu"

# ---------------------------------------------------------------------------
# Previous school year — same students, one grade lower, schoolyr = _PY
# ---------------------------------------------------------------------------

_GRADE_DOWN = {
    'TK': 'TK', 'KN': 'TK', '1': 'KN',  '2': '1',  '3': '2',
    '4':  '3',  '5': '4',  '6': '5',  '7': '6',  '8': '7',
    '9':  '8',  '10': '9', '11': '10','12': '11',
}
_Y2  = '2023-2024'
_Y3  = '2022-2023'
_PY_YEAR_END = date(2025, 6, 30)
_Y2_YEAR_END = date(2024, 6, 30)
_Y3_YEAR_END = date(2023, 6, 30)

STUDENTS_PY = []
for _s in STUDENTS:
    _p = _s.copy()
    _p['student_id'] = 'PY' + _s['student_id'][1:]   # S1001 → PY1001
    _p['schoolyr']   = _PY
    _p['grade']      = _GRADE_DOWN.get(_s['grade'], _s['grade'])
    # Carry exit_date only if it falls within 2024-2025; otherwise the
    # student was active for the full previous year.
    if _s.get('exit_date') and _s['exit_date'] <= _PY_YEAR_END:
        _p['exit_date'] = _s['exit_date']
    else:
        _p['exit_date'] = None
    STUDENTS_PY.append(_p)

def _grade_n_down(grade, n):
    g = grade
    for _ in range(n):
        g = _GRADE_DOWN.get(g, g)
    return g

# 2023-2024 — 90 students (realistic upward trend)
STUDENTS_Y2 = []
for _s in STUDENTS[:90]:
    _p = _s.copy()
    _p['student_id'] = 'Y2' + _s['student_id'][1:]
    _p['schoolyr']   = _Y2
    _p['grade']      = _grade_n_down(_s['grade'], 2)
    _p['exit_date']  = None
    STUDENTS_Y2.append(_p)

# 2022-2023 — 80 students
STUDENTS_Y3 = []
for _s in STUDENTS[:80]:
    _p = _s.copy()
    _p['student_id'] = 'Y3' + _s['student_id'][1:]
    _p['schoolyr']   = _Y3
    _p['grade']      = _grade_n_down(_s['grade'], 3)
    _p['exit_date']  = None
    STUDENTS_Y3.append(_p)

# course_code → teacher employee_id + site
COURSES = [
    # Lincoln Elementary
    dict(course_name='Reading & Literacy',      course_code='ELA101',  grade_level='1',  period='1st', teacher_emp='T001', site_code='LE001', max_students=25),
    dict(course_name='Mathematics K-6',         course_code='MATH101', grade_level='1',  period='2nd', teacher_emp='T002', site_code='LE001', max_students=25),
    dict(course_name='Science & Discovery',     course_code='SCI101',  grade_level='3',  period='3rd', teacher_emp='T003', site_code='LE001', max_students=25),
    dict(course_name='Physical Education LE',   course_code='PEE101',  grade_level='1',  period='4th', teacher_emp='T003', site_code='LE001', max_students=25),
    # Washington Elementary
    dict(course_name='Reading & Literacy WE',   course_code='ELA201',  grade_level='1',  period='1st', teacher_emp='T004', site_code='WE002', max_students=25),
    dict(course_name='Mathematics K-6 WE',      course_code='MATH201', grade_level='1',  period='2nd', teacher_emp='T005', site_code='WE002', max_students=25),
    dict(course_name='Science & Discovery WE',  course_code='SCI201',  grade_level='3',  period='3rd', teacher_emp='T006', site_code='WE002', max_students=25),
    dict(course_name='Physical Education WE',   course_code='PEE201',  grade_level='1',  period='4th', teacher_emp='T006', site_code='WE002', max_students=25),
    # Jefferson Middle School
    dict(course_name='English Language Arts',   course_code='ELA301',  grade_level='7',  period='1st', teacher_emp='T008', site_code='JMS003', max_students=25),
    dict(course_name='Mathematics 7-8',         course_code='MATH301', grade_level='7',  period='2nd', teacher_emp='T009', site_code='JMS003', max_students=25),
    dict(course_name='Life Science',            course_code='SCI301',  grade_level='8',  period='3rd', teacher_emp='T007', site_code='JMS003', max_students=25),
    dict(course_name='Physical Education MS',   course_code='PEM301',  grade_level='7',  period='4th', teacher_emp='T007', site_code='JMS003', max_students=25),
    # Roosevelt High School
    dict(course_name='Algebra I',               course_code='MATH401', grade_level='9',  period='1st', teacher_emp='T010', site_code='RHS004', max_students=25),
    dict(course_name='Pre-Calculus',            course_code='MATH402', grade_level='10', period='2nd', teacher_emp='T010', site_code='RHS004', max_students=25),
    dict(course_name='English Literature',      course_code='ENG401',  grade_level='10', period='1st', teacher_emp='T011', site_code='RHS004', max_students=25),
    dict(course_name='Biology',                 course_code='BIO401',  grade_level='9',  period='2nd', teacher_emp='T012', site_code='RHS004', max_students=25),
    dict(course_name='US History',              course_code='HIST401', grade_level='11', period='3rd', teacher_emp='T013', site_code='RHS004', max_students=25),
    dict(course_name='Physical Education HS',   course_code='PEH401',  grade_level='9',  period='4th', teacher_emp='T013', site_code='RHS004', max_students=25),
    # Kennedy Elementary
    dict(course_name='Reading & Literacy KE',   course_code='ELA501',  grade_level='1',  period='1st', teacher_emp='T014', site_code='KE005', max_students=25),
    dict(course_name='Mathematics K-6 KE',      course_code='MATH501', grade_level='1',  period='2nd', teacher_emp='T015', site_code='KE005', max_students=25),
    dict(course_name='Science & Discovery KE',  course_code='SCI501',  grade_level='3',  period='3rd', teacher_emp='T016', site_code='KE005', max_students=25),
    dict(course_name='Physical Education KE',   course_code='PEE501',  grade_level='1',  period='4th', teacher_emp='T016', site_code='KE005', max_students=25),
    # Madison Middle School
    dict(course_name='English Language Arts MMS', course_code='ELA601', grade_level='7', period='1st', teacher_emp='T018', site_code='MMS006', max_students=25),
    dict(course_name='Mathematics 7-8 MMS',     course_code='MATH601', grade_level='7',  period='2nd', teacher_emp='T019', site_code='MMS006', max_students=25),
    dict(course_name='Earth Science MMS',       course_code='SCI601',  grade_level='8',  period='3rd', teacher_emp='T017', site_code='MMS006', max_students=25),
    dict(course_name='Physical Education MMS',  course_code='PEM601',  grade_level='7',  period='4th', teacher_emp='T017', site_code='MMS006', max_students=25),
    # Adams High School
    dict(course_name='Algebra II',              course_code='MATH701', grade_level='10', period='1st', teacher_emp='T020', site_code='AHS007', max_students=25),
    dict(course_name='American Literature',     course_code='ENG701',  grade_level='11', period='2nd', teacher_emp='T021', site_code='AHS007', max_students=25),
    dict(course_name='Chemistry',               course_code='SCI701',  grade_level='10', period='3rd', teacher_emp='T022', site_code='AHS007', max_students=25),
    dict(course_name='US Government',           course_code='HIST701', grade_level='12', period='4th', teacher_emp='T021', site_code='AHS007', max_students=25),
    # Chavez Elementary
    dict(course_name='Reading & Literacy CE',   course_code='ELA801',  grade_level='1',  period='1st', teacher_emp='T023', site_code='CHE008', max_students=25),
    dict(course_name='Mathematics K-6 CE',      course_code='MATH801', grade_level='1',  period='2nd', teacher_emp='T024', site_code='CHE008', max_students=25),
    dict(course_name='Science & Discovery CE',  course_code='SCI801',  grade_level='3',  period='3rd', teacher_emp='T025', site_code='CHE008', max_students=25),
    dict(course_name='Physical Education CE',   course_code='PEE801',  grade_level='1',  period='4th', teacher_emp='T025', site_code='CHE008', max_students=25),
    # Fremont K-8 Academy
    dict(course_name='Integrated ELA FK8',      course_code='ELA901',  grade_level='3',  period='1st', teacher_emp='T026', site_code='FKA009', max_students=25),
    dict(course_name='Mathematics FK8',         course_code='MATH901', grade_level='3',  period='2nd', teacher_emp='T027', site_code='FKA009', max_students=25),
    dict(course_name='STEM Exploration FK8',    course_code='SCI901',  grade_level='5',  period='3rd', teacher_emp='T028', site_code='FKA009', max_students=25),
    dict(course_name='Physical Education FK8',  course_code='PEM901',  grade_level='5',  period='4th', teacher_emp='T028', site_code='FKA009', max_students=25),
]

ENROLLMENTS = {
    # Lincoln Elementary
    'S1001': ['ELA101', 'MATH101'],
    'S1002': ['ELA101', 'MATH101'],
    'S1003': ['ELA101', 'MATH101', 'SCI101'],
    'S1004': ['ELA101', 'MATH101', 'PEE101'],
    'S1005': ['ELA101', 'MATH101', 'SCI101'],
    'S1006': ['ELA101', 'MATH101', 'SCI101'],
    'S1007': ['ELA101', 'MATH101', 'SCI101', 'PEE101'],
    'S1008': ['ELA101', 'MATH101'],
    'S1009': ['MATH101', 'SCI101', 'PEE101'],
    'S1010': ['MATH101', 'SCI101', 'PEE101'],
    'S1011': ['MATH101', 'SCI101', 'PEE101'],
    'S1012': ['MATH101', 'SCI101', 'PEE101'],
    # Washington Elementary
    'S1013': ['ELA201', 'MATH201'],
    'S1014': ['ELA201', 'MATH201'],
    'S1015': ['ELA201', 'MATH201', 'SCI201'],
    'S1016': ['ELA201', 'MATH201', 'PEE201'],
    'S1017': ['ELA201', 'MATH201', 'SCI201'],
    'S1018': ['ELA201', 'MATH201'],
    'S1019': ['ELA201', 'MATH201', 'SCI201'],
    'S1020': ['ELA201', 'MATH201', 'SCI201'],
    'S1021': ['MATH201', 'SCI201', 'PEE201'],
    'S1022': ['MATH201', 'SCI201'],
    'S1023': ['MATH201', 'SCI201', 'PEE201'],
    'S1024': ['MATH201', 'SCI201', 'PEE201'],
    # Jefferson Middle School
    'S1025': ['ELA301', 'MATH301', 'PEM301'],
    'S1026': ['ELA301', 'MATH301'],
    'S1027': ['ELA301', 'MATH301', 'PEM301'],
    'S1028': ['ELA301', 'MATH301', 'PEM301'],
    'S1029': ['ELA301', 'SCI301', 'PEM301'],
    'S1030': ['ELA301', 'SCI301'],
    'S1031': ['ELA301', 'MATH301', 'SCI301'],
    'S1032': ['MATH301', 'SCI301', 'PEM301'],
    'S1033': ['ELA301', 'SCI301', 'PEM301'],
    'S1034': ['ELA301', 'MATH301'],
    # Roosevelt High School
    'S1035': ['MATH401', 'BIO401', 'PEH401'],
    'S1036': ['MATH401', 'ENG401', 'PEH401'],
    'S1037': ['MATH401', 'BIO401'],
    'S1038': ['MATH402', 'ENG401', 'PEH401'],
    'S1039': ['MATH402', 'ENG401'],
    'S1040': ['MATH402', 'BIO401', 'PEH401'],
    'S1041': ['HIST401', 'ENG401', 'PEH401'],
    'S1042': ['HIST401', 'ENG401', 'PEH401'],
    'S1043': ['HIST401', 'ENG401'],
    'S1044': ['HIST401', 'PEH401'],
    'S1045': ['ENG401', 'HIST401'],
    # Kennedy Elementary
    'S1046': ['ELA501', 'MATH501'],
    'S1047': ['ELA501', 'MATH501'],
    'S1048': ['ELA501', 'MATH501', 'SCI501'],
    'S1049': ['ELA501', 'MATH501', 'PEE501'],
    'S1050': ['ELA501', 'MATH501', 'SCI501'],
    'S1051': ['ELA501', 'MATH501', 'SCI501'],
    'S1052': ['ELA501', 'MATH501', 'SCI501', 'PEE501'],
    'S1053': ['MATH501', 'SCI501', 'PEE501'],
    'S1054': ['MATH501', 'SCI501', 'PEE501'],
    'S1055': ['MATH501', 'SCI501', 'PEE501'],
    'S1056': ['ELA501', 'MATH501', 'SCI501'],
    'S1057': ['MATH501', 'SCI501', 'PEE501'],
    # Madison Middle School
    'S1058': ['ELA601', 'MATH601', 'PEM601'],
    'S1059': ['ELA601', 'MATH601'],
    'S1060': ['ELA601', 'MATH601', 'PEM601'],
    'S1061': ['ELA601', 'MATH601'],
    'S1062': ['ELA601', 'SCI601', 'PEM601'],
    'S1063': ['ELA601', 'SCI601'],
    'S1064': ['ELA601', 'MATH601', 'SCI601'],
    'S1065': ['MATH601', 'SCI601', 'PEM601'],
    'S1066': ['ELA601', 'MATH601', 'PEM601'],
    'S1067': ['MATH601', 'SCI601', 'PEM601'],
    'S1068': ['ELA601', 'MATH601'],
    'S1069': ['MATH601', 'SCI601', 'PEM601'],
    # Adams High School
    'S1070': ['SCI701', 'ENG701'],
    'S1071': ['MATH701', 'SCI701'],
    'S1072': ['MATH701', 'ENG701', 'SCI701'],
    'S1073': ['MATH701', 'ENG701'],
    'S1074': ['ENG701', 'HIST701'],
    'S1075': ['HIST701', 'ENG701'],
    'S1076': ['ENG701', 'HIST701'],
    'S1077': ['ENG701', 'HIST701'],
    'S1078': ['ENG701', 'HIST701'],
    'S1079': ['MATH701', 'SCI701'],
    'S1080': ['MATH701', 'ENG701'],
    'S1081': ['ENG701', 'HIST701'],
    # Chavez Elementary
    'S1082': ['ELA801', 'MATH801'],
    'S1083': ['ELA801', 'MATH801'],
    'S1084': ['ELA801', 'MATH801', 'SCI801'],
    'S1085': ['ELA801', 'MATH801'],
    'S1086': ['ELA801', 'MATH801', 'SCI801'],
    'S1087': ['ELA801', 'MATH801', 'SCI801'],
    'S1088': ['ELA801', 'MATH801', 'PEE801'],
    'S1089': ['MATH801', 'SCI801', 'PEE801'],
    'S1090': ['MATH801', 'SCI801', 'PEE801'],
    'S1091': ['MATH801', 'SCI801', 'PEE801'],
    'S1092': ['ELA801', 'MATH801', 'SCI801'],
    'S1093': ['MATH801', 'SCI801', 'PEE801'],
    # Fremont K-8 Academy
    'S1094': ['ELA901', 'MATH901'],
    'S1095': ['ELA901', 'MATH901', 'SCI901'],
    'S1096': ['ELA901', 'MATH901', 'SCI901'],
    'S1097': ['ELA901', 'MATH901', 'SCI901'],
    'S1098': ['MATH901', 'SCI901', 'PEM901'],
    'S1099': ['MATH901', 'SCI901'],
    'S1100': ['MATH901', 'SCI901', 'PEM901'],
    'S1101': ['ELA901', 'MATH901', 'PEM901'],
    'S1102': ['ELA901', 'MATH901'],
    'S1103': ['MATH901', 'SCI901', 'PEM901'],
    'S1104': ['ELA901', 'MATH901', 'SCI901'],
    'S1105': ['MATH901', 'SCI901', 'PEM901'],
    # Additional grade 2 students
    'S1106': ['ELA101', 'MATH101', 'SCI101', 'PEE101'],
    'S1107': ['ELA201', 'MATH201', 'SCI201', 'PEE201'],
    'S1108': ['ELA801', 'MATH801', 'SCI801', 'PEE801'],
    # Additional grade 4 students
    'S1109': ['ELA501', 'MATH501', 'SCI501', 'PEE501'],
    'S1110': ['ELA101', 'MATH101', 'SCI101', 'PEE101'],
    'S1111': ['ELA201', 'MATH201', 'SCI201', 'PEE201'],
    # Additional grade 6 students
    'S1112': ['ELA501', 'MATH501', 'SCI501', 'PEE501'],
    'S1113': ['ELA801', 'MATH801', 'SCI801', 'PEE801'],
    'S1114': ['ELA901', 'MATH901', 'SCI901', 'PEM901'],
}

PARENTS = [
    # Lincoln Elementary
    dict(first_name='Rosa',      last_name='Ramirez',    relationship='Mother',   email='r.ramirez@email.com',    phone='(555) 200-0001', student_ids=['S1001', 'S1002']),
    dict(first_name='Daniel',    last_name='Kim',        relationship='Father',   email='d.kim@email.com',        phone='(555) 200-0002', student_ids=['S1004']),
    dict(first_name='Grace',     last_name='Johnson',    relationship='Mother',   email='g.johnson@email.com',    phone='(555) 200-0003', student_ids=['S1003', 'S1006']),
    dict(first_name='Miguel',    last_name='Mendoza',    relationship='Father',   email='m.mendoza@email.com',    phone='(555) 200-0004', student_ids=['S1005', 'S1008']),
    dict(first_name='Karen',     last_name='Davis',      relationship='Guardian', email='k.davis@email.com',      phone='(555) 200-0005', student_ids=['S1007', 'S1009']),
    dict(first_name='Andre',     last_name='Brown',      relationship='Father',   email='a.brown@email.com',      phone='(555) 200-0006', student_ids=['S1010']),
    dict(first_name='Sunita',    last_name='Sharma',     relationship='Mother',   email='s.sharma@email.com',     phone='(555) 200-0007', student_ids=['S1011']),
    dict(first_name='Carmen',    last_name='Herrera',    relationship='Mother',   email='c.herrera@email.com',    phone='(555) 200-0008', student_ids=['S1012']),
    # Washington Elementary
    dict(first_name='Patricia',  last_name='Nelson',     relationship='Mother',   email='p.nelson@email.com',     phone='(555) 200-0009', student_ids=['S1013']),
    dict(first_name='Wei',       last_name='Chen',       relationship='Father',   email='w.chen@email.com',       phone='(555) 200-0010', student_ids=['S1014']),
    dict(first_name='Ngozi',     last_name='Okafor',     relationship='Mother',   email='n.okafor@email.com',     phone='(555) 200-0011', student_ids=['S1015']),
    dict(first_name='Donna',     last_name='Wilson',     relationship='Mother',   email='d.wilson@email.com',     phone='(555) 200-0012', student_ids=['S1016', 'S1018']),
    dict(first_name='Pedro',     last_name='Cruz',       relationship='Father',   email='p.cruz@email.com',       phone='(555) 200-0013', student_ids=['S1017']),
    dict(first_name='Tanya',     last_name='Robinson',   relationship='Mother',   email='t.robinson@email.com',   phone='(555) 200-0014', student_ids=['S1019']),
    dict(first_name='Hoa',       last_name='Nguyen',     relationship='Father',   email='h.nguyen@email.com',     phone='(555) 200-0015', student_ids=['S1020']),
    dict(first_name='Steven',    last_name='Thompson',   relationship='Father',   email='s.thompson@email.com',   phone='(555) 200-0016', student_ids=['S1021']),
    dict(first_name='Renee',     last_name='Jackson',    relationship='Mother',   email='r.jackson@email.com',    phone='(555) 200-0017', student_ids=['S1022']),
    dict(first_name='Gloria',    last_name='Morales',    relationship='Guardian', email='g.morales@email.com',    phone='(555) 200-0018', student_ids=['S1023', 'S1024']),
    # Jefferson Middle School
    dict(first_name='Michael',   last_name='Lee',        relationship='Father',   email='mi.lee@email.com',       phone='(555) 200-0019', student_ids=['S1025']),
    dict(first_name='Denise',    last_name='Thompson',   relationship='Mother',   email='de.thompson@email.com',  phone='(555) 200-0020', student_ids=['S1026']),
    dict(first_name='Roberto',   last_name='Santos',     relationship='Father',   email='r.santos@email.com',     phone='(555) 200-0021', student_ids=['S1027', 'S1034']),
    dict(first_name='Linda',     last_name='Harris',     relationship='Mother',   email='l.harris@email.com',     phone='(555) 200-0022', student_ids=['S1028']),
    dict(first_name='Hiroshi',   last_name='Tanaka',     relationship='Father',   email='h.tanaka@email.com',     phone='(555) 200-0023', student_ids=['S1029']),
    dict(first_name='Joyce',     last_name='Williams',   relationship='Mother',   email='jo.williams@email.com',  phone='(555) 200-0024', student_ids=['S1030', 'S1033']),
    dict(first_name='Antonio',   last_name='Castro',     relationship='Father',   email='a.castro@email.com',     phone='(555) 200-0025', student_ids=['S1031']),
    dict(first_name='Beth',      last_name='Parker',     relationship='Mother',   email='b.parker@email.com',     phone='(555) 200-0026', student_ids=['S1032']),
    # Roosevelt High School
    dict(first_name='Sandra',    last_name='Mitchell',   relationship='Mother',   email='s.mitchell@email.com',   phone='(555) 200-0027', student_ids=['S1035']),
    dict(first_name='Kevin',     last_name='Evans',      relationship='Father',   email='k.evans@email.com',      phone='(555) 200-0028', student_ids=['S1036']),
    dict(first_name='Raj',       last_name='Patel',      relationship='Father',   email='ra.patel@email.com',     phone='(555) 200-0029', student_ids=['S1037']),
    dict(first_name='Valerie',   last_name='Turner',     relationship='Mother',   email='v.turner@email.com',     phone='(555) 200-0030', student_ids=['S1038']),
    dict(first_name='Luis',      last_name='Vasquez',    relationship='Father',   email='lu.vasquez@email.com',   phone='(555) 200-0031', student_ids=['S1039']),
    dict(first_name='Carol',     last_name='Wright',     relationship='Mother',   email='c.wright@email.com',     phone='(555) 200-0032', student_ids=['S1040']),
    dict(first_name='Tyrone',    last_name='Jenkins',    relationship='Guardian', email='ty.jenkins@email.com',   phone='(555) 200-0033', student_ids=['S1041']),
    dict(first_name='Grace',     last_name='Kim',        relationship='Mother',   email='gr.kim@email.com',       phone='(555) 200-0034', student_ids=['S1042']),
    dict(first_name='Jennifer',  last_name='Foster',     relationship='Mother',   email='j.foster@email.com',     phone='(555) 200-0035', student_ids=['S1043']),
    dict(first_name='Marcus',    last_name='Washington', relationship='Father',   email='ma.washington@email.com',phone='(555) 200-0036', student_ids=['S1044']),
    dict(first_name='Maria',     last_name='Reyes',      relationship='Mother',   email='ma.reyes@email.com',     phone='(555) 200-0037', student_ids=['S1045']),
    # Kennedy Elementary
    dict(first_name='Elena',     last_name='Gutierrez',  relationship='Mother',   email='el.gutierrez@email.com', phone='(555) 200-0038', student_ids=['S1046']),
    dict(first_name='Patricia',  last_name='Clark',      relationship='Mother',   email='pa.clark@email.com',     phone='(555) 200-0039', student_ids=['S1047']),
    dict(first_name='Fatou',     last_name='Hassan',     relationship='Mother',   email='fa.hassan@email.com',    phone='(555) 200-0040', student_ids=['S1048']),
    dict(first_name='James',     last_name='Chow',       relationship='Father',   email='ja.chow@email.com',      phone='(555) 200-0041', student_ids=['S1049']),
    dict(first_name='Lorenzo',   last_name='Rivera',     relationship='Father',   email='lo.rivera@email.com',    phone='(555) 200-0042', student_ids=['S1050']),
    dict(first_name='George',    last_name='Young',      relationship='Father',   email='ge.young@email.com',     phone='(555) 200-0043', student_ids=['S1051']),
    dict(first_name='Brenda',    last_name='Cooper',     relationship='Mother',   email='br.cooper@email.com',    phone='(555) 200-0044', student_ids=['S1052']),
    dict(first_name='Isabel',    last_name='Ruiz',       relationship='Mother',   email='is.ruiz@email.com',      phone='(555) 200-0045', student_ids=['S1053']),
    dict(first_name='Thanh',     last_name='Nguyen',     relationship='Mother',   email='th.nguyen@email.com',    phone='(555) 200-0046', student_ids=['S1054']),
    dict(first_name='Alexei',    last_name='Petrov',     relationship='Father',   email='al.petrov@email.com',    phone='(555) 200-0047', student_ids=['S1055']),
    dict(first_name='Donna',     last_name='Coleman',    relationship='Guardian', email='do.coleman@email.com',   phone='(555) 200-0048', student_ids=['S1056']),
    dict(first_name='Ana',       last_name='Santos',     relationship='Mother',   email='an.santos@email.com',    phone='(555) 200-0049', student_ids=['S1057']),
    # Madison Middle School
    dict(first_name='Christine', last_name='Harrison',   relationship='Mother',   email='ch.harrison@email.com',  phone='(555) 200-0050', student_ids=['S1058']),
    dict(first_name='Kofi',      last_name='Asante',     relationship='Father',   email='ko.asante@email.com',    phone='(555) 200-0051', student_ids=['S1059']),
    dict(first_name='Mei',       last_name='Chen',       relationship='Mother',   email='me.chen@email.com',      phone='(555) 200-0052', student_ids=['S1060']),
    dict(first_name='Rosa',      last_name='Navarro',    relationship='Mother',   email='ro.navarro@email.com',   phone='(555) 200-0053', student_ids=['S1061']),
    dict(first_name='Carl',      last_name='Hoffman',    relationship='Father',   email='ca.hoffman@email.com',   phone='(555) 200-0054', student_ids=['S1062']),
    dict(first_name='Shirley',   last_name='Bradley',    relationship='Mother',   email='sh.bradley@email.com',   phone='(555) 200-0055', student_ids=['S1063']),
    dict(first_name='Yasmine',   last_name='Khalil',     relationship='Mother',   email='ya.khalil@email.com',    phone='(555) 200-0056', student_ids=['S1064']),
    dict(first_name='Mark',      last_name='Price',      relationship='Father',   email='ma.price@email.com',     phone='(555) 200-0057', student_ids=['S1065']),
    dict(first_name='Carmen',    last_name='Fuentes',    relationship='Mother',   email='ca.fuentes@email.com',   phone='(555) 200-0058', student_ids=['S1066']),
    dict(first_name='Akira',     last_name='Iwata',      relationship='Father',   email='ak.iwata@email.com',     phone='(555) 200-0059', student_ids=['S1067']),
    dict(first_name='Renata',    last_name='Monroe',     relationship='Guardian', email='re.monroe@email.com',    phone='(555) 200-0060', student_ids=['S1068']),
    dict(first_name='Patrick',   last_name='McCann',     relationship='Father',   email='pa.mccann@email.com',    phone='(555) 200-0061', student_ids=['S1069']),
    # Adams High School
    dict(first_name='Diana',     last_name='Marquez',    relationship='Mother',   email='di.marquez@email.com',   phone='(555) 200-0062', student_ids=['S1070']),
    dict(first_name='Jeff',      last_name='Owens',      relationship='Father',   email='je.owens@email.com',     phone='(555) 200-0063', student_ids=['S1071']),
    dict(first_name='Yvonne',    last_name='Solomon',    relationship='Mother',   email='yv.solomon@email.com',   phone='(555) 200-0064', student_ids=['S1072']),
    dict(first_name='Ricardo',   last_name='Ferreira',   relationship='Father',   email='ri.ferreira@email.com',  phone='(555) 200-0065', student_ids=['S1073']),
    dict(first_name='Susan',     last_name='Reed',       relationship='Mother',   email='su.reed@email.com',      phone='(555) 200-0066', student_ids=['S1074']),
    dict(first_name='Victor',    last_name='Hawkins',    relationship='Father',   email='vi.hawkins@email.com',   phone='(555) 200-0067', student_ids=['S1075']),
    dict(first_name='Keiko',     last_name='Ishida',     relationship='Mother',   email='ke.ishida@email.com',    phone='(555) 200-0068', student_ids=['S1076']),
    dict(first_name='Terry',     last_name='Cole',       relationship='Father',   email='te.cole@email.com',      phone='(555) 200-0069', student_ids=['S1077']),
    dict(first_name='Luz',       last_name='Delgado',    relationship='Guardian', email='lu.delgado@email.com',   phone='(555) 200-0070', student_ids=['S1078']),
    dict(first_name='Brian',     last_name='Flynn',      relationship='Father',   email='br.flynn@email.com',     phone='(555) 200-0071', student_ids=['S1079']),
    dict(first_name='Claudette', last_name='Freeman',    relationship='Guardian', email='cl.freeman@email.com',   phone='(555) 200-0072', student_ids=['S1080']),
    dict(first_name='Thanh',     last_name='Tran',       relationship='Mother',   email='tn.tran@email.com',      phone='(555) 200-0073', student_ids=['S1081']),
    # Chavez Elementary
    dict(first_name='Gabriela',  last_name='Jimenez',    relationship='Mother',   email='ga.jimenez@email.com',   phone='(555) 200-0074', student_ids=['S1082']),
    dict(first_name='Darnell',   last_name='Brooks',     relationship='Father',   email='da.brooks@email.com',    phone='(555) 200-0075', student_ids=['S1083']),
    dict(first_name='Tomoko',    last_name='Yamamoto',   relationship='Mother',   email='to.yamamoto@email.com',  phone='(555) 200-0076', student_ids=['S1084']),
    dict(first_name='Maria',     last_name='Restrepo',   relationship='Mother',   email='ma.restrepo@email.com',  phone='(555) 200-0077', student_ids=['S1085']),
    dict(first_name='Eleanor',   last_name='Stone',      relationship='Mother',   email='el.stone@email.com',     phone='(555) 200-0078', student_ids=['S1086']),
    dict(first_name='David',     last_name='Hunt',       relationship='Father',   email='da.hunt@email.com',      phone='(555) 200-0079', student_ids=['S1087']),
    dict(first_name='Patricia',  last_name='DeLeon',     relationship='Mother',   email='pa.deleon@email.com',    phone='(555) 200-0080', student_ids=['S1088']),
    dict(first_name='Michael',   last_name='Walsh',      relationship='Father',   email='mi.walsh@email.com',     phone='(555) 200-0081', student_ids=['S1089']),
    dict(first_name='Ama',       last_name='Diallo',     relationship='Mother',   email='am.diallo@email.com',    phone='(555) 200-0082', student_ids=['S1090']),
    dict(first_name='Rosa',      last_name='Romero',     relationship='Mother',   email='ro.romero@email.com',    phone='(555) 200-0083', student_ids=['S1091']),
    dict(first_name='Denise',    last_name='Harris',     relationship='Guardian', email='de.harris@email.com',    phone='(555) 200-0084', student_ids=['S1092']),
    dict(first_name='Stefan',    last_name='Bergmann',   relationship='Father',   email='st.bergmann@email.com',  phone='(555) 200-0085', student_ids=['S1093']),
    # Fremont K-8 Academy
    dict(first_name='Zainab',    last_name='Ahmed',      relationship='Mother',   email='za.ahmed@email.com',     phone='(555) 200-0086', student_ids=['S1094']),
    dict(first_name='Sean',      last_name='OBrien',     relationship='Father',   email='se.obrien@email.com',    phone='(555) 200-0087', student_ids=['S1095']),
    dict(first_name='Lucia',     last_name='Esposito',   relationship='Mother',   email='lu.esposito@email.com',  phone='(555) 200-0088', student_ids=['S1096']),
    dict(first_name='Tyrone',    last_name='Jefferson',  relationship='Father',   email='ty.jefferson@email.com', phone='(555) 200-0089', student_ids=['S1097']),
    dict(first_name='Li',        last_name='Huang',      relationship='Mother',   email='li.huang@email.com',     phone='(555) 200-0090', student_ids=['S1098']),
    dict(first_name='Maria',     last_name='Salinas',    relationship='Mother',   email='ma.salinas@email.com',   phone='(555) 200-0091', student_ids=['S1099']),
    dict(first_name='Abena',     last_name='Osei',       relationship='Mother',   email='ab.osei@email.com',      phone='(555) 200-0092', student_ids=['S1100']),
    dict(first_name='Marco',     last_name='Marchetti',  relationship='Father',   email='ma.marchetti@email.com', phone='(555) 200-0093', student_ids=['S1101']),
    dict(first_name='Ngozi',     last_name='Bello',      relationship='Mother',   email='ng.bello@email.com',     phone='(555) 200-0094', student_ids=['S1102']),
    dict(first_name='Jose',      last_name='Vega',       relationship='Father',   email='jo.vega@email.com',      phone='(555) 200-0095', student_ids=['S1103']),
    dict(first_name='Yuki',      last_name='Kobayashi',  relationship='Mother',   email='yu.kobayashi@email.com', phone='(555) 200-0096', student_ids=['S1104']),
    dict(first_name='Erik',      last_name='Larsen',     relationship='Father',   email='er.larsen@email.com',    phone='(555) 200-0097', student_ids=['S1105']),
    # Additional grade 2/4/6 parents
    dict(first_name='Denise',    last_name='Williams',   relationship='Mother',   email='de.williams2@email.com', phone='(555) 200-0098', student_ids=['S1106']),
    dict(first_name='Antonio',   last_name='Reyes',      relationship='Father',   email='an.reyes2@email.com',    phone='(555) 200-0099', student_ids=['S1107']),
    dict(first_name='Patricia',  last_name='Greene',     relationship='Mother',   email='pa.greene@email.com',    phone='(555) 200-0100', student_ids=['S1108']),
    dict(first_name='Carmen',    last_name='Lopez',      relationship='Mother',   email='ca.lopez2@email.com',    phone='(555) 200-0101', student_ids=['S1109']),
    dict(first_name='Robert',    last_name='Patterson',  relationship='Father',   email='ro.patterson@email.com', phone='(555) 200-0102', student_ids=['S1110']),
    dict(first_name='Shirley',   last_name='Foster',     relationship='Mother',   email='sh.foster2@email.com',   phone='(555) 200-0103', student_ids=['S1111']),
    dict(first_name='Denise',    last_name='Simmons',    relationship='Mother',   email='de.simmons@email.com',   phone='(555) 200-0104', student_ids=['S1112']),
    dict(first_name='Jorge',     last_name='Ortega',     relationship='Father',   email='jo.ortega@email.com',    phone='(555) 200-0105', student_ids=['S1113']),
    dict(first_name='James',     last_name='Blackwell',  relationship='Father',   email='ja.blackwell@email.com', phone='(555) 200-0106', student_ids=['S1114']),
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Absence records  (ssid, grade, abs_desc, abs_abbr, bell_period, school_yr, site_code)
# ---------------------------------------------------------------------------

_UA  = ('Unexcused Absence',     'UA')
_EA  = ('Excused Absence',       'EA')
_UT  = ('Unexcused Tardy',       'UT')
_ET  = ('Excused Tardy',         'ET')
_MED = ('Medical Absence',       'MED')
_ISS = ('In-School Suspension',  'ISS')
_SS  = ('Suspension',            'SS')

def _abs(ssid, grade, atype, period, yr, site_code, d):
    return dict(ssid=ssid, grade=grade, abs_desc=atype[0], abs_abbr=atype[1],
                bell_period=period, school_yr=yr, site_code=site_code, abs_date=d)

ABSENCES = [
    # ── Lincoln Elementary 2025-2026 ────────────────────────────────────────
    _abs('1000000001','TK',_UA, '1st','2025-2026','LE001', date(2025, 9, 5)),
    _abs('1000000001','TK',_ET, '2nd','2025-2026','LE001', date(2025,10, 7)),
    _abs('1000000005','2', _EA, '1st','2025-2026','LE001', date(2025, 9,10)),
    _abs('1000000005','2', _MED,'2nd','2025-2026','LE001', date(2025,11, 3)),
    _abs('1000000005','2', _MED,'3rd','2025-2026','LE001', date(2025,11, 4)),
    _abs('1000000008','3', _UA, '2nd','2025-2026','LE001', date(2025,10,14)),
    _abs('1000000008','3', _UT, '1st','2025-2026','LE001', date(2026, 1,13)),
    _abs('1000000010','4', _EA, '3rd','2025-2026','LE001', date(2025,12, 2)),
    _abs('1000000010','4', _UA, '4th','2025-2026','LE001', date(2026, 2, 3)),
    _abs('1000000011','5', _MED,'1st','2025-2026','LE001', date(2025, 9,19)),
    _abs('1000000003','1', _ET, '2nd','2025-2026','LE001', date(2025,10,21)),
    _abs('1000000007','3', _UA, '1st','2025-2026','LE001', date(2026, 3, 4)),
    _abs('1000000012','6', _ISS,'2nd','2025-2026','LE001', date(2026, 1,27)),
    # ── Washington Elementary 2025-2026 ─────────────────────────────────────
    _abs('1000000014','KN', _UA, '1st','2025-2026','WE002', date(2025, 9, 8)),
    _abs('1000000017','2', _EA, '2nd','2025-2026','WE002', date(2025,10,20)),
    _abs('1000000017','2', _MED,'1st','2025-2026','WE002', date(2025,11,17)),
    _abs('1000000019','3', _UA, '3rd','2025-2026','WE002', date(2025, 9,15)),
    _abs('1000000019','3', _UT, '2nd','2025-2026','WE002', date(2025,10, 8)),
    _abs('1000000019','3', _UA, '1st','2025-2026','WE002', date(2025,11,10)),
    _abs('1000000022','4', _ISS,'4th','2025-2026','WE002', date(2026, 2,10)),
    _abs('1000000023','5', _EA, '2nd','2025-2026','WE002', date(2025,12, 9)),
    _abs('1000000023','5', _ET, '3rd','2025-2026','WE002', date(2026, 1, 6)),
    _abs('1000000024','6', _UA, '1st','2025-2026','WE002', date(2026, 3,10)),
    _abs('1000000020','3', _MED,'2nd','2025-2026','WE002', date(2025, 9,22)),
    _abs('1000000015','1', _UA, '1st','2025-2026','WE002', date(2025,10,28)),
    # ── Jefferson Middle School 2025-2026 ────────────────────────────────────
    _abs('1000000027','7', _UA, '2nd','2025-2026','JMS003', date(2025, 9,12)),
    _abs('1000000027','7', _UT, '4th','2025-2026','JMS003', date(2025,10,15)),
    _abs('1000000029','8', _EA, '1st','2025-2026','JMS003', date(2025,11, 5)),
    _abs('1000000029','8', _MED,'3rd','2025-2026','JMS003', date(2025,11, 6)),
    _abs('1000000030','8', _UA, '5th','2025-2026','JMS003', date(2025,12, 8)),
    _abs('1000000030','8', _ISS,'2nd','2025-2026','JMS003', date(2026, 1,20)),
    _abs('1000000032','8', _SS, '1st','2025-2026','JMS003', date(2025,10, 6)),
    _abs('1000000032','8', _SS, '2nd','2025-2026','JMS003', date(2025,10, 7)),
    _abs('1000000033','8', _UA, '3rd','2025-2026','JMS003', date(2026, 2,24)),
    _abs('1000000025','7', _ET, '1st','2025-2026','JMS003', date(2025, 9,17)),
    _abs('1000000028','7', _UA, '4th','2025-2026','JMS003', date(2026, 1,14)),
    _abs('1000000031','8', _EA, '6th','2025-2026','JMS003', date(2026, 3,18)),
    # ── Roosevelt High School 2025-2026 ─────────────────────────────────────
    _abs('1000000035','9', _UA, '1st','2025-2026','RHS004', date(2025, 9, 4)),
    _abs('1000000035','9', _UT, '3rd','2025-2026','RHS004', date(2025,10, 2)),
    _abs('1000000036','9', _EA, '2nd','2025-2026','RHS004', date(2025,11,13)),
    _abs('1000000038','10',_UA, '4th','2025-2026','RHS004', date(2025, 9,24)),
    _abs('1000000038','10',_MED,'5th','2025-2026','RHS004', date(2025,10,23)),
    _abs('1000000038','10',_MED,'6th','2025-2026','RHS004', date(2025,10,24)),
    _abs('1000000041','11',_ISS,'1st','2025-2026','RHS004', date(2025,12,10)),
    _abs('1000000041','11',_SS, '2nd','2025-2026','RHS004', date(2025,12,11)),
    _abs('1000000044','12',_UA, '7th','2025-2026','RHS004', date(2026, 2,17)),
    _abs('1000000044','12',_UA, '6th','2025-2026','RHS004', date(2026, 3,17)),
    _abs('1000000039','10',_EA, '3rd','2025-2026','RHS004', date(2025,11,18)),
    _abs('1000000042','11',_UT, '2nd','2025-2026','RHS004', date(2026, 1,21)),
    _abs('1000000045','12',_MED,'1st','2025-2026','RHS004', date(2025,10,30)),
    _abs('1000000037','9', _EA, '5th','2025-2026','RHS004', date(2026, 2, 5)),
    # ── Lincoln Elementary 2024-2025 ────────────────────────────────────────
    _abs('1000000001','TK',_UA, '1st','2024-2025','LE001', date(2024, 9, 6)),
    _abs('1000000005','1', _EA, '2nd','2024-2025','LE001', date(2024,10, 4)),
    _abs('1000000008','2', _MED,'1st','2024-2025','LE001', date(2024,11, 8)),
    _abs('1000000010','3', _UA, '3rd','2024-2025','LE001', date(2025, 1,10)),
    _abs('1000000010','3', _UT, '2nd','2024-2025','LE001', date(2025, 1,14)),
    # ── Washington Elementary 2024-2025 ─────────────────────────────────────
    _abs('1000000017','1', _UA, '1st','2024-2025','WE002', date(2024, 9,11)),
    _abs('1000000019','2', _EA, '2nd','2024-2025','WE002', date(2024,10,16)),
    _abs('1000000019','2', _UT, '3rd','2024-2025','WE002', date(2024,11,20)),
    _abs('1000000022','3', _ISS,'1st','2024-2025','WE002', date(2025, 2,12)),
    _abs('1000000023','4', _MED,'2nd','2024-2025','WE002', date(2024,10,22)),
    # ── Jefferson Middle School 2024-2025 ────────────────────────────────────
    _abs('1000000026','6', _UA, '2nd','2024-2025','JMS003', date(2024, 9,16)),
    _abs('1000000027','6', _EA, '1st','2024-2025','JMS003', date(2024,10,28)),
    _abs('1000000029','7', _UA, '3rd','2024-2025','JMS003', date(2024,11,12)),
    _abs('1000000030','7', _MED,'5th','2024-2025','JMS003', date(2025, 1,22)),
    _abs('1000000032','7', _SS, '2nd','2024-2025','JMS003', date(2024,10, 7)),
    # ── Roosevelt High School 2024-2025 ─────────────────────────────────────
    _abs('1000000035','8', _UA, '1st','2024-2025','RHS004', date(2024, 9,18)),
    _abs('1000000038','9', _EA, '4th','2024-2025','RHS004', date(2024,11, 4)),
    _abs('1000000041','10',_ISS,'2nd','2024-2025','RHS004', date(2025, 2, 3)),
    _abs('1000000044','11',_UA, '6th','2024-2025','RHS004', date(2024,10, 9)),
    _abs('1000000044','11',_UT, '3rd','2024-2025','RHS004', date(2024,11,13)),

    # ── CHRONIC ABSENTEEISM: student 1000000019 (WE002, grade 3) ── 20 total ──
    _abs('1000000019','3',_UA, '1st','2025-2026','WE002', date(2025,11,12)),
    _abs('1000000019','3',_UA, '2nd','2025-2026','WE002', date(2025,11,18)),
    _abs('1000000019','3',_MED,'3rd','2025-2026','WE002', date(2025,11,19)),
    _abs('1000000019','3',_EA, '1st','2025-2026','WE002', date(2025,12, 2)),
    _abs('1000000019','3',_EA, '2nd','2025-2026','WE002', date(2025,12, 3)),
    _abs('1000000019','3',_UA, '4th','2025-2026','WE002', date(2026, 1, 7)),
    _abs('1000000019','3',_UA, '1st','2025-2026','WE002', date(2026, 1, 8)),
    _abs('1000000019','3',_UT, '2nd','2025-2026','WE002', date(2026, 1,21)),
    _abs('1000000019','3',_MED,'1st','2025-2026','WE002', date(2026, 2, 4)),
    _abs('1000000019','3',_MED,'3rd','2025-2026','WE002', date(2026, 2, 5)),
    _abs('1000000019','3',_UA, '2nd','2025-2026','WE002', date(2026, 2,18)),
    _abs('1000000019','3',_UA, '1st','2025-2026','WE002', date(2026, 3, 4)),
    _abs('1000000019','3',_EA, '3rd','2025-2026','WE002', date(2026, 3,24)),
    _abs('1000000019','3',_UA, '2nd','2025-2026','WE002', date(2026, 4, 7)),
    _abs('1000000019','3',_UA, '4th','2025-2026','WE002', date(2026, 4,14)),
    _abs('1000000019','3',_UA, '1st','2025-2026','WE002', date(2026, 4,28)),
    _abs('1000000019','3',_UA, '2nd','2025-2026','WE002', date(2026, 5, 5)),

    # ── BORDERLINE: student 1000000030 (JMS003, grade 8) ── 14 total ──
    _abs('1000000030','8',_UA, '3rd','2025-2026','JMS003', date(2025,11,17)),
    _abs('1000000030','8',_EA, '1st','2025-2026','JMS003', date(2025,11,24)),
    _abs('1000000030','8',_UA, '2nd','2025-2026','JMS003', date(2025,12,15)),
    _abs('1000000030','8',_UA, '4th','2025-2026','JMS003', date(2026, 1, 6)),
    _abs('1000000030','8',_MED,'1st','2025-2026','JMS003', date(2026, 2, 3)),
    _abs('1000000030','8',_UA, '3rd','2025-2026','JMS003', date(2026, 2,23)),
    _abs('1000000030','8',_UT, '2nd','2025-2026','JMS003', date(2026, 3,16)),
    _abs('1000000030','8',_UA, '5th','2025-2026','JMS003', date(2026, 3,30)),
    _abs('1000000030','8',_UA, '1st','2025-2026','JMS003', date(2026, 4,13)),
    _abs('1000000030','8',_EA, '4th','2025-2026','JMS003', date(2026, 4,27)),
    _abs('1000000030','8',_UA, '2nd','2025-2026','JMS003', date(2026, 5, 4)),
    _abs('1000000030','8',_UA, '3rd','2025-2026','JMS003', date(2026, 5,11)),

    # ── Kennedy Elementary 2025-2026 ─────────────────────────────────────────
    _abs('1000000048','1', _UA, '1st','2025-2026','KE005', date(2025, 9, 9)),
    _abs('1000000050','2', _EA, '2nd','2025-2026','KE005', date(2025,10, 6)),
    _abs('1000000050','2', _MED,'1st','2025-2026','KE005', date(2025,10, 7)),
    _abs('1000000052','3', _UA, '3rd','2025-2026','KE005', date(2025,11, 4)),
    _abs('1000000052','3', _UT, '2nd','2025-2026','KE005', date(2026, 1,12)),
    _abs('1000000056','5', _EA, '1st','2025-2026','KE005', date(2025,12, 8)),
    _abs('1000000057','6', _UA, '4th','2025-2026','KE005', date(2026, 2, 9)),
    _abs('1000000048','1', _MED,'2nd','2025-2026','KE005', date(2026, 3,23)),
    _abs('1000000050','2', _UA, '1st','2025-2026','KE005', date(2026, 4,20)),
    _abs('1000000052','3', _UA, '3rd','2025-2026','KE005', date(2026, 5, 4)),

    # ── Madison Middle School 2025-2026 ──────────────────────────────────────
    _abs('1000000059','7', _UA, '1st','2025-2026','MMS006', date(2025, 9,16)),
    _abs('1000000061','7', _EA, '2nd','2025-2026','MMS006', date(2025,10,13)),
    _abs('1000000063','8', _UA, '3rd','2025-2026','MMS006', date(2025,11,10)),
    _abs('1000000063','8', _MED,'1st','2025-2026','MMS006', date(2025,11,11)),
    _abs('1000000064','8', _UA, '4th','2025-2026','MMS006', date(2025,12,16)),
    _abs('1000000064','8', _ISS,'2nd','2025-2026','MMS006', date(2026, 1,27)),
    _abs('1000000066','7', _UT, '1st','2025-2026','MMS006', date(2026, 2,10)),
    _abs('1000000059','7', _UA, '3rd','2025-2026','MMS006', date(2026, 3,17)),
    _abs('1000000063','8', _EA, '2nd','2025-2026','MMS006', date(2026, 4, 8)),
    _abs('1000000064','8', _UA, '1st','2025-2026','MMS006', date(2026, 5, 6)),

    # ── Adams High School 2025-2026 ───────────────────────────────────────────
    _abs('1000000070','9', _UA, '2nd','2025-2026','AHS007', date(2025, 9,22)),
    _abs('1000000072','10',_EA, '1st','2025-2026','AHS007', date(2025,10,20)),
    _abs('1000000072','10',_MED,'3rd','2025-2026','AHS007', date(2025,10,21)),
    _abs('1000000075','11',_UA, '4th','2025-2026','AHS007', date(2025,11,19)),
    _abs('1000000075','11',_ISS,'2nd','2025-2026','AHS007', date(2025,12, 3)),
    _abs('1000000078','12',_UA, '1st','2025-2026','AHS007', date(2026, 1,26)),
    _abs('1000000070','9', _UT, '5th','2025-2026','AHS007', date(2026, 2,23)),
    _abs('1000000072','10',_UA, '2nd','2025-2026','AHS007', date(2026, 3,30)),
    _abs('1000000075','11',_EA, '3rd','2025-2026','AHS007', date(2026, 4,20)),
    _abs('1000000078','12',_UA, '1st','2025-2026','AHS007', date(2026, 5, 4)),

    # ── Chavez Elementary 2025-2026 ───────────────────────────────────────────
    _abs('1000000085','1', _UA, '1st','2025-2026','CHE008', date(2025, 9,11)),
    _abs('1000000085','1', _MED,'2nd','2025-2026','CHE008', date(2025, 9,12)),
    _abs('1000000087','3', _UA, '3rd','2025-2026','CHE008', date(2025,10,27)),
    _abs('1000000091','5', _EA, '1st','2025-2026','CHE008', date(2025,11,24)),
    _abs('1000000092','5', _UA, '4th','2025-2026','CHE008', date(2025,12,10)),
    _abs('1000000083','KN', _ET, '2nd','2025-2026','CHE008', date(2026, 1,20)),
    _abs('1000000087','3', _UT, '1st','2025-2026','CHE008', date(2026, 2,17)),
    _abs('1000000085','1', _UA, '3rd','2025-2026','CHE008', date(2026, 3,23)),
    _abs('1000000091','5', _UA, '2nd','2025-2026','CHE008', date(2026, 4,14)),
    _abs('1000000087','3', _EA, '1st','2025-2026','CHE008', date(2026, 5, 5)),

    # ── Fremont K-8 Academy 2025-2026 ────────────────────────────────────────
    _abs('1000000094','KN', _UA, '1st','2025-2026','FKA009', date(2025, 9,18)),
    _abs('1000000097','3', _EA, '2nd','2025-2026','FKA009', date(2025,10,15)),
    _abs('1000000099','5', _UA, '1st','2025-2026','FKA009', date(2025,11,13)),
    _abs('1000000099','5', _MED,'3rd','2025-2026','FKA009', date(2025,11,14)),
    _abs('1000000102','7', _UA, '4th','2025-2026','FKA009', date(2025,12,17)),
    _abs('1000000102','7', _ISS,'2nd','2025-2026','FKA009', date(2026, 1,22)),
    _abs('1000000103','8', _UA, '1st','2025-2026','FKA009', date(2026, 2,19)),
    _abs('1000000097','3', _UT, '3rd','2025-2026','FKA009', date(2026, 3,26)),
    _abs('1000000094','KN', _UA, '2nd','2025-2026','FKA009', date(2026, 4,22)),
    _abs('1000000099','5', _EA, '1st','2025-2026','FKA009', date(2026, 5, 7)),

    # ── Lincoln Elementary 2023-2024 ────────────────────────────────────────
    _abs('1000000001','TK',_UA, '1st','2023-2024','LE001', date(2023, 9, 7)),
    _abs('1000000005','KN', _EA, '2nd','2023-2024','LE001', date(2023,10, 5)),
    _abs('1000000008','1', _MED,'1st','2023-2024','LE001', date(2023,11, 9)),
    _abs('1000000010','2', _UA, '3rd','2023-2024','LE001', date(2024, 1, 9)),
    _abs('1000000003','KN', _ET, '2nd','2023-2024','LE001', date(2023,10,16)),
    # ── Washington Elementary 2023-2024 ─────────────────────────────────────
    _abs('1000000017','1', _UA, '1st','2023-2024','WE002', date(2023, 9,12)),
    _abs('1000000019','1', _EA, '2nd','2023-2024','WE002', date(2023,10,17)),
    _abs('1000000022','2', _MED,'3rd','2023-2024','WE002', date(2023,11,21)),
    _abs('1000000023','3', _ISS,'1st','2023-2024','WE002', date(2024, 2,13)),
    # ── Jefferson Middle School 2023-2024 ────────────────────────────────────
    _abs('1000000026','5', _UA, '2nd','2023-2024','JMS003', date(2023, 9,13)),
    _abs('1000000027','5', _EA, '1st','2023-2024','JMS003', date(2023,10,24)),
    _abs('1000000029','6', _UA, '3rd','2023-2024','JMS003', date(2023,11,14)),
    _abs('1000000030','6', _MED,'5th','2023-2024','JMS003', date(2024, 1,23)),
    _abs('1000000032','6', _SS, '2nd','2023-2024','JMS003', date(2023,10, 8)),
    # ── Roosevelt High School 2023-2024 ─────────────────────────────────────
    _abs('1000000035','7', _UA, '1st','2023-2024','RHS004', date(2023, 9,19)),
    _abs('1000000038','8', _EA, '4th','2023-2024','RHS004', date(2023,11, 6)),
    _abs('1000000041','9', _ISS,'2nd','2023-2024','RHS004', date(2024, 2, 5)),
    _abs('1000000044','10',_UA, '6th','2023-2024','RHS004', date(2023,10,10)),
    # ── Kennedy Elementary 2023-2024 ─────────────────────────────────────────
    _abs('1000000048','TK',_UA, '1st','2023-2024','KE005', date(2023, 9,11)),
    _abs('1000000050','1', _EA, '2nd','2023-2024','KE005', date(2023,10, 9)),
    _abs('1000000052','2', _MED,'1st','2023-2024','KE005', date(2023,11, 7)),
    # ── Madison Middle School 2023-2024 ──────────────────────────────────────
    _abs('1000000059','6', _UA, '1st','2023-2024','MMS006', date(2023, 9,20)),
    _abs('1000000063','7', _MED,'3rd','2023-2024','MMS006', date(2023,11,15)),
    _abs('1000000064','7', _UA, '4th','2023-2024','MMS006', date(2023,12,13)),

    # ── Lincoln Elementary 2022-2023 ────────────────────────────────────────
    _abs('1000000001','TK',_UA, '1st','2022-2023','LE001', date(2022, 9, 8)),
    _abs('1000000005','TK',_EA, '2nd','2022-2023','LE001', date(2022,10, 6)),
    _abs('1000000008','TK',_MED,'1st','2022-2023','LE001', date(2022,11,10)),
    _abs('1000000010','1', _UA, '3rd','2022-2023','LE001', date(2023, 1,11)),
    # ── Washington Elementary 2022-2023 ─────────────────────────────────────
    _abs('1000000017','TK',_UA, '1st','2022-2023','WE002', date(2022, 9,14)),
    _abs('1000000019','TK',_EA, '2nd','2022-2023','WE002', date(2022,10,18)),
    _abs('1000000022','1', _MED,'3rd','2022-2023','WE002', date(2022,11,22)),
    # ── Jefferson Middle School 2022-2023 ────────────────────────────────────
    _abs('1000000026','4', _UA, '2nd','2022-2023','JMS003', date(2022, 9,14)),
    _abs('1000000027','4', _EA, '1st','2022-2023','JMS003', date(2022,10,25)),
    _abs('1000000030','5', _MED,'5th','2022-2023','JMS003', date(2023, 1,24)),
    _abs('1000000032','5', _SS, '2nd','2022-2023','JMS003', date(2022,10, 9)),
    # ── Roosevelt High School 2022-2023 ─────────────────────────────────────
    _abs('1000000035','6', _UA, '1st','2022-2023','RHS004', date(2022, 9,20)),
    _abs('1000000038','7', _EA, '4th','2022-2023','RHS004', date(2022,11, 7)),
    _abs('1000000041','8', _ISS,'2nd','2022-2023','RHS004', date(2023, 2, 6)),
    _abs('1000000044','9', _UA, '6th','2022-2023','RHS004', date(2022,10,11)),
    # ── Kennedy Elementary 2022-2023 ─────────────────────────────────────────
    _abs('1000000048','TK',_UA, '1st','2022-2023','KE005', date(2022, 9,12)),
    _abs('1000000052','1', _MED,'1st','2022-2023','KE005', date(2022,11, 8)),
    # ── Madison Middle School 2022-2023 ──────────────────────────────────────
    _abs('1000000059','5', _UA, '1st','2022-2023','MMS006', date(2022, 9,21)),
    _abs('1000000063','6', _MED,'3rd','2022-2023','MMS006', date(2022,11,16)),
]


# ---------------------------------------------------------------------------
# Grade seed data (MS + HS students only)
# ---------------------------------------------------------------------------
# Profiles: list of (term, letter, mark, type)
_GRADE_PROFILES = {
    'excellent':  [('Q1','A',96.0,'Quarter'),('Q2','A',94.0,'Quarter'),('Q3','A',97.0,'Quarter'),('S1','A',95.0,'Semester')],
    'good':       [('Q1','B',87.0,'Quarter'),('Q2','A',91.0,'Quarter'),('Q3','B',85.0,'Quarter'),('S1','B',88.0,'Semester')],
    'average':    [('Q1','C',75.0,'Quarter'),('Q2','B',83.0,'Quarter'),('Q3','C',74.0,'Quarter'),('S1','C',77.0,'Semester')],
    'struggling': [('Q1','D',65.0,'Quarter'),('Q2','C',72.0,'Quarter'),('Q3','D',63.0,'Quarter'),('S1','D',66.0,'Semester')],
    'atrisk':     [('Q1','D',62.0,'Quarter'),('Q2','F',48.0,'Quarter'),('Q3','F',44.0,'Quarter'),('S1','F',51.0,'Semester')],
}

_STUDENT_PROFILES = {
    # ── Grade 2 (existing) ───────────────────────────────────────────────────
    'S1005':'average',   'S1006':'struggling', 'S1017':'average',   'S1018':'good',
    'S1050':'good',      'S1086':'excellent',  'S1096':'average',
    # ── Grade 4 (existing) ───────────────────────────────────────────────────
    'S1009':'good',      'S1010':'average',    'S1021':'excellent', 'S1022':'good',
    'S1053':'average',   'S1054':'good',       'S1089':'excellent', 'S1090':'average',
    'S1098':'good',
    # ── Grade 6 (existing) ───────────────────────────────────────────────────
    'S1012':'good',      'S1024':'average',    'S1057':'struggling','S1093':'average',
    'S1100':'good',
    # ── Jefferson Middle School ──────────────────────────────────────────────
    'S1025':'good',      'S1026':'struggling', 'S1027':'average',   'S1028':'good',
    'S1029':'excellent', 'S1030':'atrisk',     'S1031':'average',   'S1032':'struggling',
    'S1033':'good',      'S1034':'struggling',
    # ── Roosevelt High School ────────────────────────────────────────────────
    'S1035':'good',      'S1036':'average',    'S1037':'good',      'S1038':'struggling',
    'S1039':'good',      'S1040':'excellent',  'S1041':'atrisk',    'S1042':'average',
    'S1043':'good',      'S1044':'atrisk',     'S1045':'struggling',
    # ── Madison Middle School ────────────────────────────────────────────────
    'S1058':'excellent', 'S1059':'good',       'S1060':'good',      'S1061':'average',
    'S1062':'good',      'S1063':'struggling', 'S1064':'average',   'S1065':'struggling',
    'S1066':'good',      'S1067':'average',    'S1068':'good',      'S1069':'average',
    # ── Adams High School ────────────────────────────────────────────────────
    'S1070':'average',   'S1071':'good',       'S1072':'good',      'S1073':'excellent',
    'S1074':'average',   'S1075':'atrisk',     'S1076':'good',      'S1077':'good',
    'S1078':'struggling','S1079':'average',    'S1080':'good',      'S1081':'excellent',
    # ── Fremont K-8 (grades 7-8) ─────────────────────────────────────────────
    'S1101':'good',      'S1102':'struggling', 'S1103':'average',   'S1104':'excellent',
    'S1105':'good',
    # ── New grade 2 students ─────────────────────────────────────────────────
    'S1106':'good',      'S1107':'excellent',  'S1108':'average',
    # ── New grade 4 students ─────────────────────────────────────────────────
    'S1109':'good',      'S1110':'atrisk',     'S1111':'excellent',
    # ── New grade 6 students ─────────────────────────────────────────────────
    'S1112':'average',   'S1113':'atrisk',     'S1114':'good',
}

_COURSE_TEACHER = {c['course_code']: c['teacher_emp'] for c in COURSES}
_COURSE_SITE    = {c['course_code']: c['site_code']   for c in COURSES}
_SITE_CDS = {
    'LE001':  _LE,  'WE002':  _WE,  'KE005':  _KE,  'CHE008': _CHE,
    'JMS003': _JMS, 'RHS004': _RHS, 'MMS006': _MMS,
    'AHS007': _AHS, 'FKA009': _FKA,
}

def _build_grades():
    rows = []
    for sid, profile_key in _STUDENT_PROFILES.items():
        profile  = _GRADE_PROFILES[profile_key]
        courses  = ENROLLMENTS.get(sid, [])
        curr_grade = profile[-1][1]
        for course_code in courses:
            site_code = _COURSE_SITE.get(course_code, '')
            schoolid  = _SITE_CDS.get(site_code, '')
            teacher   = _COURSE_TEACHER.get(course_code, '')
            for term, letter, mark, gtype in profile:
                passing   = letter not in ('D', 'F')
                credatt   = 5.0 if gtype == 'Semester' else 0.0
                credcomp  = credatt if passing else 0.0
                rows.append(dict(
                    grades_stuid     = sid,
                    grades_schoolid  = schoolid,
                    grades_coursenum = course_code,
                    grades_teacherid = teacher,
                    grades_courseyr  = '2025-2026',
                    grades_term      = term,
                    grades_grade     = letter,
                    grades_mark      = mark,
                    grades_type      = gtype,
                    grades_credatt   = credatt,
                    grades_credcomp  = credcomp,
                    grades_currgrade = curr_grade,
                ))
    return rows

GRADES = _build_grades()


ALL_STUDENT_FIELDS = (
    'first_name', 'middle_name', 'last_name', 'grade', 'gender', 'date_of_birth',
    'gradyr', 'ethnicity', 'frm_code', 'english_status', 'enter_date', 'exit_date',
    'disability', 'dwelling', 'migrant', 'schoolyr', 'foster', 'sed504',
    'ssid', 'cds_code', 'email',
)

with app.app_context():
    try:
        # --- Sites ---
        site_map = {}  # site_code → Site object
        for s in SITES:
            obj = Site.query.filter_by(site_code=s['site_code']).first()
            if obj:
                for k, v in s.items():
                    setattr(obj, k, v)
                print(f"  Site updated:  {s['site_name']}")
            else:
                obj = Site(**s)
                db.session.add(obj)
                db.session.flush()
                print(f"  Site added:    {s['site_name']}")
            site_map[s['site_code']] = obj
        db.session.flush()

        # --- Teachers ---
        teacher_map = {}  # employee_id → Teacher object
        for t in TEACHERS:
            t_data = {k: v for k, v in t.items() if k != 'site_code'}
            site_id = site_map[t['site_code']].id
            obj = Teacher.query.filter_by(employee_id=t['employee_id']).first()
            if obj:
                print(f"  Teacher exists: {t['last_name']}, {t['first_name']}")
            else:
                obj = Teacher(site_id=site_id, **t_data)
                db.session.add(obj)
                db.session.flush()
                print(f"  Teacher added:  {t['last_name']}, {t['first_name']}")
            teacher_map[t['employee_id']] = obj
        db.session.flush()

        # --- Students ---
        student_map = {}  # student_id → Student object
        for s in STUDENTS + STUDENTS_PY + STUDENTS_Y2 + STUDENTS_Y3:
            s_data = {k: v for k, v in s.items() if k != 'site_code'}
            site_id = site_map[s['site_code']].id
            obj = Student.query.filter_by(student_id=s['student_id']).first()
            if obj:
                for field in ALL_STUDENT_FIELDS:
                    if field in s_data:
                        setattr(obj, field, s_data[field])
                obj.site_id = site_id
                print(f"  Student updated: {s['last_name']}, {s['first_name']}")
            else:
                obj = Student(site_id=site_id, **s_data)
                db.session.add(obj)
                db.session.flush()
                print(f"  Student added:   {s['last_name']}, {s['first_name']}")
            student_map[s['student_id']] = obj
        db.session.flush()

        # --- Courses ---
        course_map = {}  # course_code → Course object
        for c in COURSES:
            teacher_emp = c['teacher_emp']
            site_id     = site_map[c['site_code']].id
            c_data = {k: v for k, v in c.items() if k not in ('teacher_emp', 'site_code')}
            obj = Course.query.filter_by(course_code=c['course_code']).first()
            if obj:
                obj.max_students = c_data.get('max_students')
                print(f"  Course exists:  {c['course_name']}")
            else:
                obj = Course(site_id=site_id, teacher_id=teacher_map[teacher_emp].id, **c_data)
                db.session.add(obj)
                db.session.flush()
                print(f"  Course added:   {c['course_name']}")
            course_map[c['course_code']] = obj
        db.session.flush()

        # --- Enrollments ---
        for sid, codes in ENROLLMENTS.items():
            student = student_map[sid]
            for code in codes:
                course = course_map[code]
                if student not in course.students:
                    course.students.append(student)
        db.session.flush()
        print(f"  Enrollments linked.")

        # --- Parents ---
        for p in PARENTS:
            linked_ids = p['student_ids']
            p_data = {k: v for k, v in p.items() if k != 'student_ids'}
            obj = Parent.query.filter_by(
                first_name=p['first_name'], last_name=p['last_name']
            ).first()
            if obj:
                print(f"  Parent exists:  {p['last_name']}, {p['first_name']}")
            else:
                obj = Parent(**p_data)
                obj.students = [student_map[sid] for sid in linked_ids if sid in student_map]
                db.session.add(obj)
                print(f"  Parent added:   {p['last_name']}, {p['first_name']}")

        # --- Incidents ---
        Incident.query.delete()
        INCIDENTS = [
            # ── Lincoln Elementary ──────────────────────────────────────────
            dict(sisid='1000000008', site='LE001', cds_code='19647330100001', incident_id='INC-2026-001', incident_date=date(2025,  9, 15), schoolyr='2025-2026', incident_time='09:30', day_of_week='Monday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000010', site='LE001', cds_code='19647330100001', incident_id='INC-2026-002', incident_date=date(2025, 10,  7), schoolyr='2025-2026', incident_time='11:15', day_of_week='Tuesday',   major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000006', site='LE001', cds_code='19647330100001', incident_id='INC-2026-003', incident_date=date(2025, 11, 20), schoolyr='2025-2026', incident_time='13:00', day_of_week='Thursday',  major=None,                    minor='Dress Code',           suspended_days=None),
            # ── Washington Elementary ────────────────────────────────────────
            dict(sisid='1000000019', site='WE002', cds_code='19647330100002', incident_id='INC-2026-004', incident_date=date(2025,  9, 22), schoolyr='2025-2026', incident_time='08:45', day_of_week='Monday',    major=None,                    minor='Disrespect',           suspended_days=None),
            dict(sisid='1000000022', site='WE002', cds_code='19647330100002', incident_id='INC-2026-005', incident_date=date(2025, 10, 14), schoolyr='2025-2026', incident_time='10:30', day_of_week='Tuesday',   major='Vandalism',             minor=None,                   suspended_days=1.0),
            dict(sisid='1000000017', site='WE002', cds_code='19647330100002', incident_id='INC-2026-006', incident_date=date(2026,  1,  8), schoolyr='2025-2026', incident_time='12:00', day_of_week='Thursday',  major=None,                    minor='Cell Phone',           suspended_days=None),
            # ── Jefferson Middle School ──────────────────────────────────────
            dict(sisid='1000000026', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-007', incident_date=date(2025,  9, 10), schoolyr='2025-2026', incident_time='07:55', day_of_week='Wednesday', major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000034', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-008', incident_date=date(2025, 10,  2), schoolyr='2025-2026', incident_time='14:10', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=3.0),
            dict(sisid='1000000030', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-009', incident_date=date(2025, 11,  6), schoolyr='2025-2026', incident_time='09:20', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000032', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-010', incident_date=date(2026,  2, 11), schoolyr='2025-2026', incident_time='11:45', day_of_week='Wednesday', major='Harassment',            minor=None,                   suspended_days=2.0),
            dict(sisid='1000000033', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-011', incident_date=date(2026,  3, 18), schoolyr='2025-2026', incident_time='13:30', day_of_week='Wednesday', major=None,                    minor='Profanity',            suspended_days=None),
            # ── Roosevelt High School ────────────────────────────────────────
            dict(sisid='1000000036', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-012', incident_date=date(2025,  9, 17), schoolyr='2025-2026', incident_time='08:10', day_of_week='Wednesday', major=None,                    minor='Cell Phone',           suspended_days=None),
            dict(sisid='1000000041', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-013', incident_date=date(2025, 10, 23), schoolyr='2025-2026', incident_time='10:00', day_of_week='Thursday',  major='Drug/Alcohol',          minor=None,                   suspended_days=5.0),
            dict(sisid='1000000044', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-014', incident_date=date(2025, 11, 13), schoolyr='2025-2026', incident_time='12:30', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=3.0),
            dict(sisid='1000000038', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-015', incident_date=date(2026,  1, 22), schoolyr='2025-2026', incident_time='14:45', day_of_week='Thursday',  major=None,                    minor='Disrespect',           suspended_days=None),
            dict(sisid='1000000045', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-016', incident_date=date(2026,  2, 26), schoolyr='2025-2026', incident_time='09:00', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000039', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-017', incident_date=date(2026,  4,  2), schoolyr='2025-2026', incident_time='11:20', day_of_week='Thursday',  major='Theft',                 minor=None,                   suspended_days=2.0),
            # ── Kennedy Elementary ───────────────────────────────────────────
            dict(sisid='1000000052', site='KE005',  cds_code='19647330100005', incident_id='INC-2026-018', incident_date=date(2025, 10,  9), schoolyr='2025-2026', incident_time='10:15', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000057', site='KE005',  cds_code='19647330100005', incident_id='INC-2026-019', incident_date=date(2026,  1, 14), schoolyr='2025-2026', incident_time='13:00', day_of_week='Wednesday', major='Vandalism',             minor=None,                   suspended_days=1.0),
            # ── Madison Middle School ────────────────────────────────────────
            dict(sisid='1000000061', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-020', incident_date=date(2025,  9, 29), schoolyr='2025-2026', incident_time='08:00', day_of_week='Monday',    major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000063', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-021', incident_date=date(2025, 11,  4), schoolyr='2025-2026', incident_time='09:50', day_of_week='Tuesday',   major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000064', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-022', incident_date=date(2026,  2,  5), schoolyr='2025-2026', incident_time='12:15', day_of_week='Thursday',  major=None,                    minor='Profanity',            suspended_days=None),
            dict(sisid='1000000065', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-023', incident_date=date(2026,  3, 10), schoolyr='2025-2026', incident_time='11:30', day_of_week='Tuesday',   major='Harassment',            minor=None,                   suspended_days=3.0),
            # ── Adams High School ────────────────────────────────────────────
            dict(sisid='1000000070', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-024', incident_date=date(2025, 10, 16), schoolyr='2025-2026', incident_time='07:45', day_of_week='Thursday',  major=None,                    minor='Cell Phone',           suspended_days=None),
            dict(sisid='1000000075', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-025', incident_date=date(2025, 11, 19), schoolyr='2025-2026', incident_time='10:30', day_of_week='Wednesday', major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000078', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-026', incident_date=date(2026,  2, 19), schoolyr='2025-2026', incident_time='13:45', day_of_week='Thursday',  major='Drug/Alcohol',          minor=None,                   suspended_days=5.0),
            dict(sisid='1000000072', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-027', incident_date=date(2026,  4, 15), schoolyr='2025-2026', incident_time='09:10', day_of_week='Wednesday', major=None,                    minor='Disrespect',           suspended_days=None),
            # ── Chavez Elementary ────────────────────────────────────────────
            dict(sisid='1000000087', site='CHE008', cds_code='19647330100008', incident_id='INC-2026-028', incident_date=date(2025,  9, 25), schoolyr='2025-2026', incident_time='10:00', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000091', site='CHE008', cds_code='19647330100008', incident_id='INC-2026-029', incident_date=date(2026,  1, 29), schoolyr='2025-2026', incident_time='14:00', day_of_week='Thursday',  major='Vandalism',             minor=None,                   suspended_days=1.0),
            # ── Fremont K-8 Academy ──────────────────────────────────────────
            dict(sisid='1000000099', site='FKA009', cds_code='19647330100009', incident_id='INC-2026-030', incident_date=date(2025, 10, 28), schoolyr='2025-2026', incident_time='11:00', day_of_week='Tuesday',   major=None,                    minor='Dress Code',           suspended_days=None),
            dict(sisid='1000000103', site='FKA009', cds_code='19647330100009', incident_id='INC-2026-031', incident_date=date(2026,  3,  4), schoolyr='2025-2026', incident_time='08:30', day_of_week='Wednesday', major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000102', site='FKA009', cds_code='19647330100009', incident_id='INC-2026-032', incident_date=date(2026,  4, 23), schoolyr='2025-2026', incident_time='12:45', day_of_week='Thursday',  major=None,                    minor='Profanity',            suspended_days=None),
            # ── Additional records for chart/table coverage ───────────────────
            # More monthly spread (Sep–May all months visible)
            dict(sisid='1000000026', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-033', incident_date=date(2025,  9,  3), schoolyr='2025-2026', incident_time='08:30', day_of_week='Wednesday', major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000041', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-034', incident_date=date(2026,  4,  9), schoolyr='2025-2026', incident_time='11:00', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000075', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-035', incident_date=date(2026,  5,  7), schoolyr='2025-2026', incident_time='10:15', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000064', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-036', incident_date=date(2026,  5, 13), schoolyr='2025-2026', incident_time='13:45', day_of_week='Wednesday', major=None,                    minor='Cell Phone',           suspended_days=None),
            # More Monday and Friday coverage for day-of-week chart
            dict(sisid='1000000052', site='KE005',  cds_code='19647330100005', incident_id='INC-2026-037', incident_date=date(2025, 10,  3), schoolyr='2025-2026', incident_time='09:00', day_of_week='Friday',    major=None,                    minor='Dress Code',           suspended_days=None),
            dict(sisid='1000000036', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-038', incident_date=date(2025, 11, 21), schoolyr='2025-2026', incident_time='14:30', day_of_week='Friday',    major='Theft',                 minor=None,                   suspended_days=1.0),
            dict(sisid='1000000087', site='CHE008', cds_code='19647330100008', incident_id='INC-2026-039', incident_date=date(2025, 12,  1), schoolyr='2025-2026', incident_time='08:15', day_of_week='Monday',    major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000097', site='FKA009', cds_code='19647330100009', incident_id='INC-2026-040', incident_date=date(2026,  1, 26), schoolyr='2025-2026', incident_time='10:45', day_of_week='Monday',    major='Vandalism',             minor=None,                   suspended_days=1.0),
            dict(sisid='1000000059', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-041', incident_date=date(2026,  3,  6), schoolyr='2025-2026', incident_time='11:15', day_of_week='Friday',    major=None,                    minor='Disrespect',           suspended_days=None),
            dict(sisid='1000000010', site='LE001',  cds_code='19647330100001', incident_id='INC-2026-042', incident_date=date(2026,  4, 24), schoolyr='2025-2026', incident_time='09:30', day_of_week='Friday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            # Additional infraction variety for Top Infractions chart
            dict(sisid='1000000044', site='RHS004', cds_code='19647330100004', incident_id='INC-2026-043', incident_date=date(2026,  2,  2), schoolyr='2025-2026', incident_time='12:00', day_of_week='Monday',    major='Harassment',            minor=None,                   suspended_days=2.0),
            dict(sisid='1000000030', site='JMS003', cds_code='19647330100003', incident_id='INC-2026-044', incident_date=date(2026,  3, 25), schoolyr='2025-2026', incident_time='09:45', day_of_week='Wednesday', major=None,                    minor='Profanity',            suspended_days=None),
            dict(sisid='1000000072', site='AHS007', cds_code='19647330100007', incident_id='INC-2026-045', incident_date=date(2026,  4,  1), schoolyr='2025-2026', incident_time='14:00', day_of_week='Wednesday', major=None,                    minor='Dress Code',           suspended_days=None),
            dict(sisid='1000000008', site='LE001',  cds_code='19647330100001', incident_id='INC-2026-046', incident_date=date(2025, 12, 15), schoolyr='2025-2026', incident_time='11:30', day_of_week='Monday',    major='Physical Aggression',   minor=None,                   suspended_days=3.0),
            dict(sisid='1000000063', site='MMS006', cds_code='19647330100006', incident_id='INC-2026-047', incident_date=date(2026,  1, 15), schoolyr='2025-2026', incident_time='13:15', day_of_week='Thursday',  major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000047', site='KE005',  cds_code='19647330100005', incident_id='INC-2026-048', incident_date=date(2026,  2, 24), schoolyr='2025-2026', incident_time='08:45', day_of_week='Tuesday',   major=None,                    minor='Disrespect',           suspended_days=None),

            # ── 2023-2024 Incidents ──────────────────────────────────────────
            dict(sisid='1000000008', site='LE001',  cds_code='19647330100001', incident_id='INC-2024-001', incident_date=date(2023,  9, 14), schoolyr='2023-2024', incident_time='09:30', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000010', site='LE001',  cds_code='19647330100001', incident_id='INC-2024-002', incident_date=date(2023, 10,  5), schoolyr='2023-2024', incident_time='11:15', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000019', site='WE002',  cds_code='19647330100002', incident_id='INC-2024-003', incident_date=date(2023,  9, 21), schoolyr='2023-2024', incident_time='08:45', day_of_week='Thursday',  major=None,                    minor='Disrespect',           suspended_days=None),
            dict(sisid='1000000022', site='WE002',  cds_code='19647330100002', incident_id='INC-2024-004', incident_date=date(2023, 10, 12), schoolyr='2023-2024', incident_time='10:30', day_of_week='Thursday',  major='Vandalism',             minor=None,                   suspended_days=1.0),
            dict(sisid='1000000026', site='JMS003', cds_code='19647330100003', incident_id='INC-2024-005', incident_date=date(2023,  9,  9), schoolyr='2023-2024', incident_time='07:55', day_of_week='Saturday',  major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000032', site='JMS003', cds_code='19647330100003', incident_id='INC-2024-006', incident_date=date(2023, 11,  7), schoolyr='2023-2024', incident_time='11:45', day_of_week='Tuesday',   major='Harassment',            minor=None,                   suspended_days=2.0),
            dict(sisid='1000000036', site='RHS004', cds_code='19647330100004', incident_id='INC-2024-007', incident_date=date(2023,  9, 15), schoolyr='2023-2024', incident_time='08:10', day_of_week='Friday',    major=None,                    minor='Cell Phone',           suspended_days=None),
            dict(sisid='1000000041', site='RHS004', cds_code='19647330100004', incident_id='INC-2024-008', incident_date=date(2023, 10, 20), schoolyr='2023-2024', incident_time='10:00', day_of_week='Friday',    major='Drug/Alcohol',          minor=None,                   suspended_days=5.0),
            dict(sisid='1000000044', site='RHS004', cds_code='19647330100004', incident_id='INC-2024-009', incident_date=date(2024,  1, 17), schoolyr='2023-2024', incident_time='12:30', day_of_week='Wednesday', major='Physical Aggression',   minor=None,                   suspended_days=3.0),
            dict(sisid='1000000052', site='KE005',  cds_code='19647330100005', incident_id='INC-2024-010', incident_date=date(2023, 10,  8), schoolyr='2023-2024', incident_time='10:15', day_of_week='Monday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000063', site='MMS006', cds_code='19647330100006', incident_id='INC-2024-011', incident_date=date(2023, 11,  2), schoolyr='2023-2024', incident_time='09:50', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000075', site='AHS007', cds_code='19647330100007', incident_id='INC-2024-012', incident_date=date(2023, 11, 16), schoolyr='2023-2024', incident_time='10:30', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000087', site='CHE008', cds_code='19647330100008', incident_id='INC-2024-013', incident_date=date(2023,  9, 24), schoolyr='2023-2024', incident_time='10:00', day_of_week='Monday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000099', site='FKA009', cds_code='19647330100009', incident_id='INC-2024-014', incident_date=date(2023, 10, 27), schoolyr='2023-2024', incident_time='11:00', day_of_week='Friday',    major=None,                    minor='Dress Code',           suspended_days=None),
            dict(sisid='1000000103', site='FKA009', cds_code='19647330100009', incident_id='INC-2024-015', incident_date=date(2024,  3,  1), schoolyr='2023-2024', incident_time='08:30', day_of_week='Friday',    major='Physical Aggression',   minor=None,                   suspended_days=2.0),

            # ── 2022-2023 Incidents ──────────────────────────────────────────
            dict(sisid='1000000008', site='LE001',  cds_code='19647330100001', incident_id='INC-2023-001', incident_date=date(2022,  9, 15), schoolyr='2022-2023', incident_time='09:30', day_of_week='Thursday',  major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000019', site='WE002',  cds_code='19647330100002', incident_id='INC-2023-002', incident_date=date(2022,  9, 22), schoolyr='2022-2023', incident_time='08:45', day_of_week='Thursday',  major=None,                    minor='Disrespect',           suspended_days=None),
            dict(sisid='1000000022', site='WE002',  cds_code='19647330100002', incident_id='INC-2023-003', incident_date=date(2022, 10, 13), schoolyr='2022-2023', incident_time='10:30', day_of_week='Thursday',  major='Vandalism',             minor=None,                   suspended_days=1.0),
            dict(sisid='1000000026', site='JMS003', cds_code='19647330100003', incident_id='INC-2023-004', incident_date=date(2022,  9, 10), schoolyr='2022-2023', incident_time='07:55', day_of_week='Saturday',  major=None,                    minor='Tardiness',            suspended_days=None),
            dict(sisid='1000000034', site='JMS003', cds_code='19647330100003', incident_id='INC-2023-005', incident_date=date(2022, 10,  3), schoolyr='2022-2023', incident_time='14:10', day_of_week='Monday',    major='Physical Aggression',   minor=None,                   suspended_days=3.0),
            dict(sisid='1000000036', site='RHS004', cds_code='19647330100004', incident_id='INC-2023-006', incident_date=date(2022,  9, 16), schoolyr='2022-2023', incident_time='08:10', day_of_week='Friday',    major=None,                    minor='Cell Phone',           suspended_days=None),
            dict(sisid='1000000041', site='RHS004', cds_code='19647330100004', incident_id='INC-2023-007', incident_date=date(2022, 10, 21), schoolyr='2022-2023', incident_time='10:00', day_of_week='Friday',    major='Drug/Alcohol',          minor=None,                   suspended_days=5.0),
            dict(sisid='1000000052', site='KE005',  cds_code='19647330100005', incident_id='INC-2023-008', incident_date=date(2022, 10,  9), schoolyr='2022-2023', incident_time='10:15', day_of_week='Monday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000063', site='MMS006', cds_code='19647330100006', incident_id='INC-2023-009', incident_date=date(2022, 11,  3), schoolyr='2022-2023', incident_time='09:50', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000075', site='AHS007', cds_code='19647330100007', incident_id='INC-2023-010', incident_date=date(2022, 11, 17), schoolyr='2022-2023', incident_time='10:30', day_of_week='Thursday',  major='Physical Aggression',   minor=None,                   suspended_days=2.0),
            dict(sisid='1000000087', site='CHE008', cds_code='19647330100008', incident_id='INC-2023-011', incident_date=date(2022,  9, 26), schoolyr='2022-2023', incident_time='10:00', day_of_week='Monday',    major=None,                    minor='Disruptive Behavior',  suspended_days=None),
            dict(sisid='1000000099', site='FKA009', cds_code='19647330100009', incident_id='INC-2023-012', incident_date=date(2022, 10, 28), schoolyr='2022-2023', incident_time='11:00', day_of_week='Friday',    major=None,                    minor='Dress Code',           suspended_days=None),
        ]
        for inc in INCIDENTS:
            db.session.add(Incident(**inc))
        db.session.flush()
        print(f"  Incidents added: {len(INCIDENTS)}")

        # --- Absences --- (always re-seed to pick up schema changes)
        Absence.query.delete()
        if True:
            for a in ABSENCES:
                site_id = site_map[a['site_code']].id
                a_data  = {k: v for k, v in a.items() if k not in ('site_code', 'abs_abbr')}
                db.session.add(Absence(site_id=site_id, **a_data))
            db.session.flush()
            print(f"  Absences added:  {len(ABSENCES)}")
        else:
            print(f"  Absences exist:  skipped")

        # --- Grades ---
        Grade.query.delete()
        for g in GRADES:
            db.session.add(Grade(**g))
        db.session.flush()
        print(f"  Grades added:    {len(GRADES)}")

        # --- Graduation Requirements ---
        for r in GRADUATION_REQUIREMENTS:
            obj = GraduationRequirement.query.filter_by(subject_name=r['subject_name']).first()
            if obj:
                print(f"  Grad requirement exists: {r['subject_name']}")
            else:
                db.session.add(GraduationRequirement(**r))
                print(f"  Grad requirement added:  {r['subject_name']}")
        db.session.flush()

        db.session.commit()
        print("\nAcademic data seeded successfully.")
        n_students = len(STUDENTS) + len(STUDENTS_PY) + len(STUDENTS_Y2) + len(STUDENTS_Y3)
        print(f"  {len(SITES)} sites | {len(TEACHERS)} teachers | {n_students} students | {len(COURSES)} courses | {len(PARENTS)} parents | {len(ABSENCES)} absences | {len(GRADES)} grades | {len(GRADUATION_REQUIREMENTS)} graduation requirements")

    except SQLAlchemyError as err:
        db.session.rollback()
        print(f"SQLAlchemy Error: {err}")
    except Exception as err:
        db.session.rollback()
        print(f"Error: {err}")
        raise
