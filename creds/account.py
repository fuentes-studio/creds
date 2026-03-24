"""Account key formatting for canonical Keychain account names."""
import re


def account_key(service_id: str, instance: str, field_id: str) -> str:
    """Return canonical account key string for Keychain storage.

    Examples:
        account_key("anthropic", "", "api_key")      -> "anthropic.api_key"
        account_key("slack", "Acme", "bot_token")    -> "slack[Acme].bot_token"
    """
    if instance:
        return f"{service_id}[{instance}].{field_id}"
    return f"{service_id}.{field_id}"


def parse_account_key(key: str) -> tuple[str, str, str]:
    """Parse a canonical account key into (service_id, instance, field_id).

    Examples:
        parse_account_key("anthropic.api_key")       -> ("anthropic", "", "api_key")
        parse_account_key("slack[Acme].bot_token")   -> ("slack", "Acme", "bot_token")
    """
    multi = re.match(r"^([^\[]+)\[([^\]]*)\]\.(.+)$", key)
    if multi:
        return multi.group(1), multi.group(2), multi.group(3)

    single = re.match(r"^([^\.]+)\.(.+)$", key)
    if single:
        return single.group(1), "", single.group(2)

    raise ValueError(f"Invalid account key format: {key!r}")
