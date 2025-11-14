# C:\Python\MY_PROJECT\v_1_0_9\my_routers\my_login.py (최종 수정 - delete_admin.py 분리)

from fastapi import APIRouter, Request, Depends, Form, status, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse 

from my_utilities.my_encrypt import encrypt_password, verify_password 

# ID 기반 함수 임포트
from my_utilities.my_config_password import (
    get_password_hash_by_id,  
    check_setup_mode          
)
# DB 관련 함수 임포트 (delete_admin_id 제거)
from my_utilities.my_db import create_admin_id, check_admin_id_exists, update_admin_ip
from my_utilities.my_authorization import redirect_login, set_no_cache_headers 
# ★ 통합 초기화 함수 임포트
from my_utilities.my_reset import run_full_system_reset 
# ★ 새 관리자 삭제 유틸리티 임포트
from my_utilities.my_delete_admin import delete_admin_account 


# APIRouter 인스턴스 생성
router = APIRouter()
templates = Jinja2Templates(directory="my_templates")


# ==========================================================
# 1. 일반 로그인 페이지 GET
# ... (내용 변경 없음) ...
# ==========================================================
@router.get("/login", response_class=HTMLResponse)
async def get_general_login_page(
    request: Request,
    _: None = Depends(redirect_login), 
    error: str = None 
):
    """일반 접속자가 사용하는 로그인 페이지를 보여줍니다."""
    is_setup_mode = check_setup_mode()
    
    context = {
        "request": request, 
        "is_setup_mode": is_setup_mode,
        "error": error,
        "form_action": "/admin/login" 
    }
    response = templates.TemplateResponse("my_login.html", context)
    return set_no_cache_headers(response)


# ==========================================================
# 2. 최초 설정 페이지 GET
# ... (내용 변경 없음) ...
# ==========================================================
@router.get("/first_login", response_class=HTMLResponse)
async def get_setup_login_page(
    request: Request,
    _: None = Depends(redirect_login), 
    is_setup_mode: bool = Depends(check_setup_mode), 
    error: str = None 
):
    """최초 접속자가 사용하는 비밀번호 등록 페이지를 보여줍니다."""
    
    context = {
        "request": request, 
        "is_setup_mode": is_setup_mode,
        "initial_id": None, 
        "error": error,
        "form_action": "/admin/login"
    }
    response = templates.TemplateResponse("my_login.html", context)
    return set_no_cache_headers(response)


# ==========================================================
# 3. 로그인 처리 POST
# ... (내용 변경 없음) ...
# ==========================================================
@router.post("/login")
async def process_login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...)
): 
    
    input_id = username.strip()
    input_password = password
    
    if not input_id or not input_password:
        error_message = "ID와 비밀번호를 모두 입력해주세요."
        redirect_path = "/admin/first_login" if check_setup_mode() else "/admin/login"
        return RedirectResponse(url=f"{redirect_path}?error={error_message}", status_code=302)

    is_setup_mode = check_setup_mode()
    
    # ... (최초 설정 및 일반 로그인 로직은 변경 없음) ...
    if is_setup_mode:
        new_hash = encrypt_password(input_password)

        success = create_admin_id(input_id, new_hash)

        if not success:
            error_message = "최초 설정 중 DB 오류가 발생했습니다."
            return RedirectResponse(url=f"/admin/first_login?error={error_message}", status_code=302)

        # 최초 설정 시 클라이언트 IP를 관리자 IP로 자동 등록
        # 리버스 프록시를 통한 접속인 경우 X-Forwarded-For 헤더에서 실제 IP 가져오기
        client_ip = request.headers.get("X-Forwarded-For")
        if client_ip:
            # X-Forwarded-For에 여러 IP가 있을 수 있으므로 첫 번째 IP 사용
            client_ip = client_ip.split(",")[0].strip()
        else:
            # X-Forwarded-For 헤더가 없으면 request.client.host 사용
            client_ip = request.client.host if request.client else None

        if client_ip:
            update_admin_ip(input_id, client_ip)
            print(f"✅ 관리자 IP({client_ip})가 관리자({input_id})에게 자동 등록되었습니다.")

        authenticated_id = input_id
        
    else:
        stored_hash = get_password_hash_by_id(input_id)
        
        if stored_hash and verify_password(input_password, stored_hash):
            authenticated_id = input_id
        else:
            error_message = "ID 또는 비밀번호가 올바르지 않습니다."
            return RedirectResponse(url=f"/admin/login?error={error_message}", status_code=302)


    # 4. 로그인 성공 (세션 저장)
    request.session['is_authenticated'] = True 
    request.session['user_id'] = authenticated_id 
    
    response = RedirectResponse(url="/admin/agreement", status_code=302)
    
    return response

# ==========================================================
# 4. 관리자 설정 전체 초기화 POST
# ... (내용 변경 없음) ...
# ==========================================================
@router.post("/reset_config")
async def process_config_reset(request: Request):
    """
    DB, 설정 파일 및 세션을 통합 초기화 함수를 사용하여 초기 상태로 되돌립니다.
    """
    
    try:
        if run_full_system_reset(request):
            # 3. 성공 응답
            return JSONResponse(
                status_code=status.HTTP_200_OK, 
                content={"message": "관리자 설정이 초기화되어 최초 접속 상태로 돌아갑니다."}
            )
        else:
            # run_full_system_reset 내에서 실패 (DB 또는 파일 문제)
            raise Exception("통합 초기화 중 실패: 상세 내용은 서버 로그를 확인하세요.")
            
    except Exception as e:
        # 4. 오류 응답
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"설정 초기화 중 오류 발생: {e}"
        )

# ==========================================================
# 5. 새 관리자 등록 페이지 GET (/admin/new_register)
# ... (내용 변경 없음) ...
# ==========================================================

@router.get("/new_register", response_class=HTMLResponse)
async def get_new_register_page(
    request: Request,
    _: None = Depends(redirect_login),
    error: str = None 
):
    """
    일반 로그인 모드에서 새 관리자 등록 페이지를 렌더링합니다.
    """
    context = {
        "request": request, 
        "error": error,
        "is_setup_mode": True,  # 등록 UI 활용을 위해 True 설정
        "form_action": "/admin/new_register" # 폼 액션 설정
    }
    
    response = templates.TemplateResponse("my_login.html", context) 
    return set_no_cache_headers(response)


# ==========================================================
# 6. 새 관리자 등록 처리 POST (/admin/new_register)
# ... (내용 변경 없음) ...
# ==========================================================

@router.post("/new_register")
async def process_new_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """
    새로운 관리자 ID를 DB에 등록하고 즉시 로그인 처리 후 리디렉션합니다.
    """
    input_id = username.strip()
    input_password = password
    
    # 1. ID 유효성 및 중복 검사
    if not input_id or not input_password:
        error_message = "ID와 비밀번호를 모두 입력해주세요."
        return RedirectResponse(url=f"/admin/new_register?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)

    if check_admin_id_exists(input_id):
        # HTML 렌더링을 위해 | safe 필터 적용을 가정하고 <br> 사용
        error_message = "이미 존재하는 관리자 ID입니다.<br>다른 ID를 사용해주세요."
        return RedirectResponse(url=f"/admin/new_register?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)

    # 2. 비밀번호 해시 및 저장
    try:
        password_hash = encrypt_password(input_password)
        
        success = create_admin_id(input_id, password_hash)
        
        if not success:
            raise Exception("DB 저장에 실패했습니다.")

    except Exception as e:
        print(f"새 관리자 등록 DB 오류: {e}")
        error_message = "관리자 등록 중 데이터베이스 오류가 발생했습니다."
        return RedirectResponse(url=f"/admin/new_register?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)

    # 3. 등록 성공 후 즉시 로그인 처리 및 리디렉션
    request.session['is_authenticated'] = True 
    request.session['user_id'] = input_id 
    
    response = RedirectResponse(url="/admin/agreement", status_code=status.HTTP_303_SEE_OTHER)
    
    return set_no_cache_headers(response)


# ==========================================================
# 7. 현재 관리자 삭제 및 로그아웃 POST (수정)
# ==========================================================
@router.post("/delete_admin")
async def delete_current_admin(request: Request):
    """
    현재 로그인된 관리자 계정을 삭제하고 로그아웃 처리 후 성공 메시지를 반환합니다.
    """
    current_user_id = request.session.get('user_id')
    
    if not current_user_id:
        # 로그인되지 않은 경우
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "인증 정보가 없습니다. 다시 로그인해주세요."}
        )
        
    try:
        # ★ 분리된 유틸리티 함수 호출
        success = delete_admin_account(request)
        
        if not success:
            raise Exception("관리자 계정 삭제 실패 (DB 오류 또는 ID 없음)")

        # 성공 응답 (JS에서 로그인 페이지로 리디렉션 처리)
        return JSONResponse(
            status_code=status.HTTP_200_OK, 
            content={"message": f"관리자 '{current_user_id}'가 성공적으로 삭제되었습니다. 로그인 페이지로 이동합니다."}
        )

    except Exception as e:
        print(f"관리자 삭제 중 오류 발생: {e}")
        # 오류 응답
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"관리자 삭제 중 오류 발생: {e}"
        )