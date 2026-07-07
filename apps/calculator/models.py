from django.db import models

class Unit(models.Model):
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )

    category = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, blank=True)
    icon = models.CharField(max_length=50,blank=True)
    conversion_factor = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=1
    )
    is_base_unit = models.BooleanField(default=False)

    def _str_(self):
        return self.name