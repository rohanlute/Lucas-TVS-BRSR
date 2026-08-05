# apps/goals/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q
from django.core.exceptions import FieldError
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

def _to_decimal(value, field_name="value"):
    """Convert a value to Decimal, handling None and empty strings."""
    if value is None or value == '':
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"Could not convert '{value}' to Decimal for {field_name}, defaulting to 0")
        return Decimal('0')


class MaterialTopic(models.Model):
    """Material topics for sustainability reporting."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_material_topics'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='updated_material_topics'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Goal(models.Model):
    """Goals associated with material topics."""
    name = models.CharField(max_length=255)
    material_topic = models.ForeignKey(
        MaterialTopic, 
        on_delete=models.CASCADE, 
        related_name='goals'
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_goals'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='updated_goals'
    )

    class Meta:
        unique_together = ['material_topic', 'name']
        ordering = ['material_topic', 'name']

    def __str__(self):
        return f"{self.material_topic.name} - {self.name}"


class KPI(models.Model):
    """Key Performance Indicators for goals."""
    goal = models.ForeignKey(
        Goal, 
        on_delete=models.CASCADE, 
        related_name='kpis'
    )
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True, null=True)
    
    # Baseline fields
    baseline_year = models.CharField(max_length=20, blank=True)
    baseline_value = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    
    # Target fields
    target_year = models.CharField(max_length=20, blank=True)
    target_reduction = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    target_value = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    
    # Mapping fields for emission data
    category_keyword = models.CharField(max_length=255, blank=True, 
                                       help_text="Keyword to match category in emission data")
    activity_keyword = models.CharField(max_length=255, blank=True, 
                                       help_text="Keyword to match activity.name in EmissionTransaction")
    source_keyword = models.CharField(max_length=255, blank=True,
                                     help_text="Keyword to match source.source_name in EmissionTransaction")
    
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_kpis'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='updated_kpis'
    )

    class Meta:
        unique_together = ['goal', 'name']
        ordering = ['goal', 'name']

    def __str__(self):
        return f"{self.goal.name} - {self.name}"

    def save(self, *args, **kwargs):
        """Auto-calculate target_value from reduction if not provided."""
        self.baseline_value = _to_decimal(self.baseline_value, 'baseline_value')
        self.target_reduction = _to_decimal(self.target_reduction, 'target_reduction')
        
        if self.baseline_value and self.target_reduction:
            self.target_value = self.baseline_value * (1 - (self.target_reduction / Decimal('100')))
        elif self.target_value not in (None, ''):
            self.target_value = _to_decimal(self.target_value, 'target_value')
            
        super().save(*args, **kwargs)

    def get_config_for_plant(self, plant_id=None):
        """
        Returns baseline/target config for a specific plant if one exists,
        otherwise falls back to the KPI's own (aggregate/"All Plants") values.
        """
        if plant_id:
            try:
                pt = self.plant_targets.get(plant_id=plant_id)
                return {
                    'baseline_year': pt.baseline_year,
                    'baseline_value': pt.baseline_value,
                    'target_year': pt.target_year,
                    'target_reduction': pt.target_reduction,
                    'target_value': pt.target_value,
                    'unit': pt.unit or self.unit,
                    'is_plant_specific': True,
                }
            except KPIPlantTarget.DoesNotExist:
                pass
        
        # Fallback to aggregate KPI values
        return {
            'baseline_year': self.baseline_year,
            'baseline_value': self.baseline_value,
            'target_year': self.target_year,
            'target_reduction': self.target_reduction,
            'target_value': self.target_value,
            'unit': self.unit,
            'is_plant_specific': False,
        }

    # apps/goals/models.py

    def get_current_value(self, company_id=None, plant_id=None, financial_year_id=None,
                        financial_month_id=None, assignment_id=None, statuses=None):
        """
        Calculate current value based on emissions data.
        For consumption KPIs: returns sum of quantity (actual consumption)
        For emission KPIs: returns sum of total_emission / 1000 (convert to tonnes)
        """
        from apps.emission.models import EmissionTransaction
        
        # Start with an empty Q object
        filters = Q()
        
        # Add filters one by one
        if plant_id:
            filters &= Q(plant_id=plant_id)
            logger.info(f"Filtering by plant_id: {plant_id}")
        
        if company_id:
            filters &= Q(company_id=company_id)
            logger.info(f"Filtering by company_id: {company_id}")
        
        if financial_year_id:
            filters &= Q(financial_year_id=financial_year_id)
            logger.info(f"Filtering by financial_year_id: {financial_year_id}")
        
        if financial_month_id:
            filters &= Q(financial_month_id=financial_month_id)
            logger.info(f"Filtering by financial_month_id: {financial_month_id}")
        
        if assignment_id:
            filters &= Q(assignment_id=assignment_id)
            logger.info(f"Filtering by assignment_id: {assignment_id}")
        
        if statuses:
            filters &= Q(status__in=statuses)
            logger.info(f"Filtering by statuses: {statuses}")
        
        # ===== ✅ FIX: Apply category keyword filter FIRST =====
        # This ensures we only get data from the specific category
        if self.category_keyword and self.category_keyword.strip():
            category_filter = Q()
            keywords = [kw.strip() for kw in self.category_keyword.split(',')]
            
            for kw in keywords:
                if kw:
                    # Filter by exact category name match
                    category_filter |= Q(activity__category__name=kw)
            
            if category_filter:
                filters &= category_filter
                logger.info(f"Applied category filter: {keywords}")
        
        # Apply activity keyword filter (only if category is not enough)
        # For emission KPIs, we only want category filter
        is_emission_kpi = (
            'tco2' in self.unit.lower() or 
            'tco₂' in self.unit.lower() or
            'tco2e' in self.unit.lower() or 
            'tco₂e' in self.unit.lower()
        )
        
        # For emission KPIs, ONLY use category filter (no activity filter)
        if is_emission_kpi:
            # Emission KPIs should only filter by category
            # No additional activity filter needed
            logger.info(f"Emission KPI: Only filtering by category: {self.category_keyword}")
        else:
            # For consumption KPIs, apply activity keyword filter
            if self.activity_keyword and self.activity_keyword.strip():
                activity_filter = Q()
                keywords = [kw.strip() for kw in self.activity_keyword.split(',')]
                
                for kw in keywords:
                    if kw:
                        activity_filter |= Q(activity__name=kw)
                
                if activity_filter:
                    filters &= activity_filter
                    logger.info(f"Applied activity filter: {keywords}")
        
        # Log the query for debugging
        queryset = EmissionTransaction.objects.filter(filters)
        logger.info(f"Query SQL: {queryset.query}")
        logger.info(f"Number of records found: {queryset.count()}")
        
        # For emission KPIs: sum total_emission and convert to tonnes
        if is_emission_kpi:
            result = queryset.aggregate(total=Sum('total_emission'))
            total = result['total']
            logger.info(f"Sum of total_emission: {total}")
            if total is None:
                return 0.0
            return float(total) / 1000.0
        
        # For consumption KPIs: sum quantity
        else:
            result = queryset.aggregate(total=Sum('quantity'))
            total = result['total']
            logger.info(f"Sum of quantity: {total}")
            if total is None:
                return 0.0
        return float(total)

    def get_total_scope_emission(self, scope_code=None, plant_id=None, company_id=None,
                                 financial_year_id=None, financial_month_id=None):
        """
        Get total scope emission for a specific scope.
        Returns sum of total_emission / 1000 in tCO₂e
        """
        from apps.emission.models import EmissionTransaction, EmissionScope
        
        filters = Q()
        
        # Add filters
        if plant_id:
            filters &= Q(plant_id=plant_id)
        if company_id:
            filters &= Q(company_id=company_id)
        if financial_year_id:
            filters &= Q(financial_year_id=financial_year_id)
        if financial_month_id:
            filters &= Q(financial_month_id=financial_month_id)
        
        # If scope_code is provided, filter by scope
        if scope_code:
            try:
                scope = EmissionScope.objects.get(code=scope_code)
                category_ids = scope.categories.values_list('id', flat=True)
                filters &= Q(activity__category_id__in=category_ids)
            except EmissionScope.DoesNotExist:
                pass
        
        # Also filter by category_keyword if set
        if self.category_keyword and self.category_keyword.strip():
            category_filter = Q()
            keywords = [kw.strip() for kw in self.category_keyword.split(',')]
            for kw in keywords:
                if kw:
                    category_filter |= Q(activity__category__name=kw)
            if category_filter:
                filters &= category_filter
        
        # Get sum of total_emission
        result = EmissionTransaction.objects.filter(filters).aggregate(
            total=Sum('total_emission'))
        total = result['total']
        if total is None:
            return 0.0
        # Convert to tCO₂e
        return float(total) / 1000.0

    def get_total_consumption(self, company_id=None, plant_id=None,
                              financial_year_id=None, financial_month_id=None):
        """
        Get total consumption (quantity) for this KPI.
        """
        from apps.emission.models import EmissionTransaction
        
        filters = Q()
        
        if plant_id:
            filters &= Q(plant_id=plant_id)
        if company_id:
            filters &= Q(company_id=company_id)
        if financial_year_id:
            filters &= Q(financial_year_id=financial_year_id)
        if financial_month_id:
            filters &= Q(financial_month_id=financial_month_id)
        
        # Apply activity keyword filter
        if self.activity_keyword and self.activity_keyword.strip():
            activity_filter = Q()
            keywords = [kw.strip() for kw in self.activity_keyword.split(',')]
            for kw in keywords:
                if kw:
                    activity_filter |= Q(activity__name=kw)
            if activity_filter:
                filters &= activity_filter
        
        # Apply category keyword filter
        elif self.category_keyword and self.category_keyword.strip():
            category_filter = Q()
            keywords = [kw.strip() for kw in self.category_keyword.split(',')]
            for kw in keywords:
                if kw:
                    category_filter |= Q(activity__category__name=kw)
            if category_filter:
                filters &= category_filter
        
        result = EmissionTransaction.objects.filter(filters).aggregate(
            total=Sum('quantity'))
        total = result['total']
        if total is None:
            return 0.0
        return float(total)

    def get_progress_percentage(self, company_id=None, plant_id=None, 
                               financial_year_id=None, financial_month_id=None,
                               assignment_id=None, statuses=None,
                               baseline_value=None, target_value=None):
        """Calculate progress towards target with optional plant-specific overrides."""
        current_value = self.get_current_value(
            company_id, plant_id, financial_year_id,
            financial_month_id, assignment_id, statuses
        )

        baseline = float(baseline_value) if baseline_value not in (None, '') else float(self.baseline_value or 0)
        target = float(target_value) if target_value not in (None, '') else float(self.target_value or 0)

        logger.info(f"Progress calculation: current={current_value}, baseline={baseline}, target={target}")

        if target and baseline:
            total_reduction_needed = baseline - target
            if total_reduction_needed <= 0:
                return 100.0
            current_reduction = baseline - current_value
            progress = (current_reduction / total_reduction_needed) * 100
            return max(0.0, min(100.0, progress))
        return 0.0

    def get_status(self, company_id=None, plant_id=None, financial_year_id=None,
                  financial_month_id=None, assignment_id=None, statuses=None,
                  baseline_value=None, target_value=None):
        """Get status based on current value against target."""
        current_value = self.get_current_value(
            company_id, plant_id, financial_year_id,
            financial_month_id, assignment_id, statuses
        )

        target = float(target_value) if target_value not in (None, '') else float(self.target_value or 0)
        baseline = float(baseline_value) if baseline_value not in (None, '') else float(self.baseline_value or 0)

        if current_value <= target:
            return 'On Track'
        elif current_value <= baseline:
            return 'In Progress'
        else:
            return 'At Risk'


class KPIPlantTarget(models.Model):
    """
    Plant-specific baseline/target for a KPI.
    If no row exists for a given plant, the KPI's own baseline_value/
    target_value act as the "All Plants" aggregate default.
    """
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='plant_targets')
    plant = models.ForeignKey('organizations.Plant', on_delete=models.CASCADE, related_name='kpi_targets')

    baseline_year = models.CharField(max_length=20, blank=True)
    baseline_value = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    target_year = models.CharField(max_length=20, blank=True)
    target_reduction = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    target_value = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    unit = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_kpi_plant_targets'
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='updated_kpi_plant_targets'
    )

    class Meta:
        unique_together = ['kpi', 'plant']
        ordering = ['kpi', 'plant']

    def __str__(self):
        return f"{self.kpi.name} - {self.plant.name}"

    def save(self, *args, **kwargs):
        """Auto-calculate target_value from reduction if not provided."""
        self.baseline_value = _to_decimal(self.baseline_value, 'baseline_value')
        self.target_reduction = _to_decimal(self.target_reduction, 'target_reduction')

        if self.baseline_value and self.target_reduction:
            self.target_value = self.baseline_value * (1 - (self.target_reduction / Decimal('100')))
        elif self.target_value not in (None, ''):
            self.target_value = _to_decimal(self.target_value, 'target_value')

        super().save(*args, **kwargs)