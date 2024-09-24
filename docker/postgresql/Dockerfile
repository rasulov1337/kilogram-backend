# Используем официальный образ PostgreSQL
FROM postgres:latest

# Устанавливаем переменные окружения для создания базы данных и пользователя
ENV POSTGRES_DB=db
ENV POSTGRES_USER=admin
ENV POSTGRES_PASSWORD=1234

# Копируем SQL-скрипт для инициализации базы данных (если требуется)
# COPY ./init.sql /docker-entrypoint-initdb.d/

# Expose порты PostgreSQL
EXPOSE 5432

# По умолчанию PostgreSQL использует команду entrypoint,
# которая указана в базовом образе, так что дополнительные CMD не требуются

# Launching:
# docker build -t rip-db .
# docker run -d -p 5432:5432 rip-db