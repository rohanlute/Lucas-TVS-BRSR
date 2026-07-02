from django.urls import path
from .views import *


app_name = 'companies'

urlpatterns = [

    path('company_list/',CompanyListView.as_view(),name='company_list'),
    path('company_create/',CompanyCreateView.as_view(),name='company_create'),
    path('company_view/<int:pk>/',CompanyDetailView.as_view(),name='company_view'),
    path('company_edit/<int:pk>/',CompanyUpdateView.as_view(),name='company_edit'),
    path('company_delete/<int:pk>/',CompanyDeleteView.as_view(),name='company_delete'),

    path("get-states/<int:country_id>/",get_states,name="get_states",),
    path("get-cities/<int:state_id>/",get_cities,name="get_cities",),
]