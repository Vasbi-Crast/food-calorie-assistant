import datetime as dt
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated, List
from pydantic import StringConstraints, PrivateAttr
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

    name: str = Field(min_length=1, max_length=25)
    weight: float = Field(ge=0, le=10000.0)
    calories: float = Field(ge=0, le=10000.0)
    proteins: float = Field(ge=0, le=1000.0)
    fats: float = Field(ge=0, le=1000.0)
    carbohydrates: float = Field(ge=0, le=1000.0)


class DishPayload(BaseModel):
    """
    Input format: dictionary of lists.
    Example: {"name": ["apple", "sugar"], "weight": [100, 50], ...}
    """

    created_at: str = Field(
        default_factory=lambda: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    name: List[str] = Field(min_length=1)
    weight: List[float] = Field(min_length=1)
    calories: List[float] = Field(min_length=1)
    proteins: List[float] = Field(min_length=1)
    fats: List[float] = Field(min_length=1)
    carbohydrates: List[float] = Field(min_length=1)

    _parsed_created_at: dt.datetime = PrivateAttr(default_factory=dt.datetime.now)
    _ingredients: List[IngredientItem] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def convert_and_validate(self):
        """Convert dictionary of lists → list of objects with validation."""

        names_len = len(self.name)

        fields = ["weight", "calories", "proteins", "fats", "carbohydrates"]
        for field in fields:
            field_value = getattr(self, field)
            if len(field_value) != names_len:
                raise ValueError(
                    f"Length mismatch: 'name' has {names_len} items, "
                    f"but '{field}' has {len(field_value)} items"
                )

        self.parsed_created_at = self._parse_datetime(self.created_at)

        self.ingredients = [
            IngredientItem(
                name=self.name[i],
                weight=self.weight[i],
                calories=(
                    (self.calories[i] / self.weight[i] * 100)
                    if self.weight[i] > 0
                    else 0.0
                ),
                proteins=(
                    (self.proteins[i] / self.weight[i] * 100)
                    if self.weight[i] > 0
                    else 0.0
                ),
                fats=(
                    (self.fats[i] / self.weight[i] * 100) if self.weight[i] > 0 else 0.0
                ),
                carbohydrates=(
                    (self.carbohydrates[i] / self.weight[i] * 100)
                    if self.weight[i] > 0
                    else 0.0
                ),
                created_at=self.created_at[i],
            )
            for i in range(names_len)
        ]

        return self

    @staticmethod
    def _parse_datetime(value: str) -> dt.datetime:
        """Parses datetime string to datetime object."""
        formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
        return dt.datetime.now()

    @property
    def ingredients(self) -> List[IngredientItem]:
        """Get converted ingredients list."""
        return self._ingredients

    @ingredients.setter
    def ingredients(self, value: List[IngredientItem]):
        self._ingredients = value

    @property
    def parsed_created_at(self) -> dt.datetime:
        """Get parsed datetime object."""
        return self._parsed_created_at

    @parsed_created_at.setter
    def parsed_created_at(self, value: dt.datetime):
        self._parsed_created_at = value
