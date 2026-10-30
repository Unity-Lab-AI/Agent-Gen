import os
from dotenv import load_dotenv
import re
import logging

logger = logging.getLogger(__name__)

# Load .env file if present, but allow environment variables to be set on the system
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    # `override=False` ensures system environment variables take precedence
    load_dotenv(env_path, override=False)
    logger.info(f"Loaded .env file from {env_path}")
else:
    logger.info(f".env file not found at {env_path}; relying on system environment variables")


# ─── Pollinations.AI endpoints ──────────────────────────────────────────────
# New stack (Website2.0 / PolliLibPy v2.1.5 pattern — gen.pollinations.ai):
#   - Chat completions: POST {GEN_CHAT_URL}  with Authorization: Bearer <key>
#   - Models list:      GET {GEN_TEXT_MODELS_URL}
#   - Image generation: GET {GEN_IMAGE_BASE}/<urlencoded_prompt>?key=<key>&...
#
# Legacy stack (V4 original — text.pollinations.ai):
#   - Chat completions: POST {LEGACY_CHAT_URL}?token=<16-char-token>
#   - Models list:      GET {LEGACY_MODELS_URL}
#   - Image generation: GET {LEGACY_IMAGE_BASE}/<urlencoded_prompt>?...&apikey=<token>
#
# The bot detects which stack to use based on the API key format:
#   - pk_<chars>  → new stack (publishable key, Bearer auth)
#   - sk_<chars>  → new stack (secret key, Bearer auth)
#   - <16 alnum>  → legacy stack (token in query string) — kept for backward compat

GEN_BASE = "https://gen.pollinations.ai"
GEN_CHAT_URL = f"{GEN_BASE}/v1/chat/completions"
GEN_TEXT_MODELS_URL = f"{GEN_BASE}/text/models"
GEN_IMAGE_MODELS_URL = f"{GEN_BASE}/image/models"
GEN_IMAGE_BASE = f"{GEN_BASE}/image"

LEGACY_CHAT_URL = "https://text.pollinations.ai/openai"
LEGACY_MODELS_URL = "https://text.pollinations.ai/models"
LEGACY_IMAGE_BASE = "https://image.pollinations.ai/prompt"


# ─── Key format regexes ─────────────────────────────────────────────────────

DISCORD_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{50,100}$")
POLLINATIONS_PK_RE = re.compile(r"^pk_[A-Za-z0-9]{8,64}$")
POLLINATIONS_SK_RE = re.compile(r"^sk_[A-Za-z0-9]{8,64}$")
POLLINATIONS_LEGACY_RE = re.compile(r"^[A-Za-z0-9]{16}$")


def detect_pollinations_stack(key: str) -> str:
    """Classify a Pollinations key as 'new_pk', 'new_sk', or 'legacy'."""
    if POLLINATIONS_PK_RE.match(key):
        return "new_pk"
    if POLLINATIONS_SK_RE.match(key):
        return "new_sk"
    if POLLINATIONS_LEGACY_RE.match(key):
        return "legacy"
    raise ValueError(
        "Invalid Pollinations key format. Expected pk_xxx (publishable), "
        "sk_xxx (secret), or legacy 16-char alphanumeric token. "
        "Get a new key at https://enter.pollinations.ai"
    )


class Config:
    def __init__(self):
        # ─── Discord token ──────────────────────────────────────────────────
        self.discord_token = os.getenv("DISCORD_TOKEN")
        if self.discord_token:
            self.discord_token = self.discord_token.strip()
            logger.debug(f"Discord token length: {len(self.discord_token)}")
            if not DISCORD_TOKEN_RE.match(self.discord_token):
                logger.error(
                    "Invalid Discord token format (length: %d)", len(self.discord_token)
                )
                raise ValueError(
                    "Invalid Discord token format. Ensure no spaces, quotes, or invalid characters."
                )
        else:
            logger.error("DISCORD_TOKEN not found in environment variables")
            raise ValueError("DISCORD_TOKEN not found in environment variables")
        logger.info("Successfully loaded discord token (length: %d)", len(self.discord_token))

        # ─── Pollinations API key (new) — with legacy fallback ──────────────
        # Preferred: POLLINATIONS_API_KEY (new pk_/sk_ format)
        # Backward-compat: POLLINATIONS_TOKEN (old 16-char format) — auto-detected
        raw_key = (
            os.getenv("POLLINATIONS_API_KEY")
            or os.getenv("POLLINATIONS_TOKEN")
            or ""
        ).strip()

        if not raw_key:
            logger.error("Neither POLLINATIONS_API_KEY nor POLLINATIONS_TOKEN found")
            raise ValueError(
                "POLLINATIONS_API_KEY (or legacy POLLINATIONS_TOKEN) not found in environment. "
                "Get a key at https://enter.pollinations.ai and add it to .env"
            )

        try:
            self.pollinations_stack = detect_pollinations_stack(raw_key)
        except ValueError as e:
            logger.error("Invalid Pollinations key (length: %d): %s", len(raw_key), e)
            raise

        self.pollinations_key = raw_key
        # Keep the legacy attribute name as an alias for any external code still reading it
        self.pollinations_token = raw_key

        if self.pollinations_stack == "legacy":
            logger.warning(
                "Legacy 16-char Pollinations token detected. Pollinations migrated to "
                "gen.pollinations.ai with pk_/sk_ keys (May 2025). The bot will use the "
                "legacy endpoints for now, but consider rotating to a pk_/sk_ key at "
                "https://enter.pollinations.ai"
            )
            self.chat_url = LEGACY_CHAT_URL
            self.models_url = LEGACY_MODELS_URL
            self.image_base = LEGACY_IMAGE_BASE
            self.image_models_url = None  # legacy stack has no image-models endpoint
            # Legacy endpoint takes token in query string
            self.api_url = f"{LEGACY_CHAT_URL}?token={raw_key}"
        else:
            logger.info(
                "Using new Pollinations stack (gen.pollinations.ai) with %s key",
                "publishable (pk_)" if self.pollinations_stack == "new_pk" else "secret (sk_)",
            )
            # Belt-and-suspenders auth (per PolliLibPy v2.1.5 pattern):
            # - Primary: `Authorization: Bearer <key>` header (set by Config.auth_header())
            # - Secondary: `?key=<key>` query string on every URL
            # Either auth mode alone works against gen.pollinations.ai; using both
            # avoids 401s in edge cases where one channel is stripped by intermediaries.
            self.chat_url = f"{GEN_CHAT_URL}?key={raw_key}"
            self.models_url = f"{GEN_TEXT_MODELS_URL}?key={raw_key}"
            self.image_base = GEN_IMAGE_BASE
            self.image_models_url = f"{GEN_IMAGE_MODELS_URL}?key={raw_key}"
            self.api_url = self.chat_url

        # ─── Bot configuration ──────────────────────────────────────────────
        self.default_model = "unity"
        try:
            with open("system_instructions.txt", "r", encoding="utf-8") as f:
                self.system_instructions = f.read().strip()
        except FileNotFoundError:
            logger.error("system_instructions.txt not found")
            raise FileNotFoundError("system_instructions.txt not found")

        self.max_history = 20
        self.max_memories = 5

        allowed_channels_env = os.getenv("ALLOWED_CHANNELS", "")
        self.allowed_channels = {
            ch.strip() for ch in allowed_channels_env.split(",") if ch.strip()
        }

        # ─── Guild allowlist (Discord servers) ──────────────────────────────
        # If set, the bot only responds in messages from these guild IDs.
        # DMs (guild=None) are always allowed unless explicitly opted out via
        # the special token "no-dms" appearing in the list.
        # If empty, the bot operates in every guild it's invited to.
        # Recommended for trust + privacy — set explicit allowlist in production.
        allowed_guilds_env = os.getenv("ALLOWED_GUILDS", "")
        raw_guilds = {g.strip() for g in allowed_guilds_env.split(",") if g.strip()}
        self.allow_dms = "no-dms" not in raw_guilds
        self.allowed_guilds = raw_guilds - {"no-dms"}
        # When True and bot is added to a non-approved guild, leave it on join
        # (see bot.py on_guild_join). Set ALLOWED_GUILDS_STRICT=1 in env to enable.
        self.allowed_guilds_strict = os.getenv("ALLOWED_GUILDS_STRICT", "").strip() in ("1", "true", "yes")

    def auth_header(self) -> dict:
        """Build the Authorization header for the new stack. Returns {} on legacy."""
        if self.pollinations_stack == "legacy":
            return {}
        return {"Authorization": f"Bearer {self.pollinations_key}"}

    def image_url(self, prompt: str, *, model: str = "flux", width: int = 1024,
                  height: int = 1024, seed: int | None = None,
                  enhance: bool = False, nologo: bool = False, safe: bool = False) -> str:
        """Build a complete image-generation URL for the active stack.

        New stack: gen.pollinations.ai/image/<encoded>?model=&width=&height=&key=
        Legacy:    image.pollinations.ai/prompt/<encoded>?model=&width=&height=&apikey=
        """
        from urllib.parse import quote
        encoded = quote(prompt)
        params = [f"model={model}", f"width={width}", f"height={height}"]
        if seed is not None:
            params.append(f"seed={seed}")
        if enhance:
            params.append("enhance=true")
        if nologo:
            params.append("nologo=true")
        if safe:
            params.append("safe=true")
        if self.pollinations_stack == "legacy":
            params.append(f"apikey={self.pollinations_key}")
            base = self.image_base
        else:
            params.append(f"key={self.pollinations_key}")
            base = self.image_base
        return f"{base}/{encoded}?{'&'.join(params)}"
