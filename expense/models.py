import datetime
from django.db import models
from django.conf import settings
from decimal import Decimal
from students.models import Campus, Term

class ExpenseCategory(models.Model):
    title = models.CharField(max_length=100, unique=True)
    expense_code = models.CharField(max_length=20, unique=True, help_text="A unique code for the expense category, e.g., 'ESK01'for 'TRAVEL'")
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Expense Categories"

    def __str__(self):
        return self.title

class Requisition(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Funded'),
        ('REJECTED', 'Rejected'),
    ]

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='requisitions')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    calendar_week = models.DateField(help_text="The Monday starting date of the operational week this budget is for")
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, blank=True, null=True, related_name='requisitions')

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='requisitions')
    requester_historical_name = models.CharField(max_length=255, help_text="Permanently preserves the user's name at the moment of application")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 🎯 FIX: Add the managers here so the view can query globally across all campuses
    objects = models.Manager()         # Standard manager (or your custom CampusIsolatedManager if you want it here)
    global_objects = models.Manager()  # Explicit global admin escape hatch for your reports view!

    class Meta:
        ordering = ['-calendar_week', '-created_at']

    def __str__(self):
        return f"Req {self.id} | {self.campus.name} | Week of {self.calendar_week}"

    @property
    def total_cost(self):
        return sum(item.cost for item in self.items.all())
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Funded'),
        ('REJECTED', 'Rejected'),
    ]

    # Core Multi-Tenant & Status Coordinates
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='requisitions')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Calendar Week calculation logic
    calendar_week = models.DateField(
        help_text="The Monday starting date of the operational week this budget is for"
    )
    
    # Dual-Layer Audit Trail for Users who might leave the company
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='requisitions'
    )
    requester_historical_name = models.CharField(
        max_length=255,
        help_text="Permanently preserves the user's name at the moment of application for strict audit integrity"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-calendar_week', '-created_at']

    def __str__(self):
        return f"Req {self.id} | {self.campus.name} | Week of {self.calendar_week}"

    @property
    def total_cost(self):
        """
        Dynamically aggregates the sum total of all related line-item rows 
        directly inside database memory loops.
        """
        # loops over the related items through the reverse relationship 'items'
        return sum(item.cost for item in self.items.all())
    
    def save(self, *args, **kwargs):
        """
        Intercepts savings lifecycle to dynamically evaluate which Academic Year 
        and Term slot maps to the current expenditure timeline window.
        """
        if self.calendar_week:
            # Locate the specific Term frame where the calendar week falls squarely between start and end bounds
            matched_term = Term.objects.filter(
                start_date__lte=self.calendar_week,
                end_date__gte=self.calendar_week
            ).first()
            
            if matched_term:
                self.term = matched_term
            else:
                # Fallback safeguard: If no explicit calendar date range hits, 
                # link it directly to the globally active invoice term profile
                self.term = Term.objects.filter(is_current=True).first()

        super().save(*args, **kwargs)

class RequisitionItem(models.Model):
    # Master-Detail cascading line relation linkage
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items')
    
    # Line Entry Data Coordinates
    expense_name = models.CharField(max_length=200, help_text="e.g., 50kg Sugar Bag, Textbooks, Printer Toner")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='requisition_items')
    
    quantity = models.PositiveIntegerField(default=1)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Requisition Item"
        verbose_name_plural = "Requisition Line Items"

    def __str__(self):
        return f"{self.expense_name} ({self.quantity} x {self.price_per_unit})"

    @property
    def cost(self):
        """
        Calculates line-item cost automatically: Quantity multiplied by unit price.
        """
        if self.quantity is None or self.price_per_unit is None:
            return Decimal('0.00')
        return Decimal(self.quantity) * self.price_per_unit