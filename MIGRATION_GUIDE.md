# 🔄 Database Migration Guide

## Проблема

Если вы обновили код бота, но база данных была создана раньше, необходимо применить миграции для обновления схемы.

**Ошибка**: `column "bio" does not exist`

Это означает, что база данных создана со старой схемой без полей профиля.

## Решение 1: Применить миграцию (рекомендуется)

Сохраняет все существующие данные.

```bash
# Применить миграцию
docker-compose exec -T db psql -U postgres -d secret_santa < sql/migrations/001_add_user_profile_fields.sql

# Или использовать готовый скрипт
./apply_migration.sh
```

После применения миграции перезапустите бот:
```bash
docker-compose restart bot
```

## Решение 2: Пересоздать базу данных (простейший способ)

⚠️ **ВНИМАНИЕ**: Все данные будут удалены!

```bash
# Остановить контейнеры
docker-compose down

# Удалить volume с данными базы
docker volume rm tainy_santa_lol_postgres_data

# Запустить заново (база создастся с новой схемой)
docker-compose up -d
```

## Решение 3: Ручное применение через psql

```bash
# Войти в контейнер базы данных
docker-compose exec db psql -U postgres -d secret_santa

# Выполнить SQL команды вручную
ALTER TABLE users
ADD COLUMN IF NOT EXISTS bio TEXT,
ADD COLUMN IF NOT EXISTS photo_file_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS wishlist TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

UPDATE users SET updated_at = created_at WHERE updated_at IS NULL;

# Выйти
\q
```

Затем перезапустите бот:
```bash
docker-compose restart bot
```

## Проверка

Проверьте что миграция применилась успешно:

```bash
docker-compose exec db psql -U postgres -d secret_santa -c "\d users"
```

Вы должны увидеть колонки: `bio`, `photo_file_id`, `wishlist`, `updated_at`.

## Будущие миграции

Все миграции находятся в папке `sql/migrations/`. Применяйте их последовательно при обновлении кода.
