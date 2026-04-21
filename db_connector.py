import datetime as dt
import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv
from typing import List, Dict
from passlib.context import CryptContext
from schemas import IngredientItem

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
load_dotenv()


class DB_connector:
    """A class for connecting to and working with a database"""

    def __init__(self):
        self.db: asyncpg.Pool | None = None

    async def connection(self):
        """connecting to the database"""
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
        username: str,
        password: str,
        age: int,
        bmr: float,
        gender: str,
        weight: float,
        height: float,
        timeout: int = 20,
    ) -> bool:
        """
        A function for adding a new user.

        Args:
            username (str): A unique username for authorization.
            password (str): User's password.
            age (int): User's age.
            bmr (float): The user's basal metabolic rate.
            gender (str): User's gender.
            weight (float): User's weight.
            height (float): User growth.
            timeout (int): Time limit for accessing the db.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            INSERT INTO users (username, hash_password, age, bmr, height, weight, gender)
            VALUES ($1, $2, $3, $4, $5, $6, $7)"""

        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    query,
                    username,
                    pwd_context.hash(password),
                    age,
                    bmr,
                    height,
                    weight,
                    gender,
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
        A function for user authentication.

        Args:
            username (str): A unique username for authorization.
            password (str): User's password.
            timeout (int): Time limit for accessing the db.
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

    async def user_information(self, username: str, timeout: int = 20) -> str:
        """
        A function for getting information about users.

        Args:
            username (str): A unique username for authorization.
            timeout (int): Time limit for accessing the db.
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
                "age": int(user["age"]),
                "bmr": float(user["bmr"]),
                "gender": user["gender"],
                "height": float(user["height"]),
                "weight": float(user["weight"]),
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
        age: int,
        bmr: float,
        gender: str,
        weight: float,
        height: float,
        timeout: int = 20,
    ) -> bool:
        """
        A function for update information about user.

        Args:
            username (str): A unique username for authorization.
            age (int): User's age.
            bmr (float): The user's basal metabolic rate.
            gender (str): User's gender.
            weight (float): User's weight.
            height (float): User growth.
            timeout (int): Time limit for accessing the db.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            UPDATE users SET age = $2, bmr = $3, height = $4, weight = $5, gender = $6
            WHERE username = $1;"""

        try:
            async with self.db.acquire() as conn:
                result = await conn.execute(
                    query,
                    username,
                    age,
                    bmr,
                    height,
                    weight,
                    gender,
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
        st_time_span: str,
        fin_time_span: str,
        timeout: int = 20,
    ) -> dict:
        """
        A function for update information about user.

        Args:
            username (str): username.
            st_time_span (str): The beginning of the time interval during which data should be collected. Format: YYYY-MM-DD.
            fin_time_span (str): The end of the time interval during which data should be collected. Format: YYYY-MM-DD.
            timeout (int): Time limit for accessing the db.
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
            st_time_span = dt.datetime.strptime(st_time_span, "%Y-%m-%d")
            fin_time_span = dt.datetime.strptime(fin_time_span, "%Y-%m-%d")
            cur_data = st_time_span
            res = {}
            while cur_data <= fin_time_span:
                res[cur_data.strftime("%Y-%m-%d")] = {
                    "calories": 0,
                    "proteins": 0,
                    "fats": 0,
                    "carbohydrates": 0,
                }
                cur_data += dt.timedelta(days=1)

            async with asyncio.timeout(timeout):
                rows = await self.db.fetch(
                    query,
                    username,
                    st_time_span,
                    fin_time_span,
                )
                if rows:
                    for row in rows:
                        macros_day = {
                            "calories": row["total_calories"],
                            "proteins": row["total_proteins"],
                            "fats": row["total_fats"],
                            "carbohydrates": row["total_carbohydrates"],
                        }
                        res[row["record_date"].strftime("%Y-%m-%d")] = macros_day
                return res
        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch nutrition info: {e}") from e

    async def add_day(
        self,
        username: str,
        created_at: dt.datetime,
        timeout: int = 20,
    ) -> int:
        """
        Creates or retrieves a day record for the user.

        If a record for the given date and username already exists,
        returns the existing day ID. Otherwise, creates a new record.

        Args:
            username (str): Unique username for authorization.
            created_at (dt.datetime): Date of the record (record_date).
            timeout (int): Time limit for database access in seconds.

        Returns:
            int: The day ID (either newly created or existing).

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            asyncio.TimeoutError: If the request exceeds the time limit.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            INSERT INTO day (record_date, username)
            VALUES ($1, $2)
            ON CONFLICT (record_date, username) 
            DO UPDATE SET record_date = EXCLUDED.record_date
            RETURNING id;
        """

        try:
            async with self.db.acquire() as conn:
                day_id = await conn.fetchval(
                    query, created_at, username, timeout=timeout
                )

                return day_id

        except asyncio.TimeoutError as e:
            raise asyncio.TimeoutError(
                f"The request exceeded the time limit ({timeout} seconds)"
            ) from e
        except Exception as e:
            raise Exception(
                f"An unexpected error occurred: {type(e).__name__}: {e}"
            ) from e

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
            timeout (int): Time limit for database access in seconds.

        Returns:
            bool: True if successful.
        """

        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        query = """
            INSERT INTO list_ingredients (id_day, id_ingredient, weight, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING;
        """

        try:
            async with self.db.acquire() as conn:
                for ingredient in ingredients:
                    ingredient_id = await self._get_or_create_ingredient(
                        conn, ingredient, timeout
                    )
                    await conn.execute(
                        query,
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

    async def _get_or_create_ingredient(
        self,
        conn,
        ingredient: IngredientItem,
        timeout: int = 20,
    ) -> int:
        """
        Gets existing ingredient ID or creates a new one.

        Internal method - not for external use.

        Args:
            conn: Database connection from pool.
            ingredient (IngredientItem): Ingredient data.
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
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id;
        """

        result = await conn.fetchval(
            create_query,
            ingredient.name,
            ingredient.calories,
            ingredient.proteins,
            ingredient.fats,
            ingredient.carbohydrates,
            timeout=timeout,
        )

        return result

    async def _get_user(self, username: str, timeout: int = 20):
        """Finding a user from the database"""
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
