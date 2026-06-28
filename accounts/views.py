# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from .forms import PremiumLoginForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect('student_list') # Send them straight to the directory if logged in
        
    if request.method == 'POST':
        form = PremiumLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # --- FIXED: Check if the user was trying to go to a specific protected page ---
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
                
            return redirect('student_list') # Redirect straight to the registry main table
    else:
        form = PremiumLoginForm()
        
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login') # Sends them cleanly back to your login view function