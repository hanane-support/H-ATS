# Caddy Admin API 기반 도메인 관리 라우터

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import json
import requests

# Caddy Admin API 주소 (기본값: http://127.0.0.1:2019)
CADDY_ADMIN_API = "http://127.0.0.1:2019"

# Caddy 설정의 HTTP 서버 ID (기본값)
CADDY_SERVER_ID = "srv0"

# FastAPI 애플리케이션의 리버스 프록시 타겟 포트
FASTAPI_PROXY_PORT = 8000

templates = Jinja2Templates(directory="my_templates")
domain_security_router = APIRouter()

# ==========================================================
# Caddy 서버 관리 유틸리티
# ==========================================================

def caddy_admin_request(method: str, endpoint: str, data: dict = None) -> tuple[bool, str]:
    """Caddy Admin API에 요청을 보내는 범용 함수."""
    url = f"{CADDY_ADMIN_API}{endpoint}"
    headers = {"Content-Type": "application/json"}
    try:
        if data is None:
            response = requests.request(method, url, headers=headers, timeout=5)
        else:
            response = requests.request(method, url, headers=headers, json=data, timeout=5)

        if response.ok:
            if response.status_code == 204 or not response.content:
                return True, "Success"
            return True, response.json()
        else:
            try:
                error_detail = response.json()
            except json.JSONDecodeError:
                error_detail = response.text
            return False, f"Caddy API Error (Status: {response.status_code}): {error_detail}"

    except requests.exceptions.RequestException as e:
        return False, f"Caddy Admin API Connection Error: {e}"

# ==========================================================
# 라우터 엔드포인트
# ==========================================================

@domain_security_router.get("/", response_class=HTMLResponse)
async def domain_security_page(request: Request):
    """도메인 및 보안 관리 페이지를 렌더링합니다."""
    return templates.TemplateResponse(
        "my_domain_security.html",
        {"request": request, "domain_name": "없음"}
    )

# ----------------------------------------------------------
# 도메인 등록 (Caddy Admin API 사용)
# ----------------------------------------------------------
@domain_security_router.post("/apply_security")
async def apply_security(request: Request):
    """Caddy Admin API를 사용하여 도메인 라우트를 동적으로 추가합니다."""
    try:
        data = await request.json()
        domain = data.get("domain")
        if not domain:
            return JSONResponse(status_code=400, content={"success": False, "message": "도메인이 제공되지 않았습니다."})
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"success": False, "message": "잘못된 JSON 형식입니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"요청 처리 중 오류: {e}"})

    route_id = f"domain_route_{domain.replace('.', '_')}"
    payload = {
        "@id": route_id,
        "match": [{"host": [domain]}],
        "handle": [{
            "handler": "reverse_proxy",
            "upstreams": [{"dial": f"127.0.0.1:{FASTAPI_PROXY_PORT}"}]
        }],
        "terminal": True
    }

    endpoint = f"/config/apps/http/servers/{CADDY_SERVER_ID}/routes"
    success, message = caddy_admin_request('POST', f"{endpoint}?@first", payload)

    if not success:
        return JSONResponse(status_code=500, content={"success": False, "message": f"Caddy API 설정 실패: {message}"})

    return JSONResponse(content={"success": True, "message": f"도메인 '{domain}'이(가) 성공적으로 등록되었습니다. Caddy가 자동으로 HTTPS를 적용합니다."})

# ----------------------------------------------------------
# 도메인 해제 (Caddy Admin API 사용)
# ----------------------------------------------------------
@domain_security_router.post("/release_security")
async def release_security(request: Request):
    """Caddy Admin API를 사용하여 도메인 라우트를 동적으로 삭제합니다."""
    try:
        data = await request.json()
        domain = data.get("current_domain")
        if not domain or domain == '없음':
            return JSONResponse(status_code=400, content={"success": False, "message": "해제할 도메인 정보가 없습니다."})
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"success": False, "message": "잘못된 JSON 형식입니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"요청 처리 중 오류: {e}"})

    route_id = f"domain_route_{domain.replace('.', '_')}"
    endpoint = f"/id/{route_id}"
    success, message = caddy_admin_request('DELETE', endpoint)

    if not success:
        # Caddy는 ID가 없으면 404 대신 500 오류와 함께 메시지를 반환할 수 있습니다.
        if "no such ID" in str(message):
             return JSONResponse(status_code=404, content={"success": False, "message": f"해당 ID({route_id})를 가진 라우트를 찾을 수 없습니다."})
        return JSONResponse(status_code=500, content={"success": False, "message": f"Caddy API 라우트 삭제 실패: {message}"})

    return JSONResponse(content={"success": True, "message": f"도메인 '{domain}'이(가) 성공적으로 해제되었습니다."})

# ----------------------------------------------------------
# Caddy 현재 상태 확인
# ----------------------------------------------------------
@domain_security_router.get("/status")
async def get_caddy_status():
    """Caddy Admin API에서 현재 설정된 도메인 정보를 가져옵니다."""
    success, config = caddy_admin_request('GET', '/config')

    if not success:
        return JSONResponse(status_code=500, content={"success": False, "domain": "오류", "status": "오류", "message": f"Caddy 설정 로드 실패: {config}"})

    try:
        routes = config.get('apps', {}).get('http', {}).get('servers', {}).get(CADDY_SERVER_ID, {}).get('routes', [])
        current_domain = "없음"
        security_status = "미적용 (HTTP)"

        for route in routes:
            hosts = route.get('match', [{}])[0].get('host', [])
            if hosts:
                # IP 주소나 다른 내부용 호스트가 아닌, 실제 도메인으로 간주할 수 있는 것을 찾습니다.
                # 여기서는 간단히 첫 번째 host를 도메인으로 간주합니다.
                domain_candidate = hosts[0]
                if '.' in domain_candidate and not domain_candidate.startswith('127.0.0.1'):
                    current_domain = domain_candidate
                    security_status = "적용 완료 (HTTPS)"
                    break

        return JSONResponse(status_code=200, content={"success": True, "domain": current_domain, "status": security_status})

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "domain": "오류", "status": "오류", "message": f"Caddy 설정 파싱 오류: {e}"})