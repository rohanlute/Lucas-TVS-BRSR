from django.urls import path
from .views import (CompanyListView,CompanyCreateView,CompanyDetailView,)


app_name = 'companies'

urlpatterns = [

    path('company_list/',CompanyListView.as_view(),name='company_list'),

    path('company_create/',CompanyCreateView.as_view(),name='company_create'),

    path('company_view/',CompanyDetailView.as_view(),name='company_view'),

]