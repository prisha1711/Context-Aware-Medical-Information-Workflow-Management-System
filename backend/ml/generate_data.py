"""
ml/generate_data.py
────────────────────────────────────────────────────────────────────────────
Synthetic data generator for the hospital prototype.

Generates:
  - 7 departments
  - ~40 staff members across all roles
  - 7 system user accounts (one per role) + one patient user per patient
  - 500 patients with RFID tags
  - Radiology records  (1–6 per patient, ~60% of patients)
  - Dental records     (1–5 per patient, ~65% of patients)
  - Blood test records (1–6 per patient, ~70% of patients, CBC panel only for ML)
  - Workflow events that follow the correct chronological sequence
  - ML labels derived from label_rules.py (NOT random)

Run from the backend/ directory:
    python -m ml.generate_data

Or directly:
    python ml/generate_data.py

The script is idempotent if the DB is deleted first. It does NOT check for
existing data — run it on a fresh database only.
────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import random
from datetime import date, datetime, timedelta

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from faker import Faker

from app.config import settings
from app.database import SessionLocal, create_all_tables
from app.models.department import Department
from app.models.patient import Patient
from app.models.staff import Staff
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.models.radiology import RadiologyRecord, SCAN_TYPES, BODY_PARTS, INDICATIONS, PRIORITIES as RAD_PRIORITIES
from app.models.dental import DentalRecord, PROCEDURE_TYPES, TOOTH_TYPES, TOOTH_QUADRANTS, DIAGNOSES, MATERIALS
from app.models.blood_test import BloodTestRecord, BloodTestResult, PANEL_ANALYTE_COUNTS
from app.models.ml_prediction import MLPrediction
from app.services.auth_service import hash_password
from ml.label_rules import derive_radiology_label, derive_dental_label, derive_blood_test_label

fake = Faker("en_IN")  # Indian locale for realistic names and addresses
Faker.seed(2024)
random.seed(2024)
np.random.seed(2024)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
N_PATIENTS = 500
START_DATE = datetime(2022, 1, 1)
END_DATE   = datetime(2026, 9, 30)

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]

# CBC analyte reference ranges by gender
CBC_ANALYTES = {
    "hemoglobin":      {"unit": "g/dL",       "M": (13.5, 17.5), "F": (12.0, 16.0)},
    "wbc_count":       {"unit": "x10^3/uL",   "M": (4.5, 11.0),  "F": (4.5, 11.0)},
    "rbc_count":       {"unit": "x10^6/uL",   "M": (4.7, 6.1),   "F": (4.2, 5.4)},
    "platelet_count":  {"unit": "x10^3/uL",   "M": (150, 400),   "F": (150, 400)},
    "hematocrit":      {"unit": "%",           "M": (42.0, 52.0), "F": (37.0, 47.0)},
    "mcv":             {"unit": "fL",          "M": (80.0, 100.0),"F": (80.0, 100.0)},
    "mchc":            {"unit": "g/dL",        "M": (32.0, 36.0), "F": (32.0, 36.0)},
    "neutrophils_pct": {"unit": "%",           "M": (50.0, 70.0), "F": (50.0, 70.0)},
    "lymphocytes_pct": {"unit": "%",           "M": (20.0, 40.0), "F": (20.0, 40.0)},
}


def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def rand_date_after(after: datetime, max_days: int = 120) -> datetime:
    return after + timedelta(hours=random.randint(1, max_days * 24))


def patient_age(dob: date, at: datetime) -> int:
    return (at.date() - dob).days // 365


# ─────────────────────────────────────────────────────────────────────────────
# 1. Departments
# ─────────────────────────────────────────────────────────────────────────────
DEPT_DATA = [
    {"name": "Radiology",         "location": "Block A, Ground Floor"},
    {"name": "Dental",            "location": "Block B, First Floor"},
    {"name": "Blood Laboratory",  "location": "Block A, Basement"},
    {"name": "General Medicine",  "location": "Block C, Ground Floor"},
    {"name": "Emergency",         "location": "Main Building, Ground Floor"},
    {"name": "Outpatient",        "location": "Block D, Ground Floor"},
    {"name": "Administration",    "location": "Main Building, First Floor"},
]


def seed_departments(db) -> dict[str, Department]:
    depts = {}
    for d in DEPT_DATA:
        dept = Department(name=d["name"], location=d["location"])
        db.add(dept)
    db.flush()
    for dept in db.query(Department).all():
        depts[dept.name] = dept
    return depts


# ─────────────────────────────────────────────────────────────────────────────
# 2. Staff
# ─────────────────────────────────────────────────────────────────────────────
STAFF_SPEC = [
    # (role, department_name, count, specialization)
    ("doctor",       "General Medicine", 6,  "General Medicine"),
    ("doctor",       "Outpatient",       4,  "Internal Medicine"),
    ("nurse",        "General Medicine", 6,  None),
    ("nurse",        "Emergency",        4,  None),
    ("radiologist",  "Radiology",        4,  "Diagnostic Radiology"),
    ("dentist",      "Dental",           4,  "General Dentistry"),
    ("lab_tech",     "Blood Laboratory", 4,  "Clinical Pathology"),
    ("admin",        "Administration",   2,  None),
]


def seed_staff(db, depts: dict[str, Department]) -> list[Staff]:
    staff_list = []
    for role, dept_name, count, spec in STAFF_SPEC:
        dept = depts.get(dept_name)
        for _ in range(count):
            gender = random.choice(["M", "F"])
            name = fake.name_male() if gender == "M" else fake.name_female()
            s = Staff(
                full_name=name,
                role=role,
                department_id=dept.id if dept else None,
                specialization=spec,
                contact_number=fake.phone_number()[:20],
                is_active=True,
            )
            db.add(s)
            staff_list.append(s)
    db.flush()
    return staff_list


# ─────────────────────────────────────────────────────────────────────────────
# 3. Users for each staff member + demo accounts
# ─────────────────────────────────────────────────────────────────────────────
DEMO_PASSWORDS = {
    "admin":       ("admin_user",       "Admin@123"),
    "doctor":      ("doctor_user",      "Doctor@123"),
    "nurse":       ("nurse_user",       "Nurse@123"),
    "radiologist": ("radiologist_user", "Radio@123"),
    "dentist":     ("dentist_user",     "Dental@123"),
    "lab_tech":    ("labtech_user",     "LabTech@123"),
}


def seed_users_for_staff(db, staff_list: list[Staff]) -> dict[str, int]:
    """
    Creates one user account per staff member.
    Also creates one 'demo' account per role with a known password.
    Returns a mapping of role → first staff_id of that role (for demo accounts).
    """
    role_first_staff: dict[str, int] = {}
    demo_created: set[str] = set()

    for s in staff_list:
        # First staff of each role becomes the demo account
        if s.role not in role_first_staff:
            role_first_staff[s.role] = s.id

        if s.role not in demo_created and s.id == role_first_staff[s.role]:
            uname, pwd = DEMO_PASSWORDS.get(s.role, (None, None))
            if uname:
                u = User(
                    username=uname,
                    email=f"{uname}@hospital.local",
                    hashed_password=hash_password(pwd),
                    role=s.role,
                    linked_staff_id=s.id,
                    is_active=True,
                )
                db.add(u)
                demo_created.add(s.role)
        else:
            # Generic account for the rest
            slug = s.full_name.lower().replace(" ", "_")[:20]
            uname = f"{slug}_{s.id}"
            u = User(
                username=uname,
                email=f"{uname}@hospital.local",
                hashed_password=hash_password("Hospital@2024"),
                role=s.role,
                linked_staff_id=s.id,
                is_active=True,
            )
            db.add(u)

    db.flush()
    return role_first_staff


# ─────────────────────────────────────────────────────────────────────────────
# 4. Patients
# ─────────────────────────────────────────────────────────────────────────────
def seed_patients(db) -> list[Patient]:
    patients = []
    for i in range(N_PATIENTS):
        gender = random.choice(["M", "F"])
        name = fake.name_male() if gender == "M" else fake.name_female()
        # Age distribution: skewed towards 25–70
        age = int(np.clip(np.random.normal(45, 18), 5, 95))
        dob = date.today() - timedelta(days=age * 365 + random.randint(0, 365))
        rfid = f"RFID-{random.randint(0, 0xFFFFFFFF):08X}"

        p = Patient(
            rfid_tag_id=rfid,
            full_name=name,
            gender=gender,
            date_of_birth=dob,
            blood_group=random.choice(BLOOD_GROUPS),
            contact_number=fake.phone_number()[:20],
            emergency_contact=fake.name()[:100],
            address=fake.address()[:300],
            is_active=True,
        )
        db.add(p)
        patients.append(p)
    db.flush()
    return patients


def seed_patient_users(db, patients: list[Patient]):
    """Creates one patient-role user account per patient (demo: first 5 get easy passwords)."""
    for i, p in enumerate(patients):
        slug = p.full_name.lower().replace(" ", "_")[:20]
        uname = f"patient_{p.id}"
        pwd = "Patient@123" if i == 0 else "Hospital@2024"
        u = User(
            username=uname,
            email=f"{uname}@hospital.local",
            hashed_password=hash_password(pwd),
            role="patient",
            linked_patient_id=p.id,
            is_active=True,
        )
        db.add(u)
    db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Workflow events (REGISTRATION + TRIAGE baseline per patient)
# ─────────────────────────────────────────────────────────────────────────────
def seed_base_workflow(
    db,
    patients: list[Patient],
    staff_list: list[Staff],
    depts: dict[str, Department],
) -> dict[int, datetime]:
    """
    Creates REGISTRATION and TRIAGE events for every patient.
    Returns a mapping of patient_id → registration datetime.
    """
    nurses = [s for s in staff_list if s.role == "nurse"]
    admin_dept = depts.get("Administration")
    reg_times: dict[int, datetime] = {}

    for p in patients:
        reg_time = rand_date(START_DATE, END_DATE)
        nurse = random.choice(nurses)

        # REGISTRATION
        db.add(WorkflowEvent(
            patient_id=p.id,
            department_id=admin_dept.id if admin_dept else None,
            staff_id=nurse.id,
            event_type="REGISTRATION",
            status="COMPLETED",
            notes="Patient registered at reception via RFID scan.",
            event_time=reg_time,
        ))

        # TRIAGE (30 min – 2 hrs after registration)
        triage_time = reg_time + timedelta(minutes=random.randint(30, 120))
        db.add(WorkflowEvent(
            patient_id=p.id,
            department_id=admin_dept.id if admin_dept else None,
            staff_id=nurse.id,
            event_type="TRIAGE",
            status="COMPLETED",
            notes=f"BP: {random.randint(110,150)}/{random.randint(70,95)} mmHg. "
                  f"Temp: {round(random.uniform(36.2, 37.8), 1)}°C. "
                  f"SpO2: {random.randint(95,100)}%.",
            event_time=triage_time,
        ))
        reg_times[p.id] = reg_time

    db.flush()
    return reg_times


# ─────────────────────────────────────────────────────────────────────────────
# 6. Radiology records
# ─────────────────────────────────────────────────────────────────────────────
def seed_radiology(
    db,
    patients: list[Patient],
    staff_list: list[Staff],
    depts: dict[str, Department],
    reg_times: dict[int, datetime],
):
    radiologists = [s for s in staff_list if s.role == "radiologist"]
    doctors = [s for s in staff_list if s.role == "doctor"]
    rad_dept = depts.get("Radiology")

    records_data = []  # collect for label derivation

    # ~60% of patients have at least one radiology record
    rad_patients = random.sample(patients, int(N_PATIENTS * 0.60))

    for p in rad_patients:
        n_records = random.randint(1, 6)
        age = patient_age(p.date_of_birth, reg_times[p.id])
        prev_scans = 0

        for j in range(n_records):
            scan_type = random.choice(SCAN_TYPES)
            indication = random.choice(INDICATIONS)

            # Age-weight priority — older patients or tumour screening get higher priority
            if age > 60 or indication == "Tumour Screening":
                priority = random.choices(RAD_PRIORITIES, weights=[3, 4, 3])[0]
            else:
                priority = random.choices(RAD_PRIORITIES, weights=[7, 2, 1])[0]

            contrast = (scan_type in ["CT", "MRI"]) and random.random() < 0.4
            dose = round(random.uniform(0.5, 15.0), 2) if scan_type in ["X-Ray", "CT"] else 0.0
            duration = round(random.uniform(10, 90), 1)
            body_part = random.choice(BODY_PARTS)

            order_time = rand_date_after(reg_times[p.id], max_days=90)
            complete_time = order_time + timedelta(hours=random.randint(1, 48))

            findings_texts = [
                "No acute abnormality identified.",
                "Mild degenerative changes noted.",
                "Possible consolidation in the lower lobe.",
                "Small pleural effusion present.",
                "Lesion noted requiring further evaluation.",
                "Normal study.",
            ]
            impressions = [
                "Normal.",
                "Findings consistent with chronic changes.",
                "Recommend follow-up in 3 months.",
                "Radiologist review recommended.",
                "No significant pathology.",
                "Abnormality detected — correlate clinically.",
            ]

            r = RadiologyRecord(
                patient_id=p.id,
                ordered_by=random.choice(doctors).id,
                reviewed_by=random.choice(radiologists).id,
                scan_type=scan_type,
                body_part=body_part,
                indication=indication,
                priority=priority,
                status="COMPLETED",
                findings=random.choice(findings_texts),
                impression=random.choice(impressions),
                radiation_dose_mgy=dose,
                contrast_used=contrast,
                scan_duration_min=duration,
                ordered_at=order_time,
                completed_at=complete_time,
            )
            db.add(r)
            records_data.append({
                "record": r,
                "patient_age": age,
                "scan_type": scan_type,
                "indication": indication,
                "priority": priority,
                "contrast_used": contrast,
                "scan_duration_min": duration,
                "previous_scans_count": prev_scans,
                "patient_gender": p.gender,
            })
            prev_scans += 1

            # RESULTS_ENTERED workflow event
            db.add(WorkflowEvent(
                patient_id=p.id,
                department_id=rad_dept.id if rad_dept else None,
                staff_id=random.choice(radiologists).id,
                event_type="RESULTS_ENTERED",
                status="COMPLETED",
                notes=f"Radiology scan completed: {scan_type} of {body_part}.",
                event_time=complete_time,
            ))

    db.flush()

    # Derive labels
    if records_data:
        df = pd.DataFrame([{
            "indication": d["indication"],
            "patient_age": d["patient_age"],
            "priority": d["priority"],
            "scan_type": d["scan_type"],
            "contrast_used": d["contrast_used"],
            "scan_duration_min": d["scan_duration_min"],
        } for d in records_data])
        labels = derive_radiology_label(df)
        for i, d in enumerate(records_data):
            d["record"].requires_radiologist_followup = bool(labels.iloc[i])

    db.flush()

    pos_count = sum(1 for d in records_data if d["record"].requires_radiologist_followup)
    print(f"  Radiology: {len(records_data)} records, "
          f"{pos_count} positive ({100*pos_count//max(len(records_data),1)}%)")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Dental records
# ─────────────────────────────────────────────────────────────────────────────
def seed_dental(
    db,
    patients: list[Patient],
    staff_list: list[Staff],
    depts: dict[str, Department],
    reg_times: dict[int, datetime],
):
    dentists = [s for s in staff_list if s.role == "dentist"]
    dental_dept = depts.get("Dental")

    records_data = []
    dental_patients = random.sample(patients, int(N_PATIENTS * 0.65))

    for p in dental_patients:
        n_records = random.randint(1, 5)
        age = patient_age(p.date_of_birth, reg_times[p.id])
        visit_count = 0
        last_visit: datetime | None = None

        for j in range(n_records):
            visit_time = rand_date_after(
                last_visit if last_visit else reg_times[p.id], max_days=180
            )
            days_since = (visit_time - last_visit).days if last_visit else 365
            visit_count += 1

            procedure = random.choice(PROCEDURE_TYPES)
            diagnosis = random.choice(DIAGNOSES)
            # Age-weighted diagnosis
            if age > 50:
                diagnosis = random.choices(
                    DIAGNOSES, weights=[3, 4, 1, 1, 1, 2]
                )[0]
            tooth_type = random.choice(TOOTH_TYPES)
            material = random.choice(MATERIALS)
            pain = random.randint(0, 10)
            cost = round(random.uniform(500, 50000), 2)

            next_appt = visit_time + timedelta(days=random.randint(30, 180))

            r = DentalRecord(
                patient_id=p.id,
                dentist_id=random.choice(dentists).id,
                procedure_type=procedure,
                tooth_notation=f"{random.randint(11,48)}",
                tooth_type=tooth_type,
                tooth_quadrant=random.choice(TOOTH_QUADRANTS),
                pain_score=pain,
                diagnosis=diagnosis,
                treatment_notes=fake.sentence(nb_words=12),
                material_used=material,
                cost=cost,
                visit_count_at_time=visit_count,
                status="COMPLETED",
                visit_date=visit_time,
                next_appointment=next_appt,
            )
            db.add(r)
            records_data.append({
                "record": r,
                "patient_age": age,
                "diagnosis": diagnosis,
                "pain_score": pain,
                "procedure_type": procedure,
                "visit_count_at_time": visit_count,
                "days_since_last_visit": float(days_since),
                "tooth_type": tooth_type,
                "patient_gender": p.gender,
            })
            last_visit = visit_time

            db.add(WorkflowEvent(
                patient_id=p.id,
                department_id=dental_dept.id if dental_dept else None,
                staff_id=random.choice(dentists).id,
                event_type="RESULTS_ENTERED",
                status="COMPLETED",
                notes=f"Dental procedure completed: {procedure}. Diagnosis: {diagnosis}.",
                event_time=visit_time,
            ))

    db.flush()

    if records_data:
        df = pd.DataFrame([{
            "diagnosis": d["diagnosis"],
            "pain_score": d["pain_score"],
            "procedure_type": d["procedure_type"],
            "visit_count_at_time": d["visit_count_at_time"],
            "days_since_last_visit": d["days_since_last_visit"],
            "tooth_type": d["tooth_type"],
            "patient_age": d["patient_age"],
        } for d in records_data])
        labels = derive_dental_label(df)
        for i, d in enumerate(records_data):
            d["record"].treatment_escalation_risk = bool(labels.iloc[i])

    db.flush()
    pos_count = sum(1 for d in records_data if d["record"].treatment_escalation_risk)
    print(f"  Dental:    {len(records_data)} records, "
          f"{pos_count} positive ({100*pos_count//max(len(records_data),1)}%)")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Blood test records (CBC panel only for ML)
# ─────────────────────────────────────────────────────────────────────────────
def _sample_analyte(name: str, gender: str, abnormal: bool) -> float:
    """Sample one analyte value: normal range 80% of the time, abnormal 20%."""
    info = CBC_ANALYTES[name]
    lo, hi = info[gender]
    if not abnormal:
        return round(random.uniform(lo, hi), 2)
    # Sample from outside the range
    if random.random() < 0.5:
        return round(random.uniform(max(0, lo * 0.5), lo * 0.99), 2)
    else:
        return round(random.uniform(hi * 1.01, hi * 1.5), 2)


def seed_blood_tests(
    db,
    patients: list[Patient],
    staff_list: list[Staff],
    depts: dict[int, Department],
    reg_times: dict[int, datetime],
):
    lab_techs = [s for s in staff_list if s.role == "lab_tech"]
    doctors = [s for s in staff_list if s.role == "doctor"]
    lab_dept = depts.get("Blood Laboratory")

    records_data = []
    bt_patients = random.sample(patients, int(N_PATIENTS * 0.70))

    for p in bt_patients:
        n_records = random.randint(1, 6)
        age = patient_age(p.date_of_birth, reg_times[p.id])

        for j in range(n_records):
            order_time = rand_date_after(reg_times[p.id], max_days=180)
            collected_time = order_time + timedelta(hours=random.randint(1, 8))
            resulted_time = collected_time + timedelta(hours=random.randint(2, 12))

            rec = BloodTestRecord(
                patient_id=p.id,
                ordered_by=random.choice(doctors).id,
                test_panel="CBC",
                priority=random.choices(["Routine", "Urgent"], weights=[8, 2])[0],
                status="RESULTED",
                ordered_at=order_time,
                collected_at=collected_time,
                resulted_at=resulted_time,
            )
            db.add(rec)
            db.flush()  # need rec.id for results

            # Generate analyte values
            # ~20% chance each individual analyte is abnormal
            analyte_values: dict[str, float] = {}
            for name, info in CBC_ANALYTES.items():
                abnormal = random.random() < 0.20
                analyte_values[name] = _sample_analyte(name, p.gender, abnormal)
                lo, hi = info[p.gender]
                val = analyte_values[name]
                is_flagged = (val < lo or val > hi)
                flag_type = None
                if is_flagged:
                    if val < lo * 0.7:
                        flag_type = "CRITICAL_LOW"
                    elif val < lo:
                        flag_type = "LOW"
                    elif val > hi * 1.3:
                        flag_type = "CRITICAL_HIGH"
                    else:
                        flag_type = "HIGH"

                db.add(BloodTestResult(
                    blood_test_id=rec.id,
                    analyte_name=name,
                    result_value=val,
                    unit=info["unit"],
                    reference_min=lo,
                    reference_max=hi,
                    is_flagged=is_flagged,
                    flag_type=flag_type,
                ))

            records_data.append({
                "record": rec,
                "patient_age": age,
                "patient_gender": p.gender,
                **analyte_values,
            })

            db.add(WorkflowEvent(
                patient_id=p.id,
                department_id=lab_dept.id if lab_dept else None,
                staff_id=random.choice(lab_techs).id,
                event_type="RESULTS_ENTERED",
                status="COMPLETED",
                notes="CBC blood test results entered.",
                event_time=resulted_time,
            ))

    db.flush()

    if records_data:
        feature_cols = list(CBC_ANALYTES.keys()) + ["patient_age", "patient_gender"]
        df = pd.DataFrame([{k: d[k] for k in feature_cols} for d in records_data])
        labels = derive_blood_test_label(df)
        for i, d in enumerate(records_data):
            d["record"].haematological_abnormality_pattern = bool(labels.iloc[i])

    db.flush()
    pos_count = sum(1 for d in records_data if d["record"].haematological_abnormality_pattern)
    print(f"  Blood:     {len(records_data)} records, "
          f"{pos_count} positive ({100*pos_count//max(len(records_data),1)}%)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Hospital Prototype — Synthetic Data Generator")
    print("=" * 60)

    print("\n[1/7] Creating database tables...")
    create_all_tables()

    db = SessionLocal()
    try:
        print("[2/7] Seeding departments...")
        depts = seed_departments(db)
        db.commit()
        print(f"      {len(depts)} departments created.")

        print("[3/7] Seeding staff...")
        staff_list = seed_staff(db, depts)
        db.commit()
        print(f"      {len(staff_list)} staff members created.")

        print("[4/7] Seeding staff user accounts...")
        seed_users_for_staff(db, staff_list)
        db.commit()
        print("      Staff user accounts created.")

        print("[5/7] Seeding patients...")
        patients = seed_patients(db)
        db.commit()
        seed_patient_users(db, patients)
        db.commit()
        print(f"      {len(patients)} patients created with user accounts.")

        print("[6/7] Seeding baseline workflow events...")
        reg_times = seed_base_workflow(db, patients, staff_list, depts)
        db.commit()
        print(f"      REGISTRATION + TRIAGE events created for all {len(patients)} patients.")

        print("[7/7] Seeding medical records (with derived ML labels)...")
        seed_radiology(db, patients, staff_list, depts, reg_times)
        seed_dental(db, patients, staff_list, depts, reg_times)
        seed_blood_tests(db, patients, staff_list, depts, reg_times)
        db.commit()

        print("\n" + "=" * 60)
        print("Data generation complete.")
        print("\nDemo login credentials:")
        print("  Role          Username              Password")
        print("  ─────────── ────────────────────── ─────────────")
        print("  admin         admin_user            Admin@123")
        print("  doctor        doctor_user           Doctor@123")
        print("  nurse         nurse_user            Nurse@123")
        print("  radiologist   radiologist_user      Radio@123")
        print("  dentist       dentist_user          Dental@123")
        print("  lab_tech      labtech_user          LabTech@123")
        print("  patient       patient_1             Patient@123")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"\n❌ Error during generation: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
