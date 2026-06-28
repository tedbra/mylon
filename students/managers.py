# students/managers.py
from django.db import models
from accounts.middleware import get_current_user_campus, is_current_user_director

class CampusIsolatedManager(models.Manager):
    def get_queryset(self):        
        
        queryset = super().get_queryset()
        
        # If it's a global network admin, show EVERYTHING
        if is_current_user_director():
            return queryset
            
        # Get the campus of the currently logged-in secretary/staff
        current_campus = get_current_user_campus()
        
        if current_campus:
            # Check if the model has a direct 'campus' field (like Student or GradeTermFee)
            has_direct_campus = any(f.name == 'campus' for f in self.model._meta.get_fields())
            
            if has_direct_campus:
                return queryset.filter(campus=current_campus)
                
            # If it doesn't have 'campus' but has a 'student' relationship (like Invoice or PaymentHistory)
            has_student_rel = any(f.name == 'student' for f in self.model._meta.get_fields())
            if has_student_rel:
                # Filter by tracing through the student relationship: student__campus
                return queryset.filter(student__campus=current_campus)
                
        # Safe default fallback
        return queryset.none()