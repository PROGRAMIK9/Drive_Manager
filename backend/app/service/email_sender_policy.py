from email.utils import parseaddr

from app.config.config import gmail_settings


def is_accepted_placement_sender(value: str | None) -> bool:
    """Accept only an address whose parsed domain exactly matches the configured college domain."""
    address = parseaddr(value or "")[1].strip().casefold()
    if "@" not in address:
        return False
    _, domain = address.rsplit("@", 1)
    expected = gmail_settings.PLACEMENT_SENDER_DOMAIN.strip().casefold().lstrip("@").rstrip(".")
    return bool(expected) and domain.rstrip(".") == expected
