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

# Caddy 데이터 백업 관련 설정
CADDY_DATA_DIR="/root/.local/share/caddy"
BACKUP_DIR="/root/caddy_backup"
BACKUP_FILE="$BACKUP_DIR/caddy_data_backup.tar.gz"

#==============================================================
# 2. 기존 Caddy 데이터 백업 확인
#==============================================================

echo ""
echo "=============================================================="
echo "🔍 기존 Caddy 인증서 데이터 확인 중..."
echo "=============================================================="

if [ -d "$CADDY_DATA_DIR" ]; then
    echo "✅ 기존 Caddy 데이터 디렉토리 발견: $CADDY_DATA_DIR"
    echo "📦 백업을 생성합니다..."

    # 백업 디렉토리 생성
    mkdir -p "$BACKUP_DIR"

    # 기존 백업 파일이 있으면 타임스탬프 추가하여 보관
    if [ -f "$BACKUP_FILE" ]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        mv "$BACKUP_FILE" "${BACKUP_DIR}/caddy_data_backup_${TIMESTAMP}.tar.gz"
        echo "   기존 백업을 caddy_data_backup_${TIMESTAMP}.tar.gz로 보관했습니다."
    fi

    # 새 백업 생성
    tar -czf "$BACKUP_FILE" -C "$(dirname $CADDY_DATA_DIR)" "$(basename $CADDY_DATA_DIR)"

    if [ $? -eq 0 ]; then
        echo "✅ Caddy 데이터 백업 완료: $BACKUP_FILE"
        echo "   백업 크기: $(du -h $BACKUP_FILE | cut -f1)"
    else
        echo "⚠️ 백업 생성 실패. 계속 진행합니다..."
    fi
else
    echo "ℹ️ 기존 Caddy 데이터 없음 (최초 설치 또는 완전 초기화 상태)"
fi

echo ""

#==============================================================
# 3. 시스템 환경 설정 및 필수 도구 설치
#==============================================================

echo ">> 시스템 업데이트 및 기본 도구 설치 시작..."
apt update -y
apt upgrade -y
# 'requests' 라이브러리를 위해 필요한 Python 도구와 Caddy, Supervisor 설치
apt install -y git python3 python3-venv python3-pip supervisor curl software-properties-common wget ufw

#==============================================================
# 4. UFW 방화벽 설정
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
# 5. 코드 다운로드 및 Python 환경 설정
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
deactivate

#==============================================================
# 6. Gunicorn 및 Supervisor 설정
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
# 7. Caddy 다운로드 및 초기 설정 (Admin API 활성화 및 IP 제한)
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

echo ">> Caddy 서비스 시작 전 백업 복원 확인..."

#==============================================================
# 8. Caddy 데이터 백업 복원
#==============================================================

echo ""
echo "=============================================================="
echo "🔄 Caddy 인증서 데이터 백업 복원 시도..."
echo "=============================================================="

if [ -f "$BACKUP_FILE" ]; then
    echo "✅ 백업 파일 발견: $BACKUP_FILE"
    echo "📂 Caddy 데이터 디렉토리로 복원 중..."

    # Caddy 서비스 일시 중지
    systemctl stop caddy 2>/dev/null || true

    # 백업 복원
    tar -xzf "$BACKUP_FILE" -C /

    if [ $? -eq 0 ]; then
        echo "✅ Caddy 데이터 복원 완료!"
        echo "   복원 위치: $CADDY_DATA_DIR"
        echo "   💡 기존 인증서가 자동으로 재사용됩니다."
    else
        echo "⚠️ 복원 실패. Caddy가 새로 인증서를 발급합니다."
    fi
else
    echo "ℹ️ 복원할 백업 파일 없음"
    echo "   💡 Caddy가 Let's Encrypt에서 자동으로 인증서를 발급합니다."
    echo "   💡 도메인 소유권이 유효하면 중복 인증서 정책으로 빠르게 발급됩니다."
fi

echo ""

#==============================================================
# 9. Caddy 서비스 시작
#==============================================================

echo ">> Caddy 서비스 시작 및 설정 적용..."
systemctl enable caddy
systemctl restart caddy

#==============================================================
# 10. 설치 완료 및 안내
#==============================================================

echo ""
echo "=============================================================="
echo "✅ 배포 스크립트가 완료되었습니다!"
echo "=============================================================="
echo ""
echo "📋 설치 정보:"
echo "   - 애플리케이션: $PROJECT_ROOT_DIR/$APP_SUB_DIR"
echo "   - Supervisor 프로그램: $SUPERVISOR_PROGRAM_NAME"
echo "   - 접근 IP 제한: $MY_IP"
echo ""
echo "🔐 Caddy 인증서 백업:"
echo "   - 백업 위치: $BACKUP_FILE"
echo "   - 재설치 시 자동 복원됩니다"
echo ""
echo "📝 상태 확인 명령어:"
echo "   - 앱 로그: supervisorctl tail -f $SUPERVISOR_PROGRAM_NAME"
echo "   - Caddy 상태: systemctl status caddy"
echo "   - 백업 확인: ls -lh $BACKUP_DIR"
echo ""
echo "💡 수동 백업/복원 명령어:"
echo "   - 백업: tar -czf $BACKUP_FILE -C /root/.local/share caddy"
echo "   - 복원: tar -xzf $BACKUP_FILE -C /"
echo ""
echo "=============================================================="