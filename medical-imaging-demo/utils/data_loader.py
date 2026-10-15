import pandas as pd
import pathlib

ROOT      = pathlib.Path(__file__).parent.parent
DATA_PATH = ROOT / "data"

def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_PATH / name)

# Cached loads
df_patients   = _csv("patients.csv")
df_vitals     = _csv("vitals.csv")
df_cohort     = _csv("cohort.csv")
df_admissions = _csv("admissions.csv")
df_labs       = _csv("labs.csv")
df_studies    = _csv("studies.csv")


# ── Census / dashboard metrics ────────────────────────────────────────────────
def get_census_metrics() -> dict:
    total       = len(df_patients)
    icu_total   = df_patients["is_icu"].sum()
    icu_cap     = 25  # beds
    avg_los     = round(float(df_patients["los_days"].mean()), 1)
    critical    = int((df_patients["risk_score"] > 70).sum())
    return {
        "total_patients": total,
        "icu_occupancy":  round(icu_total / icu_cap * 100, 1),
        "avg_los":        avg_los,
        "critical_alerts":critical,
    }

def get_risk_overview() -> dict:
    return {
        "sepsis":       round(float(df_patients["sepsis_risk"].mean()), 1),
        "fall":         round(float(df_patients["fall_risk"].mean()), 1),
        "readmit":      round(float(df_patients["readmit_risk"].mean()), 1),
        "deterioration":round(float(df_patients["deterioration_risk"].mean()), 1),
    }


# ── Admissions ────────────────────────────────────────────────────────────────
def get_admissions_data(department: str = "All", period: str = "30d") -> pd.DataFrame:
    df = df_admissions.copy()
    df["date"] = pd.to_datetime(df["date"])
    days = {"7d": 7, "14d": 14, "30d": 30}.get(period, 30)
    df = df[df["date"] >= df["date"].max() - pd.Timedelta(days=days-1)]
    if department != "All":
        df = df[df["department"] == department]
    return df


# ── Vitals ────────────────────────────────────────────────────────────────────
PERIOD_HOURS = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "72h": 72}

def get_vitals(patient_id: str, period: str = "24h") -> pd.DataFrame:
    df = df_vitals[df_vitals["patient_id"] == patient_id].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    hours = PERIOD_HOURS.get(period, 24)
    cutoff = df["timestamp"].max() - pd.Timedelta(hours=hours)
    return df[df["timestamp"] >= cutoff].reset_index(drop=True)

def get_vitals_stats(patient_id: str, vital: str, period: str = "24h") -> dict:
    df = get_vitals(patient_id, period)
    if df.empty or vital not in df.columns:
        return {}
    col = df[vital]
    return {
        "current": round(float(col.iloc[-1]), 1),
        "min":     round(float(col.min()), 1),
        "max":     round(float(col.max()), 1),
        "mean":    round(float(col.mean()), 1),
    }


# ── Cohort ────────────────────────────────────────────────────────────────────
def get_cohort() -> pd.DataFrame:
    return df_cohort.copy()


# ── Labs ──────────────────────────────────────────────────────────────────────
def get_labs(patient_id: str) -> pd.DataFrame:
    return df_labs[df_labs["patient_id"] == patient_id].copy()


# ── Studies ───────────────────────────────────────────────────────────────────
def get_studies() -> pd.DataFrame:
    return df_studies.copy()

def get_study(study_id: str) -> dict:
    row = df_studies[df_studies["study_id"] == study_id]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


# ── Patient helpers ───────────────────────────────────────────────────────────
def get_patient(patient_id: str) -> dict:
    row = df_patients[df_patients["patient_id"] == patient_id]
    return row.iloc[0].to_dict() if not row.empty else {}

def get_icu_patients() -> pd.DataFrame:
    return df_patients[df_patients["is_icu"]].head(5).copy()
