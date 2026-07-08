from django.urls import path
from . import views

app_name = "environmental"

urlpatterns = [

    path("transactions/",views.EmissionTransactionListView.as_view(),name="transaction_list",),
    path("transactions/create/",views.EmissionTransactionCreateView.as_view(),name="transaction_create",),
    path("transactions/<int:pk>/edit/",views.EmissionTransactionUpdateView.as_view(),name="transaction_update",),
    path("transactions/<int:pk>/delete/",views.EmissionTransactionDeleteView.as_view(),name="transaction_delete",),
]