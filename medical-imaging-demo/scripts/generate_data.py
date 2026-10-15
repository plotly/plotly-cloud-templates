"""Generate all synthetic clinical CSVs for the demo."""
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

np.random.seed(42)
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# ── Names ────────────────────────────────────────────────────────────────────
FIRST = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda",
         "David","Barbara","William","Elizabeth","Richard","Susan","Joseph",
         "Jessica","Thomas","Sarah","Charles","Karen","Christopher","Lisa",
         "Daniel","Nancy","Matthew","Betty","Anthony","Margaret","Mark","Sandra"]
LAST  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
         "Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White","Harris",
         "Martin","Thompson","Young","Lewis","Walker","Hall","Allen","King",
         "Wright","Scott","Green","Baker","Adams","Nelson"]

DIAGNOSES   = ["Pneumonia","Sepsis","COPD Exacerbation","Heart Failure","Acute MI",
               "Stroke","Trauma","UTI","GI Bleed","Pulmonary Embolism",
               "Hypertensive Crisis","Diabetic Ketoacidosis","Cellulitis",
               "Atrial Fibrillation","Respiratory Failure"]
WARDS       = ["ICU","MICU","CCU","Step-Down","General Med","ED Obs"]
DEPARTMENTS = ["Cardiology","Pulmonology","Neurology","General Medicine",
               "Surgery","Nephrology","Oncology"]

# ── Patient roster ────────────────────────────────────────────────────────────
N = 60
rows = []
for i in range(N):
    ward = np.random.choice(WARDS, p=[0.10,0.08,0.07,0.15,0.45,0.15])
    rows.append({
        "patient_id":    f"PT{i+1001}",
        "name":          f"{np.random.choice(FIRST)} {np.random.choice(LAST)}",
        "age":           int(np.random.randint(22, 91)),
        "gender":        np.random.choice(["M","F"]),
        "diagnosis":     np.random.choice(DIAGNOSES),
        "ward":          ward,
        "department":    np.random.choice(DEPARTMENTS),
        "admitted_date": (datetime(2026,6,1) + timedelta(days=int(np.random.randint(0,15)))).strftime("%Y-%m-%d"),
        "los_days":      int(np.random.randint(1,15)),
        "risk_score":    round(float(np.random.beta(2,5)*100), 1),
        "sepsis_risk":   round(float(np.random.beta(1.5,8)*100), 1),
        "fall_risk":     round(float(np.random.beta(2,6)*100), 1),
        "readmit_risk":  round(float(np.random.beta(2,5)*100), 1),
        "deterioration_risk": round(float(np.random.beta(1.5,7)*100), 1),
        "is_icu":        ward in ("ICU","MICU","CCU"),
    })

df_patients = pd.DataFrame(rows)
# Ensure first 5 are ICU patients for the live panel
for i in range(5):
    df_patients.at[i, "ward"] = ["ICU","MICU","CCU","ICU","MICU"][i]
    df_patients.at[i, "is_icu"] = True
df_patients.to_csv(DATA / "patients.csv", index=False)
print(f"patients.csv  — {len(df_patients)} rows")

# ── Vitals time series (72 h, 15-min intervals, 8 ICU patients) ───────────────
ICU_BASES = [
    {"patient_id":"PT1001","base_hr":72,"base_spo2":98.5,"base_sbp":118,"base_dbp":76,"base_rr":14},
    {"patient_id":"PT1002","base_hr":92,"base_spo2":96.8,"base_sbp":148,"base_dbp":90,"base_rr":18},
    {"patient_id":"PT1003","base_hr":88,"base_spo2":93.5,"base_sbp":108,"base_dbp":68,"base_rr":21},
    {"patient_id":"PT1004","base_hr":78,"base_spo2":99.1,"base_sbp":168,"base_dbp":97,"base_rr":16},
    {"patient_id":"PT1005","base_hr":66,"base_spo2":98.9,"base_sbp":125,"base_dbp":80,"base_rr":13},
    {"patient_id":"PT1006","base_hr":95,"base_spo2":95.2,"base_sbp":135,"base_dbp":82,"base_rr":20},
    {"patient_id":"PT1007","base_hr":74,"base_spo2":97.8,"base_sbp":120,"base_dbp":75,"base_rr":15},
    {"patient_id":"PT1008","base_hr":82,"base_spo2":96.0,"base_sbp":142,"base_dbp":88,"base_rr":17},
]

base_time = datetime(2026, 6, 14, 0, 0, 0)
vitals_rows = []
for p in ICU_BASES:
    pid = p["patient_id"]
    hr  = float(p["base_hr"])
    spo = float(p["base_spo2"])
    sbp = float(p["base_sbp"])
    dbp = float(p["base_dbp"])
    rr  = float(p["base_rr"])
    for i in range(72 * 4):
        t    = base_time + timedelta(minutes=15*i)
        hour = t.hour
        # Gentle circadian drift
        hr  = float(np.clip(hr  + np.random.normal(-0.05*(hr-p["base_hr"])*0.1, 1.2), 40, 200))
        spo = float(np.clip(spo + np.random.normal(-0.05*(spo-p["base_spo2"])*0.1, 0.25), 85, 100))
        sbp = float(np.clip(sbp + np.random.normal(0, 2.0), 70, 220))
        dbp = float(np.clip(dbp + np.random.normal(0, 1.5), 40, 130))
        rr  = float(np.clip(rr  + np.random.normal(0, 0.4), 8, 40))
        vitals_rows.append({
            "patient_id": pid,
            "timestamp":  t.strftime("%Y-%m-%d %H:%M:%S"),
            "HR":   round(hr,  1),
            "SpO2": round(spo, 1),
            "Temp": round(np.random.normal(37.1, 0.3), 1),
            "SysBP": round(sbp, 1),
            "DiaBP": round(dbp, 1),
            "RR":   round(rr,  1),
        })

df_vitals = pd.DataFrame(vitals_rows)
df_vitals.to_csv(DATA / "vitals.csv", index=False)
print(f"vitals.csv    — {len(df_vitals)} rows")

# ── Cohort biomarkers (200 patients) ─────────────────────────────────────────
COH_DIAG = ["Type 2 Diabetes","Hypertension","COPD","Heart Failure","CKD",
            "Obesity","CAD","Asthma","Hyperlipidemia","Atrial Fibrillation"]
cohort = []
for i in range(200):
    age  = int(np.random.randint(20, 85))
    bmi  = float(np.clip(np.random.normal(28, 6), 16, 55))
    sbp  = float(np.clip(np.random.normal(130, 22), 80, 220))
    ldl  = float(np.clip(np.random.normal(115, 38), 40, 260))
    hba1c= float(np.clip(np.random.normal(6.8, 1.6), 4.5, 14))
    egfr = float(np.clip(np.random.normal(68, 26), 5, 130))

    score = (int(sbp>160)*2 + int(ldl>160) + int(hba1c>8)*2 +
             int(egfr<45)*2 + int(bmi>35))
    risk  = "High" if score >= 4 else "Medium" if score >= 2 else "Low"
    cohort.append({
        "patient_id":  f"CO{i+2001}",
        "age":          age,
        "gender":       np.random.choice(["M","F"]),
        "bmi":          round(bmi, 1),
        "systolic_bp":  round(sbp, 0),
        "ldl":          round(ldl, 1),
        "hba1c":        round(hba1c, 1),
        "egfr":         round(egfr, 1),
        "diagnosis":    np.random.choice(COH_DIAG),
        "risk_level":   risk,
    })

df_cohort = pd.DataFrame(cohort)
df_cohort.to_csv(DATA / "cohort.csv", index=False)
print(f"cohort.csv    — {len(df_cohort)} rows")

# ── Admissions time series (30 days) ─────────────────────────────────────────
BASE_COUNT = {"Cardiology":12,"Pulmonology":8,"Neurology":6,
              "General Medicine":20,"Surgery":10,"Nephrology":5,"Oncology":4}
adm_rows = []
for d in range(30):
    dt = datetime(2026,5,17) + timedelta(days=d)
    for dept, base in BASE_COUNT.items():
        # Weekend dip
        weekend = dt.weekday() >= 5
        count = max(0, int(np.random.normal(base * (0.75 if weekend else 1.0), 2)))
        adm_rows.append({"date": dt.strftime("%Y-%m-%d"), "department": dept, "admissions": count})

pd.DataFrame(adm_rows).to_csv(DATA / "admissions.csv", index=False)
print(f"admissions.csv — {len(adm_rows)} rows")

# ── Labs (20 patients) ────────────────────────────────────────────────────────
LAB_TESTS = {
    "WBC":        (4.5,  11.0, "10³/µL"),
    "Hemoglobin": (12.0, 17.5, "g/dL"),
    "Platelets":  (150,  400,  "10³/µL"),
    "Sodium":     (136,  145,  "mEq/L"),
    "Potassium":  (3.5,  5.0,  "mEq/L"),
    "Creatinine": (0.7,  1.3,  "mg/dL"),
    "BUN":        (7,    25,   "mg/dL"),
    "Glucose":    (70,   100,  "mg/dL"),
    "Lactate":    (0.5,  2.0,  "mmol/L"),
    "Troponin":   (0.0,  0.04, "ng/mL"),
}
lab_rows = []
for _, pat in df_patients.head(20).iterrows():
    for test, (lo, hi, unit) in LAB_TESTS.items():
        mid = (lo + hi) / 2
        val = round(float(np.clip(np.random.normal(mid, (hi-lo)*0.3), lo*0.5, hi*2)), 3)
        flag = "H" if val > hi else "L" if val < lo else "N"
        lab_rows.append({
            "patient_id": pat["patient_id"],
            "date": "2026-06-15",
            "test": test,
            "value": val,
            "unit": unit,
            "reference_low": lo,
            "reference_high": hi,
            "flag": flag,
        })

pd.DataFrame(lab_rows).to_csv(DATA / "labs.csv", index=False)
print(f"labs.csv      — {len(lab_rows)} rows")

# ── Imaging studies metadata ──────────────────────────────────────────────────
STUDIES = [
    {"study_id":"ST0001","findings":"No Finding",               "age":45,"gender":"M","view":"PA"},
    {"study_id":"ST0002","findings":"Cardiomegaly",             "age":67,"gender":"F","view":"PA"},
    {"study_id":"ST0003","findings":"Pleural Effusion|Cardiomegaly","age":72,"gender":"M","view":"AP"},
    {"study_id":"ST0004","findings":"Pneumonia|Consolidation",  "age":58,"gender":"F","view":"PA"},
    {"study_id":"ST0005","findings":"Atelectasis",              "age":81,"gender":"M","view":"AP"},
    {"study_id":"ST0006","findings":"Nodule",                   "age":63,"gender":"F","view":"PA"},
    {"study_id":"ST0007","findings":"Pneumothorax",             "age":34,"gender":"M","view":"AP"},
    {"study_id":"ST0008","findings":"Mass",                     "age":69,"gender":"F","view":"PA"},
]
pat_names = df_patients["name"].tolist()
study_rows = []
for i, s in enumerate(STUDIES):
    study_rows.append({
        "study_id":     s["study_id"],
        "patient_id":   f"PT{i+1001}",
        "patient_name": pat_names[i],
        "age":          s["age"],
        "gender":       s["gender"],
        "view_position":s["view"],
        "finding_labels":s["findings"],
        "study_date":   "2026-06-15",
        "accession":    f"ACC{np.random.randint(100000,999999)}",
        "image_file":   f"xray_{i+1:02d}.png",
        "referrer":     "Dr. " + np.random.choice(LAST),
    })

pd.DataFrame(study_rows).to_csv(DATA / "studies.csv", index=False)
print(f"studies.csv   — {len(study_rows)} rows")
print("\nAll data generated.")
