from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
import re

from ..companies.models import Country,State,City
# apps/organizations/models.py

class Plant(models.Model):
    """Manufacturing Plant/Unit"""
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    country = models.ForeignKey(Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plants"
    )

    state = models.ForeignKey(State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plants"
    )

    city = models.ForeignKey(City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plants"
    )
    pincode = models.CharField(max_length=10)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="created_plants")
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Plant'
        verbose_name_plural = 'Plants'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def clean(self):
        if self.code:
            self.code = self.code.upper()
    
    @property
    def zone_count(self):
        return self.zones.count()
    
    @property
    def active_zone_count(self):
        return self.zones.filter(is_active=True).count()
    
    @property
    def location_count(self):
        """Get count of all locations through zones"""
        from django.db.models import Count
        return Location.objects.filter(zone__plant=self).count()
    
    @property
    def active_location_count(self):
        """Get count of active locations through zones"""
        return Location.objects.filter(zone__plant=self, is_active=True).count()
    
    @property
    def sublocation_count(self):
        """Get count of all sublocations through zones and locations"""
        from .models import SubLocation
        return SubLocation.objects.filter(location__zone__plant=self).count()
    
    @property
    def active_sublocation_count(self):
        """Get count of active sublocations through zones and locations"""
        from .models import SubLocation
        return SubLocation.objects.filter(location__zone__plant=self, is_active=True).count()

class Zone(models.Model):
    """Zones within a Plant (e.g., Zone A, Zone B)"""
    
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sequence = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['plant','sequence', 'name']
        unique_together = ['plant', 'code']
        verbose_name = 'Zone'
        verbose_name_plural = 'Zones'
    
    def __str__(self):
        return f"{self.plant.name} - {self.name}"
    
    def clean(self):
        # Convert code to uppercase
        if self.code:
            self.code = self.code.upper()
    
    def save(self, *args, **kwargs):
        if self.name:
            match = re.search(r'\d+', self.name)
            if match:
                self.sequence = int(match.group())
            else:
                self.sequence = 0
        super().save(*args, **kwargs)

    @property
    def location_count(self):
        return self.locations.count()
    
    @property
    def active_location_count(self):
        return self.locations.filter(is_active=True).count()


class Location(models.Model):
    """Locations within a Zone"""
    
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['zone', 'name']
        unique_together = ['zone', 'code']
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
    
    def __str__(self):
        return f"{self.zone.plant.name} - {self.zone.name} - {self.name}"
    
    def clean(self):
        # Convert code to uppercase
        if self.code:
            self.code = self.code.upper()
    
    @property
    def plant(self):
        """Get the plant through zone"""
        return self.zone.plant

class SubLocation(models.Model):
    """Sub-locations within a Location"""
    
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='sublocations')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50,blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['location', 'name']
        verbose_name = 'Sub-Location'
        verbose_name_plural = 'Sub-Locations'
    
    def __str__(self):
        return f"{self.location.zone.plant.name} - {self.location.zone.name} - {self.location.name} - {self.name}"
    
    def clean(self):
        # Convert code to uppercase
        if self.code:
            self.code = self.code.upper()
    
    @property
    def plant(self):
        """Get the plant through location -> zone"""
        return self.location.zone.plant
    
    @property
    def zone(self):
        """Get the zone through location"""
        return self.location.zone
    
class FinancialYear(models.Model):
    financial_year = models.CharField(
        max_length=9,
        unique=True,
        help_text="Example: 2022-2023"
    )
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.financial_year

    def clean(self):
        # Ensure end date is after start date
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date.")

        # Validate financial year format
        try:
            start_year, end_year = map(int, self.financial_year.split("-"))
        except ValueError:
            raise ValidationError(
                "Financial year must be in the format YYYY-YYYY (e.g., 2022-2023)."
            )

        if end_year != start_year + 1:
            raise ValidationError(
                "Financial year must span consecutive years (e.g., 2022-2023)."
            )

        # Validate dates match the financial year
        if (
            self.start_date.year != start_year
            or self.end_date.year != end_year
        ):
            raise ValidationError(
                "Start and end dates must match the financial year."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class FinancialMonth(models.Model):

    MONTH_CHOICES = [
        (1, "April"),
        (2, "May"),
        (3, "June"),
        (4, "July"),
        (5, "August"),
        (6, "September"),
        (7, "October"),
        (8, "November"),
        (9, "December"),
        (10, "January"),
        (11, "February"),
        (12, "March"),
    ]

    month_number = models.PositiveSmallIntegerField(
        unique=True
    )

    month_code = models.CharField(
        max_length=5,
        unique=True
    )

    month_name = models.CharField(
        max_length=20
    )

    quarter = models.CharField(
        max_length=2
    )

    half_year = models.CharField(
        max_length=2
    )

    display_order = models.PositiveSmallIntegerField(
        default=1
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "org_financial_month"
        ordering = ["display_order"]
        verbose_name = "Financial Month"
        verbose_name_plural = "Financial Months"

    def __str__(self):
        return self.month_name


class ApprovalConfigurationTemplate(models.Model):
    """
    Company-scoped workflow configuration definition for configurable workflow flows.
    """

    FRAMEWORK_CHOICES = [
        ("BRSR", "BRSR"),
        ("GRI", "GRI"),
        ("EMISSION", "Emission"),
        ("OTHER", "Other"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="workflow_configuration_templates",
    )
    framework = models.CharField(max_length=50, choices=FRAMEWORK_CHOICES, default="BRSR")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__company_name", "framework", "name"]
        unique_together = ("company", "framework", "name")

    def __str__(self):
        return f"{self.company} - {self.name}"

    @property
    def stage_count(self):
        return self.stages.count()

    @property
    def first_stage(self):
        return self.stages.order_by("level").first()


class ApprovalConfigurationStage(models.Model):
    STAGE_TYPE_CHOICES = [
        ("question_assignment","Question Assignment"),
        ("data_entry", "Data Entry"),
        ("review", "Review"),
        ("approval", "Approval"),
        ("pre_final_approval", "Pre-Final Approval"),
        ("final_approval", "Final Approval"),
    ]

    template = models.ForeignKey(ApprovalConfigurationTemplate, on_delete=models.CASCADE, related_name="stages",)
    level = models.PositiveIntegerField()
    label = models.CharField(max_length=100)
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPE_CHOICES)
    role = models.ForeignKey("accounts.Role", on_delete=models.PROTECT, related_name="workflow_configuration_stages",)
    can_approve = models.BooleanField(default=True)
    can_reject = models.BooleanField(default=True)
    can_reassign = models.BooleanField(default=False)
    can_escalate = models.BooleanField(default=False)
    due_days = models.PositiveIntegerField(null=True, blank=True)
    escalation_role = models.ForeignKey( "accounts.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",)   

    class Meta:
        ordering = ["template", "level"]
        unique_together = ("template", "level")

    def __str__(self):
        return f"{self.template.name} - L{self.level}: {self.label}"

    def next_stage(self):
        return (
            ApprovalConfigurationStage.objects.filter(template=self.template, level__gt=self.level)
            .order_by("level")
            .first()
        )

    def previous_stage(self):
        return (
            ApprovalConfigurationStage.objects.filter(template=self.template, level__lt=self.level)
            .order_by("-level")
            .first()
        )


class ApprovalConfigurationTask(models.Model):

    template = models.ForeignKey(
        ApprovalConfigurationTemplate,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    current_stage = models.ForeignKey(
        ApprovalConfigurationStage,
        on_delete=models.PROTECT,
        related_name="+",
    )

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
    )
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey("target_content_type", "target_object_id")

    current_assignee_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
    )
    current_assignee_object_id = models.PositiveIntegerField()
    current_assignee = GenericForeignKey(
        "current_assignee_content_type",
        "current_assignee_object_id",
    )

    is_completed = models.BooleanField(default=False)
    is_returned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["current_assignee_content_type", "current_assignee_object_id"]),
            models.Index(fields=["is_completed", "is_returned"]),
        ]

    def __str__(self):
        return f"Task[{self.target}] @ {self.current_stage}"

    @property
    def is_overdue(self):
        due_days = self.current_stage.due_days
        if not due_days:
            return False
        return self.created_at and self.created_at + timedelta(days=due_days) < timezone.now()


class ApprovalConfigurationTaskLog(models.Model):
    ACTION_CHOICES = [
        ("submit", "Submit"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("reassign", "Reassign"),
        ("escalate", "Escalate"),
    ]

    task = models.ForeignKey(ApprovalConfigurationTask, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    from_stage = models.ForeignKey(
        ApprovalConfigurationStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_stage = models.ForeignKey(
        ApprovalConfigurationStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_object_id = models.PositiveIntegerField(null=True, blank=True)
    actor = GenericForeignKey("actor_content_type", "actor_object_id")
    remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.task_id} - {self.action}"
