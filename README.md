# MedGrid — Digital Medical Record Management System

A centralized, role-based healthcare platform built with **Django + Django REST
Framework**. Patients get a QR-verified Medical ID; doctors manage records and
prescriptions; hospitals manage doctors, departments and appointments; system
administrators approve accounts and audit the whole platform.

## Tech stack

- **Backend:** Python, Django 6, Django REST Framework, Simple JWT
- **Frontend:** Django templates (HTML/CSS/JS), no build step required
- **Database:** SQLite by default (swap to MySQL/Postgres by editing `DATABASES` in settings.py)
- **QR codes:** `qrcode` + `Pillow`, generated automatically on patient registration

## Quick start

```bash
cd medrecord_system
python3 -m venv venv && source venv/bin/activate     # optional but recommended
pip install -r requirements.txt

export DJANGO_DEBUG=1                                  # local development only (production keeps DEBUG off)
python3 manage.py migrate
python3 manage.py createsuperuser                     # creates your first login
python3 manage.py seed_demo                            # optional: demo hospital/doctor/patient
python3 manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

> After creating a superuser, open `/admin/`, find your user under **Users**,
> and set **role = System Administrator** and **status = Approved** — the
> system admin dashboard at `/dashboard/` checks the `role` field.
> `seed_demo` does this for you automatically for demo accounts (see below).

### Demo accounts (created by `manage.py seed_demo`)

| Role            | Username             | Password     |
|-----------------|-----------------------|--------------|
| Hospital Admin  | `cityhospital_admin`  | `Demo@12345` |
| Doctor          | `dr_arjun`             | `Demo@12345` |
| Patient         | `asha_rao`             | `Demo@12345` (has consented to `dr_arjun`) |
| Patient         | `meera_iyer`           | `Demo@12345` (has consented to nobody)     |

`seed_demo` refuses to run when `DJANGO_DEBUG` is off (it creates accounts with a well-known password).

Plus whatever superuser you create via `createsuperuser` — set its role to
`SYSTEM_ADMIN` in `/admin/` as noted above.

## Privacy & access model (read this first)

Every page and API endpoint decides what a viewer may see through **one function**: `consents.policy.resolve_access(user, patient)`.

| Viewer | Access |
|---|---|
| The patient | Everything of their own |
| Doctor **with the patient's consent** | Read (or read + add consultation notes), until the consent expires or is removed |
| Doctor flagged *emergency-authorized*, **without** consent | Critical info only (blood group, allergies, medications, chronic conditions, emergency contact, organ-donor), via a "break-glass" form that needs a reason and is logged |
| Any other doctor, hospital admin, system admin | **Nothing** (admins manage the platform; they do not read clinical records) |

* Patients grant consent in **Privacy & Access** (choose doctor, duration 7 d – 1 yr, view-only or view + add notes), or approve a doctor's request. They can remove access instantly.
* Documents a patient uploads have a *"Shared with doctors"* switch; untick it to keep one private even from consented doctors.
* Every non-owner access (view, file download, QR scan, emergency use, **and denied attempts**) is written to `RecordAccessLog` (visible to the patient) and to the `AuditLog`.
* Medical files are **never** served from `/media/`. They stream through permission-checked views / API `download/` actions.

### QR codes
* Each patient has one QR. It encodes `https://<your-host>/q/<random-uuid4-token>/` — no Medical ID, no health data.
* Scanning requires login (the login page returns to the scan). The scanner then sees only what the table above allows.
* Patients can **download** (PNG), **generate a new** code (old one dies immediately) or **disable** it. New codes expire after `QR_TOKEN_LIFETIME_DAYS` (default 365; `0` = never).
* Unknown, revoked, rotated and expired tokens all give the *same* 404 page; 10 bad scans in 10 min locks the scanner out for a while.

## Configuration (environment variables)

See `.env.example` for the full list. The essentials:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | **Required** when `DJANGO_DEBUG` is off (app refuses to start without it) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames (Render's own hostname is added automatically) |
| `DATABASE_URL` | Postgres URL; if unset, SQLite `db.sqlite3` is used (unchanged default) |
| `AWS_STORAGE_BUCKET_NAME` (+ `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`) | Durable **private** storage for medical documents (S3 / Cloudflare R2 / Backblaze B2) |
| `MEDIA_ROOT` | Alternative: a mounted Render persistent disk, e.g. `/var/data/media` |
| `SITE_BASE_URL` | URL embedded in QR codes (defaults to the Render hostname) |
| `DJANGO_DEBUG` | `1` for local development only |

## Deploying the update to Render

> Render's local disk is **wiped on every deploy**. Without S3-compatible storage (or a persistent disk) uploaded
> medical documents *will be lost*. `manage.py check --deploy` warns about this (`medgrid.W001`).

1. Commit the updated project (**do not commit** `db.sqlite3`, `media/`, `.env` — they are git-ignored).
2. In the Render dashboard → your service → **Environment**, set at least `DJANGO_SECRET_KEY` (generate a **new** one: the old
   key was committed to the repository and must be considered public — rotating it signs everyone out once), your storage
   variables, and `DATABASE_URL` if you use Postgres. Remove any old `DEBUG` variable.
3. **Build command:** `./build.sh`  (= `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`)
4. **Start command:** `gunicorn medrecord_system.wsgi:application --workers 3 --timeout 60`
5. **Health check path:** `/healthz/`
6. If `manage.py` is not at the repository root, set Render's *Root Directory* to the folder that contains it.

Then verify: `python manage.py check --deploy` (run in the Render shell) should only show the optional HSTS warnings.

Migrations are purely additive (4 new migrations: `core.0001`, `consents.0001`, `medical_records.0003`, `qr_management.0002`);
existing rows are untouched. **Existing QR codes keep working** until the patient rotates them — they do not expire until then.

> **Behaviour change for existing data:** doctors previously saw every patient. Now a doctor sees a patient only after that
> patient consents. Existing doctor↔patient relationships are *not* auto-converted into consents (the patient never agreed
> to that) — doctors request access and patients approve.

## Tests

```bash
python manage.py test          # 125 tests: auth, ownership, consent, QR, uploads, API leak regression
```

## Trying it by hand (after `seed_demo`)

1. Log in as `asha_rao` → **My Documents → Upload** a PDF → it appears in the list; **My Medical ID & QR** → *Download QR*.
2. Log in as `meera_iyer` (private window) → try to open Asha's file URL: **404**.
3. Log in as `dr_arjun` → open Asha's QR link (or **Scan QR → paste**) → Asha's records and her shared document are shown.
4. As `dr_arjun` open Meera's QR link: only the **Limited access / emergency** gate appears; enter a reason → critical info only.
5. As `meera_iyer` → **Privacy & Access**: the emergency access and reason are in the log. Click **Generate a new QR code** → the old link now says *not valid*.
6. As `dr_arjun` → **Search Patient** (Meera's Medical ID) → *Request access*. As Meera → **Approve**. The doctor now sees her under **My Patients**; Meera → **Remove access** locks it again.

## What's implemented

- **Auth & roles** — custom `User` model (`users` app) with four roles, role-based
  redirect after login, doctor/hospital accounts requiring system-admin approval.
- **Patients** — registration auto-generates a Medical ID + QR code (via a signal
  in `patients/signals.py`), medical record viewing, appointment booking, profile
  editing, allergy/vaccination display, emergency-access transparency log.
- **Doctors** — profile completion, patient search by Medical ID, QR-token lookup,
  record creation with inline prescriptions, appointment accept/reject/complete.
- **Hospitals** — profile + approval workflow, departments, staff, doctor roster,
  appointment monitoring, multi-hospital record-share requests.
- **System admin** — hospital/doctor approval queues, account suspension, full
  audit log (`users.AuditLog`), platform analytics.
- **Emergency Access Mode** — QR/token lookup that returns *only* critical fields
  (blood group, allergies, medications, chronic conditions, emergency contact,
  organ-donor status), logs every access, and is visible to the patient afterward.
- **REST API** — full DRF router under `/api/` (patients, doctors, hospitals,
  medical records, appointments, QR codes, emergency logs, audit logs) with
  JWT auth (`/api/auth/token/`) and role-scoped querysets.
- **Design system** — a distinct clinical-trust visual identity (deep teal-green +
  warm gold, Fraunces/Inter/IBM Plex Mono type system) defined in
  `static/css/main.css`, with a signature "digital health card" component used
  throughout.

## What you'll likely want to extend for production or a fuller demo

These were intentionally scoped down to keep the delivered code working end-to-end
rather than partially stubbed:

- **Multilingual support** — the `LANGUAGES` setting and `LocaleMiddleware` are
  wired up, and users have a `preferred_language` field, but the `.po` translation
  files for Telugu/Hindi/Tamil/Kannada/Malayalam aren't populated yet. Run
  `django-admin makemessages -l te` (etc.) and translate the generated `.po` files
  under `locale/`.
- **File attachments on a doctor's consultation form** — patients can upload their own PDFs/images (done), and doctors can add
  prescription text; attaching files to a *doctor-authored* note is still API/admin-only.
- **SMS reminders** — marked optional in the spec; not implemented (would need a
  provider like Twilio).
- **In-browser QR camera scanning** — the QR now encodes a URL, so a phone's built-in camera opens it directly; the
  "Scan QR" page is a paste-the-link fallback.
- **Patient notifications** — there is no e-mail/SMS channel; access is shown in the patient's *Privacy & Access* page and
  on their dashboard instead (`patient_notified` is therefore always `False`).
- **Password reset by e-mail** — needs an e-mail backend; password *change* is implemented.

## Project structure

```
medrecord_system/
  core/            public pages (home, about, services, contact, FAQ, search)
  users/           custom User model, AuditLog, auth views, registration forms
  patients/        PatientProfile, Allergy, Vaccination + patient-facing views
  doctors/         DoctorProfile + doctor-facing views (search, records, appts)
  hospitals/       Hospital, Department, HospitalStaff, RecordShareRequest
  medical_records/ MedicalRecord, Prescription, LabReport, MedicalAttachment
  appointments/    Appointment model + booking/management views
  emergency/       EmergencyAccessLog + emergency access mode
  qr_management/   PatientQRCode model + QR generation service
  administration/  system-admin approval queues, audit logs, analytics
  dashboard/       role-based dashboard dispatch (HTML) + stats endpoint (API)
  api/             central DRF router aggregating every app's viewsets
  templates/       all HTML templates (base.html + per-app folders)
  static/css/      design system (main.css)
```

## REST API

Base path: `/api/`. Auth via JWT (`POST /api/auth/token/` with `username`/`password`)
or the browsable API's session auth (log in via `/accounts/login/` first).

Key endpoints: `patients/`, `doctors/`, `hospitals/`, `departments/`,
`medical-records/`, `prescriptions/`, `lab-reports/`, `appointments/`,
`documents/`, `qr-codes/` (+ `rotate/`, `revoke/`), `qr/<token>/`, `qr/<token>/emergency/`, `emergency-logs/`, `audit-logs/`,
`users/me/`, `dashboard/stats/`.

## Notes on the "college project + portfolio" framing

The codebase favors clarity over cleverness — plain Django views (not heavy
abstractions), one model per real-world concept, and a REST layer that mirrors
the HTML views so you can demo both "traditional site" and "API-driven" modes
in a presentation.
#   M e d i - p l u s  
 