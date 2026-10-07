DURATION_FEATURES = ["test_code", "modality", "contrast", "sedation", "inpatient", "age", "hour", "dow", "tech_exp"]
DURATION_CATEGORICAL = ["test_code", "modality"]
NOSHOW_FEATURES = ["modality", "age", "lead_days", "prior_no_shows", "dow", "hour", "sms_confirmed", "inpatient", "distance_km"]
NOSHOW_CATEGORICAL = ["modality"]
DURATION_QUANTILE = 0.80   # schedule against the 80th percentile, not the mean
