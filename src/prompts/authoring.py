SYSTEM = (
    "You are a senior technical writer. You produce clear, concise Markdown documents for Confluence. "
    "Prefer short paragraphs, descriptive headings, and actionable steps. Use fenced code blocks where needed. "
    "Avoid fluff. If the user provides an outline, follow it."
)

OUTLINE_PROMPT = """\
Given:
- Working title: "{title}"
- Audience: {audience}
- Purpose: {purpose}
- Style/tone: {tone}

Produce a concise Markdown outline with 4-8 top-level sections and brief bullets per section.
Only output Markdown (no commentary).
"""

DRAFT_PROMPT = """\
Title: {title}

Audience: {audience}
Purpose: {purpose}
Style/tone: {tone}

Outline:
{outline}

Write the full document in Markdown suitable for Confluence. Use headings, lists, code blocks where helpful.
Keep it practical and skimmable. Do not include front matter. Start with an H1 title.
"""
