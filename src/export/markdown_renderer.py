from __future__ import annotations

from src.core.models import KnowledgeDoc
from src.markdown.renderer import render_course_markdown


def render_designbrain_markdown(doc: KnowledgeDoc) -> str:
    """Backward-compatible export API → DesignBrain markdown renderer."""
    return render_course_markdown(doc)
