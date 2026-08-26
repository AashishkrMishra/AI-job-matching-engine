"""Application configuration, read once from the environment.

Required variables are validated at import time. A missing DATABASE_URL or
SECRET_KEY is a deployment mistake, and failing loudly here is far safer than
booting a server that signs tokens with a value anyone can look up.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            f"or set {name} in the deployment environment."
        )
    return value


DATABASE_URL = _require("DATABASE_URL")

# Deliberately no default. A fallback would be identical in every clone of this
# repository, so anyone who read it could mint a valid token for any account.
SECRET_KEY = _require("SECRET_KEY")

# Optional: without a token the LLM recommendation degrades, but the app runs.
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
