# C:\Python\MY_PROJECT\v_1_0_9\my_routers\my_agreement.py

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# DB 유틸리티 함수 임포트
from my_utilities.my_db import get_user_agreement_status, set_user_agreement_status 

# 사용자 ID를 가져오는 함수 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers, get_current_admin_user 

# APIRouter 인스턴스 생성
router = APIRouter()

# 템플릿 디렉토리 설정 
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 라우터 엔드포인트: 약관 페이지 GET
# ==========================================================

@router.get("/agreement", response_class=HTMLResponse)
async def get_agreement_page(
    request: Request,
    # 세션에서 현재 로그인된 사용자의 ID를 가져옵니다.
    user_id: str = Depends(get_current_admin_user), 
    # 인증 확인
    _: None = Depends(require_admin_login) 
):
    """
    약관 동의 페이지(my_agreement.html)를 렌더링하고 현재 사용자의 DB 동의 상태를 전달합니다.
    """
    # 1. 현재 약관 동의 상태를 DB에서 사용자 ID 기반으로 읽어옵니다.
    is_agreement_checked = get_user_agreement_status(user_id)
    
    context = {
        "request": request, 
        "is_agreement_checked": is_agreement_checked, 
        "current_page": "/admin/agreement" 
    }
    
    # 2. 템플릿 응답을 생성하고 캐시 방지 헤더를 추가합니다.
    response = templates.TemplateResponse("my_agreement.html", context)
    return set_no_cache_headers(response) 

# ==========================================================
# 라우터 엔드포인트: 약관 동의 처리 POST
# ==========================================================

@router.post("/agreement_confirm")
async def process_agreement_confirm(
    # 세션에서 현재 로그인된 사용자의 ID를 가져옵니다.
    user_id: str = Depends(get_current_admin_user),
    # 인증 확인
    _: None = Depends(require_admin_login) 
):
    """
    약관 동의 상태를 DB에 사용자별로 True로 설정합니다.
    """
    try:
        # 1. 약관 동의 상태를 DB에 사용자 ID 기반으로 True로 저장
        success = set_user_agreement_status(user_id, True)
        
        if not success:
            raise Exception("DB 업데이트 실패 또는 사용자 ID를 찾을 수 없음")
        
        return JSONResponse(content={"message": "약관 동의 상태가 성공적으로 저장되었습니다."}, status_code=status.HTTP_200_OK)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"약관 동의 저장 중 오류 발생: {e}"
        )

# ==========================================================
# 라우터 엔드포인트: 약관 철회 처리 POST
# ==========================================================

@router.post("/agreement_revoke")
async def process_agreement_revoke(
    # 세션에서 현재 로그인된 사용자의 ID를 가져옵니다.
    user_id: str = Depends(get_current_admin_user),
    # 인증 확인
    _: None = Depends(require_admin_login) 
):
    """
    약관 동의 상태를 DB에 사용자별로 False로 설정합니다.
    """
    try:
        # 1. 약관 동의 상태를 DB에 사용자 ID 기반으로 False로 저장
        success = set_user_agreement_status(user_id, False)
        
        if not success:
            raise Exception("DB 업데이트 실패 또는 사용자 ID를 찾을 수 없음")
        
        return JSONResponse(content={"message": "약관 동의가 성공적으로 철회되었습니다."}, status_code=status.HTTP_200_OK)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"약관 동의 철회 중 오류 발생: {e}"
        )