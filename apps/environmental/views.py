from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .models import EmissionTransaction
from .forms import EmissionTransactionForm

class EmissionTransactionListView(ListView):

    model = EmissionTransaction

    template_name = "environmental/transaction_list.html"

    context_object_name = "transactions"

    paginate_by = 20

    def get_queryset(self):

        queryset = (
            EmissionTransaction.objects
            .select_related(
                "company",
                "plant",
                "financial_year",
                "financial_month",
                "activity",
                "unit",
            )
            .order_by(
                "-financial_year",
                "financial_month",
                "plant",
            )
        )

        search = self.request.GET.get("search")

        if search:

            queryset = queryset.filter(
                activity__name__icontains=search
            )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["search"] = self.request.GET.get(
            "search",
            "",
        )

        context["total_transactions"] = (
            EmissionTransaction.objects.count()
        )

        context["draft_count"] = (
            EmissionTransaction.objects.filter(
                status="DRAFT"
            ).count()
        )

        context["submitted_count"] = (
            EmissionTransaction.objects.filter(
                status="SUBMITTED"
            ).count()
        )

        context["approved_count"] = (
            EmissionTransaction.objects.filter(
                status="APPROVED"
            ).count()
        )

        return context

class EmissionTransactionCreateView(CreateView):

    model = EmissionTransaction

    form_class = EmissionTransactionForm

    template_name = "environmental/transaction_form.html"

    success_url = reverse_lazy(
        "environmental:transaction_list"
    )

    def form_valid(self, form):

        if self.request.user.is_authenticated:

            form.instance.created_by = self.request.user

        return super().form_valid(form)
    


class EmissionTransactionUpdateView(UpdateView):

    model = EmissionTransaction

    form_class = EmissionTransactionForm

    template_name = "environmental/transaction_form.html"

    success_url = reverse_lazy(
        "environmental:transaction_list"
    )


class EmissionTransactionDeleteView(DeleteView):

    model = EmissionTransaction

    template_name = "environmental/transaction_delete.html"

    success_url = reverse_lazy(
        "environmental:transaction_list"
    )