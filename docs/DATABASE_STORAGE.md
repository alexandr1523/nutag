# Хранение БД, backup и restore

Этот документ описывает хранение реальных данных Nutag в локальном и онлайн-режиме. Оперативный порядок работ находится в `IMPLEMENTATION_PLAN.md`, причины решения — в `docs/DECISIONS.md`.

Практическая инструкция Streamlit Cloud deploy находится в `docs/STREAMLIT_CLOUD_DEPLOY.md`. Чистый старт первых реальных данных описан в `docs/POSTGRESQL_REAL_DATA_START.md`.

## Текущая модель

- PostgreSQL является целевой БД для реальных данных и production-like проверки локально и онлайн.
- Реальная локальная работа тоже должна по возможности использовать PostgreSQL через `NUTAG_DATABASE_URL`, чтобы не было расхождения с онлайн-средой.
- SQLite остаётся dev/fallback-режимом для быстрого запуска, тестов, демо и временной локальной работы.
- Приложение сначала читает `NUTAG_DATABASE_URL`; если он не задан, используется dev/fallback SQLite.
- В Streamlit UI root-level secrets `NUTAG_DATABASE_URL` и `NUTAG_APP_PASSWORD` поднимаются в переменные окружения перед инициализацией БД, чтобы общий DB-helper использовал те же настройки, что и страница входа.
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
- если `NUTAG_APP_PASSWORD` задан, но `NUTAG_DATABASE_URL` не найден, приложение должно остановиться с ошибкой настройки, а не открываться на SQLite fallback;
- backup/restore PostgreSQL должен быть описан через возможности провайдера БД до переноса реальных данных.

Пример формы секрета без реальных значений:

```toml
NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
NUTAG_APP_PASSWORD = "replace-with-real-password-after-access-gate-is-implemented"
```

`NUTAG_APP_PASSWORD` задаёт минимальный пароль доступа к Streamlit-приложению. Если приложение запущено с PostgreSQL URL и этот секрет не задан, страницы с данными должны быть заблокированы. Для dev/fallback SQLite запуск без пароля допускается.

Если `NUTAG_APP_PASSWORD` задан, а `NUTAG_DATABASE_URL` отсутствует, это считается ошибкой онлайн-настройки: приложение блокируется, чтобы не записывать реальные данные в SQLite-файл облачного окружения.

Перед фактическим переносом реальных данных нужно реализовать и проверить:

- отдельного PostgreSQL-пользователя приложения с доступом только к нужной БД;
- PostgreSQL runtime-зависимость;
- миграции Alembic на PostgreSQL URL;
- smoke-check запуска приложения с внешней БД;
- минимальную защиту доступа;
- выбранный сценарий старта данных;
- backup/restore PostgreSQL у выбранного провайдера.

## Чистый старт в PostgreSQL

Для первых реальных онлайн-данных выбран чистый старт в PostgreSQL без переноса SQLite: реальных данных пока нет, поэтому миграционный инструмент SQLite -> PostgreSQL сейчас не нужен.

Это не отменяет Alembic-миграции схемы: будущие изменения структуры БД выполняются через `migrations/versions`. Если позже появятся реальные данные и потребуется изменить логику их хранения, отдельный data migration нужно проектировать под конкретное преобразование.

Перед вводом первых реальных данных нужно:

1. Создать или подтвердить чистую PostgreSQL-БД.
2. Создать отдельного PostgreSQL-пользователя приложения и заменить owner/admin в `NUTAG_DATABASE_URL`.
3. Ротировать временные или раскрытые пароли.
4. Обновить `NUTAG_DATABASE_URL` и `NUTAG_APP_PASSWORD` в Streamlit secrets.
5. Проверить вход в приложение после `Reboot app`.
6. Проверить backup/restore у провайдера PostgreSQL.
7. Ввести контрольный минимальный набор данных: единицы измерения, ингредиент, упаковку, продукт, первую закупку.
8. Проверить, что остатки и справочники сохраняются после перезапуска приложения.

Backup/restore для текущего Neon Free режима закреплён в `docs/POSTGRESQL_REAL_DATA_START.md`: используется 6-часовое History window, instant restore/time travel/branch from past state, а долгосрочные scheduled backups на текущем тарифе не считаются настроенными.

Если позже появится локальная SQLite-БД с реальными данными, решение о миграционном инструменте нужно принять отдельно и зафиксировать в `IMPLEMENTATION_PLAN.md` и `docs/DECISIONS.md`.

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
- PostgreSQL backup/restore выполняется средствами Neon; для Free-режима зафиксирован 6-часовой History window, поэтому рискованные действия нужно планировать и проверять в пределах этого окна.
