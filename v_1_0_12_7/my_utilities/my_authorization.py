# C:\Python\MY_PROJECT\v_1_0_8\my_utilities\my_authorization.py (ID 기반 세션 인증)

import os
from fastapi import Request, Depends, HTTPException, status, Response 
from fastapi.responses import RedirectResponse
from typing import Optional

# my_config_password의 유틸리티 함수 임포트 (기존 내용 유지)
from my_utilities.my_config_password import admin_config_check, check_setup_mode 


# ==========================================================
# 1. 인증 확인 및 ID 반환 함수 (세션 'user_id' 기반으로 변경)
# ==========================================================

def get_current_admin_user(request: Request) -> str:
    """
    Dependency Injection: 세션에 저장된 인증된 사용자 ID를 반환합니다.
    ID가 없으면 로그인 페이지로 강제 리디렉트합니다.
    """
    # ★ 수정: 세션에서 'user_id' 키의 값을 확인합니다.
    user_id = request.session.get('user_id')
    
    # ID가 없거나 값이 비어있다면 인증 실패로 간주
    if not user_id: 
        # 로그인되지 않았다면 HTTP 302와 Location 헤더를 이용해 리다이렉션
        # FastAPI에서 Depends를 통해 리다이렉션하려면 HTTPException을 사용해야 합니다.
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, # 302: Found (임시 리다이렉션)
            detail="Not authenticated, redirecting to login page.",
            headers={"Location": "/admin/login"}
        )
    
    # 인증 성공 시, 해당 ID를 반환하여 라우트 함수에서 사용 가능하도록 합니다.
    return user_id

# 이전 이름 require_admin_login의 역할을 대체하지만, 반환 값이 ID이므로 이름을 변경하는 것이 좋습니다.
# 만약 기존 이름 그대로 사용하고 싶다면:
require_admin_login = get_current_admin_user


# ==========================================================
# 2. 캐시 방지 헤더 설정 함수 (유지)
# ==========================================================

def set_no_cache_headers(response: Response) -> Response:
    """
    응답 헤더에 브라우저 캐시를 방지하는 설정을 추가합니다. 
    (로그아웃 후 뒤로 가기 문제 해결의 핵심)
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ==========================================================
# 3. 로그인/최초 설정 검사 및 리디렉션 의존성 함수 (정의 명확화)
# ==========================================================

async def redirect_login(request: Request):
    """
    로그인 페이지 또는 최초 설정 페이지(/admin) 접속 시, 
    최초 설정 완료 여부에 따라 적절한 페이지로 리다이렉션합니다.
    """
    # 1. 이미 로그인 되어 있는지 확인 (세션에 user_id가 있는지 확인)
    # 로그인 되어 있다면 무조건 agreement 페이지로 리다이렉션 (로그인 페이지 접근 차단)
    if request.session.get('user_id'):
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Already logged in, redirecting to admin dashboard.",
            headers={"Location": "/admin/agreement"}
        )

    # 2. 최초 설정이 완료되었는지 확인
    if admin_config_check():
        # 설정 완료 (O) -> 일반 로그인 페이지로 가도록 통과
        return None # 통과
    else:
        # 설정 필요 (X) -> 최초 설정 페이지로 리다이렉션
        # first_login 페이지로 가도록 통과
        return None # 통과