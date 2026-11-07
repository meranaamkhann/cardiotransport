def bp_status(systolic, diastolic):
    if systolic is None and diastolic is None:
        return None
    s = systolic if systolic is not None else 0
    d = diastolic if diastolic is not None else 0
    if s > 180 or d > 120:
        return "crisis"
    if s >= 140 or d >= 90:
        return "stage2"
    if s >= 130 or d >= 80:
        return "stage1"
    if s >= 120:
        return "elevated"
    return "normal"


def bmi_value(height_cm, weight_kg):
    if not height_cm or not weight_kg:
        return None
    return weight_kg / (height_cm / 100) ** 2


def factor(key, label, value, status, detail, tip):
    return {"key": key, "label": label, "value": value, "status": status, "detail": detail, "tip": tip}


def assess_wellness(w):
    items = []
    urgent = []

    status = bp_status(w.systolic, w.diastolic)
    if status is None:
        items.append(factor("bp", "Blood pressure", "not provided", "unknown",
                            "Blood pressure is one of the strongest everyday risk factors.",
                            "Get it measured at a pharmacy, clinic, or with a validated home monitor."))
    else:
        reading = f"{int(w.systolic) if w.systolic else '?'}/{int(w.diastolic) if w.diastolic else '?'} mmHg"
        table = {
            "normal": ("good", "In the normal range.", "Keep checking it at least once a year."),
            "elevated": ("watch", "Slightly above normal.", "Cut back on salt, stay active, and recheck in a few months."),
            "stage1": ("watch", "Stage 1 high blood pressure range.",
                       "Recheck on separate days and discuss it with a doctor, especially with other risk factors."),
            "stage2": ("action", "Stage 2 high blood pressure range.",
                       "See a doctor in the coming days to confirm the reading and plan treatment."),
            "crisis": ("action", "Very high reading.",
                       "Rest and recheck after 5 minutes. If it stays this high, get medical care the same day. "
                       "With chest pain, breathlessness, or weakness, call emergency services."),
        }[status]
        items.append(factor("bp", "Blood pressure", reading, table[0], table[1], table[2]))
        if status == "crisis":
            urgent.append("Your blood pressure reading is in a range that needs same-day medical advice.")

    if w.cholesterol is None:
        items.append(factor("chol", "Total cholesterol", "not provided", "unknown",
                            "Cholesterol has no symptoms, so only a blood test shows it.",
                            "A lipid profile is a simple blood test; ask for one if you have not had it in the past few years."))
    else:
        if w.cholesterol < 200:
            s, d, t = "good", "Desirable range.", "Keep a diet rich in vegetables, fibre, and unsaturated fats."
        elif w.cholesterol < 240:
            s, d, t = "watch", "Borderline high.", "Review diet and activity, and discuss the full lipid profile with a doctor."
        else:
            s, d, t = "action", "High.", "Book a doctor visit to review the full lipid profile and treatment options."
        items.append(factor("chol", "Total cholesterol", f"{int(w.cholesterol)} mg/dL", s, d, t))

    if w.fasting_glucose is None:
        items.append(factor("glucose", "Fasting blood sugar", "not provided", "unknown",
                            "High blood sugar quietly damages blood vessels.",
                            "A fasting glucose or HbA1c test is quick and inexpensive."))
    else:
        if w.fasting_glucose < 100:
            s, d, t = "good", "Normal range.", "Keep your weight and activity steady."
        elif w.fasting_glucose < 126:
            s, d, t = "watch", "Prediabetes range.", "Weight loss and regular activity can reverse this. Ask for an HbA1c test."
        else:
            s, d, t = "action", "In the diabetes range.", "A single reading is not a diagnosis, so see a doctor to confirm it."
        items.append(factor("glucose", "Fasting blood sugar", f"{int(w.fasting_glucose)} mg/dL", s, d, t))

    bmi = bmi_value(w.height_cm, w.weight_kg)
    if bmi is None:
        items.append(factor("bmi", "Body weight", "not provided", "unknown",
                            "Extra weight, especially around the waist, raises heart risk.",
                            "Enter height and weight to see your BMI."))
    else:
        over, obese = (23.0, 27.5) if w.south_asian_cutoffs else (25.0, 30.0)
        if bmi < 18.5:
            s, d, t = "watch", "Below the healthy range.", "If this is unintentional, mention it to a doctor."
        elif bmi < over:
            s, d, t = "good", "In the healthy range.", "Maintain it with regular activity."
        elif bmi < obese:
            s, d, t = "watch", "Above the healthy range.", "A 5 to 10 percent weight loss lowers blood pressure and sugar."
        else:
            s, d, t = "action", "In the obesity range.", "Talk to a doctor about a structured weight-loss plan."
        items.append(factor("bmi", "Body mass index", f"{bmi:.1f}", s, d, t))

    if w.smoking == "current":
        items.append(factor("smoking", "Smoking", "current", "action", "Smoking is among the biggest preventable causes of heart disease.",
                            "Quitting lowers heart risk within the first year. Ask your doctor about quit support."))
    elif w.smoking == "former":
        items.append(factor("smoking", "Smoking", "former", "good", "Quitting has already reduced your risk.",
                            "Stay smoke-free and avoid second-hand smoke."))
    else:
        items.append(factor("smoking", "Smoking", "never", "good", "Not smoking is one of the best things for your heart.",
                            "Keep avoiding tobacco and second-hand smoke."))

    if w.activity_minutes is None:
        items.append(factor("activity", "Physical activity", "not provided", "unknown",
                            "Regular movement protects the heart.", "Aim for about 150 minutes of brisk activity a week."))
    else:
        if w.activity_minutes >= 150:
            s, d, t = "good", "Meets the 150 minutes a week guideline.", "Add strength exercises twice a week."
        elif w.activity_minutes >= 75:
            s, d, t = "watch", "Some activity, below the guideline.", "Add a 10 minute brisk walk after meals."
        else:
            s, d, t = "action", "Well below the 150 minutes a week guideline.", "Start with 10 minute brisk walks and build up."
        items.append(factor("activity", "Physical activity", f"{w.activity_minutes} min/week", s, d, t))

    if w.diabetes:
        items.append(factor("diabetes", "Known diabetes", "yes", "watch", "Diabetes raises heart risk when sugar, blood pressure, and cholesterol are off target.",
                            "Keep regular reviews with your doctor and follow your treatment plan."))
    if w.family_history:
        items.append(factor("family", "Family history", "yes", "watch",
                            "A parent or sibling with early heart disease (men under 55, women under 65) raises your risk.",
                            "Tell your doctor and do not skip routine checks."))

    actions = sum(1 for i in items if i["status"] == "action")
    watches = sum(1 for i in items if i["status"] == "watch")
    unknown = sum(1 for i in items if i["status"] == "unknown")
    if urgent:
        overall = "urgent"
    elif actions >= 2:
        overall = "several"
    elif actions == 1 or watches >= 2:
        overall = "some"
    else:
        overall = "good"
    headline = {
        "urgent": "One reading needs medical advice today",
        "several": "Several risk factors need attention",
        "some": "A few things are worth improving",
        "good": "Your risk factors look favourable",
    }[overall]
    return {
        "overall": overall,
        "headline": headline,
        "factors": items,
        "counts": {"action": actions, "watch": watches, "unknown": unknown},
        "urgent": urgent,
        "context": "Age and sex also shape risk but cannot be changed. This check counts well-known risk factors and is not a prediction of whether you have heart disease.",
        "next_steps": [
            "Ask for a blood pressure, lipid profile, and blood sugar check at your next doctor visit.",
            "If you ever get chest pain or pressure, breathlessness on mild effort, or fainting, use the symptom check or see a doctor.",
            "For a formal 10-year risk estimate, ask your doctor to use a validated population calculator.",
        ],
    }
