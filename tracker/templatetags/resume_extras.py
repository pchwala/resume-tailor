"""Template filters for the resume PDF layout."""
from django import template

register = template.Library()


@register.filter
def display_url(value: str) -> str:
    """Human-friendly link text: drop the scheme, a leading ``www.``, and any trailing slash.

    ``https://github.com/pchwala`` -> ``github.com/pchwala``
    ``https://pchwala.dev/``       -> ``pchwala.dev``
    """
    if not value:
        return ""
    text = str(value)
    for scheme in ("https://", "http://"):
        if text.startswith(scheme):
            text = text[len(scheme):]
            break
    if text.startswith("www."):
        text = text[4:]
    return text.rstrip("/")
