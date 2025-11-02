from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json, os
from pathlib import Path

from my_utilities.my_authorization import require_admin_login, set_no_cache_headers
from my_utilities.my_db import set_config_value, get_config_value

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

# Caddy 설정 파일 경로
CADDYFILE_PATH = Path("Caddyfile")  # 프로젝트 루트의 Caddyfile


@router.get("/domain")
async def get_domain_page(request: Request, current_user_id: str = Depends(require_admin_login)):
    # require_admin_login used via Depends so FastAPI injects Request and handles redirect
    # 읽기 전용으로 DB에서 저장된 도메인을 가져와 템플릿에 전달
    saved_domain = get_config_value('CADDY_DOMAIN')
    context = {"request": request, "current_page": "/admin/domain", "domain": saved_domain}
    response = templates.TemplateResponse("my_domain_security.html", context)
    return set_no_cache_headers(response)


def update_caddyfile(domain: str, port: int = 9000) -> None:
    """Caddyfile을 업데이트합니다."""
    caddyfile_content = f"""
{domain} {{
    reverse_proxy 127.0.0.1:{port}
}}
"""
    CADDYFILE_PATH.write_text(caddyfile_content.strip(), encoding='utf-8')


@router.post("/update-my_domain")
async def update_my_domain(request: Request, current_user_id: str = Depends(require_admin_login)):
    try:
        payload = await request.json()
        domain_name = payload.get('domain')
        if not domain_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="도메인 이름이 누락되었습니다.")

        # 1. DB에 도메인 저장
        if not set_config_value('CADDY_DOMAIN', domain_name):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="도메인을 DB에 저장하는데 실패했습니다."
            )

        # 2. Caddyfile 업데이트
        try:
            update_caddyfile(domain_name)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Caddyfile 업데이트 실패: {str(e)}"
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"도메인 '{domain_name}' 설정이 DB와 Caddyfile에 저장되었습니다."
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"도메인 설정 오류: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
