# expense/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('requisitions/new/', views.requisition_create_view, name='requisition_create'),
    path('reports/', views.expense_report_view, name='expense_report'),
    path('reports/admin/', views.expense_report_admin_view, name='expense_report_admin'),    
    path('control/export/requisitions/', views.export_requisitions_excel, name='export_requisitions_excel'),

    path('requisitions/<int:pk>/edit/', views.requisition_update_view, name='requisition_update'),
    path('requisitions/<int:pk>/', views.requisition_detail_view, name='requisition_detail'),    
    path('requisitions/<int:pk>/status/<str:status_choice>/', views.update_requisition_status, name='update_requisition_status'),
]