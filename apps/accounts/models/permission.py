from django.contrib.auth.models import AbstractUser
from django.db import models

class Permissions(models.Model):
    """Permission Master with Module Hierarchy - 5 Modules Only"""
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    module_name = models.TextField(blank=True, null=True)
    permission_type = models.CharField(
        max_length=20,
        choices=[
            ('MODULE_ACCESS', 'Module Access'),
            ('CREATE', 'Create'),
            ('EDIT', 'Edit'),
            ('VIEW', 'View'),
            ('DELETE', 'Delete'),
            ('APPROVE', 'Approve'),
            ('CLOSE', 'Close'),
            ('MANAGE', 'Manage'),
            ('EXPORT', 'Export'),
        ],
        default='VIEW',
        help_text="Type of permission"
    )
    display_order = models.IntegerField(default=0, help_text="Order to display in UI (lower = first)")

    class Meta:
        ordering = ['name', 'display_order', 'code']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def is_module_access(self):
        """Check if this is a module access permission"""
        return self.permission_type == 'MODULE_ACCESS'