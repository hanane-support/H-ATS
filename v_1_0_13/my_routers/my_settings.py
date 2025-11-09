# C:\Python\MY_PROJECT\v_1_0_9\my_routers\my_settings.py (콘솔 설정 라우터 - ID 변경 추가)

from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# 유틸리티 임포트
from my_utilities.my_authorization import require_admin_login, set_no_cache_headers 
from my_utilities.my_config_password import (
    get_password_hash_by_id,   
    set_password_hash_by_id    
)
from my_utilities.my_encrypt import verify_password, encrypt_password 

# ★ ID 변경 관련 유틸리티 함수 임포트 추가
from my_utilities.my_db import update_admin_id, check_admin_id_exists 

router = APIRouter()
templates = Jinja2Templates(directory="my_templates")

# ==========================================================
# 1. 콘솔 설정 페이지 GET (/admin/settings)
# ==========================================================

@router.get("/settings", response_class=HTMLResponse)
async def get_settings_page(
    request: Request,
    current_user_id: str = Depends(require_admin_login) 
):
    """
    콘솔 설정 페이지(my_settings.html)를 렌더링하고 캐시 방지 헤더를 설정합니다.
    """
    
    context = {
        "request": request, 
        "current_page": "/admin/settings", 
        "user_id": current_user_id
    }
    
    response = templates.TemplateResponse("my_settings.html", context) 
    return set_no_cache_headers(response)


# ==========================================================
# 2. 비밀번호 변경 POST (/admin/change_password)
# ==========================================================

@router.post("/change_password", response_class=JSONResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user_id: str = Depends(require_admin_login) 
):
    """
    현재 로그인된 사용자(current_user_id)의 비밀번호를 변경하고 DB에 저장합니다.
    """
    
    stored_hash = get_password_hash_by_id(current_user_id)
    
    if not stored_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="관리자 계정의 비밀번호 설정 상태가 올바르지 않습니다."
        )

    # 1. 현재 비밀번호 검증
    if not verify_password(current_password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="현재 비밀번호가 일치하지 않습니다."
        )

    # 2. 새 비밀번호 해시 및 저장
    try:
        new_hash = encrypt_password(new_password)
        set_password_hash_by_id(current_user_id, new_hash)
    except Exception as e:
        print(f"DB 업데이트 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="비밀번호 변경 중 데이터베이스 오류가 발생했습니다."
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"message": f"사용자 '{current_user_id}'님의 비밀번호가 성공적으로 변경되었습니다."}
    )

# ==========================================================
# 3. 아이디 변경 POST (/admin/change_id) - 새로 추가된 로직
# ==========================================================

@router.post("/change_id", response_class=JSONResponse)
async def change_admin_id(
    request: Request,
    current_id: str = Form(...),
    new_id: str = Form(...),
    password: str = Form(...), # ID 변경 시에도 비밀번호를 받아 보안을 강화합니다.
    current_user_id: str = Depends(require_admin_login) 
):
    """
    현재 로그인된 사용자(current_user_id)의 ID를 새 ID로 변경하고 세션을 업데이트합니다.
    """
    
    # 0. 입력 ID 유효성 및 일치 검사
    current_id = current_id.strip()
    new_id = new_id.strip()

    if current_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="현재 ID가 세션 정보와 일치하지 않습니다. 다시 로그인해주세요."
        )

    # 1. 새 ID 중복 및 유효성 검증
    if not new_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="새 ID를 입력해주세요."
        )
    
    # DB에 새 ID가 이미 존재하는지 확인
    if check_admin_id_exists(new_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="새로 지정하려는 ID는 이미 사용 중입니다."
        )

    # 2. 현재 비밀번호 검증 (보안 검증)
    stored_hash = get_password_hash_by_id(current_user_id)
    
    if not stored_hash or not verify_password(password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="비밀번호가 일치하지 않아 ID를 변경할 수 없습니다."
        )

    # 3. DB에서 ID 업데이트
    try:
        # my_db.py의 update_admin_id 함수를 호출하여 ID를 변경합니다.
        success = update_admin_id(current_id, new_id)
        
        if not success:
             raise Exception("DB에서 ID 업데이트에 실패했습니다.")
        
    except Exception as e:
        print(f"DB ID 업데이트 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="아이디 변경 중 데이터베이스 오류가 발생했습니다."
        )

    # 4. 세션 업데이트 및 응답
    
    # 세션에 저장된 user_id를 새 ID로 업데이트합니다.
    request.session['user_id'] = new_id
    
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"message": f"아이디가 성공적으로 '{new_id}'로 변경되었습니다. 세션이 업데이트되었습니다."}
    )