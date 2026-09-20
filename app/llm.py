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

# Gemma 4 31B Instruct (free tier) — dense model, good structured JSON output
# Override via GEMMA_MODEL env var if needed
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "google/gemma-4-31b-it:free")

# Timeout: curriculum generation prompts require large outputs
DEFAULT_TIMEOUT_SECONDS = 300.0


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
    max_tokens: int = 8192,
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

    api_key = os.getenv("OPENROUTER_API_KEY") or OPENROUTER_API_KEY
    model = os.getenv("GEMMA_MODEL") or GEMMA_MODEL

    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # For models with thinking/reasoning modes, set effort to none to dedicate 100% tokens to JSON content
    if any(k in model.lower() for k in ["nemotron", "qwen", "liquid"]):
        payload["reasoning"] = {"effort": "none"}
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "TSP AI Service",
    }

    import asyncio as _asyncio
    max_attempts = 6
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            if not content or not content.strip():
                content = msg.get("reasoning", "")
            return (content or "").strip()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429 and attempt < max_attempts:
                wait = 10 * (2 ** (attempt - 1))
                err_detail = e.response.text[:120].replace('\n', ' ')
                print(f"[LLM] Rate limited (429: {err_detail}), retrying in {wait}s (attempt {attempt}/{max_attempts})")
                await _asyncio.sleep(wait)
                continue
            if status == 402 and attempt < max_attempts:
                current = payload.get("max_tokens", 4096)
                reduced = max(1024, current // 2)
                print(f"[LLM] Credit limit (402): reducing max_tokens {current} → {reduced} (attempt {attempt}/{max_attempts})")
                payload["max_tokens"] = reduced
                continue
            raise LLMError(
                f"OpenRouter API error {status}: {e.response.text}"
            ) from e
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException,
                httpx.RemoteProtocolError, httpx.WriteError) as e:
            if attempt < max_attempts:
                wait = 5 * attempt
                print(f"[LLM] Network error ({type(e).__name__}), retrying in {wait}s (attempt {attempt}/{max_attempts})")
                await _asyncio.sleep(wait)
                continue
            raise LLMError(f"Network error after {max_attempts} attempts: {e}") from e
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e


def _extract_json_from_response(text: str) -> str:
    """
    Strip markdown fences and extract the JSON object/array from a response.
    Handles ```json ... ``` blocks, trailing commentary, and preamble text.
    """
    text = text.strip()
    # Check for markdown code fence first
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    # Prefer locating start of a genuine JSON object e.g. {"key":
    obj_match = re.search(r'\{\s*"[a-zA-Z0-9_-]+"\s*:', text)
    if obj_match:
        start = obj_match.start()
        end = text.rfind("}")
        if end != -1 and end >= start:
            return text[start:end+1]

    start = next((i for i, c in enumerate(text) if c in "{["), None)
    if start is None:
        return text
    end = max(text.rfind("}"), text.rfind("]"))
    if end != -1 and end >= start:
        return text[start:end+1]
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
                temperature=0.1,
                max_tokens=7500,
                response_format={"type": "json_object"},
            )
            print(f"[LLM JSON] Raw response length: {len(raw)}, start: {repr(raw[:150])}, end: {repr(raw[-150:])}")
            clean = _extract_json_from_response(raw)
            try:
                return json.loads(clean)
            except json.JSONDecodeError as jde:
                print(f"[LLM JSON] JSONDecodeError: {jde}. Clean start: {repr(clean[:300])}")
                raise

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error (attempt {attempt + 1}): {e}"
            full_prompt += (
                f"\n\nYour previous response could not be parsed as JSON. "
                f"Error: {e}. Output ONLY valid JSON starting with {{."
            )

        except LLMError as e:
            if attempt == max_retries - 1:
                raise
            last_error = f"LLM error on attempt {attempt + 1}: {e}"

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
