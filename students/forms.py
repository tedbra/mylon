from django import forms
from .models import Student, PaymentHistory, Term, GradeTermFee, Invoice, Campus,TransportRoute, ExtraItem
from decimal import Decimal

class xStudentEnrollmentForm(forms.ModelForm):
    transport_route = forms.ModelChoiceField(
        queryset=TransportRoute.objects.none(), # Start empty
        required=False,
        empty_label="--- Select an Available Route ---"
    )

    class Meta:
        model = Student
        fields = [
            'name', 'date_of_birth', 'gender', 'grade', 
            'parent_name', 'phone_number_1', 'phone_number_2',
            'address', 'city', 'country', 'profile_picture',
            'needs_transport', 'transport_route', 'extra_items',  
            'status', 'proposed_scholarship_amount',
            'campus',  
            'image_use_consent',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'needs_transport': forms.Select(choices=[(False, 'No, Self Dropping'), (True, 'Yes, Requires Transport')]),
            'image_use_consent': forms.RadioSelect(choices=[(True, "Yes, I agree"), (False, "No, I do not authorize")]),            
            'extra_items': forms.CheckboxSelectMultiple(),
            'proposed_scholarship_amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.user_profile = kwargs.pop('user_profile', None)
        super().__init__(*args, **kwargs)
        
        # 1. Safely handle creation vs update for status field
        if not self.instance or not self.instance.pk:
            self.fields['status'].initial = 'ACTIVE'
            self.fields['status'].widget = forms.HiddenInput()
            self.fields['status'].required = False
        else:
            self.fields['status'].widget = forms.Select(choices=Student._meta.get_field('status').choices)

        # 2. Add form styling wrapper dynamically
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                field.widget.attrs.update({'class': 'form-control'})

        self.fields['image_use_consent'].required = False
        self.fields['transport_route'].required = False

        # 3. Dynamic Multi-Tenant Management
        if self.user_profile:
            if not self.user_profile.is_director:
                # Local Secretaries: Autofill campus and lock it down
                if self.user_profile.campus:
                    self.fields['campus'].initial = self.user_profile.campus
                    self.fields['campus'].widget = forms.HiddenInput()
                    self.fields['campus'].required = False
                    # 🔒 Multi-Tenant Lockdown: Only show routes belonging to this secretary's campus
                self.fields['transport_route'].queryset = TransportRoute.objects.filter(campus=self.user_profile.campus)
                
            else:
                # Directors: Must explicitly choose a campus via UI
                self.fields['campus'].required = True  
                # Directors can see all routes across all campuses
                self.fields['transport_route'].queryset = TransportRoute.objects.all()
                  


class StudentEnrollmentForm(forms.ModelForm):
    # 🎯 UI Toggle Field: This exists only on the form, NOT in the database model
    apply_for_scholarship = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.Select(choices=[(False, 'No Scholarship'), (True, 'Yes, Apply for Sponsor')])
    )

    transport_route = forms.ModelChoiceField(
        queryset=TransportRoute.objects.none(),
        required=False,
        empty_label="--- Select an Available Route ---"
    )

    class Meta:
        model = Student
        fields = [
            'name', 'date_of_birth', 'gender', 'grade', 
            'parent_name', 'phone_number_1', 'phone_number_2',
            'address', 'city', 'country', 'profile_picture',
            'needs_transport', 'transport_route', 'extra_items',  
            'status', 'proposed_scholarship_amount', # 🎯 Exclude model's on_scholarship
            'campus', 'image_use_consent',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'needs_transport': forms.Select(choices=[(False, 'No, Self Dropping'), (True, 'Yes, Requires Transport')]),
            'image_use_consent': forms.RadioSelect(choices=[(True, "Yes, I agree"), (False, "No, I do not authorize")]),
            'extra_items': forms.CheckboxSelectMultiple(),
            'proposed_scholarship_amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.user_profile = kwargs.pop('user_profile', None)
        super().__init__(*args, **kwargs)
        
        # Determine the initial toggle state if editing an existing student
        if self.instance and self.instance.pk:
            if self.instance.scholarship_status in ['PENDING', 'APPROVED']:
                self.fields['apply_for_scholarship'].initial = True
        
        # Status field setup
        if not self.instance or not self.instance.pk:
            self.fields['status'].initial = 'ACTIVE'
            self.fields['status'].widget = forms.HiddenInput()
            self.fields['status'].required = False
        else:
            self.fields['status'].widget = forms.Select(choices=Student._meta.get_field('status').choices)

        # Dynamic Multi-Tenant Management
        if self.user_profile:
            if not self.user_profile.is_director:
                if self.user_profile.campus:
                    self.fields['campus'].initial = self.user_profile.campus
                    self.fields['campus'].widget = forms.HiddenInput()
                    self.fields['campus'].required = False
                self.fields['transport_route'].queryset = TransportRoute.objects.filter(campus=self.user_profile.campus)
            else:
                self.fields['campus'].required = True  
                self.fields['transport_route'].queryset = TransportRoute.objects.all()

        if self.instance and self.instance.pk and self.instance.transport_route:
            current_route_qs = TransportRoute.objects.filter(pk=self.instance.transport_route.pk)
            self.fields['transport_route'].queryset = self.fields['transport_route'].queryset | current_route_qs

        # Styling
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                field.widget.attrs.update({'class': 'form-control'})

        self.fields['image_use_consent'].required = False
        self.fields['transport_route'].required = False

    # 🎯 State Controller Business Logic
    def save(self, commit=True):
        student = super().save(commit=False)
        is_applied = self.cleaned_data.get('apply_for_scholarship')

        if is_applied:
            # If they turned it on and it wasn't already approved, flag as pending
            if student.scholarship_status not in ['APPROVED', 'PENDING']:
                student.scholarship_status = 'PENDING'
        else:
            # If they explicitly turned it off, clear out values entirely
            student.scholarship_status = 'NONE'
            student.proposed_scholarship_amount = Decimal('0.00')
            student.scholarship_amount = Decimal('0.00')
            student.approved_by = None
            
        if commit:
            student.save()
            self.save_m2m()
        return student



# Form: Standard Payment Form
class NewPaymentForm(forms.ModelForm):
    class Meta:
        model = PaymentHistory
        fields = ['amount_paying', 'reference', 'date_paid']
        widgets = {'date_paid': forms.DateInput(attrs={'type': 'date'})}

