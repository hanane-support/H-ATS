# my_utilities/my_delete_admin.py 파일 내용

from fastapi import Request
# DB 함수 임포트
from .my_db import delete_admin_id 

def delete_admin_account(request: Request) -> bool:
    """
    현재 세션의 관리자 계정을 DB에서 삭제하고 세션을 초기화합니다.
    
    Args:
        request: FastAPI Request 객체 (세션 정보 접근용).
    
    Returns:
        bool: 삭제 및 세션 초기화 성공 여부.
    """
    current_user_id = request.session.get('user_id')
    
    if not current_user_id:
        return False

    try:
        # 1. DB에서 관리자 ID 삭제 (my_db.py의 함수 사용)
        success = delete_admin_id(current_user_id)
        
        if not success:
            return False

        # 2. 세션 초기화 (로그아웃)
        request.session.pop('is_authenticated', None)
        request.session.pop('user_id', None)
        
        return True

    except Exception as e:
        print(f"delete_admin_account 오류: {e}")
        return False