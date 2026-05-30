import streamlit as st
from functools import lru_cache
import yaml
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Iterable, Any, Set, Callable
import asyncio
import re

import threading


def get_canonical_name(name: str) -> str:
    """Returns the normalized canonical name for an ingredient.

    Args:
        name (str): Ingredient name string.

    Returns:
        str: Normalized name (lowercase, stripped, prefix preserved).
    """
    return IngredientTranslator.normalize(name)


class IngredientTranslator:
    """Manages translation of ingredient names and persists changes to disk.

    Handles caching, normalization, and asynchronous synchronization with
    the backend API. Implements debounced saving to prevent excessive I/O.
    """

    def __init__(
        self,
        path: str = "resources/locales/ingredient_translations.json",
        app_languages: Iterable[str] = ("en", "ru"),
    ):
        """Initializes the translator with cache, pending queue, and I/O locks.

        Args:
            path (str): Path to the JSON translation cache file.
            app_languages (Iterable[str]): List of supported language codes.
        """
        self.app_languages = set(app_languages)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._cache: Dict[str, Dict[str, str]] = self._load()
        self._pending: Dict[str, set[str]] = {}

        self._io_lock = threading.Lock()
        self._save_task: Optional[asyncio.Task] = None

    def _load(self) -> Dict[str, Dict[str, str]]:
        """Loads translation cache from disk.

        Returns:
            Dict[str, Dict[str, str]]: Loaded translations dictionary.
                Returns empty dict if file does not exist or is invalid.
        """
        if self.path.exists():
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def normalize(name: str) -> str:
        """Normalizes an ingredient name string.

        Converts to lowercase, strips whitespace, collapses multiple spaces,
        and preserves the '~' prefix if present.

        Args:
            name (str): The raw ingredient name.

        Returns:
            str: The normalized canonical name.
        """
        return re.sub(r"\s+", " ", name.strip().lower())

    def resolve(self, key: str, lang: str) -> str:
        """Retrieves the translation for a specific ingredient key and language.

        Checks the cache. If the translation is missing, records all missing
        language variants for future synchronization.

        Args:
            key (str): The normalized ingredient key.
            lang (str): The target language code.

        Returns:
            str: The translated ingredient name, or the original key if not found.
        """
        entry = self._cache.get(key, {})

        if entry and lang in entry:
            return entry[lang]

        missing = self.app_languages - set(entry)
        if missing:
            self._pending.setdefault(key, set()).update(missing)
        return key

    def register(self, name: str) -> str:
        """Registers a new ingredient name into the cache or pending list.

        Normalizes the name and stores it. If already cached, marks missing
        languages as pending. Otherwise, queues it for all app languages.

        Args:
            name (str): The raw ingredient name.

        Returns:
            str: The normalized canonical key for the ingredient.
        """
        key = self.normalize(name)

        existing_entry = self._cache.get(key)
        if existing_entry:
            missing = self.app_languages - set(existing_entry)
            if missing:
                self._pending.setdefault(key, set()).update(missing)
            return key

        self._pending[key] = self.app_languages
        return key

    async def sync(
        self, api_fetch_func: Callable, limit_to_lang: Optional[set[str]] = None
    ) -> Dict[str, str]:
        """Synchronizes pending and missing translations with the backend API.

        Collects all keys that need translation, sends them to the backend,
        updates the local cache with canonical keys, and removes obsolete entries
        to prevent database bloat.

        Args:
            api_fetch_func (Callable): An async function to call the backend API.
            limit_to_lang (Optional[set[str]]): If provided, only fetch translations
                for these specific languages. Defaults to None (fetch all missing).

        Returns:
            Dict[str, str]: A mapping of old keys to new canonical keys.
        """
        payload: Dict[str, set] = {}

        for key, val in self._pending.items():
            if not limit_to_lang:
                payload[key] = val
            else:
                payload[key] = val & self.app_languages & limit_to_lang

        for key, entry in self._cache.items():
            if key in payload:
                continue
            missing = self.app_languages - set(entry)
            if limit_to_lang:
                payload[key] = missing & self.app_languages & limit_to_lang
            else:
                payload[key] = missing

        payload = {k: list(v) for k, v in payload.items() if v}
        if not payload:
            return {}

        try:
            results = await api_fetch_func(
                method="POST",
                endpoint="translate_ingredients",
                timeout=100000,
                json={"ingredients": payload},
            )
        except Exception as e:
            print(f"⚠️ Sync failed: {e}")
            return {}

        if not isinstance(results, dict):
            print("⚠️ Sync failed, unexpected result received from backend.")
            return {}

        status = results.get("status")
        if status not in ("success", "partial_success"):
            print(f"⚠️ Sync aborted. Status: {status} | Error: {results.get('error')}")
            return {}

        results = results.get("result", {})
        norm_mapping = {}

        for old_key, translations in results.items():
            has_llm_marker = old_key.startswith("~")

            if has_llm_marker:
                for lang, val in translations.items():
                    if isinstance(val, str) and not val.startswith("~"):
                        translations[lang] = "~" + val
            else:
                for lang, val in translations.items():
                    if isinstance(val, str) and val.startswith("~"):
                        translations[lang] = val[1:]

            en_translation = translations.get("en", old_key)
            canonical = self.normalize(en_translation)

            self._cache.setdefault(canonical, {}).update(translations)

            if old_key != canonical:
                self._cache.pop(old_key, None)
                self._pending.pop(old_key, None)
                norm_mapping[old_key] = canonical

            self._pending.pop(canonical, None)

        self._schedule_save()
        return norm_mapping

    def _schedule_save(self) -> None:
        """Schedules a debounced save operation if one is not already running."""
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        """Debounces writes to disk using atomic replacement. Doesn't block reads."""
        with self._io_lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2), "utf-8"
            )
            os.replace(tmp, self.path)


class Translator:
    """
    A class to manage multi-language translations for Streamlit applications.

    Loads all translation files at initialization and caches them in memory.
    Language is stored in st.session_state and can be switched instantly.

    Translation keys support dot notation for nested structure:
        "auth.title" -> translations[lang]["auth"]["title"]

    Attributes:
        _translations (dict): All loaded translations cached in memory.
        _default_lang (str): Default language if session_state is not set.

    Example:
        translator = Translator("locales")
        translator.set_language("en")
        text = translator("auth.title")  # "Calorie Tracker"
    """

    def __init__(
        self, locales_dir: str = "resources/locales", default_lang: str = "en"
    ):
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
            "auth.title" -> translations[lang]["auth"]["title"]

        Args:
            key (str): Translation key in dot notation.
                Example: "auth.title", "home.calories", "stats.weight"
            lang (str, optional): Language code. If None, uses language from
                st.session_state or default_lang. Default: None

        Returns:
            Any: Translated value. Can be str, list, dict, or any YAML type.
                Example:
                    t("login.title") -> str: "Login"
                    t("register.gender.options") -> list: [":blue[Man]", ":red[Woman]", ...]
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
