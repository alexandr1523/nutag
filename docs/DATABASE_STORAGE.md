# Хранение БД, backup и restore

Этот документ описывает хранение реальных локальных данных Nutag. Оперативный порядок работ находится в `IMPLEMENTATION_PLAN.md`, причины решения — в `docs/DECISIONS.md`.

## Текущая модель

- Основной режим MVP для реальных данных одного пользователя — локальный SQLite.
- Приложение сначала читает `NUTAG_DATABASE_URL`.
- Если `NUTAG_DATABASE_URL` не задан, используется SQLite в пользовательском каталоге:
  - Windows: `%LOCALAPPDATA%\Nutag\nutag.sqlite3`
  - macOS: `~/Library/Application Support/Nutag/nutag.sqlite3`
  - Linux: `$XDG_DATA_HOME/Nutag/nutag.sqlite3` или `~/.local/share/Nutag/nutag.sqlite3`
- Если при первом переходе найден старый файл `nutag.sqlite3` в папке проекта, он копируется в новый пользовательский каталог. Старый файл остаётся на месте как дополнительная страховка.

## Настройка своего пути

Можно явно указать БД через переменную окружения:

```powershell
$env:NUTAG_DATABASE_URL = "sqlite:///C:/Users/alexa/AppData/Local/Nutag/nutag.sqlite3"
```

Для временной проверки можно использовать отдельный файл:

```powershell
$env:NUTAG_DATABASE_URL = "sqlite:///C:/Temp/nutag-test.sqlite3"
```

## Backup перед изменением схемы

Перед изменениями схемы SQLite приложение создаёт копию в папке `backups` рядом с файлом БД.

Примеры имён:

```text
nutag.before-migration.20260705-193000.sqlite3
nutag.before-initialization.20260705-193000.sqlite3
nutag.before-compatibility.20260705-193000.sqlite3
```

Backup создаётся перед:

- Alembic-миграциями, если версия БД отличается от текущей версии миграций;
- первичной инициализацией старой SQLite-БД без `alembic_version`;
- compatibility-исправлениями старых локальных БД.

## Restore

1. Закрыть Streamlit-приложение.
2. Найти текущий файл БД в пользовательском каталоге или в пути из `NUTAG_DATABASE_URL`.
3. Переименовать повреждённый/неудачно обновлённый файл, например:

```powershell
Rename-Item "$env:LOCALAPPDATA\Nutag\nutag.sqlite3" "nutag.failed.sqlite3"
```

4. Скопировать нужный backup на место рабочей БД:

```powershell
Copy-Item "$env:LOCALAPPDATA\Nutag\backups\nutag.before-migration.20260705-193000.sqlite3" "$env:LOCALAPPDATA\Nutag\nutag.sqlite3"
```

5. Запустить приложение снова.

## Онлайн-режим

SQLite остаётся целевым локальным режимом MVP. Для будущего онлайн-режима нужно использовать внешний PostgreSQL через `NUTAG_DATABASE_URL`; это отдельный этап, не текущий фокус.
