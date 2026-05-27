import streamlit as st
from pathlib import Path

from translator import Translator
from handlers.init_session_state import clear_session_states
from handlers.api_handler import log_out

t = Translator()

ICON_PATH = Path(__file__).parent / "resources" / "icons8-chinese-noodle-100.png"
"""Path to the application icon."""


def _format_language(code: str) -> str:
    """Returns language label with flag emoji.
    
    Args:
        code (str): Language code (e.g., "en", "ru").
    
    Returns:
        str: Formatted string with flag and language.
    """
    flags = {"en": "🇬🇧", "ru": "🇷🇺"}
    language = {"en": "English", "ru": "Русский"}
    return f"{flags.get(code, '🌍')} {language.get(code, 'English')}"


def show_help():
    """Displays the help modal dialog with topic selection.
    
    Shows a Streamlit dialog containing step-by-step instructions
    for using the app. Topics are loaded from the translator.
    """
    @st.dialog(t("help_page.modal.title"), width="large")
    def help_dialog():
        steps = t("help_page.modal.steps")
        if isinstance(steps, list):
            selected_topic = st.selectbox(
                t("help_page.modal.select_title"),
                options=[step["title"] for step in steps],
                index=0,
            )
            selected_step = next(
                (step for step in steps if step["title"] == selected_topic), steps[0]
            )
            st.markdown(selected_step["text"], unsafe_allow_html=True)

        st.markdown("---")
        st.caption(t("help_page.description"))

    help_dialog()


def authenticated_menu():
    """Renders sidebar navigation for authenticated users.
    
    Displays buttons for: Home, Daily Log, Recognition, Statistics,
    Settings, and Logout. Clears session state on navigation.
    """
    if st.sidebar.button(label=t("home.btn_title"), width="stretch"):
        clear_session_states()
        st.switch_page("pages/home.py")

    if st.sidebar.button(label=t("daily_log.btn_title"), width="stretch"):
        clear_session_states()
        st.switch_page("pages/daily_log.py")

    if st.sidebar.button(label=t("recognition.btn_title"), width="stretch"):
        clear_session_states()
        st.switch_page("pages/recognition.py")

    if st.sidebar.button(label=t("general_stat.btn_title"), width="stretch"):
        clear_session_states()
        st.switch_page("pages/general_stat.py")

    if st.sidebar.button(label=t("settings.btn_title"), width="stretch"):
        clear_session_states()
        st.switch_page("pages/settings.py")

    if st.sidebar.button(label=t("home.log_out"), width="stretch"):
        log_out()
        st.switch_page("main_page.py")


def unauthenticated_menu():
    """Renders sidebar navigation for guests (not logged in).
    
    Displays buttons for: Login and Register.
    """
    if st.sidebar.button(label=t("login.btn_title"), width="stretch"):
        st.switch_page("main_page.py")

    if st.sidebar.button(label=t("register.btn_title"), width="stretch"):
        st.switch_page("pages/register.py")


def menu():
    """Main menu renderer: handles onboarding, language, and auth state.
    
    Sets page config (title, icon, sidebar state), shows help dialog
    on first start per language, renders auth-aware sidebar buttons,
    and provides language selector with auto-rerun on change.
    
    Note:
        Relies on session_state keys initialized in init_session_state.py:
        - first_start, onboarding_seen, username, language
    """
    current_lang = st.session_state.get("language", "en")
    
    if not st.session_state["first_start"]:
        st.set_page_config(
            page_title="Food Assistant",
            initial_sidebar_state="collapsed",
            page_icon=str(ICON_PATH),
        )
    else:
        st.set_page_config(
            page_title="Food Assistant",
            initial_sidebar_state="expanded",
            page_icon=str(ICON_PATH),
        )
        if current_lang not in st.session_state["onboarding_seen"]:
            st.session_state["onboarding_seen"].add(current_lang)
        st.session_state["first_start"] = False
        show_help()

    if st.session_state["username"].strip():
        authenticated_menu()
    else:
        unauthenticated_menu()
        
    st.sidebar.divider()
    
    st.session_state["language"] = st.sidebar.selectbox(
        label="🌍 Language / Язык",
        options=t.available_languages,
        format_func=_format_language,
        index=t.available_languages.index(current_lang),
        key="language_selector",
    )

    if st.sidebar.button("❓ " + t("help_page.button"), width="stretch"):
        show_help()

    if st.session_state["language"] != current_lang:
        t.set_language(st.session_state["language"])
        if st.session_state["language"] not in st.session_state["onboarding_seen"]:
            st.session_state["first_start"] = True
        st.rerun()