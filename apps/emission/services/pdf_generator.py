# apps/emission/services/pdf_generator.py
"""
BRSR-style PDF generator — Emissions Report Only
"""
import os
from io import BytesIO
from decimal import Decimal
from typing import Dict, List, Optional

from django.db.models import Sum, Q
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from ..models import (
    EmissionScope,
    EmissionCategory,
    EmissionActivity,
    EmissionSource,
    EmissionTransaction,
    EmissionAssignment,
)


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
        report_year: str = None,
        user=None,
    ):
        self.assignment_id = assignment_id
        self.company_id = company_id
        self.plant_id = plant_id
        self.financial_year_id = financial_year_id
        self.financial_month_id = financial_month_id
        self.user = user
        
        # Set company name - prioritize provided company_name
        if company_name:
            self.company_name = company_name
            print(f"DEBUG: Using provided company_name: {self.company_name}")
        else:
            # Try to get from user
            self.company_name = self._get_company_name_from_user()
            print(f"DEBUG: Fetched company_name from user: {self.company_name}")
        
        # Auto-fetch financial year if not provided
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

        # Color palette
        self.colors = {
            'primary': colors.HexColor('#1a237e'),
            'secondary': colors.HexColor('#283593'),
            'accent': colors.HexColor('#3949ab'),
            'table_header': colors.HexColor('#1a237e'),
            'table_header_text': colors.HexColor('#ffffff'),
            'subheader_bg': colors.HexColor('#e8eaf6'),
            'border': colors.HexColor('#c5cae9'),
            'white': colors.HexColor('#ffffff'),
            'black': colors.HexColor('#1a2332'),
            'gray': colors.HexColor('#6b7280'),
            'light_gray': colors.HexColor('#f5f7fb'),
            'scope1': colors.HexColor('#1a237e'),
            'scope2': colors.HexColor('#283593'),
            'scope3': colors.HexColor('#3949ab'),
        }

    def _get_company_name_from_user(self) -> str:
        """Get company name from user object."""
        from apps.accounts.models import User
        from apps.companies.models import Company
        
        if not self.user:
            print("DEBUG: No user object provided")
            return "Lucas TVS Ltd"
        
        try:
            # If user is a User object, get company directly
            if hasattr(self.user, 'company') and self.user.company:
                company_name = self.user.company.company_name
                print(f"DEBUG: Company from user.company: {company_name}")
                return company_name
            
            # If user has company_id
            if hasattr(self.user, 'company_id') and self.user.company_id:
                try:
                    company = Company.objects.get(id=self.user.company_id)
                    company_name = company.company_name
                    print(f"DEBUG: Company from user.company_id: {company_name}")
                    return company_name
                except Company.DoesNotExist:
                    print(f"DEBUG: Company with id {self.user.company_id} not found")
            
            # If user is a dict or has id, try to fetch from DB
            user_id = getattr(self.user, 'id', None)
            if user_id:
                try:
                    user = User.objects.select_related('company').get(id=user_id)
                    if user.company:
                        company_name = user.company.company_name
                        print(f"DEBUG: Company from DB user: {company_name}")
                        return company_name
                except User.DoesNotExist:
                    print(f"DEBUG: User with id {user_id} not found")
        
        except Exception as e:
            print(f"DEBUG: Error getting company: {e}")
        
        print("DEBUG: No company found, using default")
        return "Lucas TVS Ltd"

    # ======================================================================
    # PDF assembly
    # ======================================================================
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

        story = []
        data = self._get_report_data()

        story.extend(self._get_report_header(data))
        
        scope_elements = self._get_scope_breakdown(data)
        story.extend(scope_elements)

        doc.build(
            story,
            onFirstPage=self._draw_page_furniture,
            onLaterPages=self._draw_page_furniture,
        )

        self.buffer.seek(0)
        return self.buffer

    def _draw_page_furniture(self, canvas, doc):
        canvas.saveState()

        if doc.page > 1:
            canvas.setFont('Helvetica-Bold', 9)
            canvas.setFillColor(self.colors['primary'])
            canvas.drawRightString(
                A4[0] - 30, A4[1] - 40, f"FY {self.report_year}"
            )
            canvas.setStrokeColor(self.colors['border'])
            canvas.setLineWidth(0.5)
            canvas.line(30, A4[1] - 45, A4[0] - 30, A4[1] - 45)

        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(self.colors['gray'])
        canvas.drawCentredString(A4[0] / 2, 30, str(doc.page))

        canvas.restoreState()

    # ======================================================================
    # Helper to clean special characters
    # ======================================================================
    def _clean_text(self, text: str) -> str:
        """Clean special characters for PDF rendering."""
        if not text:
            return text
        replacements = {
            '₆': '6',
            '₄': '4',
            '₂': '2',
            '₃': '3',
            '₁': '1',
            '₅': '5',
            '₇': '7',
            '₈': '8',
            '₉': '9',
            '₀': '0',
            '■': '',
            '●': '',
            '•': '',
            '—': '-',
            '–': '-',
            '…': '...',
            '”': '"',
            '“': '"',
            '’': "'",
            '‘': "'",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    # ======================================================================
    # Data - Get ALL activities with their sources (converted to tCO2e)
    # ======================================================================
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
                plant_name = "All Plants"
            except Exception:
                pass

        # Get company name - use the one from constructor
        company_name = self.company_name

        # Get current financial year info
        from apps.organizations.models import FinancialYear
        
        current_fy_name = self.report_year

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
                    # Get ALL sources for this activity
                    all_sources = EmissionSource.objects.filter(
                        activity=activity,
                        is_active=True
                    ).order_by('display_order')

                    # Get transactions for this activity
                    transactions = EmissionTransaction.objects.filter(
                        activity_id=activity.id, **filter_kwargs
                    ).select_related('source', 'unit')

                    has_data = transactions.exists()
                    
                    total_quantity = Decimal('0')
                    total_emission_tco2e = Decimal('0')  # Store in tCO2e

                    if has_data:
                        total_quantity = transactions.aggregate(
                            total=Sum('quantity')
                        )['total'] or Decimal('0')

                        # Get total emission in kg and convert to tonnes
                        total_emission_kg = transactions.aggregate(
                            total=Sum('total_emission')
                        )['total'] or Decimal('0')
                        
                        # Convert kg to tonnes (tCO2e) - divide by 1000
                        total_emission_tco2e = total_emission_kg / Decimal('1000')

                    # Build sources list with data
                    sources = []
                    
                    if all_sources.exists():
                        for source in all_sources:
                            # Get transactions for this specific source
                            source_transactions = transactions.filter(source=source)
                            
                            if source_transactions.exists():
                                source_total_qty = source_transactions.aggregate(
                                    total=Sum('quantity')
                                )['total'] or Decimal('0')
                                
                                # Convert source emission from kg to tonnes
                                source_total_em_kg = source_transactions.aggregate(
                                    total=Sum('total_emission')
                                )['total'] or Decimal('0')
                                source_total_em_tco2e = source_total_em_kg / Decimal('1000')
                                
                                # Get the unit from the first transaction
                                first_trans = source_transactions.first()
                                unit = first_trans.unit.symbol if first_trans and first_trans.unit else ''
                                has_source_data = True
                            else:
                                source_total_qty = Decimal('0')
                                source_total_em_tco2e = Decimal('0')
                                # Try to get unit from activity's base_unit
                                unit = activity.base_unit.symbol if activity.base_unit else ''
                                has_source_data = False

                            clean_name = self._clean_text(source.source_name)
                            sources.append({
                                'name': clean_name,
                                'unit': unit,
                                'quantity': source_total_qty,
                                'emission': source_total_em_tco2e,  # Already in tCO2e
                                'has_data': has_source_data,
                            })
                    else:
                        # No sources in database - use transaction data directly
                        if has_data:
                            # Group transactions by source
                            source_groups = transactions.values(
                                'source__source_name', 
                                'unit__symbol'
                            ).annotate(
                                total_qty=Sum('quantity'),
                                total_em=Sum('total_emission')  # This is in kg
                            ).order_by('source__display_order')
                            
                            for sg in source_groups:
                                clean_name = self._clean_text(sg.get('source__source_name', 'Unknown'))
                                unit = sg.get('unit__symbol', '')
                                total_em_kg = sg.get('total_em', 0)
                                # Convert to tonnes
                                total_em_tco2e = total_em_kg / Decimal('1000')
                                sources.append({
                                    'name': clean_name,
                                    'unit': unit,
                                    'quantity': sg.get('total_qty', 0),
                                    'emission': total_em_tco2e,  # In tCO2e
                                    'has_data': True,
                                })
                        else:
                            # No data at all - use activity's base unit
                            unit = activity.base_unit.symbol if activity.base_unit else ''
                            sources.append({
                                'name': 'No data available',
                                'unit': unit,
                                'quantity': Decimal('0'),
                                'emission': Decimal('0'),
                                'has_data': False,
                            })

                    clean_activity_name = self._clean_text(activity.name)
                    
                    activity_data = {
                        'id': activity.id,
                        'name': clean_activity_name,
                        'code': activity.code,
                        'total_quantity': total_quantity,
                        'total_emission': total_emission_tco2e,  # In tCO2e
                        'has_data': has_data,
                        'sources': sources,
                    }

                    category_data['activities'].append(activity_data)
                    category_data['total'] += total_emission_tco2e  # In tCO2e

                if category_data['activities']:
                    scope_data['categories'].append(category_data)
                    scope_data['total'] += category_data['total']  # In tCO2e
                    total_emissions += category_data['total']  # In tCO2e

            if scope_data['categories']:
                scopes_data.append(scope_data)
                scope_totals[scope.code] = scope_data['total']  # In tCO2e

        return {
            'scopes': scopes_data,
            'total_emissions': total_emissions,  # In tCO2e
            'scope_totals': scope_totals,  # In tCO2e
            'plant_name': plant_name,
            'company_name': company_name,
            'generated_date': timezone.now().strftime('%d-%b-%Y %H:%M'),
            'report_year': self.report_year,
            'current_fy': current_fy_name,
            'has_data': len(scopes_data) > 0,
        }

    # ======================================================================
    # BRSR-style table builder
    # ======================================================================
    def _brsr_table(self, table_data, col_widths, header_rows=1, right_align_from=None):
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
                            fontName='Helvetica-Bold',
                            fontSize=9,
                            textColor=self.colors['table_header_text'],
                            alignment=TA_CENTER,
                            leading=10,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    elif col_idx in [0, 1]:
                        style = ParagraphStyle(
                            f'BodyCell_{row_idx}_{col_idx}',
                            fontName='Helvetica',
                            fontSize=8,
                            textColor=self.colors['black'],
                            alignment=TA_LEFT,
                            leading=9,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    elif col_idx in [2, 4]:
                        style = ParagraphStyle(
                            f'BodyCellNum_{row_idx}_{col_idx}',
                            fontName='Helvetica',
                            fontSize=8,
                            textColor=self.colors['black'],
                            alignment=TA_RIGHT,
                            leading=9,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                    else:
                        style = ParagraphStyle(
                            f'BodyCellUnit_{row_idx}_{col_idx}',
                            fontName='Helvetica',
                            fontSize=8,
                            textColor=self.colors['black'],
                            alignment=TA_CENTER,
                            leading=9,
                        )
                        styled_row.append(Paragraph(str(cell), style))
                else:
                    styled_row.append(cell)
            styled_data.append(styled_row)
        
        style = [
            ('BACKGROUND', (0, 0), (-1, header_rows - 1), self.colors['table_header']),
            ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), self.colors['table_header_text']),
            ('FONTNAME', (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, header_rows - 1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.colors['border']),
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
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), self.colors['subheader_bg']),
                ('FONTSIZE', (0, -1), (-1, -1), 9),
            ])

        table = Table(styled_data, colWidths=col_widths, repeatRows=header_rows)
        table.setStyle(TableStyle(style))
        return table

    def _heading(self, text, size=14, space_before=10, space_after=10):
        styles = getSampleStyleSheet()
        style = ParagraphStyle(
            'BRSRHeading',
            parent=styles['Heading2'],
            fontSize=size,
            textColor=self.colors['primary'],
            fontName='Helvetica-Bold',
            spaceBefore=space_before,
            spaceAfter=space_after,
        )
        return Paragraph(text, style)

    def _category_heading(self, text, size=12, space_before=8, space_after=6):
        styles = getSampleStyleSheet()
        style = ParagraphStyle(
            'CategoryHeading',
            parent=styles['Heading3'],
            fontSize=size,
            textColor=self.colors['black'],
            fontName='Helvetica-Bold',
            spaceBefore=space_before,
            spaceAfter=space_after,
        )
        return Paragraph(f"Category: {text}", style)

    # ======================================================================
    # Report Header
    # ======================================================================
    def _get_report_header(self, data: Dict) -> List:
        styles = getSampleStyleSheet()
        elements = []

        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Title'],
            fontSize=26,
            textColor=self.colors['primary'],
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=4,
        )
        elements.append(Paragraph(data['company_name'], company_style))

        report_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=self.colors['secondary'],
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=4,
        )
        elements.append(Paragraph("Emissions Report", report_style))

        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.colors['gray'],
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        subtitle_text = f"FY {data['report_year']} | {data['plant_name']}"
        elements.append(Paragraph(subtitle_text, subtitle_style))

        elements.append(HRFlowable(
            width="100%", thickness=1.5, color=self.colors['primary'],
            spaceBefore=6, spaceAfter=12,
        ))

        return elements

    # ======================================================================
    # Scope-wise breakdown
    # ======================================================================
    def _get_scope_breakdown(self, data: Dict) -> List:
        elements = []
        elements.append(self._heading("Scope-wise Emission Breakdown", size=14, space_before=8, space_after=10))

        if not data['scopes']:
            no_data_style = ParagraphStyle(
                'NoData',
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
            1.8 * inch,
            2.0 * inch,
            0.8 * inch,
            0.6 * inch,
            1.2 * inch,
        ]

        for idx, scope in enumerate(data['scopes']):
            if idx > 0:
                elements.append(PageBreak())
                elements.append(self._heading("Scope-wise Emission Breakdown", size=14, space_before=8, space_after=10))
            
            scope_color = scope_colors.get(scope['code'], self.colors['primary'])
            
            scope_style = ParagraphStyle(
                'ScopeHeader',
                parent=getSampleStyleSheet()['Normal'],
                fontSize=13,
                textColor=scope_color,
                fontName='Helvetica-Bold',
                spaceAfter=4,
                spaceBefore=8
            )
            elements.append(Paragraph(f"{scope['code']} — {scope['name']}", scope_style))

            if scope.get('description'):
                desc_style = ParagraphStyle(
                    'ScopeDesc',
                    fontSize=9,
                    textColor=self.colors['gray'],
                    spaceAfter=6,
                )
                elements.append(Paragraph(scope['description'], desc_style))

            for category in scope['categories']:
                elements.append(self._category_heading(category['name']))

                activity_data = [['Activity', 'Source', 'Quantity', 'Unit', 'Total (tCO2e)']]
                total_qty = Decimal('0')
                total_em_tco2e = Decimal('0')

                for activity in category['activities']:
                    total_qty += activity['total_quantity'] or Decimal('0')
                    total_em_tco2e += activity['total_emission'] or Decimal('0')
                    
                    if activity['sources'] and len(activity['sources']) > 0:
                        first_row = True
                        for source in activity['sources']:
                            qty = source.get('quantity', 0)
                            em_tco2e = source.get('emission', 0)  # Already in tCO2e
                            unit = source.get('unit', '')
                            
                            qty_str = f"{qty:,.2f}"
                            em_str = f"{em_tco2e:,.2f}"  # Format with 2 decimal places
                            source_name = source.get('name', 'Unknown')
                            
                            activity_name = activity['name'] if first_row else ''
                            
                            activity_data.append([
                                activity_name,
                                source_name,
                                qty_str,
                                unit,
                                em_str,
                            ])
                            first_row = False
                    else:
                        # No sources - use activity's base unit
                        unit = activity.get('base_unit', {}).get('symbol', '') if hasattr(activity, 'base_unit') else ''
                        activity_data.append([
                            activity['name'],
                            'No sources available',
                            '0.00',
                            unit,
                            '0.00'
                        ])

                total_qty_str = f"{total_qty:,.2f}"
                total_em_str = f"{total_em_tco2e:,.2f}"
                activity_data.append([
                    'Category Total',
                    '',
                    total_qty_str,
                    '',
                    total_em_str
                ])

                table = self._brsr_table(
                    activity_data,
                    col_widths,
                    header_rows=1,
                    right_align_from=2,
                )
                elements.append(table)
                elements.append(Spacer(1, 0.06 * inch))

            # Scope total in tCO2e
            if scope['total'] > 0:
                scope_total_style = ParagraphStyle(
                    'ScopeTotal',
                    fontSize=11,
                    alignment=TA_RIGHT,
                    textColor=scope_color,
                    fontName='Helvetica-Bold',
                    spaceAfter=4,
                )
                elements.append(Paragraph(
                    f"<b>Scope {scope['code']} Total: {scope['total']:,.2f} tCO2e</b>",
                    scope_total_style,
                ))

            elements.append(HRFlowable(
                width="100%", thickness=0.75, color=self.colors['border'],
                spaceBefore=4, spaceAfter=8
            ))

        # Grand total in tCO2e
        if data['total_emissions'] > 0:
            grand_style = ParagraphStyle(
                'GrandTotal',
                fontSize=14,
                alignment=TA_RIGHT,
                textColor=self.colors['primary'],
                fontName='Helvetica-Bold',
                spaceBefore=6,
                spaceAfter=10,
            )
            elements.append(Paragraph(
                f"<b>GRAND TOTAL: {data['total_emissions']:,.2f} tCO2e</b>",
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
    report_year: str = None,
    user=None,
) -> BytesIO:
    """
    Generate a BRSR-styled, emissions-only PDF report with blue table headers.
    """
    generator = BRSRPDFGenerator(
        assignment_id=assignment_id,
        company_id=company_id,
        plant_id=plant_id,
        financial_year_id=financial_year_id,
        financial_month_id=financial_month_id,
        company_name=company_name,
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
        
        # Get user with company loaded using select_related
        company_name = None
        
        if user.is_authenticated:
            # Refresh user from database with company loaded
            user = User.objects.select_related('company').get(id=user.id)
            print(f"DEBUG: User: {user.username}")
            print(f"DEBUG: User has company: {user.company is not None}")
            
            if user.company:
                company_name = user.company.company_name
                print(f"DEBUG: Company Name from user: {company_name}")
            else:
                print(f"DEBUG: User has no company assigned!")
        
        # If user doesn't have company, try assignment
        if not company_name and assignment.company_id:
            try:
                company = Company.objects.get(id=assignment.company_id)
                company_name = company.company_name
                print(f"DEBUG: Company Name from assignment: {company_name}")
            except Company.DoesNotExist:
                print(f"DEBUG: Assignment company not found")
        
        # Final fallback
        if not company_name:
            company_name = "Lucas TVS Ltd"
            print(f"DEBUG: Using default company name: {company_name}")
        
        # Check permissions
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

        # Pass the company name directly
        pdf_buffer = generate_emission_pdf_report(
            assignment_id=assignment_id,
            company_id=assignment.company_id,
            plant_id=assignment.plant_id,
            financial_year_id=assignment.financial_year_id,
            financial_month_id=assignment.financial_month_id,
            company_name=company_name,  # Pass company name directly
            user=user,  # Still pass user for any other use
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