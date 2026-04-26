import datetime as dt
from pydantic import BaseModel, Field, field_validator, model_validator, PrivateAttr
from typing import Annotated, List, ClassVar, Dict
from pydantic import StringConstraints
import re
import base64


# === String Constraints for Reusability ===

UsernameStr = Annotated[
    str,
    StringConstraints(
        to_lower=True, strip_whitespace=True, min_length=3, max_length=20
    ),
]
"""
Constrained string type for usernames.

Constraints:
    - Converted to lowercase
    - Whitespace stripped from both ends
    - Minimum length: 3 characters
    - Maximum length: 20 characters

Example:
    >>> username: UsernameStr = "JohnDoe"  # Valid
    >>> username: UsernameStr = "ab"       # Invalid (too short)
"""

PasswordStr = Annotated[str, StringConstraints(min_length=6)]
"""
Constrained string type for passwords.

Constraints:
    - Minimum length: 6 characters

Note:
    Additional complexity validation is performed in RegisterInput validator.
"""

GenderStr = Annotated[str, StringConstraints(pattern=r"^(None)|(m)|(w)$")]
"""
Constrained string type for gender selection.

Allowed values:
    - 'm': Male
    - 'w': Female
    - 'None': Unspecified/Other

Example:
    >>> gender: GenderStr = "m"      # Valid
    >>> gender: GenderStr = "other"  # Invalid
"""


# === Date Handling Classes ===


class DateMixin(BaseModel):
    """
    Mixin base class providing reusable datetime parsing functionality.

    This class defines common date parsing logic supporting multiple formats
    across the application. It should not be instantiated directly — use
    SingleDate or DateRange instead.

    Supported Date Formats (in order of precedence):
        1. "%Y-%m-%d %H:%M:%S" (e.g., "2024-04-23 10:30:00")
        2. "%Y-%m-%dT%H:%M:%S" (e.g., "2024-04-23T10:30:00")
        3. "%Y-%m-%d" (e.g., "2024-04-23")

    Class Attributes:
        DATE_FORMATS (ClassVar[List[str]]): List of supported datetime format strings.

    Methods:
        _parse_datetime(value): Static method to parse date strings.

    Note:
        If parsing fails for all formats, returns current datetime.
    """

    DATE_FORMATS: ClassVar[List[str]] = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    @staticmethod
    def _parse_datetime(value: str) -> dt.datetime:
        """
        Parses a datetime string into a datetime object.

        Args:
            value (str): Date string in one of the supported formats.

        Returns:
            datetime: Parsed datetime object, or current datetime if parsing fails.
        """
        for fmt in DateMixin.DATE_FORMATS:
            try:
                return dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
        return dt.datetime.now()

    model_config = {"arbitrary_types_allowed": True}


class SingleDate(DateMixin):
    """
    Model for single date input with automatic parsing and validation.

    Used for endpoints that require a single date parameter, such as
    fetching daily logs or records for a specific day.

    Query Parameters:
        date (str, optional): Date string. Defaults to today if empty.
            Supported formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS

    Properties:
        parsed_date (datetime): Parsed datetime object (read/write).
    """

    date: str = Field(
        default="", description="Date (YYYY-MM-DD). Defaults to today if empty."
    )
    _parsed_date: dt.datetime = PrivateAttr(default_factory=dt.datetime.now)

    @model_validator(mode="after")
    def parse_date(self):
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
        """Returns the parsed datetime object."""
        return self._parsed_date

    @parsed_date.setter
    def parsed_date(self, value: dt.datetime):
        """Sets custom datetime (overrides automatic parsing)."""
        self._parsed_date = value


class DateRange(DateMixin):
    """
    Model for date range queries with automatic parsing and validation.

    Used for endpoints that require a start and end date, such as
    fetching nutrition history or progress reports over a time period.

    Query Parameters:
        start (str, optional): Start date string. Defaults to today if empty.
        end (str, optional): End date string. Defaults to today if empty.

    Properties:
        st_time_span (datetime): Parsed start datetime object (read/write).
        fin_time_span (datetime): Parsed end datetime object (read/write).

    Raises:
        ValueError: If start date is after end date.
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
    def parse_dates(self):
        """
        Validates and parses both date strings.
        Empty strings default to today's date.
        Validates that start date is not after end date.

        Returns:
            DateRange: The validated model instance with parsed dates.

        Raises:
            ValueError: If start date is after end date.
        """
        # Handle empty strings → default to today
        if not self.start:
            self._parsed_start = dt.datetime.now()
        else:
            self._parsed_start = self._parse_datetime(self.start)

        if not self.end:
            self._parsed_end = dt.datetime.now()
        else:
            self._parsed_end = self._parse_datetime(self.end)

        # Validate date range
        if self._parsed_start > self._parsed_end:
            raise ValueError("Start date cannot be after end date")

        return self

    @property
    def st_time_span(self) -> dt.datetime:
        """Returns the parsed start datetime object."""
        return self._parsed_start

    @st_time_span.setter
    def st_time_span(self, value: dt.datetime):
        """Sets custom start datetime (overrides automatic parsing)."""
        self._parsed_start = value

    @property
    def fin_time_span(self) -> dt.datetime:
        """Returns the parsed end datetime object."""
        return self._parsed_end

    @fin_time_span.setter
    def fin_time_span(self, value: dt.datetime):
        """Sets custom end datetime (overrides automatic parsing)."""
        self._parsed_end = value


# === User Models ===


class User(BaseModel):
    """
    Pydantic model for user profile data with automatic nutrition norms calculation.

    Calculates daily caloric intake and macronutrient distribution using the
    Mifflin-St Jeor equation when the model is instantiated or validated.

    Attributes:
        age (int): User's age in years. Range: 10-120.
        bmr (float): Activity level multiplier. Range: 0-5 (e.g., 1.2=sedentary, 1.55=moderate).
        gender (GenderStr): User's gender. Allowed: 'm', 'w', 'None'.
        weight (float): User's weight in kilograms. Range: 20-500.
        height (float): User's height in centimeters. Range: 50-250.

    Properties (calculated automatically):
        norm_calories (float): Daily caloric needs based on BMR and activity.
        norm_proteins (float): Daily protein needs in grams (30% of calories).
        norm_fats (float): Daily fat needs in grams (30% of calories).
        norm_carbohydrates (float): Daily carbohydrate needs in grams (40% of calories).

    Formula:
        BMR = (10 × weight) + (6.25 × height) - (5 × age) + gender_offset
        Total Calories = BMR × activity_multiplier
    """

    age: int = Field(ge=10, le=120, description="User's age in years (10-120)")
    bmr: float = Field(gt=0, le=5, description="Activity level multiplier (0-5)")
    gender: GenderStr = Field(
        description="User's gender: 'm' (male), 'w' (female), or 'None'"
    )
    weight: float = Field(ge=20, le=500, description="Weight in kilograms (20-500)")
    height: float = Field(ge=50, le=250, description="Height in centimeters (50-250)")

    _norm_calories: float = PrivateAttr(default=0)
    _norm_proteins: float = PrivateAttr(default=0)
    _norm_fats: float = PrivateAttr(default=0)
    _norm_carbohydrates: float = PrivateAttr(default=0)

    @model_validator(mode="after")
    def calculate_nutrition_norms(self):
        """
        Calculates daily nutrition norms using the Mifflin-St Jeor equation.

        Macronutrient ratios (balanced maintenance diet):
            - Proteins: 30% (4 cal/g)
            - Fats: 30% (9 cal/g)
            - Carbohydrates: 40% (4 cal/g)

        Returns:
            User: The validated model instance with calculated norms.
        """
        CAL_PER_G = {"proteins": 4, "fats": 9, "carbohydrates": 4}
        P_RATIO, F_RATIO, C_RATIO = 0.3, 0.3, 0.4

        base = 10 * self.weight + 6.25 * self.height - 5 * self.age
        if self.gender == "m":
            base += 5
        elif self.gender == "w":
            base -= 161
        else:
            base -= 78  # Neutral/averaged fallback for 'None'

        total_calories = base * self.bmr
        self._norm_calories = round(total_calories, 1)
        self._norm_proteins = round(
            (total_calories * P_RATIO) / CAL_PER_G["proteins"], 1
        )
        self._norm_fats = round((total_calories * F_RATIO) / CAL_PER_G["fats"], 1)
        self._norm_carbohydrates = round(
            (total_calories * C_RATIO) / CAL_PER_G["carbohydrates"], 1
        )

        return self

    @property
    def norm_calories(self) -> float:
        """Returns calculated daily caloric needs."""
        return self._norm_calories

    @property
    def norm_proteins(self) -> float:
        """Returns calculated daily protein needs in grams."""
        return self._norm_proteins

    @property
    def norm_fats(self) -> float:
        """Returns calculated daily fat needs in grams."""
        return self._norm_fats

    @property
    def norm_carbohydrates(self) -> float:
        """Returns calculated daily carbohydrate needs in grams."""
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
        age, bmr, gender, weight, height: Inherited from User model.

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
            ValueError: If password does not meet complexity requirements.
        """
        pattern = r"^(?=.*[#!$^*@])(?=.*[a-z])(?=.*[A-Z])(?=.*\d{3,}).+$"
        if not re.match(pattern, v):
            raise ValueError(
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
        user_description (str, optional): Custom description of the dish.
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
        description="Optional custom description of the dish to improve recognition accuracy.",
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
            ValueError: If the string is not valid Base64 format.
        """
        # Remove common data URI prefixes if present
        if v.startswith("data:"):
            v = v.split(",", 1)[-1]

        # Strip whitespace
        v = v.strip()

        # Validate Base64 format
        try:
            base64.b64decode(v, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid Base64 format: {str(e)}")

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
    Model representing a single ingredient with nutritional information.

    Used within DishPayload to represent individual ingredients in a meal.
    All nutritional values are per 100g of the ingredient.

    Attributes:
        name (str): Ingredient name. Length: 1-25 characters.
        weight (float): Weight in grams. Range: 0-10000g.
        calories (float): Calorie content per 100g. Range: 0-10000 kcal.
        proteins (float): Protein content per 100g. Range: 0-1000g.
        fats (float): Fat content per 100g. Range: 0-1000g.
        carbohydrates (float): Carbohydrate content per 100g. Range: 0-1000g.
    """

    name: str = Field(
        min_length=1, max_length=25, description="Ingredient name (1-25 characters)"
    )
    weight: float = Field(ge=0, le=10000.0, description="Weight in grams (0-10000g)")
    calories: float = Field(
        ge=0, le=10000.0, description="Calories per 100g (0-10000 kcal)"
    )
    proteins: float = Field(ge=0, le=1000.0, description="Proteins per 100g (0-1000g)")
    fats: float = Field(ge=0, le=1000.0, description="Fats per 100g (0-1000g)")
    carbohydrates: float = Field(
        ge=0, le=1000.0, description="Carbohydrates per 100g (0-1000g)"
    )


class DishPayload(SingleDate):
    """
    Input model for adding multiple ingredients to a day record.

    Accepts parallel lists of ingredient data and converts them into
    IngredientItem objects with normalized nutritional values (per 100g).

    Attributes:
        created_at (str): Date string for the record. Defaults to current datetime.
        name (List[str]): List of ingredient names.
        weight (List[float]): List of weights in grams.
        calories (List[float]): List of calorie values.
        proteins (List[float]): List of protein values.
        fats (List[float]): List of fat values.
        carbohydrates (List[float]): List of carbohydrate values.

    Properties:
        parsed_created_at (datetime): Parsed date object.
        ingredients (List[IngredientItem]): Converted list of ingredient objects.

    Validation:
        - All lists must have the same length.
        - Nutritional values are normalized to per 100g.
        - Weight must be > 0 for normalization (defaults to 0 if weight is 0).
    """

    created_at: str = Field(
        default_factory=lambda: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Date string for the record (defaults to current datetime)",
    )

    name: List[str] = Field(min_length=1, description="List of ingredient names")
    weight: List[float] = Field(min_length=1, description="List of weights in grams")
    calories: List[float] = Field(min_length=1, description="List of calorie values")
    proteins: List[float] = Field(min_length=1, description="List of protein values")
    fats: List[float] = Field(min_length=1, description="List of fat values")
    carbohydrates: List[float] = Field(
        min_length=1, description="List of carbohydrate values"
    )

    _ingredients: List[IngredientItem] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def convert_and_validate(self):
        """
        Validates list lengths and converts to IngredientItem objects.

        Normalizes nutritional values to per 100g basis.

        Returns:
            DishPayload: The validated model instance with converted ingredients.

        Raises:
            ValueError: If list lengths do not match.
        """
        names_len = len(self.name)

        fields = ["weight", "calories", "proteins", "fats", "carbohydrates"]
        for field in fields:
            field_value = getattr(self, field)
            if len(field_value) != names_len:
                raise ValueError(
                    f"Length mismatch: 'name' has {names_len} items, "
                    f"but '{field}' has {len(field_value)} items"
                )

        self._ingredients = [
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
            )
            for i in range(names_len)
        ]

        return self

    @property
    def ingredients(self) -> List[IngredientItem]:
        """Returns the converted list of IngredientItem objects."""
        return self._ingredients

    @property
    def parsed_created_at(self) -> dt.datetime:
        """Returns the parsed datetime object."""
        return self._parsed_created_at


class ChangeDailyLog(SingleDate):
    """
    Input model for partial daily log updates (edited, added, deleted).

    Used for the /daily_log/update endpoint to apply incremental changes
    to a user's daily nutrition log.

    Attributes:
        date (str): Date string (YYYY-MM-DD). Defaults to today if empty.
        edited (List[LogIngredientItem]): Ingredients with modified values.
        added (List[LogIngredientItem]): New ingredients to add.
        deleted (List[str]): Ingredient names to remove.

    Example:
        {
            "date": "2024-04-23",
            "edited": [{"ingredient": "Apple", "weight_g": 150, ...}],
            "added": [{"ingredient": "Banana", "weight_g": 100, ...}],
            "deleted": ["Orange"]
        }

    Properties:
        parsed_date (datetime): Parsed date object (inherited from SingleDate).
    """

    edited: List[IngredientItem] = Field(
        default_factory=list, description="List of edited ingredients with new values"
    )
    added: List[IngredientItem] = Field(
        default_factory=list, description="List of new ingredients to add"
    )
    deleted: List[str] = Field(
        default_factory=list, description="List of ingredient names to delete"
    )

    @model_validator(mode="after")
    def validate_has_changes(self):
        """
        Validates that at least one change type is present.

        Returns:
            ChangeDailyLog: The validated model instance.

        Note:
            Empty changes are allowed (no-op), but logged for debugging.
        """
        if not self.edited and not self.added and not self.deleted:
            pass

        return self
