from src import config


def test_config_importable():
    assert hasattr(config, "require_config")
