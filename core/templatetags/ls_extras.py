import bleach
import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = ["p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "ul", "ol", "li", "strong", "em", "code",
                "pre", "blockquote", "table", "thead", "tbody", "tr", "th", "td", "a", "span"]
ALLOWED_ATTRS = {"a": ["href", "title"]}


@register.filter
def render_md(text):
    html = md.markdown(text or "", extensions=["fenced_code", "tables", "nl2br"])
    return mark_safe(bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True))


@register.filter
def pct_class(p):
    p = p or 0
    return "good" if p >= 70 else "mid" if p >= 50 else "bad"


@register.filter
def stars(n):
    return "⭐" * int(n or 0)
