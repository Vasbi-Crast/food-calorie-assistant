import requests
import httpx
import streamlit as st
from dotenv import load_dotenv
import os
import datetime as dt
from typing import Optional, Dict, Union, Any
import uuid

from translator import Translator, IngredientTranslator, get_canonical_name

t = Translator()

ing_translator = IngredientTranslator(app_languages=t.available_languages)

load_dotenv()
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
if not SERVER_URL:
    raise ValueError("SERVER_URL environment variable is not set")

INACTIVITY_MINUTES = 15

# ==============================================================================
# API REQUEST WRAPPERS
# ==============================================================================


def _handle_response(resp: Union[requests.Response, httpx.Response]) -> Optional[Dict]:
    """Unified handler for API responses (sync and async).

    Parses JSON, handles HTTP errors (401, 422), and formats validation messages.

    Args:
        resp (Union[requests.Response, httpx.Response]): Response object from
            either requests or httpx client.

    Returns:
        Optional[Dict]: Parsed JSON on success (2xx), None on error.
    """
    if resp.status_code < 400:
        return resp.json()

    try:
        data = resp.json()
    except Exception:
        data = {}

    detail = data.get("detail", "Unknown error")
    base_msg = t(f"error.http.{resp.status_code}")

    if resp.status_code == 401:
        if detail == "USER_NOT_FOUND":
            st.error(t("error.auth.user_not_found"))
        elif detail == "INVALID_PASSWORD":
            st.error(t("error.auth.invalid_password"))
        else:
            st.session_state["auth_error"] = t("error.session.inactive")
            st.switch_page("main_page.py")

    elif resp.status_code == 409:
        if detail == "username":
            st.error(t("error.form.user_already_exists"))
        else:
            st.error(t("error.form.duplicate_error").format(field=detail))

    elif resp.status_code == 422:
        detail_data = data.get("errors", [])
        if isinstance(detail_data, list):
            for err in detail_data:
                field = t(f"error.fields.{err.get('field', 'unknown')}")
                error_type = err.get("type_error", "value_error")
                ctx = err.get("ctx", {})

                if error_type == "missing":
                    text_err = t("error.validation.missing")
                elif error_type == "string_too_short":
                    num_char = ctx.get("min_length", "inf")
                    text_err = t("error.validation.string_too_short").format(
                        num_char=num_char, field=field
                    )
                elif error_type == "string_too_long":
                    num_char = ctx.get("max_length", "inf")
                    text_err = t("error.validation.string_too_long").format(
                        num_char=num_char, field=field
                    )
                elif error_type == "greater_than_equal":
                    text_err = t("error.validation.greater_than_equal").format(
                        field=field
                    )
                elif error_type == "less_than_equal":
                    text_err = t("error.validation.less_than_equal").format(field=field)
                elif error_type == "greater_than":
                    text_err = t("error.validation.greater_than").format(field=field)
                elif error_type == "less_than":
                    text_err = t("error.validation.less_than").format(field=field)
                elif error_type == "value_error" and field == "password":
                    text_err = t("error.validation.value_error.password").format(
                        form_pattern=t("ui.password.pattern")
                    )
                elif error_type == "int_parsing":
                    text_err = t("error.validation.int_parsing")
                elif error_type == "float_parsing":
                    text_err = t("error.validation.float_parsing")
                elif error_type == "date_parsing":
                    text_err = t("error.validation.date_parsing")
                else:
                    text_err = err.get("msg", t("error.validation.generic"))

                st.error(f"🔴 {field}: {text_err}")
        else:
            st.error(f"{base_msg}: {detail}")
    else:
        st.error(f"{base_msg}: {detail}")
    return None


async def async_api_request(
    method: str, endpoint: str, timeout: float = 20, **kwargs
) -> Optional[Dict]:
    """
    Asynchronous wrapper for API requests using httpx.

    Handles network errors, HTTP status codes (401, 422, etc.), and validation errors.
    Automatically injects the Authorization Bearer token from session_state.

    ⚠️ This is a coroutine — must be called with `await`.

    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE).
        endpoint (str): API endpoint path (without base URL).
        timeout (float, optional): Request timeout in seconds. Defaults to 20.
        **kwargs: Additional arguments for httpx.AsyncClient.request()
                  (e.g., json, params, headers).

    Returns:
        Optional[Dict]: Parsed JSON response on success (2xx), None on error.
    """
    headers = kwargs.get("headers", {})
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as asynch_client:
        try:
            resp = await asynch_client.request(
                method, f"{SERVER_URL}/{endpoint}", timeout=timeout, **kwargs
            )

        except httpx.TimeoutException:
            st.error(t("error.network.timeout"))
            return None
        except httpx.ConnectError:
            st.error(t("error.network.connection"))
            return None
        except Exception as e:
            st.error(t("error.network.generic").format(error=str(e)))
            return None

        return _handle_response(resp)


def api_request(
    method: str, endpoint: str, timeout: float = 20, **kwargs
) -> Optional[Dict]:
    """
    Synchronous wrapper for API requests using requests.

    Handles network errors, HTTP status codes (401, 422, etc.), and validation errors.
    Automatically injects the Authorization Bearer token from session_state.

    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE).
        endpoint (str): API endpoint path (without base URL).
        timeout (float, optional): Request timeout in seconds. Defaults to 20.
        **kwargs: Additional arguments for requests.Session.request()
                  (e.g., json, params, headers).

    Returns:
        Optional[Dict]: Parsed JSON response on success (2xx), None on error.
    """
    headers = kwargs.get("headers", {})
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers
    with requests.Session() as client:
        try:
            resp = client.request(
                method, f"{SERVER_URL}/{endpoint}", timeout=timeout, **kwargs
            )
        except requests.exceptions.Timeout:
            st.error(t("error.network.timeout"))
            return None
        except requests.exceptions.ConnectionError:
            st.error(t("error.network.connection"))
            return None
        except requests.exceptions.RequestException as e:
            st.error(t("error.network.generic").format(error=str(e)))
            return None

        return _handle_response(resp)


async def translate_table_ingredients() -> bool:
    """Synchronizes ingredient names in the session state table with backend translations.

    Calls IngredientTranslator.sync() to fetch/normalize translations,
    updates the local cache (removing obsolete keys), and renames ingredients
    in the current table to match canonical keys.

    Returns:
        bool: True if synchronization was attempted (ingredients existed),
            False if the table was empty.
    """
    ings = st.session_state.get("table_ingredients", [])
    if not ings:
        return False
    mapping = await ing_translator.sync(async_api_request)

    if mapping:
        for ing in ings:
            raw_name = ing.get("name")
            if not raw_name:
                continue

            if raw_name in mapping:
                ing["name"] = mapping[raw_name]
        return True
    return False


def parse_meals(nutritional_info: list[dict]) -> None:
    """Parses LLM/API response into a structured ingredients table for session state.

    Converts each item in the nutritional_info list into a standardized dictionary
    with UUID index, numeric fields cast to float, and default values for missing keys.
    Stores the result in st.session_state["table_ingredients"].

    Args:
        nutritional_info (list[dict]): List of ingredient dictionaries from the backend
            or LLM. Expected keys: name, weight, calories, proteins, fats,
            carbohydrates, owner.

    Note:
        Uses safe_float conversion to prevent crashes on malformed numeric values.
        Each row receives a unique UUID for stable Streamlit component keying.
    """

    def safe_float(value: Any) -> float:
        """Safely converts a value to float, returning 0.0 on failure."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    if not nutritional_info:
        return

    rows = []
    for item in nutritional_info:
        rows.append(
            {
                "idx": str(uuid.uuid4()),
                "name": item.get("name"),
                "weight": safe_float(item.get("weight")),
                "calories": safe_float(item.get("calories")),
                "proteins": safe_float(item.get("proteins")),
                "fats": safe_float(item.get("fats")),
                "carbohydrates": safe_float(item.get("carbohydrates")),
                "owner": item.get("owner", "admin"),
            }
        )

    st.session_state["table_ingredients"] = rows


def check_activity() -> None:
    """Checks user inactivity and logs out if timeout threshold is exceeded.

    Compares the current UTC time with st.session_state["last_active_time"].
    If the difference exceeds INACTIVITY_MINUTES, clears the session via log_out(),
    sets an auth error message, and redirects to the login page.

    Updates last_active_time to the current time on every successful check.

    Note:
        Uses timezone-aware datetime objects (dt.timezone.utc) for reliable
        comparison across different server/client timezones.
    """
    last_active = st.session_state.get("last_active_time")
    if last_active:
        now = dt.datetime.now(dt.timezone.utc)

        if now - last_active >= dt.timedelta(minutes=INACTIVITY_MINUTES):
            log_out()
            st.session_state["auth_error"] = t("error.session.inactive")
            st.switch_page("main_page.py")

        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)


def check_auth() -> None:
    """Verifies that the user has a valid authentication token in session state.

    If st.session_state["token"] is missing or falsy, sets an auth error message
    and redirects to the login page (main_page.py).

    Note:
        Should be called at the start of protected pages to enforce authentication.
    """
    if not st.session_state.get("token"):
        st.session_state["auth_error"] = t("error.session.logged_in")
        st.switch_page("main_page.py")


def log_out() -> None:
    """Clears all user-specific data from session state to end the authenticated session.

    Resets the following keys to None or empty values:
        - username, token, last_active_time
        - user_info, days_info, daily_nutrition_norms
        - users_ingredients

    Note:
        Does not call the backend logout endpoint (stateless JWT auth).
        Client-side session clearance is sufficient for logout flow.
    """
    st.session_state["username"] = ""
    st.session_state["last_active_time"] = None
    st.session_state["user_info"] = None
    st.session_state["days_info"] = None
    st.session_state["daily_nutrition_norms"] = None
    st.session_state["users_ingredients"] = None
    st.session_state["token"] = None
