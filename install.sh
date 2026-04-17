#!/usr/bin/env bash
# Идемпотентный установщик — безопасно запускать повторно.
# Каждый шаг проверяет, выполнен ли он уже, и пропускает если да.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$APP_DIR/.venv"
PY=python3
STAMP_DIR="$APP_DIR/.install_stamps"
mkdir -p "$STAMP_DIR"

stamp_done()  { touch "$STAMP_DIR/$1.done"; }
stamp_check() { [ -f "$STAMP_DIR/$1.done" ]; }

echo "=== Conference Backend Installer (идемпотентный) ==="
echo "    APP_DIR: $APP_DIR"
echo ""

# ---------------------------------------------------------------------------
# 1. Системные пакеты
# ---------------------------------------------------------------------------
if stamp_check "01_apt"; then
    echo "[SKIP] 1. Системные пакеты уже установлены"
else
    echo "=== 1. Системные пакеты ==="
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        ffmpeg postgresql postgresql-contrib \
        redis-server curl wget git \
        libpq-dev build-essential \
        libmagic1 libmagic-dev
    stamp_done "01_apt"
fi

# ---------------------------------------------------------------------------
# 2. MinIO server + client
# ---------------------------------------------------------------------------
if stamp_check "02_minio"; then
    echo "[SKIP] 2. MinIO уже установлен"
else
    echo "=== 2. MinIO ==="
    if ! command -v minio &>/dev/null; then
        wget -q https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
        chmod +x /usr/local/bin/minio
    fi
    if ! command -v mc &>/dev/null; then
        wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
        chmod +x /usr/local/bin/mc
    fi
    stamp_done "02_minio"
fi

# ---------------------------------------------------------------------------
# 3. Ollama
# ---------------------------------------------------------------------------
if stamp_check "03_ollama"; then
    echo "[SKIP] 3. Ollama уже установлен"
else
    echo "=== 3. Ollama ==="
    if ! command -v ollama &>/dev/null; then
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    stamp_done "03_ollama"
fi

# ---------------------------------------------------------------------------
# 4. Python venv + зависимости
# ---------------------------------------------------------------------------
if stamp_check "04_venv"; then
    echo "[SKIP] 4. Python venv уже создан и зависимости установлены"
else
    echo "=== 4. Python venv + pip install ==="
    cd "$APP_DIR"
    $PY -m venv .venv
    source "$VENV/bin/activate"
    pip install --upgrade pip
    pip install -r requirements.txt
    stamp_done "04_venv"
fi

# ---------------------------------------------------------------------------
# 5. PostgreSQL: пользователь и база
# ---------------------------------------------------------------------------
if stamp_check "05_postgres"; then
    echo "[SKIP] 5. PostgreSQL БД уже настроена"
else
    echo "=== 5. PostgreSQL setup ==="
    sudo systemctl start postgresql
    sudo -u postgres psql -c "CREATE USER confuser WITH PASSWORD 'confpass';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE conferences_db OWNER confuser;" 2>/dev/null || true
    stamp_done "05_postgres"
fi

# ---------------------------------------------------------------------------
# 6. Redis
# ---------------------------------------------------------------------------
if stamp_check "06_redis"; then
    echo "[SKIP] 6. Redis уже настроен"
else
    echo "=== 6. Redis ==="
    sudo systemctl enable --now redis-server
    stamp_done "06_redis"
fi

# ---------------------------------------------------------------------------
# 7. MinIO systemd-сервис
# ---------------------------------------------------------------------------
if stamp_check "07_minio_service"; then
    echo "[SKIP] 7. MinIO systemd-сервис уже установлен"
else
    echo "=== 7. MinIO service ==="
    sudo mkdir -p /var/lib/minio/data
    sudo useradd -r minio-user -s /sbin/nologin 2>/dev/null || true
    sudo chown minio-user /var/lib/minio/data

    cat > /tmp/minio.service <<'EOF'
[Unit]
Description=MinIO
After=network.target
[Service]
User=minio-user
ExecStart=/usr/local/bin/minio server /var/lib/minio/data --console-address ":9001"
Environment=MINIO_ROOT_USER=minioadmin
Environment=MINIO_ROOT_PASSWORD=minioadmin
Restart=always
[Install]
WantedBy=multi-user.target
EOF
    sudo mv /tmp/minio.service /etc/systemd/system/minio.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now minio
    stamp_done "07_minio_service"
fi

# ---------------------------------------------------------------------------
# 8. .env файл
# ---------------------------------------------------------------------------
if [ -f "$APP_DIR/.env" ]; then
    echo "[SKIP] 8. .env уже существует"
else
    echo "=== 8. .env ==="
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    elif [ -f "$APP_DIR/env.example" ]; then
        cp "$APP_DIR/env.example" "$APP_DIR/.env"
    fi
    sed -i 's|postgresql+asyncpg://user:password@|postgresql+asyncpg://confuser:confpass@|' "$APP_DIR/.env"
    echo "    .env создан из шаблона — проверьте настройки!"
fi

# ---------------------------------------------------------------------------
# 9. Argostranslate: языковые пакеты ru<->en
# ---------------------------------------------------------------------------
if stamp_check "09_argos"; then
    echo "[SKIP] 9. Языковые пакеты Argostranslate уже установлены"
else
    echo "=== 9. Argostranslate language packs (ru<->en) ==="
    source "$VENV/bin/activate"
    python3 - <<'PYEOF'
from argostranslate import package
package.update_package_index()
pkgs = package.get_available_packages()
installed = 0
for p in pkgs:
    if (p.from_code == 'ru' and p.to_code == 'en') or \
       (p.from_code == 'en' and p.to_code == 'ru'):
        print(f"  Installing {p.from_code}->{p.to_code} ...")
        package.install_from_path(p.download())
        installed += 1
print(f"  Установлено пакетов: {installed}")
PYEOF
    stamp_done "09_argos"
fi

# ---------------------------------------------------------------------------
# 10. Ollama: загрузка модели llama3
# ---------------------------------------------------------------------------
if stamp_check "10_ollama_model"; then
    echo "[SKIP] 10. Модель llama3 уже загружена"
else
    echo "=== 10. Pull Ollama model (llama3) ==="
    if sudo systemctl is-active --quiet ollama 2>/dev/null; then
        : # уже работает
    else
        ollama serve &>/dev/null &
        sleep 5
    fi
    ollama pull llama3
    stamp_done "10_ollama_model"
fi

# ---------------------------------------------------------------------------
# 11. Systemd-сервисы приложения
# ---------------------------------------------------------------------------
if stamp_check "11_app_services"; then
    echo "[SKIP] 11. Systemd-сервисы приложения уже установлены"
    echo "      (для принудительного обновления удалите: $STAMP_DIR/11_app_services.done)"
else
    echo "=== 11. Systemd services (API + Worker) ==="
    cat > /tmp/conference-api.service <<EOF
[Unit]
Description=Conference API
After=network.target postgresql.service redis.service minio.service

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

    cat > /tmp/conference-worker.service <<EOF
[Unit]
Description=Conference Celery Worker
After=network.target redis.service postgresql.service

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$VENV/bin/celery -A app.workers.tasks.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=5
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

    sudo mv /tmp/conference-api.service /etc/systemd/system/
    sudo mv /tmp/conference-worker.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable conference-api conference-worker
    stamp_done "11_app_services"
fi

# ---------------------------------------------------------------------------
# Запуск / перезапуск сервисов приложения (всегда)
# ---------------------------------------------------------------------------
echo ""
echo "=== Запуск сервисов ==="
sudo systemctl restart conference-api
sudo systemctl restart conference-worker
sudo systemctl status conference-api  --no-pager -l | head -6
sudo systemctl status conference-worker --no-pager -l | head -6

echo ""
echo "✅ Готово!"
echo "   API:    http://localhost:8000"
echo "   Docs:   http://localhost:8000/docs"
echo "   MinIO:  http://localhost:9001"
echo ""
echo "   Повторный запуск install.sh пропустит уже выполненные шаги."
echo "   Для сброса шага удалите файл из: $STAMP_DIR/"
