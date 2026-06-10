from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    employee_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    mobile_number = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )

    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True
    )

    is_company_user = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.username
    
    @property
    def is_super_admin(self):
        return (
            self.role and
            self.role.role_code == 'SUPERADMIN'
        )


    @property
    def is_company_admin(self):
        return (
            self.role and
            self.role.role_code == 'COMPANYADMIN'
        )


    @property
    def is_company_user_role(self):
        return (
            self.role and
            self.role.role_code == 'COMPANYUSER'
        )