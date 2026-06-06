"""Helper script to generate and optionally auto-translate ingredient base translations.

Reads ingredient names from a CSV, generates a base JSON dictionary,
and optionally synchronizes missing translations via the backend API
using the IngredientTranslator class. Designed for one-time data preparation.
"""

import csv
import json
import os
import re
from pathlib import Path
from typing import List, Optional


def normalize(name: str) -> str:
    """Normalizes an ingredient name by lowercasing and collapsing whitespace.

    Args:
        name (str): Raw ingredient name string.

    Returns:
        str: Normalized name suitable for dictionary keys.
    """
    return re.sub(r"\s+", " ", name.strip().lower())


def generate_base_translations_from_csv(
    csv_path: str,
    col_with_ing_name: str,
    output_path: str = "data/base_translations.json",
    extra_languages: Optional[List[str]] = None,
    fill_with_empty: bool = False,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> None:
    """Generates a base JSON translation file from a CSV ingredient list.

    Reads ingredient names from a specified CSV column, normalizes them,
    and builds a dictionary mapping normalized keys to translation entries.
    Supports optional pre-initialization of extra language keys.

    Args:
        csv_path (str): Path to the source CSV file.
        col_with_ing_name (str): Name of the CSV column containing ingredient names.
        output_path (str): Destination path for the generated JSON file.
            Defaults to "data/base_translations.json".
        extra_languages (Optional[List[str]]): List of additional language codes
            to include as keys in each entry. Defaults to None.
        fill_with_empty (bool): If True, initializes extra language keys with
            empty strings for manual editing. If False, only "en" is included.
            Defaults to False.
        delimiter (str): CSV field delimiter. Defaults to ",".
        encoding (str): File encoding for reading CSV and writing JSON.
            Defaults to "utf-8".

    Raises:
        ValueError: If the specified column does not exist in the CSV header.
        FileNotFoundError: If the CSV file path is invalid.

    Note:
        Uses atomic file writing (temporary file + os.replace) to prevent
        data corruption if the process is interrupted.
    """
    extra_languages = extra_languages or []
    translations = {}
    count = 0

    with open(csv_path, mode="r", encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no headers.")
        if col_with_ing_name not in reader.fieldnames:
            raise ValueError(
                f"Column '{col_with_ing_name}' not found in CSV. "
                f"Available columns: {reader.fieldnames}"
            )

        for row in reader:
            raw_name = row.get(col_with_ing_name, "").strip()
            if not raw_name:
                continue

            norm_key = normalize(raw_name)

            entry = {"en": raw_name}
            if fill_with_empty:
                for lang in extra_languages:
                    entry[lang] = ""

            if norm_key not in translations:
                translations[norm_key] = entry
                count += 1

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(translations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, out)

    print(f"✅ Generated {count} unique records -> {out}")


if __name__ == "__main__":
    CSV_PATH = "nutrition.csv"
    OUTPUT_JSON = "ingredient_translations.json"

    print("🚀 Starting base translation generation...")
    generate_base_translations_from_csv(
        csv_path=CSV_PATH,
        col_with_ing_name="name",
        output_path=OUTPUT_JSON,
        extra_languages=["ru", "eu"],
        fill_with_empty=False,
    )
    print("🏁 Script finished successfully.")
