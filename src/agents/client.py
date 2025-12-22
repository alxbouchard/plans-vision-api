"""GPT-5.2 Vision client using the Responses API."""

from __future__ import annotations

import base64
from typing import Optional

import httpx
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.logging import get_logger

logger = get_logger(__name__)


class VisionClientError(Exception):
    """Error from the Vision client."""

    def __init__(self, message: str, error_code: str = "VISION_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class VisionClient:
    """
    Client for GPT-5.2 Vision using the Responses API.

    Uses the new GPT-5.2 features:
    - reasoning.effort parameter
    - text.verbosity parameter
    - Image inputs via base64
    """

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        model: str,
        reasoning_effort: str = "high",
        verbosity: str = "high",
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Analyze an image using GPT-5.2 Vision.

        Args:
            image_bytes: PNG image bytes
            prompt: The analysis prompt
            model: Model to use (gpt-5.2, gpt-5.2-pro)
            reasoning_effort: none, low, medium, high, or xhigh
            verbosity: low, medium, or high
            system_prompt: Optional system-level instructions

        Returns:
            The model's text response
        """
        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Build input with image
        input_content = [
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{image_b64}",
            },
            {
                "type": "input_text",
                "text": prompt,
            },
        ]

        # Build the request
        request_params = {
            "model": model,
            "input": input_content,
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": verbosity},
        }

        # Add system prompt if provided
        if system_prompt:
            request_params["instructions"] = system_prompt

        logger.info(
            "vision_request",
            model=model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            image_size=len(image_bytes),
        )

        try:
            response = await self.client.responses.create(**request_params)

            # Extract text from response
            output_text = ""
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            output_text += content.text

            logger.info(
                "vision_response",
                model=model,
                response_length=len(output_text),
            )

            return output_text

        except Exception as e:
            logger.error(
                "vision_error",
                model=model,
                error=str(e),
            )
            raise VisionClientError(f"Vision API error: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def analyze_text(
        self,
        prompt: str,
        model: str,
        reasoning_effort: str = "high",
        verbosity: str = "high",
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Analyze text using GPT-5.2 (no image).

        Args:
            prompt: The analysis prompt
            model: Model to use
            reasoning_effort: none, low, medium, high, or xhigh
            verbosity: low, medium, or high
            system_prompt: Optional system-level instructions

        Returns:
            The model's text response
        """
        request_params = {
            "model": model,
            "input": prompt,
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": verbosity},
        }

        if system_prompt:
            request_params["instructions"] = system_prompt

        logger.info(
            "text_request",
            model=model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
        )

        try:
            response = await self.client.responses.create(**request_params)

            output_text = ""
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            output_text += content.text

            logger.info(
                "text_response",
                model=model,
                response_length=len(output_text),
            )

            return output_text

        except Exception as e:
            logger.error(
                "text_error",
                model=model,
                error=str(e),
            )
            raise VisionClientError(f"API error: {e}")
