# C:\Python\MY_PROJECT\v_1_0_9\my_utilities\my_config_password.py (최종 수정)

from my_utilities.my_db import get_admin_hash, get_unconfigured_admin_id, get_db_connection, create_admin_id # create_admin_id 임포트
from typing import Optional

# ==========================================================
# 1. 특정 ID의 비밀번호 해시 가져오기 (DB 쿼리)
# ==========================================================

def get_password_hash_by_id(admin_id: str) -> Optional[str]:
    """
    특정 관리자 ID의 비밀번호 해시 값을 가져옵니다.
    ID가 없거나 해시 값이 빈 문자열이면 None을 반환합니다.
    """
    # my_db.py의 get_admin_hash 함수를 직접 사용합니다.
    stored_hash = get_admin_hash(admin_id)
    
    # 해시 값이 존재하고 빈 문자열이 아니면 반환
    if stored_hash and stored_hash != '':
        return stored_hash
        
    return None 

# ==========================================================
# 2. 특정 ID의 비밀번호 해시 설정 (DB 쿼리)
# ==========================================================

def set_password_hash_by_id(admin_id: str, new_hash: str):
    """
    DB에 특정 관리자 ID의 새로운 비밀번호 해시 값을 저장합니다.
    - ID가 존재하면 업데이트합니다.
    - ★ ID가 존재하지 않으면, 이 함수는 사용되지 않는 것이 논리적입니다. 
    (최초 설정은 my_login.py에서 create_admin_id를 사용하고, 이 함수는 설정 변경 용도로만 사용)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 설정 변경(UPDATE) 용도로만 사용합니다.
    # 최초 설정 시에는 my_login.py에서 create_admin_id를 사용했습니다.
    cursor.execute("UPDATE admin SET password_hash = ? WHERE id = ?", (new_hash, admin_id))
    
    # NOTE: rowcount가 0이어도 오류를 발생시키지 않습니다. (ID가 없으면 아무 일도 안 함)
    conn.commit()
    conn.close()

# ==========================================================
# 3. 최초 설정 완료 여부 검사 (DB 레코드가 0개인지 확인)
# ==========================================================

def admin_config_check() -> bool:
    """
    DB에 최소한 하나의 관리자 레코드가 설정되었는지 확인합니다.
    - 레코드가 있으면 설정 완료 (True)
    - 레코드가 없으면 설정 필요 (False)
    """
    # ★ 수정: get_unconfigured_admin_id() 함수는 이제 레코드가 0개이면 None을 반환합니다.
    # 따라서 반환값이 'configured'와 같은 문자열이면 설정 완료 (True)입니다.
    
    # get_unconfigured_admin_id가 None을 반환하면 레코드 0개 = 설정 필요 (False)
    # get_unconfigured_admin_id가 문자열(예: 'configured')을 반환하면 설정 완료 (True)
    
    result = get_unconfigured_admin_id()
    
    # get_unconfigured_admin_id()가 None을 반환하면 설정되지 않은 것(False)입니다.
    return result is not None

# ==========================================================
# 4. setup_mode 검사 함수 (DB 기반)
# ==========================================================

def check_setup_mode() -> bool:
    """최초 설정 모드인지 (DB에 관리자 레코드가 없는지) 확인합니다."""
    # admin_config_check()의 반대입니다.
    return not admin_config_check()