from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path

from my_utilities.my_authorization import require_admin_login, set_no_cache_headers

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

CONFIG_PATH = Path("my_admin_config.json")


@router.get("/security")
async def get_security_page(request: Request, current_user_id: str = Depends(require_admin_login)):
    context = {"request": request, "current_page": "/admin/security"}
    response = templates.TemplateResponse("my_security.html", context)
    return set_no_cache_headers(response)


@router.post("/update-my_security")
async def update_my_security(request: Request, current_user_id: str = Depends(require_admin_login)):
    try:
        payload = await request.json()
        action = payload.get('action')

        # Simple behavior: record that security was applied
        config = {}
        if CONFIG_PATH.exists():
            try:
                config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            except Exception:
                config = {}

        config['CADDY_SECURITY_APPLIED'] = True if action == 'apply' else config.get('CADDY_SECURITY_APPLIED', False)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding='utf-8')

        return JSONResponse(status_code=200, content={"success": True, "message": "보안(HTTPS) 적용 요청을 기록했습니다."})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
