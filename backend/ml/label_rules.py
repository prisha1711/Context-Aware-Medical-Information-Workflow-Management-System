"""
ml/label_rules.py
─────────────────────────────────────────────────────────────────────────────
Synthetic ML label derivation rules for all three domains.

IMPORTANT: These labels are SYNTHETIC and derived from logical rules applied
to other synthetic features. They are used to train ML models for educational
and demonstration purposes only. They do not represent real clinical outcomes.

All three functions add ~8–10% random noise to simulate real-world uncertainty.
Without noise, ML models would achieve near-perfect accuracy, which would be
unbelievable in a demo.
─────────────────────────────────────────────────────────────────────────────
"""
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# 1. RADIOLOGY — requires_radiologist_followup
# Target: Should this scan result be escalated for radiologist follow-up?
# ─────────────────────────────────────────────────────────────────────────────

def derive_radiology_label(df: pd.DataFrame, noise_rate: float = 0.10) -> pd.Series:
    """
    Derives the binary label `requires_radiologist_followup` from radiology features.

    Rules (logical OR — any one condition makes label = 1):
      A. indication == "Tumour Screening"
      B. indication == "Chronic Disease" AND patient_age > 55
      C. priority == "STAT"
      D. scan_type == "CT" AND indication == "Infection" AND patient_age > 60
      E. contrast_used == True AND scan_duration_min > 60

    Then ~10% of labels are randomly flipped to simulate uncertainty.

    Expected positive rate: ~28–35%

    Args:
        df: DataFrame with columns: indication, patient_age, priority,
            scan_type, contrast_used, scan_duration_min
        noise_rate: Fraction of labels to randomly flip (default 0.10)

    Returns:
        pd.Series of int (0 or 1)
    """
    label = (
        (df["indication"] == "Tumour Screening")
        | (  (df["indication"] == "Chronic Disease") & (df["patient_age"] > 55)  )
        | (df["priority"] == "STAT")
        | (  (df["scan_type"] == "CT") & (df["indication"] == "Infection") & (df["patient_age"] > 60)  )
        | (  (df["contrast_used"] == True) & (df["scan_duration_min"] > 60)  )
    ).astype(int)

    # Add noise: randomly flip noise_rate fraction of labels
    rng = np.random.default_rng(seed=42)
    flip_mask = rng.random(len(label)) < noise_rate
    label = label.copy()
    label[flip_mask] = 1 - label[flip_mask]

    return label


# ─────────────────────────────────────────────────────────────────────────────
# 2. DENTAL — treatment_escalation_risk
# Target: Is this patient likely to need a more complex future intervention?
# ─────────────────────────────────────────────────────────────────────────────

def derive_dental_label(df: pd.DataFrame, noise_rate: float = 0.10) -> pd.Series:
    """
    Derives the binary label `treatment_escalation_risk` from dental features.

    Rules (logical OR):
      A. diagnosis == "Abscess"
      B. diagnosis == "Periodontitis" AND pain_score >= 6
      C. procedure_type == "Filling" AND visit_count_at_time >= 3
              AND days_since_last_visit < 180
      D. diagnosis == "Caries" AND tooth_type == "Molar" AND patient_age < 25
      E. pain_score >= 8 AND diagnosis != "Healthy"

    Expected positive rate: ~30–38%

    Args:
        df: DataFrame with columns: diagnosis, pain_score, procedure_type,
            visit_count_at_time, days_since_last_visit, tooth_type, patient_age
        noise_rate: Fraction of labels to randomly flip (default 0.10)

    Returns:
        pd.Series of int (0 or 1)
    """
    label = (
        (df["diagnosis"] == "Abscess")
        | (  (df["diagnosis"] == "Periodontitis") & (df["pain_score"] >= 6)  )
        | (
              (df["procedure_type"] == "Filling")
              & (df["visit_count_at_time"] >= 3)
              & (df["days_since_last_visit"] < 180)
          )
        | (
              (df["diagnosis"] == "Caries")
              & (df["tooth_type"] == "Molar")
              & (df["patient_age"] < 25)
          )
        | (  (df["pain_score"] >= 8) & (df["diagnosis"] != "Healthy")  )
    ).astype(int)

    rng = np.random.default_rng(seed=43)
    flip_mask = rng.random(len(label)) < noise_rate
    label = label.copy()
    label[flip_mask] = 1 - label[flip_mask]

    return label


# ─────────────────────────────────────────────────────────────────────────────
# 3. BLOOD TESTS — haematological_abnormality_pattern
# Target: Do the CBC results show a pattern consistent with a notable
#         haematological concern?
# Only applicable to CBC panel records.
# ─────────────────────────────────────────────────────────────────────────────

# Gender-adjusted haemoglobin thresholds (g/dL)
HGB_THRESHOLD = {"F": 12.0, "M": 13.5}
HCT_THRESHOLD = {"F": 37.0, "M": 42.0}

def derive_blood_test_label(df: pd.DataFrame, noise_rate: float = 0.08) -> pd.Series:
    """
    Derives the binary label `haematological_abnormality_pattern` from CBC analyte values.

    Four physiologically grounded patterns (logical OR):
      Pattern A — Microcytic Anaemia:
          hemoglobin < gender_threshold AND mcv < 80 AND mchc < 32
      Pattern B — Infection / Inflammatory Response:
          wbc_count > 11.0 AND neutrophils_pct > 75
      Pattern C — Thrombocytopenia risk:
          platelet_count < 150 AND hematocrit < gender_threshold
      Pattern D — Macrocytic concern (B12/Folate):
          mcv > 100 AND hemoglobin < gender_threshold

    Expected positive rate: ~30–38%

    Args:
        df: DataFrame with columns: hemoglobin, wbc_count, platelet_count,
            hematocrit, mcv, mchc, neutrophils_pct, patient_gender
            (patient_gender: "M" or "F")
        noise_rate: Fraction of labels to randomly flip (default 0.08)

    Returns:
        pd.Series of int (0 or 1). Returns 0 for all rows if panel is not CBC.
    """
    hgb_thresh = df["patient_gender"].map(HGB_THRESHOLD).fillna(12.5)
    hct_thresh = df["patient_gender"].map(HCT_THRESHOLD).fillna(39.5)

    pattern_a = (
        (df["hemoglobin"] < hgb_thresh)
        & (df["mcv"] < 80)
        & (df["mchc"] < 32)
    )
    pattern_b = (
        (df["wbc_count"] > 11.0)
        & (df["neutrophils_pct"] > 75)
    )
    pattern_c = (
        (df["platelet_count"] < 150)
        & (df["hematocrit"] < hct_thresh)
    )
    pattern_d = (
        (df["mcv"] > 100)
        & (df["hemoglobin"] < hgb_thresh)
    )

    label = (pattern_a | pattern_b | pattern_c | pattern_d).astype(int)

    rng = np.random.default_rng(seed=44)
    flip_mask = rng.random(len(label)) < noise_rate
    label = label.copy()
    label[flip_mask] = 1 - label[flip_mask]

    return label
