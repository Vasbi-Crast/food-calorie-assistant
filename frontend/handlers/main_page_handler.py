import streamlit as st

from handlers.api_handler import api_request
import datetime as dt
from translator import Translator
t = Translator()

def authorization(username: str, password: str) -> bool:
    """
    User login. Saves token to session_state on success.
    
    Args:
        username (str): User's username.
        password (str): User's password.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    if not username.strip():
        st.error(t("error.form.username_required"))
        return False
    if not password.strip():
        st.error(t("error.form.password_required"))
        return False

    payload = {"username": username.lower(), "password": password}

    response = api_request("POST", "authentication", json=payload)

    if response:
        
        st.session_state["token"] = response.get("access_token")
        st.session_state["last_active_time"] = dt.datetime.now(dt.timezone.utc)
        st.session_state["username"] = username
        return True
    return False