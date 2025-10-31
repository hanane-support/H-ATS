# C:\Python\MY_PROJECT\v_1_0_9\my_utilities\my_db.py

import sqlite3
import os
from typing import Optional, Tuple

# DB 파일 경로 설정
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'admin_config.db')

def get_db_connection():
    """SQLite DB 연결 객체를 반환합니다."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    """DB 파일이 없거나 테이블이 없으면 생성하고, 필요한 컬럼을 추가합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 'admin' 테이블 생성
    # is_agreed 컬럼 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_agreed INTEGER DEFAULT 0 NOT NULL
        )
    """)
    
    # [방어 로직] 이미 테이블이 있지만 is_agreed 컬럼이 없는 경우를 대비
    try:
        cursor.execute("SELECT is_agreed FROM admin LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'is_agreed'가 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE admin ADD COLUMN is_agreed INTEGER DEFAULT 0 NOT NULL")
        
    conn.commit()
    conn.close()

# -------------------------------------------------------------
# ID 관리 함수
# -------------------------------------------------------------

def get_admin_hash(admin_id: str) -> Optional[str]:
    """주어진 ID의 저장된 비밀번호 해시 값을 조회합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM admin WHERE id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return None

def create_admin_id(admin_id: str, password_hash: str) -> bool:
    """
    새로운 관리자 ID와 비밀번호 해시를 DB에 삽입합니다.
    ID가 이미 존재하면 업데이트합니다. (UPSERT 역할)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO admin (id, password_hash) VALUES (?, ?)",
            (admin_id, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()

def check_admin_id_exists(admin_id: str) -> bool:
    """
    주어진 ID가 'admin' 테이블에 이미 존재하는지 확인합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) FROM admin WHERE id = ?", (admin_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def update_admin_id(old_id: str, new_id: str) -> bool:
    """
    기존 ID를 새 ID로 변경합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE admin SET id = ? WHERE id = ?",
            (new_id, old_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError as e:
        print(f"ID 변경 실패: 새 ID({new_id})가 이미 존재합니다. {e}")
        return False
    except sqlite3.Error as e:
        print(f"DB ID 업데이트 오류: {e}")
        return False
    finally:
        conn.close()

def delete_admin_id(admin_id: str) -> bool:
    """
    주어진 ID를 'admin' 테이블에서 삭제합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM admin WHERE id = ?",
            (admin_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB ID 삭제 오류: {e}")
        return False
    finally:
        conn.close()

def get_unconfigured_admin_id() -> Optional[str]:
    """
    최초 설정 여부만 확인합니다. 테이블에 레코드가 하나도 없으면 None, 있으면 'configured' 반환.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) FROM admin")
    count = cursor.fetchone()[0]
    conn.close()
    
    if count == 0:
        return None
    
    return 'configured'

def reset_all_admin_passwords():
    """
    'admin' 테이블의 모든 레코드를 삭제하여 최초 설정 상태로 되돌립니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin")
    conn.commit()
    conn.close()
    
# -------------------------------------------------------------
# 이용 약관 동의 상태 관리 함수 (DB 기반)
# -------------------------------------------------------------

def get_user_agreement_status(admin_id: str) -> bool:
    """
    주어진 관리자 ID의 이용 약관 동의 상태(is_agreed)를 DB에서 조회합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_agreed FROM admin WHERE id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()
    
    # 0/1 값을 bool로 변환하여 반환
    if result:
        return bool(result[0])
    return False

def set_user_agreement_status(admin_id: str, is_agreed: bool) -> bool:
    """
    주어진 관리자 ID의 이용 약관 동의 상태(is_agreed)를 DB에 저장합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Python bool을 SQLite INTEGER (0 또는 1)로 변환
    status_int = 1 if is_agreed else 0
    
    try:
        # 해당 ID의 is_agreed 컬럼을 업데이트
        cursor.execute(
            "UPDATE admin SET is_agreed = ? WHERE id = ?",
            (status_int, admin_id)
        )
        conn.commit()
        # 업데이트된 행이 1개 이상인지 확인
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB 약관 상태 업데이트 오류: {e}")
        return False
    finally:
        conn.close()