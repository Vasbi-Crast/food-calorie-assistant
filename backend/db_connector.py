import datetime as dt
import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from passlib.context import CryptContext

from schemas import IngredientItem, User, RegisterInput

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
load_dotenv()


class DB_connector:
    """A class for connecting to and working with a database"""

    def __init__(self):
        self.db: asyncpg.Pool | None = None

    async def connection(self):
        """Connecting to the database"""
        try:
            db_kwargs = json.loads(os.getenv("DB_CONFIG", "{}"))
            self.db = await asyncpg.create_pool(**db_kwargs)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def close(self):
        """Closing the database connection"""
        try:
            if self.db:
                await self.db.close()
                self.db = None
        except Exception as e:
            raise ConnectionError(f"Failed to close database connection: {e}") from e

    async def add_user(
        self,
        user_data: RegisterInput,
        timeout: int = 20,
    ) -> bool:
        """
        Adds a new user to the database.

        Args:
            username (str): A unique username for authorization.
            password (str): User's password (will be hashed).
            age (int): User's age.
            bmr (float): The user's activity level multiplier.
            gender (str): User's gender ('m', 'w', or 'None').
            weight (float): User's weight in kilograms.
            height (float): User's height in centimeters.
            norm_calories (float): Daily caloric needs.
            norm_proteins (float): Daily protein needs in grams.
            norm_fats (float): Daily fat needs in grams.
            norm_carbohydrates (float): Daily carbohydrate needs in grams.
            timeout (int): Time limit for accessing the db.

        Returns:
            bool: True if successful, False if username already exists.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            INSERT INTO users (
                username, hash_password, age, bmr, gender, goal,
                height, weight,
                norm_calories, norm_proteins, norm_fats, norm_carbohydrates
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """

        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    query,
                    user_data.username,
                    pwd_context.hash(user_data.password),
                    user_data.age,
                    user_data.bmr,
                    user_data.gender,
                    user_data.goal,
                    user_data.height,
                    user_data.weight,
                    user_data.norm_calories,
                    user_data.norm_proteins,
                    user_data.norm_fats,
                    user_data.norm_carbohydrates,
                    timeout=timeout,
                )
            return True

        except asyncpg.UniqueViolationError:
            return False
        except asyncio.TimeoutError as e:
            raise Exception(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def verify(self, username: str, password: str, timeout: int = 20) -> str:
        """
        Authenticates a user.

        Args:
            username (str): A unique username for authorization.
            password (str): User's password.
            timeout (int): Time limit for accessing the db.

        Returns:
            str: "SUCCESSFUL", "USER_NOT_FOUND", or "INVALID_PASSWORD".
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        try:
            user = await self._get_user(username, timeout)

            if not user:
                return "USER_NOT_FOUND"

            if pwd_context.verify(password, user["hash_password"]):
                return "SUCCESSFUL"

            return "INVALID_PASSWORD"

        except asyncio.TimeoutError as e:
            raise Exception(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def user_information(
        self, username: str, timeout: int = 20
    ) -> Dict[str, Any]:
        """
        Gets user profile information.

        Args:
            username (str): A unique username for authorization.
            timeout (int): Time limit for accessing the db.

        Returns:
            dict: User's profile information (age, bmr, gender, weight, height).
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        try:
            user = await self._get_user(username, timeout)
            if not user:
                return {}

            return {
                "age": user["age"],
                "bmr": user["bmr"],
                "goal": user["goal"],
                "gender": user["gender"],
                "height": user["height"],
                "weight": user["weight"],
            }

        except asyncio.TimeoutError as e:
            raise Exception(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def update_user(
        self,
        username: str,
        user_data: User,
        timeout: int = 20,
    ) -> bool:
        """
        Updates user profile information.

        Args:
            username (str): A unique username for authorization.
            age (int): User's age.
            bmr (float): The user's activity level multiplier.
            gender (str): User's gender.
            weight (float): User's weight in kilograms.
            height (float): User's height in centimeters.
            norm_calories (int): Daily caloric needs.
            norm_proteins (float): Daily protein needs in grams.
            norm_fats (float): Daily fat needs in grams.
            norm_carbohydrates (float): Daily carbohydrate needs in grams.
            timeout (int): Time limit for accessing the db.

        Returns:
            bool: True if successful.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            UPDATE users SET 
                age = $2, bmr = $3, gender = $4, goal = $5,
                height = $6, weight = $7,
                norm_calories = $8, norm_proteins = $9, 
                norm_fats = $10, norm_carbohydrates = $11
            WHERE username = $1;
        """

        try:
            async with self.db.acquire() as conn:
                result = await conn.execute(
                    query,
                    username,
                    user_data.age,
                    user_data.bmr,
                    user_data.gender,
                    user_data.goal,
                    user_data.height,
                    user_data.weight,
                    user_data.norm_calories,
                    user_data.norm_proteins,
                    user_data.norm_fats,
                    user_data.norm_carbohydrates,
                    timeout=timeout,
                )
            return result == "UPDATE 1"

        except asyncpg.UniqueViolationError:
            return False
        except asyncio.TimeoutError as e:
            raise Exception(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def info_nutrition(
        self,
        username: str,
        st_time_span: dt.datetime,
        fin_time_span: dt.datetime,
        timeout: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches daily nutrition history for a date range.
        Fills gaps with zeros (all days in range are returned).

        Args:
            username (str): User's username.
            st_time_span (datetime): Start of the time interval.
            fin_time_span (datetime): End of the time interval.
            timeout (int): Time limit for accessing the db.

        Returns:
            dict: Nutrition info keyed by date.
                Example: {"2024-04-01": {"calories": 2000, "proteins": 150, ...}, ...}
                Note: All days in range are returned (gaps filled with zeros).
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            SELECT
                record_date, total_calories, total_proteins, total_fats, total_carbohydrates
            FROM day
            WHERE username = $1
                AND record_date >= $2
                AND record_date <= $3;
        """

        try:
            async with asyncio.timeout(timeout):
                rows = await self.db.fetch(
                    query,
                    username,
                    st_time_span,
                    fin_time_span,
                )

                nutrition_by_date = {
                    row["record_date"].strftime("%Y-%m-%d"): {
                        "calories": row["total_calories"],
                        "proteins": row["total_proteins"],
                        "fats": row["total_fats"],
                        "carbohydrates": row["total_carbohydrates"],
                    }
                    for row in rows
                }

                cur_data = st_time_span.date()
                end_data = fin_time_span.date()
                res: Dict[str, Dict[str, Any]] = {}

                while cur_data <= end_data:
                    date_key = cur_data.strftime("%Y-%m-%d")

                    if date_key in nutrition_by_date:
                        res[date_key] = nutrition_by_date[date_key]
                    else:
                        res[date_key] = {
                            "calories": 0,
                            "proteins": 0,
                            "fats": 0,
                            "carbohydrates": 0,
                        }

                    cur_data += dt.timedelta(days=1)

                return res

        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch nutrition info: {e}") from e

    async def nutrition_norms(
        self,
        username: str,
        st_time_span: dt.datetime,
        fin_time_span: dt.datetime,
        timeout: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches nutrition norms for a date range.
        Fills gaps with last known norm (carry-forward logic).

        OPTIMIZATION: If querying only today, fetches from users table (faster).
        For historical dates, uses user_metrics_history with fallback to last record before interval.

        Args:
            username (str): User's username.
            st_time_span (datetime): Start of the time interval.
            fin_time_span (datetime): End of the time interval.
            timeout (int): Time limit for accessing the db.

        Returns:
            dict: Nutrition norms keyed by date.
                Example: {
                    "2024-04-01": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                    "2024-04-02": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                    "2024-04-03": {"calories": 2300, "proteins": 130, "fats": 75, "carbohydrates": 270},
                    ...
                }
                Note: All days in range are returned. Gaps use last known norm (carry-forward).

        Priority:
            1. First record within the interval (if exists).
            2. Last record before the interval starts (if exists).
            3. Current norms from users table (fallback).
            4. Zeros (if no data at all).

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If database query exceeds timeout limit.
            RuntimeError: If an unexpected error occurs.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        try:
            async with self.db.acquire() as conn:
                today = dt.datetime.now().date()

                # OPTIMIZATION: If querying only today — fetch from users
                is_today_only = (
                    st_time_span.date() == today and fin_time_span.date() == today
                )

                if is_today_only:
                    current_query = """
                        SELECT norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                        FROM users
                        WHERE username = $1;
                    """
                    current_row = await conn.fetchrow(
                        current_query, username, timeout=timeout
                    )

                    if current_row:
                        return {
                            today.strftime("%Y-%m-%d"): {
                                "calories": current_row["norm_calories"],
                                "proteins": current_row["norm_proteins"],
                                "fats": current_row["norm_fats"],
                                "carbohydrates": current_row["norm_carbohydrates"],
                            }
                        }
                    return {
                        today.strftime("%Y-%m-%d"): {
                            "calories": 0,
                            "proteins": 0,
                            "fats": 0,
                            "carbohydrates": 0,
                        }
                    }

                # Historical queries — use user_metrics_history
                history_query = """
                    SELECT recorded_at, norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                    FROM user_metrics_history
                    WHERE username = $1 
                    AND recorded_at::date >= $2::date 
                    AND recorded_at::date <= $3::date
                    ORDER BY recorded_at ASC;
                """
                history_rows = await conn.fetch(
                    history_query,
                    username,
                    st_time_span,
                    fin_time_span,
                    timeout=timeout,
                )

                # Get default norms (first in interval or last before interval)
                if history_rows:
                    default_norms = {
                        "calories": history_rows[0]["norm_calories"],
                        "proteins": history_rows[0]["norm_proteins"],
                        "fats": history_rows[0]["norm_fats"],
                        "carbohydrates": history_rows[0]["norm_carbohydrates"],
                    }
                else:
                    # Fallback: last record BEFORE interval starts
                    last_before_query = """
                        SELECT norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                        FROM user_metrics_history
                        WHERE username = $1 
                        AND recorded_at::date < $2::date
                        ORDER BY recorded_at DESC
                        LIMIT 1;
                    """
                    last_before = await conn.fetchrow(
                        last_before_query,
                        username,
                        st_time_span,
                        timeout=timeout,
                    )

                    if last_before:
                        default_norms = {
                            "calories": last_before["norm_calories"],
                            "proteins": last_before["norm_proteins"],
                            "fats": last_before["norm_fats"],
                            "carbohydrates": last_before["norm_carbohydrates"],
                        }
                    else:
                        # Fallback: users table (registration values)
                        current_row = await conn.fetchrow(
                            "SELECT norm_calories, norm_proteins, norm_fats, norm_carbohydrates FROM users WHERE username = $1",
                            username,
                            timeout=timeout,
                        )
                        default_norms = {
                            "calories": (
                                current_row["norm_calories"] if current_row else 0
                            ),
                            "proteins": (
                                current_row["norm_proteins"] if current_row else 0
                            ),
                            "fats": current_row["norm_fats"] if current_row else 0,
                            "carbohydrates": (
                                current_row["norm_carbohydrates"] if current_row else 0
                            ),
                        }

                # Convert history to dict for fast lookup
                norms_by_date = {
                    row["recorded_at"].date(): {
                        "calories": row["norm_calories"],
                        "proteins": row["norm_proteins"],
                        "fats": row["norm_fats"],
                        "carbohydrates": row["norm_carbohydrates"],
                    }
                    for row in history_rows
                }

                # Fill EVERY day in range (carry-forward)
                cur_data = st_time_span.date()
                end_data = fin_time_span.date()
                last_norms = default_norms.copy()
                res: Dict[str, Dict[str, Any]] = {}

                while cur_data <= end_data:
                    if cur_data in norms_by_date:
                        last_norms = norms_by_date[cur_data]

                    res[cur_data.strftime("%Y-%m-%d")] = {
                        "calories": last_norms["calories"],
                        "proteins": last_norms["proteins"],
                        "fats": last_norms["fats"],
                        "carbohydrates": last_norms["carbohydrates"],
                    }

                    cur_data += dt.timedelta(days=1)

                return res

        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch nutrition info: {e}") from e

    async def weight_history(
        self,
        username: str,
        st_time_span: dt.datetime,
        fin_time_span: dt.datetime,
        timeout: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches weight history for a date range.
        Fills gaps with last known weight (carry-forward logic).

        OPTIMIZATION: If querying only today, fetches from users table (faster).
        For historical dates, uses user_metrics_history with fallback to last record before interval.

        Args:
            username (str): User's username.
            st_time_span (datetime): Start of the time interval.
            fin_time_span (datetime): End of the time interval.
            timeout (int): Time limit for accessing the db.

        Returns:
            dict: Weight values keyed by date.
                Example: {
                    "2024-04-01": {"weight": 75.5},
                    "2024-04-02": {"weight": 75.5},
                    "2024-04-03": {"weight": 74.0},
                    ...
                }
                Note: All days in range are returned. Gaps use last known weight (carry-forward).

        Priority:
            1. First record within the interval (if exists).
            2. Last record before the interval starts (if exists).
            3. Current weight from users table (fallback).
            4. Zero (if no data at all).

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If database query exceeds timeout limit.
            RuntimeError: If an unexpected error occurs.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        try:
            async with asyncio.timeout(timeout):
                today = dt.datetime.now().date()

                # OPTIMIZATION: If querying only today — fetch from users
                is_today_only = (
                    st_time_span.date() == today and fin_time_span.date() == today
                )

                if is_today_only:
                    current_weight = await self.db.fetchval(
                        "SELECT weight FROM users WHERE username = $1", username
                    )
                    return {
                        today.strftime("%Y-%m-%d"): {
                            "weight": current_weight if current_weight else 0
                        }
                    }

                # Historical queries — use user_metrics_history
                query = """
                    SELECT weight, recorded_at
                    FROM user_metrics_history
                    WHERE username = $1
                        AND recorded_at::date >= $2::date
                        AND recorded_at::date <= $3::date
                    ORDER BY recorded_at ASC
                """
                rows = await self.db.fetch(
                    query,
                    username,
                    st_time_span,
                    fin_time_span,
                )

                # Get default weight (first in interval or last before interval)
                if rows:
                    default_weight = rows[0]["weight"]
                else:
                    # Fallback: last record BEFORE interval starts
                    last_before = await self.db.fetchval(
                        """
                        SELECT weight
                        FROM user_metrics_history
                        WHERE username = $1 
                        AND recorded_at::date < $2::date
                        ORDER BY recorded_at DESC
                        LIMIT 1;
                        """,
                        username,
                        st_time_span,
                    )

                    if last_before:
                        default_weight = last_before
                    else:
                        # Fallback: users table (registration values)
                        current_weight = await self.db.fetchval(
                            "SELECT weight FROM users WHERE username = $1", username
                        )
                        default_weight = current_weight if current_weight else 0

                # Convert history to dict for fast lookup
                weight_by_date = {
                    row["recorded_at"].date(): row["weight"] for row in rows
                }

                # Fill EVERY day in range (carry-forward)
                cur_data = st_time_span.date()
                end_data = fin_time_span.date()
                last_weight = default_weight
                res: Dict[str, Any] = {}

                while cur_data <= end_data:
                    if cur_data in weight_by_date:
                        last_weight = weight_by_date[cur_data]

                    res[cur_data.strftime("%Y-%m-%d")] = last_weight

                    cur_data += dt.timedelta(days=1)

                return res

        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch weight history: {e}") from e

    async def add_day(
        self,
        username: str,
        created_at: dt.datetime,
        timeout: int = 20,
    ) -> int:
        """
        Creates or retrieves a day record for the user.

        Args:
            username (str): Unique username for authorization.
            created_at (datetime): Date of the record (record_date).
            timeout (int): Time limit for database access in seconds.

        Returns:
            int: The day ID (either newly created or existing).
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        insert_query = """
            INSERT INTO day (record_date, username)
            VALUES ($1, $2)
            ON CONFLICT (record_date, username) DO NOTHING
        """

        select_query = "SELECT id FROM day WHERE record_date = $1 AND username = $2"

        try:
            async with self.db.acquire() as conn:
                await conn.execute(insert_query, created_at, username, timeout=timeout)
                day_id = await conn.fetchval(select_query, created_at, username, timeout=timeout)
                return day_id

        except asyncio.TimeoutError as e:
            raise asyncio.TimeoutError(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def daily_log(
        self,
        username: str,
        date: dt.datetime,
        timeout: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetches ingredients and nutrition info for a specific day record.

        Args:
            username (str): The username of the user.
            date (datetime): The date of the day record.
            timeout (int): Time limit for database access in seconds.

        Returns:
            list: List of dictionaries with ingredient nutrition info.
                Each dict contains: ingredient, weight, calories,
                proteins, fats, carbohydrates.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            SELECT
                ing.id as id_ingredient,
                ing.name as name,
                lis.weight as weight,
                ROUND(ing.calories * lis.weight / 100.0, 2) AS calories,
                ROUND(ing.proteins * lis.weight / 100.0, 2) AS proteins,
                ROUND(ing.fats * lis.weight / 100.0, 2) AS fats,
                ROUND(ing.carbohydrates * lis.weight / 100.0, 2) AS carbohydrates
            FROM
                list_ingredients AS lis  
                INNER JOIN ingredient AS ing ON lis.id_ingredient = ing.id
                INNER JOIN day ON lis.id_day = day.id
            WHERE
                day.username = $1 
                AND day.record_date = $2
            ORDER BY
                lis.created_at ASC; 
        """

        try:
            res: List[Dict[str, Any]] = []
            async with asyncio.timeout(timeout):
                rows = await self.db.fetch(query, username, date)
                if rows:
                    for row in rows:
                        ingredient = {
                            "ingredient": row["name"],
                            "weight": row["weight"],
                            "calories": row["calories"],
                            "proteins": row["proteins"],
                            "fats": row["fats"],
                            "carbohydrates": row["carbohydrates"],
                        }
                        res.append(ingredient)
                return res

        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch nutrition info: {e}") from e

    async def add_ingredients_to_day(
        self,
        day_id: int,
        ingredients: List[IngredientItem],
        created_at: dt.datetime,
        timeout: int = 20,
    ) -> bool:
        """
        Adds ingredients to a specific day record.

        Args:
            day_id (int): The day ID from add_day().
            ingredients (List[IngredientItem]): List of ingredients to add.
                - name: Ingredient name
                - weight: Actual weight in grams
                - calories/proteins/fats/carbohydrates: Values for THIS WEIGHT (not per 100g!)
            created_at (datetime): Date of the record.
            timeout (int): Time limit for database access in seconds.

        Returns:
            bool: True if successful.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        insert_query = """
            INSERT INTO list_ingredients (id_day, id_ingredient, weight, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id_day, id_ingredient) 
            DO UPDATE SET 
                weight = list_ingredients.weight + EXCLUDED.weight,
                created_at = EXCLUDED.created_at
        """

        try:
            async with self.db.acquire() as conn:
                for ingredient in ingredients:
                    ingredient_id = await self._get_or_create_ingredient(
                        conn, ingredient, timeout
                    )
                    await conn.execute(
                        insert_query,
                        day_id,
                        ingredient_id,
                        ingredient.weight,
                        created_at,
                        timeout=timeout,
                    )

                return True

        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def change_ingredients_in_day(
        self,
        day_id: int,
        edited: List[IngredientItem],
        timeout: int = 20,
    ) -> bool:
        """
        Updates existing ingredients in a specific day record.

        IMPORTANT:
            - Always updates weight in list_ingredients
            - Only updates ingredient table (per 100g) if update_macros=True

        Args:
            day_id (int): The day ID from add_day().
            edited (List[IngredientItem]): List of ingredients with updated values.
                - name: Ingredient name (for lookup)
                - weight: New weight in grams
                - calories/proteins/fats/carbohydrates: Used ONLY if update_macros=True
            update_macros (bool): If True, also updates ingredient reference table.
            timeout (int): Time limit for database access in seconds.

        Returns:
            bool: True if successful.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        update_weight_query = """
            UPDATE list_ingredients li
            SET weight = $1
            FROM ingredient ing
            WHERE li.id_ingredient = ing.id
            AND li.id_day = $2
            AND ing.name = $3
        """

        update_macros_query = """
            UPDATE ingredient
            SET calories = ROUND(($1::decimal / NULLIF($6::decimal, 0)) * 100, 1),
                proteins = ROUND(($2::decimal / NULLIF($6::decimal, 0)) * 100, 1),
                fats     = ROUND(($3::decimal / NULLIF($6::decimal, 0)) * 100, 1),
                carbohydrates = ROUND(($4::decimal / NULLIF($6::decimal, 0)) * 100, 1)
            WHERE name = $5
        """

        try:
            async with self.db.acquire() as conn:
                for ingredient in edited:
                    await conn.execute(
                        update_weight_query,
                        ingredient.weight,
                        day_id,
                        ingredient.name,
                        timeout=timeout,
                    )

                    await conn.execute(
                        update_macros_query,
                        ingredient.calories,
                        ingredient.proteins,
                        ingredient.fats,
                        ingredient.carbohydrates,
                        ingredient.name,
                        ingredient.weight,
                        timeout=timeout,
                    )

                return True

        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def del_ingredients_in_day(
        self,
        day_id: int,
        deleted: List[str],
        timeout: int = 20,
    ) -> bool:
        """
        Deletes ingredients from a specific day record.

        Note: Only removes from list_ingredients, NOT from ingredient table.
        The ingredient remains in the reference table for other days.

        Args:
            day_id (int): The day ID from add_day().
            deleted (List[str]): List of ingredient names to delete.
            timeout (int): Time limit for database access in seconds.

        Returns:
            bool: True if successful.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            DELETE FROM list_ingredients li
            USING ingredient ing
            WHERE li.id_ingredient = ing.id
            AND li.id_day = $1
            AND ing.name = ANY($2);
        """

        try:
            async with self.db.acquire() as conn:
                await conn.execute(query, day_id, deleted, timeout=timeout)

                return True

        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

    async def _get_or_create_ingredient(
        self,
        conn,
        ingredient: IngredientItem,
        timeout: int = 20,
    ) -> int:
        """
        Gets existing ingredient ID or creates a new one.

        IMPORTANT: Converts КБЖУ from actual weight to per 100g for storage.

        Formula: per_100g = (actual_value / weight) * 100

        Args:
            conn: Database connection from pool.
            ingredient (IngredientItem): Ingredient data.
                - calories/proteins/fats/carbohydrates: Values for ACTUAL weight
                - weight: Actual weight in grams
            timeout (int): Time limit for database access.

        Returns:
            int: The ingredient ID.
        """

        get_query = """
            SELECT id FROM ingredient WHERE name = $1
        """

        row = await conn.fetchrow(get_query, ingredient.name, timeout=timeout)

        if row:
            return row["id"]

        create_query = """
            INSERT INTO ingredient (name, calories, proteins, fats, carbohydrates)
            VALUES (
                $1,
                ROUND(($2::decimal / NULLIF($3::decimal, 0)) * 100, 1),
                ROUND(($4::decimal / NULLIF($3::decimal, 0)) * 100, 1),
                ROUND(($5::decimal / NULLIF($3::decimal, 0)) * 100, 1),
                ROUND(($6::decimal / NULLIF($3::decimal, 0)) * 100, 1)
            )
            ON CONFLICT (name) DO UPDATE SET 
                calories = EXCLUDED.calories,
                proteins = EXCLUDED.proteins,
                fats = EXCLUDED.fats,
                carbohydrates = EXCLUDED.carbohydrates
            RETURNING id;
        """

        result = await conn.fetchval(
            create_query,
            ingredient.name,
            ingredient.calories,
            ingredient.weight,
            ingredient.proteins,
            ingredient.fats,
            ingredient.carbohydrates,
            timeout=timeout,
        )

        return result

    async def _get_user(
        self, username: str, timeout: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a user from the database.

        Args:
            username (str): User's username.
            timeout (int): Time limit for database access.

        Returns:
            dict | None: User data as dictionary, or None if not found.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = "SELECT * FROM users WHERE username = $1"

        try:
            async with self.db.acquire() as conn:
                response = await conn.fetchrow(query, username, timeout=timeout)

            if response:
                return dict(response)
            return None

        except asyncio.TimeoutError as e:
            raise Exception(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e
