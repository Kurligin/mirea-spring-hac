# МАКС-2 · Запись абитуриентов на мероприятия

Чат-бот в мессенджере **МАКС** для записи абитуриентов РТУ МИРЭА на мероприятия
приёмной кампании + веб-админка для организаторов и экран контролёра с QR-чек-ином на входе.

**Хакатон «Весенний код» 2026** — трек МАКС, кейс №2.

## Возможности

- **Бот в МАКС**: каталог мероприятий, запись по шагам (гибкая форма), подтверждение,
  статус, отмена, лист ожидания, напоминания, QR-билет.
- **Веб-админка**: конструктор мероприятий и полей формы, управление записями,
  рассылки, аналитика (воронка/явка), команда (админы и контролёры).
- **QR-чек-ин**: отметка участника на входе по QR с ротацией кода (защита от передачи).

Полный список — в [ФУНКЦИОНАЛ.md](ФУНКЦИОНАЛ.md).

## Стек

FastAPI + SQLAlchemy + Alembic + APScheduler · React + Vite + TS + Mantine (админка)
· PostgreSQL 16 · Docker Compose.

---

## 🚀 Быстрый старт (Docker)

Поднимается «из коробки»: скопировал примеры окружения → запустил. Менять ничего не нужно —
в примерах уже лежат валидные dev-значения.

```bash
git clone <repo-url> mirea-spring-hac
cd mirea-spring-hac

cp .env.example .env                                 # пароль БД для compose
cp backend/.env.docker.example backend/.env.docker   # окружение бэкенда (dev-заглушки)

# для краткости команд compose
export COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml

docker compose up -d --build      # миграции накатятся сами (сервис api-migrate)
```

Залить **моковые данные** (для демо):

```bash
# витринные мероприятия — опубликованы, с будущими датами, видны в каталоге бота
docker compose exec api python -m scripts.seed_demo_events
# пользователи + записи + воронка (наполняет аналитику дашборда)
docker compose exec api python -m scripts.seed_demo
```

Оба сидера идемпотентны — повторный запуск не плодит дубли.

Создать **демо-админа** (логин в админку):

```bash
docker compose exec api maxbot create-admin admin@mirea.ru admin12345 --role super
```

Открыть:

| Что | URL | Доступ |
|-----|-----|--------|
| Админка | http://localhost/admin/ | `admin@mirea.ru` / `admin12345` |
| API | http://localhost/api/... | — |
| Health | http://localhost/health | — |

Логи: `docker compose logs -f api`. Остановить: `docker compose down`
(данные останутся; `down -v` сотрёт БД).

---

## Для проверяющих

1. Выполни блок «Быстрый старт» выше (5 команд) — стек, моки и админ создаются сразу.
2. Зайди в админку `http://localhost/admin/` с демо-кредами `admin@mirea.ru` / `admin12345`.
3. Внутри: список мероприятий с моковыми записями, аналитика, конструктор форм,
   управление командой. Сидер кладёт ~20 пользователей, ~14 мероприятий в разных
   статусах/форматах и ~90 регистраций (часть с отметкой на входе).

> **Бот в МАКС** требует реального `MAX_BOT_TOKEN` из кабинета разработчика. Без него
> админка, API и моковые данные полностью работают; в логах будут ошибки long-poll —
> это ожидаемо (боту нечем авторизоваться).

---

## Запуск без Docker (бэкенд)

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

cp .env.example .env     # dev-значения; DATABASE_URL смотрит на localhost:5432

# Postgres (если нет своего):
docker run -d --name pg -e POSTGRES_PASSWORD=localdev -e POSTGRES_USER=app \
  -e POSTGRES_DB=mirea_max -p 5432:5432 postgres:16-alpine

.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_demo            # моки (опционально)
.venv/bin/maxbot create-admin admin@mirea.ru admin12345 --role super
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000
```

Фронтенд-админка отдельно:

```bash
cd admin && npm install && npm run dev           # http://localhost:5173 (proxy на :8000)
```

---

## Структура

- `backend/` — FastAPI + SQLAlchemy + Alembic, бот (`app/bot/`), API (`app/api/`), CLI (`app/cli.py`)
- `backend/scripts/` — сидеры моков (`seed_demo.py`, `seed_catalog.py`)
- `admin/` — React + Vite + TS + Mantine (веб-админка)
- `nginx/` — reverse-proxy (dev: `nginx.conf`; prod: шаблоны)
- `docs/` — дизайн-спека и планы
- `DEPLOY.md` — прод-развёртывание (HTTPS, webhook, два варианта)

## Тесты

```bash
cd backend && .venv/bin/pytest
```

## Безопасность и секреты

- Все значения в `*.example` — **dev-заглушки**, не для прода. Реальные `.env`,
  `backend/.env`, `backend/.env.docker` — в `.gitignore`, в репозиторий не попадают.
- Перед продом сгенерируй секреты заново и не публикуй боевые токены/креды.
# mirea-spring-hac
