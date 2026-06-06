"""Pre-run synchronization script for ingredient translations.

Generates base translations from CSV and syncs missing translations
via the backend API. Runs once on first frontend startup.

Usage:
    python helper/pre_run_sync.py

Or via docker-compose command in frontend service.
"""
import asyncio
import os
import httpx
import sys
from pathlib import Path

CACHE_FILE = "resources/locales/ingredient_translations.json"
SERVER_URL = os.getenv("SERVER_URL", "http://backend:8000")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

APP_DIR = Path(__file__).parent.parent.resolve()
HELPER_DIR = Path(__file__).parent.resolve()

sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(HELPER_DIR))

from init_translation_dict import generate_base_translations_from_csv


class AuthenticatedClient:
    """HTTP client with automatic JWT authentication for backend API requests."""
    
    def __init__(self, base_url: str, username: str, password: str):
        """Initialize authenticated client.
        
        Args:
            base_url: Backend API base URL.
            username: Admin username for authentication.
            password: Admin password for authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = None

    async def authenticate(self) -> bool:
        """Authenticate with backend and store JWT token.
        
        Returns:
            bool: True if authentication succeeded, False otherwise.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/authentication",
                    json={"username": self.username, "password": self.password},
                    timeout=10.0
                )
                resp.raise_for_status()
                data = resp.json()
                self.token = data.get("access_token")
                if self.token:
                    print(f"✅ Authenticated as {self.username}")
                    return True
                print("❌ No access_token in response")
                return False
        except Exception as e:
            print(f"❌ Authentication failed: {type(e).__name__}: {e}")
            return False

    async def request(self, method: str, endpoint: str, **kwargs):
        """Send authenticated request to backend API.
        
        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            **kwargs: Additional arguments for httpx.AsyncClient.request().
            
        Returns:
            Any: Parsed JSON response.
            
        Raises:
            RuntimeError: If authentication fails.
        """
        if not self.token and not await self.authenticate():
            raise RuntimeError("Authentication required but failed")
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, f"{self.base_url}/{endpoint.lstrip('/')}", headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()


async def wait_for_backend(url: str, max_attempts: int = 30, delay: float = 2.0) -> bool:
    """Wait for backend API to become available.
    
    Polls /docs endpoint until response received or max_attempts reached.
    
    Args:
        url: Backend base URL to check.
        max_attempts: Maximum connection attempts (default: 30).
        delay: Seconds between attempts (default: 2.0).
        
    Returns:
        bool: True if backend responded, False if all attempts failed.
    """
    health_url = f"{url}/docs"
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(health_url, timeout=5.0)
                if resp.status_code < 500:
                    print(f"✅ Backend ready after {attempt + 1} attempts")
                    return True
        except httpx.ConnectError:
            print(f"⏳ Waiting for backend... attempt {attempt + 1}/{max_attempts}")
        except Exception as e:
            print(f"⚠️ Backend check error: {type(e).__name__}: {e}")
        await asyncio.sleep(delay)
    print("❌ Backend not available after all attempts")
    return False


async def main():
    """Main entry point: generate base translations and sync via API.
    
    Workflow:
    1. Skip if CACHE_FILE already exists.
    2. Generate base translations from helper/nutrition.csv.
    3. Wait for backend to be ready.
    4. Authenticate as admin.
    5. Sync missing translations via backend API.
    
    Exits early on any failure (non-fatal, logged only).
    """
    if os.path.exists(CACHE_FILE):
        print("✅ Translations cache found. Skipping sync.")
        return

    print("⏳ First run detected. Generating base translations...")
    
    try:
        csv_path = Path("helper/nutrition.csv").resolve()
        output_path = Path(CACHE_FILE).resolve()
        
        generate_base_translations_from_csv(
            csv_path=str(csv_path),
            col_with_ing_name="name",
            output_path=str(output_path),
            extra_languages=["ru", "eu"],
        )
        print(f"✅ Base translations generated at {CACHE_FILE}")
    except Exception as e:
        print(f"❌ Base generation failed: {type(e).__name__}: {e}")
        return

    print("🔍 Waiting for backend to be ready...")
    if not await wait_for_backend(SERVER_URL):
        print("⚠️ Backend not ready, skipping API sync")
        return

    print("🔐 Authenticating as admin...")
    api = AuthenticatedClient(SERVER_URL, username="admin", password=ADMIN_PASSWORD)
    
    if not await api.authenticate():
        print("⚠️ Authentication failed, skipping API sync")
        return

    print("🌐 Starting API sync for translations...")
    try:
        from translator import IngredientTranslator
        
        translator = IngredientTranslator()
        result = await translator.sync(api.request, limit_to_lang={"ru", "eu"})
        if result:
            print(f"✅ API sync completed: {len(result)} keys updated")
        else:
            print("ℹ️ API sync completed: no new translations needed")
            
    except ImportError as e:
        print(f"⚠️ IngredientTranslator not available: {e}")
    except Exception as e:
        print(f"⚠️ API sync failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())