import streamlit as st

from translator import Translator
t = Translator()

def default_session_state():
    if "username" not in st.session_state:
        st.session_state["username"] = ""
    if "user_info" not in st.session_state:
        st.session_state["user_info"] = None
    if "days_info" not in st.session_state:
        st.session_state["days_info"] = None
    if "daily_nutrition_norms" not in st.session_state:
        st.session_state["daily_nutrition_norms"] = None
    if "table_ingredients" not in st.session_state:
        st.session_state["table_ingredients"] = None
    if "total_macros" not in st.session_state:
        st.session_state["total_macros"] = None
    if "last_deleted" not in st.session_state:
        st.session_state["last_deleted"] = []
    if "saved_data" not in st.session_state:
        st.session_state["saved_data"] = False
    if "empty_day" not in st.session_state:
        st.session_state["empty_day"] = False
    if "stat_data" not in st.session_state:
        st.session_state["stat_data"] = {
            "weight": None,
            "info_nutrition": None,
            "norms": None,
        }
    if "language" not in st.session_state:
        accept_lang = st.context.headers.to_dict().get("Accept-Language", "")

        languages = [lang.split(";")[0].strip() for lang in accept_lang.split(",")]

        lang_codes = [lang[:2].lower() for lang in languages]

        detected_lang = "en"
        for code in lang_codes:
            if code in t.available_languages:
                detected_lang = code
                break
        st.session_state["language"] = detected_lang

    if "first_start" not in st.session_state:
        st.session_state["first_start"] = True
    if "onboarding_seen" not in st.session_state:
        st.session_state["onboarding_seen"] = set()
    if "auth_error" not in st.session_state:
        st.session_state["auth_error"] = ""
    if "last_active_time" not in st.session_state:
        st.session_state["last_active_time"] = None