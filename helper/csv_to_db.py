import asyncpg
import csv
import asyncio
from typing import Dict, Any
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
import json
from pgvector.asyncpg import register_vector

async def create_admin_user(db_config: dict) -> bool:
    """
    Creates a default 'admin' user for global ingredients.
    
    Returns:
        bool: True if created or already exists.
    """
    conn = await asyncpg.connect(**db_config)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE username = $1", "admin"
        )
        
        if not exists:
            await conn.execute("""
                INSERT INTO users (
                    username, hash_password, age, bmr, gender, goal,
                    height, weight,
                    norm_calories, norm_proteins, norm_fats, norm_carbohydrates
                ) VALUES (
                    'admin', 'admin_placeholder_hash', 30, 1.2, 'None', 'weight_maintenance',
                    170, 70,
                    2000, 100, 70, 250
                )
                ON CONFLICT (username) DO NOTHING
            """)
            print("✅ Created 'admin' user for global ingredients")
        else:
            print("✅ 'admin' user already exists")
        
        return True
    finally:
        await conn.close()


def load_data(dataset_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Loads the ingredient nutrition data from the CSV file.

    Returns:
        Dict[str, Dict[str, Any]]: A dictionary where keys are ingredient names (in lowercase)
                                   and values are their nutrition data.
    """
    ingredients = {}

    try:
        with open(dataset_path, mode="r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)

            ingredients = {
                row["name"].lower(): {
                    "calories": float(row["calories"]),
                    "fats": float(row["total_fat"].strip("g")),
                    "proteins": float(row["protein"].strip("g")),
                    "carbohydrates": float(row["carbohydrate"].strip("g")),
                }
                for row in csv_reader
            }

    except FileNotFoundError:
        raise FileNotFoundError(
            f"Error: The file '{dataset_path}' was not found."
        )
    except KeyError as e:
        raise KeyError(f"Error: Missing expected column in CSV file: {e}")
    except Exception as e:
        raise Exception(f"An error occurred while reading the file: {e}")

    return ingredients


def generate_embeddings(
    names: list[str],
    model: SentenceTransformer,
    batch_size: int = 200
) -> list[list[float]]:
    """
    Generates embeddings for a list of names.
    
    Args:
        names: List of ingredient names to encode.
        model: SentenceTransformer model for embedding generation.
        batch_size: Number of embeddings to generate in one batch.
    
    Returns:
        list[list[float]]: List of embedding vectors (each vector is a list of floats).
    """
    embeddings = model.encode(
        names,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=batch_size
    )
    return embeddings.tolist()


async def insert_ingredients(
    ingredients: Dict[str, Dict[str, Any]],
    embeddings: list[list[float]],
    db_config: dict,
    owner_username: str = 'admin'
) -> int:
    """
    Inserts ingredients with embeddings into PostgreSQL.
    
    Args:
        ingredients: Dictionary of ingredient data (name → nutrition info).
        embeddings: List of embedding vectors corresponding to ingredients.
        db_config: Database connection configuration.
        owner_username: Owner of the ingredients (default: 'admin' for global).
    
    Returns:
        int: Number of successfully inserted records.
    """
    conn = await asyncpg.connect(**db_config)
    try:
        await register_vector(conn)
        
        records = []
        for (name, info), embedding in zip(ingredients.items(), embeddings):
            records.append((
                name,
                owner_username,
                info['calories'],
                info['proteins'],
                info['fats'],
                info['carbohydrates'],
                embedding
            ))
        
        await conn.copy_records_to_table(
            'ingredient',
            records=records,
            columns=['name', 'owner_username', 'calories', 'proteins', 'fats', 'carbohydrates', 'embedding']
        )
        return len(records)
    finally:
        await conn.close()


async def load_ingredients_to_db(
    dataset_path: str,
    db_config: dict,
    embedding_model: str = 'intfloat/multilingual-e5-small',
    owner_username: str = 'admin',
    batch_size: int = 200
) -> int:
    """
    Loads ingredients from CSV to PostgreSQL with embeddings.
    
    Args:
        dataset_path: Path to the CSV file with ingredient data.
        db_config: Database connection configuration.
        embedding_model: Name of the sentence-transformers model to use.
        owner_username: Owner of the ingredients (default: 'admin' for global).
        batch_size: Batch size for embedding generation.
    
    Returns:
        int: Number of loaded records
    """
    print(f"🚀 Loading: {dataset_path}")
    
    print("👤 Ensuring 'admin' user exists...")
    await create_admin_user(db_config)
    
    # 1. Load data from CSV
    print("📖 Reading CSV...")
    ingredients = load_data(dataset_path)
    print(f"✅ Found {len(ingredients)} ingredients")
    
    # 2. Initialize model
    print(f"🔄 Loading model: {embedding_model}")
    model = SentenceTransformer(embedding_model)
    print(f"✅ Model ready ({model.get_sentence_embedding_dimension()} dim)")

    print("🔄 Generating embeddings...")
    names = list(ingredients.keys())
    embeddings = generate_embeddings(names, model, batch_size)

    print("💾 Inserting into database...")
    count = await insert_ingredients(ingredients, embeddings, db_config, owner_username)
    
    print(f"🎉 Complete! Loaded: {count} records")
    return count


if __name__ == '__main__':
    load_dotenv()
    DB_CONFIG = json.loads(os.getenv("DB_CONFIG", "{}"))
    
    asyncio.run(
        load_ingredients_to_db(
            dataset_path='nutrition.csv',
            db_config=DB_CONFIG,
            embedding_model='intfloat/multilingual-e5-small',
            owner_username='admin',
            batch_size=200
        )
    )