import os
import sys

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

    # 고정 IP 주소
    MY_IP = "61.85.61.62"

    # --- HTTP 설정 (IP 기반 접근 및 거부) ---
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
        # 해제 모드: HTTP 설정만으로 복구
        caddyfile_content = http_config.strip()
        action_description = f"도메인 해제 (HTTP 복구)"
    else:
        # 등록 모드 (기본): HTTP와 HTTPS 통합
        # 두 설정 사이에 명확한 구분을 위해 줄바꿈 추가
        caddyfile_content = f"{http_config.strip()}\n\n{https_config_part.strip()}"
        action_description = f"도메인 등록 (HTTPS 적용)"

    # 파일 쓰기
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(caddyfile_content)

        # 성공 메시지 출력
        if command == 'release':
            print(f"'{file_name}' 파일이 업데이트되었습니다. {action_description}")
        else:
            print(f"'{file_name}' 파일이 성공적으로 생성/업데이트되었습니다. 도메인: {dynamic_domain}")
        
        print("-" * 30)
    except IOError as e:
        print(f"파일 '{file_name}' 쓰기 중 오류가 발생했습니다: {e}")
        sys.exit(1)
