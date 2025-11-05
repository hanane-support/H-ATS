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

# 템플릿 디렉토리가 'my_templates'에 있다고 가정합니다. (환경에 따라 수정 필요)
templates = Jinja2Templates(directory="my_templates")

# 라우터 객체 설정
domain_security_router = APIRouter()


# ==========================================================
# 🚨 Caddy 서버 관리 유틸리티 (실제 실행 로직 구현)
# ==========================================================

def run_caddyfile_script(*args: str) -> tuple[bool, str]:
    """
    my_caddyfile.py 스크립트를 subprocess로 실행하는 함수입니다.
    가변 인수를 명령줄 인수로 전달하여 Caddyfile을 덮어쓰거나 새로 생성합니다.
    (주의: my_caddyfile.py가 인수의 개수와 내용을 내부적으로 처리한다고 가정)
    """

    # my_utilities/my_caddyfile.py 파일의 절대 경로를 계산합니다.
    # 라우터 파일 위치: .../my_routers/
    # 스크립트 파일 위치: .../my_utilities/
    script_dir = os.path.dirname(os.path.dirname(__file__))
    script_path = os.path.join(script_dir, 'my_utilities', 'my_caddyfile.py')

    if not os.path.exists(script_path):
        error_msg = f">> my_caddyfile.py 스크립트 파일을 찾을 수 없습니다: {script_path}"
        print(error_msg)
        return False, error_msg

    try:
        # Caddyfile 스크립트를 파이썬 인터프리터로 실행하고, 가변 인수를 전달합니다.
        command_list = ["python", script_path] + list(args)

        print(f">> my_caddyfile.py 실행 명령: {' '.join(command_list)}") # 실행 명령 로그 추가

        result = subprocess.run(
            command_list,
            check=True,
            capture_output=True,
            text=True
        )

        # my_caddyfile.py가 성공 시 stdout에 성공 메시지를, 실패 시 stderr에 오류 메시지를 출력한다고 가정합니다.
        print(f">> my_caddyfile.py 실행 완료. Stderr: {result.stderr.strip()}, Stdout: {result.stdout.strip()}")

        # 스크립트 실행은 성공했지만, 스크립트 내부에서 오류 메시지를 stderr로 출력한 경우
        if result.stderr:
            return False, result.stderr.strip()

        # 성공 메시지 반환 (stdout 내용)
        return True, result.stdout.strip()

    except subprocess.CalledProcessError as e:
        error_msg = f">> my_caddyfile.py 실행 실패 (스크립트 내부 오류): {e.stderr.strip()}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f">> my_caddyfile.py 실행 중 예상치 못한 오류 발생: {e}"
        print(error_msg)
        return False, error_msg

def is_caddy_active() -> bool:
    """Caddy 서버의 상태를 확인하는 함수입니다. (더미 로직 유지)"""
    try:
        print(">> Caddy 서버 상태 확인 로직 (더미) - 활성(Active)으로 가정")
        return True
    except Exception as e:
        print(f">> Caddy 서버 상태 확인 실패: {e}")
        return False

# ==========================================================
# 1. 템플릿 렌더링 (GET)
# ==========================================================

# 최종 경로는 /admin/domain_security
@domain_security_router.get("/domain_security", response_class=HTMLResponse)
async def domain_security_manager(request: Request):
    """
    도메인 보안 설정 페이지(my_domain_security.html)를 렌더링하고 보안 상태를 전달합니다.
    """
    if is_caddy_active():
        current_security_status = 'HTTPS'
    else:
        current_security_status = 'HTTP'

    context = {
        "request": request,
        "security_status": current_security_status
    }
    return templates.TemplateResponse(
        "my_domain_security.html",
        context
    )

# ==========================================================
# 2. 보안 적용 로직 (POST) - 기존 로직 복구 (run_caddyfile_script 시그니처 변경에 맞게 호출 유지)
# ==========================================================

@domain_security_router.post("/domain_security/apply_security")
async def apply_security(request: Request):
    """
    my_caddyfile.py를 실행하여 보안 적용을 시도합니다.
    """
    domain_to_register = None
    # IP를 받지 않음 (기존 로직 유지)

    try:
        data = await request.json()
        domain_to_register = data.get("domain")
        # IP 주소 처리는 my_caddyfile.py 내부에서 처리한다고 가정하고, 여기서는 도메인만 전달합니다.

        if not domain_to_register:
             return JSONResponse(
                 status_code=400,
                 content={"success": False, "message": "도메인 정보가 요청 본문에 포함되어 있지 않습니다."}
             )

        print(f"클라이언트에서 받은 도메인: {domain_to_register}")
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

    # 2. my_caddyfile.py 실행 로직 (도메인 인수를 전달)
    # run_caddyfile_script가 *args를 받으므로, 단일 인수로 호출해도 문제 없습니다.
    success, message = run_caddyfile_script(LINUX_CADDYFILE_PATH, domain_to_register)

    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"my_caddyfile.py 실행 실패: {message}"}
        )

    # 3. Caddy 서버 상태 확인 (더미)
    if not is_caddy_active():
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Caddyfile 적용 성공, 하지만 Caddy 서버 활성화 상태 확인 실패."}
        )

    # 모든 과정 성공 시
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": message or "Caddyfile 생성/덮어쓰기 완료."}
    )

# ==========================================================
# 3. 도메인 해제 로직 (POST) - IP 정보 전달 및 run_caddyfile_script 호출 수정
# ==========================================================

@domain_security_router.post("/domain_security/release_security")
async def release_security(request: Request):
    """
    my_caddyfile.py를 실행하여 도메인 보안을 해제하고 IP 기반으로 복구합니다.
    """
    # domain_to_release는 필요 없지만, ip_address는 복구 Caddyfile 생성을 위해 필수적입니다.
    ip_address = None

    try:
        data = await request.json()
        # IP 주소 정보를 요청 본문에서 가져옵니다.
        ip_address = data.get("ip")

        if not ip_address:
            # IP 주소가 없으면 복구 Caddyfile을 만들 수 없으므로 400 오류 반환
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

    # 2. my_caddyfile.py 실행 로직 (해제 명령과 IP 인수를 전달)
    # my_caddyfile.py가 첫 번째 인수를 도메인(여기서는 IP로 대체), 두 번째를 명령으로 인식합니다.
    success, message = run_caddyfile_script(LINUX_CADDYFILE_PATH, ip_address, "release")

    if not success:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"my_caddyfile.py 실행 실패: {message}"}
        )

    # 3. Caddy 서버 상태 확인 (더미)
    if not is_caddy_active():
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Caddyfile 해제 성공, 하지만 Caddy 서버 활성화 상태 확인 실패."}
        )

    # 모든 과정 성공 시
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": message or "Caddyfile 해제/복구 완료."}
    )
