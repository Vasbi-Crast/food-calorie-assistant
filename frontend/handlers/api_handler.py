import requests
import streamlit as st
from dotenv import load_dotenv
import os
import datetime as dt
from typing import Optional, Dict

from translator import Translator
t = Translator()

load_dotenv()
SERVER_URL = os.getenv("SERVER_URL")
INACTIVITY_MINUTES = 15

def api_request(method: str, endpoint: str, timeout = 20, **kwargs) -> Optional[Dict]:
    """
    Unified wrapper for API requests.
    Handles network errors, HTTP errors, and validation errors.
    Automatically adds Auth token if available.
    
    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE).
        endpoint (str): API endpoint path.
        **kwargs: Additional arguments for requests.request().
    
    Returns:
        dict: JSON response on success, None on error.
    """
    
    headers = kwargs.get("headers", {})
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers

    try:
        resp = requests.request(
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

    if resp.status_code >= 400:
        try:
            data = resp.json()
        except:
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

        elif resp.status_code == 422:
            detail_data = data.get("errors", [])
            if isinstance(detail_data, list):
                for err in detail_data:
                    field = err.get("field", "unknown")
                    text_field = field[0].upper() + field[1:]
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
                        text_err = t("error.validation.greater_than_equal").format(field=field)
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

                    st.error(f"🔴 {text_field}: {text_err}")
            else:
                st.error(f"{base_msg}: {detail}")
        else:
            st.error(f"{base_msg}: {detail}")
        return None

    return resp.json()

def check_activity():
    last_active = st.session_state.get("last_active_time")
    if last_active:
        now = dt.datetime.now(dt.timezone.utc)
        
        if now - last_active >= dt.timedelta(minutes=INACTIVITY_MINUTES):
            log_out()
            st.session_state["auth_error"] = t("error.session.inactive")
            st.switch_page("main_page.py")

        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)

def check_auth():
    if not st.session_state.get("token"):
        st.session_state["auth_error"] = t("error.session.logged_in")
        st.switch_page("main_page.py")

def log_out():
    st.session_state["username"] = ""
    st.session_state["last_active_time"] = None
    st.session_state["user_info"] = None
    st.session_state["days_info"] = None
    st.session_state["daily_nutrition_norms"] = None
    st.session_state["token"] = None