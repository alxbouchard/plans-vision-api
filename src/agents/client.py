"""Vision client using OpenAI GPT-5.2 Responses API with vision capability."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Optional

import httpx
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.logging import get_logger

logger = get_logger(__name__)


# GPT-5.2 pricing (per 1M tokens) - adjust based on actual pricing
PRICING = {
    "gpt-5.2-pro": {"input": 2.50, "output": 10.00},
    "gpt-5.2": {"input": 1.25, "output": 5.00},
}


@dataclass
class UsageStats:
    """Token usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


# Global usage tracker for the current pipeline run
_current_usage = UsageStats()


def get_current_usage() -> UsageStats:
    """Get the current usage stats."""
    return _current_usage


def reset_usage() -> None:
    """Reset usage stats for a new pipeline run."""
    global _current_usage
    _current_usage = UsageStats()


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD."""
    pricing = PRICING.get(model, PRICING["gpt-5.2"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


class VisionClientError(Exception):
    """Error from the Vision client."""

    def __init__(self, message: str, error_code: str = "VISION_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class VisionClient:
    """
    Client for OpenAI Vision using GPT-5.2 Responses API.

    Uses gpt-5.2-pro for vision capabilities with image analysis.
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
        Analyze an image using GPT-5.2 Responses API.

        Args:
            image_bytes: PNG image bytes
            prompt: The analysis prompt
            model: Model to use (gpt-5.2-pro or gpt-5.2)
            reasoning_effort: Reasoning effort level (low, medium, high, xhigh)
            verbosity: Text verbosity level (low, medium, high)
            system_prompt: Optional system-level instructions

        Returns:
            The model's text response
        """
        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Use the model as specified (gpt-5.2-pro or gpt-5.2)
        actual_model = model if model.startswith("gpt-5.2") else "gpt-5.2-pro"

        # Build input array for Responses API
        input_content = []

        if system_prompt:
            input_content.append({
                "type": "message",
                "role": "system",
                "content": system_prompt
            })

        # User message with image and text
        input_content.append({
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{image_b64}",
                },
                {
                    "type": "input_text",
                    "text": prompt
                }
            ]
        })

        logger.info(
            "vision_request",
            model=actual_model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            image_size=len(image_bytes),
        )

        try:
            response = await self.client.responses.create(
                model=actual_model,
                input=input_content,
                reasoning={"effort": reasoning_effort},
                text={"verbosity": verbosity},
            )

            # Extract text from response output
            output_text = ""
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            output_text += content.text

            # Track usage
            usage = getattr(response, 'usage', None)
            input_tokens = 0
            output_tokens = 0
            if usage:
                input_tokens = getattr(usage, 'input_tokens', 0)
                output_tokens = getattr(usage, 'output_tokens', 0)
                cost = _calculate_cost(actual_model, input_tokens, output_tokens)

                # Update global tracker
                _current_usage.input_tokens += input_tokens
                _current_usage.output_tokens += output_tokens
                _current_usage.total_tokens += input_tokens + output_tokens
                _current_usage.cost_usd += cost
                _current_usage.requests += 1

            logger.info(
                "vision_response",
                model=actual_model,
                response_length=len(output_text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost_usd=round(_current_usage.cost_usd, 4),
            )

            return output_text

        except Exception as e:
            logger.error(
                "vision_error",
                model=actual_model,
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
        Analyze text using GPT-5.2 Responses API (no image).

        Args:
            prompt: The analysis prompt
            model: Model to use (gpt-5.2-pro or gpt-5.2)
            reasoning_effort: Reasoning effort level (low, medium, high, xhigh)
            verbosity: Text verbosity level (low, medium, high)
            system_prompt: Optional system-level instructions

        Returns:
            The model's text response
        """
        # Use the model as specified (gpt-5.2-pro or gpt-5.2)
        actual_model = model if model.startswith("gpt-5.2") else "gpt-5.2"

        # Build input array for Responses API
        input_content = []

        if system_prompt:
            input_content.append({
                "type": "message",
                "role": "system",
                "content": system_prompt
            })

        input_content.append({
            "type": "message",
            "role": "user",
            "content": prompt
        })

        logger.info(
            "text_request",
            model=actual_model,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
        )

        try:
            response = await self.client.responses.create(
                model=actual_model,
                input=input_content,
                reasoning={"effort": reasoning_effort},
                text={"verbosity": verbosity},
            )

            # Extract text from response output
            output_text = ""
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            output_text += content.text

            # Track usage
            usage = getattr(response, 'usage', None)
            input_tokens = 0
            output_tokens = 0
            if usage:
                input_tokens = getattr(usage, 'input_tokens', 0)
                output_tokens = getattr(usage, 'output_tokens', 0)
                cost = _calculate_cost(actual_model, input_tokens, output_tokens)

                # Update global tracker
                _current_usage.input_tokens += input_tokens
                _current_usage.output_tokens += output_tokens
                _current_usage.total_tokens += input_tokens + output_tokens
                _current_usage.cost_usd += cost
                _current_usage.requests += 1

            logger.info(
                "text_response",
                model=actual_model,
                response_length=len(output_text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost_usd=round(_current_usage.cost_usd, 4),
            )

            return output_text

        except Exception as e:
            logger.error(
                "text_error",
                model=actual_model,
                error=str(e),
            )
            raise VisionClientError(f"API error: {e}")
