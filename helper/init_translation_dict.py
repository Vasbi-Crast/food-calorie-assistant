"""Pre-run synchronization script for ingredient translations.

This module handles the initial setup of ingredient translations on first application
startup. It performs three main tasks:

1. Generates a base translation dictionary from the nutrition CSV file
2. Waits for the backend API to become available
3. Synchronizes missing translations via the backend API using authenticated requests

The script is designed to run once during frontend initialization and can be safely
skipped on subsequent runs if the translation cache already exists.

Typical usage:
    $ python helper/pre_run_sync.py

Or as part of frontend startup via docker-compose command:
    command: sh -c "python helper/pre_run_sync.py && streamlit run main_page.py ..."

Attributes:
    CACHE_FILE (str): Path to the ingredient translations JSON cache file.
    SERVER_URL (str): Base URL for the backend API, from environment or default.
    ADMIN_PASSWORD (str): Admin password for authentication, from environment or default.
    APP_DIR (Path): Resolved path to the application root directory (/app).
    HELPER_DIR (Path): Resolved path to the helper scripts directory (/app/helper).

Note:
    This script modifies sys.path to enable imports from both APP_DIR and HELPER_DIR.
    Ensure the backend is running and accessible before executing the sync step.
"""
import asyncio
import os
import httpx
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set

# =============================================================================
# Configuration Constants
# =============================================================================

CACHE_FILE: str = "resources/locales/ingredient_translations.json"
"""Path to the ingredient translations JSON cache file (relative to /app)."""

SERVER_URL: str = os.getenv("SERVER_URL", "http://backend:8000")
"""Base URL for backend API requests. Defaults to Docker service name."""

ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")
"""Password for admin user authentication. Defaults to 'admin' for development."""

APP_DIR: Path = Path(__file__).parent.parent.resolve()
"""Resolved absolute path to the application root directory (/app)."""

HELPER_DIR: Path = Path(__file__).parent.resolve()
"""Resolved absolute path to the helper scripts directory (/app/helper)."""

# Add directories to sys.path for dynamic imports
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(HELPER_DIR))

class AuthenticatedClient:
    """HTTP client with automatic JWT authentication and token management.

    This client handles the authentication flow with the backend API and
    automatically attaches the JWT token to all subsequent requests.

    Attributes:
        base_url (str): Base URL for API endpoints (trailing slash removed).
        username (str): Username for authentication.
        password (str): Password for authentication.
        token (Optional[str]): Cached JWT access token after successful auth.

    Example:
        >>> api = AuthenticatedClient("http://backend:8000", "admin", "secret")
        >>> await api.authenticate()
        True
        >>> result = await api.request("POST", "translate_ingredients", json={...})
    """

    def __init__(self, base_url: str, username: str, password: str) -> None:
        """Initialize the authenticated HTTP client.

        Args:
            base_url: Base URL for the API (e.g., "http://backend:8000").
            username: Username for authentication (typically "admin").
            password: Password for authentication.
        """
        self.base_url: str = base_url.rstrip("/")
        self.username: str = username
        self.password: str = password
        self.token: Optional[str] = None

    async def authenticate(self) -> bool:
        """Authenticate with the backend API and store the JWT token.

        Makes a POST request to the /authentication endpoint with credentials.
        If successful, stores the access token for use in subsequent requests.

        Returns:
            bool: True if authentication succeeded and token was received,
                  False otherwise.

        Side Effects:
            - Prints authentication status to stdout
            - Sets self.token if authentication succeeds
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

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Send an authenticated HTTP request to the backend API.

        Automatically authenticates if no token is cached, then attaches
        the JWT token to the Authorization header before sending the request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            endpoint: API endpoint path (e.g., "translate_ingredients").
            **kwargs: Additional arguments passed to httpx.AsyncClient.request().

        Returns:
            Any: Parsed JSON response from the API.

        Raises:
            RuntimeError: If authentication is required but fails.
            httpx.HTTPStatusError: If the response status code indicates an error.
            httpx.RequestError: If the request fails to complete.

        Example:
            >>> result = await api.request(
            ...     "POST",
            ...     "translate_ingredients",
            ...     json={"ingredients": {"apple": ["ru"]}}
            ... )
        """
        if not self.token and not await self.authenticate():
            raise RuntimeError("Authentication required but failed")
        
        # Inject Authorization header
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.base_url}/{endpoint.lstrip('/')}",
                headers=headers,
                **kwargs
            )
            resp.raise_for_status()
            return resp.json()


async def wait_for_backend(
    url: str,
    max_attempts: int = 30,
    delay: float = 2.0
) -> bool:
    """Wait for the backend API to become available and responsive.

    Polls the /docs endpoint (which should always be available if FastAPI
    is running) until a response is received or max_attempts is reached.

    Args:
        url: Base URL of the backend API to check.
        max_attempts: Maximum number of connection attempts (default: 30).
        delay: Seconds to wait between attempts (default: 2.0).

    Returns:
        bool: True if backend responded successfully, False if all attempts failed.

    Side Effects:
        - Prints progress messages to stdout for each attempt
        - Logs success or failure status

    Example:
        >>> if await wait_for_backend("http://backend:8000"):
        ...     print("Backend is ready!")
    """
    health_url: str = f"{url}/docs"
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(health_url, timeout=5.0)
                # 2xx or 4xx means server is running; 5xx means server error but still "up"
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


async def main() -> None:
    """Main entry point for the pre-run synchronization process.

    Orchestrates the complete translation initialization workflow:

    1. Checks if translation cache already exists (skips if yes)
    2. Generates base translations from nutrition.csv
    3. Waits for backend API to be ready
    4. Authenticates as admin user
    5. Syncs missing translations via backend API

    This function is designed to be idempotent: running it multiple times
    is safe and will skip work that has already been completed.

    Side Effects:
        - May create or update CACHE_FILE with translation data
        - Prints progress and status messages to stdout
        - Makes HTTP requests to the backend API

    Note:
        The function exits early (returns) if:
        - Cache file already exists
        - Base translation generation fails
        - Backend is not available after retries
        - Authentication fails
        - Translation sync encounters an error (non-fatal, logged only)
    """
    # Step 1: Skip if cache already exists
    if os.path.exists(CACHE_FILE):
        print("✅ Translations cache found. Skipping sync.")
        return

    print("⏳ First run detected. Generating base translations...")
    
    # Step 2: Generate base translations from CSV
    try:
        csv_path: Path = Path("helper/nutrition.csv").resolve()
        output_path: Path = Path(CACHE_FILE).resolve()
        
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

    # Step 3: Wait for backend to be ready
    print("🔍 Waiting for backend to be ready...")
    if not await wait_for_backend(SERVER_URL):
        print("⚠️ Backend not ready, skipping API sync")
        return

    # Step 4: Authenticate as admin
    print("🔐 Authenticating as admin...")
    api = AuthenticatedClient(SERVER_URL, username="admin", password=ADMIN_PASSWORD)
    
    if not await api.authenticate():
        print("⚠️ Authentication failed, skipping API sync")
        return

    # Step 5: Sync translations via API
    print("🌐 Starting API sync for translations...")
    try:
        from translator import IngredientTranslator
        
        translator = IngredientTranslator()
        result: Dict[str, str] = await translator.sync(
            api.request,
            limit_to_lang={"ru", "eu"}
        )
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