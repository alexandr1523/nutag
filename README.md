# nutag

Платформа для ведения бизнеса.

На текущем этапе проект развивается как Streamlit-приложение для управленческого учёта домашнего производства замороженных полуфабрикатов. Текущий трек доработки — PostgreSQL как целевая БД для реальных данных локально и онлайн; SQLite остаётся только dev/fallback-режимом.

## Документы проекта

- `IMPLEMENTATION_PLAN.md` — оперативная очередь работ, текущий backlog и следующий шаг.
- `docs/DECISIONS.md` — принятые, изменённые и отклонённые решения с причинами.
- `docs/CHANGELOG_IMPLEMENTATION.md` — подробная история реализации.
- `docs/REQUIREMENTS_AUDIT.md` — актуальность исходной функциональной постановки.
- `docs/DATABASE_STORAGE.md` — где хранится БД, как работают backup и restore.
- `docs/STREAMLIT_CLOUD_DEPLOY.md` — настройки Streamlit Cloud, secrets и smoke-check после deploy.
- `README_FUNCTIONAL.md` и файлы `01...04...` — исходная постановка; перед реализацией сверять с audit и decisions.

## Что означает блок `Testing` в сообщениях агента

Блок `Testing` — это отчёт о проверках, которые агент уже запустил перед коммитом.

Например:

```text
✅ pytest -q
✅ python3 -m compileall app.py nutag tests
✅ git status --short --branch
```

Это не обязательные команды, которые нужно немедленно выполнять после каждого ответа. Они нужны, чтобы было видно:

- какие проверки были сделаны;
- прошли они или нет;
- есть ли ограничения окружения;
- чистая ли рабочая директория после изменений.

Если хочешь самостоятельно перепроверить проект локально, обычно достаточно команд из разделов ниже.


## Типичный порядок действий в Codespace

Когда я пишу, что сделал новый PR, тебе обычно нужно:

1. Открыть GitHub и посмотреть PR.
2. Если всё устраивает — нажать **Merge pull request**.
3. Перейти в Codespace.
4. Проверить текущую ветку:

```bash
git status --short --branch
```

5. Переключиться на `main`, если ты сейчас не на ней:

```bash
git checkout main
```

6. Подтянуть свежий `main` из GitHub:

```bash
git pull origin main
```

7. Если менялся `pyproject.toml` или появились новые зависимости — обновить окружение:

```bash
python -m pip install -e '.[dev]'
```

8. Запустить тесты:

```bash
pytest -q
```

9. Если нужно посмотреть приложение:

```bash
streamlit run app.py
```

10. Проверить состояние git:

```bash
git status --short --branch
```

Если после `git pull`, установки зависимостей, тестов или запуска приложения появляется ошибка — лучше скопировать её полностью и прислать сюда.

## Что делать, если тесты падают из-за отсутствующей зависимости

Если видишь ошибку вида:

```text
ModuleNotFoundError: No module named 'sqlalchemy'
```

это означает, что зависимости проекта не установлены в текущем Codespace или виртуальном окружении.

Сначала выполни:

```bash
python -m pip install -e '.[dev]'
```

Потом повтори:

```bash
pytest -q
```

## Установка зависимостей

Рекомендуемый вариант:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Если виртуальное окружение уже создано и активировано, достаточно выполнить:

```bash
python -m pip install -e '.[dev]'
```

## Запуск тестов

```bash
pytest -q
```

Эта команда запускает автоматические тесты расчётного ядра.

## Проверка синтаксиса Python-файлов

```bash
python3 -m compileall app.py nutag tests
```

Эта команда проверяет, что Python-файлы компилируются без синтаксических ошибок.

## Запуск приложения локально

Для реальных данных локально предпочтительно использовать PostgreSQL через `NUTAG_DATABASE_URL`, чтобы локальная среда не расходилась с онлайн-deploy.

```powershell
$env:NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
```

### Dev/fallback SQLite

Если `NUTAG_DATABASE_URL` не задан, приложение использует fallback SQLite вне папки проекта:

- Windows: `%LOCALAPPDATA%\Nutag\nutag.sqlite3`
- macOS: `~/Library/Application Support/Nutag/nutag.sqlite3`
- Linux: `$XDG_DATA_HOME/Nutag/nutag.sqlite3` или `~/.local/share/Nutag/nutag.sqlite3`

Если нужен другой SQLite-файл для временной проверки, задай переменную окружения:

```powershell
$env:NUTAG_DATABASE_URL = "sqlite:///C:/Users/alexa/AppData/Local/Nutag/nutag.sqlite3"
```

Подробности по backup/restore: `docs/DATABASE_STORAGE.md`.

```bash
streamlit run app.py
```

После запуска Streamlit покажет локальный адрес в терминале.

## Онлайн-режим

Онлайн-режим является текущим направлением доработки, но для реальных данных он должен использовать внешний PostgreSQL через `NUTAG_DATABASE_URL`/secrets. SQLite не считается production-like источником истины и не подходит как устойчивое хранилище внутри облачного окружения приложения.

Полная инструкция deploy: `docs/STREAMLIT_CLOUD_DEPLOY.md`.

Для Streamlit Cloud нужно задать оба root-level секрета:

```toml
NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
NUTAG_APP_PASSWORD = "replace-with-real-password"
```

`NUTAG_DATABASE_URL` указывает на внешнюю PostgreSQL-БД. `NUTAG_APP_PASSWORD` задаёт минимальный пароль доступа к приложению. Если пароль задан, а PostgreSQL URL отсутствует, приложение блокируется вместо скрытого перехода на SQLite fallback.

После изменения secrets в Streamlit Cloud нужно перезапустить приложение через **Reboot app** или дождаться повторного deploy.

Для минимальной защиты доступа локально можно задать пароль приложения:

```powershell
$env:NUTAG_APP_PASSWORD = "replace-with-real-password"
```

Проверка подключения и инициализации схемы на тестовой PostgreSQL-БД:

```powershell
$env:NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
.\.venv\Scripts\python.exe scripts\check_database_url.py
```

Актуальный порядок работ и ограничения описаны в `IMPLEMENTATION_PLAN.md`, детали хранения БД — в `docs/DATABASE_STORAGE.md`.

## Проверка состояния git

```bash
git status --short --branch
```

Эта команда показывает текущую ветку и наличие незакоммиченных изменений.
