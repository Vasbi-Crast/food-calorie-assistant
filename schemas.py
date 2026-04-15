from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated, List
from pydantic import StringConstraints
import re


# === String Constraints for Reusability ===

UsernameStr = Annotated[
    str,
    StringConstraints(
        to_lower=True, strip_whitespace=True, min_length=3, max_length=20
    ),
]
PasswordStr = Annotated[str, StringConstraints(min_length=6)]
GenderStr = Annotated[str, StringConstraints(pattern=r"^(None)|(m)|(w)$")]


class LoginInput(BaseModel):
    """Input model for user authentication"""

    username: str
    password: str


class RegisterInput(BaseModel):
    """Input model for user registration"""

    username: UsernameStr
    password: PasswordStr
    age: int = Field(ge=10, le=120)
    bmr: float = Field(gt=0, le=5)
    gender: GenderStr
    weight: float = Field(ge=20, le=500)
    height: float = Field(ge=50, le=250)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        pattern = r"^(?=.*[#!$^*@])(?=.*[a-z])(?=.*[A-Z])(?=.*\d{3,}).+$"
        if not re.match(pattern, v):
            raise ValueError("Incorrect password")
        return v


class SettingsInput(BaseModel):
    """Input model for user settings"""
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


class IngredientItem(BaseModel):
    """Model representing a single ingredient."""
    
    name: str = Field(min_length=1, max_length=25, description="Ingredient name")
    weight: float = Field(ge=0, le=10000.0, description="Weight in grams")
    calories: float = Field(ge=0, le=10000.0, description="Calories per ingredient")
    proteins: float = Field(ge=0, le=1000.0, description="Proteins in grams")
    fats: float = Field(ge=0, le=1000.0, description="Fats in grams")
    carbohydrates: float = Field(ge=0, le=1000.0, description="Carbohydrates in grams")


class DishPayload(BaseModel):
    """
    Input format: dictionary of lists.
    Example: {"name": ["apple", "sugar"], "weight": [100, 50], ...}
    """
    
    name: List[str] = Field(min_length=1, description="List of ingredient names")
    weight: List[float] = Field(min_length=1, description="List of weights in grams")
    calories: List[float] = Field(min_length=1, description="List of calories")
    proteins: List[float] = Field(min_length=1, description="List of proteins in grams")
    fats: List[float] = Field(min_length=1, description="List of fats in grams")
    carbohydrates: List[float] = Field(min_length=1, description="List of carbohydrates in grams")

    ingredients: List[IngredientItem] = Field(default=[], init=False)

    @model_validator(mode='after')
    def convert_and_validate(self):
        """Convert dictionary of lists → list of objects with validation."""

        names_len = len(self.name)

        fields = ['weight', 'calories', 'proteins', 'fats', 'carbohydrates']
        for field in fields:
            field_value = getattr(self, field)
            if len(field_value) != names_len:
                raise ValueError(
                    f"Length mismatch: 'name' has {names_len} items, "
                    f"but '{field}' has {len(field_value)} items"
                )

        self.ingredients = [
            IngredientItem(
                name=self.name[i],
                weight=self.weight[i],
                calories=self.calories[i],
                proteins=self.proteins[i],
                fats=self.fats[i],
                carbohydrates=self.carbohydrates[i],
            )
            for i in range(names_len)
        ]
        
        return self
    
