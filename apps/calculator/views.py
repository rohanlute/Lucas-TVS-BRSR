from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Unit
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from decimal import Decimal
from .models import Unit
from .forms import UnitCategoryForm
from .forms import UnitCategoryForm

class UnitCategoryListView(LoginRequiredMixin, ListView):
    """List all unit categories with unit counts"""
    model = Unit
    template_name = 'calculator/unit_category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    
    def get_queryset(self):
        # Get distinct categories with unit counts (only parent units)
        queryset = Unit.objects.filter(
            parent__isnull=True
        ).annotate(
            unit_count=Count('children', distinct=True)
        ).order_by('category')
        
        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(category__icontains=search_query) |
                Q(icon__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class UnitCategoryCreateView(LoginRequiredMixin, CreateView):
    """Create a new unit category with units"""
    model = Unit
    template_name = 'calculator/unit_category_form.html'
    form_class = UnitCategoryForm
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['units'] = []  # No units for new category
        return context
    
    def form_valid(self, form):
        # Save the category first
        response = super().form_valid(form)
        
        # Process units from the form
        self.process_units()
        
        unit_count = getattr(self, '_unit_count', 0)
        messages.success(
            self.request, 
            f'Category "{form.instance.category}" created successfully with {unit_count} unit(s)!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def process_units(self):
        """Process units from POST data"""
        unit_count = 0
        
        for key, value in self.request.POST.items():
            if key.startswith('unit_') and key.endswith('_name'):
                prefix = key.replace('_name', '')
                
                name = value
                symbol = self.request.POST.get(f'{prefix}_symbol', '')
                conversion_factor = self.request.POST.get(f'{prefix}_conversion_factor', 1)
                is_base_unit = self.request.POST.get(f'{prefix}_is_base_unit', 'false') == 'true'
                
                # Only create if name is provided
                if name and name.strip():
                    Unit.objects.create(
                        parent=self.object,
                        category=self.object.category,
                        name=name.strip(),
                        symbol=symbol,
                        conversion_factor=conversion_factor,
                        is_base_unit=is_base_unit
                    )
                    unit_count += 1
        
        self._unit_count = unit_count


class UnitCategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing unit category with units"""
    model = Unit
    template_name = 'calculator/unit_category_form.html'
    form_class = UnitCategoryForm
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_queryset(self):
        return Unit.objects.filter(parent__isnull=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['units'] = self.object.children.all().order_by('id')
        return context
    
    def form_valid(self, form):
        # Save the category first
        response = super().form_valid(form)
        
        # Process units from the form
        self.process_units()
        
        messages.success(self.request, f'Category "{form.instance.category}" updated successfully!')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def process_units(self):
        """Process units from POST data - create, update, delete"""
        existing_unit_ids = set()
        
        for key, value in self.request.POST.items():
            if key.startswith('unit_') and key.endswith('_name'):
                prefix = key.replace('_name', '')
                unit_id = prefix.replace('unit_', '')
                
                name = value
                symbol = self.request.POST.get(f'{prefix}_symbol', '')
                conversion_factor = self.request.POST.get(f'{prefix}_conversion_factor', 1)
                is_base_unit = self.request.POST.get(f'{prefix}_is_base_unit', 'false') == 'true'
                
                # Skip if name is empty
                if not name or not name.strip():
                    continue
                
                if unit_id.startswith('new_'):
                    # New unit
                    Unit.objects.create(
                        parent=self.object,
                        category=self.object.category,
                        name=name.strip(),
                        symbol=symbol,
                        conversion_factor=conversion_factor,
                        is_base_unit=is_base_unit
                    )
                else:
                    # Update existing unit
                    try:
                        unit = Unit.objects.get(id=unit_id, parent=self.object)
                        unit.name = name.strip()
                        unit.symbol = symbol
                        unit.conversion_factor = conversion_factor
                        unit.is_base_unit = is_base_unit
                        unit.save()
                        existing_unit_ids.add(int(unit_id))
                    except Unit.DoesNotExist:
                        pass
        
        # Delete units that were removed (not in the POST data)
        for unit in self.object.unit_set.all():
            if unit.id not in existing_unit_ids:
                unit.delete()


class UnitCategoryDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a unit category"""
    model = Unit
    template_name = 'calculator/category_delete.html'
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_queryset(self):
        return Unit.objects.filter(parent__isnull=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unit_count'] = self.object.children.count()
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        category_name = self.object.category
        unit_count = self.object.children.count()
        
        # Delete all child units first (cascade will handle it)
        self.object.delete()
        
        if unit_count > 0:
            messages.success(
                request, 
                f'Category "{category_name}" and {unit_count} associated unit(s) deleted successfully!'
            )
        else:
            messages.success(request, f'Category "{category_name}" deleted successfully!')
        
        return redirect(self.success_url)

# ================================================================
# CRUD Views for Unit Categories
# ================================================================

class UnitCategoryListView(LoginRequiredMixin, ListView):
    """List all unit categories with unit counts"""
    model = Unit
    template_name = 'calculator/unit_category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Unit.objects.filter(
            parent__isnull=True
        ).annotate(
            unit_count=Count('children', distinct=True)
        ).order_by('category')
        
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(category__icontains=search_query) |
                Q(icon__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class UnitCategoryCreateView(LoginRequiredMixin, CreateView):
    """Create a new unit category with units"""
    model = Unit
    template_name = 'calculator/unit_category_form.html'
    form_class = UnitCategoryForm
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['units'] = []
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        self.process_units()
        unit_count = getattr(self, '_unit_count', 0)
        messages.success(
            self.request, 
            f'Category "{form.instance.category}" created successfully with {unit_count} unit(s)!'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def process_units(self):
        unit_count = 0
        for key, value in self.request.POST.items():
            if key.startswith('unit_') and key.endswith('_name'):
                prefix = key.replace('_name', '')
                name = value
                symbol = self.request.POST.get(f'{prefix}_symbol', '')
                conversion_factor = self.request.POST.get(f'{prefix}_conversion_factor', 1)
                is_base_unit = self.request.POST.get(f'{prefix}_is_base_unit', 'false') == 'true'
                
                if name and name.strip():
                    Unit.objects.create(
                        parent=self.object,
                        category=self.object.category,
                        name=name.strip(),
                        symbol=symbol,
                        conversion_factor=conversion_factor,
                        is_base_unit=is_base_unit
                    )
                    unit_count += 1
        self._unit_count = unit_count


class UnitCategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing unit category with units"""
    model = Unit
    template_name = 'calculator/unit_category_form.html'
    form_class = UnitCategoryForm
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_queryset(self):
        return Unit.objects.filter(parent__isnull=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['units'] = self.object.children.all().order_by('id')
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        self.process_units()
        messages.success(self.request, f'Category "{form.instance.category}" updated successfully!')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def process_units(self):
        existing_unit_ids = set()
        
        for key, value in self.request.POST.items():
            if key.startswith('unit_') and key.endswith('_name'):
                prefix = key.replace('_name', '')
                unit_id = prefix.replace('unit_', '')
                
                name = value
                symbol = self.request.POST.get(f'{prefix}_symbol', '')
                conversion_factor = self.request.POST.get(f'{prefix}_conversion_factor', 1)
                is_base_unit = self.request.POST.get(f'{prefix}_is_base_unit', 'false') == 'true'
                
                if not name or not name.strip():
                    continue
                
                if unit_id.startswith('new_'):
                    Unit.objects.create(
                        parent=self.object,
                        category=self.object.category,
                        name=name.strip(),
                        symbol=symbol,
                        conversion_factor=conversion_factor,
                        is_base_unit=is_base_unit
                    )
                else:
                    try:
                        unit = self.object.children.get(id=unit_id)
                        unit.name = name.strip()
                        unit.symbol = symbol
                        unit.conversion_factor = conversion_factor
                        unit.is_base_unit = is_base_unit
                        unit.save()
                        existing_unit_ids.add(int(unit_id))
                    except Unit.DoesNotExist:
                        pass
        
        for unit in self.object.children.all():
            if unit.id not in existing_unit_ids:
                unit.delete()


class UnitCategoryDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a unit category"""
    model = Unit
    template_name = 'calculator/category_delete.html'
    success_url = reverse_lazy('calculator:unit_category_list')
    
    def get_queryset(self):
        return Unit.objects.filter(parent__isnull=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unit_count'] = self.object.children.count()
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        category_name = self.object.category
        unit_count = self.object.children.count()
        self.object.delete()
        
        if unit_count > 0:
            messages.success(
                request, 
                f'Category "{category_name}" and {unit_count} associated unit(s) deleted successfully!'
            )
        else:
            messages.success(request, f'Category "{category_name}" deleted successfully!')
        
        return redirect(self.success_url)


# ================================================================
# API Views for the Converter Modal
# ================================================================

class GetCategoriesView(LoginRequiredMixin, View):
    """Get all categories for the sidebar"""
    
    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        try:
            categories = Unit.objects.filter(
                parent__isnull=True
            ).order_by('category')
            
            # Define icons for categories
            category_icons = {
                'Length/Distance': '📏',
                'Weight/Mass': '⚖️',
                'Volume': '🧪',
                'Energy': '⚡',
                'Temperature': '🌡️',
                'Area': '📐',
                'Speed': '🚀',
                'Time': '⏱️'
            }
            
            categories_data = []
            for cat in categories:
                icon = cat.icon if cat.icon else category_icons.get(cat.category, '📐')
                categories_data.append({
                    'id': cat.id,
                    'name': cat.category,
                    'icon': icon
                })
            
            return JsonResponse({
                'success': True,
                'categories': categories_data
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class GetCategoryDataView(LoginRequiredMixin, View):
    """Get all data for a specific category"""
    
    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        category_id = request.GET.get('category')
        
        if not category_id:
            return JsonResponse({'success': False, 'error': 'Category ID required'}, status=400)
        
        try:
            # Get the category (parent unit)
            category = Unit.objects.get(id=category_id, parent__isnull=True)
            
            # Get all child units
            units = category.children.all().order_by('name')
            
            if not units.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No units found for this category'
                })
            
            # Prepare units data
            units_data = []
            for unit in units:
                units_data.append({
                    'id': unit.id,
                    'name': unit.name,
                    'symbol': unit.symbol or '',
                    'conversion_factor': float(unit.conversion_factor),
                    'is_base_unit': unit.is_base_unit
                })
            
            # Auto-detect: Show table if category has more than 2 units
            has_table = units.count() > 2
            
            table_data = None
            table_units = None
            
            if has_table:
                # Build conversion table with error handling
                table_data = []
                table_units = list(units.values_list('name', flat=True))
                
                for from_unit in units:
                    row = {
                        'unit': from_unit.name,
                        'values': []
                    }
                    
                    for to_unit in units:
                        try:
                            # Skip if conversion factor is zero
                            if to_unit.conversion_factor == 0:
                                row['values'].append(0)
                                continue
                            
                            # Convert from_unit to to_unit
                            if from_unit.is_base_unit:
                                value_in_base = Decimal(1)
                            else:
                                value_in_base = Decimal(1) * from_unit.conversion_factor
                            
                            if to_unit.is_base_unit:
                                result = value_in_base
                            else:
                                result = value_in_base / to_unit.conversion_factor
                            
                            row['values'].append(float(result))
                        except (ZeroDivisionError, decimal.DivisionByZero):
                            # Handle division by zero
                            row['values'].append(0)
                        except Exception as e:
                            # Handle any other errors
                            print(f"Error converting {from_unit.name} to {to_unit.name}: {e}")
                            row['values'].append(0)
                    
                    table_data.append(row)
            
            return JsonResponse({
                'success': True,
                'category_name': category.category,
                'category_icon': category.icon or '📐',
                'units': units_data,
                'has_table': has_table,
                'table_data': table_data,
                'table_units': table_units
            })
            
        except Unit.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Category not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

class GetConversionView(LoginRequiredMixin, View):
    """Get conversion result for a category"""
    
    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        category_id = request.GET.get('category')
        amount = float(request.GET.get('amount', 1))
        from_unit_name = request.GET.get('from_unit', '')
        to_unit_name = request.GET.get('to_unit', '')
        precision = int(request.GET.get('precision', 4))
        
        if not category_id or not from_unit_name or not to_unit_name:
            return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)
        
        try:
            # Get the category
            category = Unit.objects.get(id=category_id, parent__isnull=True)
            
            # Get from and to units
            from_unit = category.children.filter(name=from_unit_name).first()
            to_unit = category.children.filter(name=to_unit_name).first()
            
            if not from_unit or not to_unit:
                return JsonResponse({
                    'success': False,
                    'error': 'Unit not found'
                })
            
            # Convert
            if from_unit.is_base_unit:
                value_in_base = Decimal(str(amount))
            else:
                value_in_base = Decimal(str(amount)) * from_unit.conversion_factor
            
            if to_unit.is_base_unit:
                result = value_in_base
            else:
                result = value_in_base / to_unit.conversion_factor
            
            return JsonResponse({
                'success': True,
                'result': round(float(result), precision),
                'from_unit': from_unit.name,
                'to_unit': to_unit.name
            })
            
        except Unit.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Category not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })