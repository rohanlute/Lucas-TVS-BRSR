from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView,DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Count
# from apps.accounts.views import AdminRequiredMixin
from django.http import JsonResponse
from django.views import View
from .models import *
from .forms import *
from django.forms import ValidationError
from .models import Plant, Zone, Location
from django.db.models import F
from django.db.models.functions import Cast,Substr
from django.db.models import IntegerField
from django.db.models.functions import Lower
from django.db.models import Case, When, IntegerField, Value
from django.db.models.functions import Cast, Substr
from .models import FinancialYear
from .forms import FinancialYearForm
from django.db import transaction
from apps.companies.models import Company
from .workflow_configuration_engine import WorkflowConfigurationEngine

class CanAccessOrganizationMixin(UserPassesTestMixin):

    def test_func(self):
        user = self.request.user

        if not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if not user.role:
            return False

        return user.role.permissions.filter(code="ACCESS_ORGANIZATIONS_MODULE").exists()

    def get_allowed_plants(self):
        user = self.request.user

        if user.is_superuser:
            return Plant.objects.all()

        if getattr(user, 'is_super_admin', False):
            return Plant.objects.all()

        if user.role and user.role.role_code == 'COMPANYADMIN':
            return Plant.objects.filter(created_by__company=user.company).distinct()

        return user.assigned_plants.filter(is_active=True)

    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access this module.')
        return redirect('accounts:dashboard')
    
class OrganizationDashboardView(LoginRequiredMixin, CanAccessOrganizationMixin, TemplateView):
    template_name = 'organizations/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allowed_plants = self.get_allowed_plants()

        # Plants
        context['total_plants'] = allowed_plants.count()
        context['active_plants'] = allowed_plants.filter(is_active=True).count()

        # Zones
        zones = Zone.objects.filter(plant__in=allowed_plants)
        context['total_zones'] = zones.count()
        context['active_zones'] = zones.filter(is_active=True).count()

        # Locations
        locations = Location.objects.filter(zone__plant__in=allowed_plants)
        context['total_locations'] = locations.count()
        context['active_locations'] = locations.filter(is_active=True).count()

        # Sub-Locations
        sublocations = SubLocation.objects.filter(location__zone__plant__in=allowed_plants)
        context['total_sublocations'] = sublocations.count()
        context['active_sublocations'] = sublocations.filter(is_active=True).count()

        return context

# ==================== PLANT VIEWS ====================

class PlantListView(LoginRequiredMixin, CanAccessOrganizationMixin, ListView):
    """List all plants"""
    model = Plant
    template_name = 'organizations/plant_list.html'
    context_object_name = 'plants'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role.role_code=='SUPREADMIN':
            queryset = Plant.objects.all()
        else:
            if user.company:
                queryset = Plant.objects.filter(Q(created_by=user) | Q(created_by__company=user.company)).distinct()
            else:
                queryset = Plant.objects.filter(created_by=user)

        queryset = queryset.annotate(
            zones_count=Count('zones', distinct=True),
            locations_count=Count('zones__locations', distinct=True),
            sublocations_count=Count('zones__locations__sublocations', distinct=True)
        )
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(country__name__icontains=search) |
                Q(state__name__icontains=search) |
                Q(city__name__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class PlantCreateView(LoginRequiredMixin, CanAccessOrganizationMixin, CreateView):
    """Create new plant"""
    model = Plant
    form_class = PlantForm
    template_name = 'organizations/plant_form.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Plant {form.instance.name} created successfully!')
        return super().form_valid(form)


class PlantUpdateView(LoginRequiredMixin, CanAccessOrganizationMixin, UpdateView):
    """Update plant"""
    model = Plant
    form_class = PlantForm
    template_name = 'organizations/plant_form.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Plant {form.instance.name} updated successfully!')
        return super().form_valid(form)


class PlantDeleteView(LoginRequiredMixin, CanAccessOrganizationMixin,  DeleteView):
    """Delete plant"""
    model = Plant
    template_name = 'organizations/plant_confirm_delete.html'
    success_url = reverse_lazy('organizations:plant_list')
    
    def delete(self, request, *args, **kwargs):
        plant = self.get_object()
        messages.success(request, f'Plant {plant.name} deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==================== LOCATION VIEWS ====================
from django.http import JsonResponse
from django.views import View

class GetZonesForPlantView(LoginRequiredMixin, CanAccessOrganizationMixin,  TemplateView):
    """AJAX view to get zones for a selected plant"""
    
    def get(self, request, *args, **kwargs):
        plant_id = request.GET.get('plant_id')
        # Ensure the plant belongs to user's allowed plants (company scope)
        allowed_plants = self.get_allowed_plants()
        if not allowed_plants.filter(id=plant_id).exists():
            return JsonResponse([], safe=False)

        zones = Zone.objects.filter(plant_id=plant_id, is_active=True).values('id', 'name', 'code')
        return JsonResponse(list(zones), safe=False)
    
class GetLocationsForZoneAjaxView(LoginRequiredMixin, View):
    """AJAX view to get locations for selected zone"""
    
    def get(self, request):
        zone_id = request.GET.get('zone_id')
        allowed_plants = self.request.user and getattr(self.request.user, 'company', None)
        if self.request.user.is_superuser or (self.request.user.role and self.request.user.role.name == 'ADMIN'):
            locations = Location.objects.filter(zone_id=zone_id, is_active=True).values('id', 'name', 'code')
            return JsonResponse(list(locations), safe=False)

        zone = Zone.objects.filter(id=zone_id, plant__created_by__company=self.request.user.company).first()
        if not zone:
            return JsonResponse([], safe=False)

        locations = Location.objects.filter(zone_id=zone_id, is_active=True).values('id', 'name', 'code')
        return JsonResponse(list(locations), safe=False)


class GetSubLocationsAjaxView(LoginRequiredMixin, View):
    """AJAX view to get sublocations for selected location"""
    
    def get(self, request):
        location_id = request.GET.get('location_id')
        # Allow admins to fetch any sublocations
        if self.request.user.is_superuser or (self.request.user.role and self.request.user.role.name == 'ADMIN'):
            sublocations = SubLocation.objects.filter(location_id=location_id, is_active=True).values('id', 'name', 'code')
            return JsonResponse(list(sublocations), safe=False)

        loc = Location.objects.filter(id=location_id, zone__plant__created_by__company=self.request.user.company).first()
        if not loc:
            return JsonResponse([], safe=False)

        sublocations = SubLocation.objects.filter(location_id=location_id, is_active=True).values('id', 'name', 'code')
        return JsonResponse(list(sublocations), safe=False)  
    
class LocationListView(LoginRequiredMixin, CanAccessOrganizationMixin, ListView):
    model = Location
    template_name = 'organizations/location_list.html'
    context_object_name = 'locations'
    paginate_by = 20
    
    def get_queryset(self):
        allowed_plants = self.get_allowed_plants()
        queryset = Location.objects.select_related('zone', 'zone__plant').prefetch_related('sublocations')
        queryset = queryset.filter(zone__plant__in=allowed_plants)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(zone__name__icontains=search) |
                Q(zone__plant__name__icontains=search)
            )
        
        plant_id = self.request.GET.get('plant')
        if plant_id:
            queryset = queryset.filter(zone__plant_id=plant_id)
        
        zone_id = self.request.GET.get('zone')
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('zone__plant__name', 'zone__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plants'] = self.get_allowed_plants().filter(is_active=True)
        context['zones'] = Zone.objects.filter(is_active=True).select_related('plant')
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_plant'] = self.request.GET.get('plant', '')
        context['selected_zone'] = self.request.GET.get('zone', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context

class LocationCreateView(LoginRequiredMixin, CanAccessOrganizationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'organizations/location_form.html'
    success_url = reverse_lazy('organizations:location_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plants'] = self.get_allowed_plants().filter(is_active=True)
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        sublocation_count = int(self.request.POST.get('sublocation_count', 0))
        
        for i in range(sublocation_count):
            name = self.request.POST.get(f'sublocation_name_{i}', '').strip()
            code = self.request.POST.get(f'sublocation_code_{i}', '').strip()
            description = self.request.POST.get(f'sublocation_description_{i}', '').strip()
            is_active = self.request.POST.get(f'sublocation_active_{i}') == '1'
            
            if name:  
                SubLocation.objects.create(
                    location=self.object,
                    name=name,
                    code=code.upper() if code else '',
                    description=description,
                    is_active=is_active
                )
        
        messages.success(self.request, f'Location "{self.object.name}" created successfully with {sublocation_count} sub-locations!')
        return response



class LocationUpdateView(LoginRequiredMixin, CanAccessOrganizationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'organizations/location_form.html'
    success_url = reverse_lazy('organizations:location_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plants'] = self.get_allowed_plants().filter(is_active=True)
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Track existing sublocation IDs
        existing_sublocation_ids = []
        
        # Process sublocations
        sublocation_count = int(self.request.POST.get('sublocation_count', 0))
        
        for i in range(sublocation_count):
            sublocation_id = self.request.POST.get(f'sublocation_id_{i}')
            name = self.request.POST.get(f'sublocation_name_{i}', '').strip()
            code = self.request.POST.get(f'sublocation_code_{i}', '').strip()
            description = self.request.POST.get(f'sublocation_description_{i}', '').strip()
            is_active = self.request.POST.get(f'sublocation_active_{i}') == '1'
            
            if name:
                if sublocation_id:
                    # Update existing sublocation
                    try:
                        sublocation = SubLocation.objects.get(id=sublocation_id, location=self.object)
                        sublocation.name = name
                        sublocation.code = code.upper() if code else ''
                        sublocation.description = description
                        sublocation.is_active = is_active
                        sublocation.save()
                        existing_sublocation_ids.append(int(sublocation_id))
                    except SubLocation.DoesNotExist:
                        pass
                else:
                    # Create new sublocation
                    new_sublocation = SubLocation.objects.create(
                        location=self.object,
                        name=name,
                        code=code.upper() if code else '',
                        description=description,
                        is_active=is_active
                    )
                    existing_sublocation_ids.append(new_sublocation.id)
        
        # Delete sublocations that were removed
        SubLocation.objects.filter(location=self.object).exclude(id__in=existing_sublocation_ids).delete()
        
        messages.success(self.request, f'Location "{self.object.name}" updated successfully!')
        return response

class LocationDeleteView(LoginRequiredMixin, DeleteView):
    model = Location
    success_url = reverse_lazy('organizations:location_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Location deleted successfully!')
        return super().delete(request, *args, **kwargs)




# ==================== ZONE VIEWS ====================

class ZoneListView(LoginRequiredMixin, CanAccessOrganizationMixin,  ListView):
    """List all zones"""
    model = Zone
    template_name = 'organizations/zone_list.html'
    context_object_name = 'zones'
    paginate_by = 10
    
    def get_queryset(self):
        allowed_plants = self.get_allowed_plants()
        queryset = Zone.objects.filter(plant__in=allowed_plants).select_related('plant').prefetch_related(
            'locations',
            'locations__sublocations'
        ).annotate(
            total_locations=Count('locations', distinct=True),
            active_locations=Count('locations',filter=Q(locations__is_active=True),distinct=True),
            zone_number=Case(When(name__regex=r'^Zone \d+$',then=Cast(Substr('name', 6), IntegerField())),default=Value(None),output_field=IntegerField()))

        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(plant__name__icontains=search)
            )

        # Filter by plant
        plant = self.request.GET.get('plant')
        if plant:
            queryset = queryset.filter(plant_id=plant,plant__in=allowed_plants)

        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset.order_by('plant__name','sequence','code','name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plants'] = self.get_allowed_plants().filter(is_active=True)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_plant'] = self.request.GET.get('plant', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context



class ZoneCreateView(LoginRequiredMixin, CanAccessOrganizationMixin,  CreateView):
    """Create new zone with locations and sublocations"""
    model = Zone
    form_class = ZoneForm
    template_name = 'organizations/zone_form.html'
    success_url = reverse_lazy('organizations:zone_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['plant'].queryset = self.get_allowed_plants().filter(is_active=True)
        return form
    
    def form_valid(self, form):
        # Save the zone first
        self.object = form.save()
        
        # DEBUG: Print all POST data
        print("=" * 50)
        print("POST DATA:")
        for key, value in self.request.POST.items():
            print(f"{key}: {value}")
        print("=" * 50)
        
        # Process locations
        location_count = int(self.request.POST.get('location_count', 0))
        print(f"Location count: {location_count}")
        
        for i in range(location_count):
            location_name = self.request.POST.get(f'location_name_{i}', '').strip()
            location_code = self.request.POST.get(f'location_code_{i}', '').strip()
            location_description = self.request.POST.get(f'location_description_{i}', '').strip()
            location_active = self.request.POST.get(f'location_active_{i}') == '1'
            
            # print(f"\nProcessing Location {i}:")
            # print(f"  Name: {location_name}")
            # print(f"  Code: {location_code}")
            # print(f"  Active: {location_active}")
            
            if location_name and location_code:
                # Create location 
                loc_data = {
                    'plant': self.object.plant.id,
                    'zone': self.object.id,
                    'name': location_name,
                    'code': location_code.upper(),
                    'description': location_description,
                    'is_active': location_active,
                }
                
                # Use LocationForm for validation
                loc_form = LocationForm(loc_data)
                if loc_form.is_valid():
                    new_location = loc_form.save()
                    print(f"  ✓ Location created via form: {new_location.id}")
                else:
                    print(f"  ✗ Location skipped due to validation error: {loc_form.errors}")
                    messages.error(self.request, f"Location '{location_name}': {loc_form.errors.as_text()}")

                # Process sublocations for this location
                sublocation_count_input = self.request.POST.get(f'sublocation_count_{i}', 0)
                try:
                    sublocation_count = int(sublocation_count_input)
                except:
                    sublocation_count = 0
                
                print(f"  Sublocation count: {sublocation_count}")
                
                for j in range(sublocation_count):
                    subloc_name = self.request.POST.get(f'location_{i}_sublocation_name_{j}', '').strip()
                    subloc_code = self.request.POST.get(f'location_{i}_sublocation_code_{j}', '').strip()
                    subloc_active = self.request.POST.get(f'location_{i}_sublocation_active_{j}') == '1'
                    
                    # print(f"    Sublocation {j}:")
                    # print(f"      Name: {subloc_name}")
                    # print(f"      Code: {subloc_code}") 
                    # print(f"      Active: {subloc_active}")
                    
                    if subloc_name:
                        new_subloc = SubLocation.objects.create(
                            location=new_location,
                            name=subloc_name,
                            code=subloc_code.upper() if subloc_code else '',
                            is_active=subloc_active
                        )
                        print(f"      ✓ Sublocation created: {new_subloc.id}")
                    else:
                        print(f"      ✗ Sublocation skipped (no name)")
            else:
                print(f"  ✗ Location skipped (missing name or code)")
        
        messages.success(
            self.request, 
            f'Zone "{self.object.name}" created successfully with {location_count} location(s)!'
        )
        return redirect(self.success_url)


class ZoneUpdateView(LoginRequiredMixin, CanAccessOrganizationMixin,  UpdateView):
    """Update zone with locations and sublocations"""
    model = Zone
    form_class = ZoneForm
    template_name = 'organizations/zone_form.html'
    success_url = reverse_lazy('organizations:zone_list')
    
    def form_valid(self, form):
        self.object = form.save() 
         
        # DEBUG: Print all POST data
        print("=" * 50)
        print("UPDATE - POST DATA:")
        for key, value in self.request.POST.items():
            print(f"{key}: {value}")
        print("=" * 50)
         
        # Track existing location IDs
        existing_location_ids = []
        
        # Process locations
        location_count = int(self.request.POST.get('location_count', 0))
        print(f"Location count: {location_count}")
        
        for i in range(location_count):
            location_id = self.request.POST.get(f'location_id_{i}')
            location_name = self.request.POST.get(f'location_name_{i}', '').strip()
            location_code = self.request.POST.get(f'location_code_{i}', '').strip()
            location_description = self.request.POST.get(f'location_description_{i}', '').strip()
            location_active = self.request.POST.get(f'location_active_{i}') == '1'
            
            # print(f"\nProcessing Location {i}:")
            # print(f"  ID: {location_id}")
            # print(f"  Name: {location_name}")
            # print(f"  Code: {location_code}")
            # print(f"  Active: {location_active}")

            if location_name and location_code:
                loc_data = {
                    'plant': self.object.plant.id,
                    'zone': self.object.id,
                    'name': location_name,
                    'code': location_code.upper(),
                    'description': location_description,
                    'is_active': location_active,
                }

                if location_id:
                    # Update existing location
                    try:
                        location_instance = Location.objects.get(id=location_id, zone=self.object)
                        loc_form = LocationForm(loc_data, instance=location_instance)
                        if loc_form.is_valid():
                            location = loc_form.save()
                            existing_location_ids.append(location.id)
                            print(f"  ✓ Location updated via form: {location.id}")
                        else:
                            print(f"  ✗ Location validation failed: {loc_form.errors}")
                            messages.error(self.request, f"Location '{location_name}': {loc_form.errors.as_text()}")
                            continue
                    except Location.DoesNotExist:
                        print(f"  ✗ Location not found: {location_id}")
                        continue
                else:
                    # Create new location via form
                    loc_form = LocationForm(loc_data)
                    if loc_form.is_valid():
                        location = loc_form.save()
                        existing_location_ids.append(location.id)
                        print(f"  ✓ New location created via form: {location.id}")
                    else:
                        print(f"  ✗ Location validation failed: {loc_form.errors}")
                        messages.error(self.request, f"Location '{location_name}': {loc_form.errors.as_text()}")
                        continue

                # Process sublocations
                existing_sublocation_ids = []
                sublocation_count_input = self.request.POST.get(f'sublocation_count_{i}', 0)
                try:
                    sublocation_count = int(sublocation_count_input)
                except:
                    sublocation_count = 0

                print(f"  Sublocation count: {sublocation_count}")

                for j in range(sublocation_count):
                    subloc_id = self.request.POST.get(f'location_{i}_sublocation_id_{j}')
                    subloc_name = self.request.POST.get(f'location_{i}_sublocation_name_{j}', '').strip()
                    subloc_code = self.request.POST.get(f'location_{i}_sublocation_code_{j}', '').strip()
                    subloc_active = self.request.POST.get(f'location_{i}_sublocation_active_{j}') == '1'

                    # print(f"    Sublocation {j}:")
                    # print(f"      ID: {subloc_id}")
                    # print(f"      Name: {subloc_name}")

                    if subloc_name:
                        if subloc_id:
                            # Update existing sublocation
                            try:
                                subloc = SubLocation.objects.get(id=subloc_id, location=location)
                                subloc.name = subloc_name
                                subloc.code = subloc_code.upper() if subloc_code else ''
                                subloc.is_active = subloc_active
                                subloc.save()
                                existing_sublocation_ids.append(subloc.id)
                                print(f"      ✓ Sublocation updated: {subloc.id}")
                            except SubLocation.DoesNotExist:
                                print(f"      ✗ Sublocation not found: {subloc_id}")
                        else:
                            # Create new sublocation
                            new_subloc = SubLocation.objects.create(
                                location=location,
                                name=subloc_name,
                                code=subloc_code.upper() if subloc_code else '',
                                is_active=subloc_active
                            )
                            existing_sublocation_ids.append(new_subloc.id)
                            print(f"      ✓ Sublocation created: {new_subloc.id}")

                # Delete removed sublocations
                deleted_sublocs = SubLocation.objects.filter(location=location).exclude(
                    id__in=existing_sublocation_ids
                )
                print(f"  Deleting {deleted_sublocs.count()} sublocations")
                deleted_sublocs.delete()

        deleted_locs = Location.objects.filter(zone=self.object).exclude(id__in=existing_location_ids)
        print(f"Deleting {deleted_locs.count()} locations")
        deleted_locs.delete()
        
        messages.success(self.request, f'Zone "{self.object.name}" updated successfully!')
        return redirect(self.success_url)

class ZoneDeleteView(LoginRequiredMixin, CanAccessOrganizationMixin,  DeleteView):
    """Delete zone"""
    model = Zone
    template_name = 'organizations/zone_confirm_delete.html'
    success_url = reverse_lazy('organizations:zone_list')
    
    def delete(self, request, *args, **kwargs):
        zone = self.get_object()
        messages.success(request, f'Zone {zone.name} deleted successfully!')
        return super().delete(request, *args, **kwargs)    
    


class GetAllPlantsAjaxView(LoginRequiredMixin, View):
    """Get all active plants"""
    def get(self, request):
        plants = Plant.objects.filter(is_active=True).values('id', 'name', 'code')
        return JsonResponse(list(plants), safe=False)



class GetZonesByPlantsAjaxView(LoginRequiredMixin, View):
    """Get zones filtered by multiple plant IDs"""
    def get(self, request):
        plant_ids = request.GET.get('plant_ids', '').split(',')
        plant_ids = [pid for pid in plant_ids if pid]
        
        if plant_ids:
            zones = Zone.objects.filter(
                plant_id__in=plant_ids,
                is_active=True
            ).select_related('plant').order_by('plant__name', 'name')
            
            result = []
            for zone in zones:
                result.append({
                    'id': zone.id,
                    'name': zone.name,
                    'code': zone.code,
                    'plant_name': zone.plant.name
                })
            return JsonResponse(result, safe=False)
        return JsonResponse([], safe=False)


class GetLocationsByZonesAjaxView(LoginRequiredMixin, View):
    """Get locations filtered by multiple zone IDs"""
    def get(self, request):
        zone_ids = request.GET.get('zone_ids', '').split(',')
        zone_ids = [zid for zid in zone_ids if zid]
        
        if zone_ids:
            locations = Location.objects.filter(
                zone_id__in=zone_ids,
                is_active=True
            ).select_related('zone').order_by('zone__name', 'name')
            
            result = []
            for location in locations:
                result.append({
                    'id': location.id,
                    'name': location.name,
                    'code': location.code,
                    'zone_name': location.zone.name
                })
            return JsonResponse(result, safe=False)
        return JsonResponse([], safe=False)


class GetSublocationsByLocationsAjaxView(LoginRequiredMixin, View):
    """Get sublocations filtered by multiple location IDs"""
    def get(self, request):
        location_ids = request.GET.get('location_ids', '').split(',')
        location_ids = [lid for lid in location_ids if lid]
        
        if location_ids:
            sublocations = SubLocation.objects.filter(
                location_id__in=location_ids,
                is_active=True
            ).select_related('location').order_by('location__name', 'name')
            
            result = []
            for sublocation in sublocations:
                result.append({
                    'id': sublocation.id,
                    'name': sublocation.name,
                    'code': sublocation.code or '',
                    'location_name': sublocation.location.name
                })
            return JsonResponse(result, safe=False)
        return JsonResponse([], safe=False)
    


class FinancialYearListView(LoginRequiredMixin, ListView):
    model = FinancialYear
    template_name = "organizations/financial_years/financial_year_list.html"
    context_object_name = "financial_years"
    paginate_by = 10

    def get_queryset(self):
        queryset = FinancialYear.objects.all().order_by("-start_date")

        search = self.request.GET.get("search")

        if search:
            queryset = queryset.filter(
                Q(financial_year__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        return context

from datetime import date

class FinancialYearCreateView(LoginRequiredMixin, CreateView):
    model = FinancialYear
    form_class = FinancialYearForm
    template_name = "organizations/financial_years/financial_year_form.html"
    success_url = reverse_lazy("organizations:financial_year_list")

    def get_initial(self):
        initial = super().get_initial()

        current_year = date.today().year
        initial["financial_year"] = f"{current_year}-{current_year + 1}"

        return initial
class FinancialYearCreateView(LoginRequiredMixin, CreateView):
    model = FinancialYear
    form_class = FinancialYearForm
    template_name = "organizations/financial_years/financial_year_form.html"
    success_url = reverse_lazy("organizations:financial_year_list")
    
    def get_initial(self):
        initial = super().get_initial()

        current_year = date.today().year
        initial["financial_year"] = f"{current_year}-{current_year + 1}"

        return initial
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Financial Year"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.save()

        messages.success(
            self.request,
            "Financial Year created successfully."
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)


class FinancialYearUpdateView(LoginRequiredMixin, UpdateView):
    model = FinancialYear
    form_class = FinancialYearForm
    template_name = "organizations/financial_years/financial_year_form.html"
    success_url = reverse_lazy("organizations:financial_year_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Financial Year"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.save()

        messages.success(
            self.request,
            "Financial Year updated successfully."
        )

        return redirect(self.success_url)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)

class CalendarWeekView(TemplateView):
    template_name = "organizations/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["events"] = [
            {
                "title": "Stretch",
                "start": "2025-06-30T08:00:00",
                "end": "2025-06-30T09:00:00",
                "color": "#ef4444",
            },
            {
                "title": "Power Strength",
                "start": "2025-06-30T09:00:00",
                "end": "2025-06-30T10:00:00",
                "color": "#16a34a",
            },
            {
                "title": "Pilates Mat",
                "start": "2025-07-01T07:30:00",
                "end": "2025-07-01T08:40:00",
                "color": "#3b82f6",
            },
        ]

        return context


class WorkflowConfigurationAccessMixin(LoginRequiredMixin, CanAccessOrganizationMixin):
    def get_workflow_configuration_company_queryset(self):
        queryset = Company.objects.filter(is_active=True).order_by("company_name")
        user = self.request.user
        if user.is_superuser or getattr(user, "is_super_admin", False):
            return queryset
        if getattr(user, "company_id", None):
            return queryset.filter(pk=user.company_id)
        return queryset.none()

    def get_workflow_configuration_template_queryset(self):
        queryset = (
            ApprovalConfigurationTemplate.objects.select_related("company")
            .prefetch_related("stages", "stages__role", "stages__escalation_role")
            .order_by("company__company_name", "framework", "name")
        )
        user = self.request.user
        if user.is_superuser or getattr(user, "is_super_admin", False):
            return queryset
        if getattr(user, "company_id", None):
            return queryset.filter(company_id=user.company_id)
        return queryset.none()

    def get_workflow_configuration_template(self, pk):
        return get_object_or_404(self.get_workflow_configuration_template_queryset(), pk=pk)

    def get_stage_payload(self, stage):
        return {
            "id": stage.id,
            "level": stage.level,
            "label": stage.label,
            "stage_type": stage.get_stage_type_display(),
            "role": stage.role.role_name if stage.role_id else "",
            "role_code": stage.role.role_code if stage.role_id else "",
            "can_approve": stage.can_approve,
            "can_reject": stage.can_reject,
            "can_reassign": stage.can_reassign,
            "can_escalate": stage.can_escalate,
            "due_days": stage.due_days,
            "escalation_role": stage.escalation_role.role_name if stage.escalation_role_id else "",
        }


class WorkflowConfigurationTemplateListView(WorkflowConfigurationAccessMixin, ListView):
    model = ApprovalConfigurationTemplate
    template_name = "organizations/workflow_configurations/workflow_configuration_template_list.html"
    context_object_name = "workflow_configuration_templates"
    paginate_by = 12

    def get_queryset(self):
        queryset = self.get_workflow_configuration_template_queryset()
        search = self.request.GET.get("search", "").strip()
        company_id = self.request.GET.get("company", "").strip()
        framework = self.request.GET.get("framework", "").strip()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if framework:
            queryset = queryset.filter(framework=framework)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(company__company_name__icontains=search)
                | Q(framework__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("search", "")
        context["selected_company"] = self.request.GET.get("company", "")
        context["selected_framework"] = self.request.GET.get("framework", "")
        context["companies"] = self.get_workflow_configuration_company_queryset()
        context["framework_choices"] = ApprovalConfigurationTemplate.FRAMEWORK_CHOICES
        return context


class WorkflowConfigurationTemplateEditorView(WorkflowConfigurationAccessMixin, View):
    template_name = "organizations/workflow_configurations/workflow_configuration_template_form.html"

    def _get_template(self, pk=None):
        if pk:
            return self.get_workflow_configuration_template(pk)
        return None

    def _build_form(self, request_data=None, instance=None):
        form = WorkflowConfigurationTemplateForm(request_data or None, instance=instance)
        form.fields["company"].queryset = self.get_workflow_configuration_company_queryset()
        if instance and instance.company_id:
            form.initial.setdefault("company", instance.company_id)
        elif getattr(self.request.user, "company_id", None) and not (
            self.request.user.is_superuser or getattr(self.request.user, "is_super_admin", False)
        ):
            form.initial.setdefault("company", self.request.user.company_id)
        return form

    def _build_formset(self, request_data=None, instance=None):
        prefix = "stages"
        if request_data is None:
            return WorkflowConfigurationStageFormSet(instance=instance, prefix=prefix)
        return WorkflowConfigurationStageFormSet(request_data, instance=instance, prefix=prefix)

    def _render(self, request, form, formset, template_obj=None):
        context = {
            "form": form,
            "formset": formset,
            "object": template_obj,
            "companies": self.get_workflow_configuration_company_queryset(),
            "framework_choices": ApprovalConfigurationTemplate.FRAMEWORK_CHOICES,
            "stage_types": ApprovalConfigurationStage.STAGE_TYPE_CHOICES,
        }
        return render(request, self.template_name, context)

    def get(self, request, pk=None):
        template_obj = self._get_template(pk)
        form = self._build_form(instance=template_obj)
        formset = self._build_formset(instance=template_obj)
        return self._render(request, form, formset, template_obj)

    def post(self, request, pk=None):
        template_obj = self._get_template(pk)
        form = self._build_form(request.POST, instance=template_obj)
        formset = self._build_formset(request.POST, instance=template_obj)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                template = form.save()
                existing_stage_ids = []
                for index, stage_form in enumerate(formset.forms, start=1):
                    if not hasattr(stage_form, "cleaned_data"):
                        continue
                    if stage_form.cleaned_data.get("DELETE"):
                        continue
                    if not stage_form.cleaned_data:
                        continue

                    stage = stage_form.save(commit=False)
                    stage.template = template
                    stage.level = index
                    stage.save()
                    existing_stage_ids.append(stage.pk)

                template.stages.exclude(pk__in=existing_stage_ids).delete()

            messages.success(
                request,
                f"Workflow configuration template '{template.name}' saved successfully.",
            )
            return redirect("organizations:workflow_configuration_template_list")

        return self._render(request, form, formset, template_obj)


class WorkflowConfigurationTemplateDeleteView(WorkflowConfigurationAccessMixin, View):
    def post(self, request, pk):
        template = self.get_workflow_configuration_template(pk)
        name = template.name
        template.delete()
        messages.success(request, f"Workflow configuration template '{name}' deleted successfully.")
        return redirect("organizations:workflow_configuration_template_list")


class WorkflowConfigurationTaskHistoryView(WorkflowConfigurationAccessMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(
            ApprovalConfigurationTask.objects.select_related("template", "current_stage"),
            pk=pk,
        )
        if not (
            request.user.is_superuser
            or getattr(request.user, "is_super_admin", False)
            or (request.user.company_id and task.template.company_id == request.user.company_id)
        ):
            return JsonResponse({"detail": "Not allowed."}, status=403)

        history = []
        for log in task.logs.select_related("from_stage", "to_stage", "actor_content_type").order_by("created_at"):
            history.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "from_stage": log.from_stage.label if log.from_stage_id else "",
                    "to_stage": log.to_stage.label if log.to_stage_id else "",
                    "actor": str(log.actor) if log.actor else "",
                    "remark": log.remark or "",
                    "created_at": log.created_at.isoformat(),
                }
            )
        return JsonResponse({"task_id": task.id, "history": history})


# Backward-compatible aliases for any remaining imports or references.
ApprovalConfigurationAccessMixin = WorkflowConfigurationAccessMixin
ApprovalConfigurationTemplateListView = WorkflowConfigurationTemplateListView
ApprovalConfigurationTemplateEditorView = WorkflowConfigurationTemplateEditorView
ApprovalConfigurationTemplateDeleteView = WorkflowConfigurationTemplateDeleteView
ApprovalConfigurationTaskHistoryView = WorkflowConfigurationTaskHistoryView
