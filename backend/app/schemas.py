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
