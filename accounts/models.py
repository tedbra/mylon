from django.db import models
from django.contrib.auth.models import User
from students.models import Campus  # Import Campus from your student app

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, null=True, blank=True)    
    is_global_admin = models.BooleanField(default=False, help_text="Designates whether this user has unrestricted, multi-campus oversight.")
    is_director = models.BooleanField(default=False, help_text="Designates whether this user is a director with elevated permissions.")
    #is_head_teacher = models.BooleanField(default=False, help_text="Designates whether this user is a campus Head Teacher of a campus.")
    #is_secretary = models.BooleanField(default=False, help_text="Designates whether this user is a campus Secretary.")


    def __str__(self):
        if self.is_global_admin:
            return f"{self.user.username} (Global Head Office)"
        elif self.is_director:
            return f"{self.user.username} (Director)"
        return f"{self.user.username} ({self.campus.name if self.campus else 'Unassigned Campus'})"

# Automatically create a UserProfile whenever a standard User is generated
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    instance.profile.save()