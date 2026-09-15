from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RouteDecision:
    route: str
    artifact_type: str | None = None


class RouteClassifier:
    ARTIFACT_WORDS = {"artifact", "markdown", "html", "css", "landing page", "one-pager", "memo"}
    HTML_WORDS = {"html", "css", "landing page", "web page", "microsite"}
    SHIP30_WORDS = {"ship 30", "essay", "post", "linkedin post", "thread", "article"}

    def classify(self, text: str) -> RouteDecision:
        lowered = text.lower()
        if any(term in lowered for term in self.SHIP30_WORDS) and "artifact" not in lowered:
            return RouteDecision(route="ship30", artifact_type="markdown")
        if any(term in lowered for term in self.ARTIFACT_WORDS):
            artifact_type = "html" if any(term in lowered for term in self.HTML_WORDS) else "markdown"
            return RouteDecision(route="artifact", artifact_type=artifact_type)
        return RouteDecision(route="qa")
