from typing import Dict, List, Any
import csv
from difflib import get_close_matches
from sentence_transformers import SentenceTransformer, util


class IngredientNutritionSearch:
    """
    A class used to search for nutrition information of ingredients using both fuzzy and semantic search methods.
    """

    def __init__(self, dataset_path: str, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initializes the IngredientNutritionSearch with the dataset path and model name.

        Raises: RuntimeError: If the sentence transformer model fails to load.

        Note: Ingredient names in the dataset and during the search are converted to lowercase for consistent matching.
        """
        self.dataset_path = dataset_path
        self.data = self._load_data()
        self._ingredients = list(self.data.keys())

        try:
            self.encoder = SentenceTransformer(model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load `{model_name}`. Error: {e}")

        self._embeddings = self.encoder.encode(
            self._ingredients, convert_to_tensor=True
        )

    def _load_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads the ingredient nutrition data from the CSV file.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are ingredient names (in lowercase)
                                       and values are their nutrition data.

            Example:
            {
                'apple': {
                    'calories': 52.0,
                    'fats': 0.2,
                    'proteins': 0.3,
                    'carbohydrates': 13.8
                },
                'banana': {
                    'calories': 89.0,
                    'fats': 0.3,
                    'proteins': 1.1,
                    'carbohydrates': 22.8
                }
            }

        Raises:
            FileNotFoundError: If the dataset file is not found.
            KeyError: If the expected columns are missing from the CSV.
            Exception: For any other errors that occur during file reading.
        """
        ingredients = {}

        try:
            with open(self.dataset_path, mode="r", encoding="utf-8") as file:
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
                f"Error: The file '{self.dataset_path}' was not found."
            )
        except KeyError as e:
            raise KeyError(f"Error: Missing expected column in CSV file: {e}")
        except Exception as e:
            raise Exception(f"An error occurred while reading the file: {e}")

        return ingredients

    def _fuzzy_search(self, ingredient_name: str, threshold: float = 0.6) -> str:
        """
        Searches for the closest matching ingredient name using fuzzy matching based on string similarity.

        The fuzzy search compares the input ingredient name (converted to lowercase) with the list of available
        ingredient names (also in lowercase) and returns the best match based on a similarity score. It uses the
        `get_close_matches` method from the `difflib` module.

        Args:
            ingredient_name (str): The name of the ingredient to search for. The input is converted to lowercase.
            threshold (float): The similarity threshold for fuzzy matching (default is 0.6).
                               This value determines how similar the input string must be to return a match.

        Returns:
            str: The closest matching ingredient name if found, otherwise None.

            Example:
                Input: "aple" (misspelled)
                Match found: "apple"
                Result: 'apple'
        """
        matches = get_close_matches(
            ingredient_name.lower(), self._ingredients, n=1, cutoff=threshold
        )

        if matches:
            return matches[0]

        return None

    def _semantic_search(
        self, ingredient_name: str, threshold: float = 0.6
    ) -> str:
        """
        Searches for the closest matching ingredient name using semantic similarity search.
        ...
        Returns:
            str: The closest matching ingredient name if found, otherwise None.
        ...
        """
        ingredient_embedding = self.encoder.encode(
            ingredient_name.lower(), convert_to_tensor=True
        )

        cosine_scores = util.pytorch_cos_sim(ingredient_embedding, self._embeddings)
        max_index = cosine_scores.argmax()
        max_score = cosine_scores[0][max_index].item()

        if max_score >= threshold:
            return self._ingredients[max_index]

        return None

    def search(
        self, 
        img_ingredients: Dict[str, float],
        search_type: str = "fuzzy"
    ) -> List[Dict[str, Any]]:
        """
        Searches for the nutritional information of a list of ingredients.
        ...
        Args:
            img_ingredients (Dict[str, float]): A dictionary of ingredients and weights:
                {'ingredient_name': weight_in_grams}.
        ...
        """
        if search_type not in ["fuzzy", "semantic"]:
            raise ValueError("`search_type` must be either 'fuzzy' or 'semantic'")

        results = []

        for ingredient_name, ingredient_weight in img_ingredients.items():
            if ingredient_weight > 0:
                match = None

                if search_type == "fuzzy":
                    match = self._fuzzy_search(ingredient_name)
                elif search_type == "semantic":
                    match = self._semantic_search(ingredient_name)

                if match:
                    ingredient_data = self.data.get(match)
                    result_data = {"match": match, "weight": ingredient_weight}

                    result_data.update(
                        {
                            key: round(value * (ingredient_weight / 100.0), 0)
                            for key, value in ingredient_data.items()
                        }
                    )

                    results.append({ingredient_name: result_data})
                else:
                    results.append({ingredient_name: {}})

        return results
