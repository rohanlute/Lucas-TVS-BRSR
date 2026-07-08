
from django.urls import path
from . import views

app_name = 'calculator'

from django.urls import path
from . import views

app_name = 'calculator'

urlpatterns = [
    # ====== CRUD URLs ======
    path('categories/', views.UnitCategoryListView.as_view(), name='unit_category_list'),
    path('categories/create/', views.UnitCategoryCreateView.as_view(), name='unit_category_create'),
    path('categories/<int:pk>/edit/', views.UnitCategoryUpdateView.as_view(), name='unit_category_update'),
    path('categories/<int:pk>/delete/', views.UnitCategoryDeleteView.as_view(), name='unit_category_delete'),
    
    # ====== API URLs for Converter Modal ======
    path('get-categories/', views.GetCategoriesView.as_view(), name='get_categories'),
    path('get-category-data/', views.GetCategoryDataView.as_view(), name='get_category_data'),
    path('get-conversion/', views.GetConversionView.as_view(), name='get_conversion'),
]