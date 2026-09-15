from __future__ import annotations

from typing import Iterable


def build_context_block(results: Iterable[dict]) -> str:
    blocks = []
    for index, item in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[S{index}] {item['transcript_title']}",
                    f"Guest: {item.get('guest') or 'Unknown'}",
                    f"Publish date: {item.get('publish_date') or 'Unknown'}",
                    f"Source path: {item['source_path']}",
                    f"YouTube: {item.get('youtube_url') or 'Unknown'}",
                    "Transcript excerpt:",
                    item["text"],
                ]
            )
        )
    return "\n\n".join(blocks)


def qa_system_prompt() -> str:
    return (
        "You are The Lenny Growth Assistant, an internal research assistant for product and growth teams. "
        "Answer ONLY from the transcript evidence provided. Be explicit about uncertainty. "
        "Never fabricate quotes, numbers, or episode details. "
        "If the evidence is weak or incomplete, say that plainly and ask a clarifying follow-up when useful. "
        "Use concise markdown with bullets when it improves clarity. "
        "Cite transcript excerpts inline with source markers like [S1] and [S2]."
    )


def qa_user_prompt(question: str, conversation_context: str, retrieval_context: str) -> str:
    return f"""
Conversation so far:
{conversation_context}

Retrieved transcript evidence:
{retrieval_context}

User question:
{question}

Respond with:
1. A direct answer grounded in the evidence
2. Key supporting bullets
3. A short 'What the transcripts do not establish' note if relevant
""".strip()


def ship30_system_prompt() -> str:
    return (
        "You are a writing skill inside The Lenny Growth Assistant. "
        "Produce a Ship 30 for 30-style essay with these encoded principles: "
        "start with a sharp hook, move through one clear narrative arc, favor short paragraphs, "
        "use skimmable headings and bullets, selectively bold only the highest-signal phrases, "
        "translate ideas into one practical takeaway, and ground every major claim in the provided sources. "
        "Output MUST contain an <answer> block followed by one <artifact> block. "
        "The artifact must be markdown and roughly 1,100 to 1,300 words. "
        "Do not mention Ship 30 unless the user asked for it explicitly. "
        "Close with a brief sources section listing the cited episodes."
    )


def ship30_user_prompt(question: str, conversation_context: str, retrieval_context: str) -> str:
    return f"""
Conversation so far:
{conversation_context}

Retrieved transcript evidence:
{retrieval_context}

Request:
{question}

Return exactly this structure:
<answer>
A 2-4 sentence note explaining the essay draft and its grounding.
</answer>
<artifact type="markdown" title="Grounded Ship 30 Essay">
# Compelling title
...
</artifact>
""".strip()


def artifact_system_prompt() -> str:
    return (
        "You generate artifacts for The Lenny Growth Assistant. "
        "Use the conversation and transcript evidence to produce either markdown or pure HTML/CSS. "
        "Treat the artifact as something rendered in-app, so keep it self-contained and readable. "
        "No JavaScript. No external scripts. No forms. No iframes. "
        "Output MUST contain an <answer> block followed by one <artifact> block."
    )


def artifact_user_prompt(
    question: str, conversation_context: str, retrieval_context: str, artifact_type: str
) -> str:
    title = "Grounded Markdown Artifact" if artifact_type == "markdown" else "Grounded HTML Artifact"
    artifact_hint = (
        "Use markdown with headings, bullets, callouts, and tables when useful."
        if artifact_type == "markdown"
        else "Return complete HTML and CSS inside one document. Put styles in a <style> tag. Do not use scripts."
    )
    return f"""
Conversation so far:
{conversation_context}

Retrieved transcript evidence:
{retrieval_context}

Request:
{question}

Generate a {artifact_type} artifact. {artifact_hint}

Return exactly this structure:
<answer>
A short note explaining what you created and how it is grounded.
</answer>
<artifact type="{artifact_type}" title="{title}">
...
</artifact>
""".strip()
