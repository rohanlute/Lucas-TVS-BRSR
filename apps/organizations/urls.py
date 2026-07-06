from django.urls import path
from . import views
from .views import (
    FinancialYearListView,
    FinancialYearCreateView,
    FinancialYearUpdateView,
)

app_name = 'organizations'

urlpatterns = [
    # Dashboard
    path('', views.OrganizationDashboardView.as_view(), name='dashboard'),
    
    # Plant URLs
    path('plants/', views.PlantListView.as_view(), name='plant_list'),
    path('plants/create/', views.PlantCreateView.as_view(), name='plant_create'),
    path('plants/<int:pk>/edit/', views.PlantUpdateView.as_view(), name='plant_update'),
    path('plants/<int:pk>/delete/', views.PlantDeleteView.as_view(), name='plant_delete'),
    
    # Zone URLs
    path('zones/', views.ZoneListView.as_view(), name='zone_list'),
    path('zones/create/', views.ZoneCreateView.as_view(), name='zone_create'),
    path('zones/<int:pk>/edit/', views.ZoneUpdateView.as_view(), name='zone_update'),
    path('zones/<int:pk>/delete/', views.ZoneDeleteView.as_view(), name='zone_delete'),
    path('ajax/get-all-plants/', views.GetAllPlantsAjaxView.as_view(), name='ajax_get_all_plants'),
    path('ajax/get-zones-by-plants/', views.GetZonesByPlantsAjaxView.as_view(), name='ajax_get_zones_by_plants'),
    path('ajax/get-locations-by-zones/', views.GetLocationsByZonesAjaxView.as_view(), name='ajax_get_locations_by_zones'),
    path('ajax/get-sublocations-by-locations/', views.GetSublocationsByLocationsAjaxView.as_view(), name='ajax_get_sublocations_by_locations'),
    # Location URLs
    path('locations/', views.LocationListView.as_view(), name='location_list'),
    path('locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/edit/', views.LocationUpdateView.as_view(), name='location_update'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    path("financial-years/",FinancialYearListView.as_view(),name="financial_year_list"),
    path("financial-years/create/",FinancialYearCreateView.as_view(),name="financial_year_create"),
    path("financial-years/<int:pk>/edit/",FinancialYearUpdateView.as_view(),name="financial_year_update"),
    path('calendar/', views.CalendarWeekView.as_view(), name='calendar')
]