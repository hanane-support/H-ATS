# C:\Python\MY_PROJECT\v_1_0_13\my_routers\my_security.py
# 보안 설정 라우터 (웹훅 패스워드)

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# 유틸리티 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers
from my_utilities.my_db import (
    get_webhook_password,
    update_webhook_password,
    delete_webhook_password,
    get_domain_security_config,
    get_webhook_endpoint,
    update_webhook_endpoint,
    get_allowed_ips,
    update_allowed_ips,
    get_home_ip
)
from .my_index import get_server_info

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 1. 보안 설정 페이지 GET (/admin/security)
# ==========================================================

@router.get("/security", response_class=HTMLResponse)
async def get_security_page(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    보안 설정 페이지(my_security.html)를 렌더링하고 캐시 방지 헤더를 설정합니다.
    """

    # DB에서 현재 사용자의 웹훅 설정 조회
    webhook_password = get_webhook_password(current_user_id)
    webhook_endpoint = get_webhook_endpoint(current_user_id)
    allowed_ips = get_allowed_ips(current_user_id)
    home_ip = get_home_ip(current_user_id)

    # DB에서 도메인 및 보안 상태 조회
    domain_config = get_domain_security_config(current_user_id)

    # 서버 정보 가져오기
    server_info = get_server_info(request)

    # allowed_ips 기본값 설정 (home_ip가 있으면 항상 포함)
    default_tradingview_ips = "52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7"

    # 기본값 계산 (해제 버튼 disabled 판단용)
    default_allowed_ips = f"{home_ip}, {default_tradingview_ips}" if home_ip else default_tradingview_ips

    # DB에서 가져온 allowed_ips가 없으면 기본값 사용
    if not allowed_ips:
        allowed_ips = default_allowed_ips
    else:
        # DB에 저장된 값이 있어도 home_ip가 포함되어 있지 않으면 추가
        if home_ip and home_ip not in allowed_ips:
            allowed_ips = f"{home_ip}, {allowed_ips}"

    context = {
        "request": request,
        "current_page": "/admin/security",
        "user_id": current_user_id,
        "webhook_password": webhook_password if webhook_password else "",
        "webhook_endpoint": webhook_endpoint if webhook_endpoint else "/webhook",
        "allowed_ips": allowed_ips,
        "default_allowed_ips": default_allowed_ips,
        "home_ip": home_ip if home_ip else "",
        "domain_name": domain_config.get("domain_name", "없음"),
        "security_status": domain_config.get("security_status", "HTTP"),
        **server_info  # 서버 정보 추가 (my_ip, server_ip 등)
    }

    response = templates.TemplateResponse("my_security.html", context)
    return set_no_cache_headers(response)


# ==========================================================
# 2. 웹훅 패스워드 등록 POST (/admin/security/register_webhook)
# ==========================================================

@router.post("/security/register_webhook", response_class=JSONResponse)
async def register_webhook_password(
    request: Request,
    webhook_password: str = Form(...),
    current_user_id: str = Depends(require_admin_login)
):
    """
    웹훅 패스워드를 등록합니다.
    """

    # 입력값 검증
    webhook_password = webhook_password.strip()

    if not webhook_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="웹훅 패스워드를 입력해주세요."
        )

    # 패스워드 길이 검증 (최소 4자)
    if len(webhook_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="웹훅 패스워드는 최소 4자 이상이어야 합니다."
        )

    # DB에 웹훅 패스워드 저장
    try:
        success = update_webhook_password(current_user_id, webhook_password)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="웹훅 패스워드 저장 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 웹훅 패스워드 저장 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="웹훅 패스워드 저장 중 데이터베이스 오류가 발생했습니다."
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"웹훅 패스워드가 성공적으로 등록되었습니다.<br>트레이딩뷰 알림 메시지에 다음 정보를 포함하세요:<br><br><strong>admin_id:</strong> {current_user_id}<br><strong>webhook_password:</strong> {webhook_password}"
        }
    )


# ==========================================================
# 3. 웹훅 패스워드 해제 POST (/admin/security/release_webhook)
# ==========================================================

@router.post("/security/release_webhook", response_class=JSONResponse)
async def release_webhook_password(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    웹훅 패스워드를 해제합니다.
    """

    # 현재 패스워드 확인
    webhook_password = get_webhook_password(current_user_id)

    if not webhook_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해제할 웹훅 패스워드가 없습니다."
        )

    # DB에서 웹훅 패스워드 삭제
    try:
        success = delete_webhook_password(current_user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="웹훅 패스워드 해제 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 웹훅 패스워드 해제 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="웹훅 패스워드 해제 중 데이터베이스 오류가 발생했습니다."
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "웹훅 패스워드가 성공적으로 해제되었습니다."}
    )


# ==========================================================
# 4. 웹훅 주소 등록 POST (/admin/security/register_endpoint)
# ==========================================================

@router.post("/security/register_endpoint", response_class=JSONResponse)
async def register_webhook_endpoint(
    request: Request,
    webhook_endpoint: str = Form(...),
    current_user_id: str = Depends(require_admin_login)
):
    """
    웹훅 주소를 등록합니다.
    """

    # 입력값 검증
    webhook_endpoint = webhook_endpoint.strip()

    if not webhook_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="웹훅 주소를 입력해주세요."
        )

    # / 로 시작하도록 보장
    if not webhook_endpoint.startswith('/'):
        webhook_endpoint = '/' + webhook_endpoint

    # DB에 웹훅 주소 저장
    try:
        success = update_webhook_endpoint(current_user_id, webhook_endpoint)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="웹훅 주소 저장 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 웹훅 주소 저장 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="웹훅 주소 저장 중 데이터베이스 오류가 발생했습니다."
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"웹훅 주소가 성공적으로 등록되었습니다.<br>웹훅 주소: {webhook_endpoint}"
        }
    )


# ==========================================================
# 5. 웹훅 주소 해제 POST (/admin/security/release_endpoint)
# ==========================================================

@router.post("/security/release_endpoint", response_class=JSONResponse)
async def release_webhook_endpoint(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    웹훅 주소를 기본값(/webhook)으로 초기화합니다.
    """

    default_endpoint = "/webhook"

    # DB에 기본 웹훅 주소 저장
    try:
        success = update_webhook_endpoint(current_user_id, default_endpoint)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="웹훅 주소 초기화 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 웹훅 주소 초기화 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="웹훅 주소 초기화 중 데이터베이스 오류가 발생했습니다."
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "웹훅 주소가 기본값(/webhook)으로 초기화되었습니다."}
    )


# ==========================================================
# 6. 허용 IP 등록 POST (/admin/security/register_ips)
# ==========================================================

@router.post("/security/register_ips", response_class=JSONResponse)
async def register_allowed_ips(
    request: Request,
    allowed_ips: str = Form(...),
    current_user_id: str = Depends(require_admin_login)
):
    """
    허용 IP 목록을 등록하고 Caddyfile을 업데이트합니다.
    """
    import os
    import subprocess

    # 입력값 검증
    allowed_ips = allowed_ips.strip()

    if not allowed_ips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="허용 IP 주소를 입력해주세요."
        )

    # DB에 허용 IP 저장
    try:
        success = update_allowed_ips(current_user_id, allowed_ips)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="허용 IP 저장 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 허용 IP 저장 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="허용 IP 저장 중 데이터베이스 오류가 발생했습니다."
        )

    # Caddyfile 업데이트
    try:
        caddyfile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Caddyfile')
        ip_list = allowed_ips.replace(',', ' ').strip()

        caddyfile_content = f""":80 {{
    @whitelist {{
        remote_ip {ip_list}
    }}
    handle @whitelist {{
        reverse_proxy 127.0.0.1:8000
    }}
    respond 403
}}
"""

        with open(caddyfile_path, 'w', encoding='utf-8') as f:
            f.write(caddyfile_content)

        # Caddy 재시작 (Windows에서는 taskkill 사용)
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'caddy.exe'], check=False, capture_output=True)
            subprocess.Popen(['caddy.exe', 'run'], cwd=os.path.dirname(caddyfile_path))
        except Exception as restart_error:
            print(f"Caddy 재시작 중 오류: {restart_error}")

    except Exception as e:
        print(f"Caddyfile 업데이트 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Caddyfile 업데이트 중 오류가 발생했습니다: {str(e)}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "허용 IP가 성공적으로 등록되었습니다.<br>Caddyfile이 업데이트되었습니다."}
    )


# ==========================================================
# 5. 허용 IP 해제 POST (/admin/security/release_ips)
# ==========================================================

@router.post("/security/release_ips", response_class=JSONResponse)
async def release_allowed_ips(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    허용 IP 목록을 기본값(home_ip + 트레이딩뷰 기본 IP)으로 초기화하고 Caddyfile을 업데이트합니다.
    """
    import os
    import subprocess

    # home_ip 조회
    home_ip = get_home_ip(current_user_id)
    default_tradingview_ips = "52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7"

    # home_ip가 있으면 맨 앞에 추가
    if home_ip:
        default_ips = f"{home_ip}, {default_tradingview_ips}"
    else:
        default_ips = default_tradingview_ips

    # DB에 기본 IP 저장
    try:
        success = update_allowed_ips(current_user_id, default_ips)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="허용 IP 초기화 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 허용 IP 초기화 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="허용 IP 초기화 중 데이터베이스 오류가 발생했습니다."
        )

    # Caddyfile 업데이트
    try:
        caddyfile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Caddyfile')
        ip_list = default_ips.replace(',', ' ').strip()

        caddyfile_content = f""":80 {{
    @whitelist {{
        remote_ip {ip_list}
    }}
    handle @whitelist {{
        reverse_proxy 127.0.0.1:8000
    }}
    respond 403
}}
"""

        with open(caddyfile_path, 'w', encoding='utf-8') as f:
            f.write(caddyfile_content)

        # Caddy 재시작
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'caddy.exe'], check=False, capture_output=True)
            subprocess.Popen(['caddy.exe', 'run'], cwd=os.path.dirname(caddyfile_path))
        except Exception as restart_error:
            print(f"Caddy 재시작 중 오류: {restart_error}")

    except Exception as e:
        print(f"Caddyfile 업데이트 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Caddyfile 업데이트 중 오류가 발생했습니다: {str(e)}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "허용 IP가 기본값으로 초기화되었습니다.<br>Caddyfile이 업데이트되었습니다."}
    )
