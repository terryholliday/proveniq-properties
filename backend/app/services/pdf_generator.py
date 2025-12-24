"""
PDF Generator Service for PROVENIQ Properties.

Generates professional PDFs for:
- STR claim packets (Airbnb/VRBO Resolution Center)
- LTR deposit dispute reports
- Inspection certificates
"""

import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class PDFGenerator:
    """Generates professional PDFs for claim packets and reports."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='Title',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a1a2e'),
        ))
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666'),
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#1a1a2e'),
            borderPadding=5,
        ))
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#888888'),
        ))
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
            spaceBefore=20,
        ))
        self.styles.add(ParagraphStyle(
            name='HashCode',
            parent=self.styles['Normal'],
            fontSize=7,
            fontName='Courier',
            textColor=colors.HexColor('#666666'),
        ))
    
    def generate_str_claim_packet(self, claim_data: Dict[str, Any]) -> bytes:
        """
        Generate PDF for STR damage claim (Airbnb/VRBO Resolution Center).
        
        Args:
            claim_data: Claim packet data from bookings router
            
        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )
        
        story = []
        
        # Header
        story.append(Paragraph("PROVENIQ", self.styles['Title']))
        story.append(Paragraph("Short-Term Rental Damage Claim Packet", self.styles['Subtitle']))
        story.append(Spacer(1, 0.25*inch))
        
        # Booking Information
        story.append(Paragraph("BOOKING INFORMATION", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        
        booking_data = [
            ["Guest Name:", claim_data.get("guest_name") or "N/A"],
            ["Check-In:", str(claim_data.get("check_in_date", "N/A"))],
            ["Check-Out:", str(claim_data.get("check_out_date", "N/A"))],
            ["Booking ID:", str(claim_data.get("booking_id", "N/A"))],
        ]
        
        booking_table = Table(booking_data, colWidths=[2*inch, 4.5*inch])
        booking_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(booking_table)
        story.append(Spacer(1, 0.25*inch))
        
        # Inspection Summary
        story.append(Paragraph("INSPECTION RECORDS", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        
        inspection_data = [
            ["", "Pre-Stay", "Post-Stay"],
            ["Inspection ID:", 
             str(claim_data.get("pre_stay_inspection_id", "N/A"))[:8] + "...",
             str(claim_data.get("post_stay_inspection_id", "N/A"))[:8] + "..."],
            ["Signed At:", 
             self._format_datetime(claim_data.get("pre_stay_signed_at")),
             self._format_datetime(claim_data.get("post_stay_signed_at"))],
            ["Content Hash:", 
             (claim_data.get("pre_stay_content_hash") or "N/A")[:16] + "...",
             (claim_data.get("post_stay_content_hash") or "N/A")[:16] + "..."],
        ]
        
        insp_table = Table(inspection_data, colWidths=[1.5*inch, 2.5*inch, 2.5*inch])
        insp_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(insp_table)
        story.append(Spacer(1, 0.25*inch))
        
        # Damage Summary
        story.append(Paragraph("DAMAGE SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        
        diff_summary = claim_data.get("diff_summary", [])
        
        if diff_summary:
            damage_data = [["Room", "Item", "Before", "After", "Est. Cost"]]
            
            for item in diff_summary:
                damage_data.append([
                    item.get("room_name", "N/A"),
                    item.get("item_name", "N/A"),
                    str(item.get("pre_condition", "-")),
                    str(item.get("post_condition", "-")),
                    f"${item.get('estimated_repair_cents', 0) / 100:.2f}",
                ])
            
            damage_table = Table(damage_data, colWidths=[1.3*inch, 2*inch, 0.8*inch, 0.8*inch, 1*inch])
            damage_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ]))
            story.append(damage_table)
        else:
            story.append(Paragraph("No damage items found.", self.styles['Normal']))
        
        story.append(Spacer(1, 0.25*inch))
        
        # Cost Summary
        story.append(Paragraph("COST ESTIMATE", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        
        total_cents = claim_data.get("total_estimated_repair_cents", 0)
        total_items = claim_data.get("total_items", 0)
        damaged_items = claim_data.get("damaged_items", 0)
        
        cost_data = [
            ["Total Items Inspected:", str(total_items)],
            ["Items with Damage:", str(damaged_items)],
            ["Total Estimated Repair:", f"${total_cents / 100:.2f}"],
        ]
        
        cost_table = Table(cost_data, colWidths=[3*inch, 3*inch])
        cost_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1a1a2e')),
        ]))
        story.append(cost_table)
        story.append(Spacer(1, 0.25*inch))
        
        # Narrative
        story.append(Paragraph("CLAIM NARRATIVE", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Paragraph(claim_data.get("narrative", "No narrative provided."), self.styles['Normal']))
        story.append(Spacer(1, 0.25*inch))
        
        # Evidence Hashes
        evidence_hashes = claim_data.get("evidence_hash_list", [])
        if evidence_hashes:
            story.append(Paragraph("EVIDENCE INTEGRITY", self.styles['SectionHeader']))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
            story.append(Paragraph(
                f"{len(evidence_hashes)} evidence files with SHA-256 hashes attached.",
                self.styles['Normal']
            ))
            
            # Show first few hashes
            for ev in evidence_hashes[:5]:
                story.append(Paragraph(
                    f"• {ev.get('item', 'Unknown')}: {ev.get('file_hash', 'N/A')[:32]}...",
                    self.styles['HashCode']
                ))
            if len(evidence_hashes) > 5:
                story.append(Paragraph(
                    f"... and {len(evidence_hashes) - 5} more evidence files",
                    self.styles['HashCode']
                ))
        
        # Disclaimer
        story.append(Spacer(1, 0.5*inch))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Paragraph(
            claim_data.get("disclaimer", 
                "This is a non-binding advisory estimate. Actual costs may vary. "
                "Evidence hashes provided for verification."),
            self.styles['Disclaimer']
        ))
        story.append(Paragraph(
            f"Generated by PROVENIQ Properties on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Disclaimer']
        ))
        
        doc.build(story)
        buffer.seek(0)
        return buffer.read()
    
    def _format_datetime(self, dt: Any) -> str:
        """Format datetime for display."""
        if dt is None:
            return "N/A"
        if isinstance(dt, str):
            return dt[:19].replace("T", " ")
        if hasattr(dt, 'strftime'):
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(dt)


def get_pdf_generator() -> PDFGenerator:
    """Get PDF generator instance."""
    return PDFGenerator()
