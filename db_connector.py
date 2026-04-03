import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
load_dotenv()


class DB_connector:
    """A class for connecting to and working with a database"""

    def __init__(self):
        self.db: asyncpg.Pool | None = None

    async def connection(self):
        """connecting to the database"""
        db_kwargs = json.loads(os.getenv("DB_CONFIG", "{}"))
        self.db = await asyncpg.create_pool(**db_kwargs)

    async def close(self):
        """Closing the database connection"""
        if self.db:
            await self.db.close()
            self.db = None

    async def add_user(
        self,
        user_name: str,
        password: str,
        gender: str,
        weight: float,
        height: float,
        timeout: int = 20,
    ) -> bool:
        """
        A class for connecting to and working with a database.

        Args:
            user_name (str): A unique username for authorization.
            password (str): User's password.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")
            
        query = '''
            INSERT INTO users (users_name, hash_password, height, weight, gender)
            VALUES ($1, $2, $3, $4, $5)'''

        try:
            async with self.db.acquire() as conn:
                await conn.execute(
                    query,
                    user_name,
                    pwd_context.hash(password),
                    height,
                    weight,
                    gender,
                    timeout=timeout
                )
            return True

        except asyncpg.UniqueViolationError:
            return False
        except asyncio.TimeoutError as e:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)") from e
        except Exception as e:
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}") from e


    async def verify(self, user_name: str, password: str, timeout: int = 20) -> str:
        """
        A function for user authentication.

        Args:
            user_name (str): A unique username for authorization.
            password (str): User's password.
            timeout (int): Time limit for accessing the db.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        try:
            user = await self._get_user(user_name, timeout)

            if not user:
                return "USER_NOT_FOUND"

            if pwd_context.verify(password, user["hash_password"]):
                return "SUCCESSFUL"

            return "INVALID_PASSWORD"

        except asyncio.TimeoutError as e:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)") from e
        except Exception as e:
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}") from e

    async def _get_user(self, user_name: str, timeout: int):
        """Finding a user from the database"""
        query = 'SELECT users_name, hash_password FROM users WHERE users_name = $1'

        async with self.db.acquire() as conn:
            response = await conn.fetchrow(query, user_name, timeout=timeout)

        if response:
            return dict(response)
        return None