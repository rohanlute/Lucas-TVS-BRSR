from django import forms
from django.core.exceptions import ValidationError
from .models import Unit

class UnitCategoryForm(forms.ModelForm):
    """Form for creating/editing a unit category"""
    
    class Meta:
        model = Unit
        fields = ['category', 'icon']
        widgets = {
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Length, Weight, Energy',
                'required': True,
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 📏, ⚖️, ⚡',
                'maxlength': 50,
            }),
        }
        labels = {
            'category': 'Category Name',
            'icon': 'Icon',
        }
        help_texts = {
            'category': 'Enter a unique name for the unit category.',
            'icon': 'Use an emoji or icon code for the category.',
        }
        error_messages = {
            'category': {
                'required': 'Category name is required.',
            },
        }
    
    def clean_category(self):
        """Validate that category name is unique and not empty"""
        category = self.cleaned_data.get('category')
        
        # Check if category is empty
        if not category or not category.strip():
            raise ValidationError('Category name is required.')
        
        # Clean the category name
        category = category.strip()
        instance = getattr(self, 'instance', None)
        
        # Check if category already exists (excluding current instance)
        queryset = Unit.objects.filter(
            category__iexact=category,
            parent__isnull=True
        )
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        
        if queryset.exists():
            raise ValidationError(f'A category with the name "{category}" already exists.')
        
        return category
    
    def clean_icon(self):
        """Clean icon field"""
        icon = self.cleaned_data.get('icon', '').strip()
        # Return default icon if empty, otherwise return the cleaned icon
        return icon if icon else '📐'
    
    def save(self, commit=True):
        """Override save to ensure icon is set"""
        instance = super().save(commit=False)
        if not instance.icon:
            instance.icon = '📐'
        if commit:
            instance.save()
        return instance