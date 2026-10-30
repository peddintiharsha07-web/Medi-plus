from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core import throttle
from core.security import client_ip
from patients.models import PatientProfile

from .forms import DoctorRegistrationForm, HospitalAdminRegistrationForm, PatientRegistrationForm
from .models import AuditLog

LOGIN_USER_LIMIT = 5       # failed attempts per username ...
LOGIN_IP_LIMIT = 20        # ... and per IP address ...
LOGIN_WINDOW = 15 * 60     # ... within 15 minutes


def register_choice(request):
    return render(request, 'users/register_choice.html')


def register_patient(request):
    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():  # never leave a user without a patient profile
                user = form.save()
                PatientProfile.objects.create(user=user)  # a signal also creates the QR record
            login(request, user)
            AuditLog.objects.create(actor=user, action_type=AuditLog.ActionType.LOGIN,
                                    description='Patient registered and logged in',
                                    ip_address=client_ip(request))
            messages.success(request, 'Welcome! Your Medical ID and QR code have been generated.')
            return redirect('dashboard:home')
    else:
        form = PatientRegistrationForm()
    return render(request, 'users/register_patient.html', {'form': form})


def register_doctor(request):
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration submitted. A system administrator must approve your '
                                       'account before you can log in.')
            return redirect('users:login')
    else:
        form = DoctorRegistrationForm()
    return render(request, 'users/register_doctor.html', {'form': form})


def register_hospital(request):
    if request.method == 'POST':
        form = HospitalAdminRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration submitted. A system administrator must approve your '
                                       'hospital before you can log in.')
            return redirect('users:login')
    else:
        form = HospitalAdminRegistrationForm()
    return render(request, 'users/register_hospital.html', {'form': form})


def _safe_next(request):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return ''


def login_view(request):
    next_url = _safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or 'dashboard:home')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        ip = client_ip(request) or 'unknown'
        ctx = {'next': next_url}

        if (throttle.is_limited('login_user', username, LOGIN_USER_LIMIT, LOGIN_WINDOW)
                or throttle.is_limited('login_ip', ip, LOGIN_IP_LIMIT, LOGIN_WINDOW)):
            messages.error(request, 'Too many failed sign-in attempts. Please wait 15 minutes and try again.')
            return render(request, 'users/login.html', ctx, status=429)

        user = authenticate(request, username=username, password=password)
        if user is None:
            throttle.record('login_user', username)
            throttle.record('login_ip', ip)
            messages.error(request, 'Invalid username or password.')
            return render(request, 'users/login.html', ctx)
        if user.role in ('DOCTOR', 'HOSPITAL_ADMIN') and user.status != 'APPROVED':
            messages.error(request, 'Your account is pending approval by a system administrator.')
            return render(request, 'users/login.html', ctx)
        if not user.in_good_standing:
            messages.error(request, 'Your account has been suspended. Contact support.')
            return render(request, 'users/login.html', ctx)

        throttle.reset('login_user', username)
        login(request, user)
        AuditLog.objects.create(actor=user, action_type=AuditLog.ActionType.LOGIN,
                                description=f'{user.username} logged in', ip_address=client_ip(request))
        return redirect(next_url or 'dashboard:home')
    return render(request, 'users/login.html', {'next': next_url})


@login_required
@require_POST
def logout_view(request):
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.LOGOUT,
                            description=f'{request.user.username} logged out', ip_address=client_ip(request))
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:home')


@login_required
def profile_view(request):
    return render(request, 'users/profile.html', {'user_obj': request.user})


def set_language_preference(request):
    if request.method == 'POST':
        lang = request.POST.get('language', 'en')
        request.session['django_language'] = lang
        if request.user.is_authenticated:
            request.user.preferred_language = lang
            request.user.save(update_fields=['preferred_language'])
    return redirect(request.META.get('HTTP_REFERER', '/'))
