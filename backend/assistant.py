import logging
from typing import Dict, Any, List, Optional
import os
import json
import asyncio
import ollama
from dotenv import load_dotenv
import re

load_dotenv()
logger = logging.getLogger("assistant")


class LLMAssistant:
    """
    A class to interact with a large language model (LLM) using the Ollama API.

    Supports three types of tasks:
    - ingredient_recognition: Identifies food ingredients and their weights from images
    - macros_extraction: Extracts nutritional information (calories, proteins, fats, carbohydrates)
    - translate_ingredients: Translates and normalizes ingredient names to target languages

    All responses are returned as structured dictionaries with status, result, and error fields.
    """

    def __init__(
        self,
        prompt_ingredient_recognition: str,
        prompt_macros_extraction: str,
        prompt_ingredient_translation: str,
        prompt_get_bmr: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        top_p: float = 0.5,
        translation_batch_size: int = 50,
        allowed_bmr_values: Optional[set] = None,
    ):
        """
        Initializes the LLMAssistant instance with system prompts and generation parameters.

        Args:
            prompt_ingredient_recognition (str): System prompt for ingredient recognition tasks.
            prompt_macros_extraction (str): System prompt for macros extraction tasks.
            prompt_ingredient_translation (str): System prompt for translation tasks.
            prompt_get_bmr (str): System prompt for BMR coefficient calculation tasks.
            temperature (float): Sampling temperature for model generation (0.0-1.0). Default: 0.2
            max_tokens (int): Maximum number of tokens to generate. Default: 1024
            top_p (float): Nucleus sampling parameter (0.0-1.0). Default: 0.5

        Raises:
            ValueError: If the OLLAMA_HOST environment variable is not set.
        """
        logger.info("Initializing LLMAssistant...")
        ollama_host = os.getenv("OLLAMA_HOST")
        if not ollama_host:
            logger.error("OLLAMA_HOST environment variable is missing or empty.")
            raise ValueError("Environment variable OLLAMA_HOST is missing or empty.")

        self.prompt_ingredient_recognition = prompt_ingredient_recognition
        self.prompt_macros_extraction = prompt_macros_extraction
        self.prompt_ingredient_translation = prompt_ingredient_translation
        self.prompt_get_bmr = prompt_get_bmr
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.client = ollama.AsyncClient(host=ollama_host)
        self.start_re = re.compile(r"^```(?:json)?\s*", flags=re.MULTILINE)
        self.end_re = re.compile(r"\s*```$", flags=re.MULTILINE)
        self.translation_batch_size = translation_batch_size
        self.allowed_bmr_values = allowed_bmr_values or {1.2, 1.375, 1.55, 1.725, 1.9}
        logger.info("✅ LLMAssistant initialized successfully")

    def _generate_payload(
        self,
        type_prompt: str,
        ingredients: str = None,
        image_base64: str = None,
        user_desk: str = "",
        payload: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates the input payload for the Ollama API based on the task type.

        Args:
            type_prompt (str): Task type identifier ("ingredient_recognition", "macros_extraction", "translate_ingredients", "get_bmr").
            ingredients (str, optional): JSON string of ingredients for macros extraction.
            image_base64 (str, optional): Base64 encoded image string for recognition.
            user_desk (str, optional): User's text description of the dish.
            payload (str, optional): JSON string payload for translation tasks or BMR calculation.
            **kwargs: Additional arguments to override default generation parameters (e.g., temperature, max_tokens).

        Returns:
            dict: A dictionary formatted for the Ollama chat API, including model, options, and messages.

        Raises:
            ValueError: If the `type_prompt` is unknown.
        """
        base = {
            "model": os.getenv("MODEL_NAME", "qwen3.5:9b"),
            "think": False,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
                "top_p": kwargs.get("top_p", self.top_p),
            },
        }

        if type_prompt == "ingredient_recognition":
            user_content = self.prompt_ingredient_recognition
            if user_desk.strip():
                user_content += f"\nDescription from the user: {user_desk}"

            base["messages"] = [
                {
                    "role": "user",
                    "content": user_content,
                    "images": [image_base64],
                }
            ]
            return base

        elif type_prompt == "macros_extraction":
            base["messages"] = [
                {
                    "role": "user",
                    "content": self.prompt_macros_extraction + "\nInput:" + ingredients,
                }
            ]
            return base

        elif type_prompt == "translate_ingredients":
            base["format"] = "json"
            base["messages"] = [
                {
                    "role": "user",
                    "content": f"{self.prompt_ingredient_translation}\n\nINPUT DATA:\n{payload}",
                }
            ]
            return base

        elif type_prompt == "get_bmr":
            base["format"] = "json"
            base["messages"] = [
                {
                    "role": "user",
                    "content": f"{self.prompt_get_bmr}\n\nUSER INPUT:\n{payload}",
                }
            ]
            return base

        raise ValueError(f"Unknown task type: {type_prompt}")

    def _parse_response(self, output: str) -> Dict[str, Any]:
        """
        Safely extracts and parses JSON from the LLM's raw text output.

        Handles markdown code blocks and trims non-JSON content.

        Args:
            output (str): The raw string output from the LLM.

        Returns:
            Dict[str, Any]: A standardized response dictionary:
                status (str): "success" or "error".
                result (Dict[str, Any] | List | None): Parsed JSON content or empty container.
                error (str): Error message or empty string.
        """
        cleaned = output.strip()
        if cleaned.startswith("```"):
            cleaned = self.start_re.sub("", cleaned)
        if cleaned.endswith("```"):
            cleaned = self.end_re.sub("", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        try:
            if start == -1 or end == -1 or end <= start:
                raise ValueError("No valid JSON object found in response")

            json_str = cleaned[start : end + 1]
            json_result = json.loads(json_str)
            return {"status": "success", "result": json_result, "error": ""}

        except json.JSONDecodeError as e:
            try:
                json_result = json.loads(output.strip())
                return {"status": "success", "result": json_result, "error": ""}
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed: {e.msg} at position {e.pos}")
                return {
                    "status": "error",
                    "result": {},
                    "error": f"Failed to parse JSON: {e.msg} (pos {e.pos})",
                }
        except Exception as e:
            logger.error(f"Unexpected parse error: {e}", exc_info=True)
            return {
                "status": "error",
                "result": {},
                "error": f"Parse error: {str(e)}",
            }

    async def _chat(self, input_data: Dict[str, Any], timeout: int):
        """
        Executes a chat request to the Ollama API with timeout and error handling.

        Args:
            input_data (dict): The full payload dictionary for the Ollama API.
            timeout (int): Time limit for the request in seconds.

        Returns:
            Dict[str, Any]: The raw response dictionary from Ollama client,
                typically containing "message" key with "content" field.

        Raises:
            Exception: If the request times out or the API returns an error.
        """
        model = input_data.get("model", "unknown")
        logger.debug(f"Calling Ollama model: {model} (timeout: {timeout}s)")

        try:
            response = await asyncio.wait_for(
                self.client.chat(**input_data), timeout=timeout
            )
            logger.debug(f"Ollama response received for {model}")
            return response
        except asyncio.TimeoutError:
            logger.error(f"Ollama request timed out ({timeout}s)")
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)")
        except ollama.ResponseError as e:
            logger.error(f"Ollama API error: {e.status_code} - {e.error}")
            raise Exception(f"Ollama API error: {e.status_code} - {e.error}")
        except Exception as e:
            logger.error(f"Unexpected error in _chat: {e}", exc_info=True)
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}")

    async def get_ingredient_recognition(
        self, image_base64: str, user_desk: str, timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Recognizes food ingredients and their weights from an image.

        Args:
            image_base64 (str): The Base64-encoded image string.
            user_desk (str): Custom description of the dish in the image.
            timeout (int): Time limit for accessing the model in seconds. Default: 60

        Returns:
            dict: Response dictionary with structure:
                {
                    "status": "success" | "error",
                    "result": dict (e.g., {"cheese": 100, "mushrooms": 200}),
                    "error": str (error message or empty string)
                }

        Raises:
            ValueError: If timeout is less than 1.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        logger.info(f"Starting ingredient recognition (timeout: {timeout}s)")
        payload = self._generate_payload(
            type_prompt="ingredient_recognition",
            image_base64=image_base64,
            user_desk=user_desk,
        )

        try:
            response = await self._chat(payload, timeout)
            return self._parse_response(response["message"]["content"])
        except Exception as e:
            logger.error(f"Ingredient recognition failed: {e}", exc_info=True)
            return {
                "status": "error",
                "result": {},
                "error": f"An error occurred during prediction: {str(e)}",
            }

    async def get_macros_extraction(
        self, ingredients: Dict[str, float], timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Extracts nutritional information (calories, proteins, fats, carbohydrates) from ingredient names.

        Args:
            ingredients (Dict[str, float]): Dictionary mapping ingredient names to their weights.
            timeout (int): Time limit for accessing the model in seconds. Default: 60

        Returns:
            dict: Response dictionary with structure:
                {
                    "status": "success" | "error",
                    "result": dict (e.g., {"banana": {"weight": 50, "calories": 110, ...}}),
                    "error": str (error message or empty string)
                }

        Raises:
            ValueError: If timeout is less than 1.
        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        logger.info(
            f"Starting macros extraction for {len(ingredients)} items (timeout: {timeout}s)"
        )
        payload = self._generate_payload(
            type_prompt="macros_extraction",
            ingredients=json.dumps(ingredients, ensure_ascii=False),
        )

        try:
            response = await self._chat(payload, timeout)
            return self._parse_response(response["message"]["content"])
        except Exception as e:
            logger.error(f"Macros extraction failed: {e}", exc_info=True)
            return {
                "status": "error",
                "result": {},
                "error": f"An error occurred during prediction: {str(e)}",
            }

    async def translate_ingredients(
        self, payload: Dict[str, List[str]], timeout_on_chunk: int = 120
    ) -> Dict[str, Any]:
        """
        Normalizes and translates ingredient names in batches.

        Processes the payload in chunks to avoid context window limits and manages retries.

        Args:
            payload (Dict[str, List[str]]): Dictionary where keys are ingredient names
                                            and values are lists of target language codes.
            timeout_on_chunk (int): Time limit for each chunk request in seconds. Default: 120

        Returns:
            dict: Response dictionary with structure:
                {
                    "status": "success" | "partial_success" | "error",
                    "result": dict (aggregated translations),
                    "error": str (aggregated error messages if any)
                }

        Raises:
            ValueError: If timeout is less than 1.
        """
        if timeout_on_chunk < 1:
            raise ValueError("Timeout must be >= 1.")

        if not payload:
            return {"status": "success", "result": {}, "error": ""}

        items = list(payload.items())
        chunks = [
            dict(items[i : i + self.translation_batch_size])
            for i in range(0, len(items), self.translation_batch_size)
        ]
        logger.info(
            f"Starting translation batch: {len(payload)} keys, {len(chunks)} chunks (timeout/chunk: {timeout_on_chunk}s)"
        )

        merged_results = {}
        errors = []

        for i, chunk in enumerate(chunks):
            try:
                payload_json = json.dumps(
                    chunk, ensure_ascii=False, separators=(",", ":")
                )
                logger.debug(
                    f"Processing translation chunk {i+1}/{len(chunks)} ({len(chunk)} items)"
                )

                chat_payload = self._generate_payload(
                    type_prompt="translate_ingredients",
                    payload=payload_json,
                    temperature=0.01,
                    max_tokens=4096,
                )

                response = await self._chat(chat_payload, timeout_on_chunk)
                parsed = self._parse_response(response["message"]["content"])

                if parsed["status"] == "success":
                    merged_results.update(parsed["result"])
                    logger.debug(f"Chunk {i+1} translated successfully")
                else:
                    logger.warning(
                        f"Translation chunk {i+1} parse failed: {parsed['error']}"
                    )
                    errors.append(f"Chunk {i+1}: {parsed['error']}")

            except Exception as e:
                logger.error(f"Translation chunk {i+1} exception: {e}", exc_info=True)
                errors.append(f"Chunk {i+1} failed: {str(e)}")

            if i < len(chunks) - 1:
                await asyncio.sleep(0.3)

        if not errors:
            logger.info("Translation batch completed successfully")
            return {"status": "success", "result": merged_results, "error": ""}
        elif merged_results:
            logger.warning(f"Translation batch partial success: {'; '.join(errors)}")
            return {
                "status": "partial_success",
                "result": merged_results,
                "error": "; ".join(errors),
            }
        else:
            logger.error(f"Translation batch failed: {'; '.join(errors)}")
            return {"status": "error", "result": {}, "error": "; ".join(errors)}

    async def get_bmr(
        self, lifestyle_description: str, timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Calculates the activity multiplier (BMR coefficient) by matching
        the user's lifestyle description to predefined activity levels.

        Args:
            lifestyle_description (str): User's description or selected preset.
            timeout (int): Request timeout in seconds. Default: 60

        Returns:
            Dict[str, Any]: Standardized response dictionary:
                status (str): "success" or "error".
                result (Dict[str, float]): {"bmr": float} with activity multiplier.
                error (str): Error message or empty string.

        Raises:
            ValueError: If timeout is less than 1.
        """
        if timeout < 1:
            raise ValueError("Timeout must be >= 1.")

        if not lifestyle_description or not lifestyle_description.strip():
            logger.debug("Empty lifestyle description, returning default bmr=1.375")
            return {"status": "success", "result": {"bmr": 1.375}, "error": ""}

        logger.info(f"Calculating BMR multiplier for: {lifestyle_description[:100]}...")

        payload_json = json.dumps(
            {"description": lifestyle_description}, ensure_ascii=False
        )
        chat_payload = self._generate_payload(
            type_prompt="get_bmr",
            payload=payload_json,
            temperature=0.01,
            max_tokens=50,
        )

        try:
            response = await self._chat(chat_payload, timeout)
            parsed = self._parse_response(response["message"]["content"])

            if parsed["status"] == "success":
                raw_val = parsed["result"].get("bmr")

                if raw_val in self.allowed_bmr_values:
                    logger.info(f"✅ LLM matched bmr={raw_val}")
                    return {
                        "status": "success",
                        "result": {"bmr": raw_val},
                        "error": "",
                    }

                if isinstance(raw_val, (int, float)):
                    closest = min(self.allowed_bmr_values, key=lambda x: abs(x - raw_val))
                    logger.warning(
                        f"LLM returned non-standard bmr={raw_val}, clamping to {closest}"
                    )
                    return {
                        "status": "success",
                        "result": {"bmr": closest},
                        "error": "",
                    }

            return {
                "status": "error",
                "result": {"bmr": 1.375},
                "error": parsed.get("error", "Invalid format"),
            }

        except Exception as e:
            logger.error(f"BMR calculation failed: {e}", exc_info=True)
            return {"status": "error", "result": {"bmr": 1.375}, "error": str(e)}
