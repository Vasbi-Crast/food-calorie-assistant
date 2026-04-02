from passlib.context import CryptContext
import asyncio

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DB_connector:
    '''A class for connecting to and working with a database'''

    def __init__(self):
        self.db = {"test": {"password_hash": pwd_context.hash("test")}}

    async def add_user(self, user_name:str, password:str, genre:str, weight:float, height:float, timeout: int):
        '''
        A class for connecting to and working with a database.
        
        Args:
            user_name (str): A unique username for authorization.
            password (str): User's password.
        '''
        try:
            if timeout < 1:
                raise ValueError("Timeout value must be greater than or equal to 1.")

            self.db[user_name] = {"password_hash": pwd_context.hash(password),
                              "genre": genre,
                              "weight": weight,
                              "height": height}
            return True

        except asyncio.TimeoutError:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)")

        except Exception as e:
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}")
        
    async def verify(self, user_name: str, password: str, timeout: int) -> str:
        '''
        A function for user authentication.
        
        Args:
            user_name (str): A unique username for authorization.
            password (str): User's password.
            timeout (int): Time limit for accessing the db.
        '''
        try:
            if timeout < 1:
                raise ValueError("Timeout value must be greater than or equal to 1.")

            user = await asyncio.wait_for(self._get_user(user_name), timeout=timeout)
            if not user:
                return 'USER_NOT_FOUND'
            
            if pwd_context.verify(password, user['password_hash']):
                return 'SUCCESSFUL'
            
            return 'INVALID_PASSWORD'

        except asyncio.TimeoutError:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)")

        except Exception as e:
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}")

    async def _get_user(self, user_name: str):
        '''Finding a user from the database'''
        if isinstance(user_name, str) and user_name:
            return self.db.get(user_name)
        return None