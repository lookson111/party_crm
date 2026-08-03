#!/usr/bin/env bash
set -euo pipefail

# Скрипт запуска тестов Django.
# По умолчанию использует config.test_settings (SQLite + locmem-email) —
# работает без настроенного PostgreSQL.
# Флаг --postgres переключает на config.settings (PostgreSQL из local_settings.py).
# Флаг --coverage запускает измерение покрытия (всегда на config.test_settings).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SETTINGS="config.test_settings"
USE_COVERAGE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sqlite)
            SETTINGS="config.test_settings"
            shift
            ;;
        --postgres|--pg)
            SETTINGS="config.settings"
            shift
            ;;
        --coverage)
            USE_COVERAGE=1
            shift
            ;;
        --help|-h)
            cat <<EOF
Использование: $0 [OPTIONS]

Опции:
  --postgres, --pg  Запустить тесты на PostgreSQL (config.settings + local_settings.py)
  --sqlite          Запустить тесты на SQLite (по умолчанию)
  --coverage        Измерить покрытие тестами (всегда на SQLite)
  --help, -h        Показать эту справку

Примеры:
  $0                  # тесты на SQLite
  $0 --postgres       # тесты на PostgreSQL из local_settings.py
  $0 --coverage       # тесты на SQLite + отчёт о покрытии
EOF
            exit 0
            ;;
        *)
            echo "Неизвестный аргумент: $1" >&2
            echo "Запустите $0 --help для справки" >&2
            exit 1
            ;;
    esac
done

if [[ -z "${VIRTUAL_ENV:-}" && -f "venv/bin/activate" ]]; then
    # shellcheck source=/dev/null
    source venv/bin/activate
fi

if [[ "$USE_COVERAGE" -eq 1 ]]; then
    coverage run manage.py test --settings=config.test_settings
    coverage report -m
else
    python manage.py test --settings="$SETTINGS"
fi
