from django.http import Http404
from rest_framework.decorators import action

from consents.audit import log_access
from consents.models import RecordAccessLog
from medical_records.files import serve_file
from medical_records.views import file_label, user_can_download


class FileDownloadMixin:
    """Adds GET <id>/download/ (JWT or session) that streams the file after a policy check."""
    file_kind = None

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        obj = self.get_object()  # queryset is already consent-scoped
        allowed, access = user_can_download(request.user, obj, self.file_kind)
        if not allowed:
            raise Http404
        patient = obj.patient if self.file_kind == 'document' else obj.record.patient
        label = file_label(obj, self.file_kind)
        log_access(request, patient, RecordAccessLog.Action.DOWNLOAD_FILE, access,
                   detail=f'{self.file_kind}: {label}'[:200])
        return serve_file(obj.file, label, as_attachment=request.query_params.get('inline') != '1')
