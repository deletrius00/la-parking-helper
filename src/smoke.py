"""Run: python -m src.smoke  -- lists models and makes one chat call."""
from . import config
from .client import get_client


def main() -> None:
    client = get_client()
    print("models:", [m.id for m in client.models.list()])
    resp = client.chat.completions.create(
        model=config.TEXT_MODEL,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()
