# Хранение БД, backup и restore

Этот документ описывает хранение реальных данных Nutag в локальном и онлайн-режиме. Оперативный порядок работ находится в `IMPLEMENTATION_PLAN.md`, причины решения — в `docs/DECISIONS.md`.

## Текущая модель

- PostgreSQL является целевой БД для реальных данных и production-like проверки локально и онлайн.
- Реальная локальная работа тоже должна по возможности использовать PostgreSQL через `NUTAG_DATABASE_URL`, чтобы не было расхождения с онлайн-средой.
- SQLite остаётся dev/fallback-режимом для быстрого запуска, тестов, демо и временной локальной работы.
- Приложение сначала читает `NUTAG_DATABASE_URL`; если он не задан, используется dev/fallback SQLite.
- SQLite нельзя использовать как production-like источник истины для реальных данных.
- SQLite-файл внутри облачного окружения приложения нельзя использовать как устойчивое хранилище реальных онлайн-данных.
- Если `NUTAG_DATABASE_URL` не задан, fallback SQLite-БД хранится в пользовательском каталоге:
  - Windows: `%LOCALAPPDATA%\Nutag\nutag.sqlite3`
  - macOS: `~/Library/Application Support/Nutag/nutag.sqlite3`
  - Linux: `$XDG_DATA_HOME/Nutag/nutag.sqlite3` или `~/.local/share/Nutag/nutag.sqlite3`
- Если при первом переходе найден старый файл `nutag.sqlite3` в папке проекта, он копируется в новый пользовательский каталог. Старый файл остаётся на месте как дополнительная страховка.

## PostgreSQL для реальных данных

Для локальной работы с реальными данными и для онлайн-режима нужно задавать PostgreSQL URL:

```powershell
$env:NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
```

Эта же переменная должна быть задана в secrets/env облачного deploy.

## Dev/fallback SQLite

SQLite остаётся для быстрого запуска без сервера БД. Это удобно для разработки или временной проверки, но новые production-like сценарии нужно проверять на PostgreSQL.

Можно явно указать БД через переменную окружения:

```powershell
$env:NUTAG_DATABASE_URL = "sqlite:///C:/Users/alexa/AppData/Local/Nutag/nutag.sqlite3"
```

Для временной проверки можно использовать отдельный файл:

```powershell
$env:NUTAG_DATABASE_URL = "sqlite:///C:/Temp/nutag-test.sqlite3"
```

## Онлайн-режим

Целевой онлайн-режим для одного пользователя:

- внешний PostgreSQL у отдельного провайдера БД;
- отдельный PostgreSQL-пользователь для приложения, без использования владельца/администратора БД в `NUTAG_DATABASE_URL`;
- строка подключения хранится в secrets/env как `NUTAG_DATABASE_URL`;
- приложение не хранит реальные данные в локальном SQLite-файле облачного контейнера;
- минимальная защита доступа хранит секрет/пароль в настройках окружения, без регистрации и ролей;
- backup/restore PostgreSQL должен быть описан через возможности провайдера БД до переноса реальных данных.

Пример формы секрета без реальных значений:

```toml
NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
NUTAG_APP_PASSWORD = "replace-with-real-password-after-access-gate-is-implemented"
```

`NUTAG_APP_PASSWORD` задаёт минимальный пароль доступа к Streamlit-приложению. Если приложение запущено с PostgreSQL URL и этот секрет не задан, страницы с данными должны быть заблокированы. Для dev/fallback SQLite запуск без пароля допускается.

Перед фактическим переносом реальных данных нужно реализовать и проверить:

- отдельного PostgreSQL-пользователя приложения с доступом только к нужной БД;
- PostgreSQL runtime-зависимость;
- миграции Alembic на PostgreSQL URL;
- smoke-check запуска приложения с внешней БД;
- минимальную защиту доступа;
- сценарий переноса SQLite/dev или старой локальной БД в PostgreSQL либо ручного повторного ввода с контрольной сверкой остатков;
- backup/restore PostgreSQL у выбранного провайдера.

Проверка подключения и инициализации схемы:

```powershell
$env:NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
.\.venv\Scripts\python.exe scripts\check_database_url.py
```

Ожидаемый результат: dialect `postgresql`, наличие таблицы `alembic_version` и ненулевое количество таблиц. Запускать эту проверку нужно на пустой или тестовой PostgreSQL-БД до переноса реальных данных.

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

## Ограничения

- Автоматический backup, описанный выше, относится к SQLite-файлам.
- PostgreSQL backup должен выполняться средствами провайдера или отдельным скриптом, который ещё нужно спроектировать.
- До появления минимальной защиты доступа онлайн-deploy нельзя использовать для реальных конфиденциальных данных.
