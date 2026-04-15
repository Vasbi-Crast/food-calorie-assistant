import requests
import streamlit as st
import json
import datetime as dt
from typing import List
from dotenv import load_dotenv
import os

# === Configuration ===
load_dotenv()
SERVER_URL = os.getenv("SERVER_URL")

INACTIVITY_MINUTES = 10

PAGE_BEFORE_AUTHORIZATIONS = ["login_page_sh", "register_page_sh"]

USERNAME_PATTERN_TEXT = """
• Minimum length: 3 characters
• Maximum length: 20 characters
• No leading or trailing spaces
• Case-insensitive (stored as lowercase)
"""

PASSWORD_PATTERN_TEXT = """
• Minimum length: 6 characters\n
• At least 3 digits\n
• At least one uppercase and one lowercase letter\n
• At least one special character (#, !, $, ^, *, @)\n
"""

# === Error Mappings (EN) ===
HTTP_STATUS_MESSAGES = {
    400: "⚠️ Bad Request",
    401: "🔐 Authorization Failed",
    403: "🚫 Access Denied",
    404: "📍 Not Found",
    422: "📝 Validation Error",
    500: "💥 Internal Server Error",
    504: "⏳ Gateway Timeout",
}

ERROR_TYPE_MESSAGES = {
    "missing": "This field is required",
    "string_too_short": "Value is too short (min __num_char__ characters for __field__)",
    "string_too_long": "Value is too long (max __num_char__ characters for __field__)",
    "greater_than_equal": "Value must be >= minimum allowed",
    "less_than_equal": "Value must be <= maximum allowed",
    "greater_than": "Value must be > minimum allowed",
    "less_than": "Value must be < maximum allowed",
    "value_error": "Incorrect form __field__.\nRulles:\n__form_pattern__",
    "int_parsing": "Must be an integer number",
    "float_parsing": "Must be a decimal number",
    "date_parsing": "Invalid date format (YYYY-MM-DD)",
    "enum": "Invalid value (choose from options)",
}


def get_error_message(error_type: str) -> str:
    """Returns user-friendly message for a given error type."""
    return ERROR_TYPE_MESSAGES.get(error_type, "Invalid value provided")


# === Navigation ===
def check_activity (old_page: str):
    if not any(st.session_state[page] for page in PAGE_BEFORE_AUTHORIZATIONS):
        if dt.datetime.now(dt.timezone.utc) < st.session_state["last_active_time"] + dt.timedelta(minutes=INACTIVITY_MINUTES):
            st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)
        else:
            log_out()
            st.session_state["auth_error"] = f"⏳ You've been inactive for too long"
            st.session_state[old_page] = False
            st.session_state["login_page_sh"] = True
            st.rerun()
    elif old_page == "login_page_sh":
        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)   
    
def log_out():
    st.session_state["username"] = ""
    st.session_state["last_active_time"] = None
    st.session_state["user_info"] = None
    st.session_state["days_info"] = None
    st.session_state["daily_nutrition_norms"] = None

def change_page(old_page: str, new_page: str):
    """Switches active page in session state."""
    check_activity(old_page)
    st.session_state[old_page] = False
    st.session_state[new_page] = True
    if new_page == "login_page_sh":
        log_out()
    st.rerun()


# === API Wrapper ===
def api_request(method: str, endpoint: str, old_page: str, **kwargs) -> dict | None:
    """
    Unified wrapper for API requests.
    Handles network errors, HTTP errors, and validation errors.
    Automatically adds Auth token if available.
    Returns JSON response on success, None on error.
    """
    check_activity(old_page)
    # Add Auth Header if token exists
    headers = kwargs.get("headers", {})
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers

    # Network Request
    try:
        resp = requests.request(
            method, f"{SERVER_URL}/{endpoint}", timeout=20, **kwargs
        )
    except requests.exceptions.Timeout:
        st.error("⏳ Server timeout. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to server. Is it running?")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Request failed: {str(e)}")
        return None

    # HTTP Error Handling
    if resp.status_code >= 400:
        try:
            data = resp.json()
        except:
            data = {}

        detail = data.get("detail", "Unknown error")
        errors = data.get("errors", [])
        base_msg = HTTP_STATUS_MESSAGES.get(
            resp.status_code, f"❌ Error {resp.status_code}"
        )

        # Problems with authorization
        if resp.status_code == 401:
            if detail == "USER_NOT_FOUND":
                st.error(f"🔐 The user does not exist. Please register.")
            elif detail == "INVALID_PASSWORD":
                st.error(f"🔐 Incorrect password. Try again.")
            else:
                st.session_state["auth_error"] = f"⏳ You've been inactive for too long"
                change_page(old_page, "login_page_sh")

        # Handle Validation Errors (422) with field-specific messages
        elif resp.status_code == 422 and errors:
            for err in errors:
                field = err.get("field", "unknown")
                error_type = err.get("type_error", "value_error")
                text_err = get_error_message(error_type).replace("__field__", field)
                if error_type in ["string_too_short", "string_too_long"]:
                    num_char = 3
                    text_err = text_err.replace("__num_char__", str(num_char))
                elif error_type == "value_error" and field == "password":
                    text_err = text_err.replace(
                        "__form_pattern__", PASSWORD_PATTERN_TEXT
                    )
                else:
                    text_err = get_error_message(error_type)
                st.error(f"🔴 {field}: {text_err}")

        else:
            # Show general error for other status codes
            st.error(f"{base_msg}: {detail}")

        return None

    # Success
    return resp.json()


# === Helpers ===
bmr = {
    "Sedentary lifestyle": 1.2,
    "Light training 1-2 times a week": 1.375,
    "3-5 training sessions per week": 1.55,
    "Daily intensive training": 1.725,
    "Heavy physical labor": 1.9,
}


def index_gender(gender: str) -> int:
    """Converts gender string to index for UI components."""
    return 0 if gender == "m" else (1 if gender == "w" else 2)


def index_lifestyle(lifestyle: str) -> int | None:
    """Converts lifestyle string to index for UI components."""
    for i, key in enumerate(bmr.keys()):
        if lifestyle == key:
            return i
    return None


# === API Functions ===

def get_meal_macros(
    old_page: str, image_base64: str, user_description: str
) -> dict | None:
    """
    Sends image for ingredient recognition and nutrition search.
    No authentication required.
    """
    payload = {"image_base64": image_base64, "user_description": user_description}

    response = api_request(
        "POST", "ingredient_recognition", old_page=old_page, json=payload
    )

    if response:
        # Handle nested result structure from LLM assistant
        result = response.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                st.warning("⚠️ Failed to parse nutrition data.")
                return None

        if result:
            return result
        else:
            st.warning("⚠️ Nutritional information not available for this image.")
            return None
    return None

def authorization(old_page: str, username: str, password: str) -> bool:
    """
    User login. Saves token to session_state on success.
    """
    # Frontend validation (critical only)
    if not username.strip():
        st.error("⚠️ Username is required.")
        return False
    if not password.strip():
        st.error("⚠️ Password is required.")
        return False

    payload = {"username": username.lower(), "password": password}

    # old_page='login_page_sh' ensures we stay or redirect correctly on 401
    response = api_request("POST", "authentication", old_page=old_page, json=payload)

    if response:
        st.session_state["token"] = response.get("access_token")
        st.session_state["username"] = username
        return True
    return False

def registration(
    old_page: str,
    username: str,
    password: str,
    re_password: str,
    age: int,
    lifestyle: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """
    Registers a new user.
    Frontend validates password match; Backend validates types/ranges.
    """
    # Critical Frontend Validation
    if not username.strip():
        st.error("⚠️ Username is required.")
        return False
    if not password.strip():
        st.error("⚠️ Password is required.")
        return False
    if password != re_password:
        st.error("⚠️ Passwords do not match.")
        return False

    # Data Transformation
    if gender == ":blue[Man]":
        gender = "m"
    elif gender == ":red[Woman]":
        gender = "w"
    else:
        gender = "None"

    payload = {
        "username": username,
        "password": password,
        "age": age,
        "bmr": bmr.get(lifestyle, 1.2),
        "gender": gender,
        "weight": weight,
        "height": height,
    }

    response = api_request("POST", "registration", old_page=old_page, json=payload)
    return response is not None

def get_user_information(old_page: str) -> dict | None:
    """
    Retrieves current user profile.
    Requires authentication (token added by wrapper).
    """
    response = api_request("GET", "users/me", old_page=old_page)

    if response:
        # Map numeric BMR back to lifestyle string for UI
        bmr_val = response.get("bmr")
        for key, val in bmr.items():
            if val == bmr_val:
                response["lifestyle"] = key
                break
        return response
    return {}

def update_user_info(
    old_page: str,
    age: int,
    lifestyle: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """
    Updates current user profile.
    Requires authentication.
    """
    # Data Transformation
    if gender == ":blue[Man]":
        gender = "m"
    elif gender == ":red[Woman]":
        gender = "w"
    else:
        gender = "None"

    payload = {
        "age": age,
        "bmr": bmr.get(lifestyle, 1.2),
        "gender": gender,
        "weight": weight,
        "height": height,
    }

    response = api_request("PUT", "users/me", old_page=old_page, json=payload)
    return response is not None

def get_info_nutrition(
    old_page: str,
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> dict | None:
    """
    Retrieves nutrition history for a time period.
    Requires authentication.
    """
    # Date Formatting
    if isinstance(time_span, list) and len(time_span) == 2:
        st_time_span = min(time_span).strftime("%Y-%m-%d")
        fin_time_span = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        st_time_span = time_span.strftime("%Y-%m-%d")
        fin_time_span = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return {}

    # Query Params for GET request
    params = {
        "st_time_span": st_time_span,
        "fin_time_span": fin_time_span,
    }

    response = api_request("GET", "info_nutrition", old_page=old_page, params=params)

    if response:
        if one_day:
            return response.get(st_time_span, {})
        return response
    return {}

def get_daily_nutrition_norms(old_page: str, user_info: dict) -> dict | None:
    """
    Calculates daily nutrition norms based on user parameters.
    Requires authentication.
    """
    # Basic Check
    required_keys = ["age", "bmr", "gender", "weight", "height"]
    if not all(k in user_info for k in required_keys):
        st.error("⚠️ Missing required user information.")
        return {}

    response = api_request(
        "POST", "daily_nutrition_norms", old_page=old_page, json=user_info
    )
    return response
