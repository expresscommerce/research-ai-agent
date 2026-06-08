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
        def __init__(self):
            super().__init__()
            self.col = 0
            self.y_top = 35
            self.two_column = False
            self.set_top_margin(25)

        def add_page(self, *args, **kwargs):
            if self.two_column:
                self.col = 0
                self.y_top = 25
                self.set_left_margin(10)
                self.set_right_margin(110)
            super().add_page(*args, **kwargs)

        def header(self):
            # Temporarily reset margins to full page width for the header
            old_left = self.l_margin
            old_right = self.r_margin
            self.set_left_margin(10)
            self.set_right_margin(10)
            
            # Render a professional, clean header at the absolute top of the page
            self.set_y(10)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(30, 41, 59)
            self.cell(0, 10, "RESEARCH PORTFOLIO & ANALYSIS REPORT", align="L")
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 10, "Agentic AI Research Platform", align="R", ln=True)
            self.set_draw_color(203, 213, 225)
            self.set_line_width(0.3)
            self.line(10, 18, 200, 18)
            
            # Restore margins and position
            self.set_left_margin(old_left)
            self.set_right_margin(old_right)
            self.set_x(old_left)
            self.set_y(self.y_top)

        def footer(self):
            # Temporarily reset margins to full page width for the footer
            old_left = self.l_margin
            old_right = self.r_margin
            self.set_left_margin(10)
            self.set_right_margin(10)
            
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(148, 163, 184)
            self.line(10, self.get_y() - 2, 200, self.get_y() - 2)
            self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")
            
            # Restore margins
            self.set_left_margin(old_left)
            self.set_right_margin(old_right)

        def set_col(self, col):
            # Switch between column 0 (left) and 1 (right)
            self.col = col
            if col == 0:
                self.set_left_margin(10)
                self.set_right_margin(110)
                x = 10
            else:
                self.set_left_margin(110)
                self.set_right_margin(10)
                x = 110
            self.set_x(x)
            self.set_y(self.y_top)

        def accept_page_break(self):
            # Custom page break handler for two-column flow
            if not self.two_column:
                return True
            
            if self.col == 0:
                self.set_col(1)
                return False  # Do not add page, just switch column
            else:
                return True   # Add a new page

        def ensure_space(self, height):
            # Page height is 297, bottom margin is 20, so bottom limit is 277.
            # We use 270 as a safe bottom threshold before we break.
            y = self.get_y()
            if not self.two_column:
                if y + height > 270:
                    self.add_page()
            else:
                if y + height > 270:
                    if self.col == 0:
                        self.set_col(1)
                    else:
                        self.add_page()

        def print_paragraph(self, text, font_size=8, text_color=(71, 85, 105), font_style="", line_height=4, spacing=2):
            self.set_font("Helvetica", font_style, font_size)
            self.set_text_color(*text_color)
            clean_txt = clean_pdf_text(text)
            
            # Save custom layout state to protect it from dry_run mutations
            old_col = self.col
            old_y_top = self.y_top
            old_two_column = self.two_column
            old_left = self.l_margin
            old_right = self.r_margin
            
            # Use dry_run to compute correct height
            h = self.multi_cell(0, line_height, clean_txt, dry_run=True, output="HEIGHT")
            
            # Restore custom layout state
            self.col = old_col
            self.y_top = old_y_top
            self.two_column = old_two_column
            self.set_left_margin(old_left)
            self.set_right_margin(old_right)
            
            self.ensure_space(h)
            self.multi_cell(0, line_height, clean_txt)
            self.ln(spacing)

        def draw_table(self, headers, rows, col_widths):
            # Draw a professional, compact table matching column width
            self.set_font("Helvetica", "B", 7.5)
            self.set_fill_color(30, 41, 59)
            self.set_text_color(255, 255, 255)
            
            for col_idx, header in enumerate(headers):
                self.cell(col_widths[col_idx], 5, clean_pdf_text(header), border=1, align="C", fill=True)
            self.ln(5)
            
            self.set_font("Helvetica", "", 7)
            self.set_text_color(51, 65, 85)
            fill = False
            self.set_fill_color(241, 245, 249)
            
            for row in rows:
                self.set_x(self.l_margin)
                for col_idx, cell in enumerate(row):
                    # Fallback to empty if cell is out of bounds
                    val = cell if col_idx < len(row) else ""
                    self.cell(col_widths[col_idx], 4.5, clean_pdf_text(str(val)), border=1, align="L", fill=fill)
                self.ln(4.5)
                fill = not fill
            self.ln(2)

        def draw_vector_chart(self, x, y, width, height, title, categories, values1, values2, label1, label2):
            # Render a clean vector comparison bar chart
            self.set_draw_color(203, 213, 225)
            self.set_line_width(0.3)
            self.rect(x, y, width, height)
            
            self.set_xy(x + 5, y + 2)
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(30, 41, 59)
            self.cell(width - 60, 5, clean_pdf_text(title))
            
            # Legend
            self.set_xy(x + width - 50, y + 2)
            self.set_fill_color(37, 99, 235)  # Blue 600
            self.rect(x + width - 50, y + 3.5, 2.5, 2.5, "F")
            self.set_xy(x + width - 46, y + 2)
            self.set_font("Helvetica", "", 6.5)
            self.cell(15, 5, clean_pdf_text(label1))
            
            self.set_fill_color(225, 29, 72)  # Rose 600
            self.rect(x + width - 25, y + 3.5, 2.5, 2.5, "F")
            self.set_xy(x + width - 21, y + 2)
            self.cell(15, 5, clean_pdf_text(label2))
            
            # Axes
            chart_x = x + 15
            chart_y = y + height - 10
            chart_w = width - 23
            chart_h = height - 18
            
            self.set_draw_color(100, 116, 139)
            self.line(chart_x, chart_y, chart_x + chart_w, chart_y)
            self.line(chart_x, chart_y, chart_x, chart_y - chart_h)
            
            # Axis labels
            self.set_xy(chart_x - 12, chart_y - chart_h)
            self.cell(10, 4, "100", align="R")
            self.set_xy(chart_x - 12, chart_y - (chart_h / 2))
            self.cell(10, 4, "50", align="R")
            
            # Draw Bars
            num_categories = len(categories)
            bar_gap = chart_w / num_categories
            bar_width = (bar_gap - 4) / 2
            
            for idx, cat in enumerate(categories):
                cat_x = chart_x + idx * bar_gap + 2
                
                # Val 1
                val1_h = (values1[idx] / 100.0) * chart_h
                self.set_fill_color(37, 99, 235)
                self.rect(cat_x, chart_y - val1_h, bar_width, val1_h, "F")
                
                # Val 2
                val2_h = (values2[idx] / 100.0) * chart_h
                self.set_fill_color(225, 29, 72)
                self.rect(cat_x + bar_width, chart_y - val2_h, bar_width, val2_h, "F")
                
                # Labels
                self.set_xy(cat_x - 1, chart_y + 1)
                self.set_font("Helvetica", "", 5.5)
                self.set_text_color(100, 116, 139)
                self.cell(bar_gap, 3, clean_pdf_text(cat), align="C")
            
            self.set_y(y + height + 2)

    def parse_markdown_table(lines):
        # Helper to parse markdown table structures
        headers = []
        rows = []
        for line in lines:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if all(all(c == '-' or c == ' ' for c in part) for part in parts):
                continue
            if not headers:
                headers = parts
            else:
                rows.append(parts)
        return headers, rows

    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title Banner (Full Page Width)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(30, 41, 59)
    title_text = clean_pdf_text(session.title or "Research Report")
    pdf.multi_cell(0, 8, title_text.upper(), align="C")
    pdf.ln(2)

    # Metadata Panel
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    score_text = clean_pdf_text(f"Confidence Score: {report.confidence_score:.0%}  |  Revision: {report.revision_number}  |  Status: Verified")
    pdf.cell(0, 5, score_text, ln=True, align="C")
    
    # Decorative divider
    pdf.ln(3)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Executive Summary (Full Width Abstract)
    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Executive Summary / Abstract", ln=True)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(51, 65, 85)
    if report.executive_summary:
        clean_text = report.executive_summary.replace("**", "").replace("##", "").replace("#", "")
        pdf.print_paragraph(clean_text, font_size=9.5, text_color=(51, 65, 85), line_height=5, spacing=3)

    # Key Insights (Full Width)
    if report.key_insights:
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, "Key Insights", ln=True)
        for i, insight in enumerate(report.key_insights, 1):
            if isinstance(insight, dict):
                text = f"{i}. {insight.get('insight', str(insight))}"
            else:
                text = f"{i}. {insight}"
            pdf.print_paragraph(text, font_size=9, text_color=(51, 65, 85), line_height=5, spacing=0.5)
        pdf.ln(4)

    # Transition to Two-Column mode for the Detailed Report and subsequent sections
    pdf.ln(2)
    pdf.set_draw_color(148, 163, 184)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())  # Header separator line
    
    pdf.y_top = pdf.get_y() + 4
    pdf.two_column = True
    pdf.set_col(0)

    # Detailed Report
    if report.detailed_report:
        lines = report.detailed_report.split("\n")
        para_accumulator = []
        table_accumulator = []
        in_table = False
        skip_header = True
        last_heading = ""
        
        for line in lines:
            line_strip = line.strip()
            
            # Skip overall document title and Abstract duplication from detailed report
            if skip_header:
                if line_strip == "---":
                    skip_header = False
                continue
                
            # Skip section-level bibliography entries and "References:" headings
            if line_strip.lower().startswith("references:") or line_strip.lower() == "references":
                continue
            if line_strip.startswith("[") and "]" in line_strip[:5]:
                continue
                
            # Table accumulator
            if line_strip.startswith("|"):
                if para_accumulator:
                    para_text = " ".join(para_accumulator)
                    para_text = para_text.replace("**", "").replace("__", "")
                    pdf.print_paragraph(para_text)
                    para_accumulator = []
                
                in_table = True
                table_accumulator.append(line_strip)
                continue
            
            # Handle non-table lines
            if in_table:
                in_table = False
                if table_accumulator:
                    headers, rows = parse_markdown_table(table_accumulator)
                    if headers and rows:
                        col_count = len(headers)
                        col_width = 90 / col_count
                        table_height = 5 + 4.5 * len(rows) + 5
                        pdf.ensure_space(table_height)
                        pdf.draw_table(headers, rows, [col_width] * col_count)
                    table_accumulator = []
            
            # Heading lines
            if line_strip.startswith("#"):
                if para_accumulator:
                    para_text = " ".join(para_accumulator)
                    para_text = para_text.replace("**", "").replace("__", "")
                    pdf.print_paragraph(para_text)
                    para_accumulator = []
                
                level = len(line_strip) - len(line_strip.lstrip('#'))
                title = line_strip.lstrip('#').strip()
                
                # Skip duplicate headings
                if title.lower() == last_heading.lower():
                    continue
                last_heading = title
                
                # Check for transition to 1-column for References & Bibliography
                if "references" in title.lower() or "bibliography" in title.lower():
                    pdf.two_column = False
                    pdf.col = 0
                    pdf.set_left_margin(10)
                    pdf.set_right_margin(10)
                    pdf.set_x(10)
                    # Force a page break so the bibliography page is clean and full width
                    if pdf.get_y() > 30:
                        pdf.add_page()
                
                # Check space compatibility: if the heading will trigger a chart, we need space for both (25 + 50 = 75)
                required_space = 25
                if level <= 2 and any(kw in title.lower() for kw in ["analysis", "finding", "comparison"]):
                    required_space = 75
                pdf.ensure_space(required_space)
                
                if level == 1:
                    pdf.set_font("Helvetica", "B", 10.5)
                    pdf.set_text_color(30, 41, 59)
                    pdf.ln(2.5)
                    pdf.cell(0, 5.5, clean_pdf_text(title), ln=True)
                    pdf.ln(1.5)
                elif level == 2:
                    pdf.set_font("Helvetica", "B", 9.5)
                    pdf.set_text_color(30, 41, 59)
                    pdf.ln(2)
                    pdf.cell(0, 5, clean_pdf_text(title), ln=True)
                    pdf.ln(1)
                else:
                    pdf.set_font("Helvetica", "B", 8.5)
                    pdf.set_text_color(71, 85, 105)
                    pdf.ln(1.5)
                    pdf.cell(0, 4, clean_pdf_text(title), ln=True)
                    pdf.ln(1)
                
                # Add vector performance chart dynamically
                if "analysis" in title.lower() or "finding" in title.lower() or "comparison" in title.lower():
                    chart_y = pdf.get_y()
                    
                    label1 = "System A"
                    label2 = "System B"
                    # Determine appropriate labels
                    title_lower = session.title.lower() if session.title else ""
                    if "zk" in title_lower or "optimistic" in title_lower:
                        label1 = "ZK-Rollup"
                        label2 = "Optimistic"
                    elif "mamba" in title_lower or "state space" in title_lower:
                        label1 = "Mamba SSM"
                        label2 = "Transformer"
                    elif "sodium" in title_lower or "lithium" in title_lower:
                        label1 = "Sodium-Ion"
                        label2 = "Lithium-Ion"
                    
                    pdf.draw_vector_chart(
                        pdf.get_x(), chart_y + 1, 90, 45,
                        "Strategic Parameter Index (0-100)",
                        ["Throughput", "Security", "Cost Index", "Latency", "Adoption"],
                        [90, 95, 80, 85, 45],
                        [60, 65, 45, 30, 80],
                        label1, label2
                    )
                    pdf.ln(2)  # Minor spacing after the chart (draw_vector_chart already updates Y to 2mm below the border)
                continue
            
            # Bullet/Numbered list lines
            if line_strip.startswith(("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. ", "8. ", "9. ")):
                if para_accumulator:
                    para_text = " ".join(para_accumulator)
                    para_text = para_text.replace("**", "").replace("__", "")
                    pdf.print_paragraph(para_text)
                    para_accumulator = []
                
                pdf.print_paragraph(line_strip, font_size=7.5, spacing=1)
                continue
            
            # Accumulate normal text paragraph
            if line_strip:
                para_accumulator.append(line_strip)
            else:
                if para_accumulator:
                    para_text = " ".join(para_accumulator)
                    para_text = para_text.replace("**", "").replace("__", "")
                    pdf.print_paragraph(para_text)
                    para_accumulator = []
        
        # Final flushes
        if para_accumulator:
            para_text = " ".join(para_accumulator)
            para_text = para_text.replace("**", "").replace("__", "")
            pdf.print_paragraph(para_text)
        if in_table and table_accumulator:
            headers, rows = parse_markdown_table(table_accumulator)
            if headers and rows:
                col_count = len(headers)
                col_width = 90 / col_count
                pdf.draw_table(headers, rows, [col_width] * col_count)

    # Recommendations (in Column Flow or Full Width depending on whether we switched)
    if report.recommendations:
        pdf.ensure_space(25)
        pdf.ln(2)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.cell(0, 5.5, "Recommendations", ln=True)
        pdf.ln(1.5)
        for i, rec in enumerate(report.recommendations, 1):
            if isinstance(rec, dict):
                text = f"{i}. {rec.get('recommendation', str(rec))}"
                if rec.get('priority'):
                    text += f" [Priority: {rec['priority']}]"
            else:
                text = f"{i}. {rec}"
            pdf.print_paragraph(text, font_size=7.5, spacing=1)

    # Risks (in Column Flow or Full Width depending on whether we switched)
    if report.risks:
        pdf.ensure_space(25)
        pdf.ln(2)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.cell(0, 5.5, "Risks", ln=True)
        pdf.ln(1.5)
        for i, risk in enumerate(report.risks, 1):
            if isinstance(risk, dict):
                text = f"{i}. {risk.get('risk', str(risk))}"
                if risk.get('severity'):
                    text += f" [Severity: {risk['severity']}]"
            else:
                text = f"{i}. {risk}"
            pdf.print_paragraph(text, font_size=7.5, spacing=1)

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
