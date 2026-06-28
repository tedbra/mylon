from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils.timezone import now
import datetime
from django.conf import settings
from .managers import CampusIsolatedManager
from django.db.models import Sum, Count, Q, F, DecimalField

# 0. CAMPUS CONFIGURATION
class Campus(models.Model):
    name = models.CharField(max_length=100)           # e.g., "Mombasa Campus"
    subdomain = models.CharField(max_length=50, unique=True,help_text="Example: mombasa, for mombasa.app.skylon.org") # e.g., "mombasa"
    city = models.CharField(max_length=100)
    campus_code = models.CharField(max_length=20, unique=True, help_text="Example: KAM, for Kamulu") # e.g., "MOMB001"
    CURRENCY_CHOICES = [
        ('$', 'US Dollar ($)'),
        ('€', 'Euro (€)'),
        ('£', 'British Pound (£)'),
        ('KES', 'Kenyan Shilling'),
        ('NGN', 'Nigerian Naira (₦)'),
        ('Xaf', 'Central African CFA'),
        ('Xof', 'West African CFA'),
        ('Rnd', 'South African Rand (R)'),
    ]
    
    currency_code = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=getattr(settings, 'DEFAULT_CURRENCY', 'USD'),
        help_text="The local currency label used for this specific campus's invoices."
    )

    # Clean property helper to fetch currency anywhere
    @property
    def currency(self):
        return self.currency_code

    class Meta:
        verbose_name_plural = "Campuses"

    def __str__(self):
        return self.name

# 1. ACADEMIC TIMELINE CALENDAR
class AcademicSession(models.Model):
    name = models.CharField(max_length=20, unique=True, help_text="Example: 2026/2027")
    is_current = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_current:
            # Ensure only one session can be marked active globally at a time
            AcademicSession.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Session {self.name}"

# 2. ACADEMIC TIMELINE CALENDAR
class Term(models.Model):
    TERM_CHOICES = (
        ('TERM_1', 'Term 1'),
        ('TERM_2', 'Term 2'),
        ('TERM_3', 'Term 3'),
    )
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='terms')
    term_name = models.CharField(max_length=10, choices=TERM_CHOICES)
    is_current = models.BooleanField(default=False, help_text="Defines the active period for invoices and billing.")
    
    # 🎯 ADD THESE TWO LINES HERE:
    start_date = models.DateField(null=True, blank=True, help_text="The opening calendar date of this term block.")
    end_date = models.DateField(null=True, blank=True, help_text="The closing calendar date of this term block.")

    class Meta:
        unique_together = ('session', 'term_name')

    def save(self, *args, **kwargs):
        if self.is_current:
            Term.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.session.name} - {self.get_term_name_display()}"

# 3. ACADEMIC STRUCTURE
class Grade(models.Model):
    title = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.title

# 4. PRICING CONFIGURATION MATRIX
class GradeTermFee(models.Model):
    # ADD THIS LINE:
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='fee_structures')    
    grade = models.ForeignKey('Grade', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    objects = CampusIsolatedManager()
    global_objects = models.Manager()

    class Meta:
        # Crucial constraint: A grade can only have ONE price rule per term per campus
        unique_together = ('campus', 'grade', 'term')

    def __str__(self):
        return f"{self.campus.name} - {self.grade.title} ({self.term.term_name}): ${self.amount}"

# 5. TRANSPORT ROUTE FEES
class TransportRoute(models.Model):
    """Master lookup table for bus routes, zones, and pricing."""
    campus = models.ForeignKey('Campus', on_delete=models.CASCADE, related_name='transport_routes')
    route_name = models.CharField(max_length=150, unique=True, help_text="e.g., Kamulu Zone A, Nyali Axis")
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    class Meta:
        # 🎯 Ensures route names are unique within a single campus, but can repeat across different campuses
        unique_together = ('campus', 'route_name')

    def __str__(self):
        return f"{self.route_name} ({self.transport_fee})"

# 6. OPTIONAL EXTRAS CONFIGURATION
class ExtraItem(models.Model):
    """Master lookup table for optional items like diaries, uniform sets, assessment books."""
    item_name = models.CharField(max_length=150, unique=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.item_name} ({self.cost})"

# 7. STUDENT ID COUNTER (Ensures unique sequential alphanumeric IDs per campus and year)
class StudentIdCounter(models.Model):
    campus = models.ForeignKey('Campus', on_delete=models.CASCADE)
    year = models.IntegerField()  # e.g., 2026, 2027
    latest_sequence = models.IntegerField(default=0)

    class Meta:
        unique_together = ('campus', 'year')

    def __str__(self):
        return f"{self.campus.campus_code} - {self.year}: Count {self.latest_sequence}"

# 8. THE STUDENT PROFILE
class Student(models.Model):
    # 1. DATABASE FIELDS (Keep these at the top)
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name='students')
    student_id = models.CharField(max_length=25, unique=True) # Permanently saved custom alphanumeric ID
    name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=(('M', 'Male'), ('F', 'Female')))
    parent_name = models.CharField(max_length=255)
    phone_number_1 = models.CharField(max_length=20)
    phone_number_2 = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='student_pics/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=(('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')), default='ACTIVE')
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT)
    date_created = models.DateTimeField(auto_now_add=True)
    image_use_consent = models.BooleanField(
        default=True,
        help_text="Explicit parental choice regarding social media marketing and promotional image use."
    )
    enrollment_year = models.PositiveIntegerField(
        db_index=True,  # Makes filtering by year lightning fast
        help_text="The calendar year the student joined (e.g., 2026)"
    )
    enrollment_term = models.PositiveSmallIntegerField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        db_index=True,  # Makes filtering by term lightning fast
        help_text="The academic term the student joined"
    )

    needs_transport = models.BooleanField(default=False)
    transport_route = models.ForeignKey(
        TransportRoute, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Assigned route/location determining their transport billing."
    )
    # 📚 Extra Items Logic (Many-to-Many so a pupil can have multiple extras like a diary AND book)
    extra_items = models.ManyToManyField(ExtraItem, blank=True)
    
    # Scholarship management
    SCHOLARSHIP_STATUS_CHOICES = (
        ('NONE', 'No Scholarship'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved & Active'),
        ('REJECTED', 'Rejected'),
    )
    
    scholarship_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    proposed_scholarship_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Amount requested by local staff awaiting review.")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_scholarships',
        help_text="The administrative user who signed off or reviewed this scholarship request."
    )
    scholarship_status = models.CharField(max_length=15, choices=SCHOLARSHIP_STATUS_CHOICES, default='NONE')

    # 🎯 DYNAMIC PROPERTY: Calculate Total Termly Cost

    # --- ATTACH MANAGERS ACCORDINGLY ---
    objects = CampusIsolatedManager()          # Default manager handles automated isolation
    global_objects = models.Manager()          # Backup manager to bypass isolation explicitly if needed in background scripts

    # 2. COMPUTED PROPERTIES (Calculated Ledger Values)
    # 🎯 DYNAMIC PROPERTY: Calculate Total Termly Cost
    
    @property
    def current_invoice(self):
        """Helper to fetch the current active term invoice safely."""
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            return None
        return self.invoices.filter(term=current_term).first()

    @property
    def current_term_arrears(self):
        """Arrears brought forward into the current term."""
        invoice = self.current_invoice
        return invoice.previous_arrears if invoice else Decimal('0.00')

    @property
    def current_term_fees_billed(self):
        """Pure billables generated strictly for this term (Tuition + Transport + Extras)."""
        invoice = self.current_invoice
        if not invoice:
            return Decimal('0.00')
        # Total invoice amount minus the carried-over arrears gives the pure current term billed
        return invoice.amount - invoice.previous_arrears

    @property
    def current_term_total_due(self):
        """The grand total balance expected for this term (Arrears + Current Fees)."""
        invoice = self.current_invoice
        return invoice.amount if invoice else Decimal('0.00')

    @property
    def current_term_paid(self):
        """Sums up all payments made strictly within the calendar boundaries of the current term."""
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term or not current_term.start_date or not current_term.end_date:
            return Decimal('0.00')
            
        total_paid = PaymentHistory.global_objects.filter(
            student=self,
            date_paid__range=(current_term.start_date, current_term.end_date)
        ).aggregate(total=Sum('amount_paying'))['total'] or Decimal('0.00')
        
        return total_paid

    @property
    def current_term_outstanding_balance(self):
        """The actual remaining balance a parent needs to pay right now."""
        balance = self.current_term_total_due - self.current_term_paid
        return balance if balance > 0 else Decimal('0.00')
    
    @property
    def current_term_tranport(self):
        """The actual tranport cost per student, so we can pull metrics on transport for analysis"""
        invoice = self.current_invoice
        return invoice.transport_amount if invoice else Decimal('0.00')

    # 3. SYNC CURRENT TERM INVOICE METHOD
    def sync_current_term_invoice(self):
        """
        Recalculates tuition, transport, and extra items for the active operational term,
        preserving frozen previous arrears balances without altering historical snapshot points.
        """        
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term or self.status != 'ACTIVE':
            return
            
        # 1. Fetch base tuition fee
        fee_rule = GradeTermFee.objects.filter(
            campus=self.campus, grade=self.grade, term=current_term
        ).first()
        base_tuition = fee_rule.amount if fee_rule else Decimal('0.00')
        
        # 2. Fetch transport fee
        transport_billed = self.transport_route.transport_fee if (self.needs_transport and self.transport_route) else Decimal('0.00')
        
        # 3. Fetch current extras sums
        extras_billed = self.extra_items.aggregate(total=Sum('cost'))['total'] or Decimal('0.00')
        extras_list_names = ", ".join([item.item_name for item in self.extra_items.all()])

        # 4. Fetch for scholarships
        scholarship_billed = Decimal('0.00')
        approver_snapshot = None

        if self.scholarship_status == 'APPROVED':
            scholarship_billed = min(self.scholarship_amount, base_tuition)
            approver_snapshot = self.approved_by  # 🎯 Capture the user reference
        
        
        # --- 🎯 THE ARREARS PROTECTOR FIX ---
        # Fetch an existing invoice to read its historical frozen arrears if it exists.
        # If no invoice exists yet, fallback to Decimal('0.00')
        existing_invoice = Invoice.objects.filter(student=self, term=current_term).first()
        current_arrears = existing_invoice.previous_arrears if existing_invoice else Decimal('0.00')
        
        # Add the existing arrears back into the total formula safely
        grand_total = base_tuition + transport_billed + Decimal(str(extras_billed)) + current_arrears - scholarship_billed
        # ------------------------------------
        
        # 4. Atomically update or generate the invoice row
        Invoice.objects.update_or_create(
            student=self,
            term=current_term,
            defaults={
                'tuition_amount': base_tuition,
                'transport_amount': transport_billed,
                'extras_amount': Decimal(str(extras_billed)),
                'extras_summary': extras_list_names,
                'previous_arrears': current_arrears, # 👈 Keeps it locked down in the database!
                'scholarship_applied' : scholarship_billed,
                'amount': grand_total,
                'scholarship_approved_by':approver_snapshot
            }
        )

    # 3. OVERRIDDEN METHODS (Automation Triggers)
    def save(self, *args, **kwargs):
        from accounts.middleware import get_current_user_campus, is_current_user_director
        from decimal import Decimal
        import datetime
        from django.db import transaction

        # 1. HYBRID LIFECYCLE CHECK: If this is a brand new creation record
        is_new_creation = not self.pk
        
        if is_new_creation: 
            # If the admin left enrollment variables empty, pull them from active terms
            if not self.enrollment_year or not self.enrollment_term:
                current_active_term = Term.objects.filter(is_current=True).select_related('session').first()
                if current_active_term:
                    if not self.enrollment_year:
                        try:
                            self.enrollment_year = int(current_active_term.session.name.split('/')[0])
                        except (ValueError, IndexError):
                            self.enrollment_year = datetime.datetime.now().year
                    
                    if not self.enrollment_term:
                        term_map = {'TERM_1': 1, 'TERM_2': 2, 'TERM_3': 3}
                        self.enrollment_term = term_map.get(current_active_term.term_name, 1)
                else:
                    if not self.enrollment_year: self.enrollment_year = datetime.datetime.now().year
                    if not self.enrollment_term: self.enrollment_term = 1

        # Automated middleware campus assignments
        user_campus = get_current_user_campus()
        if user_campus and not is_current_user_director():
            self.campus = user_campus
            
        if not is_new_creation:
            # Save core field changes first
            super().save(*args, **kwargs)
            # Sync standard profile fields
            self.sync_current_term_invoice()
        else:
            # ... keep your existing sequential ID generator code block exactly the same ...
            super().save(*args, **kwargs)
            self.sync_current_term_invoice()

    
    # 4. STRING REPRESENTATION (Always at the bottom)
    def __str__(self):
        # Now safely references the static alphanumeric string saved directly in the db row!
        return f"{self.student_id} - {self.name}"

# FOR AUTOMATIC INVOICE UPDATES WHEN EXTRAS CHANGE: Listen to changes in the Many-to-Many relationship and trigger invoice syncs accordingly
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

@receiver(m2m_changed, sender=Student.extra_items.through)
def update_invoice_on_extras_change(sender, instance, action, **kwargs):
    """
    Listens specifically to shifts in the extra items Many-to-Many relation table.
    Fires whenever items are cleared, appended, or modified via forms or dashboard views.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        # Recalculate invoice totals now that database rows are committed
        instance.sync_current_term_invoice()


# 9. HISTORICAL TERM INVOICE
class Invoice(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invoices')
    term = models.ForeignKey(Term, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_issued = models.DateTimeField(auto_now_add=True)

    # 🎯 THE NEW MAP: Itemized Breakdown Fields
    tuition_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    scholarship_applied = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    extras_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    previous_arrears = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Unpaid balance carried forward from the immediate previous term.")
    scholarship_approved_by = models.ForeignKey( settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoice_scholarship_authorizations')
    approver_name_snapshot = models.CharField(max_length=150, blank=True, default="")
    
    # Optional metadata log to list exactly which extras were bought (e.g., "Diary, Assessment Book")
    extras_summary = models.TextField(blank=True, null=True)

    objects = CampusIsolatedManager()
    global_objects = models.Manager()

    class Meta:
        unique_together = ('student', 'term') # Prevents double billing a student for the same term
    
    def save(self, *args, **kwargs):
        if self.scholarship_approved_by and not self.approver_name_snapshot:
            user = self.scholarship_approved_by
            # Grab full name if available, fallback to their system username
            self.approver_name_snapshot = user.get_full_name() or user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.student.student_id} — {self.term} ({self.amount})"


# 10. PAYMENT RECORD VOUCHER
class PaymentHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    amount_paying = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    date_paid = models.DateField()
    date_created = models.DateTimeField(auto_now_add=True)

    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payments')
    processed_by_name = models.CharField(max_length=255, blank=True, default='')

    objects = CampusIsolatedManager()
    global_objects = models.Manager()

    def save(self, *args, **kwargs):
        if self.processed_by and not self.processed_by_name:
            user = self.processed_by
            full_name = f"{user.first_name} {user.last_name}".strip()
            self.processed_by_name = full_name if full_name else user.username
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.reference} — {self.student.name} (${self.amount_paying})"
    

# 11. EXCHANGE RATE FOR DIFFERENT CAMPUSES
class ExchangeRate(models.Model):
    """
    Stores conversion rates relative to your global HQ Reporting Currency (e.g., USD).
    Example: currency_code='EUR', rate_to_reporting_currency=1.08
    Meaning: 1 EUR = 1.08 USD
    """
    currency_code = models.CharField(max_length=3, unique=True, help_text="e.g., EUR, NGN, KES")
    rate_to_reporting_currency = models.DecimalField(
        max_digits=12, 
        decimal_places=6, 
        help_text="Multiply local currency by this factor to convert to HQ reporting currency."
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"1.00 {self.currency_code} = {self.rate_to_reporting_currency} HQ Units"
    
