# expense/admin.py
from django.contrib import admin
from .models import ExpenseCategory, Requisition, RequisitionItem

class RequisitionItemInline(admin.TabularInline):
    model = RequisitionItem
    extra = 0
    fields = ['expense_name', 'category', 'quantity', 'price_per_unit', 'get_cost']
    readonly_fields = ['get_cost']

    def get_cost(self, obj):
        return f" {obj.cost:,.2f}" if obj.cost else " 0.00"
    get_cost.short_description = "Calculated Cost"

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'description']
    search_fields = ['title']

@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'campus', 'calendar_week', 'requester_historical_name', 'status', 'get_total_cost', 'created_at']
    list_filter = ['status', 'campus', 'calendar_week']
    search_fields = ['requester_historical_name', 'id']
    readonly_fields = ['requester_historical_name', 'created_at']
    inlines = [RequisitionItemInline]

    def get_total_cost(self, obj):
        return f" {obj.total_cost:,.2f}"
    get_total_cost.short_description = "Total Requisition Budget"