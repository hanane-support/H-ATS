import subprocess
import requests

# ==========================================================
# 헬퍼 함수: 시스템 상태 확인
# ==========================================================

def get_service_status(service_name: str) -> str:
    """systemd 또는 supervisorctl을 사용하여 서비스 상태를 가져옵니다."""
    if service_name == 'caddy':
        try:
            # systemctl을 사용하여 caddy 상태 확인
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                check=False
            )
            status = result.stdout.strip()
            return status if status else 'UNKNOWN'
        except Exception:
            return 'ERROR'
    
    elif service_name == 'server_log':
        try:
            # supervisorctl을 사용하여 server_log 상태 확인
            result = subprocess.run(
                ['supervisorctl', 'status', service_name],
                capture_output=True,
                text=True,
                check=False
            )
            # 상태 문자열에서 "RUNNING" 또는 "FATAL" 추출
            if 'RUNNING' in result.stdout:
                return 'RUNNING'
            elif 'FATAL' in result.stdout:
                return 'FATAL'
            else:
                # 상태를 알 수 없는 경우 UNKNOWN 반환
                return result.stdout.split()[1].strip() if result.stdout else 'UNKNOWN'
        except Exception:
            return 'ERROR'
            
    return 'N/A'

def get_vultr_server_ip() -> str:
    """외부 서비스를 통해 서버의 공인 IP를 가져옵니다."""
    try:
        # 5초 타임아웃 설정
        response = requests.get('https://api.ipify.org', timeout=5) 
        return response.text.strip()
    except requests.exceptions.RequestException:
        return 'UNKNOWN (API Fail)'

def get_server_info(request) -> dict:
    """모든 서버 상태 및 IP 정보를 딕셔너리로 반환합니다."""
    
    # 1. 클라이언트(나의) IP 주소 가져오기
    # Caddy가 X-Forwarded-For 헤더를 설정해줄 것으로 가정합니다.
    client_ip = request.headers.get("x-forwarded-for") or request.client.host
    
    # 2. 서버 (Vultr) IP 주소 가져오기
    server_ip = get_vultr_server_ip()
    
    # 3. 서비스 상태 가져오기
    fastapi_status = get_service_status('server_log')
    caddy_status = get_service_status('caddy')
    
    return {
        "request": request,
        "my_ip": client_ip,
        "vultr_ip": server_ip,
        "fastapi_status": fastapi_status,
        "caddy_status": caddy_status
    }