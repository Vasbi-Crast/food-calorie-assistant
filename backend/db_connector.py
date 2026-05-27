import datetime as dt
import os
import json
import asyncio
import asyncpg
from pgvector.asyncpg import register_vector
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Tuple
from passlib.context import CryptContext
from sentence_transformers import SentenceTransformer
import logging

from schemas import IngredientItem, User, RegisterInput

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
load_dotenv()

logger = logging.getLogger("db_connector")


class DBConnector:
    """
    Database connector for PostgreSQL with pgvector support.

    Handles user management, ingredient search, nutrition tracking,
    and daily log operations with proper owner attribution.

    Architecture:
        ingredient table: stores per-100g values (reference data)
        list_ingredients table: stores only weight (actual portion)
        IngredientItem: stores per-100g internally
        API boundary: actual ↔ per-100g conversion via to_actual()
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small", embedding_batch_size: int = 32):
        """
        Initializes DBConnector configuration.
        
        Args:
            model_name (str): Name of the SentenceTransformer model. Default: "intfloat/multilingual-e5-small".
            embedding_batch_size (int): Batch size for embedding generation. Default: 32.
        """
        logger.info("Initializing DBConnector configuration...")
        self.db: asyncpg.Pool | None = None
        self.model_name = model_name
        self.embedding_batch_size = embedding_batch_size
        self.encoder: Optional[SentenceTransformer] = None
        logger.info("✅ DBConnector configuration initialized")

    async def connection(self):
        """
        Establishes database connection pool with pgvector support.

        Raises:
            ConnectionError: If database connection fails.
        """
        logger.info("Connecting to database pool...")
        try:
            db_kwargs = json.loads(os.getenv("DB_CONFIG", "{}"))
            logger.debug(
                f"Database config loaded for host: {db_kwargs.get('host', 'unknown')}"
            )

            async def init_pool_connection(conn: asyncpg.Connection):
                await register_vector(conn)
                logger.debug("✅ pgvector extension registered")

            self.db = await asyncpg.create_pool(**db_kwargs, init=init_pool_connection)
            logger.info("✅ Database pool connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def load_model(self) -> None:
        """
        Loads the embedding model asynchronously.
        
        Must be called after __init__ and before any embedding operations.
        
        Raises:
            Exception: If model loading fails.
        """
        if self.encoder is not None:
            logger.debug("Embedding model already loaded")
            return
            
        logger.info(f"Loading embedding model: {self.model_name}")
        try:
            self.encoder = await asyncio.to_thread(
                SentenceTransformer, 
                self.model_name
            )
            logger.info("✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}", exc_info=True)
            raise

    async def close(self):
        """
        Closes database connection pool.

        Raises:
            ConnectionError: If closing connection fails.
        """
        logger.info("Closing database connection...")
        try:
            if self.db:
                await self.db.close()
                self.db = None
                logger.info("✅ Database connection closed")
        except Exception as e:
            logger.error(f"Failed to close database connection: {e}", exc_info=True)
            raise ConnectionError(f"Failed to close database connection: {e}") from e

    # ============================================
    # INGREDIENT SEARCH
    # ============================================

    async def search_ingredients_batch(
        self,
        img_ingredients: Dict[str, float],
        owner_username: str = "admin",
        distance_threshold_user_ingr: float = 0.1,
        distance_threshold_admin_ingr: float = 0.11,
        timeout: int = 20,
    ) -> Tuple[List[IngredientItem], Dict[str, float]]:
        """
        Batch search for ingredients using semantic similarity.

        Searches in priority order:
            1. User's own ingredients (owner_username)
            2. Global ingredients (owner = 'admin')

        Args:
            img_ingredients (Dict[str, float]): Dict of {ingredient_name: weight_in_grams}.
            owner_username (str): Username to search for first. Default: "admin".
            distance_threshold_user_ingr (float): Similarity threshold for user ingredients.
                Lower values = stricter matching. Default: 0.1.
            distance_threshold_admin_ingr (float): Similarity threshold for admin ingredients.
                Should be slightly higher than user threshold. Default: 0.11.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Tuple[List[IngredientItem], Dict[str, float]]: Tuple of (results, not_found):
                results: List[IngredientItem] with per-100g values (internal format).
                    Use item.to_actual() to convert to actual values for API response.
                not_found: Dict of {ingredient_name: weight} for unmatched items.

        Raises:
            ConnectionError: If database connection is not established.
        """
        if not self.db:
            logger.error("Database connection not established")
            raise ConnectionError("Database connection not established")

        if not img_ingredients:
            logger.debug("Empty img_ingredients provided, returning empty results")
            return [], {}

        names = list(img_ingredients.keys())
        logger.info(
            f"Starting batch search for {len(names)} ingredients (User: {owner_username})"
        )

        try:
            np_array = await asyncio.to_thread(
                self.encoder.encode,
                names,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=self.embedding_batch_size,
            )
            embeddings = np_array.tolist()
            logger.debug(f"✅ Embeddings generated for {len(embeddings)} items")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
            raise

        results: List[IngredientItem] = []
        not_found: Dict[str, float] = {}

        async with self.db.acquire() as conn:
            for embedding, (name, weight) in zip(embeddings, img_ingredients.items()):
                logger.debug(f" Searching for: '{name}'")

                row = await conn.fetchrow(
                    """
                    SELECT name, calories, proteins, fats, carbohydrates, owner_username,
                        embedding <=> $1::vector AS distance
                    FROM ingredient
                    WHERE owner_username = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT 1
                """,
                    embedding,
                    owner_username,
                    timeout=timeout,
                )

                if row and row["distance"] < distance_threshold_user_ingr:
                    logger.debug(
                        f"✅ Match found in user ingredients: '{row['name']}' (dist: {row['distance']:.4f})"
                    )
                else:
                    logger.debug(
                        f"⚠️ No user match (dist: {row['distance'] if row else 'N/A'}), checking admin..."
                    )
                    row = await conn.fetchrow(
                        """
                        SELECT name, calories, proteins, fats, carbohydrates, owner_username,
                            embedding <=> $1::vector AS distance
                        FROM ingredient
                        WHERE owner_username = 'admin'
                        ORDER BY embedding <=> $1::vector
                        LIMIT 1
                    """,
                        embedding,
                        timeout=timeout,
                    )

                if row and row["distance"] < distance_threshold_admin_ingr:
                    ingredient = IngredientItem(
                        name=row["name"],
                        weight=weight,
                        calories=row["calories"],
                        proteins=row["proteins"],
                        fats=row["fats"],
                        carbohydrates=row["carbohydrates"],
                        owner=row["owner_username"],
                    )
                    results.append(ingredient)
                    logger.debug(f"✅ Final match: '{name}' → '{row['name']}'")
                else:
                    not_found[name] = weight
                    logger.warning(f"❌ No match for '{name}' within thresholds")

        logger.info(
            f"Search complete: {len(results)} found, {len(not_found)} not found"
        )
        return results, not_found

    # ============================================
    # USER INGREDIENT MANAGEMENT
    # ============================================

    async def user_ingredients(
        self,
        username: str,
        timeout: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetches all ingredients owned by a specific user.

        Retrieves ingredient names and nutritional values (per 100g) from the
        database for the given username. Used to populate user's personal
        ingredient library in the UI.

        Args:
            username (str): Username whose ingredients to fetch.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            List[Dict[str, Any]]: List of ingredient dictionaries.
                Each dict contains:
                    name (str): Ingredient name
                    calories (float): Calories per 100g
                    proteins (float): Proteins per 100g
                    fats (float): Fats per 100g
                    carbohydrates (float): Carbohydrates per 100g
                Note: All values are per-100g (reference format).

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds the timeout limit.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Fetching user ingredients for: {username}")
        query = """
            SELECT name, calories, proteins, fats, carbohydrates
            FROM ingredient
            WHERE owner_username = $1;
        """
        try:
            async with asyncio.timeout(timeout):
                rows = await self.db.fetch(query, username)
                result = [
                    {
                        "name": row["name"],
                        "calories": row["calories"],
                        "proteins": row["proteins"],
                        "fats": row["fats"],
                        "carbohydrates": row["carbohydrates"],
                    }
                    for row in rows
                ]
                logger.debug(f"✅ Retrieved {len(result)} ingredients")
                return result

        except asyncio.TimeoutError:
            logger.error(
                f"Query timeout for user_ingredients({username})", exc_info=True
            )
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except Exception as e:
            logger.error(f"Failed to fetch user ingredients: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch user ingredients: {e}") from e

    # ============================================
    # USER MANAGEMENT
    # ============================================

    async def add_user(
        self,
        user_data: RegisterInput,
        timeout: int = 20,
    ) -> bool:
        """
        Adds a new user to the database.

        Args:
            user_data (RegisterInput): RegisterInput model with user profile and credentials.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            bool: True if user created successfully, False if username exists.

        Raises:
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Attempting to register user: {user_data.username}")
        query = """
            INSERT INTO users (
                username, hash_password, age, bmr, lifestyle_description, gender, goal,
                height, weight,
                norm_calories, norm_proteins, norm_fats, norm_carbohydrates
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """

        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    query,
                    user_data.username,
                    pwd_context.hash(user_data.password),
                    user_data.age,
                    user_data.bmr,
                    user_data.lifestyle_description,
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
            logger.info(f"✅ User registered: {user_data.username}")
            return True

        except asyncpg.UniqueViolationError:
            logger.warning(f"Username already exists: {user_data.username}")
            raise asyncpg.UniqueViolationError("username")
        except asyncio.TimeoutError as e:
            logger.error(
                f"Query timeout for add_user({user_data.username})", exc_info=True
            )
            raise TimeoutError(f"Query exceeded {timeout} seconds timeout") from e
        except Exception as e:
            logger.error(f"Unexpected error in add_user: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}") from e

    async def verify(self, username: str, password: str, timeout: int = 20) -> str:
        """
        Authenticates a user by username and password.

        Args:
            username (str): User's username.
            password (str): User's password (plain text).
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            str: "SUCCESSFUL", "USER_NOT_FOUND", or "INVALID_PASSWORD".

        Raises:
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Auth attempt for user: {username}")
        try:
            user = await self._get_user(username, timeout)

            if not user:
                logger.warning(f"User not found: {username}")
                return "USER_NOT_FOUND"

            if pwd_context.verify(password, user["hash_password"]):
                logger.info(f"✅ Auth successful: {username}")
                return "SUCCESSFUL"

            logger.warning(f"Invalid password for user: {username}")
            return "INVALID_PASSWORD"

        except asyncio.TimeoutError as e:
            logger.error(f"Query timeout for verify({username})", exc_info=True)
            raise TimeoutError(f"Query exceeded {timeout} seconds timeout") from e
        except Exception as e:
            logger.error(f"Unexpected error in verify: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}") from e

    async def user_information(
        self, username: str, timeout: int = 20
    ) -> Dict[str, Any]:
        """
        Gets user profile information.

        Args:
            username (str): User's username.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Dict[str, Any]: User's profile information (age, bmr, gender, goal, weight, height).
                Empty dict if user not found.

        Raises:
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.debug(f"Fetching profile info for: {username}")
        try:
            user = await self._get_user(username, timeout)
            if not user:
                return {}

            return {
                "age": user["age"],
                "bmr": user["bmr"],
                "lifestyle_description": user["lifestyle_description"],
                "goal": user["goal"],
                "gender": user["gender"],
                "height": user["height"],
                "weight": user["weight"],
            }

        except asyncio.TimeoutError as e:
            logger.error(
                f"Query timeout for user_information({username})", exc_info=True
            )
            raise TimeoutError(f"Query exceeded {timeout} seconds timeout") from e
        except Exception as e:
            logger.error(f"Unexpected error in user_information: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}") from e

    async def update_user(
        self,
        username: str,
        user_data: User,
        timeout: int = 20,
    ) -> bool:
        """
        Updates user profile information.

        Args:
            username (str): User's username.
            user_data (User): User model with updated profile values.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            bool: True if update successful, False if user not found.

        Raises:
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Updating profile for: {username}")
        query = """
            UPDATE users SET 
                age = $2, bmr = $3, lifestyle_description = $4, gender = $5, goal = $6,
                height = $7, weight = $8,
                norm_calories = $9, norm_proteins = $10, 
                norm_fats = $11, norm_carbohydrates = $12
            WHERE username = $1;
        """

        try:
            async with self.db.acquire() as conn:
                result = await conn.execute(
                    query,
                    username,
                    user_data.age,
                    user_data.bmr,
                    user_data.lifestyle_description,
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
            success = result == "UPDATE 1"
            logger.info(
                f"{'✅' if success else '⚠️'} Profile update for {username}: {'success' if success else 'user not found'}"
            )
            return success

        except asyncio.TimeoutError as e:
            logger.error(f"Query timeout for update_user({username})", exc_info=True)
            raise TimeoutError(f"Query exceeded {timeout} seconds timeout") from e
        except Exception as e:
            logger.error(f"Unexpected error in update_user: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {type(e).__name__}: {e}") from e

    # ============================================
    # NUTRITION HISTORY
    # ============================================

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
            st_time_span (dt.datetime): Start of the time interval.
            fin_time_span (dt.datetime): End of the time interval.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Dict[str, Dict[str, Any]]: Nutrition info keyed by date (YYYY-MM-DD).
                Example: {"2024-04-01": {"calories": 2000, "proteins": 150, ...}, ...}
                Note: All days in range are returned (gaps filled with zeros).

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(
            f"Fetching nutrition history for {username}: {st_time_span.date()} → {fin_time_span.date()}"
        )
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
                rows = await self.db.fetch(query, username, st_time_span, fin_time_span)
                logger.debug(f"Retrieved {len(rows)} raw records from DB")

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

                logger.debug(f"✅ Nutrition history processed: {len(res)} days")
                return res

        except asyncio.TimeoutError:
            logger.error(f"Query timeout for info_nutrition({username})", exc_info=True)
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except Exception as e:
            logger.error(f"Failed to fetch nutrition info: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch nutrition info: {e}") from e

    async def nutrition_norms(
        self,
        username: str,
        st_time_span: dt.datetime,
        fin_time_span: dt.datetime,
        timeout: int = 20,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches nutrition norms for a date range with carry-forward logic.

        Days without records use the last known norm (carry-forward).
        If no history exists, uses initial norms from registration.
        All days in range are returned.

        Args:
            username (str): User's username.
            st_time_span (dt.datetime): Start of the time interval.
            fin_time_span (dt.datetime): End of the time interval.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Dict[str, Dict[str, Any]]: Nutrition norms keyed by date (YYYY-MM-DD).
                Example: {
                    "2024-04-01": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                    "2024-04-02": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                }

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")
        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(
            f"Fetching nutrition norms for {username}: {st_time_span.date()} → {fin_time_span.date()}"
        )

        try:
            async with self.db.acquire() as conn:
                today = dt.datetime.now().date()
                is_today_only = (
                    st_time_span.date() == today and fin_time_span.date() == today
                )

                if is_today_only:
                    current_query = "SELECT norm_calories, norm_proteins, norm_fats, norm_carbohydrates FROM users WHERE username = $1;"
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

                history_query = """
                    SELECT recorded_at, norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                    FROM user_metrics_history WHERE username = $1 AND recorded_at::date >= $2::date AND recorded_at::date <= $3::date ORDER BY recorded_at ASC;
                """
                history_rows = await conn.fetch(
                    history_query,
                    username,
                    st_time_span,
                    fin_time_span,
                    timeout=timeout,
                )

                if history_rows:
                    default_norms = {
                        "calories": history_rows[0]["norm_calories"],
                        "proteins": history_rows[0]["norm_proteins"],
                        "fats": history_rows[0]["norm_fats"],
                        "carbohydrates": history_rows[0]["norm_carbohydrates"],
                    }
                else:
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

                norms_by_date = {
                    row["recorded_at"].date(): {
                        "calories": row["norm_calories"],
                        "proteins": row["norm_proteins"],
                        "fats": row["norm_fats"],
                        "carbohydrates": row["norm_carbohydrates"],
                    }
                    for row in history_rows
                }

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
        except Exception as e:
            logger.error(f"Error in nutrition_norms: {e}", exc_info=True)
            raise

    async def weight_history(
        self,
        username: str,
        st_time_span: dt.datetime,
        fin_time_span: dt.datetime,
        timeout: int = 20,
    ) -> Dict[str, float]:
        """
        Fetches weight history for a date range with carry-forward logic.

        Days without weight records use the last known weight.
        If no history exists, uses initial weight from registration.
        All days in range are returned.

        Args:
            username (str): User's username.
            st_time_span (dt.datetime): Start of the time interval.
            fin_time_span (dt.datetime): End of the time interval.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Dict[str, float]: Weight values keyed by date (YYYY-MM-DD).
                Example: {"2024-04-01": 75.5, "2024-04-02": 75.5, ...}
                Note: All days in range returned. Gaps use last known weight.

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")
        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(
            f"Fetching weight history for {username}: {st_time_span.date()} → {fin_time_span.date()}"
        )

        try:
            async with asyncio.timeout(timeout):
                today = dt.datetime.now().date()

                is_today_only = (
                    st_time_span.date() == today and fin_time_span.date() == today
                )

                if is_today_only:
                    current_weight = await self.db.fetchval(
                        "SELECT weight FROM users WHERE username = $1", username
                    )
                    return {
                        today.strftime("%Y-%m-%d"): (
                            current_weight if current_weight else 0
                        )
                    }

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

                if rows:
                    default_weight = rows[0]["weight"]
                else:
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
                        current_weight = await self.db.fetchval(
                            "SELECT weight FROM users WHERE username = $1", username
                        )
                        default_weight = current_weight if current_weight else 0

                weight_by_date = {
                    row["recorded_at"].date(): row["weight"] for row in rows
                }

                cur_data = st_time_span.date()
                end_data = fin_time_span.date()
                last_weight = default_weight
                res: Dict[str, float] = {}

                while cur_data <= end_data:
                    if cur_data in weight_by_date:
                        last_weight = weight_by_date[cur_data]

                    res[cur_data.strftime("%Y-%m-%d")] = last_weight

                    cur_data += dt.timedelta(days=1)

                return res

        except asyncio.TimeoutError:
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except Exception as e:
            logger.error(f"Error in weight_history: {e}", exc_info=True)
            raise

    # ============================================
    # MEAL MANAGEMENT
    # ============================================

    async def daily_log(
        self,
        username: str,
        date: dt.datetime,
        timeout: int = 20,
    ) -> List[IngredientItem]:
        """
        Fetches ingredients and nutrition info for a specific day record.

        Args:
            username (str): User's username.
            date (dt.datetime): The date of the day record.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            List[IngredientItem]: List of ingredients with per-100g values.
                Each item contains: name, weight, calories, proteins, fats,
                carbohydrates, owner.
                Note: calories/proteins/fats/carbohydrates are per-100g.
                Use item.to_actual() to convert to actual values for API response.

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            TimeoutError: If query exceeds timeout.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Fetching daily log for {username} on {date.date()}")
        query = """
            SELECT
                ing.name as name, lis.weight as weight,
                ing.calories as calories, ing.proteins as proteins,
                ing.fats as fats, ing.carbohydrates as carbohydrates,
                ing.owner_username as owner
            FROM list_ingredients AS lis  
            INNER JOIN ingredient AS ing ON lis.id_ingredient = ing.id
            INNER JOIN day ON lis.id_day = day.id
            WHERE day.username = $1 AND day.record_date = $2
            ORDER BY lis.created_at ASC;
        """

        try:
            async with asyncio.timeout(timeout):
                rows = await self.db.fetch(query, username, date)
                logger.debug(f"✅ Retrieved {len(rows)} items for daily log")

                return [
                    IngredientItem(
                        name=row["name"],
                        weight=row["weight"],
                        calories=row["calories"],
                        proteins=row["proteins"],
                        fats=row["fats"],
                        carbohydrates=row["carbohydrates"],
                        owner=row["owner"],
                    )
                    for row in rows
                ]

        except asyncio.TimeoutError:
            logger.error(f"Query timeout for daily_log({username})", exc_info=True)
            raise TimeoutError(f"Database query exceeded {timeout} seconds timeout")
        except Exception as e:
            logger.error(f"Failed to fetch daily log: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch daily log: {e}") from e

    async def save_meal(
        self,
        username: str,
        modified_ingredients: List[IngredientItem],
        table: List[IngredientItem],
        date: dt.datetime,
        timeout: int = 40,
    ) -> None:
        """
        Appends a single meal to the user's daily log.

        Args:
            username (str): User's username.
            modified_ingredients (List[IngredientItem]): Ingredients with updated per-100g macros.
            table (List[IngredientItem]): Ingredients to add for this meal (per-100g macros + actual weight).
            date (dt.datetime): Date of the daily record.
            timeout (int): Query timeout in seconds. Default: 40.

        Raises:
            ValueError: If timeout < 1.
            ConnectionError: If the database pool is not initialized.
            TimeoutError: If query exceeds timeout.
            RuntimeError: On unexpected database errors.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")
        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(f"Saving meal for {username} on {date.date()} ({len(table)} items)")
        try:
            async with self.db.acquire() as conn:
                async with conn.transaction():
                    day_id = await self._add_day(conn, username, date, timeout)
                    await self._change_ingredient(conn, modified_ingredients, timeout)
                    await self._add_ingredients_to_day(
                        conn, day_id, table, date, timeout, mode="accumulate"
                    )
                    logger.debug("✅ Meal saved successfully")
        except Exception as e:
            logger.error(f"Failed to save meal: {e}", exc_info=True)
            raise

    async def save_daily_log(
        self,
        username: str,
        modified_ingredients: List[IngredientItem],
        table: List[IngredientItem],
        date: dt.datetime,
        timeout: int = 40,
    ) -> None:
        """
        Synchronizes the complete daily log state for the user.

        Args:
            username (str): User's username.
            modified_ingredients (List[IngredientItem]): Ingredients with updated per-100g macros.
            table (List[IngredientItem]): Complete list of ingredients that SHOULD remain in the day log.
            date (dt.datetime): Date of the daily record.
            timeout (int): Query timeout in seconds. Default: 40.

        Raises:
            ValueError: If timeout < 1.
            ConnectionError: If the database pool is not initialized.
            TimeoutError: If query exceeds timeout.
            RuntimeError: On unexpected database errors.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")
        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.info(
            f"Syncing daily log for {username} on {date.date()} ({len(table)} items)"
        )
        try:
            async with self.db.acquire() as conn:
                async with conn.transaction():
                    day_id = await self._add_day(conn, username, date, timeout)
                    await self._change_ingredient(conn, modified_ingredients, timeout)
                    await self._add_ingredients_to_day(
                        conn, day_id, table, date, timeout, mode="sync"
                    )
                    logger.debug("✅ Daily log synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync daily log: {e}", exc_info=True)
            raise

    async def _add_day(
        self, conn: asyncpg.Connection, username: str, created_at: dt.datetime, timeout: int = 20
    ) -> int:
        """
        Creates or retrieves a daily record ID for the user.

        Args:
            conn: Active asyncpg database connection.
            username (str): User's username.
            created_at (dt.datetime): Date of the daily record.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            int: The day record ID.
        """
        create_query = """
            INSERT INTO day (record_date, username)
            VALUES ($1, $2)
            ON CONFLICT (record_date, username) DO NOTHING
            RETURNING id
        """
        get_query = "SELECT id FROM day WHERE record_date = $1 AND username = $2"

        day_id = await conn.fetchval(
            create_query, created_at, username, timeout=timeout
        )
        if day_id is None:
            day_id = await conn.fetchval(
                get_query, created_at, username, timeout=timeout
            )
            logger.debug(f"✅ Retrieved existing day_id: {day_id}")
        else:
            logger.debug(f"✅ Created new day_id: {day_id}")
        return day_id

    async def _add_ingredients_to_day(
        self,
        conn: asyncpg.Connection,
        day_id: int,
        ingredients: List[IngredientItem],
        created_at: dt.datetime,
        timeout: int = 20,
        mode: str = "accumulate",
    ) -> bool:
        """
        Links ingredients to a daily record. Supports accumulation or full state sync.

        Args:
            conn: Active asyncpg database connection.
            day_id (int): Target day record ID.
            ingredients (List[IngredientItem]): List of IngredientItem objects.
            created_at (dt.datetime): Timestamp for the entry.
            timeout (int): Query timeout in seconds. Default: 20.
            mode (str): "accumulate" (adds weight) or "sync" (replaces weight & deletes missing).

        Returns:
            bool: True on success.
        """
        logger.debug(
            f"Linking {len(ingredients)} ingredients to day {day_id} (mode: {mode})"
        )

        resolved_ids = []
        resolved_weights = []
        for ing in ingredients:
            ing_id, _ = await self._get_or_create_ingredient(conn, ing, timeout)
            resolved_ids.append(ing_id)
            resolved_weights.append(ing.weight)

        if mode == "sync":
            if resolved_ids:
                await conn.execute(
                    """DELETE FROM list_ingredients WHERE id_day = $1 AND id_ingredient NOT IN (SELECT unnest($2::int[]))""",
                    day_id,
                    resolved_ids,
                    timeout=timeout,
                )
            else:
                await conn.execute(
                    "DELETE FROM list_ingredients WHERE id_day = $1",
                    day_id,
                    timeout=timeout,
                )
            logger.debug(f"Sync mode: Removed unmatched ingredients")

        if mode == "sync":
            upsert_query = """
                INSERT INTO list_ingredients (id_day, id_ingredient, weight, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id_day, id_ingredient) DO UPDATE SET weight = EXCLUDED.weight, created_at = EXCLUDED.created_at
            """
        else:
            upsert_query = """
                INSERT INTO list_ingredients (id_day, id_ingredient, weight, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id_day, id_ingredient) DO UPDATE SET weight = list_ingredients.weight + EXCLUDED.weight
            """

        for ing_id, weight in zip(resolved_ids, resolved_weights):
            await conn.execute(
                upsert_query, day_id, ing_id, weight, created_at, timeout=timeout
            )

        logger.debug(f"✅ Ingredients linked to day {day_id}")
        return True

    async def _change_ingredient(
        self, conn: asyncpg.Connection, modified_ingredients: List[IngredientItem], timeout: int = 20
    ) -> None:
        """
        Updates per-100g nutritional values for existing user-owned ingredients.

        Args:
            conn: Active asyncpg database connection.
            modified_ingredients (List[IngredientItem]): Ingredients with updated macros.
            timeout (int): Query timeout in seconds. Default: 20.
        """
        if not modified_ingredients:
            return

        logger.debug(f"Updating macros for {len(modified_ingredients)} ingredients")
        update_macros_query = """
            UPDATE ingredient SET calories = $1, proteins = $2, fats = $3, carbohydrates = $4
            WHERE id = $5 AND owner_username = $6
        """
        for ingredient in modified_ingredients:
            ing_id, status = await self._get_or_create_ingredient(
                conn, ingredient, timeout
            )
            if status == "get":
                await conn.execute(
                    update_macros_query,
                    ingredient.calories,
                    ingredient.proteins,
                    ingredient.fats,
                    ingredient.carbohydrates,
                    ing_id,
                    ingredient.owner,
                    timeout=timeout,
                )

    async def _get_or_create_ingredient(
        self, conn: asyncpg.Connection, ingredient: IngredientItem, timeout: int = 20, max_retries: int = 3
    ) -> Tuple[int, str]:
        """
        Resolves an ingredient ID, creating it if necessary with a semantic embedding.

        Implements retry logic to handle race conditions on unique constraints.

        Args:
            conn: Active asyncpg database connection.
            ingredient (IngredientItem): Ingredient to resolve.
            timeout (int): Query timeout in seconds. Default: 20.
            max_retries (int): Maximum retry attempts on conflict. Default: 3.

        Returns:
            Tuple[int, str]: Tuple of (ingredient_id, status) where status is "get" or "create".

        Raises:
            RuntimeError: If failed to create ingredient after max_retries attempts.
        """
        logger.debug(f"Resolving ingredient: '{ingredient.name}'")

        row = await conn.fetchrow(
            "SELECT id FROM ingredient WHERE name = $1 AND owner_username = $2",
            ingredient.name,
            ingredient.owner,
            timeout=timeout,
        )
        if row:
            return row["id"], "get"

        np_array = await asyncio.to_thread(
            self.encoder.encode,
            ingredient.name,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        embedding = np_array.tolist()

        for attempt in range(max_retries):
            try:
                result = await conn.fetchval(
                    """
                    INSERT INTO ingredient (name, calories, proteins, fats, carbohydrates, owner_username, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (name, owner_username) DO UPDATE SET 
                        calories = EXCLUDED.calories, proteins = EXCLUDED.proteins,
                        fats = EXCLUDED.fats, carbohydrates = EXCLUDED.carbohydrates
                    RETURNING id;
                    """,
                    ingredient.name,
                    ingredient.calories,
                    ingredient.proteins,
                    ingredient.fats,
                    ingredient.carbohydrates,
                    ingredient.owner,
                    embedding,
                    timeout=timeout,
                )
                logger.debug(f"✅ Created/Updated ingredient_id: {result}")
                return result, "create"
            except asyncpg.UniqueViolationError:
                logger.warning(
                    f"Unique violation on attempt {attempt+1}, retrying select..."
                )
                row = await conn.fetchrow(
                    "SELECT id FROM ingredient WHERE name = $1 AND owner_username = $2",
                    ingredient.name,
                    ingredient.owner,
                    timeout=timeout,
                )
                if row:
                    return row["id"], "get"
            except Exception as e:
                logger.error(f"Error in _get_or_create_ingredient: {e}", exc_info=True)
                raise

        raise RuntimeError(
            f"Failed to create ingredient '{ingredient.name}' after {max_retries} retries"
        )

    async def _get_user(
        self, username: str, timeout: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches a user from the database by username.

        Args:
            username (str): User's username.
            timeout (int): Query timeout in seconds. Default: 20.

        Returns:
            Optional[Dict[str, Any]]: User data as dictionary, or None if not found.

        Raises:
            ValueError: If timeout is less than 1.
            ConnectionError: If database connection is not established.
            RuntimeError: If an unexpected database error occurs.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        if not self.db:
            raise ConnectionError("Database connection not established")

        logger.debug(f"Fetching user: {username}")
        query = "SELECT * FROM users WHERE username = $1"

        try:
            async with self.db.acquire() as conn:
                response = await conn.fetchrow(query, username, timeout=timeout)
            if response:
                return dict(response)
            return None
        except Exception as e:
            logger.error(f"Error in _get_user: {e}", exc_info=True)
            raise
