NUMERIC = ["age", "trestbps", "chol", "thalach", "oldpeak", "ca"]
CATEGORICAL = ["sex", "cp", "fbs", "restecg", "exang", "slope", "thal"]

CORE = ["age", "sex", "cp", "exang", "trestbps", "chol", "fbs"]
CLINICAL = CORE + ["restecg", "thalach", "oldpeak"]
FULL = CLINICAL + ["slope", "ca", "thal"]

DEPLOY = {"core": CORE, "clinical": CLINICAL}
PAPER = {"full13": FULL, "portable10": CLINICAL}

SITES = ["Cleveland", "Hungary", "Switzerland", "Long Beach VA"]

LABELS = {
    "age": "Your age",
    "sex": "Your sex",
    "cp": "Your chest pain pattern",
    "exang": "Chest pain brought on by exertion",
    "trestbps": "Resting blood pressure",
    "chol": "Cholesterol",
    "fbs": "Fasting blood sugar",
    "restecg": "Resting ECG result",
    "thalach": "Highest heart rate in a stress test",
    "oldpeak": "ST depression in a stress test",
}
