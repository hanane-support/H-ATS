#!/bin/bash

#==============================================================
# 1. 설정 변수
#==============================================================

GITHUB_REPO_URL="https://github.com/hanane-support/H-ATS.git"
PROJECT_ROOT_DIR="/H-ATS"
APP_SUB_DIR="v_1_0_12"
APP_MODULE="my_main:app"
APP_PORT=8000
# Supervisor 프로그램 이름을 "server_log"로 지정
SUPERVISOR_PROGRAM_NAME="server_log"
DB_FILE_NAME="my_admin_config.db"
MY_IP="61.85.61.62" # 외부 접근 시 사용할 사용자님의 공인 IP

#==============================================================
# 2. 시스템 환경 설정 및 필수 도구 설치
#==============================================================

echo ">> 시스템 업데이트 및 기본 도구 설치 시작..."
apt update -y
apt upgrade -y
# 'requests' 라이브러리를 위해 필요한 Python 도구와 Caddy, Supervisor 설치
apt install -y git python3 python3-venv python3-pip supervisor curl software-properties-common wget ufw

#==============================================================
# 3. UFW 방화벽 설정
#==============================================================

echo ">> UFW 방화벽 설정 (22, 80, 443번 포트 허용) 시작..."
# 포트 443(HTTPS)을 미리 열어두어 Caddy의 자동 인증서 발급이 가능하게 합니다.
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
echo ">> UFW 방화벽 설정 완료. (sudo ufw status로 확인 가능)"

#==============================================================
# 4. 코드 다운로드 및 Python 환경 설정
#==============================================================

echo ">> 프로젝트 코드 다운로드 및 Python 환경 설정 시작..."
mkdir -p "$PROJECT_ROOT_DIR"
cd "$PROJECT_ROOT_DIR" || exit 1
git clone --depth 1 "$GITHUB_REPO_URL" .

cd "$APP_SUB_DIR" || exit 1
CURRENT_APP_DIR=$(pwd)

# --------------------------------------------------------------------------
# DB 파일 초기화 로직 및 IP 정보 수집
# --------------------------------------------------------------------------
echo ">> [초기화] 이전 설치된 DB 파일(${DB_FILE_NAME}) 확인 및 삭제 시작..."
if [ -f "$DB_FILE_NAME" ]; then
    rm "$DB_FILE_NAME"
    echo "✅ ${DB_FILE_NAME} 파일을 삭제하여 관리자 설정을 초기화했습니다."
else
    echo "DB 파일이 존재하지 않아 초기화가 필요 없습니다. (최초 설치 상태)"
fi

# VULTR 서버의 IP 주소 조회
echo ">> [IP 수집] VULTR 서버의 공인 IP 주소 조회 중..."
VULTR_IP=$(curl -s https://ifconfig.me/ip || echo "")
if [ -z "$VULTR_IP" ]; then
    VULTR_IP=$(curl -s https://api.ipify.org || echo "미설정")
fi
echo "✅ VULTR IP: $VULTR_IP"
echo "✅ MY IP (사용자): $MY_IP"
# --------------------------------------------------------------------------

echo ">> Python 가상 환경을 ${CURRENT_APP_DIR}에 설치합니다."
python3 -m venv venv
source venv/bin/activate
pip install gunicorn
# Caddy Admin API 호출을 위해 'requests' 라이브러리 추가
pip install -r my_requirements.txt requests

# DB 초기 설정: VULTR IP와 MY IP 저장
echo ">> [DB 초기화] DB에 VULTR IP와 MY IP 초기값 저장 중..."
python3 << 'PYTHON_SCRIPT'
import sqlite3
import sys

DB_FILE = "${DB_FILE_NAME}"
VULTR_IP = "${VULTR_IP}"
MY_IP = "${MY_IP}"

try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # admin 테이블 생성 (없을 경우)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_agreed INTEGER DEFAULT 0 NOT NULL
        )
    """)

    # domain 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS domain (
            admin_id TEXT PRIMARY KEY,
            domain_name TEXT,
            ssl_status TEXT DEFAULT 'HTTP' NOT NULL,
            vultr_ip TEXT,
            my_ip TEXT,
            FOREIGN KEY (admin_id) REFERENCES admin (id)
        )
    """)

    conn.commit()
    print(f"✅ DB 초기화 완료: {DB_FILE}")
    print(f"   - VULTR IP: {VULTR_IP}")
    print(f"   - MY IP: {MY_IP}")

except Exception as e:
    print(f"❌ DB 초기화 오류: {e}")
    sys.exit(1)
finally:
    if conn:
        conn.close()
PYTHON_SCRIPT

deactivate

#==============================================================
# 5. Gunicorn 및 Supervisor 설정
#==============================================================

SUPERVISOR_CONF="/etc/supervisor/conf.d/${SUPERVISOR_PROGRAM_NAME}.conf"
echo ">> Supervisor 설정 파일 (${SUPERVISOR_CONF}) 생성..."

cat <<EOF | sudo tee "$SUPERVISOR_CONF" > /dev/null
[program:${SUPERVISOR_PROGRAM_NAME}]
directory=$CURRENT_APP_DIR
command=$CURRENT_APP_DIR/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker $APP_MODULE -b 0.0.0.0:$APP_PORT
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/${SUPERVISOR_PROGRAM_NAME}/err.log
stdout_logfile=/var/log/${SUPERVISOR_PROGRAM_NAME}/out.log
EOF

sudo mkdir -p /var/log/${SUPERVISOR_PROGRAM_NAME}
sudo chown -R root:root /var/log/${SUPERVISOR_PROGRAM_NAME}

echo ">> Supervisor 설정 적용 및 앱 실행 시작..."
systemctl restart supervisor
supervisorctl reread
supervisorctl update
supervisorctl start ${SUPERVISOR_PROGRAM_NAME}

#==============================================================
# 6. Caddy 다운로드 및 초기 설정 (Admin API 활성화 및 IP 제한)
#==============================================================

echo ">> Caddy 웹 서버 설치 시작..."
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/cfg/setup/bash.deb.sh' | sudo -E bash
apt update -y
apt install caddy -y

systemctl daemon-reload

CADDY_CONF="/etc/caddy/Caddyfile"
echo ">> Caddyfile (${CADDY_CONF}) 생성 및 초기 설정 (Admin API 활성화 및 MY_IP 제한)..."
cat <<EOF | sudo tee "$CADDY_CONF" > /dev/null
# Caddy Admin API를 로컬호스트에 바인딩
{
    admin 127.0.0.1:2019
}

# 초기 접근: MY_IP로 접근하는 관리자 콘솔만 허용
:80 {
    @myip {
        remote_ip $MY_IP
    }

    handle @myip {
        reverse_proxy 127.0.0.1:$APP_PORT
    }

    # IP가 일치하지 않는 모든 요청은 접근을 거부합니다.
    handle {
        respond "Access Denied" 403
    }
}
EOF

echo ">> Caddy 서비스 시작 및 설정 적용..."
systemctl enable caddy
systemctl restart caddy

echo ">> 배포 스크립트가 완료되었습니다. 상태는 'server_log'를 확인하십시오."