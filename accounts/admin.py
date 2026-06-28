from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

# 1. Clean, basic Inline layout without internal code hacks
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Institutional Profile Permissions'

# 2. Main Admin engine managing custom model saving routines safely
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = BaseUserAdmin.list_display + ('get_campus', 'get_director_status','get_global_admin_status')

    def save_model(self, request, obj, form, change):
        """
        Forces Django to commit the core User instance FIRST, which enables
        the post_save signal to build the empty profile smoothly.
        """
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """
        Intercepts related model updates. If a profile already exists,
        we fetch the pre-created instance instead of running an INSERT statement.
        """
        # Loop through active forms to catch our inline module
        for formset in formsets:
            if formset.model == UserProfile:
                # Iterate through inline instances filled out on screen
                instances = formset.save(commit=False)
                for instance in instances:
                    # Look up if our background post_save signal already made a profile row
                    profile, created = UserProfile.objects.get_or_create(user=instance.user)
                    
                    # Update fields dynamically from form parameters
                    profile.campus = instance.campus
                    profile.is_global_admin = instance.is_global_admin
                    profile.save()
                    
                # Mark formset as processed so Django doesn't run a duplicate insert
                formset.save_m2m()
            else:
                # Handle other built-in related formsets normally (like groups or user permissions)
                super().save_related(request, form, [formset], change)

    # Context Display Methods
    def get_campus(self, obj):
        try:
            return obj.profile.campus.name if obj.profile.campus else "Global Head Office"
        except UserProfile.DoesNotExist:
            return "Unassigned"
    get_campus.short_description = 'Assigned Campus'

    def get_global_admin_status(self, obj):
        try:
            return obj.profile.is_global_admin
        except UserProfile.DoesNotExist:
            return False
    get_global_admin_status.boolean = True
    get_global_admin_status.short_description = 'Global Admin'

    def get_director_status(self, obj):
        try:
            return obj.profile.is_director
        except UserProfile.DoesNotExist:
            return False
    get_director_status.boolean = True
    get_director_status.short_description = 'Director'

# 3. Unregister default settings and load our optimized suite
admin.site.unregister(User)
admin.site.register(User, UserAdmin)