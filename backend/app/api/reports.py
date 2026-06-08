"""
Report API routes — view and download research reports.
"""

from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.report import ReportResponse, SourceResponse
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research/{session_id}", tags=["Reports"])


@router.get("/report", response_model=ReportResponse)
async def get_report(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest report for a research session."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")

    report = await service.get_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet available")

    return ReportResponse.model_validate(report)


@router.get("/report/download")
async def download_report_pdf(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the report as a PDF."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")

    report = await service.get_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet available")

    # Generate PDF using fpdf2
    from fpdf import FPDF

    def clean_pdf_text(text: str) -> str:
        if not text:
            return ""
        # Replace common non-latin-1 characters
        replacements = {
            "\u2014": " - ",  # em-dash
            "\u2013": " - ",  # en-dash
            "\u201c": '"',    # smart open double quote
            "\u201d": '"',    # smart close double quote
            "\u2018": "'",    # smart open single quote
            "\u2019": "'",    # smart close single quote
            "\u2022": "*",    # bullet point
            "\u2026": "...",  # ellipsis
        }
        for orig, rep in replacements.items():
            text = text.replace(orig, rep)
        # Encode to latin-1 and ignore any remaining unsupported characters to prevent crashes
        return text.encode("latin-1", "ignore").decode("latin-1")

    class PDFReport(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(120, 120, 120)
                self.cell(0, 8, "Agentic AI Research Platform - Research Report", align="R", ln=True)
                self.ln(2)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title - wrapped via multi_cell to handle long titles cleanly
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 41, 59)  # Slate 800
    title_text = clean_pdf_text(session.title or "Research Report")
    pdf.multi_cell(0, 9, title_text, align="C")
    pdf.ln(3)

    # Confidence Score & Metadata
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)  # Slate 500
    score_text = clean_pdf_text(f"Confidence Score: {report.confidence_score:.0%}  |  Revision: {report.revision_number}")
    pdf.cell(0, 6, score_text, ln=True, align="C")
    
    # Decorative Divider Line
    pdf.ln(4)
    pdf.set_draw_color(226, 232, 240)  # Slate 200
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)

    # Executive Summary
    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(51, 65, 85)
    if report.executive_summary:
        clean_text = report.executive_summary.replace("**", "").replace("##", "").replace("#", "")
        pdf.multi_cell(0, 5.5, clean_pdf_text(clean_text))
    pdf.ln(4)

    # Key Insights
    if report.key_insights:
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Key Insights", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        for i, insight in enumerate(report.key_insights, 1):
            if isinstance(insight, dict):
                text = f"{i}. {insight.get('insight', str(insight))}"
            else:
                text = f"{i}. {insight}"
            pdf.multi_cell(0, 5.5, clean_pdf_text(text))
            pdf.ln(1)
        pdf.ln(3)

    # Detailed Report
    if report.detailed_report:
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Detailed Report", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        clean = report.detailed_report.replace("**", "").replace("##", "").replace("# ", "")
        for para in clean.split("\n\n"):
            stripped = para.strip()
            if stripped:
                pdf.multi_cell(0, 5.5, clean_pdf_text(stripped))
                pdf.ln(2.5)

    # Recommendations
    if report.recommendations:
        pdf.ln(3)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Recommendations", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        for i, rec in enumerate(report.recommendations, 1):
            if isinstance(rec, dict):
                text = f"{i}. {rec.get('recommendation', str(rec))}"
                if rec.get('priority'):
                    text += f" [Priority: {rec['priority']}]"
            else:
                text = f"{i}. {rec}"
            pdf.multi_cell(0, 5.5, clean_pdf_text(text))
            pdf.ln(1)

    # Risks
    if report.risks:
        pdf.ln(3)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Risks", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)
        for i, risk in enumerate(report.risks, 1):
            if isinstance(risk, dict):
                text = f"{i}. {risk.get('risk', str(risk))}"
                if risk.get('severity'):
                    text += f" [Severity: {risk['severity']}]"
            else:
                text = f"{i}. {risk}"
            pdf.multi_cell(0, 5.5, clean_pdf_text(text))
            pdf.ln(1)

    # Sources
    if report.source_references:
        pdf.ln(3)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Source References", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(71, 85, 105)
        for i, src in enumerate(report.source_references, 1):
            if isinstance(src, dict):
                text = f"[{i}] {src.get('title', 'Unknown Source')} - {src.get('type', '')}"
            else:
                text = f"[{i}] {src}"
            pdf.multi_cell(0, 5, clean_pdf_text(text))
            pdf.ln(0.5)

    # Output PDF to buffer
    pdf_bytes = pdf.output()
    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)

    filename = "research_report.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sources discovered during research."""
    service = ResearchService(db)
    session = await service.get_session(session_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Research session not found")

    sources = await service.get_sources(session_id)
    return [SourceResponse.model_validate(s) for s in sources]
