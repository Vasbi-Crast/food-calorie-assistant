import requests
import streamlit as st
import json
import datetime as dt
from typing import List, Dict, Optional, Any
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
    "value_error": "Incorrect form __field__.\nRules:\n__form_pattern__",
    "int_parsing": "Must be an integer number",
    "float_parsing": "Must be a decimal number",
    "date_parsing": "Invalid date format (YYYY-MM-DD)",
    "enum": "Invalid value (choose from options)",
}


def get_error_message(error_type: str) -> str:
    """Returns user-friendly message for a given error type."""
    return ERROR_TYPE_MESSAGES.get(error_type, "Invalid value provided")


# === Session Helpers ===
def check_activity(old_page: str):
    if not any(st.session_state[page] for page in PAGE_BEFORE_AUTHORIZATIONS):
        if dt.datetime.now(dt.timezone.utc) < st.session_state[
            "last_active_time"
        ] + dt.timedelta(minutes=INACTIVITY_MINUTES):
            st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)
        else:
            log_out()
            st.session_state["auth_error"] = f"⏳ You've been inactive for too long"
            st.session_state[old_page] = False
            st.session_state["login_page_sh"] = True
            st.rerun()
    elif old_page == "login_page_sh":
        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)


def clear_new_uploader():
    st.session_state["table_ingredients"], st.session_state["total_macros"] = None, None
    st.session_state["last_table_ingredients"] = []


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


def calculate_total_macros():
    if "widget_table" in st.session_state:
        edited_rows = st.session_state["widget_table"].get("edited_rows")
        added_rows = st.session_state["widget_table"].get("added_rows")
        deleted_rows = st.session_state["widget_table"].get("deleted_rows")

        for r_key, r_val in edited_rows.items():
            for key, val in r_val.items():
                st.session_state["table_ingredients"][r_key][key] = val
        for val in added_rows:
            st.session_state["table_ingredients"].append(val)

        deleted_row = set(deleted_rows) - set(
            st.session_state["last_table_ingredients"]
        )
        if deleted_row:
            st.session_state["table_ingredients"] = [
                row
                for idx, row in enumerate(st.session_state["table_ingredients"])
                if idx not in deleted_row
            ]

        st.session_state["last_table_ingredients"] = deleted_rows

    total = {"calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbohydrates": 0.0}

    for row in st.session_state.get("table_ingredients", []):
        for key in total.keys():
            try:
                value = row.get(key)
                if value is None or value == "":
                    value = 0.0
                total[key] += float(value)
            except (TypeError, ValueError):
                pass

    st.session_state["total_macros"] = total


def parse_dish(nutritional_info):
    if not nutritional_info:
        st.warning("No data to display")
        return

    rows = []
    for item in nutritional_info:
        if not isinstance(item, dict) or not item:
            continue

        original_name, payload = next(iter(item.items()))
        if not payload:
            rows.append(
                {
                    "ingredient": original_name,
                    "match": "no match",
                    "weight": 0,
                    "calories": 0,
                    "proteins": 0,
                    "fats": 0,
                    "carbohydrates": 0,
                }
            )
        else:
            rows.append(
                {
                    "ingredient": original_name,
                    "match": payload.get("match", ""),
                    "weight": payload.get("weight", 0),
                    "calories": payload.get("calories", 0),
                    "proteins": payload.get("proteins", 0),
                    "fats": payload.get("fats", 0),
                    "carbohydrates": payload.get("carbohydrates", 0),
                }
            )

    st.session_state["table_ingredients"] = rows
    calculate_total_macros()


def get_statistic_info():
    if (
        "stat_date_range" in st.session_state
        and len(st.session_state["stat_date_range"]) == 2
    ):
        history_weight = get_weight_history(
            "general_stat_sh", st.session_state["stat_date_range"]
        )
        history_info_nutrition = get_info_nutrition(
            "general_stat_sh", st.session_state["stat_date_range"]
        )
        history_norms = get_nutrition_norms(
            "general_stat_sh", st.session_state["stat_date_range"]
        )
        st.session_state["stat_data"]["weight"] = history_weight
        st.session_state["stat_data"]["info_nutrition"] = history_info_nutrition
        st.session_state["stat_data"]["norms"] = history_norms
        st.session_state["saved_data"] = True


# === API Wrapper ===
def api_request(method: str, endpoint: str, old_page: str, **kwargs) -> Optional[Dict]:
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

        # ✅ Handle Validation Errors (422) - Pydantic v2 format
        elif resp.status_code == 422:
            detail_data = data.get("detail", [])

            # Pydantic v2: detail is a list of errors
            if isinstance(detail_data, list):
                for err in detail_data:
                    # Extract field name from loc (e.g., ["body", "username"])
                    loc = err.get("loc", [])
                    field = loc[-1] if len(loc) > 0 else "unknown"

                    # Extract error type
                    error_type = err.get("type", "value_error")

                    # Get context for min/max values
                    ctx = err.get("ctx", {})

                    # Format message
                    if error_type == "missing":
                        text_err = "This field is required"
                    elif error_type == "string_too_short":
                        num_char = ctx.get("min_length", 3)
                        text_err = f"Value is too short (min {num_char} characters for {field})"
                    elif error_type == "string_too_long":
                        num_char = ctx.get("max_length", 500)
                        text_err = (
                            f"Value is too long (max {num_char} characters for {field})"
                        )
                    elif error_type == "greater_than_equal":
                        text_err = f"Value must be >= minimum allowed for {field}"
                    elif error_type == "less_than_equal":
                        text_err = f"Value must be <= maximum allowed for {field}"
                    elif error_type == "greater_than":
                        text_err = f"Value must be > minimum allowed for {field}"
                    elif error_type == "less_than":
                        text_err = f"Value must be < maximum allowed for {field}"
                    elif error_type == "value_error" and field == "password":
                        text_err = (
                            f"Incorrect form {field}.\nRules:\n{PASSWORD_PATTERN_TEXT}"
                        )
                    elif error_type == "int_parsing":
                        text_err = "Must be an integer number"
                    elif error_type == "float_parsing":
                        text_err = "Must be a decimal number"
                    elif error_type == "date_parsing":
                        text_err = "Invalid date format (YYYY-MM-DD)"
                    else:
                        text_err = err.get("msg", "Invalid value provided")

                    st.error(f"🔴 {field}: {text_err}")

            # Fallback: show detail as-is
            else:
                st.error(f"{base_msg}: {detail}")

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


def index_lifestyle(lifestyle: str) -> Optional[int]:
    """Converts lifestyle string to index for UI components."""
    for i, key in enumerate(bmr.keys()):
        if lifestyle == key:
            return i
    return None


# === API Functions ===


def get_meal_macros(
    old_page: str, image_base64: str, user_description: str
) -> Optional[List[Dict]]:
    """
    Sends image for ingredient recognition and nutrition search.
    No authentication required.
    """
    payload = {"image_base64": image_base64, "user_description": user_description}

    response = api_request(
        "POST", "ingredient_recognition", old_page=old_page, json=payload
    )

    if response:
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

    Note: Nutrition norms are calculated on backend automatically.
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


def get_user_information(old_page: str) -> Dict:
    """
    Retrieves current user profile.
    Requires authentication (token added by wrapper).
    """
    response = api_request("GET", "users/me", old_page=old_page)

    if response:
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

    Note: Nutrition norms are recalculated on backend automatically.
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
) -> Dict | None:
    """
    Retrieves nutrition history for a time period.
    Requires authentication.

    Note: Query params changed from st_time_span/fin_time_span to start/end.
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = time_span.strftime("%Y-%m-%d")
        end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return {}

    params = {
        "start": start,
        "end": end,
    }

    response = api_request("GET", "info_nutrition", old_page=old_page, params=params)
    if response:
        response = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
        if one_day:
            return response.get(start, {})
        return response
    return {}


def get_nutrition_norms(
    old_page: str,
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict[str, float] | List[Dict[str, float]] | None:
    """
    Retrieves nutrition norms history for a time period.
    Requires authentication.

    Note: Query params changed from st_time_span/fin_time_span to start/end.
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = time_span.strftime("%Y-%m-%d")
        end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return {}

    params = {
        "start": start,
        "end": end,
    }

    response = api_request(
        "GET", "daily_nutrition_norms", old_page=old_page, params=params
    )
    if response:
        response = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
        if one_day:
            return response.get(start, {})
        return response
    return {}


def get_weight_history(
    old_page: str,
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict[str, float] | None:
    """
    Retrieves weight history for a time period.
    Requires authentication.

    Args:
        old_page (str): Current page name for activity tracking.
        time_span: Either a single datetime or a list/tuple of [start, end].

    Returns:
        dict: Weight values keyed by date. Example: {"2024-04-01": 75.5, ...}
        None: On error.
    """

    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return None

    params = {"start": start, "end": end}

    response = api_request("GET", "weight_history", old_page=old_page, params=params)

    if response:
        response = {key: float(val) for key, val in response.items()}

        if one_day:
            return response.get(start)

        return response

    return None


def save_dish(old_page: str) -> bool:
    """Saves the current dish from the table to the database."""

    ingredients = st.session_state.get("table_ingredients")
    if not ingredients:
        st.error("No ingredients to save")
        return False

    payload = {
        "name": [],
        "weight": [],
        "calories": [],
        "proteins": [],
        "fats": [],
        "carbohydrates": [],
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    for row in ingredients:
        payload["name"].append(row.get("match", "").split(",")[0].strip())
        payload["weight"].append(float(row.get("weight", 0)))
        payload["calories"].append(float(row.get("calories", 0)))
        payload["proteins"].append(float(row.get("proteins", 0)))
        payload["fats"].append(float(row.get("fats", 0)))
        payload["carbohydrates"].append(float(row.get("carbohydrates", 0)))

    res = api_request("POST", "add_new_dish", old_page=old_page, json=payload)

    if res:
        st.session_state["days_info"] = None
        return True
    return False


def get_daily_log(date: dt.datetime, old_page: str) -> List[Dict] | None:
    """
    Fetches daily log for a specific date.

    Note: Date format changed to YYYY-MM-DD for SingleDate model.
    """
    params = {"date": date.strftime("%Y-%m-%d")}

    res = api_request("GET", "get_daily_log", old_page=old_page, params=params)

    if res:
        float_keys = ["weight", "calories", "proteins", "fats", "carbohydrates"]
        for row in res:
            for key, val in row.items():
                if key in float_keys and val is not None:
                    row[key] = float(val)
        st.session_state["table_ingredients"] = res
        return res
    return []


def change_daily_log(date: dt.datetime, old_page: str) -> None:
    """
    Detects and saves ONLY the specific changes made in data_editor.
    Clears widget state after processing to prevent accumulation.
    """
    widget_data = st.session_state.get("log_widget_table", {})

    edited_rows = widget_data.get("edited_rows", {}).copy()
    added_rows = widget_data.get("added_rows", []).copy()
    deleted_rows = widget_data.get("deleted_rows", []).copy()

    edited_converted = []
    for r_key, r_val in edited_rows.items():
        ed_row = st.session_state["table_ingredients"][int(r_key)].copy()
        for key, val in r_val.items():
            ed_row[key] = val
        edited_converted.append(
            {
                "name": ed_row["ingredient"],
                "weight": ed_row["weight"],
                "calories": ed_row["calories"],
                "proteins": ed_row["proteins"],
                "fats": ed_row["fats"],
                "carbohydrates": ed_row["carbohydrates"],
            }
        )

    added_converted = []
    for row in added_rows:
        added_converted.append(
            {
                "name": row["ingredient"],
                "weight": row["weight"],
                "calories": row["calories"],
                "proteins": row["proteins"],
                "fats": row["fats"],
                "carbohydrates": row["carbohydrates"],
            }
        )

    deleted_converted = [
        st.session_state["table_ingredients"][int(key)]["ingredient"]
        for key in deleted_rows
        if int(key) < len(st.session_state["table_ingredients"])
    ]

    if not st.session_state.get("empty_day"):
        changes = {
            "edited": edited_converted,
            "added": added_converted,
            "deleted": deleted_converted,
            "date": date.strftime("%Y-%m-%d"),
        }
    else:
        changes = {
            "edited": [],
            "added": edited_converted,
            "deleted": [],
            "date": date.strftime("%Y-%m-%d"),
        }
        if edited_converted:
            st.session_state["empty_day"] = False

    res = api_request("PUT", "daily_log/update", old_page=old_page, json=changes)
    return res
