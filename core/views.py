from django.http import HttpResponse
from django.shortcuts import render
from doctors.models import DoctorProfile
from hospitals.models import Hospital


def home(request):
    featured_doctors = DoctorProfile.objects.select_related('user', 'hospital').filter(
        user__status='APPROVED')[:6]
    featured_hospitals = Hospital.objects.filter(status='APPROVED')[:6]
    return render(request, 'core/home.html', {
        'featured_doctors': featured_doctors,
        'featured_hospitals': featured_hospitals,
    })


def about(request):
    return render(request, 'core/about.html')


def services(request):
    return render(request, 'core/services.html')


def contact(request):
    if request.method == 'POST':
        from django.contrib import messages
        messages.success(request, "Thanks for reaching out! Our team will get back to you shortly.")
    return render(request, 'core/contact.html')


def faq(request):
    return render(request, 'core/faq.html')


def search(request):
    query = request.GET.get('q', '').strip()
    doctors = DoctorProfile.objects.select_related('user', 'hospital').filter(user__status='APPROVED')
    hospitals = Hospital.objects.filter(status='APPROVED')
    if query:
        doctors = doctors.filter(specialization__icontains=query) | doctors.filter(
            user__first_name__icontains=query) | doctors.filter(user__last_name__icontains=query)
        hospitals = hospitals.filter(name__icontains=query) | hospitals.filter(city__icontains=query)
    return render(request, 'core/search_results.html', {
        'query': query, 'doctors': doctors[:20], 'hospitals': hospitals[:20],
    })


def healthz(request):
    """Liveness probe for Render: touches no database, exposes no data."""
    return HttpResponse('ok', content_type='text/plain')
