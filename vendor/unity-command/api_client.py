import aiohttp
import random
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class APIClient:
    """Async HTTP client for the Pollinations.AI text API.

    Supports both stacks based on `config.pollinations_stack`:
      - 'new_pk' / 'new_sk' → gen.pollinations.ai/v1/chat/completions  with Authorization: Bearer
      - 'legacy'            → text.pollinations.ai/openai?token=<16char>

    Selection is made by `config.py` at startup; this client just honors the
    `config.chat_url`, `config.models_url`, and `config.auth_header()` it was given.
    """

    USER_AGENT = "UnityBotV4/2.0 (PolliLibPy-compatible)"

    def __init__(self, config):
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self.retry_attempts = 6
        self.retry_delay = 2

    async def initialize(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _headers(self, extra: Dict[str, str] | None = None) -> Dict[str, str]:
        """Merge default headers + auth header (if applicable) + per-call extras."""
        headers: Dict[str, str] = {"User-Agent": self.USER_AGENT}
        headers.update(self.config.auth_header())
        if extra:
            headers.update(extra)
        return headers

    async def _request_json(self, method: str, url: str, **kwargs) -> Dict[str, Any] | str:
        if self.session is None or self.session.closed:
            await self.initialize()

        # Merge headers — caller-supplied headers take precedence after our defaults
        caller_headers = kwargs.pop("headers", None) or {}
        kwargs["headers"] = self._headers(caller_headers)

        for attempt in range(self.retry_attempts):
            try:
                async with self.session.request(method, url, **kwargs) as resp:
                    if resp.status == 200:
                        # New stack returns JSON, legacy also returns JSON for /openai
                        ctype = resp.headers.get("Content-Type", "")
                        if "json" in ctype:
                            return await resp.json()
                        # Fallback — some endpoints return text/plain; wrap as a stub
                        text = await resp.text()
                        try:
                            import json as _json
                            return _json.loads(text)
                        except Exception:
                            return {"_text": text}

                    if resp.status in {429, 500, 502, 503, 504}:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        else:
                            delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        logger.warning(
                            f"Retry {attempt + 1}/{self.retry_attempts} status {resp.status} wait {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Other HTTP errors — surface immediately
                    try:
                        error_text = await resp.text()
                    except Exception:
                        error_text = ""
                    return f"Error: API returned status {resp.status} {error_text}"

            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(
                    f"Retry {attempt + 1}/{self.retry_attempts} due to {e} wait {delay:.2f}s"
                )
                await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(f"Unexpected exception {e}")
                return f"Error: Unexpected exception {e}"

        logger.error("API unreachable after retries")
        return "Error: Upstream API unreachable after retries"

    async def fetch_models(self) -> List[Dict[str, str]]:
        """List available text-generation models.

        Returns a list of {name, description?} dicts. Falls back to a single
        'unity' model if the endpoint errors out.
        """
        result = await self._request_json("GET", self.config.models_url, timeout=15)
        if isinstance(result, list):
            if all(isinstance(m, str) for m in result):
                return [{"name": m.strip()} for m in result]
            if all(isinstance(m, dict) and "name" in m for m in result):
                return [
                    {"name": m["name"].strip(), "description": m.get("description", "")}
                    for m in result
                ]
        # New stack /v1/models returns {"data": [...]} (OpenAI-compatible)
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            data = result["data"]
            if all(isinstance(m, dict) and ("id" in m or "name" in m) for m in data):
                return [
                    {"name": m.get("name") or m.get("id"), "description": m.get("description", "")}
                    for m in data
                ]
        return [{"name": "unity", "description": "Default unity model"}]

    async def send_message(self, messages: list, model: str | None):
        """Send a chat-completion request through whichever stack is active.

        Payload follows the OpenAI-compatible shape used by both
        text.pollinations.ai/openai (legacy) and gen.pollinations.ai/v1/chat/completions (new).
        """
        if self.session is None or self.session.closed:
            await self.initialize()

        if not model or not isinstance(model, str) or model.strip() == "":
            model = self.config.default_model
        logger.info(f"Using model: {model}")

        payload = {
            "messages": messages,
            "model": model,
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": False,
        }

        try:
            result = await self._request_json(
                "POST",
                self.config.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            )
        except asyncio.TimeoutError:
            return "Error: Request timed out"

        if isinstance(result, str):
            return result
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            return f"Error: Invalid response format {e}"
