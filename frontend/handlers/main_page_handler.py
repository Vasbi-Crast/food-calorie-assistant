"""Handler module for main page authentication logic."""

import streamlit as st
import datetime as dt
from typing import Optional, Dict, Any

from handlers.api_handler import api_request
from translator import Translator

t = Translator()


def authorization(username: str, password: str) -> bool:
    """Authenticates user credentials against the backend API.

    Validates input, sends a POST request to the authentication endpoint,
    and updates the session state with the access token and user data
    upon successful response.

    Args:
        username (str): The user's login identifier.
        password (str): The user's password.

    Returns:
        bool: True if authentication succeeds, False otherwise.
        Displays error messages via Streamlit UI on validation or API failure.
    """
    if not username.strip():
        st.error(t("error.form.username_required"))
        return False
    if not password.strip():
        st.error(t("error.form.password_required"))
        return False

    payload = {"username": username.lower(), "password": password}

    response: Optional[Dict[str, Any]] = api_request(
        "POST", "authentication", json=payload
    )

    if response:
        st.session_state["token"] = response.get("access_token")
        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)
        st.session_state["username"] = username
        return True

    return False
