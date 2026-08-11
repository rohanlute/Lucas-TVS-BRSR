"""
BRSR-style PDF generator — Emissions Report Only
"""
import os
from io import BytesIO
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from ..models import (
    EmissionScope,
    EmissionCategory,
    EmissionActivity,
    EmissionSource,
    EmissionTransaction,
    EmissionAssignment,
)


# ==========================================================================
# Font setup
# ==========================================================================
FONT_REGULAR = 'Times-Roman'
FONT_BOLD = 'Times-Bold'
FONT_ITALIC = 'Times-Italic'

_GEORGIA_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'fonts'),
    '/usr/share/fonts/truetype/msttcorefonts',
    'C:\\Windows\\Fonts',
]


def _register_georgia_if_available():
    global FONT_REGULAR, FONT_BOLD, FONT_ITALIC
    for folder in _GEORGIA_CANDIDATES:
        reg = os.path.join(folder, 'georgia.ttf')
        bold = os.path.join(folder, 'georgiab.ttf')
        italic = os.path.join(folder, 'georgiai.ttf')
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont('Georgia', reg))
                pdfmetrics.registerFont(TTFont('Georgia-Bold', bold))
                FONT_REGULAR = 'Georgia'
                FONT_BOLD = 'Georgia-Bold'
                if os.path.exists(italic):
                    pdfmetrics.registerFont(TTFont('Georgia-Italic', italic))
                    FONT_ITALIC = 'Georgia-Italic'
                return True
            except Exception:
                continue
    return False


_register_georgia_if_available()


class BRSRPDFGenerator:
    """Generate a BRSR-styled PDF report with emission data only."""

    def __init__(
        self,
        assignment_id: Optional[int] = None,
        company_id: Optional[int] = None,
        plant_id: Optional[int] = None,
        financial_year_id: Optional[int] = None,
        financial_month_id: Optional[int] = None,
        company_name: str = None,
        cin: str = None,
        report_year: str = None,
        user=None,
    ):
        self.assignment_id = assignment_id
        self.company_id = company_id
        self.plant_id = plant_id
        self.financial_year_id = financial_year_id
        self.financial_month_id = financial_month_id
        self.user = user
        self._report_data = {}

        if company_name:
            self.company_name = company_name
            self.cin = cin or self._get_cin_only_from_user()
        else:
            self.company_name, self.cin = self._get_company_details_from_user()

        if not self.cin:
            self.cin = "N/A"

        if report_year is None:
            from apps.organizations.models import FinancialYear
            today = timezone.now().date()
            current_fy = FinancialYear.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
            if current_fy:
                self.report_year = current_fy.financial_year
            else:
                self.report_year = "2024-25"
        else:
            self.report_year = report_year

        self.buffer = BytesIO()

        self.colors = {
            'navy': colors.HexColor('#012060'),
            'navy_light': colors.HexColor('#0C2D6B'),
            'gold': colors.HexColor('#FFB600'),
            'gold_text': colors.HexColor('#B8860B'),
            'table_header': colors.HexColor('#012060'),
            'table_header_text': colors.HexColor('#ffffff'),
            'grid_line': colors.HexColor('#D9A628'),
            'subheader_bg': colors.HexColor('#FFF3D6'),
            'white': colors.HexColor('#ffffff'),
            'black': colors.HexColor('#1a2332'),
            'gray': colors.HexColor('#6b7280'),
            'light_gray': colors.HexColor('#EEF2FA'),
            'scope1': colors.HexColor('#012060'),
            'scope2': colors.HexColor('#0C2D6B'),
            'scope3': colors.HexColor('#B8860B'),
        }

    def _get_company_details_from_user(self) -> Tuple[str, str]:
        from apps.accounts.models import User
        from apps.companies.models import Company

        default_name, default_cin = "Lucas TVS Ltd", "N/A"

        if not self.user:
            return default_name, default_cin

        try:
            if hasattr(self.user, 'company') and self.user.company:
                company = self.user.company
                return company.company_name, getattr(company, 'cin', None) or default_cin

            if hasattr(self.user, 'company_id') and self.user.company_id:
                try:
                    company = Company.objects.get(id=self.user.company_id)
                    return company.company_name, getattr(company, 'cin', None) or default_cin
                except Company.DoesNotExist:
                    pass

            user_id = getattr(self.user, 'id', None)
            if user_id:
                try:
                    db_user = User.objects.select_related('company').get(id=user_id)
                    if db_user.company:
                        return db_user.company.company_name, getattr(db_user.company, 'cin', None) or default_cin
                except User.DoesNotExist:
                    pass

        except Exception as e:
            print(f"DEBUG: Error getting company details: {e}")

        return default_name, default_cin

    def _get_cin_only_from_user(self) -> str:
        _, cin = self._get_company_details_from_user()
        return cin

    def generate(self) -> BytesIO:
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=48,
            bottomMargin=54,
            title=f"Emissions Report - {self.company_name}",
        )

        data = self._get_report_data()
        self._report_data = data

        story = []

        # Page 1 — Cover
        story.append(Spacer(1, 1))
        story.append(PageBreak())

        # Page 2 — Scope-wise GHG Emissions Summary
        story.extend(self._get_scope_summary_page(data))
        story.append(PageBreak())

        # Page 3+ — Scope breakdown (each scope and category starts on new page)
        story.extend(self._get_scope_breakdown(data))

        doc.build(
            story,
            onFirstPage=self._draw_cover_page,
            onLaterPages=self._draw_page_furniture,
        )

        self.buffer.seek(0)
        return self.buffer

    def _draw_cover_page(self, canvas, doc):
        """Draw the cover page with Emission Report in BRSR style."""
        canvas.saveState()
        width, height = A4

        data = self._report_data or {}

        # ========== THICK WHITE BORDER ==========
        border_margin = 12
        border_thickness = 4
        
        # White background (entire page)
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        
        # Navy content area with thick white border
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.rect(
            border_margin + border_thickness, 
            border_margin + border_thickness,
            width - 2 * (border_margin + border_thickness), 
            height - 2 * (border_margin + border_thickness),
            fill=1, stroke=0
        )

        # ========== SHIFT THE ENTIRE PANEL TO THE RIGHT ==========
        panel_shift = 80
        
        # ========== GOLD BLOCK (Company Name + Plant Name) ==========
        gold_block_width = width * 0.35
        gold_block_height = height * 0.30  # Increased height to accommodate both names with same font size
        gold_block_x = (width - gold_block_width) / 2 + panel_shift
        gold_block_top = height - border_margin - border_thickness
        
        shifted_gold_center_x = gold_block_x + (gold_block_width / 2)

        canvas.setFillColor(colors.HexColor('#FFB600'))
        canvas.rect(gold_block_x, gold_block_top - gold_block_height,
                    gold_block_width, gold_block_height, fill=1, stroke=0)

        # Company Name - Font size 18
        canvas.setFont(FONT_BOLD, 18)
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.drawCentredString(shifted_gold_center_x, gold_block_top - gold_block_height * 0.30, self.company_name)

        # Plant Name - Same font size as company name (18)
        plant_name = data.get('plant_name', '')
        if not plant_name or plant_name == "All Plants":
            plant_name = "All Plants"
        
        # Calculate available width for plant name (gold block width minus padding)
        available_width = gold_block_width - 20  # 10 points padding on each side
        
        # Wrap text into lines with font size 18
        wrapped_lines = self._wrap_text(plant_name, available_width, FONT_BOLD, 19)
        
        # Calculate starting Y position for plant name (below company name)
        start_y = gold_block_top - gold_block_height * 0.55
        line_height = 22  # Space between lines for larger font
        
        canvas.setFont(FONT_BOLD, 19)  # Same font size as company name
        canvas.setFillColor(colors.HexColor('#012060'))
        
        # Draw each line
        for i, line in enumerate(wrapped_lines):
            y_pos = start_y - (i * line_height)
            canvas.drawCentredString(shifted_gold_center_x, y_pos, line)

        # ========== WHITE BLOCK ==========
        white_block_width = gold_block_width
        white_block_height = height * 0.35
        white_block_x = gold_block_x
        white_block_y = gold_block_top - gold_block_height

        shifted_white_center_x = white_block_x + (white_block_width / 2)

        canvas.setFillColor(colors.white)
        canvas.rect(white_block_x, white_block_y - white_block_height,
                    white_block_width, white_block_height, fill=1, stroke=0)

        title_start_y = white_block_y - 35
        title_line_height = 30

        # "Emission"
        canvas.setFont(FONT_BOLD, 22)
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.drawCentredString(shifted_white_center_x, title_start_y, "Emission")

        # "Report"
        report_y = title_start_y - title_line_height
        canvas.setFont(FONT_BOLD, 22)
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.drawCentredString(shifted_white_center_x, report_y, "Report")

        # "FY"
        fy_y = report_y - title_line_height - 5
        canvas.setFont(FONT_BOLD, 18)
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.drawCentredString(shifted_white_center_x, fy_y, "FY")

        # Year
        year_y = fy_y - title_line_height + 5
        canvas.setFont(FONT_BOLD, 22)
        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.drawCentredString(shifted_white_center_x, year_y, data.get('report_year', self.report_year))

        # ========== GOLD STRIP ==========
        divider_y = white_block_y - white_block_height
        canvas.setFillColor(colors.HexColor('#FFB600'))
        canvas.rect(white_block_x, divider_y - 5, white_block_width, 5, fill=1, stroke=0)

        # ========== WHITE SECTION + THICK DIVIDER LINE ==========
        extra_white_height = height * 0.035
        thick_line_height = 4

        extra_white_top = divider_y - 5
        extra_white_bottom = extra_white_top - extra_white_height

        canvas.setFillColor(colors.white)
        canvas.rect(white_block_x, extra_white_bottom,
                    white_block_width, extra_white_height, fill=1, stroke=0)

        canvas.setFillColor(colors.HexColor('#012060'))
        canvas.rect(white_block_x, extra_white_bottom - thick_line_height,
                    white_block_width, thick_line_height, fill=1, stroke=0)

        canvas.restoreState()

    def _wrap_text(self, text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
        """Wrap text into multiple lines based on available width."""
        if not text:
            return [""]
        
        # Get the font metrics
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.pdfmetrics import stringWidth
        
        words = text.split(' ')
        lines = []
        current_line = []
        current_width = 0
        
        # Approximate space width
        space_width = stringWidth(' ', font_name, font_size)
        
        for word in words:
            word_width = stringWidth(word, font_name, font_size)
            
            # Check if adding this word exceeds max width
            if current_width + word_width + (space_width if current_line else 0) <= max_width:
                current_line.append(word)
                current_width += word_width + (space_width if len(current_line) > 1 else 0)
            else:
                # If current line has content, save it and start new line
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_width = word_width
                else:
                    # Single word is longer than max width - force it
                    lines.append(word)
                    current_line = []
                    current_width = 0
        
        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
        
    def _draw_page_furniture(self, canvas, doc):
        """Draw black border, header with BRSR FY on right, and page number on right."""
        canvas.saveState()
        width, height = A4

        # ========== BLACK BORDER ==========
        border_margin = 10
        border_thickness = 1.5
        
        # Draw black border
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(border_thickness)
        canvas.rect(
            border_margin, 
            border_margin,
            width - 2 * border_margin, 
            height - 2 * border_margin,
            fill=0, stroke=1
        )

        # ========== HEADER - BRSR FY on RIGHT CORNER ==========
        # Draw line below header
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.5)
        canvas.line(30, height - 55, width - 30, height - 55)
        
        # Header text: "BRSR FY 2024-25" - Aligned to RIGHT
        canvas.setFont(FONT_BOLD, 11)
        canvas.setFillColor(colors.HexColor('#1a2332'))
        # Draw on the right side
        canvas.drawRightString(width - 30, height - 42, f"Emission {self.report_year}")

        # ========== FOOTER - Page Number on RIGHT CORNER ==========
        canvas.setFont('Helvetica', 10)
        canvas.setFillColor(colors.black)
        # Draw page number on the right side
        canvas.drawRightString(width - 30, 20, str(doc.page))

        canvas.restoreState()

    def _clean_text(self, text: str) -> str:
        if not text:
            return text
        replacements = {
            '₆': '6', '₄': '4', '₂': '2', '₃': '3', '₁': '1', '₅': '5',
            '₇': '7', '₈': '8', '₉': '9', '₀': '0',
            '■': '', '●': '', '•': '',
            '—': '-', '–': '-', '…': '...',
            '”': '"', '“': '"', '’': "'", '‘': "'",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _get_report_data(self) -> Dict:
        filter_kwargs = {}
        if self.assignment_id:
            filter_kwargs['assignment_id'] = self.assignment_id
        if self.company_id:
            filter_kwargs['company_id'] = self.company_id
        if self.plant_id:
            filter_kwargs['plant_id'] = self.plant_id
        if self.financial_year_id:
            filter_kwargs['financial_year_id'] = self.financial_year_id
        if self.financial_month_id:
            filter_kwargs['financial_month_id'] = self.financial_month_id

        plant_name = "All Plants"
        if self.plant_id:
            from apps.organizations.models import Plant
            try:
                plant = Plant.objects.get(id=self.plant_id)
                plant_name = plant.name
            except Plant.DoesNotExist:
                pass

        scopes_data = []
        scopes = EmissionScope.objects.filter(is_active=True).order_by('display_order')
        total_emissions = Decimal('0')
        scope_totals = {}

        for scope in scopes:
            scope_data = {
                'id': scope.id,
                'code': scope.code,
                'name': scope.name,
                'description': scope.description,
                'categories': [],
                'total': Decimal('0'),
            }

            categories = EmissionCategory.objects.filter(
                scope=scope, is_active=True
            ).order_by('display_order')

            for category in categories:
                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'activities': [],
                    'total': Decimal('0'),
                }

                activities = EmissionActivity.objects.filter(
                    category=category, is_active=True
                ).order_by('display_order')

                for activity in activities:
                    all_sources = EmissionSource.objects.filter(
                        activity=activity, is_active=True
                    ).order_by('display_order')

                    transactions = EmissionTransaction.objects.filter(
                        activity_id=activity.id, **filter_kwargs
                    ).select_related('source', 'unit')

                    has_data = transactions.exists()
                    total_quantity = Decimal('0')
                    total_emission_kg = Decimal('0')
                    total_emission_tco2e = Decimal('0')

                    if has_data:
                        total_quantity = transactions.aggregate(
                            total=Sum('quantity')
                        )['total'] or Decimal('0')
                        total_emission_kg = transactions.aggregate(
                            total=Sum('total_emission')
                        )['total'] or Decimal('0')
                        total_emission_tco2e = total_emission_kg / Decimal('1000')

                    sources = []
                    if all_sources.exists():
                        for source in all_sources:
                            source_transactions = transactions.filter(source=source)
                            if source_transactions.exists():
                                source_total_qty = source_transactions.aggregate(
                                    total=Sum('quantity')
                                )['total'] or Decimal('0')
                                source_total_em_kg = source_transactions.aggregate(
                                    total=Sum('total_emission')
                                )['total'] or Decimal('0')
                                source_total_em_tco2e = source_total_em_kg / Decimal('1000')
                                first_trans = source_transactions.first()
                                unit = first_trans.unit.symbol if first_trans and first_trans.unit else ''
                            else:
                                source_total_qty = Decimal('0')
                                source_total_em_kg = Decimal('0')
                                source_total_em_tco2e = Decimal('0')
                                unit = activity.base_unit.symbol if activity.base_unit else ''

                            clean_name = self._clean_text(source.source_name)
                            sources.append({
                                'name': clean_name,
                                'unit': unit,
                                'quantity': source_total_qty,
                                'emission_kg': source_total_em_kg,
                                'emission': source_total_em_tco2e,
                                'has_data': source_transactions.exists(),
                            })
                    else:
                        if has_data:
                            source_groups = transactions.values(
                                'source__source_name', 'unit__symbol'
                            ).annotate(
                                total_qty=Sum('quantity'),
                                total_em=Sum('total_emission')
                            ).order_by('source__display_order')

                            for sg in source_groups:
                                clean_name = self._clean_text(sg.get('source__source_name', 'Unknown'))
                                unit = sg.get('unit__symbol', '')
                                total_em_kg = sg.get('total_em', 0) or Decimal('0')
                                total_em_tco2e = total_em_kg / Decimal('1000')
                                sources.append({
                                    'name': clean_name,
                                    'unit': unit,
                                    'quantity': sg.get('total_qty', 0),
                                    'emission_kg': total_em_kg,
                                    'emission': total_em_tco2e,
                                    'has_data': True,
                                })
                        else:
                            unit = activity.base_unit.symbol if activity.base_unit else ''
                            sources.append({
                                'name': 'No data available',
                                'unit': unit,
                                'quantity': Decimal('0'),
                                'emission_kg': Decimal('0'),
                                'emission': Decimal('0'),
                                'has_data': False,
                            })

                    clean_activity_name = self._clean_text(activity.name)
                    activity_data = {
                        'id': activity.id,
                        'name': clean_activity_name,
                        'code': activity.code,
                        'total_quantity': total_quantity,
                        'total_emission_kg': total_emission_kg,
                        'total_emission': total_emission_tco2e,
                        'has_data': has_data,
                        'sources': sources,
                    }

                    category_data['activities'].append(activity_data)
                    category_data['total'] += total_emission_tco2e

                if category_data['activities']:
                    scope_data['categories'].append(category_data)
                    scope_data['total'] += category_data['total']
                    total_emissions += category_data['total']

            if scope_data['categories']:
                scopes_data.append(scope_data)
                scope_totals[scope.code] = scope_data['total']

        return {
            'scopes': scopes_data,
            'total_emissions': total_emissions,
            'scope_totals': scope_totals,
            'plant_name': plant_name,
            'company_name': self.company_name,
            'cin': self.cin,
            'generated_date': timezone.now().strftime('%d-%b-%Y %H:%M'),
            'report_year': self.report_year,
            'has_data': len(scopes_data) > 0,
        }

    def _brsr_table(self, table_data, col_widths, header_rows=1, right_align_from=None,
                     header_font_size=9, body_font_size=8.5):
        styled_data = []

        for row_idx, row in enumerate(table_data):
            styled_row = []
            for col_idx, cell in enumerate(row):
                if cell is None or cell == '':
                    styled_row.append('')
                elif isinstance(cell, str) and cell:
                    if row_idx < header_rows:
                        style = ParagraphStyle(
                            f'HeaderCell_{row_idx}_{col_idx}',
                            fontName=FONT_BOLD,
                            fontSize=header_font_size,
                            textColor=self.colors['table_header_text'],
                            alignment=TA_CENTER,
                            leading=header_font_size + 2,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    elif col_idx in [0, 1]:
                        style = ParagraphStyle(
                            f'BodyCell_{row_idx}_{col_idx}',
                            fontName=FONT_REGULAR,
                            fontSize=body_font_size,
                            textColor=self.colors['black'],
                            alignment=TA_LEFT,
                            leading=body_font_size + 1.5,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    elif col_idx in [2, 4, 5]:
                        style = ParagraphStyle(
                            f'BodyCellNum_{row_idx}_{col_idx}',
                            fontName=FONT_REGULAR,
                            fontSize=body_font_size,
                            textColor=self.colors['black'],
                            alignment=TA_RIGHT,
                            leading=body_font_size + 1.5,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    else:
                        style = ParagraphStyle(
                            f'BodyCellUnit_{row_idx}_{col_idx}',
                            fontName=FONT_REGULAR,
                            fontSize=body_font_size,
                            textColor=self.colors['black'],
                            alignment=TA_CENTER,
                            leading=body_font_size + 1.5,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                else:
                    styled_row.append(cell)
            styled_data.append(styled_row)

        style = [
            ('BACKGROUND', (0, 0), (-1, header_rows - 1), self.colors['table_header']),
            ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), self.colors['table_header_text']),
            ('FONTNAME', (0, 0), (-1, header_rows - 1), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, header_rows - 1), header_font_size),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.6, self.colors['grid_line']),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]

        if right_align_from is not None:
            style.append(('ALIGN', (right_align_from, header_rows), (-1, -1), 'RIGHT'))

        if len(styled_data) > header_rows + 1:
            for i in range(header_rows + 1, len(styled_data) - 1, 2):
                style.append(('BACKGROUND', (0, i), (-1, i), self.colors['light_gray']))

        if len(styled_data) > 1:
            style.extend([
                ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
                ('BACKGROUND', (0, -1), (-1, -1), self.colors['subheader_bg']),
                ('FONTSIZE', (0, -1), (-1, -1), body_font_size + 0.5),
            ])

        table = Table(styled_data, colWidths=col_widths, repeatRows=header_rows)
        table.setStyle(TableStyle(style))
        return table

    def _heading(self, text, size=14, space_before=10, space_after=10):
        style = ParagraphStyle(
            'BRSRHeading',
            fontName=FONT_BOLD,
            fontSize=size,
            textColor=self.colors['gold_text'],
            spaceBefore=space_before,
            spaceAfter=space_after,
            leading=size + 3,
        )
        return Paragraph(text, style)

    def _section_bar(self, text, font_size=10.5):
        style = ParagraphStyle(
            'SectionBar',
            fontName=FONT_BOLD,
            fontSize=font_size,
            textColor=self.colors['navy'],
            leftIndent=10,
        )
        table = Table([[Paragraph(text, style)]], colWidths=[6.9 * inch])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.75, self.colors['navy']),
            ('LINEBEFORE', (0, 0), (0, 0), 5, self.colors['gold']),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return table

    def _category_heading(self, text, size=12, space_before=8, space_after=6):
        style = ParagraphStyle(
            'CategoryHeading',
            fontName=FONT_BOLD,
            fontSize=size,
            textColor=self.colors['navy'],
            spaceBefore=space_before,
            spaceAfter=space_after,
        )
        return Paragraph(f"Category: {text}", style)

    def _get_scope_summary_page(self, data: Dict) -> List:
        elements = []
        elements.append(self._heading("Scope-wise GHG Emissions Summary", size=15))
        elements.append(self._section_bar(f"Emission Overview — FY {data['report_year']}"))
        elements.append(Spacer(1, 0.15 * inch))

        scope_label = {
            'S1': 'Total Scope 1 emissions (Direct)',
            'S2': 'Total Scope 2 emissions (Energy indirect)',
            'S3': 'Total Scope 3 emissions (Other indirect)',
        }

        rows = [["Parameter", "Unit", "Value"]]
        if not data['scopes']:
            rows.append(["No emission data available for the selected filters.", "", ""])
        else:
            for scope in data['scopes']:
                label = scope_label.get(scope['code'], f"Total {scope['name']} emissions")
                rows.append([label, "tCO2e", f"{scope['total']:,.2f}"])
            rows.append(["GRAND TOTAL (Scope 1 + 2 + 3)", "tCO2e", f"{data['total_emissions']:,.2f}"])

        col_widths = [3.8 * inch, 1.2 * inch, 1.6 * inch]
        table = self._brsr_table(rows, col_widths, header_rows=1, right_align_from=2)
        elements.append(table)

        return elements

    def _get_scope_breakdown(self, data: Dict) -> List:
            elements = []
            
            if not data['scopes']:
                no_data_style = ParagraphStyle(
                    'NoData',
                    fontName=FONT_REGULAR,
                    fontSize=10,
                    textColor=self.colors['gray'],
                    alignment=TA_CENTER,
                    spaceAfter=20
                )
                elements.append(Paragraph(
                    "No emission data available for the selected filters.",
                    no_data_style,
                ))
                return elements

            scope_colors = {
                'S1': self.colors['scope1'],
                'S2': self.colors['scope2'],
                'S3': self.colors['scope3'],
            }

            col_widths = [
                1.5 * inch,   # Activity
                1.6 * inch,   # Source
                0.7 * inch,   # Quantity
                0.5 * inch,   # Unit
                1.1 * inch,   # Total (kgCO2e)
                1.0 * inch,   # Total (tCO2e)
            ]

            # A4 page height: 842 points
            # Top margin: 48, Bottom margin: 54
            # Header takes about 55 points (BRSR FY + line)
            # Footer takes about 30 points (page number)
            # Usable space: 842 - 48 - 54 - 55 - 30 = ~655 points
            usable_space = 655  # points available for content
            
            for idx, scope in enumerate(data['scopes']):
                # Add page break before each scope (except the first one)
                if idx > 0:
                    elements.append(PageBreak())
                    current_space_used = 0
                else:
                    current_space_used = 0
                
                # Scope header
                scope_header_elements = []
                scope_header_elements.append(self._heading("Scope-wise Emission Breakdown", size=14, space_before=0, space_after=10))
                
                scope_color = scope_colors.get(scope['code'], self.colors['gold_text'])

                scope_style = ParagraphStyle(
                    'ScopeHeader',
                    fontName=FONT_BOLD,
                    fontSize=13,
                    textColor=scope_color,
                    spaceAfter=4,
                    spaceBefore=8
                )
                scope_header_elements.append(Paragraph(f"{scope['code']} — {scope['name']}", scope_style))

                if scope.get('description'):
                    desc_style = ParagraphStyle(
                        'ScopeDesc',
                        fontName=FONT_ITALIC,
                        fontSize=9,
                        textColor=self.colors['gray'],
                        spaceAfter=6,
                    )
                    scope_header_elements.append(Paragraph(scope['description'], desc_style))
                
                # Add scope header elements and calculate exact space
                for elem in scope_header_elements:
                    elements.append(elem)
                    # More accurate space estimation for header elements
                    if hasattr(elem, 'fontSize'):
                        if hasattr(elem, 'text'):
                            current_space_used += int(elem.fontSize) + 8
                        else:
                            current_space_used += 25
                    else:
                        current_space_used += 25

                # Process each category in the scope
                for category in scope['categories']:
                    # Build activity data first to calculate rows
                    activity_data = [
                        ['Activity', 'Source', 'Quantity', 'Unit', 'Total (kgCO2e)', 'Total (tCO2e)']
                    ]
                    total_qty = Decimal('0')
                    total_em_kg = Decimal('0')
                    total_em_tco2e = Decimal('0')
                    row_count = 1  # Start with header row

                    for activity in category['activities']:
                        total_qty += activity['total_quantity'] or Decimal('0')
                        total_em_kg += activity.get('total_emission_kg') or Decimal('0')
                        total_em_tco2e += activity['total_emission'] or Decimal('0')

                        if activity['sources'] and len(activity['sources']) > 0:
                            first_row = True
                            for source in activity['sources']:
                                qty = source.get('quantity', 0)
                                kg = source.get('emission_kg', 0)
                                em_tco2e = source.get('emission', 0)
                                unit = source.get('unit', '')

                                qty_str = f"{qty:,.2f}"
                                kg_str = f"{kg:,.2f}"
                                em_str = f"{em_tco2e:,.2f}"
                                source_name = source.get('name', 'Unknown')

                                activity_name = activity['name'] if first_row else ''

                                activity_data.append([
                                    activity_name,
                                    source_name,
                                    qty_str,
                                    unit,
                                    kg_str,
                                    em_str,
                                ])
                                first_row = False
                                row_count += 1
                        else:
                            unit = activity.get('base_unit', {}).get('symbol', '') if hasattr(activity, 'base_unit') else ''
                            activity_data.append([
                                activity['name'],
                                'No sources available',
                                '0.00',
                                unit,
                                '0.00',
                                '0.00'
                            ])
                            row_count += 1

                    total_qty_str = f"{total_qty:,.2f}"
                    total_em_kg_str = f"{total_em_kg:,.2f}"
                    total_em_str = f"{total_em_tco2e:,.2f}"
                    activity_data.append([
                        'Category Total',
                        '',
                        total_qty_str,
                        '',
                        total_em_kg_str,
                        total_em_str
                    ])
                    row_count += 1  # Category Total row

                    # Calculate exact space needed for this category
                    # Category heading: ~25 points
                    # Table: row_count * 18 points (average row height) + 20 points for header
                    # Spacer: ~12 points
                    table_height = row_count * 18 + 25
                    category_space_needed = 25 + table_height + 12
                    
                    # Check if category fits on current page
                    if current_space_used + category_space_needed > usable_space:
                        elements.append(PageBreak())
                        # Re-add scope header on new page for context
                        for elem in scope_header_elements:
                            elements.append(elem)
                        current_space_used = len(scope_header_elements) * 25
                        # If still doesn't fit, add it anyway
                        if current_space_used + category_space_needed > usable_space:
                            pass
                    
                    # Add category heading
                    category_heading = self._category_heading(category['name'])
                    elements.append(category_heading)
                    current_space_used += 25

                    # Create and add the table
                    table = self._brsr_table(
                        activity_data,
                        col_widths,
                        header_rows=1,
                        right_align_from=2,
                    )
                    elements.append(table)
                    current_space_used += table_height
                    
                    # Add spacer
                    spacer = Spacer(1, 0.06 * inch)
                    elements.append(spacer)
                    current_space_used += 12

                if scope['total'] > 0:
                    scope_total_style = ParagraphStyle(
                        'ScopeTotal',
                        fontName=FONT_BOLD,
                        fontSize=11,
                        alignment=TA_RIGHT,
                        textColor=scope_color,
                        spaceAfter=4,
                    )
                    scope_total = Paragraph(
                        f"Scope {scope['code']} Total: {scope['total']:,.2f} tCO2e",
                        scope_total_style,
                    )
                    elements.append(scope_total)
                    current_space_used += 30

                elements.append(HRFlowable(
                    width="100%", thickness=1, color=self.colors['gold'],
                    spaceBefore=4, spaceAfter=8
                ))

            if data['total_emissions'] > 0:
                grand_style = ParagraphStyle(
                    'GrandTotal',
                    fontName=FONT_BOLD,
                    fontSize=14,
                    alignment=TA_RIGHT,
                    textColor=self.colors['navy'],
                    spaceBefore=6,
                    spaceAfter=10,
                )
                elements.append(Paragraph(
                    f"GRAND TOTAL: {data['total_emissions']:,.2f} tCO2e",
                    grand_style,
                ))

            return elements

# ==========================================================
# Helper functions
# ==========================================================

def generate_emission_pdf_report(
    assignment_id: Optional[int] = None,
    company_id: Optional[int] = None,
    plant_id: Optional[int] = None,
    financial_year_id: Optional[int] = None,
    financial_month_id: Optional[int] = None,
    company_name: str = None,
    cin: str = None,
    report_year: str = None,
    user=None,
) -> BytesIO:
    generator = BRSRPDFGenerator(
        assignment_id=assignment_id,
        company_id=company_id,
        plant_id=plant_id,
        financial_year_id=financial_year_id,
        financial_month_id=financial_month_id,
        company_name=company_name,
        cin=cin,
        report_year=report_year,
        user=user,
    )
    return generator.generate()


def download_emission_pdf(request, assignment_id=None):
    from django.http import JsonResponse
    from apps.accounts.models import User
    from apps.companies.models import Company

    try:
        assignment = EmissionAssignment.objects.get(id=assignment_id)
        user = request.user

        company_name = None
        cin = None

        if user.is_authenticated:
            user = User.objects.select_related('company').get(id=user.id)
            if user.company:
                company_name = user.company.company_name
                cin = getattr(user.company, 'cin', None)

        if not company_name and assignment.company_id:
            try:
                company = Company.objects.get(id=assignment.company_id)
                company_name = company.company_name
                cin = getattr(company, 'cin', None)
            except Company.DoesNotExist:
                pass

        if not company_name:
            company_name = "Lucas TVS Ltd"
        if not cin:
            cin = "N/A"

        has_access = (
            assignment.assignee == user
            or assignment.assigner == user
            or assignment.reviewer == user
            or (hasattr(user, 'role') and user.role and user.role.role_code in ['COMPANYADMIN', 'ESG-HEAD', 'ESG-COORD'])
        )

        if not has_access:
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to download this report.',
            }, status=403)

        pdf_buffer = generate_emission_pdf_report(
            assignment_id=assignment_id,
            company_id=assignment.company_id,
            plant_id=assignment.plant_id,
            financial_year_id=assignment.financial_year_id,
            financial_month_id=assignment.financial_month_id,
            company_name=company_name,
            cin=cin,
            user=user,
        )

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Emissions_Report_{assignment.assignment_code}_{timestamp}.pdf"

        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except EmissionAssignment.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Assignment not found.'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error generating PDF: {str(e)}'}, status=500)