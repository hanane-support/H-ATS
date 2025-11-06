import os
import sys
import subprocess # Caddy 서비스 재로드 안내 메시지 출력을 위해 포함할 수 있지만, 여기서는 로직만 유지

# 웹 서버 시작 시 실행되는 것을 방지하기 위해 if __name__ == '__main__': 블록으로 감쌉니다.
if __name__ == '__main__':
    # Caddyfile 경로를 /etc/caddy/Caddyfile 로 고정합니다.
    file_name = "/etc/caddy/Caddyfile"

    # --- 인수 처리 로직 ---
    args = sys.argv[1:]
    if not args:
        print("오류: 인수가 제공되지 않았습니다. 사용법: python my_caddyfile.py <도메인/IP> [release]")
        sys.exit(1)

    dynamic_domain = args[0]
    command = args[1].lower() if len(args) > 1 else 'register'

    # 🚨 수정: 환경 변수에서 허용된 클라이언트 IP를 가져옵니다.
    # 환경 변수가 설정되어 있지 않으면 기본값 '61.85.61.62'를 사용합니다.
    # 사용자의 현재 IP로 변경하려면 'MY_AUTHORIZED_IP' 환경 변수를 설정하세요.
    MY_IP = os.environ.get("MY_AUTHORIZED_IP", "61.85.61.62")

    # --- HTTP 설정 (IP 기반 접근 및 거부) ---
    # 이 설정은 MY_IP로 접근하는 클라이언트만 reverse_proxy를 통해 FastAPI에 접근하도록 허용합니다.
    http_config = f"""
# HTTP (MY_IP로 접근하는 경우)
:80 {{
    @myip {{
        remote_ip {MY_IP}
    }}

    handle @myip {{
        reverse_proxy 127.0.0.1:8000
    }}

    # IP가 일치하지 않는 모든 요청은 접근을 거부합니다.
    handle {{
        respond "Access Denied" 403
    }}
}}"""

    # --- HTTPS 설정 (도메인 등록 시) ---
    https_config_part = f"""
# HTTPS (도메인으로 접근하는 경우, 자동 인증서 발급)
{dynamic_domain} {{
    reverse_proxy 127.0.0.1:8000
}}"""

    # --- Caddyfile 내용 결정 로직 ---
    caddyfile_content = ""
    action_description = ""

    if command == 'release':
        # 해제 모드: HTTP 설정만으로 복구 (IP 기반 접근 제어 유지)
        caddyfile_content = http_config.strip()
        action_description = f"도메인 해제 (HTTP 복구 - 허용 IP: {MY_IP})"
    else:
        # 등록 모드 (기본): HTTP(IP 기반)와 HTTPS(도메인) 통합
        caddyfile_content = http_config.strip() + "\\n\\n" + https_config_part.strip()
        action_description = f"도메인 등록 (HTTPS) 및 IP 접근 제어 (허용 IP: {MY_IP})"

    # 4. Caddyfile에 내용 쓰기
    try:
        with open(file_name, 'w') as f:
            f.write(caddyfile_content)
        print(f"성공: Caddyfile '{file_name}'이(가) 다음과 같이 업데이트되었습니다: {action_description}")
        print("참고: Caddyfile 변경 사항을 적용하려면 'sudo systemctl reload caddy' 명령을 실행해야 합니다.")
    except Exception as e:
        print(f"오류: Caddyfile '{file_name}'에 쓰는 중 오류 발생: {e}")
        sys.exit(1)