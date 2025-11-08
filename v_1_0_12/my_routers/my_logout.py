# C:\Python\MY_PROJECT\v_1_0_7\my_routers\my_logout.py (ID 기반 세션 인증 버전)

from fastapi import APIRouter, Request 
from fastapi.responses import RedirectResponse
# ✅ JWT 유틸리티 임포트 제거: delete_auth_cookie 제거

# APIRouter 인스턴스 생성
router = APIRouter()

# ==========================================================
# 라우터 엔드포인트: 로그아웃 처리 POST 
# ==========================================================

@router.post("/logout")
async def process_logout(request: Request): 
    """
    사용자의 세션에 저장된 모든 인증 정보를 제거하고 로그인 페이지로 리디렉션합니다.
    """
    
    # 1. 세션에서 인증 정보 제거 (로그아웃 처리)
    # ★ 수정: 'is_authenticated'와 'user_id' 모두 삭제합니다.
    if 'is_authenticated' in request.session:
        del request.session['is_authenticated']
        
    if 'user_id' in request.session:
        # ✅ 세션에서 사용자 ID를 제거하는 것이 ID 기반 로그아웃의 핵심입니다.
        del request.session['user_id']
        
    # 2. 로그인 페이지로 리디렉션할 응답 객체 생성
    # 참고: 로그아웃 후 뒤로 가기 문제를 완전히 방지하려면 
    # my_authorization.py의 set_no_cache_headers를 응답에 적용할 수 있습니다.
    response = RedirectResponse(url="/admin/login", status_code=302)
    
    return response