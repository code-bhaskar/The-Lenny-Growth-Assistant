from __future__ import annotations

import html
import re
from dataclasses import dataclass

import bleach
import markdown
from bs4 import BeautifulSoup

from app.core.config import get_settings


@dataclass
class ArtifactPayload:
    title: str
    type: str
    content: str
    sanitized_content: str
    render_mode: str


class ArtifactService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._markdown = markdown.Markdown(extensions=["extra", "tables", "fenced_code", "sane_lists"])

    def create(self, artifact_type: str, title: str, content: str) -> ArtifactPayload:
        if artifact_type == "html":
            return self.create_html(title, content)
        return self.create_markdown(title, content)

    def create_markdown(self, title: str, content: str) -> ArtifactPayload:
        trimmed = content[: self.settings.artifact_max_chars]
        rendered = self._markdown.convert(trimmed)
        self._markdown.reset()
        sanitized = bleach.clean(
            rendered,
            tags=[
                "a",
                "abbr",
                "b",
                "blockquote",
                "br",
                "code",
                "em",
                "h1",
                "h2",
                "h3",
                "h4",
                "hr",
                "i",
                "li",
                "ol",
                "p",
                "pre",
                "strong",
                "table",
                "thead",
                "tbody",
                "tr",
                "th",
                "td",
                "ul",
            ],
            attributes={"a": ["href", "title", "target", "rel"]},
            strip=True,
        )
        return ArtifactPayload(
            title=title or "Markdown artifact",
            type="markdown",
            content=trimmed,
            sanitized_content=sanitized,
            render_mode="markdown",
        )

    def create_html(self, title: str, content: str) -> ArtifactPayload:
        trimmed = content[: self.settings.artifact_max_chars]
        return ArtifactPayload(
            title=title or "HTML artifact",
            type="html",
            content=trimmed,
            sanitized_content=self._sanitize_html(trimmed),
            render_mode="html",
        )

    def _sanitize_html(self, raw_html: str) -> str:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup.find_all(["script", "iframe", "object", "embed", "form", "link", "meta"]):
            tag.decompose()
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr, value in attrs.items():
                attr_name = attr.lower()
                joined = " ".join(value) if isinstance(value, list) else str(value)
                if attr_name.startswith("on"):
                    del tag.attrs[attr]
                elif attr_name in {"src", "href"} and re.match(r"(?i)\s*javascript:", joined):
                    del tag.attrs[attr]
                elif attr_name == "style" and "expression(" in joined.lower():
                    del tag.attrs[attr]
        body = str(soup)
        csp = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; "
            "font-src https: data:; media-src https: data:; frame-ancestors 'none';"
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta http-equiv='Content-Security-Policy' content=\"{html.escape(csp, quote=True)}\">"
            "<style>body{font-family:Inter,Arial,sans-serif;margin:16px;color:#111827;background:#fff;}"
            "*{box-sizing:border-box;}table{border-collapse:collapse;width:100%;}"
            "th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;}"
            "pre{white-space:pre-wrap;overflow:auto;background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;}"
            "code{font-family:ui-monospace,SFMono-Regular,monospace;}</style></head>"
            f"<body>{body}</body></html>"
        )
