"""Helper module for importing ingredient nutrition data and embeddings into PostgreSQL.

This script reads nutrition data from a CSV file, generates vector embeddings
using SentenceTransformer, and bulk inserts the data into the database.
It also ensures an 'admin' user exists for global ingredient management.
"""

import asyncpg
import csv
import asyncio
from typing import Dict, Any
from sentence_transformers import SentenceTransformer
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
import json
from pgvector.asyncpg import register_vector


async def create_admin_user(db_config: dict, admin_password: str) -> bool:
    """Creates a default 'admin' user for global ingredients if it does not exist.

    Checks the database for an existing 'admin' user. If not found, inserts
    a new record with default nutritional norms and a hashed password.

    Args:
        db_config (dict): Database connection configuration dictionary.
        admin_password (str): The password to hash and store for the admin user.

    Returns:
        bool: True if the user was created or already exists.
    """
    conn = await asyncpg.connect(**db_config)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    try:
        exists = await conn.fetchval("SELECT 1 FROM users WHERE username = $1", "admin")

        if not exists:
            await conn.execute(
                """
                INSERT INTO users (
                    username, hash_password, age, bmr, gender, goal,
                    height, weight,
                    norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                ) VALUES (
                    'admin', $1, 30, 1.2, 'None', 'weight_maintenance',
                    170, 70,
                    2000, 100, 70, 250
                )
                ON CONFLICT (username) DO NOTHING
            """,
                pwd_context.hash(admin_password),
            )
            print("✅ Created 'admin' user for global ingredients")
        else:
            print("✅ 'admin' user already exists")

        return True
    finally:
        await conn.close()


def safe_float(value: Any) -> float:
    """Safely converts a value to float, returning 0.0 on failure.

    Args:
        value (Any): The value to convert.

    Returns:
        float: The converted float value, or 0.0 if conversion fails.
    """
    try:
        cleaned = str(value).replace("g", "").strip()
        if not cleaned:
            return 0.0
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def load_data(
    dataset_path: str, fields_config: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Loads ingredient nutrition data from a CSV file into a dictionary.

    Parses the CSV, maps columns using the provided configuration, and converts
    nutritional values to floats using safe_float.

    Args:
        dataset_path (str): Absolute or relative path to the CSV file.
        fields_config (Dict[str, str]): Mapping of internal keys to CSV column names.
            Expected keys: "name", "calories", "fats", "proteins", "carbohydrates".

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary where keys are lowercase ingredient names
            and values are dictionaries containing nutritional data (floats).

    Raises:
        FileNotFoundError: If the CSV file does not exist at the specified path.
        KeyError: If a required column name from fields_config is missing in the CSV.
    """
    ingredients = {}

    try:
        with open(dataset_path, mode="r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)

            if csv_reader.fieldnames:
                for key, col_name in fields_config.items():
                    if col_name not in csv_reader.fieldnames:
                        raise KeyError(
                            f"Missing expected column in CSV file: '{col_name}'"
                        )

            ingredients = {
                row[fields_config.get("name", "name")].lower(): {
                    "calories": safe_float(row.get(fields_config["calories"], 0)),
                    "fats": safe_float(row.get(fields_config["fats"], 0)),
                    "proteins": safe_float(row.get(fields_config["proteins"], 0)),
                    "carbohydrates": safe_float(
                        row.get(fields_config["carbohydrates"], 0)
                    ),
                }
                for row in csv_reader
            }

    except FileNotFoundError:
        raise FileNotFoundError(f"Error: The file '{dataset_path}' was not found.")
    except Exception as e:
        raise Exception(f"An error occurred while reading the file: {e}")

    return ingredients


def generate_embeddings(
    names: list[str], model: SentenceTransformer, batch_size: int = 200
) -> list[list[float]]:
    """Generates vector embeddings for a list of ingredient names.

    Uses the provided SentenceTransformer model to encode names into dense vectors.
    Progress bar is shown during processing.

    Args:
        names (list[str]): List of ingredient name strings to encode.
        model (SentenceTransformer): Pre-loaded embedding model.
        batch_size (int): Number of samples per batch. Defaults to 200.

    Returns:
        list[list[float]]: List of embedding vectors, each represented as a list of floats.
    """
    embeddings = model.encode(
        names, convert_to_numpy=True, show_progress_bar=True, batch_size=batch_size
    )
    return embeddings.tolist()


async def insert_ingredients(
    ingredients: Dict[str, Dict[str, Any]],
    embeddings: list[list[float]],
    db_config: dict,
    owner_username: str = "admin",
) -> int:
    """Bulk inserts ingredients and their embeddings into the PostgreSQL database.

    Deletes existing records for the owner_username before insertion to ensure
    a fresh state (overwrite logic). Uses asyncpg's copy_records_to_table for
    high-performance insertion.

    Args:
        ingredients (Dict[str, Dict[str, Any]]): Ingredient data dictionary.
        embeddings (list[list[float]]): List of embedding vectors aligned with ingredients.
        db_config (dict): Database connection configuration.
        owner_username (str): Username to assign as owner. Defaults to 'admin'.

    Returns:
        int: Number of records successfully inserted.
    """
    conn = await asyncpg.connect(**db_config)
    try:
        await register_vector(conn)

        await conn.execute(
            "DELETE FROM ingredient WHERE owner_username = $1", owner_username
        )
        print(f"🧹 Cleared old records for user '{owner_username}'")

        records = []
        for (name, info), embedding in zip(ingredients.items(), embeddings):
            records.append(
                (
                    name,
                    owner_username,
                    info["calories"],
                    info["proteins"],
                    info["fats"],
                    info["carbohydrates"],
                    embedding,
                )
            )

        await conn.copy_records_to_table(
            "ingredient",
            records=records,
            columns=[
                "name",
                "owner_username",
                "calories",
                "proteins",
                "fats",
                "carbohydrates",
                "embedding",
            ],
        )
        return len(records)
    finally:
        await conn.close()


async def load_ingredients_to_db(
    dataset_path: str,
    db_config: dict,
    admin_password: str,
    fields_config: Dict[str, str],
    embedding_model: str = "intfloat/multilingual-e5-small",
    owner_username: str = "admin",
    batch_size: int = 200,
) -> int:
    """Orchestrates the full pipeline: load CSV, generate embeddings, insert to DB.

    Ensures the owner user exists, reads data, computes vectors, and performs
    bulk insertion. Prints progress logs to stdout.

    Args:
        dataset_path (str): Path to the source CSV file.
        db_config (dict): Database connection configuration.
        admin_password (str): Password for the admin user creation.
        fields_config (Dict[str, str]): Column mapping for the CSV parser.
        embedding_model (str): HuggingFace model identifier. Defaults to 'intfloat/multilingual-e5-small'.
        owner_username (str): Owner username for DB records. Defaults to 'admin'.
        batch_size (int): Batch size for embedding generation. Defaults to 200.

    Returns:
        int: Total number of records loaded into the database.
    """
    print(f"🚀 Loading: {dataset_path}")

    print("👤 Ensuring 'admin' user exists...")
    await create_admin_user(db_config, admin_password)

    print("📖 Reading CSV...")
    ingredients = load_data(dataset_path, fields_config)
    print(f"✅ Found {len(ingredients)} ingredients")

    if not ingredients:
        print("️ No ingredients found. Aborting.")
        return 0

    print(f"🔄 Loading model: {embedding_model}")
    model = SentenceTransformer(embedding_model)
    print(f"✅ Model ready ({model.get_sentence_embedding_dimension()} dim)")

    print("🔄 Generating embeddings...")
    names = list(ingredients.keys())
    embeddings = generate_embeddings(names, model, batch_size)

    print("💾 Inserting into database (overwriting old data)...")
    count = await insert_ingredients(ingredients, embeddings, db_config, owner_username)

    print(f"🎉 Complete! Loaded: {count} records")
    return count


if __name__ == "__main__":
    load_dotenv()

    db_config_str = os.getenv("DB_CONFIG", "{}")
    try:
        DB_CONFIG = json.loads(db_config_str)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in DB_CONFIG environment variable")

    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

    fields_config = {
        "name": "name",
        "calories": "calories",
        "fats": "total_fat",
        "proteins": "protein",
        "carbohydrates": "carbohydrate",
    }

    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    csv_path = os.path.join(current_dir, "nutrition.csv")
    
    asyncio.run(
        load_ingredients_to_db(
            dataset_path=csv_path,
            db_config=DB_CONFIG,
            admin_password=ADMIN_PASSWORD,
            fields_config=fields_config,
            embedding_model="intfloat/multilingual-e5-small",
            owner_username="admin",
            batch_size=200,
        )
    )
