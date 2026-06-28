from django.contrib import admin
from .models import AcademicSession, Campus, Grade, Term, GradeTermFee
from .models import Student, StudentIdCounter, Invoice, PaymentHistory
from .models import TransportRoute, ExtraItem, ExchangeRate

@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ('name', 'campus_code', 'subdomain', 'city')
    search_fields = ('name', 'campus_code')

@admin.register(StudentIdCounter)
class StudentIdCounterAdmin(admin.ModelAdmin):
    list_display = ('campus', 'year', 'latest_sequence')
    list_filter = ('campus', 'year')

@admin.register(GradeTermFee)
class GradeTermFeeAdmin(admin.ModelAdmin):
    list_display = ('campus', 'grade', 'term', 'amount')
    list_filter = ('campus', 'term', 'grade')
    search_fields = ('grade__title',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    # Displays crucial registry parameters on the table index row
    list_display = ('student_id', 'name', 'campus', 'grade', 'status', 'current_term_outstanding_balance')
    
    # Left-side sidebar filter tabs to drill down into segments instantly
    list_filter = ('campus', 'status', 'grade', 'gender','needs_transport','image_use_consent', 'scholarship_status')
    
    # Global search panel querying explicit identifiers or names
    search_fields = ('student_id', 'name', 'parent_name', 'phone_number_1')
    
    # Organizes the individual profile dashboard view cleanly using segmented fields
    fieldsets = (
        ('Institutional Identity', {
            'fields': ('student_id', 'campus', 'grade', 'status','enrollment_year', 'enrollment_term',)
        }),
        ('Personal Details', {
            'fields': ('name', 'date_of_birth', 'gender', 'profile_picture')
        }),
        ('Guardianship & Contact', {
            'fields': ('parent_name', 'phone_number_1', 'phone_number_2')
        }),
        ('Location Details', {
            'fields': ('address', 'city', 'country')
        }),        
        ('Logistics', {
            'fields': ('proposed_scholarship_amount','needs_transport', 'transport_route', 'extra_items','image_use_consent', 'scholarship_status')
        }),
    )
    
    # Keeps student_id un-editable directly since the background code generates it safely
    readonly_fields = ('student_id',)

@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    """
    Admin control panel layout for managing global transport pricing tiers.
    """
    list_display = ('id', 'route_name', 'campus','formatted_transport_fee')
    list_display_links = ('id', 'route_name')
    search_fields = ('route_name',)
    ordering = ('route_name',)

    @admin.display(description='Transport Fee ()')
    def formatted_transport_fee(self, obj):
        return f" {obj.transport_fee:,.2f}"

@admin.register(ExtraItem)
class ExtraItemAdmin(admin.ModelAdmin):
    """
    Admin control panel layout for handling optional books, uniforms, and student accessories.
    """
    list_display = ('id', 'item_name', 'formatted_cost')
    list_display_links = ('id', 'item_name')
    search_fields = ('item_name',)
    ordering = ('item_name',)

    @admin.display(description='Cost ()')
    def formatted_cost(self, obj):
        return f" {obj.cost:,.2f}"

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    """
    Admin control panel layout for managing exchange rates.
    """
    list_display = ('id', 'currency_code', 'rate_to_reporting_currency')
    list_display_links = ('id', 'currency_code')
    search_fields = ('currency_code',)
    ordering = ('currency_code',)

    @admin.display(description='Exchange Rate')
    def formatted_rate(self, obj):
        return f"{obj.rate_to_reporting_currency:.4f}"

# Register remaining accounting components cleanly
admin.site.register(AcademicSession)
admin.site.register(Grade)
admin.site.register(Term)
admin.site.register(Invoice)
admin.site.register(PaymentHistory)
