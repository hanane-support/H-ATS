# 리눅스용

import sys
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import json
import requests # Caddy Admin API 호출을 위해 requests 라이브러리 사용
import os # 현재 디렉토리 확인용
import subprocess # Caddyfile 스크립트 실행을 위해 추가

# Caddy Admin API 주소 (Admin API는 배포 스크립트에서 127.0.0.1:2019로 설정됨)
CADDY_ADMIN_API = "http://127.0.0.1:2019"

# Caddy 설정의 HTTP 서버 ID (기본값)
CADDY_SERVER_ID = "srv0"

# Vultr Linux 서버의 Caddyfile 경로 (해제 시 IP 전용 설정 복구를 위해 필요)
LINUX_CADDYFILE_PATH = "/etc/caddy/Caddyfile"

# Gunicorn으로 실행되는 FastAPI 애플리케이션의 포트 (배포 스크립트의 APP_PORT와 일치해야 함)
# 도메인 등록 시 리버스 프록시 타겟으로 사용됩니다.
FASTAPI_PROXY_PORT = 8000

# 템플릿 디렉토리가 'my_templates'에 있다고 가정합니다. (환경에 따라 수정 필요)
templates = Jinja2Templates(directory="my_templates")

# 라우터 객체 설정
domain_security_router = APIRouter()


# ==========================================================
# 🚨 Caddy 서버 관리 유틸리티 (스크립트 실행 로직 재도입)
# ==========================================================

def run_caddyfile_script(*args: str) -> tuple[bool, str]:
    """
    my_caddyfile.py 스크립트를 subprocess로 실행하는 함수입니다.
    가변 인수를 명령줄 인수로 전달하여 Caddyfile을 덮어쓰거나 새로 생성하고 Caddy를 재시작합니다.
    """

    # my_utilities/my_caddyfile.py 파일의 절대 경로를 계산합니다.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 가정: 라우터 파일 위치: .../my_routers/, 스크립트 파일 위치: .../my_utilities/
    # 실제 환경에 맞게 경로를 조정해야 합니다.
    script_path = os.path.join(script_dir, "..", "my_utilities", "my_caddyfile.py")

    # 스크립트 경로가 존재하는지 확인 (디버깅 목적)
    if not os.path.exists(script_path):
        return False, f"오류: 스크립트 파일이 존재하지 않습니다. 경로 확인: {script_path}"

    try:
        # 명령: python my_caddyfile.py <도메인/IP> [release]
        command_list = [sys.executable, script_path] + list(args)

        # subprocess.run을 사용하여 스크립트 실행 및 결과 캡처
        result = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=True # 0이 아닌 반환 코드가 발생하면 CalledProcessError 발생
        )
        # 스크립트가 성공적으로 실행되고 Caddy가 재시작되면 True 반환
        return True, result.stdout.strip()

    except subprocess.CalledProcessError as e:
        # 스크립트 실행 중 오류 발생 (예: sys.exit(1) 또는 0이 아닌 코드 반환)
        error_output = e.stderr.strip()
        return False, f"스크립트 실행 오류: {error_output}"
    except FileNotFoundError:
        return False, f"오류: Python 인터프리터({sys.executable}) 또는 스크립트 파일({script_path})을 찾을 수 없습니다."
    except Exception as e:
        return False, f"예상치 못한 오류 발생: {e}"


def caddy_admin_request(method: str, endpoint: str, data: dict = None) -> tuple[bool, str]:
    """Caddy Admin API에 요청을 보내는 범용 함수."""
    url = f"{CADDY_ADMIN_API}{endpoint}"
    headers = {"Content-Type": "application/json"}
    try:
        if data is None:
            response = requests.request(method, url, headers=headers, timeout=5)
        else:
            response = requests.request(method, url, headers=headers, json=data, timeout=5)

        # 200/201/204 등 성공 코드 확인
        if response.ok:
            # DELETE 요청이나 content가 없는 경우 예외 처리
            if response.status_code == 204 or not response.content:
                return True, "Success"
            return True, response.json()
        else:
            # Caddy에서 반환된 오류 메시지 확인
            try:
                error_detail = response.json()
            except json.JSONDecodeError:
                error_detail = response.text
            return False, f"Caddy API 오류 (Status: {response.status_code}): {error_detail}"

    except requests.exceptions.RequestException as e:
        return False, f"Caddy Admin API 통신 오류: {e}"


def get_config_route_id(domain: str) -> str | None:
    """도메인에 해당하는 Caddy 라우트의 ID를 찾아 반환합니다."""
    success, config = caddy_admin_request('GET', '/config')
    if not success:
        print(f"Caddy 설정 로드 실패: {config}")
        return None

    try:
        # Caddy config 구조: apps -> http -> servers -> srv0 -> routes
        routes = config.get('apps', {}).get('http', {}).get('servers', {}).get(CADDY_SERVER_ID, {}).get('routes', [])

        for route in routes:
            # match[0].host[0]이 등록된 도메인과 일치하는지 확인
            # 'match' 리스트의 첫 번째 요소에서 'host' 리스트의 첫 번째 요소를 확인
            hosts = route.get('match', [{}])[0].get('host', [])
            if hosts and hosts[0] == domain:
                return route.get('id')

        return None
    except Exception as e:
        print(f"Caddy 설정 파싱 오류: {e}")
        return None


# ==========================================================
# 라우터 엔드포인트
# ==========================================================

@domain_security_router.get("/", response_class=HTMLResponse)
async def domain_security_page(request: Request):
    """도메인 및 보안 관리 페이지 (Jinja2 템플릿 렌더링)."""
    # 실제 도메인 상태는 클라이언트 측 JavaScript에서 Caddy API를 통해 가져옵니다.
    # 초기 템플릿 렌더링을 위해 '없음'으로 설정
    return templates.TemplateResponse(
        "my_domain_security.html",
        {"request": request, "domain_name": "없음"}
    )


# ----------------------------------------------------------
# Caddy Admin API를 통한 동적 도메인 등록 (유지)
# ----------------------------------------------------------

@domain_security_router.post("/register_domain")
async def register_domain(request: Request):
    """Caddy Admin API를 사용하여 도메인 라우트를 동적으로 추가합니다."""
    domain = None
    try:
        data = await request.json()
        domain = data.get("domain")

        if not domain:
            return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "도메인 정보가 요청 본문에 포함되어 있지 않습니다."}
             )
    except json.JSONDecodeError:
        return JSONResponse(
             status_code=400,
             content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
         )
    except Exception as e:
        return JSONResponse(
             status_code=500,
             content={"success": False, "message": f"요청 처리 중 오류 발생: {e}"}
         )

    # 1. 라우트 ID 생성 (Caddy가 자동으로 생성할 수도 있지만 명시적으로 관리하기 위해)
    route_id = f"domain_route_{domain.replace('.', '_')}"

    # 2. Caddy API에 보낼 설정 JSON 페이로드 (리버스 프록시 설정)
    # {domain}으로 들어오는 요청을 FastAPI 포트(8000)로 리버스 프록시
    payload = {
        "id": route_id,
        "match": [
            {
                "host": [domain]
            }
        ],
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [
                    {
                        "dial": f"127.0.0.1:{FASTAPI_PROXY_PORT}"
                    }
                ]
            }
        ],
        "terminal": True # 이 라우트가 처리되면 이후 라우트를 검사하지 않음
    }

    # Caddy API 호출: HTTP 서버의 routes 리스트에 새로운 라우트 추가
    # Endpoint: /config/apps/http/servers/srv0/routes
    endpoint = f"/config/apps/http/servers/{CADDY_SERVER_ID}/routes"
    success, message = caddy_admin_request('POST', endpoint, payload)

    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Caddy API 설정 실패: {message}"}
        )

    # 성공 시
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"도메인 '{domain}'이(가) 성공적으로 등록되었습니다. HTTPS로 접근 가능합니다."}
    )


# ----------------------------------------------------------
# my_caddyfile.py 스크립트를 통한 도메인 해제 (복구된 로직)
# ----------------------------------------------------------

@domain_security_router.post("/release_domain")
async def release_domain(request: Request):
    """
    my_caddyfile.py 스크립트를 실행하여 Caddyfile을 IP 전용 설정으로 덮어쓰고
    Caddy를 재시작하여 IP 기반 접근으로 복구합니다.
    """
    domain_to_release = None
    ip_address = None
    try:
        data = await request.json()
        # my_caddyfile.py 스크립트 실행을 위해 IP 주소와 도메인 정보를 받음
        domain_to_release = data.get("current_domain")
        ip_address = data.get("ip") # 클라이언트에서 전송되는 IP 주소

        if not ip_address:
             return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "IP 주소 정보가 요청 본문에 포함되어 있지 않습니다."}
             )

        if not domain_to_release or domain_to_release == '없음':
             # 도메인 정보가 없더라도 IP 복구는 시도할 수 있지만, 메시지 처리를 위해 확인
             print("경고: 해제할 도메인 정보가 명확하지 않습니다. IP 복구를 시도합니다.")

        print(f"클라이언트에서 받은 해제 요청 IP: {ip_address}")
    except json.JSONDecodeError:
        return JSONResponse(
             status_code=400,
             content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
         )
    except Exception as e:
        return JSONResponse(
             status_code=500,
             content={"success": False, "message": f"요청 처리 중 오류 발생: {e}"}
         )

    # 2. my_caddyfile.py 실행 로직 (해제 명령과 IP 인수를 전달)
    # my_caddyfile.py는 첫 번째 인수를 도메인(여기서는 IP로 대체), 두 번째를 명령으로 인식합니다.
    # IP 복구 로직이 실행되도록 합니다.
    success, message = run_caddyfile_script(ip_address, "release")

    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"my_caddyfile.py 실행 실패: {message}"}
        )

    # 성공 시 (스크립트에서 Caddy 재시작까지 완료됨)
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"도메인 '{domain_to_release}'이(가) 성공적으로 해제되었습니다. IP 기반 접근으로 복구됩니다. 스크립트 결과: {message}"}
    )


# ----------------------------------------------------------
# Caddy 현재 상태 확인 (유지)
# ----------------------------------------------------------

@domain_security_router.get("/status")
async def get_caddy_status():
    """Caddy Admin API에서 현재 설정된 도메인 정보를 가져옵니다."""
    success, config = caddy_admin_request('GET', '/config')

    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "domain": "오류", "status": "오류", "message": f"Caddy 설정 로드 실패: {config}"}
        )

    try:
        # Caddy config 구조: apps -> http -> servers -> srv0 -> routes
        routes = config.get('apps', {}).get('http', {}).get('servers', {}).get(CADDY_SERVER_ID, {}).get('routes', [])

        current_domain = "없음"
        security_status = "미적용 (HTTP)"

        # 라우트 목록을 순회하며 도메인(HTTPS) 라우트를 찾습니다.
        for route in routes:
            # 도메인 등록 라우트는 host 매칭이 있어야 합니다.
            hosts = route.get('match', [{}])[0].get('host', [])
            if hosts:
                current_domain = hosts[0]
                security_status = "적용 완료 (HTTPS)"
                break # 첫 번째 도메인 라우트를 찾으면 종료

        return JSONResponse(
            status_code=200,
            content={"success": True, "domain": current_domain, "status": security_status}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "domain": "오류", "status": "오류", "message": f"Caddy 설정 파싱 오류: {e}"}
        )