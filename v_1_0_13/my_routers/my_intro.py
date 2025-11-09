# C:\Python\MY_PROJECT\v_1_0_8\my_routers\my_intro.py

from fastapi import APIRouter, Request, Depends, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# 세션 인증 및 캐시 방지 유틸리티 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers 

# APIRouter 인스턴스 생성
router = APIRouter()

# 템플릿 디렉토리 설정 
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 라우터 엔드포인트: 소개 페이지 GET (/admin/intro)
# ==========================================================

@router.get("/intro", response_class=HTMLResponse)
async def get_intro_page(
    request: Request,
    # ✅ 세션 인증 의존성 적용: 인증 실패 시 로그인 페이지로 리디렉션됩니다.
    _: None = Depends(require_admin_login) 
):
    """
    소개 페이지(my_intro.html)를 렌더링하고 캐시 방지 헤더를 설정합니다.
    """
    
    context = {
        "request": request, 
        "current_page": "/admin/intro" # 사이드바 활성화를 위한 현재 경로
    }
    
    # 1. 템플릿 응답을 생성합니다.
    response = templates.TemplateResponse("my_intro.html", context)
    
    # 2. ✅ 캐시 방지 헤더를 응답에 추가하여 뒤로 가기/앞으로 가기 문제 해결
    return set_no_cache_headers(response)