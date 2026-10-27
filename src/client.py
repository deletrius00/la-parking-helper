from openai import OpenAI

from . import config


def get_client() -> OpenAI:
    config.require_config()
    return OpenAI(base_url=config.API_BASE, api_key=config.API_KEY)
