from django.db import models
from apps.calculator.models import Unit
from ..companies.models import Company
from config import settings
from ..organizations.models import FinancialYear,FinancialMonth,Plant
from decimal import Decimal
from django.utils import timezone

class EmissionScope(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "env_emission_scope"
        ordering = ["display_order"]
        verbose_name = "Emission Scope"
        verbose_name_plural = "Emission Scopes"

    def __str__(self):
        return self.name
    


class EmissionCategory(models.Model):
    scope = models.ForeignKey(
        EmissionScope,
        on_delete=models.PROTECT,
        related_name="categories"
    )

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "env_emission_category"
        ordering = ["scope", "display_order"]

        constraints = [
            models.UniqueConstraint(
                fields=["scope", "code"],
                name="uq_emission_category_scope_code"
            )
        ]

        verbose_name = "Emission Category"
        verbose_name_plural = "Emission Categories"

    def __str__(self):
        return f"{self.scope.name} - {self.name}"


class EmissionActivity(models.Model):

    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT,
        related_name="activities"
    )

    code = models.CharField(max_length=30,unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="emission_activities"
    )

    requires_emission_factor = models.BooleanField(
        default=True,
        help_text="Whether this activity requires emission factor calculation."
    )
    allow_manual_entry = models.BooleanField(default=True)
    allow_excel_import = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "env_emission_activity"
        ordering = [
            "category",
            "display_order",
            "name"
        ]
        verbose_name = "Emission Activity"
        verbose_name_plural = "Emission Activities"

    def __str__(self):
        return f"{self.category.name} - {self.name}"
    

class EmissionSource(models.Model):

    activity = models.ForeignKey(
        EmissionActivity,
        on_delete=models.CASCADE,
        related_name="sources"
    )

    source_code = models.CharField(
        max_length=30
    )

    source_name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    display_order = models.PositiveIntegerField(
        default=1
    )

    class Meta:

        db_table = "env_emission_source"

        ordering = [
            "activity",
            "display_order"
        ]

        unique_together = (
            "activity",
            "source_code",
        )

    def __str__(self):

        return f"{self.activity.name} - {self.source_name}"



class EmissionFactor(models.Model):

    activity = models.ForeignKey(
        EmissionActivity,
        on_delete=models.PROTECT,
        related_name="emission_factors"
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="emission_factors"
    )

    emission_factor = models.DecimalField(max_digits=20,decimal_places=10)
    source = models.CharField(max_length=255)
    version = models.CharField(max_length=50,blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True,blank=True)
    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "env_emission_factor"
        ordering = ["activity", "-effective_from"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "activity",
                    "unit",
                    "effective_from"
                ],
                name="uq_emission_factor"
            )
        ]

        indexes = [
            models.Index(fields=["activity"]),
            models.Index(fields=["effective_from"]),
            models.Index(fields=["is_active"]),
        ]

        verbose_name = "Emission Factor"
        verbose_name_plural = "Emission Factors"

    def __str__(self):
        return (
            f"{self.activity.name} | "
            f"{self.unit.symbol} | "
            f"{self.emission_factor}"
        )
    



class EmissionTransaction(models.Model):

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    SOURCE_CHOICES = [
        ("MANUAL", "Manual Entry"),
        ("EXCEL", "Excel Import"),
        ("API", "API"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="emission_transactions"
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="emission_transactions"
    )

    financial_year = models.ForeignKey(
        FinancialYear,
        on_delete=models.PROTECT,
        related_name="emission_transactions"
    )

    financial_month = models.ForeignKey(
        FinancialMonth,
        on_delete=models.PROTECT,
        related_name="emission_transactions"
    )

    activity = models.ForeignKey(
        EmissionActivity,
        on_delete=models.PROTECT,
        related_name="transactions"
    )

    source = models.ForeignKey(
        EmissionSource,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="emission_transactions"
    )

    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=4
    )

    emission_factor = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=0
    )

    emission_factor_source = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions"
    )
        
    total_emission = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    entry_source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="MANUAL"
    )

    remarks = models.TextField(
        blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_emission_transactions"
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_emission_transactions"
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_emission_transactions"
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        db_table = "env_emission_transaction"

        ordering = [
            "-financial_year",
            "financial_month",
            "plant",
            "activity",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "plant",
                    "financial_year",
                    "financial_month",
                    "activity",
                    "source",
                ],
                name="uq_env_transaction"
            )
        ]

        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["plant"]),
            models.Index(fields=["financial_year"]),
            models.Index(fields=["financial_month"]),
            models.Index(fields=["activity"]),
            models.Index(fields=["status"]),
        ]

        verbose_name = "Emission Transaction"
        verbose_name_plural = "Emission Transactions"

    def calculate_emission(self):

        factor = (
            EmissionFactor.objects.filter(
                activity=self.activity,
                unit=self.unit,
                is_active=True,
                effective_from__lte=timezone.now().date(),
            )
            .order_by("-effective_from")
            .first()
        )

        if not factor:
            raise ValueError(
                f"No active emission factor found for '{self.activity.name}'."
            )

        self.emission_factor = factor.emission_factor
        self.emission_factor_source = factor

        self.total_emission = (Decimal(self.quantity) * Decimal(factor.emission_factor))


    def save(self, *args, **kwargs):

        self.calculate_emission()

        super().save(*args, **kwargs)


    def __str__(self):

        return (
            f"{self.company.company_name} | "
            f"{self.plant.name} | "
            f"{self.financial_year} | "
            f"{self.financial_month.month_name} | "
            f"{self.activity.name}"
        )

