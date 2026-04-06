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
