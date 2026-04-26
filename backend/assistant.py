from typing import Dict, Any
import os
import json
import asyncio
import ollama
from dotenv import load_dotenv


class LLMAssistant:
    """
    A class to interact with a large language model (LLM) using the Ollama API.
    
    Supports two types of tasks:
    - ingredient_recognition: Identifies food ingredients and their weights from images
    - macros_extraction: Extracts nutritional information (calories, proteins, fats, carbohydrates)
    
    All responses are returned as structured dictionaries with status, result, and error fields.
    """

    def __init__(
        self,
        prompt_ingredient_recognition: str,
        prompt_macros_extraction: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        top_p: float = 0.5,
    ):
        """
        Initializes the LLMAssistant instance with system prompts and generation parameters.

        Args:
            prompt_ingredient_recognition (str): System prompt for ingredient recognition tasks.
            prompt_macros_extraction (str): System prompt for macros extraction tasks.
            temperature (float): Sampling temperature for model generation (0.0-1.0). Default: 0.2
            max_tokens (int): Maximum number of tokens to generate. Default: 1024
            top_p (float): Nucleus sampling parameter (0.0-1.0). Default: 0.5

        Raises:
            ValueError: If the OLLAMA_HOST environment variable is not set.
        """
        load_dotenv()

        ollama_host = os.getenv("OLLAMA_HOST")
        if not ollama_host:
            raise ValueError("Environment variable OLLAMA_HOST is missing or empty.")

        self.prompt_ingredient_recognition = prompt_ingredient_recognition
        self.prompt_macros_extraction = prompt_macros_extraction
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.client = ollama.AsyncClient(host=ollama_host)

    def _generate_payload(self,
                          type_prompt: str,
                          ingredients: str = None,
                          image_base64: str = None,
                          user_desk: str = "") -> Dict[str, Any]:
        """
        Generates the input payload for the Ollama API using a Base64-encoded image.

        Args:
            image_base64 (str): The Base64-encoded image string.
            type_prompt (str): Type of prompt ('ingredient_recognition' or 'macros_extraction').
            user_desk (str): Optional custom description from user. Default: ""

        Returns:
            dict: Payload dictionary for the Ollama API chat endpoint.
        """
        if type_prompt == 'ingredient_recognition':
            return {
                "model": os.getenv("MODEL_NAME", "qwen3.5:9b"),
                "think": False,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": (self.prompt_ingredient_recognition if not user_desk.strip()
                        else self.prompt_ingredient_recognition + "\nDescription from the user: " + user_desk),
                        "images": [image_base64],
                    }
                ],
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_p": self.top_p,
                },
            }
        
        elif type_prompt == 'macros_extraction':
            return {
                "model": os.getenv("MODEL_NAME", "qwen3.5:9b"),
                "think": False,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": self.prompt_macros_extraction + "\nInput:" + ingredients,
                    }
                ],
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_p": self.top_p,
                    "think": False,
                    "stream": False,
                },
            }
            

    def _parse_response(self, output: str) -> Dict[str, Any]:
        """
        Parses the model output into a JSON object with status information.

        Args:
            output (str): Raw text response from the LLM.

        Returns:
            dict: Parsed response with structure:
                {"status": "success" | "error", "result": dict, "error": str}
        """
        try:
            output = output.replace("```", "").replace("json", "")
            json_result = json.loads(output)
            return {"status": "success", "result": json_result, "error": ""}
        except json.JSONDecodeError:
            return {
                "status": "error",
                "result": {},
                "error": "Failed to parse the model response as JSON.",
            }

    async def _chat(self, input_data: dict, timeout: int):
        """
        Executes a chat request to the Ollama API with timeout and error handling.

        Args:
            input_data (dict): Payload dictionary for the Ollama API.
            timeout (int): Time limit for the request in seconds.

        Returns:
            dict: Raw response from the Ollama API.

        Raises:
            Exception: If timeout, API error, or unexpected error occurs.
        """
        try:
            response = await asyncio.wait_for(
                self.client.chat(**input_data), timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)")
        except ollama.ResponseError as e:
            raise Exception(f"Ollama API error: {e.status_code} - {e.error}")
        except Exception as e:
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

        payload = self._generate_payload(type_prompt="ingredient_recognition",
                                         image_base64=image_base64,
                                         user_desk=user_desk,)

        try:
            response = await self._chat(payload, timeout)

            output = response["message"]["content"]

            return self._parse_response(output)

        except Exception as e:
            return {
                "status": "error",
                "result": {},
                "error": f"An error occurred during prediction: {str(e)}",
            }

    async def get_macros_extraction(
        self, ingredients: Dict[str, float], timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Extracts nutritional information (calories, proteins, fats, carbohydrates) from a food image.

        Args:
            image_base64 (str): The Base64-encoded image string.
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

        payload = self._generate_payload(type_prompt="macros_extraction",
                                         ingredients=json.dumps(ingredients, ensure_ascii=False),
                                         )

        try:
            response = await self._chat(payload, timeout)
            output = response["message"]["content"]
            return self._parse_response(output)

        except Exception as e:
            return {
                "status": "error",
                "result": {},
                "error": f"An error occurred during prediction: {str(e)}",
            }