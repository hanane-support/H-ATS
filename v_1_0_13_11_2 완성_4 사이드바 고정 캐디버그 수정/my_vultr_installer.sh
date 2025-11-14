#!/bin/bash

#==============================================================
# 1. 설정 변수
#==============================================================

GITHUB_REPO_URL="https://github.com/hanane-support/H-ATS.git"
PROJECT_ROOT_DIR="/H-ATS"
APP_SUB_DIR="v_1_0_13"
APP_MODULE="my_main:app"
APP_PORT=8000
# Supervisor 프로그램 이름을 "server_log"로 지정
SUPERVISOR_PROGRAM_NAME="server_log"
DB_FILE_NAME="my_admin_config.db"
# HOME_IP="여기에 IP 주소 입력" # 외부 접근 시 사용할 사용자님의 공인 IP. 예: "61.85.61.62"
# 또는 아래 명령어로 자동 감지 (SSH 접속 시)
HOME_IP=$(who am i | awk '{print $5}' | tr -d '()')

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
# DB 파일 초기화 로직
# --------------------------------------------------------------------------
echo ">> [초기화] 이전 설치된 DB 파일(${DB_FILE_NAME}) 확인 및 삭제 시작..."
if [ -f "$DB_FILE_NAME" ]; then
    rm "$DB_FILE_NAME"
    echo "✅ ${DB_FILE_NAME} 파일을 삭제하여 관리자 설정을 초기화했습니다."
else
    echo "DB 파일이 존재하지 않아 초기화가 필요 없습니다. (최초 설치 상태)"
fi
# --------------------------------------------------------------------------

echo ">> Python 가상 환경을 ${CURRENT_APP_DIR}에 설치합니다."
python3 -m venv venv
source venv/bin/activate
pip install gunicorn
# Caddy Admin API 호출을 위해 'requests' 라이브러리 추가
pip install -r my_requirements.txt requests

# --------------------------------------------------------------------------
# DB 초기화 및 HOME_IP 등록
# --------------------------------------------------------------------------
echo ">> DB 초기화 및 HOME_IP(${HOME_IP}) 등록 시작..."
python3 << PYTHON_SCRIPT
import sys
sys.path.insert(0, '${CURRENT_APP_DIR}')

from my_utilities.my_db import init_db, get_unconfigured_admin_id, update_home_ip

# DB 초기화
init_db()
print("✅ DB 초기화 완료")

# 미설정 관리자 ID 조회 (최초 설치 시 자동 생성된 admin ID)
admin_id = get_unconfigured_admin_id()

if admin_id:
    # HOME_IP 등록
    success = update_home_ip(admin_id, '${HOME_IP}')
    if success:
        print(f"✅ HOME_IP(${HOME_IP})가 관리자({admin_id})에게 성공적으로 등록되었습니다.")
    else:
        print(f"❌ HOME_IP 등록 실패")
else:
    print("⚠️ 미설정 관리자 ID를 찾을 수 없습니다.")
PYTHON_SCRIPT
# --------------------------------------------------------------------------

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
echo ">> Caddyfile (${CADDY_CONF}) 생성 및 초기 설정 (Admin API 활성화 및 HOME_IP + 트레이딩뷰 IP 제한)..."
cat <<EOF | sudo tee "$CADDY_CONF" > /dev/null
# Caddy Admin API를 로컬호스트에 바인딩
{
    admin 127.0.0.1:2019
}

# 초기 접근: HOME_IP + 트레이딩뷰 기본 IP 허용
:80 {
    @allowed_ips {
        remote_ip ${HOME_IP} 52.89.214.238 34.212.75.30 54.218.53.128 52.32.178.7
    }

    handle @allowed_ips {
        reverse_proxy 127.0.0.1:${APP_PORT}
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