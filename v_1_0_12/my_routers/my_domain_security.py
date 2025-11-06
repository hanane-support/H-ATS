# 리눅스용

import sys
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess
import os
import json # Request.json() 처리를 위해 추가

# Vultr Linux 서버의 Caddyfile 경로
LINUX_CADDYFILE_PATH = "/etc/caddy/Caddyfile"
CADDY_SERVICE_NAME = "caddy" # 리눅스에서 Caddy 서비스 이름

# 템플릿 디렉토리가 'my_templates'에 있다고 가정합니다. (환경에 따라 수정 필요)
templates = Jinja2Templates(directory="my_templates")

# 라우터 객체 설정
domain_security_router = APIRouter()


# ==========================================================
# 🚨 Caddy 서버 관리 유틸리티 (실제 실행 로직 구현)
# ==========================================================

def run_caddyfile_script(caddyfile_path: str, dynamic_host: str, command: str) -> tuple[bool, str]:
    """
    my_caddyfile.py 스크립트를 subprocess로 실행하는 함수입니다.
    Caddyfile 경로, 도메인/IP, 명령을 인수로 전달하여 Caddyfile을 생성/덮어씁니다.
    """

    # my_utilities/my_caddyfile.py 파일의 절대 경로를 계산합니다.
    # __file__은 현재 my_domain_security.py의 경로입니다.
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "my_utilities")
    script_path = os.path.join(script_dir, "my_caddyfile.py")

    command_list = [sys.executable, script_path, caddyfile_path, dynamic_host, command]

    # Caddyfile은 root 권한이 필요하므로 sudo를 사용합니다.
    command_list.insert(0, 'sudo')

    try:
        # check=True: 0이 아닌 종료 코드가 반환되면 CalledProcessError 발생
        result = subprocess.run(command_list, capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_message = f"스크립트 실행 실패 (종료 코드 {e.returncode}): {e.stderr.strip()}"
        print(f"오류: {error_message}")
        return False, error_message
    except FileNotFoundError:
        error_message = f"스크립트 파일 또는 파이썬 인터프리터(sudo 포함)를 찾을 수 없습니다."
        print(f"오류: {error_message}")
        return False, error_message
    except Exception as e:
        error_message = f"알 수 없는 오류 발생: {e}"
        print(f"오류: {error_message}")
        return False, error_message

def reload_caddy_server() -> tuple[bool, str]:
    """
    systemctl을 사용하여 Caddy 서비스를 재시작/재로드하여 새 Caddyfile을 적용합니다.
    """
    # Caddyfile이 변경되면 reload가 더 안전하고 빠릅니다.
    command = ['sudo', 'systemctl', 'reload', CADDY_SERVICE_NAME]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_message = f"Caddy 서비스 재로드 실패 (종료 코드 {e.returncode}): {e.stderr.strip()}"
        print(f"Caddy 재로드 오류: {error_message}")
        return False, error_message
    except FileNotFoundError:
        error_message = "systemctl 또는 sudo를 찾을 수 없습니다."
        print(f"Caddy 재로드 오류: {error_message}")
        return False, error_message
    except Exception as e:
        error_message = f"Caddy 재로드 중 알 수 없는 오류 발생: {e}"
        print(f"Caddy 재로드 오류: {error_message}")
        return False, error_message

# ==========================================================
# 🌐 라우트 정의
# ==========================================================

@domain_security_router.get("/", response_class=HTMLResponse)
async def get_domain_security_page(request: Request):
    """도메인 및 보안 관리 페이지 표시"""
    return templates.TemplateResponse(
        "my_domain_security.html",
        {
            "request": request,
            # 실제 도메인 상태는 클라이언트 JS에서 Caddy Admin API를 통해 확인합니다.
            "domain_name": request.session.get("active_domain", None),
            "security_status": request.session.get("security_status", "HTTP")
        }
    )

@domain_security_router.post("/apply_security")
async def apply_security(request: Request):
    """
    새로운 도메인을 등록하고 Caddyfile을 업데이트합니다.
    """
    try:
        # 클라이언트에서 도메인과 IP 주소를 JSON으로 받습니다.
        data = await request.json()
        domain_name = data.get("domain")
        ip_address = data.get("ip")

        if not domain_name or not ip_address:
            return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "도메인 이름 또는 IP 주소가 누락되었습니다."}
             )

        print(f"클라이언트에서 받은 등록 요청 도메인: {domain_name}, IP: {ip_address}")
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

    # 1. my_caddyfile.py 실행 로직 (등록 명령과 도메인, IP 인수를 전달)
    # my_caddyfile.py의 예상 인수: [CADDYFILE_PATH, 도메인, command]
    success_caddyfile, message_caddyfile = run_caddyfile_script(LINUX_CADDYFILE_PATH, domain_name, "register")

    if not success_caddyfile:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Caddyfile 생성/업데이트 실패: {message_caddyfile}"}
        )

    # 2. Caddy 서버 재시작 로직 실행 (핵심 추가 로직)
    success_reload, message_reload = reload_caddy_server()

    if not success_reload:
        # Caddyfile 생성은 성공했지만 Caddy 재시작 실패.
        # Caddyfile은 새 설정이 적용되어 있으나 서비스가 로드하지 못함.
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Caddyfile 업데이트는 성공했으나, Caddy 서비스 재로드 실패: {message_reload}"}
        )

    # 성공 시: 클라이언트 측에서 상태 업데이트 및 HTTPS 확인 시작
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"도메인 '{domain_name}' 등록 및 Caddy 재로드 성공. HTTPS 적용 대기 중."}
    )

@domain_security_router.post("/release_security")
async def release_security(request: Request):
    """
    도메인을 해제하고 Caddyfile에서 도메인 설정을 제거합니다 (IP 접근 복구).
    """
    try:
        # 클라이언트에서 IP 주소를 JSON으로 받습니다.
        data = await request.json()
        ip_address = data.get("ip")

        if not ip_address:
            return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "IP 주소 정보가 요청 본문에 포함되어 있지 않습니다."}
             )

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

    # 1. my_caddyfile.py 실행 로직 (해제 명령과 IP 인수를 전달)
    # my_caddyfile.py의 예상 인수: [CADDYFILE_PATH, IP, command]
    success_caddyfile, message_caddyfile = run_caddyfile_script(LINUX_CADDYFILE_PATH, ip_address, "release")

    if not success_caddyfile:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Caddyfile 생성/복구 실패: {message_caddyfile}"}
        )

    # 2. Caddy 서버 재시작 로직 실행 (핵심 추가 로직)
    success_reload, message_reload = reload_caddy_server()

    if not success_reload:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Caddyfile 업데이트는 성공했으나, Caddy 서비스 재로드 실패: {message_reload}"}
        )

    # 성공 시: 클라이언트 측에서 상태 업데이트
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"도메인 해제 및 Caddy 재로드 성공. HTTP 접근으로 복구되었습니다."}
    )