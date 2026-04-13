from pydantic import BaseModel, Field, field_validator
from typing import Annotated
from pydantic import StringConstraints
import re


# === String Constraints for Reusability ===

UsernameStr = Annotated[str, StringConstraints(to_lower=True, strip_whitespace=True, min_length=3, max_length=20)]
PasswordStr = Annotated[str, StringConstraints(min_length=6)]
GenderStr = Annotated[str, StringConstraints(pattern=r"^(None)|(m)|(w)$")]


class LoginInput(BaseModel):
    """Input model for user authentication"""
    
    username: UsernameStr
    password: PasswordStr

    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        pattern = r"^(?=.*[#!$^*@])(?=.*[a-z])(?=.*[A-Z])(?=.*\d{3,}).+$"
        if not re.match(pattern, v):
            raise ValueError("Incorrect password")
        return v


class RegisterInput(LoginInput):
    """Input model for user registration (extends LoginInput)"""

    age: int = Field(ge=10, le=120)
    bmr: float = Field(gt=0, le=5)
    gender: GenderStr
    weight: float = Field(ge=20, le=500)
    height: float = Field(ge=50, le=250)


class NutritionInput(BaseModel):
    """Input model for nutrition calculation"""
    
    age: int = Field(ge=10, le=120)
    bmr: float = Field(gt=0, le=5)
    gender: GenderStr
    weight: float = Field(ge=20, le=500)
    height: float = Field(ge=50, le=250)


class NutritionOutput(BaseModel):
    """Output model for nutrition calculation results"""
    
    calories: int = Field(ge=0, le=10000)
    proteins: float = Field(ge=0, le=1000)
    fats: float = Field(ge=0, le=1000)
    carbohydrates: float = Field(ge=0, le=1000)