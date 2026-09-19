"""
OpenRouter + Gemma LLM client.

Uses OpenRouter's OpenAI-compatible API.
Model: google/gemma-4-26b-a4b-it (Gemma 4 — 26B total, 4B active params, instruct)

Why Gemma 4 (A4B):
- 26B total / 4B active parameter MoE model optimised for instruction following
- Faster inference and lower cost than dense 31B variant
- Context window: 128K tokens — sufficient for full curriculum prompts
- Available on OpenRouter free tier as: google/gemma-4-26b-a4b-it:free
"""

import os
import json
import re
import httpx
from typing import Optional


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Gemma 4 (26B-A4B) Instruct — recommended model for this service
# Override via GEMMA_MODEL env var if needed (e.g. for testing paid tier)
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "google/gemma-4-26b-a4b-it:free")

# Timeout: E4B is fast, but curriculum generation prompts are large
DEFAULT_TIMEOUT_SECONDS = 120.0


class LLMError(Exception):
    """Raised when the LLM call fails for any reason."""
    pass


def _validate_api_key() -> None:
    """Raise LLMError early if key is missing or still a placeholder."""
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_key_here":
        raise LLMError(
            "OPENROUTER_API_KEY is not set or is still a placeholder. "
            "Copy .env.example to .env and fill in your real key from https://openrouter.ai/keys"
        )


async def call_gemma(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    response_format: Optional[dict] = None,
) -> str:
    """
    Call Gemma E4B via OpenRouter's OpenAI-compatible endpoint.

    Args:
        prompt: User-turn prompt content.
        system_prompt: Optional system instruction (prepended as system role message).
        temperature: Sampling temperature. Use low values (0.0–0.2) for structured output.
        max_tokens: Maximum tokens to generate.
        response_format: Optional {"type": "json_object"} to request JSON mode.

    Returns:
        The model's text response (stripped).

    Raises:
        LLMError: On API errors, network errors, or missing key.
    """
    _validate_api_key()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
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

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_attempts:
                    # Rate limited — exponential backoff (10s, 20s, 40s)
                    wait = 10 * (2 ** (attempt - 1))
                    print(f"[LLM] Rate limited (429), retrying in {wait}s (attempt {attempt}/{max_attempts})")
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                raise LLMError(
                    f"OpenRouter API error {e.response.status_code}: {e.response.text}"
                ) from e
            except Exception as e:
                raise LLMError(f"LLM call failed: {e}") from e


def _extract_json_from_response(text: str) -> str:
    """
    Strip markdown fences and extract the first JSON object/array from a response.
    Handles ```json ... ``` blocks that some models emit despite being told not to.
    """
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    # Find first { or [ and last matching bracket
    start = next((i for i, c in enumerate(text) if c in "{["), None)
    if start is None:
        return text
    return text[start:]


async def call_gemma_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    schema: Optional[dict] = None,
    max_retries: int = 3,
) -> dict:
    """
    Call Gemma and parse JSON response, with retry-on-parse-failure.

    Strategy:
    1. Request JSON mode via response_format (supported on some OpenRouter routes)
    2. Append explicit JSON-only instruction to user prompt
    3. On JSONDecodeError, strip markdown fences and retry with error feedback
    4. After max_retries, raise LLMError

    Args:
        prompt: User-turn prompt.
        system_prompt: Optional system instruction.
        schema: Optional JSON schema dict appended as guidance (not enforced server-side).
        max_retries: Number of attempts before giving up.

    Returns:
        Parsed dict from the model's JSON response.

    Raises:
        LLMError: If JSON cannot be parsed after all retries, or on API error.
    """
    schema_hint = ""
    if schema:
        # Truncate schema to avoid token overflow — include only top-level properties
        top_level = {
            k: v for k, v in schema.get("properties", {}).items()
        }
        schema_hint = f"\n\nExpected JSON schema (top-level fields):\n{json.dumps(top_level, indent=2)}"

    json_instruction = (
        "\n\nCRITICAL: Respond with ONLY valid JSON. "
        "No markdown, no ``` fences, no explanation, no trailing text. "
        "Start your response with { and end with }."
        + schema_hint
    )
    full_prompt = prompt + json_instruction

    last_error: Optional[str] = None
    for attempt in range(max_retries):
        try:
            raw = await call_gemma(
                full_prompt,
                system_prompt,
                temperature=0.1,  # Low temperature for deterministic JSON
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            clean = _extract_json_from_response(raw)
            return json.loads(clean)

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error (attempt {attempt + 1}): {e}"
            # Feed the error back into the next attempt's prompt
            full_prompt += (
                f"\n\nYour previous response could not be parsed as JSON. "
                f"Error: {e}. Output ONLY valid JSON starting with {{."
            )

        except LLMError:
            # API/network errors — re-raise immediately on final attempt
            if attempt == max_retries - 1:
                raise
            # Otherwise retry
            last_error = f"LLM error on attempt {attempt + 1}"

    raise LLMError(
        f"Failed to get valid JSON after {max_retries} attempts. Last error: {last_error}"
    )


async def test_gemma_connection() -> bool:
    """Smoke-test the OpenRouter + Gemma E4B connection."""
    try:
        response = await call_gemma(
            "Reply with exactly: Hello from Gemma E4B",
            max_tokens=20,
        )
        print(f"[LLM] Test response: {response}")
        return bool(response)
    except LLMError as e:
        print(f"[LLM] Connection test failed: {e}")
        return False
