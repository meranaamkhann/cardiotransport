from ..schemas import SymptomAssessment

LEVELS = ["routine", "soon", "prompt", "urgent", "emergency"]

LEVEL_TEXT = {
    "routine": ("Routine follow-up", "Mention these symptoms at your next routine check-up and keep monitoring them."),
    "soon": ("See a doctor in the coming weeks", "Book a non-urgent appointment and bring this report."),
    "prompt": ("See a doctor within a few days", "Arrange a medical review within the next few days and avoid strenuous effort until then."),
    "urgent": ("Get medical care today", "Contact a doctor or urgent care today. If symptoms worsen, call your emergency number."),
    "emergency": ("Call emergency services now", "Your answers include warning signs that can mean a heart attack. Call your local emergency number (112 in India, 911 in the US, 999 in the UK) and do not drive yourself."),
}

LABELS = {
    "pain_at_rest": "chest pain at rest lasting more than 15 minutes",
    "pain_spreading": "pain spreading to the arm, jaw or back with sweating or nausea",
    "fainting": "fainting or nearly fainting",
    "sudden_breathlessness": "sudden severe breathlessness",
}


def rank(level: str) -> int:
    return LEVELS.index(level)


def higher(a: str, b: str) -> str:
    return a if rank(a) >= rank(b) else b


def triage(s: SymptomAssessment) -> dict:
    level, reasons = "routine", []

    def raise_to(new, reason):
        nonlocal level
        level = higher(level, new)
        reasons.append(reason)

    chest = s.chest_discomfort != "none"
    recent = s.duration in ("minutes", "hours")
    for flag in s.emergency:
        raise_to("emergency", f"You reported {LABELS[flag]}.")
    if chest and s.severity >= 8 and recent:
        raise_to("emergency", "Severe chest discomfort of recent onset.")
    if s.breathlessness == "at_rest" and (chest or s.dizziness):
        raise_to("emergency", "Breathlessness at rest together with chest discomfort or dizziness.")
    if chest and s.discomfort_with_effort and s.duration != "months" and s.severity >= 5:
        raise_to("urgent", "Chest discomfort brought on by effort that is recent and moderately severe.")
    if s.breathlessness == "at_rest":
        raise_to("urgent", "Breathlessness at rest.")
    if s.palpitations and s.dizziness:
        raise_to("urgent", "Palpitations with dizziness.")
    if chest and s.severity >= 7:
        raise_to("urgent", "Severe chest discomfort.")
    if "previous_heart_disease" in s.conditions and chest:
        raise_to("prompt", "Chest discomfort in someone with known heart disease.")
    if chest and (s.discomfort_with_effort or s.chest_discomfort == "typical"):
        raise_to("prompt", "Chest discomfort with an effort-related or typical pattern.")
    if chest:
        raise_to("soon", "Chest discomfort that should be evaluated.")
    if s.breathlessness == "on_exertion":
        raise_to("soon", "Breathlessness on exertion.")
    if s.palpitations or s.dizziness:
        raise_to("soon", "Palpitations or dizziness.")
    if not reasons and s.fatigue:
        reasons.append("Fatigue alone is common and rarely an emergency, but persistent fatigue deserves a check-up.")
    if not reasons:
        reasons.append("No concerning symptom pattern was reported.")
    title, message = LEVEL_TEXT[level]
    return {"level": level, "title": title, "message": message, "reasons": reasons,
            "limits": "A questionnaire cannot rule out a heart attack. If you feel something is seriously wrong, seek care regardless of this result."}
