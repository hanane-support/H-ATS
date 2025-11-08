# C:\Python\MY_PROJECT\v_1_0_9\my_utilities\my_reset.py (수정)

from fastapi import Request # ✅ Request 임포트 추가
from my_utilities.my_db import reset_all_admin_passwords 
# from .my_config_agreement import set_agreement_status # (삭제된 상태 유지)

# ==========================================================
# 전체 시스템 초기화 함수
# ==========================================================

# ✅ Request 객체를 받고, 세션을 초기화하는 로직 추가
def run_full_system_reset(request: Request) -> bool:
    """
    DB (관리자 ID/PW/약관), 세션을 통합 초기화 함수를 사용하여 초기 상태로 되돌립니다.
    """
    print("WARNING: Starting full system reset...")
    
    try:
        # 1. DB에 저장된 모든 관리자 계정 정보 (ID, PW 해시, is_agreed) 초기화
        reset_all_admin_passwords()
        
        # 2. 현재 세션 정보 초기화 (로그아웃 효과)
        if 'is_authenticated' in request.session:
            del request.session['is_authenticated']
        if 'user_id' in request.session:
            del request.session['user_id']
            
        print("Full system reset complete. All admin accounts and agreement states have been cleared.")
        return True
        
    except Exception as e:
        print(f"ERROR: Full system reset failed: {e}")
        return False