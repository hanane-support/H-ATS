import os
import sys

# 웹 서버 시작 시 실행되는 것을 방지하기 위해 if __name__ == '__main__': 블록으로 감쌉니다.
if __name__ == '__main__':

    # --- 인수 처리 로직 ---
    # 예상 인수: [Caddyfile 경로, 도메인/IP, command]
    args = sys.argv[1:]
    if len(args) < 3:
        # Caddyfile 경로, dynamic_host, command 3개의 인수가 필요합니다.
        sys.stderr.write("오류: 인수가 부족합니다. 사용법: python my_caddyfile.py <파일 경로> <도메인/IP> <명령>\n")
        sys.exit(1)

    file_name = args[0] # my_domain_security.py에서 전달받은 Caddyfile 경로
    dynamic_host = args[1] # 도메인 등록 시: 도메인 이름, 해제 시: IP 주소
    command = args[2].lower() # register 또는 release

    # 고정 IP 주소 (HTTP 블록에 사용)
    # 사용자님이 입력하신 MY_IP: 61.85.61.62
    MY_IP = "61.85.61.62"

    # --- 공통 설정 (Admin API) ---
    admin_config = f"""# Caddy Admin API를 로컬호스트에 바인딩
{{
    admin 127.0.0.1:2019
}}
"""

    # --- HTTP 설정 (IP 기반 접근 및 거부) ---
    # MY_IP를 사용하여 IP 기반 접근 제어 설정
    http_config = f"""
# 초기 접근: MY_IP로 접근하는 관리자 콘솔만 허용
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
    # dynamic_host에 도메인 이름이 들어오므로 이를 사용합니다.
    https_config_part = f"""
# HTTPS (도메인으로 접근하는 경우, 자동 인증서 발급)
{dynamic_host} {{
    reverse_proxy 127.0.0.1:8000
}}"""

    # --- Caddyfile 내용 결정 로직 ---
    caddyfile_content = ""
    action_description = ""

    # Caddyfile은 항상 Admin API 설정으로 시작해야 합니다.
    base_content = f"{admin_config.strip()}\n{http_config.strip()}"

    if command == 'release':
        # 해제 모드: Admin API와 HTTP 설정만 포함하여 복구
        caddyfile_content = base_content
        action_description = f"도메인 해제 (HTTP 복구)"
    else:
        # 등록 모드 (기본): Admin API, HTTP, HTTPS 설정 모두 포함
        caddyfile_content = f"{base_content}\n\n{https_config_part.strip()}"
        action_description = f"도메인 '{dynamic_host}' 등록 (HTTPS 적용)"


    # 4. 파일에 내용 쓰기
    try:
        # 이 스크립트는 'sudo python my_caddyfile.py ...' 형태로 실행되어야 합니다.
        with open(file_name, "w") as f:
            f.write(caddyfile_content)

        print(f"성공: {action_description} 완료.")

    except Exception as e:
        # 오류 발생 시 stderr로 출력
        sys.stderr.write(f"오류: Caddyfile 작성 실패: {e}\n")
        sys.exit(1)