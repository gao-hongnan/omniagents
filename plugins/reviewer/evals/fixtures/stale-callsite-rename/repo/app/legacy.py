"""Legacy settings shim kept for the old CLI."""


def load_settings(path: str) -> dict[str, str]:
    settings: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                key, _, value = line.partition("=")
                settings[key.strip()] = value.strip()
    except Exception:
        pass
    return settings
