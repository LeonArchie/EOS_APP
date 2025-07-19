#!/bin/bash

# Функция для очистки CRLF
clean_line() {
    echo "$1" | tr -d '\r'
}

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

# 4. Проверка и создание requirements.txt
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Создаём стандартный requirements.txt..."
    cat > "$REQUIREMENTS_FILE" <<EOF
Flask==3.0.0
gunicorn==21.2.0
EOF
fi

# 5. Чтение переменных из install.conf
while IFS='=' read -r key value; do
    key=$(clean_line "$key")
    value=$(clean_line "$value")
    declare "$key=$value"
done < "$SCRIPT_DIR/application/install.conf"

# Проверка обязательных переменных
if [ -z "$SERVICE_NAME" ] || [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
    echo "Ошибка: в install.conf должны быть определены SERVICE_NAME, USER и PASSWORD"
    exit 1
fi

# Очистка переменных от возможных CR
SERVICE_NAME=$(clean_line "$SERVICE_NAME")
USER=$(clean_line "$USER")
PASSWORD=$(clean_line "$PASSWORD")

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
pip3 install -r "$REQUIREMENTS_FILE"
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

# 9. Проверка и выдача прав
if ! groups "$USER" | grep -q '\bsudo\b'; then
    echo "Добавляем пользователя $USER в группу sudo..."
    usermod -aG sudo "$USER"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
    chmod 440 /etc/sudoers.d/$USER
fi

# 10. Создание основной директории
if [ ! -d "/opt/EOS_server" ]; then
    echo "Создаем директорию /opt/EOS_server..."
    mkdir -p "/opt/EOS_server"
fi

# 11. Создание и очистка директории логов
LOG_DIR="/opt/EOS_server/log"
echo "Создаем и очищаем директорию логов $LOG_DIR..."
mkdir -p "$LOG_DIR"
rm -rf "$LOG_DIR"/*

# 12. Назначение прав
echo "Назначаем права на /opt/EOS_server для пользователя $USER..."
chown -R "$USER:$USER" "/opt/EOS_server"
chmod -R 755 "/opt/EOS_server"

# 13. Работа с директорией приложения
APP_DIR="/opt/EOS_server/app"
echo "Очищаем и настраиваем директорию приложения $APP_DIR..."
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR"/*

# 14. Копирование файлов приложения
echo "Копируем файлы приложения в $APP_DIR..."
cp -r "$SCRIPT_DIR/application/"* "$APP_DIR/"

# 15. Настройка systemd сервиса
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
echo "Создаем сервис $SERVICE_NAME..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=EOS Server Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $APP_DIR/app.py
Restart=always
StandardOutput=append:$LOG_DIR/app.log
StandardError=append:$LOG_DIR/app.log

[Install]
WantedBy=multi-user.target
EOF

# 16. Настройка ротации логов
LOGROTATE_FILE="/etc/logrotate.d/$SERVICE_NAME"
echo "Настраиваем ротацию логов..."
cat > "$LOGROTATE_FILE" <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 640 $USER $USER
    sharedscripts
    postrotate
        systemctl restart $SERVICE_NAME >/dev/null 2>&1 || true
    endscript
}
EOF

# 17. Перезагрузка и запуск сервиса
echo "Запускаем сервис $SERVICE_NAME..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"
systemctl start "$SERVICE_NAME.service"

# Проверка статуса
echo "Проверяем статус сервиса..."
systemctl status "$SERVICE_NAME.service" --no-pager

echo "Установка завершена успешно!"