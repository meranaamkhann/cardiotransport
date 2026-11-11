from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

EmergencyFlag = Literal["pain_at_rest", "pain_spreading", "fainting", "sudden_breathlessness"]


class LocalCalibration(BaseModel):
    tier: Literal["core", "clinical"]
    intercept: float = Field(ge=-8, le=8)
    slope: float = Field(ge=0.1, le=3)
    label: Optional[str] = Field(default=None, max_length=80)
    n: Optional[int] = Field(default=None, ge=0)


class Assessment(BaseModel):
    pathway: Literal["symptomatic", "referred"]
    age: int = Field(ge=18, le=100)
    sex: Literal["female", "male"]
    chest_pain: Literal["typical", "atypical", "non_anginal", "none"]
    exercise_pain: bool
    systolic: Optional[float] = Field(default=None, ge=70, le=260)
    cholesterol: Optional[float] = Field(default=None, ge=80, le=700)
    fasting_glucose: Optional[float] = Field(default=None, ge=40, le=700)
    ecg: Optional[Literal["normal", "st_t_abnormality", "lv_hypertrophy"]] = None
    max_hr: Optional[float] = Field(default=None, ge=60, le=230)
    st_depression: Optional[float] = Field(default=None, ge=-3, le=8)
    emergency: List[EmergencyFlag] = Field(default_factory=list)
    local_calibrations: List[LocalCalibration] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def pathway_matches_symptoms(self):
        if self.pathway == "symptomatic" and self.chest_pain == "none":
            raise ValueError("The symptom pathway needs a chest pain pattern; use the referral pathway otherwise.")
        return self


class Wellness(BaseModel):
    age: int = Field(ge=18, le=100)
    sex: Literal["female", "male"]
    systolic: Optional[float] = Field(default=None, ge=70, le=260)
    diastolic: Optional[float] = Field(default=None, ge=40, le=160)
    cholesterol: Optional[float] = Field(default=None, ge=80, le=700)
    fasting_glucose: Optional[float] = Field(default=None, ge=40, le=700)
    height_cm: Optional[float] = Field(default=None, ge=120, le=230)
    weight_kg: Optional[float] = Field(default=None, ge=30, le=250)
    smoking: Literal["never", "former", "current"]
    diabetes: bool = False
    family_history: bool = False
    activity_minutes: Optional[int] = Field(default=None, ge=0, le=3000)
    south_asian_cutoffs: bool = True


Level = Literal["routine", "soon", "prompt", "urgent", "emergency"]
Condition = Literal["hypertension", "diabetes", "high_cholesterol", "previous_heart_disease", "family_history"]


class Credentials(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=128)


class Registration(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    clinic_code: Optional[str] = Field(default=None, max_length=16)


class ClinicRegistration(BaseModel):
    clinic_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)


class StaffCreate(BaseModel):
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["clinician", "researcher", "clinic_admin"]


class JoinClinic(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class ProfileUpdate(BaseModel):
    sex: Optional[Literal["female", "male"]] = None
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    height_cm: Optional[float] = Field(default=None, ge=120, le=230)
    smoking: Optional[Literal["never", "former", "current"]] = None
    diabetes: Optional[bool] = None
    family_history: Optional[bool] = None
    conditions: Optional[List[Condition]] = None
    activity_minutes: Optional[int] = Field(default=None, ge=0, le=3000)


class SymptomAssessment(BaseModel):
    chest_discomfort: Literal["none", "typical", "atypical", "non_anginal"]
    discomfort_with_effort: bool = False
    breathlessness: Literal["none", "on_exertion", "at_rest"] = "none"
    palpitations: bool = False
    dizziness: bool = False
    fatigue: bool = False
    duration: Literal["minutes", "hours", "days", "weeks", "months"]
    severity: int = Field(ge=1, le=10)
    emergency: List[EmergencyFlag] = Field(default_factory=list)
    conditions: List[Condition] = Field(default_factory=list)
    systolic: Optional[float] = Field(default=None, ge=70, le=260)
    cholesterol: Optional[float] = Field(default=None, ge=80, le=700)
    fasting_glucose: Optional[float] = Field(default=None, ge=40, le=700)
    ecg: Optional[Literal["normal", "st_t_abnormality", "lv_hypertrophy"]] = None
    max_hr: Optional[float] = Field(default=None, ge=60, le=230)
    st_depression: Optional[float] = Field(default=None, ge=-3, le=8)


class WellnessAssessment(BaseModel):
    systolic: Optional[float] = Field(default=None, ge=70, le=260)
    diastolic: Optional[float] = Field(default=None, ge=40, le=160)
    cholesterol: Optional[float] = Field(default=None, ge=80, le=700)
    fasting_glucose: Optional[float] = Field(default=None, ge=40, le=700)
    weight_kg: Optional[float] = Field(default=None, ge=30, le=250)
    activity_minutes: Optional[int] = Field(default=None, ge=0, le=3000)
    save_measurements: bool = True
    south_asian_cutoffs: bool = True


MeasurementKind = Literal["systolic", "diastolic", "cholesterol", "glucose", "weight", "resting_hr"]


class MeasurementCreate(BaseModel):
    kind: MeasurementKind
    value: float = Field(gt=0, le=1000)
    measured_at: Optional[datetime] = None


class AppointmentCreate(BaseModel):
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=255)
    clinician_id: Optional[int] = None


class AppointmentUpdate(BaseModel):
    status: Literal["requested", "confirmed", "completed", "cancelled"]
    scheduled_at: Optional[datetime] = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    assessment_id: Optional[int] = None


class ReviewCreate(BaseModel):
    summary: str = Field(min_length=3, max_length=3000)


class DeleteAccount(BaseModel):
    password: str = Field(min_length=1, max_length=128)
