# 리눅스용

import sys
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import json
import requests # Caddy Admin API 호출을 위해 requests 라이브러리 사용
import os # 현재 디렉토리 확인용

# Caddy Admin API 주소 (Admin API는 배포 스크립트에서 127.0.0.1:2019로 설정됨)
CADDY_ADMIN_API = "http://127.0.0.1:2019"

# Caddy 설정의 HTTP 서버 ID (기본값)
CADDY_SERVER_ID = "srv0"

# Gunicorn으로 실행되는 FastAPI 애플리케이션의 포트 (배포 스크립트의 APP_PORT와 일치해야 함)
# 도메인 등록 시 리버스 프록시 타겟으로 사용됩니다.
FASTAPI_PROXY_PORT = 8000

# 템플릿 디렉토리가 'my_templates'에 있다고 가정합니다. (환경에 따라 수정 필요)
# 주의: 실제 프로젝트 구조에 맞게 경로를 설정해야 합니다.
# 예: templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "my_templates"))
templates = Jinja2Templates(directory="my_templates")

# 라우터 객체 설정
domain_security_router = APIRouter()


# ==========================================================
# 🚨 Caddy Admin API 유틸리티 (핵심 구현)
# ==========================================================

def get_config_route_id(domain: str) -> str:
    """도메인으로 라우트 ID를 생성합니다. (고유 식별자)"""
    # Caddy 설정에서 사용할 고유 ID를 생성합니다.
    return f"route_{domain.replace('.', '_').replace('-', '_')}"

def caddy_admin_request(method: str, endpoint: str, json_data: dict = None) -> tuple[bool, str]:
    """Caddy Admin API에 HTTP 요청을 보내는 범용 함수"""
    url = f"{CADDY_ADMIN_API}{endpoint}"
    print(f">> Caddy API 요청: {method} {url}")
    try:
        if method == 'POST':
            response = requests.post(url, json=json_data, timeout=5)
        elif method == 'DELETE':
            response = requests.delete(url, timeout=5)
        elif method == 'GET':
            response = requests.get(url, timeout=5)
        else:
            return False, "지원하지 않는 HTTP 메소드입니다."

        response.raise_for_status()  # 4xx, 5xx 에러 시 예외 발생

        # POST, DELETE는 성공 시 빈 응답을 반환할 수 있음
        if method == 'GET':
             return True, response.json()
        return True, "Caddy 설정 변경 성공"

    except requests.exceptions.HTTPError as e:
        error_msg = f"Caddy Admin API HTTP 오류: {response.status_code} - {response.text.strip()}"
        print(f">> 오류: {error_msg}")
        return False, error_msg
    except requests.exceptions.ConnectionError:
        error_msg = f"Caddy Admin API 연결 실패. Caddy가 켜져 있고 {CADDY_ADMIN_API}에서 실행 중인지 확인하세요."
        print(f">> 오류: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Caddy Admin API 통신 중 예상치 못한 오류: {e}"
        print(f">> 오류: {error_msg}")
        return False, error_msg


# ==========================================================
# 1. 템플릿 렌더링 (GET)
# ==========================================================

# 최종 경로는 /admin/domain_security
@domain_security_router.get("/domain_security", response_class=HTMLResponse)
async def domain_security_manager(request: Request):
    """
    도메인 보안 설정 페이지(my_domain_security.html)를 렌더링합니다.
    (실제 도메인 상태는 클라이언트 JS에서 API 호출로 확인하는 것이 더 정확합니다.)
    """
    context = {
        "request": request,
        # 초기 상태는 '미적용 (HTTP)'로 가정하고 클라이언트에서 업데이트합니다.
        "security_status": 'HTTP'
    }
    return templates.TemplateResponse(
        "my_domain_security.html",
        context
    )

# ==========================================================
# 2. 보안 적용 로직 (POST) - Caddy Admin API 호출
# ==========================================================

@domain_security_router.post("/domain_security/apply_security")
async def apply_security(request: Request):
    """
    Caddy Admin API를 사용하여 새로운 도메인 라우트를 동적으로 추가합니다.
    """
    domain_to_register = None
    try:
        data = await request.json()
        domain_to_register = data.get("domain")

        if not domain_to_register:
             return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "도메인 정보가 요청 본문에 포함되어 있지 않습니다."}
             )

        # Caddy가 자동으로 HTTPS 인증서를 발급하고 리버스 프록시하는 JSON 설정
        route_id = get_config_route_id(domain_to_register)
        caddy_json_config = {
            "@id": route_id,
            "match": [
                {
                    "host": [domain_to_register]
                }
            ],
            "handle": [
                {
                    "handler": "reverse_proxy",
                    "upstreams": [
                        {
                            "dial": f"127.0.0.1:{FASTAPI_PROXY_PORT}" # FastAPI 포트로 리버스 프록시
                        }
                    ]
                }
            ],
            # 이 라우트가 처리되면 다른 라우트는 확인하지 않도록 설정
            "terminal": True
        }

        # Caddy API 호출: 기존 HTTP 서버의 라우트 배열에 새 라우트 추가
        # Endpoint: /config/apps/http/servers/srv0/routes (배열에 POST하면 추가됨)
        endpoint = f"/config/apps/http/servers/{CADDY_SERVER_ID}/routes"
        success, message = caddy_admin_request('POST', endpoint, caddy_json_config)

        if not success:
            # 실패 시, 에러 메시지 반환
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"Caddy API 설정 실패: {message}"}
            )

        # 성공 시
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": f"도메인 '{domain_to_register}'이(가) 성공적으로 등록되었으며, Caddy가 자동 HTTPS 인증서 발급을 시작합니다."}
        )

    except json.JSONDecodeError:
        return JSONResponse(
             status_code=400,
             content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
         )
    except Exception as e:
        return JSONResponse(
             status_code=500,
             content={"success": False, "message": f"요청 처리 중 예상치 못한 오류 발생: {e}"}
         )


# ==========================================================
# 3. 도메인 해제 로직 (POST) - Caddy Admin API 호출
# ==========================================================

@domain_security_router.post("/domain_security/release_security")
async def release_security(request: Request):
    """
    Caddy Admin API를 사용하여 도메인 라우트를 삭제합니다.
    """
    domain_to_release = None
    try:
        data = await request.json()
        # 클라이언트 JS가 현재 등록된 도메인 이름을 'current_domain'으로 보낸다고 가정
        domain_to_release = data.get("current_domain")

        if not domain_to_release or domain_to_release == '없음':
            return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "해제할 유효한 도메인 정보가 요청 본문에 포함되어 있지 않습니다."}
             )

        route_id = get_config_route_id(domain_to_release)

        # Caddy API 호출: ID를 이용해 라우트 설정 삭제
        # Endpoint: /id/{route_id}
        endpoint = f"/id/{route_id}"
        success, message = caddy_admin_request('DELETE', endpoint)

        if not success:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"Caddy API 설정 실패: {message}"}
            )

        # 성공 시
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": f"도메인 '{domain_to_release}'이(가) 성공적으로 해제되었습니다. IP 기반 접근으로 복구됩니다."}
        )

    except json.JSONDecodeError:
        return JSONResponse(
             status_code=400,
             content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
         )
    except Exception as e:
        return JSONResponse(
             status_code=500,
             content={"success": False, "message": f"요청 처리 중 예상치 못한 오류 발생: {e}"}
         )