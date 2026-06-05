"""Generate styled PDF from notes using ReportLab."""
import io
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY


ACCENT = colors.HexColor("#7C3AED")
ACCENT_LIGHT = colors.HexColor("#EDE9FE")
DARK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
WHITE = colors.white


def generate_pdf(notes_data: dict, video_title: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=22,
        textColor=DARK,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=ACCENT,
        spaceBefore=14,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        borderPad=0,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=DARK,
        spaceBefore=8,
        spaceAfter=3,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=DARK,
        alignment=TA_JUSTIFY,
    )
    muted_style = ParagraphStyle(
        "Muted",
        parent=styles["Normal"],
        fontSize=9,
        textColor=MUTED,
        leading=13,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        leftIndent=10,
        textColor=DARK,
    )

    story = []

    title = notes_data.get("title") or video_title or "Video Notes"
    story.append(Paragraph(title, title_style))

    meta_parts = []
    if notes_data.get("content_type"):
        meta_parts.append(f"Type: {notes_data['content_type'].title()}")
    if notes_data.get("language_detected"):
        meta_parts.append(f"Language: {notes_data['language_detected'].upper()}")
    if meta_parts:
        story.append(Paragraph("  ·  ".join(meta_parts), muted_style))

    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=10))

    # TL;DR
    if notes_data.get("tldr"):
        story.append(Paragraph("TL;DR", h1_style))
        story.append(Paragraph(notes_data["tldr"], body_style))
        story.append(Spacer(1, 8))

    # Main topics
    if notes_data.get("main_topics"):
        story.append(Paragraph("Main Topics", h1_style))
        items = [ListItem(Paragraph(t, bullet_style), bulletColor=ACCENT) for t in notes_data["main_topics"]]
        story.append(ListFlowable(items, bulletType="bullet", start="•"))
        story.append(Spacer(1, 8))

    # Detailed notes
    if notes_data.get("detailed_notes"):
        story.append(Paragraph("Detailed Notes", h1_style))
        _render_markdown_lite(notes_data["detailed_notes"], story, body_style, h2_style, bullet_style)
        story.append(Spacer(1, 8))

    # Key concepts
    if notes_data.get("key_concepts"):
        story.append(Paragraph("Key Concepts", h1_style))
        for kc in notes_data["key_concepts"]:
            if isinstance(kc, dict):
                concept = kc.get("concept", "")
                explanation = kc.get("explanation", "")
                story.append(Paragraph(f"<b>{concept}</b>", bullet_style))
                story.append(Paragraph(explanation, muted_style))
                story.append(Spacer(1, 4))

    # Key takeaways
    if notes_data.get("key_takeaways"):
        story.append(Paragraph("Key Takeaways", h1_style))
        items = [ListItem(Paragraph(t, bullet_style), bulletColor=ACCENT) for t in notes_data["key_takeaways"]]
        story.append(ListFlowable(items, bulletType="bullet", start="•"))
        story.append(Spacer(1, 8))

    # Visual summary
    if notes_data.get("visual_summary"):
        story.append(Paragraph("Visual Summary", h1_style))
        story.append(Paragraph(notes_data["visual_summary"], body_style))
        story.append(Spacer(1, 8))

    # Scenes
    scenes = notes_data.get("scenes") or notes_data.get("scenes_summary")
    if scenes:
        story.append(Paragraph("Scenes", h1_style))
        for s in scenes:
            if isinstance(s, dict):
                label = s.get("scene_label", "Scene")
                desc = s.get("description", "")
                story.append(Paragraph(f"<b>{label}</b>", h2_style))
                if desc:
                    story.append(Paragraph(desc, muted_style))

    # Confidence notes
    if notes_data.get("confidence_notes"):
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
        story.append(Paragraph("Confidence Notes", muted_style))
        story.append(Paragraph(notes_data["confidence_notes"], muted_style))

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Paragraph("Generated by AI Video Summarizer", muted_style))

    doc.build(story)
    return buf.getvalue()


def _render_markdown_lite(text: str, story: list, body_style, h2_style, bullet_style):
    """Minimal markdown-to-ReportLab renderer for detailed_notes."""
    for line in text.split("\n"):
        line = line.rstrip()
        if line.startswith("## "):
            story.append(Paragraph(line[3:], h2_style))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], h2_style))
        elif line.startswith("### "):
            story.append(Paragraph(f"<b>{line[4:]}</b>", bullet_style))
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph(f"• {line[2:]}", bullet_style))
        elif line.startswith("  - ") or line.startswith("  * "):
            story.append(Paragraph(f"  ◦ {line[4:]}", bullet_style))
        elif line.strip() == "":
            story.append(Spacer(1, 4))
        else:
            # Bold inline
            line = _process_inline(line)
            story.append(Paragraph(line, body_style))


def _process_inline(text: str) -> str:
    """Convert **bold** and `code` to ReportLab XML."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    return text
