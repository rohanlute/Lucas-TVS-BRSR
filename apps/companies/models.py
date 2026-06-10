from django.db import models


class Company(models.Model):

    company_code = models.CharField(
        max_length=20,
        unique=True
    )

    company_name = models.CharField(
        max_length=255
    )

    contact_person = models.CharField(
        max_length=255
    )

    email = models.EmailField()

    mobile_number = models.CharField(
        max_length=15
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    industry_type = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    website = models.URLField(
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.company_code} - {self.company_name}"