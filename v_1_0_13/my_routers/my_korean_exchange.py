# C:\Python\MY_PROJECT\v_1_0_13\my_routers\my_korean_exchange.py
# 국내 거래소 설정 라우터 (업비트)

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# 유틸리티 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers
from my_utilities.my_db import (
    get_upbit_api_keys,
    update_upbit_api_keys,
    delete_upbit_api_keys,
    get_discord_webhook_url
)
from my_utilities.my_discord import (
    send_upbit_api_registered,
    send_upbit_api_released
)

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 1. 국내 거래소 설정 페이지 GET (/admin/korean_exchange)
# ==========================================================

@router.get("/korean_exchange", response_class=HTMLResponse)
async def get_korean_exchange_page(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    국내 거래소 설정 페이지(my_korean_exchange.html)를 렌더링하고 캐시 방지 헤더를 설정합니다.
    """

    # DB에서 현재 사용자의 업비트 API 키 조회
    api_key, secret_key = get_upbit_api_keys(current_user_id)

    context = {
        "request": request,
        "current_page": "/admin/korean_exchange",
        "user_id": current_user_id,
        "upbit_api_key": api_key if api_key else "",
        "upbit_secret_key": secret_key if secret_key else ""
    }

    response = templates.TemplateResponse("my_korean_exchange.html", context)
    return set_no_cache_headers(response)


# ==========================================================
# 2. 업비트 API 키 등록 POST (/admin/korean_exchange/register_upbit)
# ==========================================================

@router.post("/korean_exchange/register_upbit", response_class=JSONResponse)
async def register_upbit_api(
    request: Request,
    api_key: str = Form(...),
    secret_key: str = Form(...),
    current_user_id: str = Depends(require_admin_login)
):
    """
    업비트 API 키와 시크릿 키를 등록하고 디스코드로 알림을 전송합니다.
    """

    # 입력값 검증
    api_key = api_key.strip()
    secret_key = secret_key.strip()

    if not api_key or not secret_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="업비트 API 키와 시크릿 키를 모두 입력해주세요."
        )

    # DB에 API 키 저장
    try:
        success = update_upbit_api_keys(current_user_id, api_key, secret_key)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="업비트 API 키 저장 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 업비트 API 키 저장 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="업비트 API 키 저장 중 데이터베이스 오류가 발생했습니다."
        )

    # 디스코드 알림 전송 (선택적)
    webhook_url = get_discord_webhook_url(current_user_id)

    if webhook_url:
        result = send_upbit_api_registered(webhook_url)

        if result["success"]:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "업비트 API 키가 성공적으로 등록되었습니다.<br>디스코드 알림이 전송되었습니다.",
                    "discord_notification": "success"
                }
            )
        else:
            # 디스코드 전송 실패해도 등록은 성공으로 처리
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "업비트 API 키가 성공적으로 등록되었습니다.<br>(디스코드 알림 전송 실패)",
                    "discord_notification": "failed"
                }
            )
    else:
        # 디스코드 Webhook이 설정되지 않은 경우
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "업비트 API 키가 성공적으로 등록되었습니다.",
                "discord_notification": "not_configured"
            }
        )


# ==========================================================
# 3. 업비트 API 키 해제 POST (/admin/korean_exchange/release_upbit)
# ==========================================================

@router.post("/korean_exchange/release_upbit", response_class=JSONResponse)
async def release_upbit_api(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    업비트 API 키를 해제하고 디스코드로 알림을 전송합니다.
    """

    # 해제하기 전에 현재 키 존재 여부 확인
    api_key, secret_key = get_upbit_api_keys(current_user_id)

    if not api_key and not secret_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해제할 업비트 API 키가 없습니다."
        )

    # 디스코드 알림 전송 (DB 삭제 전에 먼저 전송)
    webhook_url = get_discord_webhook_url(current_user_id)
    discord_sent = False

    if webhook_url:
        result = send_upbit_api_released(webhook_url)
        discord_sent = result["success"]

    # DB에서 API 키 삭제
    try:
        success = delete_upbit_api_keys(current_user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="업비트 API 키 해제 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 업비트 API 키 해제 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="업비트 API 키 해제 중 데이터베이스 오류가 발생했습니다."
        )

    # 응답 메시지 생성
    if webhook_url:
        if discord_sent:
            message = "업비트 API 키가 성공적으로 해제되었습니다.<br>디스코드 알림이 전송되었습니다."
        else:
            message = "업비트 API 키가 성공적으로 해제되었습니다.<br>(디스코드 알림 전송 실패)"
    else:
        message = "업비트 API 키가 성공적으로 해제되었습니다."

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": message}
    )
