from django.db import models
from apps.calculator.models import Unit

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
        unique_together = ("scope", "code")
        verbose_name = "Emission Category"
        verbose_name_plural = "Emission Categories"

    def __str__(self):
        return self.name
    



class EmissionActivity(models.Model):

    category = models.ForeignKey(
        EmissionCategory,
        on_delete=models.PROTECT,
        related_name="activities"
    )

    code = models.CharField(
        max_length=30,
        unique=True
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    default_unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="emission_activities"
    )

    allow_manual_entry = models.BooleanField(
        default=True
    )

    allow_excel_import = models.BooleanField(
        default=True
    )

    display_order = models.PositiveIntegerField(
        default=1
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        db_table = "env_emission_activity"
        ordering = ["category", "display_order"]
        verbose_name = "Emission Activity"
        verbose_name_plural = "Emission Activities"

    def __str__(self):
        return self.name