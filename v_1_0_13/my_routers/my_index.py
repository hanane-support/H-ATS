import subprocess
import requests
import platform
from datetime import datetime, timedelta

# ==========================================================
# 캐싱을 위한 전역 변수
# ==========================================================
_cached_server_ip = None
_cache_timestamp = None
_cache_duration = timedelta(minutes=5)  # 5분간 캐시 유지

# ==========================================================
# 헬퍼 함수: 시스템 상태 확인
# ==========================================================

def get_service_status(service_name: str) -> str:
    """systemd 또는 supervisorctl을 사용하여 서비스 상태를 가져옵니다."""
    # Windows 환경에서는 건너뛰기
    if platform.system() == "Windows":
        return 'N/A (Windows)'

    if service_name == 'caddy':
        try:
            # systemctl을 사용하여 caddy 상태 확인
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=1  # 1초 타임아웃 추가
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
                check=False,
                timeout=1  # 1초 타임아웃 추가
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
    """외부 서비스를 통해 서버의 공인 IP를 가져옵니다. (캐싱 적용)"""
    global _cached_server_ip, _cache_timestamp

    # 캐시가 유효한 경우 캐시된 값 반환
    if _cached_server_ip and _cache_timestamp:
        if datetime.now() - _cache_timestamp < _cache_duration:
            return _cached_server_ip

    try:
        # 2초 타임아웃으로 단축
        response = requests.get('https://api.ipify.org', timeout=2)
        ip = response.text.strip()

        # 캐시 업데이트
        _cached_server_ip = ip
        _cache_timestamp = datetime.now()

        return ip
    except requests.exceptions.RequestException:
        # 캐시된 값이 있으면 반환, 없으면 UNKNOWN
        return _cached_server_ip if _cached_server_ip else 'UNKNOWN (API Fail)'

def get_server_info(request) -> dict:
    """모든 서버 상태 및 IP 정보를 딕셔너리로 반환합니다."""

    # 1. 클라이언트(나의) IP 주소 가져오기
    # Caddy가 X-Forwarded-For 헤더를 설정해줄 것으로 가정합니다.
    client_ip = request.headers.get("x-forwarded-for") or request.client.host

    # 2. 서버 (Vultr) IP 주소 가져오기 (캐싱됨)
    server_ip = get_vultr_server_ip()

    # 3. 서비스 상태 가져오기 (Windows에서는 건너뜀)
    fastapi_status = get_service_status('server_log')
    caddy_status = get_service_status('caddy')

    return {
        "request": request,
        "my_ip": client_ip,
        "server_ip": server_ip,
        "fastapi_status": fastapi_status,
        "caddy_status": caddy_status
    }