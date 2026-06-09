from django.urls import path
from .views import *

app_name = 'companies'

urlpatterns = [

    path('company_list/',company_list,name='company_list'),
    path('company_create/',company_create,name='company_create'),
    path('company_view/',company_view,name='company_view'),

]