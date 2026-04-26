"""
Translator module for multi-language support in Streamlit applications.

This module provides a Translator class that loads all translations at startup
and provides fast lookup by key. Language is stored in session_state and can
be switched instantly without reloading.

Example:
    from translator import t
    
    # Set language
    t.set_language("en")
    
    # Get translation
    st.title(t("auth.title"))
    st.button(t("auth.login"))

Attributes:
    t (Translator): Global translator instance loaded at module import.
"""

import streamlit as st
from functools import lru_cache
import yaml
from pathlib import Path
from typing import List, Optional, Any


class Translator:
    """
    A class to manage multi-language translations for Streamlit applications.
    
    Loads all translation files at initialization and caches them in memory.
    Language is stored in st.session_state and can be switched instantly.
    
    Translation keys support dot notation for nested structure:
        "auth.title" → translations[lang]["auth"]["title"]
    
    Attributes:
        _translations (dict): All loaded translations cached in memory.
        _default_lang (str): Default language if session_state is not set.
    
    Example:
        translator = Translator("locales")
        translator.set_language("en")
        text = translator("auth.title")  # "Calorie Tracker"
    """
    
    def __init__(self, locales_dir: str = "locales", default_lang: str = "en"):
        """
        Initializes the Translator instance and loads all translation files.
        
        Args:
            locales_dir (str): Path to directory containing .yaml translation files.
                Default: "locales"
            default_lang (str): Default language code if session_state is not set.
                Default: "en"
        
        Raises:
            FileNotFoundError: If locales directory does not exist.
            yaml.YAMLError: If translation file has invalid YAML syntax.
        
        Note:
            Translation files are loaded once at initialization and cached.
            File format: {lang}.yaml (e.g., en.yaml, ru.yaml, es.yaml)
        """
        self._default_lang = default_lang
        self._translations = self._load_all_locales(locales_dir)
    
    @staticmethod
    @lru_cache(maxsize=None)
    def _load_all_locales(locales_dir: str) -> dict:
        """
        Loads all translation files from the specified directory.
        
        This method is cached with @lru_cache to ensure files are loaded
        only once per application lifetime.
        
        Args:
            locales_dir (str): Path to directory containing .yaml files.
        
        Returns:
            dict: Dictionary with language codes as keys and translation
                dictionaries as values.
                Example: {
                    "en": {"auth": {"title": "Login", ...}},
                    "ru": {"auth": {"title": "Вход", ...}},
                    ...
                }
        
        Raises:
            FileNotFoundError: If locales directory does not exist.
            yaml.YAMLError: If any translation file has invalid syntax.
        
        Note:
            Files must be named with language code as stem (e.g., en.yaml, ru.yaml).
            Files are loaded with UTF-8 encoding.
        """
        translations = {}
        locales_path = Path(locales_dir)
        
        if not locales_path.exists():
            raise FileNotFoundError(f"Locales directory not found: {locales_dir}")
        
        for file in locales_path.glob("*.yaml"):
            lang = file.stem
            with open(file, "r", encoding="utf-8") as f:
                translations[lang] = yaml.safe_load(f) or {}
        
        return translations
    
    def __call__(self, key: str, lang: Optional[str] = None) -> Any:
        """
        Translates a key to the current or specified language.
        
        Supports dot notation for nested keys:
            "auth.title" → translations[lang]["auth"]["title"]
        
        Args:
            key (str): Translation key in dot notation.
                Example: "auth.title", "home.calories", "stats.weight"
            lang (str, optional): Language code. If None, uses language from
                st.session_state or default_lang. Default: None

        Returns:
            Any: Translated value. Can be str, list, dict, or any YAML type.
                Example:
                    t("login.title") → str: "Login"
                    t("register.gender.options") → list: [":blue[Man]", ":red[Woman]", ...]
        """
        if lang is None:
            lang = st.session_state.get("language", self._default_lang)
        
        keys = key.split(".")
        value = self._translations.get(lang, {})
        
        for k in keys:
            value = value.get(k, {}) if isinstance(value, dict) else {}
        
        return value if value else key
    
    @property
    def available_languages(self) -> List[str]:
        """
        Returns list of available language codes.
        
        Returns:
            list: List of language codes loaded from locales directory.
                Example: ["en", "ru", "es"]
        
        Example:
            t = Translator()
            for lang in t.available_languages:
                st.write(lang)
        """
        return list(self._translations.keys())
    
    def set_language(self, lang: str) -> None:
        """
        Sets the current language in st.session_state.
        
        Args:
            lang (str): Language code to set. Must be in available_languages.
        
        Raises:
            ValueError: If lang is not in available_languages.
        
        Example:
            t = Translator()
            t.set_language("en")  # Switch to English
            t.set_language("ru")  # Switch to Russian
        
        Note:
            Language change takes effect immediately for subsequent t() calls.
            Streamlit will re-run the script on next interaction.
        """
        if lang not in self._translations:
            raise ValueError(
                f"Language '{lang}' not available. "
                f"Available languages: {self.available_languages}"
            )
        st.session_state.language = lang
    
    def get_category(self, category: str, lang: Optional[str] = None) -> dict:
        """
        Returns all translations for a category (top-level key).
        
        Useful for pages that need multiple translations from the same category.
        
        Args:
            category (str): Top-level category key.
                Example: "auth", "home", "stats"
            lang (str, optional): Language code. If None, uses current language.
                Default: None
        
        Returns:
            dict: Dictionary with all translations for the category.
                Example: {
                    "title": "Calorie Tracker",
                    "login": "Login",
                    "password": "Password"
                }
        
        Example:
            auth = t.get_category("auth")
            st.title(auth["title"])
            st.button(auth["login"])
        
        Note:
            Returns empty dict if category is not found.
        """
        if lang is None:
            lang = st.session_state.get("language", self._default_lang)
        
        return self._translations.get(lang, {}).get(category, {})


class TranslatorContext:
    """
    Context wrapper for translator to provide attribute-style access.
    
    Allows using t.login.title instead of t("login.title") for better
    IDE autocomplete and type safety.
    
    Attributes:
        _t (Translator): Reference to parent Translator instance.
        _category (str): Category name for this context.
    
    Example:
        t = Translator()
        t.login.title  # "Login" (instead of t("login.title"))
    """
    
    def __init__(self, translator: Translator, category: str):
        """
        Initializes TranslatorContext with translator and category.
        
        Args:
            translator (Translator): Parent Translator instance.
            category (str): Category name for attribute access.
                Example: "login", "home", "daily_log"
        """
        self._t = translator
        self._category = category
    
    def __getattr__(self, key: str) -> str:
        """
        Translates a key within the context's category.
        
        Args:
            key (str): Translation key (without category prefix).
        
        Returns:
            str: Translated string.
        
        Example:
            t.login.title  # → t("login.title")
            t.home.title  # → t("home.title")
        
        Note:
            If key is not found, returns the key itself as fallback.
        """
        return self._t(f"{self._category}.{key}")
