import datetime as dt
import logging
import re
import base64
from typing import Annotated, List, Literal, Dict, Any, Optional

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    PrivateAttr,
    StringConstraints,
    ValidationError,
)

logger = logging.getLogger("schemas")


DATE_PARSING_FORMATS: tuple[str] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)
"""Supported date formats for parsing (in precedence order)."""

PASSWORD_COMPLEXITY_RE = re.compile(
    r"^(?=.*[#!$^*@])(?=.*[a-z])(?=.*[A-Z])(?=(?:.*\d){3,}).+$"
)
"""Compiled regex for password complexity validation."""

# === String Constraints for Reusability ===

UsernameStr = Annotated[
    str,
    StringConstraints(
        to_lower=True, strip_whitespace=True, min_length=3, max_length=20
    ),
]
"""Constrained string type for usernames (lowercase, stripped, 3-20 chars)."""

PasswordStr = Annotated[str, StringConstraints(min_length=6)]
"""Constrained string type for passwords (min 6 characters)."""

GenderStr = Literal["None", "m", "w"]
"""Constrained literal for gender selection: 'm', 'w', or 'None'."""

UserGoal = Literal["weight_loss", "weight_maintenance", "weight_gain"]
"""Constrained literal for user fitness goals."""


# === Date Handling Classes ===


class DateMixin(BaseModel):
    """
    Mixin base class providing reusable datetime parsing functionality.

    Supported Date Formats (in order of precedence):
        1. "%Y-%m-%d %H:%M:%S" (e.g., "2024-04-23 10:30:00")
        2. "%Y-%m-%dT%H:%M:%S" (e.g., "2024-04-23T10:30:00")
        3. "%Y-%m-%d" (e.g., "2024-04-23")


    Note:
        If parsing fails for all formats, returns current datetime.
    """

    @staticmethod
    def _parse_datetime(value: str) -> dt.datetime:
        """
        Parses a datetime string into a datetime object.

        Args:
            value (str): Date string in one of the supported formats.

        Returns:
            dt.datetime: Parsed datetime object.

        Note:
            If parsing fails for all formats, returns current datetime (dt.datetime.now()).
        """
        for fmt in DATE_PARSING_FORMATS:
            try:
                return dt.datetime.strptime(value, fmt)
            except Exception:
                continue
        logger.debug(f"Failed to parse date '{value}', falling back to now()")
        return dt.datetime.now()

    model_config = {"arbitrary_types_allowed": True}


class SingleDate(DateMixin):
    """
    Model for single date input with automatic parsing and validation.

    Used for endpoints that require a single date parameter, such as
    fetching daily logs or records for a specific day.

    Attributes:
        date (str, optional): Date string. Defaults to today if empty.
            Supported formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS

    Properties:
        parsed_date (dt.datetime): Parsed datetime object (read/write).
    """

    date: str = Field(
        default="", description="Date (YYYY-MM-DD). Defaults to today if empty."
    )
    _parsed_date: dt.datetime = PrivateAttr(default_factory=dt.datetime.now)

    @model_validator(mode="after")
    def parse_date(self) -> "SingleDate":
        """
        Validates and parses the date string.

        Empty string defaults to today's date.

        Returns:
            SingleDate: The validated model instance with parsed date.
        """
        if not self.date:
            self._parsed_date = dt.datetime.now()
        else:
            self._parsed_date = self._parse_datetime(self.date)
        return self

    @property
    def parsed_date(self) -> dt.datetime:
        """
        Returns the parsed datetime object.

        Returns:
            dt.datetime: The parsed date.
        """
        return self._parsed_date

    @parsed_date.setter
    def parsed_date(self, value: dt.datetime) -> None:
        """
        Sets custom datetime (overrides automatic parsing).

        Args:
            value (dt.datetime): The datetime to set.
        """
        self._parsed_date = value


class DateRange(DateMixin):
    """
    Model for date range queries with automatic parsing and validation.

    Used for endpoints that require a start and end date, such as
    fetching nutrition history or progress reports over a time period.

    Attributes:
        start (str, optional): Start date string. Defaults to today if empty.
        end (str, optional): End date string. Defaults to today if empty.

    Properties:
        st_time_span (dt.datetime): Parsed start datetime object (read/write).
        fin_time_span (dt.datetime): Parsed end datetime object (read/write).

    Raises:
        ValidationError: If start date is after end date.
    """

    start: str = Field(
        default="", description="Start date (YYYY-MM-DD). Defaults to today if empty."
    )
    end: str = Field(
        default="", description="End date (YYYY-MM-DD). Defaults to today if empty."
    )

    _parsed_start: dt.datetime = PrivateAttr(default_factory=dt.datetime.now)
    _parsed_end: dt.datetime = PrivateAttr(default_factory=dt.datetime.now)

    @model_validator(mode="after")
    def parse_dates(self) -> "DateRange":
        """
        Validates and parses both date strings.

        Empty strings default to today's date.
        Validates that start date is not after end date.

        Returns:
            DateRange: The validated model instance with parsed dates.

        Raises:
            ValidationError: If start date is after end date.
        """
        if not self.start:
            self._parsed_start = dt.datetime.now()
        else:
            self._parsed_start = self._parse_datetime(self.start)

        if not self.end:
            self._parsed_end = dt.datetime.now()
        else:
            self._parsed_end = self._parse_datetime(self.end)

        if self._parsed_start > self._parsed_end:
            raise ValidationError("Start date cannot be after end date")

        return self

    @property
    def st_time_span(self) -> dt.datetime:
        """
        Returns the parsed start datetime object.

        Returns:
            dt.datetime: The parsed start date.
        """
        return self._parsed_start

    @st_time_span.setter
    def st_time_span(self, value: dt.datetime) -> None:
        """
        Sets custom start datetime (overrides automatic parsing).

        Args:
            value (dt.datetime): The datetime to set.
        """
        self._parsed_start = value

    @property
    def fin_time_span(self) -> dt.datetime:
        """
        Returns the parsed end datetime object.

        Returns:
            dt.datetime: The parsed end date.
        """
        return self._parsed_end

    @fin_time_span.setter
    def fin_time_span(self, value: dt.datetime) -> None:
        """
        Sets custom end datetime (overrides automatic parsing).

        Args:
            value (dt.datetime): The datetime to set.
        """
        self._parsed_end = value


# === User Models ===


class User(BaseModel):
    """
    Pydantic model for user profile data with automatic nutrition norms calculation.

    Calculates daily caloric intake and macronutrient distribution using the
    Mifflin-St Jeor equation when the model is instantiated or validated.
    LLM-based BMR calculation is handled in the endpoint layer, not in this model.

    Attributes:
        age (int): User's age in years. Range: 10-120.
        bmr (Optional[float]): Activity level multiplier. Range: 0-5.
            Example: 1.2=sedentary, 1.55=moderate. Calculated via LLM or provided explicitly.
        lifestyle_description (Optional[str]): User's lifestyle description or selected preset.
            Max length: 300 characters. Used for analytics and profile display.
        gender (GenderStr): User's gender. Allowed values: 'm', 'w', 'None'.
        goal (UserGoal): User's fitness goal.
            Allowed: 'weight_loss', 'weight_maintenance', 'weight_gain'.
        weight (float): User's weight in kilograms. Range: 20-500.
        height (float): User's height in centimeters. Range: 50-250.

    Properties (calculated automatically):
        norm_calories (float): Daily caloric needs based on BMR and activity.
        norm_proteins (float): Daily protein needs in grams.
        norm_fats (float): Daily fat needs in grams.
        norm_carbohydrates (float): Daily carbohydrate needs in grams.
    """

    age: int = Field(ge=10, le=120, description="User's age in years (10-120)")
    bmr: Optional[float] = Field(
        gt=0, le=5, description="Activity level multiplier (0-5)"
    )
    lifestyle_description: Optional[str] = Field(
        default=None,
        max_length=300,
        description="User's lifestyle description or selected activity preset",
    )
    gender: GenderStr = Field(
        default="None", description="User's gender: 'm' (male), 'w' (female), or 'None'"
    )
    goal: UserGoal = Field(
        default="weight_maintenance",
        description="User's goal: 'weight_loss', 'weight_maintenance' or 'weight_gain'",
    )
    weight: float = Field(ge=20, le=500, description="Weight in kilograms (20-500)")
    height: float = Field(ge=50, le=250, description="Height in centimeters (50-250)")

    _norm_calories: float = PrivateAttr(default=0)
    _norm_proteins: float = PrivateAttr(default=0)
    _norm_fats: float = PrivateAttr(default=0)
    _norm_carbohydrates: float = PrivateAttr(default=0)

    @model_validator(mode="after")
    def calculate_nutrition_norms(self) -> "User":
        """
        Calculates daily nutrition norms using Mifflin-St Jeor with goal adjustments.

        Uses effective_bmr: either the provided value or a safe default (1.375).
        This method does NOT perform LLM calls; BMR calculation via LLM is handled
        in the endpoint layer before model instantiation.

        Returns:
            Self: The validated model instance with calculated nutrition norms.
        """
        effective_bmr = self.bmr if self.bmr else 1.375

        base = 10 * self.weight + 6.25 * self.height - 5 * self.age
        if self.gender == "m":
            base += 5
        elif self.gender == "w":
            base -= 161
        else:
            base -= 78

        tdee = base * effective_bmr

        if self.goal == "weight_loss":
            target_calories = tdee - 300
            protein_factor = 1.6
            fat_ratio = 0.30
        elif self.goal == "weight_gain":
            target_calories = tdee + 300
            protein_factor = 1.8
            fat_ratio = 0.25
        else:
            target_calories = tdee
            protein_factor = 1.2
            fat_ratio = 0.30

        min_calories = (
            1200 if self.gender == "w" else (1500 if self.gender == "m" else 1400)
        )
        target_calories = max(target_calories, min_calories)

        if self.goal == "weight_loss":
            target_calories = max(target_calories, tdee * 0.75)

        self._norm_calories = round(target_calories, 1)

        protein_g = self.weight * protein_factor
        protein_cal = protein_g * 4

        fat_cal = target_calories * fat_ratio
        fat_g = fat_cal / 9

        carbs_cal = target_calories - protein_cal - fat_cal
        carbs_g = max(0, carbs_cal / 4)

        self._norm_proteins = round(protein_g, 1)
        self._norm_fats = round(fat_g, 1)
        self._norm_carbohydrates = round(carbs_g, 1)

        return self

    @property
    def norm_calories(self) -> float:
        """
        Returns calculated daily caloric needs.

        Returns:
            float: Daily caloric target.
        """
        return self._norm_calories

    @property
    def norm_proteins(self) -> float:
        """
        Returns calculated daily protein needs in grams.

        Returns:
            float: Daily protein target in grams.
        """
        return self._norm_proteins

    @property
    def norm_fats(self) -> float:
        """
        Returns calculated daily fat needs in grams.

        Returns:
            float: Daily fat target in grams.
        """
        return self._norm_fats

    @property
    def norm_carbohydrates(self) -> float:
        """
        Returns calculated daily carbohydrate needs in grams.

        Returns:
            float: Daily carbohydrate target in grams.
        """
        return self._norm_carbohydrates


class LoginInput(BaseModel):
    """
    Input model for user authentication.

    Used for the /authentication endpoint to obtain a JWT access token.

    Attributes:
        username (str): User's unique username.
        password (str): User's password (plain text, will be hashed for verification).
    """

    username: str = Field(description="User's unique username")
    password: str = Field(description="User's password")


class RegisterInput(User):
    """
    Input model for user registration.

    Extends User model with authentication credentials (username, password).
    Used for the /registration endpoint to create a new user account.

    Attributes:
        username (UsernameStr): Unique username (3-20 chars, lowercase, no whitespace).
        password (PasswordStr): Password (min 6 chars, must contain special char,
            uppercase, lowercase, and 3+ digits).
        age, bmr, gender, goal, weight, height: Inherited from User model.

    Password Requirements:
        - At least one special character (#!$^*@)
        - At least one lowercase letter
        - At least one uppercase letter
        - At least 3 digits
    """

    username: UsernameStr = Field(description="Unique username (3-20 characters)")
    password: PasswordStr = Field(description="Password (min 6 characters)")

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        Validates password meets complexity requirements.

        Args:
            v (str): Password string to validate.

        Returns:
            str: The validated password.

        Raises:
            ValidationError: If password does not meet complexity requirements.
        """
        if not PASSWORD_COMPLEXITY_RE.match(v):
            raise ValidationError(
                "Password must contain: special char (#!$^*@), uppercase, lowercase, and 3+ digits"
            )
        return v


# === Nutrition Models ===


class IngredientRecognitionInput(BaseModel):
    """
    Input model for ingredient recognition from food image.

    Used for the /ingredient_recognition endpoint to analyze food images
    and identify ingredients with their nutritional information.

    Attributes:
        image_base64 (str): Base64-encoded image data. Required.
            - Must be a valid Base64 string
            - Supported formats: JPEG, PNG, WebP
            - Recommended max size: 5MB
        user_description (str, optional): Custom description of the meal.
            - Helps improve recognition accuracy
            - Max length: 500 characters
    """

    image_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded image data (JPEG, PNG, or WebP). Required.",
    )
    user_description: str = Field(
        default="",
        max_length=500,
        description="Optional custom description of the meal to improve recognition accuracy.",
    )

    @field_validator("image_base64")
    @classmethod
    def validate_base64_format(cls, v: str) -> str:
        """
        Validates that the input is a valid Base64-encoded string.

        Args:
            v (str): The Base64 string to validate.

        Returns:
            str: The validated Base64 string.

        Raises:
            ValidationError: If the string is not valid Base64 format.
        """
        if v.startswith("data:"):
            v = v.split(",", 1)[-1]

        v = v.strip()

        try:
            base64.b64decode(v, validate=True)
        except Exception as e:
            logger.debug(f"Base64 validation failed: {e}")
            raise ValidationError(f"Invalid Base64 format: {str(e)}")

        return v


class NutritionOutput(BaseModel):
    """
    Output model for nutrition calculation results.

    Returned by the /daily_nutrition_norms endpoint with calculated
    daily caloric and macronutrient targets.

    Attributes:
        calories (int): Daily caloric target. Range: 400-10000 kcal.
        proteins (float): Daily protein target in grams. Range: 0-1000g.
        fats (float): Daily fat target in grams. Range: 0-1000g.
        carbohydrates (float): Daily carbohydrate target in grams. Range: 0-1000g.
    """

    calories: int = Field(
        ge=400, le=10000, description="Daily caloric target (400-10000 kcal)"
    )
    proteins: float = Field(ge=0, le=1000, description="Daily protein target (0-1000g)")
    fats: float = Field(ge=0, le=1000, description="Daily fat target (0-1000g)")
    carbohydrates: float = Field(
        ge=0, le=1000, description="Daily carbohydrate target (0-1000g)"
    )


class IngredientItem(BaseModel):
    """
    Ingredient with per-100g nutritional values (internal format).

    Input: actual values → converted to per-100g by DishPayload validator.
    Output: per-100g values → converted to actual by to_actual() for API.

    Attributes:
        name (str): Ingredient name (1-255 chars).
        weight (float): Portion weight in grams (0-10000).
        calories (float): Calories per 100g (0-10000).
        proteins (float): Proteins per 100g in grams (0-1000).
        fats (float): Fats per 100g in grams (0-1000).
        carbohydrates (float): Carbohydrates per 100g in grams (0-1000).
        owner (str): Owner username (default: "admin").
    """

    name: str = Field(min_length=1, max_length=255)
    weight: float = Field(ge=0, le=10000.0)
    calories: float = Field(ge=0, le=10000.0)
    proteins: float = Field(ge=0, le=1000.0)
    fats: float = Field(ge=0, le=1000.0)
    carbohydrates: float = Field(ge=0, le=1000.0)
    owner: str = Field(min_length=1, max_length=255, default="admin")

    def to_actual(self) -> Dict[str, Any]:
        """
        Converts per-100g values to actual values for API response.

        Returns:
            Dict[str, Any]: Dictionary with actual nutritional values for the portion:
                name (str): Ingredient name.
                weight (float): Portion weight in grams.
                calories (float): Calories for the portion.
                proteins (float): Proteins in grams for the portion.
                fats (float): Fats in grams for the portion.
                carbohydrates (float): Carbohydrates in grams for the portion.
                owner (str): Owner username.
        """
        factor = self.weight / 100.0
        return {
            "name": self.name,
            "weight": self.weight,
            "calories": round(self.calories * factor, 1),
            "proteins": round(self.proteins * factor, 1),
            "fats": round(self.fats * factor, 1),
            "carbohydrates": round(self.carbohydrates * factor, 1),
            "owner": self.owner,
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns per-100g values for internal use.

        Returns:
            Dict[str, Any]: Dict with per-100g nutritional values.
        """
        return self.model_dump()


class DishPayload(SingleDate):
    """
    Input model for adding ingredients to a day record.

    Converts actual values → per-100g on validation.
    All internal operations use per-100g format.

    Attributes:
        table (List[Dict]): List of ingredient dicts with actual values.
        modified_ingredients (List[Dict]): List of modified ingredient dicts.

    Properties:
        parse_table (List[IngredientItem]): Ingredients with per-100g values.
        parse_modified_ingredients (List[IngredientItem]): Modified ingredients with per-100g values.
    """

    table: List[Dict] = Field(min_length=1)
    modified_ingredients: List[Dict] = Field(min_length=0)

    _table: List[IngredientItem] = PrivateAttr(default_factory=list)
    _modified_ingredients: List[IngredientItem] = PrivateAttr(default_factory=list)

    @staticmethod
    def _convert_to_per100g(ing: Dict[str, Any]) -> IngredientItem:
        """Converts actual values to per-100g format.

        Args:
            ing (Dict[str, Any]): Dictionary with actual nutritional values and weight.

        Returns:
            IngredientItem: Ingredient model with per-100g values.
        """
        weight = ing["weight"]
        factor = 100.0 / weight if weight > 0 else 0.0
        return IngredientItem(
            name=ing["name"].lower().strip(),
            weight=weight,
            calories=ing["calories"] * factor,
            proteins=ing["proteins"] * factor,
            fats=ing["fats"] * factor,
            carbohydrates=ing["carbohydrates"] * factor,
            owner=ing.get("owner", "admin").lower().strip(),
        )

    @model_validator(mode="after")
    def convert_and_validate(self) -> "DishPayload":
        self._table = [self._convert_to_per100g(ing) for ing in self.table]
        self._modified_ingredients = [
            self._convert_to_per100g(ing) for ing in self.modified_ingredients
        ]
        return self

    @property
    def parse_table(self) -> List[IngredientItem]:
        """
        Returns ingredients with per-100g values.

        Returns:
            List[IngredientItem]: List of validated ingredients.
        """
        return self._table

    @property
    def parse_modified_ingredients(self) -> List[IngredientItem]:
        """
        Returns ingredients with per-100g values.

        Returns:
            List[IngredientItem]: List of modified validated ingredients.
        """
        return self._modified_ingredients


class TranslatorInput(BaseModel):
    """
    Input model for ingredient translation requests.

    Used for the /translate_ingredients endpoint to batch-translate
    ingredient names to target languages.

    Attributes:
        ingredients (Dict[str, List[str]]): Dictionary mapping ingredient names
            to lists of target language codes.
            Example: {"яйцо": ["en", "de"], "butter, salted": ["ru"]}

    Note:
        Empty `ingredients` dict is valid and returns empty result without error.
    """

    ingredients: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dict mapping ingredient names to target language codes.",
    )
