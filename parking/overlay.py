import base64
import io

from src import config
from src.client import get_client

COLORS = {"ok": "a green", "warn": "an amber", "bad": "a red"}


def overlay(photo: bytes, status: str, caption: str) -> bytes:
    """muse-image-1.0 edit: frame the sign photo in a verdict colour with a caption banner."""
    buf = io.BytesIO(photo)
    buf.name = "sign.jpg"
    r = get_client().images.edit(
        model=config.IMAGE_MODEL, image=buf, output_format="jpeg",
        prompt=(f"Keep this photo exactly as is, but add {COLORS[status]} border and a clean banner at the "
                f"bottom with the text: {caption}. Do not alter the sign text."),
    )
    return base64.b64decode(r.data[0].b64_json)
