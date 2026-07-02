from django.db import models

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    iso_code = models.CharField(max_length=5, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Countries"

        indexes = [
            models.Index(fields=['iso_code']),
        ]

    def __str__(self):
        return self.name


class State(models.Model):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="states"
    )
    name = models.CharField(max_length=100)
    state_code = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

        unique_together = (
            ('country', 'name'),
            ('country', 'state_code'),
        )

        indexes = [
            models.Index(fields=['country']),
            models.Index(fields=['state_code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.country.name})"


class City(models.Model):

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="cities"
    )

    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name="cities"
    )

    name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

        unique_together = (
            ('country', 'state', 'name'),
        )

        indexes = [
            models.Index(fields=['country']),
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Company(models.Model):
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    company_code = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    about_company = models.TextField(blank=True, null=True)
    company_password_hash = models.CharField(max_length=128, blank=True, null=True)
    billing_address = models.TextField(blank=True, null=True)
    billing_zip_code = models.CharField(max_length=20, blank=True, null=True)
    billing_country = models.ForeignKey(Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies"
    )
    billing_state = models.ForeignKey(State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies"
    )
    billing_city = models.ForeignKey(City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies"
    )
    contact_person = models.CharField(max_length=255)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15)
    address = models.TextField(blank=True, null=True)
    industry_type = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    module_access_brsr = models.BooleanField(default=False)
    module_access_gri = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_code} - {self.company_name}"