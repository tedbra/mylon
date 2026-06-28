from django.urls import path
from . import views
from . import views_admin
from . import views_summary

urlpatterns = [
    path('', views.revenue_dashboard_view, name='revenue_dashboard'),    
    path('list', views.student_list_view, name='student_list'),    
    path('register/', views.student_create_view, name='student_create'),
    path('analytics/', views_summary.global_analytics_dashboard, name='global_analytics_dashboard'),
    path('analytics/summary/', views_summary.term_summary_dashboard, name='term_summary_dashboard'),
    path('analytics/summary/export/', views_summary.export_term_summary_excel, name='export_term_summary_excel'),
    # 🚀 New Administrative Action Routings
    path('control/', views_admin.admin_work, name='admin_work'),
    path('control/rollover/', views_admin.execute_automatic_next_term_rollover, name='execute_auto_rollover'),
    path('control/recalculate-fees/', views_admin.recalculate_current_term_fees, name='recalculate_current_fees'),    
    path('control/export/excel/', views_admin.export_students_excel, name='export_students_excel'),
    path('control/export/excel_all/', views_admin.export_students_excel_all, name='export_students_excel_all'),  
    path('scholarship/review/', views_admin.scholarship_review_dashboard, name='scholarship_review_dashboard'),  

    path('<str:student_id>/', views.student_detail_view, name='student_detail'),
    path('<str:student_id>/edit/', views.student_update_view, name='student_update'),
    path('<str:student_id>/payment/', views.process_payment_view, name='process_payment'),
    
]