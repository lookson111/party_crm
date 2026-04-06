# Project Context: party_crm

## Overview
CRM system for party work of the Russian Workers' Party (RPR / РПР) — Moscow branch. The application tracks newspaper distribution activities: when/where party members distribute newspapers at factory locations, quantities distributed, and generates periodic Excel reports.

**Tech Stack:**
- Django 4.2 (Python)
- PostgreSQL database (psycopg3)
- HTMX + Alpine.js + Bootstrap 5 for frontend
- XlsxWriter for Excel report generation
- Gunicorn for production

## Project Structure

```
party_crm/
├── config/              # Django settings, URLs, WSGI/ASGI
│   ├── settings.py      # Main settings (imports local_settings at bottom)
│   └── urls.py          # Root URL configuration
├── person/              # Custom user model, authentication, party member management
│   ├── models.py        # Person (custom User), PartyOrganization
│   └── views.py         # Login, logout, profile
├── press/               # Core business logic
│   ├── models.py        # Newspaper, Town, FactoryPoint, Distribution, Sympathizer, etc.
│   ├── views.py         # Distribution CRUD, reports, reference data management
│   ├── services/        # Business logic: distributions, report generation, email
│   └── management/      # Management commands (send_report)
├── helpers/             # Shared utilities (name_normalizer)
├── templates/           # Global base templates
└── static/              # CSS, JS (HTMX, Alpine.js, Bootstrap, Select2, jQuery)
```

## Key Models

### person app
- **Person** — Custom user model (`AUTH_USER_MODEL`), extends `AbstractUser`, uses `email` as `USERNAME_FIELD`. Has `party_member` (bool), `party_ticket_number`, `party_organization` (FK).
- **PartyOrganization** — Simple title field for party organization names.

### press app
- **Newspaper** — Party newspaper catalog (`title`, `short_title`).
- **NewspaperNumber** — Specific issue (`number`, `year` as DateField) linked to Newspaper.
- **Town** — Geographic town reference.
- **FactoryPoint** — Factory/enterprise location with title, description, geo coordinates. FK to Town.
- **Distribution** — Main event record: date, time, description. FK to Person (author) and FactoryPoint.
- **NewspaperNumbersOnDistribution** — Quantity of each newspaper issue distributed. FK to Distribution + NewspaperNumber.
- **DistributionPartyMembers** — How many newspapers each party member distributed. FK to Person + Distribution.
- **DistributionSympathizerMember** — How many newspapers each sympathizer distributed. FK to Sympathizer + Distribution.
- **Sympathizer** — Non-member supporters with `name` field.

## URL Patterns

| Path | Description |
|---|---|
| `login/` | Email-based login |
| `profile/` | User dashboard (person app) |
| `""` | List all distributions |
| `new-distrib/` | Create distribution record |
| `hx-distrib/<pk>/` | Delete distribution (HTMX) |
| `hx-newspaper-field/` | Dynamic newspaper fields (HTMX) |
| `report/` | Generate & email Excel report |
| `towns/`, `towns/<pk>/` | CRUD towns |
| `factory/` | CRUD factory points |
| `newspaper/`, `newspaper-numbers/` | CRUD newspapers and issues |
| `admin/` | Django admin |

**Note:** Several URLs/views are marked DEPRECATED (`hx-add-party-member/`, `hx-delete-pary-member/`).

## Coding Conventions

### Python/Django
- **Imports**: Standard library → Django → third-party → local app imports
- **Naming**: snake_case for functions/variables, PascalCase for models
- **URLs**: kebab-case with prefixes (`new-distrib/`, `hx-add-party-member/`)
- **HTMX views**: Use `hx_` prefix for HTMX-specific endpoints
- **Type hints**: Used inconsistently; service layer has partial typing

### Code Organization
- Business logic partially extracted into `services/` subdirectories
- Some views still contain significant logic (e.g., `new_distrib` ~80 lines)
- Use `select_related`/`prefetch_related` for query optimization

### Language
- All user-facing strings in Russian (`verbose_name`, error messages, templates)
- Locale: `ru-ru`, Timezone: `Europe/Moscow`

## Key Features

### Authentication
- Email-based login (no username field)
- Custom `Person` model with `USERNAME_FIELD = "email"`

### HTMX Integration
- Heavy use of HTMX for dynamic partial-page updates
- `render_block_to_string` for partial template rendering
- `django_htmx.middleware.HtmxMiddleware` in middleware stack
- `retarget` for targeting specific DOM elements

### Report Generation
- Excel reports with three sheets:
  1. "Общие данные" — All distributions with dates, factories, newspapers, quantities
  2. "Распространители" — Per-person monthly breakdown
  3. "Предприятия" — Per-factory monthly breakdown
- Can be generated via web UI (emailed) or management command
- Management command: `python manage.py send_report` (requires `REPORT_MONTH_EMAIL` in settings)

## Testing

**Minimal test coverage:**
- `person/tests.py` has basic user manager tests
- `press/tests.py` is empty
- No integration tests, view tests, or service layer tests

## Configuration

- Settings imports `config/local_settings.py` at bottom (gitignored) — contains `DATABASES`, `SECRET_KEY`, `EMAIL` settings, `REPORT_MONTH_EMAIL`
- Database: PostgreSQL (psycopg3)
- Static files: Bootstrap 5, HTMX, Alpine.js, Select2, jQuery, service worker

## Notable Code Quality Observations

- Several DEPRECATED views still present in codebase
- TODO comment exists in `towns_delete`: `#TODO: Слить с предыдущим методом`
- `person/signals.py` references a broken signal pattern (signals on `User` model trying to create `Person`, but `Person` IS the user model)
- Mixed code organization — some logic in services, some in views

## Project Issues Audit

### Critical Issues

| # | File | Issue |
|---|---|---|
| C1 | `press/views.py:268,296,330,353` | `HttpResponse(request, '', status='200')` — `HttpResponse` takes content as first arg, not request. Renders `HttpRequest` object as string. Fix: `HttpResponse('', status=200)` |
| C2 | `person/signals.py` | Broken signals on `django.contrib.auth.models.User` — `Person` IS the user model (`AUTH_USER_MODEL`), signals will never fire correctly and would crash. Delete entire file |
| C3 | `press/views.py:312,316` | `title.strip == ''` — `.strip` is a method, needs parentheses: `title.strip() == ''`. As-is, validation never triggers |
| C4 | `press/views.py:105` | Division by zero risk: `all_quantity // all_memb_count` when `all_memb_count` could be 0 |
| C5 | `person/views.py:30-33` | `NoneType` error in profile view: if no matching `Sympathizer` found, `.filter(member_id=sympathizer.pk)` raises `AttributeError` |

### High Severity

| # | File | Issue |
|---|---|---|
| H1 | `press/views.py` | DELETE operations read ID from `request.GET.get('id')` — should use URL path params or `request.POST`, not query strings for destructive ops |
| H2 | `config/settings.py` | No security settings: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF` all missing |
| H3 | `config/settings.py:113` | No `local_settings.example.py` template for new devs/deployments |
| H4 | `press/services/distributions.py:5`, `factory.py:4` | `filter(**filter_by)` accepts arbitrary dict from POST — whitelist allowed keys |

### Medium Severity

| # | File | Issue |
|---|---|---|
| M1 | `press/views.py:266` | `Town.objects.get(pk=pk)` raises `DoesNotExist` → 500. Use `get_object_or_404` |
| M2 | `press/views.py` (all delete views) | No permission checks — any authenticated user can delete any object |
| M3 | `press/models.py:87` | `Distribution.count_members()` broken: `len(self.party_members)` on `RelatedManager` — needs `.count()` |
| M4 | `press/models.py:20` | Confusing `related_name='newspaper'` on `NewspaperNumber` — should be `related_name='numbers'` |
| M5 | `press/views.py:287-300` | Unreachable code: `if request.method == 'DELETE'` should be `elif` (same in `newspaper`, `newspaper_numbers`) |
| M6 | `press/services/report.py:41-49` | O(n*m) nested loop for member matching — use dict keyed by member ID |
| M7 | `press/views.py:39-133` | `new_distrib` view ~90 lines with business logic — extract to service layer |
| M8 | `press/views.py:124,134` | `print()` debug statements left in production — use `logging` |
| M9 | `templates/base.html:11` | `meta_descripiton` typo — should be `meta_description` |

### Low Severity / Technical Debt

| # | File | Issue |
|---|---|---|
| L1 | `press/views.py` | DEPRECATED views still present: `new_party_member_distrib`, `new_sympathizer_distrib`, `hx_delete_party_member`, `hx_add_party_member` |
| L2 | `press/services/report.py:52-72` | Commented-out "OLD REALISATION" code — remove (it's in git history) |
| L3 | `press/views.py:365` | Typo: `err_lsit` → `err_list` |
| L4 | Multiple | Typo: `factoryes` → `factories` |
| L5 | Templates | Typo: `sypathizer_member_field.html` → `sympathizer_...` |
| L6 | `press/models.py` | No custom `indexes = [...]` — `Distribution.distribution_date`, FK fields would benefit |
| L7 | `press/models.py:80` | Typo: `autor` → `author` |
| L8 | `press/admin.py:28-31` | `DistributionSympathizerMemberAdmin` has wrong inlines — belongs on `Distribution` admin |
| L9 | `press/tests.py` | Empty test file — no coverage for views, services, or forms |
| L10 | `person/models.py:38` | `Person.full_name`: if `last_name`/`first_name` is `None`, produces `"None John"` |
| L11 | `person/views.py` | No brute-force/rate limiting on login |
| L12 | `press/templates/press/new-distrib.html:32` | `max=datenow` only client-side — no server-side validation for future dates |

## Common Commands

```bash
# Run development server
python manage.py runserver

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Send monthly report via management command
python manage.py send_report

# Run tests
python manage.py test
```

## Commit Message Conventions
- Do not write about tests in commit messages
- Clear, concise, focused on "why" rather than "what"
