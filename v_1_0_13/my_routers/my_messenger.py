# C:\Python\MY_PROJECT\v_1_0_13\my_routers\my_messenger.py
# 메신저 설정 라우터 (디스코드)

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# 유틸리티 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers
from my_utilities.my_db import (
    get_discord_webhook_url,
    update_discord_webhook_url,
    delete_discord_webhook_url
)
from my_utilities.my_discord import (
    send_console_connection_success,
    send_console_connection_failure,
    send_console_disconnection
)

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 1. 메신저 설정 페이지 GET (/admin/messenger)
# ==========================================================

@router.get("/messenger", response_class=HTMLResponse)
async def get_messenger_page(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    메신저 설정 페이지(my_messenger.html)를 렌더링하고 캐시 방지 헤더를 설정합니다.
    """

    # DB에서 현재 사용자의 디스코드 Webhook URL 조회
    webhook_url = get_discord_webhook_url(current_user_id)

    context = {
        "request": request,
        "current_page": "/admin/messenger",
        "user_id": current_user_id,
        "discord_webhook_url": webhook_url if webhook_url else ""
    }

    response = templates.TemplateResponse("my_messenger.html", context)
    return set_no_cache_headers(response)


# ==========================================================
# 2. 디스코드 Webhook URL 등록 POST (/admin/messenger/register_discord)
# ==========================================================

@router.post("/messenger/register_discord", response_class=JSONResponse)
async def register_discord_webhook(
    request: Request,
    webhook_url: str = Form(...),
    current_user_id: str = Depends(require_admin_login)
):
    """
    디스코드 Webhook URL을 등록하고 메시지를 전송합니다.
    """

    # 입력값 검증
    webhook_url = webhook_url.strip()

    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="디스코드 Webhook URL을 입력해주세요."
        )

    # Webhook URL 유효성 검사 (기본적인 형식 체크)
    if not webhook_url.startswith("https://discord.com/api/webhooks/") and \
       not webhook_url.startswith("https://discordapp.com/api/webhooks/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바른 디스코드 Webhook URL 형식이 아닙니다."
        )

    # DB에 Webhook URL 저장
    try:
        success = update_discord_webhook_url(current_user_id, webhook_url)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="디스코드 Webhook URL 저장 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 디스코드 Webhook URL 저장 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="디스코드 Webhook URL 저장 중 데이터베이스 오류가 발생했습니다."
        )

    # 성공 메시지 전송
    result = send_console_connection_success(webhook_url)

    if result["success"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "디스코드 연동이 성공적으로 완료되었습니다.<br>성공 메시지를 확인해주세요.",
                "test_result": "success"
            }
        )
    else:
        # 메시지 전송 실패 시 DB에서 삭제
        delete_discord_webhook_url(current_user_id)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"디스코드 메시지 전송에 실패했습니다: {result['message']}"
        )


# ==========================================================
# 3. 디스코드 Webhook URL 해제 POST (/admin/messenger/release_discord)
# ==========================================================

@router.post("/messenger/release_discord", response_class=JSONResponse)
async def release_discord_webhook(
    request: Request,
    current_user_id: str = Depends(require_admin_login)
):
    """
    디스코드 Webhook URL을 해제합니다.
    """

    # 해제하기 전에 현재 URL 조회 (해제 메시지 전송을 위해)
    webhook_url = get_discord_webhook_url(current_user_id)

    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해제할 디스코드 Webhook URL이 없습니다."
        )

    # 해제 메시지 전송 (DB 삭제 전에 먼저 전송)
    send_result = send_console_disconnection(webhook_url)

    # DB에서 Webhook URL 삭제
    try:
        success = delete_discord_webhook_url(current_user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="디스코드 Webhook URL 해제 중 오류가 발생했습니다."
            )
    except Exception as e:
        print(f"DB 디스코드 Webhook URL 해제 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="디스코드 Webhook URL 해제 중 데이터베이스 오류가 발생했습니다."
        )

    # 메시지 전송 결과와 상관없이 해제는 성공으로 처리
    if send_result["success"]:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "디스코드 연동이 성공적으로 해제되었습니다.<br>해제 메시지를 확인해주세요."}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "디스코드 연동이 해제되었습니다.<br>(해제 메시지 전송 실패)"}
        )
