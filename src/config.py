import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MODEL_API_KEY", "")
API_BASE = os.getenv("MODEL_API_BASE", "https://api.meta.ai/v1")

TEXT_MODEL = "muse-spark-1.3"
REASONING_MODEL = "muse-wonder-1.0"
IMAGE_MODEL = "muse-image-1.0"
SEGMENT_MODEL = "sam-3.1"
TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0"


def require_config() -> None:
    if not API_KEY:
        raise SystemExit("MODEL_API_KEY missing: copy .env.example to .env and add your key")
