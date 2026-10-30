from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import OWNER, resolve_access
from core.decorators import patient_required

from .files import serve_file
from .forms import PatientDocumentEditForm, PatientDocumentForm
from .models import LabReport, MedicalAttachment, PatientDocument, Prescription


@patient_required
def document_list(request):
    profile = request.user.patient_profile
    category = request.GET.get('category', '')
    documents = profile.documents.all()
    if category in PatientDocument.Category.values:
        documents = documents.filter(category=category)
    else:
        category = ''
    return render(request, 'patients/documents.html', {
        'profile': profile, 'documents': documents, 'category': category,
        'categories': PatientDocument.Category.choices})


@patient_required
def document_upload(request):
    profile = request.user.patient_profile
    if request.method == 'POST':
        form = PatientDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.patient = profile
            document.uploaded_by = request.user
            document.save()
            messages.success(request, 'Record saved.')
            return redirect('medical_records:document_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = PatientDocumentForm()
    return render(request, 'patients/document_form.html', {'form': form, 'editing': False})


@patient_required
def document_edit(request, pk):
    document = get_object_or_404(PatientDocument, pk=pk, patient=request.user.patient_profile)
    if request.method == 'POST':
        form = PatientDocumentEditForm(request.POST, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, 'Record updated.')
            return redirect('medical_records:document_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = PatientDocumentEditForm(instance=document)
    return render(request, 'patients/document_form.html', {'form': form, 'editing': True, 'document': document})


@patient_required
@require_POST
def document_delete(request, pk):
    get_object_or_404(PatientDocument, pk=pk, patient=request.user.patient_profile).delete()
    messages.info(request, 'Record deleted.')
    return redirect('medical_records:document_list')


# ---- Authenticated, permission-checked file download (the ONLY way files are served) ----
_KINDS = {
    'document': (PatientDocument.objects.select_related('patient__user'),
                 lambda o: o.patient, lambda o: o.title),
    'prescription': (Prescription.objects.select_related('record__patient__user'),
                     lambda o: o.record.patient, lambda o: f'prescription-{o.medication_name}'),
    'labreport': (LabReport.objects.select_related('record__patient__user'),
                  lambda o: o.record.patient, lambda o: o.title),
    'attachment': (MedicalAttachment.objects.select_related('record__patient__user'),
                   lambda o: o.record.patient, lambda o: o.description or 'attachment'),
}


def user_can_download(user, obj, kind):
    """(allowed, access). Shared by the HTML view and the REST API."""
    access = resolve_access(user, _KINDS[kind][1](obj))
    if not access.can_view_full:
        return False, access
    if kind == 'document' and access.level != OWNER and not obj.shared_with_doctors:
        return False, access
    return True, access


def file_label(obj, kind):
    return _KINDS[kind][2](obj)


@login_required
def file_download(request, kind, pk):
    if kind not in _KINDS:
        raise Http404
    queryset, get_patient, label = _KINDS[kind]
    try:
        obj = queryset.get(pk=pk)
    except (queryset.model.DoesNotExist, ValueError, ValidationError):
        raise Http404
    allowed, access = user_can_download(request.user, obj, kind)
    if not allowed:
        # 404 (not 403) so file ids cannot be probed; denied doctor attempts are still recorded.
        if request.user.role == 'DOCTOR':
            log_access(request, get_patient(obj), RecordAccessLog.Action.ACCESS_DENIED, access, detail=f'file {kind}')
        raise Http404
    if not obj.file:
        raise Http404
    log_access(request, get_patient(obj), RecordAccessLog.Action.DOWNLOAD_FILE, access,
               detail=f'{kind}: {label(obj)}'[:200])
    return serve_file(obj.file, label(obj), as_attachment=request.GET.get('download') == '1')
