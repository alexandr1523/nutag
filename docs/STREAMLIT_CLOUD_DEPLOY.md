# Streamlit Cloud deploy

Этот документ описывает текущий deploy Nutag в Streamlit Cloud для онлайн-режима одного пользователя. Общая модель хранения БД описана в `docs/DATABASE_STORAGE.md`, порядок работ — в `IMPLEMENTATION_PLAN.md`.

## Настройки приложения

В Streamlit Cloud при создании или редактировании приложения использовать:

- Repository: `alexandr1523/nutag`
- Branch: `nutag-mvp`
- Main file path: `app.py`
- Python version: `3.11` или новее, совместимо с `pyproject.toml` (`requires-python = ">=3.11"`).

Если приложение показывает старый интерфейс после push, проверить в логах, что оно стартует именно из ветки `nutag-mvp`.

Ожидаемая строка в логах:

```text
Starting up repository: 'nutag', branch: 'nutag-mvp', main module: 'app.py'
```

## Secrets

В `Settings -> Secrets` нужно задать root-level TOML, без секций:

```toml
NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
NUTAG_APP_PASSWORD = "replace-with-real-password"
```

Если провайдер PostgreSQL требует дополнительные параметры, добавлять их через `&`, например:

```toml
NUTAG_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require&channel_binding=require"
```

Правила:

- `NUTAG_DATABASE_URL` должен указывать на внешний PostgreSQL, а не на SQLite.
- `NUTAG_APP_PASSWORD` задаёт пароль входа в приложение.
- Если задан `NUTAG_APP_PASSWORD`, но отсутствует `NUTAG_DATABASE_URL`, приложение должно остановиться с ошибкой настройки.
- Если задан PostgreSQL URL, но отсутствует `NUTAG_APP_PASSWORD`, приложение должно остановиться с ошибкой настройки.
- После изменения secrets выполнить `Reboot app`.

## Smoke-check после deploy

После push в `nutag-mvp` и reboot проверить:

1. В новой/incognito-сессии приложение показывает экран входа.
2. Неверный пароль не открывает приложение.
3. Правильный пароль открывает главную страницу.
4. Разделы `Справочники`, `Закупки и остатки`, `Заказы` открываются без traceback.
5. Кнопка `Выйти из Nutag` возвращает к экрану входа.
6. Кнопки `Выйти из программы` быть не должно.
7. После первого cold start повторные переходы между страницами не должны каждый раз ощущаться как полный холодный старт.

## Если пароль не запрашивается

Проверить по порядку:

1. В Streamlit Cloud branch должен быть `nutag-mvp`.
2. В логах должен быть старт из `nutag-mvp`, `app.py`.
3. В secrets должен быть root-level `NUTAG_APP_PASSWORD`.
4. После изменения secrets должен быть выполнен `Reboot app`.
5. Открыть приложение в новой/incognito-сессии, чтобы не использовать старую authenticated-сессию браузера.

## Если данные пишутся не туда

Признаки проблемы: приложение открывается, но PostgreSQL остаётся пустым или данные пропадают после перезапуска окружения.

Проверить:

1. В secrets задан `NUTAG_DATABASE_URL`.
2. URL начинается с `postgresql+psycopg://`.
3. URL содержит корректный `@` между паролем и host.
4. Параметры URL разделены через `&`, например `?sslmode=require&channel_binding=require`.
5. В логах deploy нет ошибок установки зависимостей или подключения к БД.

## После изменения кода

Локальная ветка разработки называется `codex`, но deploy-ветка на GitHub — `nutag-mvp`.

Для отправки текущего локального состояния в deploy-ветку:

```powershell
git push origin HEAD:nutag-mvp
```

Если локальная ветка уже отслеживает `origin/nutag-mvp`, Git всё равно может отказаться от простого `git push`, потому что локальная ветка называется иначе. В таком случае использовать явный push выше.
