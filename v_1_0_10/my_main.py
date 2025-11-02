# C:\Python\MY_PROJECT\v_1_0_8\my_main.py (최종 SQLite 및 세션 적용 버전)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse 
from starlette_session import SessionMiddleware 
import os 

# ✅ DB 초기화 함수 임포트 (my_db로 파일명 변경 반영)
from my_utilities.my_db import init_db 

# 라우터 임포트
from my_routers.my_index import get_server_info 
from my_routers.my_login import router as login_router 
from my_routers.my_logout import router as logout_router 
from my_routers.my_agreement import router as agreement_router 
from my_routers.my_intro import router as intro_router 
from my_routers.my_settings import router as settings_router
from my_routers.my_domain import router as domain_router
from my_routers.my_security import router as security_router
# 파일 존재 확인 유틸리티 임포트
from my_utilities.my_config_password import admin_config_check 

app = FastAPI()
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 1. 앱 시작 시 DB 초기화 및 세션 미들웨어 추가
# ==========================================================

# ✅ DB 초기화: 앱 시작 시 my_admin_config.db 파일을 확인 및 생성합니다.
init_db() 

# NOTE: SECRET_KEY는 반드시 안전하게 관리되는 임의의 긴 문자열이어야 합니다.
SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "your-very-secret-key-tH-ATS-is-long-and-random-for-security-key")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY, 
    # ✅ 세션 미들웨어 오류 수정 반영: 'session_cookie' 대신 'cookie_name' 사용
    cookie_name="my_admin_session", 
    max_age=3600, 
    same_site="lax" 
)

# ==========================================================
# 라우터 포함 (Include Router)
# ==========================================================

app.include_router(login_router, prefix="/admin") 
app.include_router(logout_router, prefix="/admin") 
app.include_router(agreement_router, prefix="/admin") 
app.include_router(intro_router, prefix="/admin") 
app.include_router(settings_router, prefix="/admin")
app.include_router(domain_router, prefix="/admin")
app.include_router(security_router, prefix="/admin")
# ==========================================================
# 관리자 기본 경로 조건부 리디렉션
# ==========================================================

@app.get("/admin")
async def admin_root_redirect():
    """
    /admin 경로 접속 시 DB에 비밀번호 해시가 설정되었는지 여부에 따라 리디렉션합니다.
    """
    if admin_config_check():
        # 비밀번호 해시 존재 (O) -> 일반 접속자 -> /admin/login
        return RedirectResponse(url="/admin/login", status_code=302)
    else:
        # 비밀번호 해시 없음 (X) -> 최초 접속자 -> /admin/first_login
        return RedirectResponse(url="/admin/first_login", status_code=302)

# ==========================================================
# 기존 루트 라우트 함수 
# ==========================================================

@app.get("/", name="root")
async def read_root(request: Request):
    
    context_data = get_server_info(request)
    context = {"request": request, **context_data}
    
    return templates.TemplateResponse("my_index.html", context)