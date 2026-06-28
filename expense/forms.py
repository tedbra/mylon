# expense/forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import Requisition, RequisitionItem, ExpenseCategory
import datetime
from django.utils import timezone

def get_next_week_monday():
    today = timezone.localdate()
    days_ahead = 7 - today.weekday()
    return today + datetime.timedelta(days=days_ahead)

class RequisitionForm(forms.ModelForm): 
    class Meta:
        model = Requisition
        # 🎯 Include 'campus' here so admins can select it
        fields = ['campus', 'calendar_week']
        widgets = {
            'campus': forms.Select(attrs={
                'class': 'form-control',
                'style': 'padding: 10px; width: 100%; border: 1px solid #cbd5e1; border-radius: 6px; margin-bottom: 15px;'
            }),
            'calendar_week': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'style': 'padding: 10px; width: 100%; border: 1px solid #cbd5e1; border-radius: 6px;'
            })
        }

    def __init__(self, *args, **kwargs):
        # We pass a custom 'user' argument into the form initialization from views.py
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if not self.instance.pk and not self.initial.get('calendar_week'):
            self.initial['calendar_week'] = get_next_week_monday()
            
        # 🎯 Dynamic Multi-Tenant Form Security Rule:
        if user:
            user_profile = getattr(user, 'profile', None)
            is_global = user_profile.is_director if user_profile else getattr(user, 'is_director', False)
            
            if not is_global:
                # If they are a normal headteacher, hide the campus choice field entirely!
                self.fields.pop('campus')

class RequisitionItemForm(forms.ModelForm):
    cost_price = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control item-cost', 
            'placeholder': '0.00',
            'readonly': 'readonly',
            'style': 'background: transparent; border: none; outline: none; font-weight: 600; text-align: center; width: 100%; padding: 8px 0; cursor: default;'
        }))
    class Meta:
        model = RequisitionItem
        fields = ['expense_name', 'category', 'quantity', 'price_per_unit', 'cost_price']
        widgets = {
            'expense_name': forms.TextInput(attrs={'class': 'form-control item-name', 'placeholder': 'e.g. Sugar Bag 50kg'}),
            'category': forms.Select(attrs={'class': 'form-control item-category'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control item-qty', 'min': '1', 'value': '1'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control item-price', 'step': '0.01', 'placeholder': '0.00'}),
            
        }

# Generate the Dynamic Dynamic Multi-Row Line Item Engine
RequisitionItemFormSet = inlineformset_factory(
    Requisition,
    RequisitionItem,
    form=RequisitionItemForm,
    extra=0,            # Renders 1 blank row template by default out of the box
    can_delete=True,     # Allows users to check a checkbox to remove extra rows
)