"""Ground-truth process used ONLY to generate synthetic data and to play out simulated days.
Replace with real SMCW history (de-identified) once a data-sharing agreement exists."""
import numpy as np

# code -> (modality, base minutes)
TESTS = {
    "MRI_BRAIN": ("MRI", 30), "MRI_SPINE": ("MRI", 40), "MRI_KNEE": ("MRI", 25),
    "CT_HEAD": ("CT", 10), "CT_CHEST": ("CT", 14), "CT_ABDOMEN": ("CT", 16),
}
SIGMA = 0.25


def expected_duration(test_code, contrast, sedation, age, inpatient, tech_exp):
    base = TESTS[test_code][1]
    d = base * (1.45 if contrast else 1.0) * (1.15 if age > 65 else 1.0) * (1.6 if sedation else 1.0)
    d *= 1.12 - 0.02 * min(tech_exp, 10)
    return d + (3 if inpatient else 0)


def true_duration(rng, **f):
    return max(5.0, expected_duration(**f) * float(np.exp(SIGMA * rng.standard_normal())))


def no_show_prob(age, lead_days, prior_no_shows, dow, hour, sms_confirmed, inpatient, distance_km):
    if inpatient:
        return 0.01
    z = (-2.6 + 0.012 * max(0, 45 - age) + 0.03 * min(lead_days, 30) + 0.55 * min(prior_no_shows, 4)
         + (0.25 if dow in (0, 4) else 0) + (0.2 if hour < 9 else 0) - 0.9 * sms_confirmed + 0.01 * min(distance_km, 40))
    return float(1 / (1 + np.exp(-z)))
