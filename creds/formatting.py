"""Shared formatting utilities."""


def age_label(days: int) -> str:
    """Human-readable age string for a credential last updated N days ago."""
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"
    months = days // 30
    if months == 1:
        return "1 month ago"
    if months < 12:
        return f"{months} months ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"
