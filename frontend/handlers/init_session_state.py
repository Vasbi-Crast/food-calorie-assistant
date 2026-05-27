import streamlit as st

from translator import Translator

t = Translator()


def default_session_state():
    """Initializes Streamlit session state variables with default values.

    Uses setdefault to ensure variables are only set if they don't exist,
    preserving user-modified data across re-runs.

    Handles:
        - User authentication info (username, user_info).
        - Daily nutrition data and norms.
        - UI state flags (onboarding, dialogs, editing modes).
        - Language detection based on browser headers ('Accept-Language').

    Note:
        Language detection is wrapped in try-except to handle cases where
        headers are unavailable (e.g., local development). Falls back to 'en'.
    """
    # User data
    st.session_state.setdefault("username", "")
    st.session_state.setdefault("user_info", None)
    st.session_state.setdefault("days_info", None)
    st.session_state.setdefault("daily_nutrition_norms", None)
    st.session_state.setdefault("table_ingredients", None)

    # Flags
    st.session_state.setdefault("saved_data", False)
    st.session_state.setdefault("empty_day", False)

    # Statistics data
    st.session_state.setdefault("stat_data", {
        "weight": None,
        "info_nutrition": None,
        "norms": None,
    })

    # Language detection with fallback
    try:
        if "language" not in st.session_state:
            accept_lang = st.context.headers.to_dict().get("Accept-Language", "")
            languages = [lang.split(";")[0].strip() for lang in accept_lang.split(",")]
            lang_codes = [lang[:2].lower() for lang in languages]

            detected_lang = "en"
            for code in lang_codes:
                if code in t.available_languages:
                    detected_lang = code
                    break
            st.session_state.setdefault("language", detected_lang)
    except Exception:
        # Fallback to English if headers are unavailable
        st.session_state.setdefault("language", "en")

    # Onboarding and auth
    st.session_state.setdefault("first_start", True)
    st.session_state.setdefault("onboarding_seen", set())
    st.session_state.setdefault("auth_error", "")
    st.session_state.setdefault("last_active_time", None)
    st.session_state.setdefault("first_daily_log", True)

    # Ingredient editing state
    st.session_state.setdefault("idx_edit_ingredient", None)
    st.session_state.setdefault("modified_ingredients", [])
    st.session_state.setdefault("users_ingredients", None)
    st.session_state.setdefault("show_add_dialog", None)
    st.session_state.setdefault("successful_save_daily_log", None)


def clear_session_states():
    """Resets session state variables related to daily logs and statistics.

    Clears data associated with the current session or daily tracking
    (e.g., days_info, modified_ingredients) while preserving user
    authentication details (username) and general settings (language).

    Note:
        This is typically called upon logout or when resetting the
        daily tracking view to start fresh.
    """
    st.session_state["days_info"] = None
    st.session_state["first_daily_log"] = True
    st.session_state["daily_nutrition_norms"] = None
    st.session_state["table_ingredients"] = None
    st.session_state["empty_day"] = False
    st.session_state["stat_data"] = {
        "weight": None,
        "info_nutrition": None,
        "norms": None,
    }
    st.session_state["auth_error"] = ""
    st.session_state["idx_edit_ingredient"] = None
    st.session_state["modified_ingredients"] = []
    st.session_state["show_add_dialog"] = None
    st.session_state["successful_save_daily_log"] = None
    st.session_state["saved_data"] = False