import streamlit as st

from translator import Translator
t = Translator()

def show_help():
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
                (step for step in steps if step["title"] == selected_topic),
                steps[0]
            )
            st.markdown(selected_step["text"], unsafe_allow_html=True)
        
        st.markdown("---")
        st.caption(t("help_page.description"))
    help_dialog()

def authenticated_menu():
    st.sidebar.page_link("pages/home.py", label = t("home.btn_title"), width="stretch")
    st.sidebar.page_link("pages/daily_log.py", label = t("daily_log.btn_title"), width="stretch")
    st.sidebar.page_link("pages/recognition.py", label=t("recognition.btn_title"), width="stretch")
    st.sidebar.page_link("pages/general_stat.py", label = t("general_stat.btn_title"), width="stretch")
    st.sidebar.page_link("pages/settings.py", label=t("settings.btn_title"), width="stretch")
    st.sidebar.page_link("main_page.py", label = t("home.log_out"), width="stretch")

def unauthenticated_menu():
    st.sidebar.page_link("main_page.py", label = t("login.btn_title"), width="stretch")
    st.sidebar.page_link("pages/register.py", label=t("register.btn_title"), width="stretch")

def menu():
    current_lang = st.session_state.get("language", "en")
    if not st.session_state["first_start"]:
        st.set_page_config(page_title="Food Assistant",
                        initial_sidebar_state="collapsed",
                        page_icon = "resources/icons8-chinese-noodle-100.png")
    else:
        st.set_page_config(page_title="Food Assistant",
                           initial_sidebar_state="expanded",
                            page_icon = "resources/icons8-chinese-noodle-100.png")
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
        format_func=lambda x: {
            "en": "🇬🇧 English",
            "ru": "🇷🇺 Русский",
        }.get(x, x),
        index=t.available_languages.index(current_lang),
        key="language_selector",
    )

    if st.sidebar.button("❓ " + t("help_page.button"), width='stretch'):
        show_help()

    if st.session_state["language"] != current_lang:
        t.set_language(st.session_state["language"])
        if st.session_state["language"] not in st.session_state["onboarding_seen"]:
            st.session_state["first_start"] = True
        st.rerun()