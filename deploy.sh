#!/bin/bash

# 1. Проверка прав sudo
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: скрипт должен быть запущен с правами sudo"
    exit 1
fi

# 2. Проверка папки application
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
if [ ! -d "$SCRIPT_DIR/application" ]; then
    echo "Ошибка: папка application не найдена в $SCRIPT_DIR"
    exit 1
fi

# 3. Проверка файла install.conf
if [ ! -f "$SCRIPT_DIR/application/install.conf" ]; then
    echo "Ошибка: файл install.conf не найден в $SCRIPT_DIR/application"
    exit 1
fi

# 4. Проверка файла requirements.txt
if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Ошибка: файл requirements.txt не найден в $SCRIPT_DIR"
    exit 1
fi

# 5. Чтение переменных из install.conf
source "$SCRIPT_DIR/application/install.conf"

# Проверка обязательных переменных
if [ -z "$SERVICE_NAME" ] || [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
    echo "Ошибка: в install.conf должны быть определены SERVICE_NAME, USER и PASSWORD"
    exit 1
fi

# 6. Проверка и остановка сервиса
if systemctl list-unit-files | grep -q "^$SERVICE_NAME.service"; then
    echo "Сервис $SERVICE_NAME существует, проверяем состояние..."
    if systemctl is-active --quiet "$SERVICE_NAME.service"; then
        echo "Останавливаем сервис $SERVICE_NAME..."
        systemctl stop "$SERVICE_NAME.service"
    fi
fi

# 7. Установка зависимостей
echo "Устанавливаем зависимости из requirements.txt..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    echo "Ошибка при установке зависимостей"
    exit 1
fi

# 8. Проверка и создание пользователя
if ! id "$USER" &>/dev/null; then
    echo "Создаем пользователя $USER..."
    useradd -m -s /bin/bash "$USER"
    echo "$USER:$PASSWORD" | chpasswd
else
    echo "Пользователь $USER уже существует"
fi

# 9. Проверка и выдача прав (пример - добавление в группу sudo)
if ! groups "$USER" | grep -q '\bsudo\b'; then
    echo "Добавляем пользователя $USER в группу sudo..."
    usermod -aG sudo "$USER"
fi

# 10. Проверка и создание директории /opt/EOS_server
if [ ! -d "/opt/EOS_server" ]; then
    echo "Создаем директорию /opt/EOS_server..."
    mkdir -p "/opt/EOS_server"
fi

# 11. Назначение прав пользователю
echo "Назначаем права на /opt/EOS_server для пользователя $USER..."
chown -R "$USER:$USER" "/opt/EOS_server"
chmod -R 755 "/opt/EOS_server"

# 12-14. Работа с директорией app
APP_DIR="/opt/EOS_server/app"
echo "Проверяем директорию $APP_DIR..."

if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
fi

# Проверка прав
if [ $(stat -c "%U" "$APP_DIR") != "$USER" ]; then
    chown -R "$USER:$USER" "$APP_DIR"
fi

# Очистка и копирование файлов
echo "Очищаем и копируем файлы в $APP_DIR..."
rm -rf "$APP_DIR"/*
cp -r "$SCRIPT_DIR/application/"* "$APP_DIR/"

# 15. Создание systemd сервиса
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Создаем сервис $SERVICE_NAME..."
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=EOS Server Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
fi

# 16. Запуск сервиса
echo "Запускаем сервис $SERVICE_NAME..."
systemctl enable "$SERVICE_NAME.service"
systemctl start "$SERVICE_NAME.service"

systemctl status "$SERVICE_NAME.service"

echo "Установка завершена успешно!"