from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, DecimalField

from mylon import settings
from .models import ExchangeRate, Student, Grade, PaymentHistory, Term, GradeTermFee, Invoice, Campus, StudentIdCounter, TransportRoute, ExtraItem 
from .forms import StudentEnrollmentForm, NewPaymentForm
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now 
from django.contrib.auth.decorators import login_required
from django.http import Http404
from expense.models import Requisition
from django.core.exceptions import ValidationError

# VIEW 1: ENROLL NEW STUDENT & AUTO-BILL CURRENT TERM
@login_required
def student_create_view(request):
    # 1. Operational Term Validation
    # 🎯 EMERGENCY DIAGNOSTIC
    print("🚀 TARGET ACQUIRED: The browser successfully reached student_create_view!")
    print("Method type is:", request.method)
    
    current_term = Term.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()
    if not current_term:
        messages.error(request, "Enrollment halted: No current operational Term has been set by administration.")
        return redirect('student_list')

    # Extract the user's campus profile authorization settings
    user_profile = request.user.profile

    if request.method == "POST":
        form = StudentEnrollmentForm(request.POST, request.FILES, user_profile=user_profile)
        
        if form.is_valid():
            try:
                # Wrap entries inside an atomic transaction for safe multi-table writes
                with transaction.atomic():
                    student = form.save(commit=False)
                    if not user_profile.is_director:
                        student.campus = user_profile.campus
                    else:
                        # For directors, pull the choice directly from the validated form data
                        student.campus = form.cleaned_data.get('campus')
                    
                    # 🛡️ Safety Check: Ensure the selected transport route belongs to the assigned campus
                    if student.needs_transport and student.transport_route:
                        if student.transport_route.campus != student.campus:
                            form.add_error('transport_route', "The selected transport route is not operational on this campus.")
                            raise ValidationError("Cross-campus transport assignment detected.")

                    # 🎯 ALPHANUMERIC ID GENERATION PASS
                    if not student.student_id:
                        current_date = now()
                        enrolled_year_full = student.enrollment_year or current_date.year
                        current_year_short = str(enrolled_year_full)[2:]  # E.g., "26"                        
                        # Grab the campus code securely (fallback if missing)
                        campus_code = student.campus.campus_code if student.campus and hasattr(student.campus, 'campus_code') else "SKL"
                        counter, created = StudentIdCounter.objects.select_for_update().get_or_create(
                            campus=student.campus,
                            year=enrolled_year_full
                        )
                        
                        # Step up the integer count sequence safely
                        counter.latest_sequence += 1
                        counter.save()
                        
                        # Build the clean target tracking ID layout: e.g., "MSA-26-0001"
                        student.student_id = f"S{campus_code}{current_year_short}{counter.latest_sequence:04d}"
                        print(f"✨ RE-CONSTRUCTED ALPHANUMERIC KEY: {student.student_id}")

                    student.save() 
                    form.save_m2m()
                    
                # 2. Redirect straight to the payment window (with our updated optional message)
                messages.success(
                    request, 
                    f"Profile for {student.name} created successfully! Proceed below to log a deposit, or skip if they are on scholarship."
                )
                return redirect('process_payment', student_id=student.student_id)
                
            except Exception as e:
                # 🎯 ADD THIS PRINT LINE RIGHT HERE:
                print("💥 DATABASE TRANSACTION CRASHED:", str(e))
                messages.error(request, f"Database transaction failed during registration: {str(e)}")
        else:
            # Re-routed: Dump validation hitches down to the terminal logs
            print("❌ REAL FORM VALIDATION ERRORS:", form.errors.get_json_data())
            print("❌ REJECTED FIELDS:", form.errors)
            print("📋 RAW POST DATA:", request.POST)
    else:
        form = StudentEnrollmentForm(user_profile=user_profile)
        
    # 3. Dynamic Multi-Tenant Fee Grid Construction
    term_fees = GradeTermFee.objects.filter(term=current_term).select_related('grade', 'campus')
        
    return render(request, 'students/student_form.html', {
        'form': form, 
        'current_term': current_term,
        'term_fees': term_fees
    })



# VIEW 2: AUTOMATED TERM ROLLOVER / BULK INVOICING TRIGGER
@login_required
def run_term_rollover_view(request):
    """Admin feature tool to automatically generate term statements school-wide."""
    current_term = Term.objects.filter(is_current=True).first()
    if not current_term:
        messages.error(request, "Rollover aborted: No term is marked as Current.")
        return redirect('revenue_dashboard')
        
    if request.method == "POST":
        active_students = Student.objects.filter(status='ACTIVE')
        invoices_created = 0
        skipped = 0
        
        for student in active_students:
            # Ensure we do not generate double invoices if this routine runs twice
            if not Invoice.objects.filter(student=student, term=current_term).exists():
                fee_rule = GradeTermFee.objects.filter(grade=student.grade, term=current_term).first()
                fee_amount = fee_rule.amount if fee_rule else 0.00
                
                Invoice.objects.create(student=student, term=current_term, amount=fee_amount)
                invoices_created += 1
            else:
                skipped += 1
                
        messages.success(request, f"Rollover completed. Billed {invoices_created} students for {current_term} ({skipped} skipped).")
        return redirect('revenue_dashboard')
        
    return render(request, 'students/rollover_confirm.html', {'current_term': current_term})



# VIEW 3: STUDENT DETAILS ADMISSION FORM WITH LEDGER ARCHIVE
@login_required
def student_detail_view(request, student_id):
    """Loads a student detail page using a direct lookup on their custom identifier string."""
    
    # Surgical direct match lookup against your existing unique student_id string field!
    student = get_object_or_404(Student, student_id=student_id)
    current_term = Term.objects.filter(is_current=True).first()
    active_invoice = Invoice.objects.filter(student=student, term=current_term).first()
    
    context = {
        'student': student,
        'active_invoice': active_invoice,
        'current_term': current_term,
    }
    return render(request, 'students/student_detail.html', context)



# VIEW 4: LOG AND POST PAYMENTS AGAINST STUDENT PROFILES
@login_required
def process_payment_view(request, student_id):
    # Fetch the student using your string student_id via your multi-tenant manager
    student = get_object_or_404(Student, student_id=student_id)
    
    if request.method == "POST":
        form = NewPaymentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.student = student
                    payment.processed_by = request.user
                    payment.save()
                
                # 🎯 FIX 1: Stripped out the hardcoded '$' currency symbol
                messages.success(
                    request, 
                    f"Payment of {payment.amount_paying:,.2f} processed successfully."
                )
                
                # 🎯 FIX 2: Explicitly pass the string student_id parameter to ensure 
                # Django's URL resolver never falls back to the database integer PK.
                return redirect('student_detail', student_id=str(student.student_id))
                
            except Exception as e:
                messages.error(request, f"Payment execution failed: {str(e)}")
    else:
        form = NewPaymentForm()
        
    return render(request, 'students/payment_form.html', {
        'form': form, 
        'student': student
    })



# VIEW 5: GENERAL LIST VIEW
@login_required
def student_list_view(request):
    if request.user.profile.is_director:
        return render(request, 'students/student_list_admin.html', {
            'students': Student.objects.all().select_related('campus','grade'),
            'grades': Grade.objects.all(),
            'campuses': Campus.objects.all(),
        })

    else:
        return render(request, 'students/student_list.html', {
            'students': Student.objects.filter(status='ACTIVE').select_related('grade'),
            'grades': Grade.objects.all()
        })



# VIEW 6: ADMIN UTILITY TO SYNC ALL CURRENT INVOICES TO MATCH MASTER PRICE MATRIX
@login_required
def sync_current_term_fees_view(request):
    """
    Administrative utility to push master price adjustments (Tuition, Transport, or Extras)
    to all active invoices globally for the current term.
    """
    if request.method == "POST":
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, "Sync aborted: No term is currently marked as active.")
            return redirect('revenue_dashboard')

        # Fetch active students using select_related to keep database queries minimal
        # Use global_objects if bypassing multi-tenant filtering to fix ALL campuses at once from HQ
        active_students = Student.global_objects.filter(status='ACTIVE').select_related('campus', 'grade', 'transport_route')
        
        updated_count = 0
        
        # Wrap the global updates in a single atomic transaction for database safety
        with transaction.atomic():
            for student in active_students:
                # Run our model's multi-tier recalculation logic
                student.sync_current_term_invoice()
                updated_count += 1

        messages.success(
            request, 
            f"Global master sync complete! Recalculated and synchronized {updated_count} active student invoices across all tiers."
        )
        return redirect('revenue_dashboard')
        
    return redirect('revenue_dashboard')


# VIEW 7: DETAILED REVENUE DASHBOARD WITH MULTI-CAMPUS AND GRADE BREAKDOWN
@login_required
def revenue_dashboard_view(request):
    current_term = Term.objects.filter(is_current=True).first()
    user_profile = request.user.profile

    # --- BASELINE NETWORK TOTALS (FOR MACRO CARDS) ---
    total_pupils = Student.objects.filter(status='ACTIVE').count()
        
    # ==========================================
    # BRANCH PATH A: GLOBAL ADMIN EXECUTIVE CORE
    # ==========================================
    if user_profile.is_director:
        all_campuses = Campus.objects.all()
        all_grades = Grade.objects.all()
        campus_data = []

        rates = { rate.currency_code: rate.rate_to_reporting_currency for rate in ExchangeRate.objects.all()}
        total_fees = Decimal('0.00')
        total_paid = Decimal('0.00')

        for campus in all_campuses:
            # Macro stats for THIS specific campus
            campus_pupils = Student.objects.filter(campus=campus, status='ACTIVE').count()
            campus_pupil_transport = Student.objects.filter(campus=campus, status='ACTIVE', needs_transport=True).count()
            #c_billed = Invoice.objects.filter(student__campus=campus, term=current_term).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            
            campus_currency = campus.currency_code if hasattr(campus, 'currency_code') else settings.DEFAULT_CURRENCY     
            conversion_factor = rates.get(campus_currency, Decimal('1.000000'))

            campus_billed = Decimal('0.00')
            campus_arrears = Decimal('0.00')
            campus_due = Decimal('0.00')
            campus_paid = Decimal('0.00')
            campus_transport = Decimal('0.00')
            for student in Student.objects.filter(campus=campus, status='ACTIVE'):
                campus_paid += student.current_term_paid
                campus_billed += student.current_term_fees_billed
                campus_arrears += student.current_term_arrears
                campus_transport += student.current_term_tranport

            campus_due = campus_billed + campus_arrears    
            campus_balance = max(campus_due - campus_paid, Decimal('0.00'))
            campus_rate = int((campus_paid / campus_due) * 100) if campus_due > 0 else 0

            # Grade breakdown for THIS specific campus
            grade_breakdown = []
            for grade in all_grades:
                fee_rule = GradeTermFee.objects.filter(campus=campus, grade=grade, term=current_term).first()
                fee_per_student = fee_rule.amount if fee_rule else Decimal('0.00')
                
                grade_pupils = Student.objects.filter(campus=campus, grade=grade, status='ACTIVE')
                grade_pupil_count = grade_pupils.count()
                grade_pupil_count_transport = grade_pupils.filter(needs_transport=True).count()
                
                #g_billed = Invoice.objects.filter(student__campus=campus, student__grade=grade, term=current_term).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                grade_paid = Decimal('0.00')
                grade_billed = Decimal('0.00')
                grade_arrears = Decimal('0.00')
                grade_transport = Decimal('0.00')
                for student in grade_pupils:
                    grade_billed += student.current_term_fees_billed
                    grade_arrears += student.current_term_arrears
                    grade_paid += student.current_term_paid
                    grade_transport += student.current_term_tranport
                
                grade_due = grade_billed + grade_arrears
                grade_balance = max(grade_due - grade_paid, Decimal('0.00'))
                grade_rate = int((grade_paid / grade_due) * 100) if grade_due > 0 else 0

                grade_breakdown.append({
                    'title': grade.title,
                    'fee_per_student': fee_per_student,
                    'grade_count': grade_pupil_count,
                    'grade_count_transport' : grade_pupil_count_transport,
                    'grade_billed': grade_billed,
                    'grade_arrears': grade_arrears,
                    'grade_due' : grade_due,
                    'grade_paid': grade_paid,
                    'grade_balance': grade_balance,
                    'grade_tranport': grade_transport,
                    'grade_collection_percentage': grade_rate,
                })

            total_fees += conversion_factor*campus_due
            total_paid += conversion_factor*campus_paid

            campus_data.append({
                'name': campus.name,
                'campus_count': campus_pupils,
                'campus_count_tranport': campus_pupil_transport,
                'campus_billed': campus_billed,
                'campus_arrears': campus_arrears,
                'campus_due' : campus_due,
                'campus_paid': campus_paid,
                'campus_balance': campus_balance,
                'campus_transport' : campus_transport,
                'campus_collection_percentage': campus_rate,
                'grades': grade_breakdown,
                'campus_currency': campus_currency,
            })

        total_balance = max(total_fees - total_paid, Decimal('0.00'))
        global_percentage = int((total_paid / total_fees) * 100) if total_fees > 0 else 0
        context = {
            'current_term': current_term,
            'total_pupils': total_pupils,
            'total_fees': total_fees,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'global_percentage': global_percentage,        
        }
        context['campus_data'] = campus_data
        context['is_director'] = user_profile.is_director
        context['is_global_admin'] = user_profile.is_global_admin

        return render(request, 'students/dashboard_admin.html', context)

    # ==========================================
    # BRANCH PATH B: LOCAL SECRETARY CORE
    # ==========================================
    else:
    
        term_invoices = Invoice.objects.filter(term=current_term) if current_term else Invoice.objects.none()
        total_fees = term_invoices.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        active_students = Student.objects.filter(status='ACTIVE')
        
        pupils_count_tranport = active_students.filter(needs_transport=True).count()
        
        total_transport = Decimal('0.00')
        total_arrears = Decimal('0.00')
        total_billed = Decimal('0.00')
        total_due = Decimal('0.00')
        total_paid = Decimal('0.00')
        for student in active_students:
            total_paid += student.current_term_paid
            total_billed += student.current_term_fees_billed
            total_due += student.current_term_total_due
            total_arrears += student.current_term_arrears
            total_transport += student.current_term_tranport

        total_balance = max(total_due - total_paid, Decimal('0.00'))
        global_percentage = int((total_paid / total_due) * 100) if total_due > 0 else 0

        # Base context that both dashboards will share
        context = {
            'current_term': current_term,
            'total_pupils': total_pupils,
            'total_pupils_tranport': pupils_count_tranport,
            'total_due': total_due,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'total_transport': total_transport,
            'total_arrears' : total_arrears,
            'global_percentage': global_percentage,
            'campus_currency': user_profile.campus.currency_code if user_profile.campus and hasattr(user_profile.campus, 'currency_code') else settings.DEFAULT_CURRENCY,        
        }
        all_grades = Grade.objects.all()
        processed_grades = []

        for grade in all_grades:
            fee_rule = GradeTermFee.objects.filter(grade=grade, term=current_term).first()
            fee_per_student = fee_rule.amount if fee_rule else Decimal('0.00')
            
            pupils_in_grade = Student.objects.filter(grade=grade, status='ACTIVE')
            grade_pupil_count = pupils_in_grade.count()
            grade_pupils_count_transport = pupils_in_grade.filter(needs_transport=True).count()
            
            #grade_fees_billed = Invoice.objects.filter(student__grade=grade, term=current_term).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            grade_transport = Decimal('0.00')
            grade_arrears = Decimal('0.00')
            grade_billed = Decimal('0.00')
            grade_due = Decimal('0.00')
            grade_paid = Decimal('0.00')
            #grade_fees_paid = Decimal('0.00')
            for student in pupils_in_grade:
                grade_paid += student.current_term_paid
                grade_billed += student.current_term_fees_billed
                grade_due += student.current_term_total_due
                grade_arrears += student.current_term_arrears
                grade_transport += student.current_term_tranport

                
            grade_balance = max(grade_due - grade_paid, Decimal('0.00'))
            grade_rate = int((grade_paid / grade_due) * 100) if grade_due > 0 else 0
                
            processed_grades.append({
                'title': grade.title,
                'fee_per_student': fee_per_student,
                'grade_count': grade_pupil_count,
                'grade_count_transport':grade_pupils_count_transport,
                'grade_billed': grade_billed,
                'grade_due': grade_due,
                'grade_arrears': grade_arrears,
                'grade_paid': grade_paid,
                'grade_balance': grade_balance,
                'grade_transport': grade_transport,
                'grade_collection_percentage': grade_rate,                
            })

        context['processed_grades'] = processed_grades
        return render(request, 'students/dashboard.html', context)



# VIEW 8: GLOBAL COHORT ANALYTICS AND REVENUE ANALYTICS DASHBOARD


# VIEW 9: STUDENT DETAILS UPDATE VIEW
@login_required
def student_update_view(request, student_id):
    """
    Administrative profile editor that safely manages structural mutations 
    and handles automatic invoice recalculation loops.
    """
    # 1. Fetch the student profile while enforcing campus isolation automatically via the manager
    student = get_object_or_404(Student, student_id=student_id)
    current_term = Term.objects.filter(is_current=True).first()
    user_profile = request.user.profile

    if request.method == "POST":
        form = StudentEnrollmentForm(request.POST, request.FILES, instance=student, user_profile=user_profile)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    student = form.save() 
                    form.save_m2m()

                messages.success(request, f"Profile for {student.name} updated successfully.")
                return redirect('student_detail', student_id=student.student_id)
                
            except Exception as e:
                messages.error(request, f"Profile modification failed: {str(e)}")
        else:
            # 🎯 Move validation error tracking here, where it actually belongs!
            print("❌ REAL FORM VALIDATION FAILED:", form.errors.as_data())
    else:
        # 🎯 GET Request: Pre-populate the form normally
        form = StudentEnrollmentForm(instance=student, user_profile=user_profile)
        # Deleted the form.errors print line from here!

    # Gather the fee matrix rules for the dynamic JavaScript tuition estimator display
    term_fees = GradeTermFee.objects.filter(term=current_term).select_related('grade', 'campus')

    # 🎯 REUSE TRICK: We pass a 'is_update' boolean flag to let our template dynamically shift copy headings
    return render(request, 'students/student_form.html', {
        'form': form,
        'student': student,
        'current_term': current_term,
        'term_fees': term_fees,
        'is_update': True
    })



# VIEW 10: DEACTIVATING A STUDENT IN THE SYSTEM
@login_required
def student_delete_view(request, student_id):
    """
    Administrative utility to safely archive student profiles instead of hard deletion,
    preserving historical data integrity and allowing for potential future restoration.
    """
    student = get_object_or_404(Student, student_id=student_id)

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Instead of deleting, we mark the status as 'INACTIVE' to preserve historical records
                student.status = 'INACTIVE'
                student.save()
                
                messages.success(request, f"Profile for {student.name} has been archived successfully.")
                return redirect('student_list')
        except Exception as e:
            messages.error(request, f"Profile archival failed: {str(e)}")
            return redirect('student_detail', student_id=student.student_id)

    return render(request, 'students/student_confirm_delete.html', {'student': student})




