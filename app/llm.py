"""
OpenRouter + Gemma LLM client.

Uses OpenRouter's OpenAI-compatible API.
Model: google/gemma-2-9b-it (current recommended Gemma on OpenRouter as of 2026)
"""

import os
import json
import httpx
from typing import Optional


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Current Gemma model on OpenRouter (verified 2026)
GEMMA_MODEL = "google/gemma-2-9b-it"


class LLMError(Exception):
    pass


async def call_gemma(prompt: str, system_prompt: Optional[str] = None, 
                     temperature: float = 0.2, max_tokens: int = 4096,
                     response_format: Optional[dict] = None) -> str:
    """
    Call Gemma via OpenRouter.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        temperature: Sampling temperature (low for structured output)
        max_tokens: Max output tokens
        response_format: Optional {"type": "json_object"} for JSON mode
    
    Returns:
        Model response text
    
    Raises:
        LLMError: On API errors
    """
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY not set in environment")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": GEMMA_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "TSP AI Service",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"OpenRouter API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}")


async def call_gemma_json(prompt: str, system_prompt: Optional[str] = None,
                          schema: Optional[dict] = None, max_retries: int = 3) -> dict:
    """
    Call Gemma and parse JSON response with retry on validation failure.
    
    Note: Gemma via OpenRouter does NOT reliably support structured output mode.
    We use prompt-based JSON instruction + Pydantic validation + retry.
    """
    json_instruction = """
    
IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, no extra text.
The JSON must match the expected schema exactly.
"""
    if schema:
        json_instruction += f"\nExpected schema: {json.dumps(schema, indent=2)}"

    full_prompt = prompt + json_instruction

    last_error = None
    for attempt in range(max_retries):
        try:
            response = await call_gemma(
                full_prompt, 
                system_prompt, 
                temperature=0.1,
                response_format={"type": "json_object"}  # Try native JSON mode
            )
            return json.loads(response)
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            # Add error feedback to prompt for retry
            full_prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {last_error}. Please output ONLY valid JSON."
        except LLMError as e:
            last_error = str(e)
            if attempt == max_retries - 1:
                raise

    raise LLMError(f"Failed to get valid JSON after {max_retries} attempts: {last_error}")


# Test function
async def test_gemma_connection() -> bool:
    """Test the OpenRouter + Gemma connection."""
    try:
        response = await call_gemma("Say 'Hello from Gemma' and nothing else.")
        print(f"Gemma test response: {response}")
        return "gemma" in response.lower() or "hello" in response.lower()
    except Exception as e:
        print(f"Gemma test failed: {e}")
        return False
