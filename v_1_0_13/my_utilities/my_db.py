import sqlite3
import os
from typing import Optional, Tuple, Dict, Any

# DB 파일 경로 설정
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'my_admin_config.db')

def get_db_connection():
    """SQLite DB 연결 객체를 반환합니다."""
    # check_same_thread=False는 FastAPI/Uvicorn 환경에서 필요합니다.
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row # 결과를 딕셔너리처럼 접근 가능하도록 설정
    return conn

def init_db():
    """DB 파일이 없거나 테이블이 없으면 생성하고, 필요한 컬럼을 추가합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 'admin' 테이블 생성 및 컬럼 추가 (기존 로직 유지)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_agreed INTEGER DEFAULT 0 NOT NULL,
            home_ip TEXT
        )
    """)

    # [방어 로직] 이미 테이블이 있지만 is_agreed 컬럼이 없는 경우를 대비
    try:
        cursor.execute("SELECT is_agreed FROM admin LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'is_agreed'가 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE admin ADD COLUMN is_agreed INTEGER DEFAULT 0 NOT NULL")

    # [방어 로직] 이미 테이블이 있지만 home_ip 컬럼이 없는 경우를 대비
    try:
        cursor.execute("SELECT home_ip FROM admin LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'home_ip'가 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE admin ADD COLUMN home_ip TEXT")
        
    # ==========================================================
    # 🟢 [신규] 'domain_security' 테이블 생성
    # ==========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS domain_security (
            admin_id TEXT PRIMARY KEY,
            domain_name TEXT,
            email TEXT,
            ssl_status TEXT DEFAULT 'HTTP' NOT NULL,
            FOREIGN KEY (admin_id) REFERENCES admin (id)
        )
    """)

    # [방어 로직] 이미 테이블이 있지만 email 컬럼이 없는 경우를 대비
    try:
        cursor.execute("SELECT email FROM domain_security LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'email'이 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE domain_security ADD COLUMN email TEXT")
    # ----------------------------------------------------------

    # ==========================================================
    # 🟢 [신규] 'messenger' 테이블 생성
    # ==========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messenger (
            admin_id TEXT PRIMARY KEY,
            discord_webhook_url TEXT,
            FOREIGN KEY (admin_id) REFERENCES admin (id)
        )
    """)
    # ----------------------------------------------------------

    # ==========================================================
    # 🟢 [신규] 'korean_exchange' 테이블 생성
    # ==========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS korean_exchange (
            admin_id TEXT PRIMARY KEY,
            upbit_api_key TEXT,
            upbit_secret_key TEXT,
            FOREIGN KEY (admin_id) REFERENCES admin (id)
        )
    """)
    # ----------------------------------------------------------

    # ==========================================================
    # 🟢 [신규] 'webhook_config' 테이블 생성
    # ==========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_config (
            admin_id TEXT PRIMARY KEY,
            webhook_password TEXT,
            webhook_endpoint TEXT DEFAULT '/webhook',
            allowed_ips TEXT DEFAULT '52.89.214.238,34.212.75.30,54.218.53.128,52.32.178.7',
            FOREIGN KEY (admin_id) REFERENCES admin (id)
        )
    """)

    # [방어 로직] webhook_endpoint 컬럼 추가
    try:
        cursor.execute("SELECT webhook_endpoint FROM webhook_config LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'webhook_endpoint'가 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE webhook_config ADD COLUMN webhook_endpoint TEXT DEFAULT '/webhook'")

    # [방어 로직] allowed_ips 컬럼 추가
    try:
        cursor.execute("SELECT allowed_ips FROM webhook_config LIMIT 1")
    except sqlite3.OperationalError:
        print("컬럼 'allowed_ips'가 없어 ALTER TABLE로 추가합니다.")
        cursor.execute("ALTER TABLE webhook_config ADD COLUMN allowed_ips TEXT DEFAULT '52.89.214.238,34.212.75.30,54.218.53.128,52.32.178.7'")
    # ----------------------------------------------------------

    conn.commit()
    conn.close()

# -------------------------------------------------------------
# ID 관리 함수 (기존 로직 유지)
# -------------------------------------------------------------

def get_admin_hash(admin_id: str) -> Optional[str]:
    """주어진 ID의 저장된 비밀번호 해시 값을 조회합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM admin WHERE id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result['password_hash']
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
# 이용 약관 동의 상태 관리 함수 (기존 로직 유지)
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
        return bool(result['is_agreed'])
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

# -------------------------------------------------------------
# 🟢 [신규] 도메인 및 보안 상태 관리 함수
# -------------------------------------------------------------

def get_domain_security_config(admin_id: str) -> Dict[str, Any]:
    """
    주어진 관리자 ID에 연결된 도메인, 이메일 및 보안 정보를 DB에서 조회합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT domain_name, email, ssl_status FROM domain_security WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "domain_name": result['domain_name'] if result['domain_name'] else "없음",
            "email": result['email'] if result['email'] else "",
            "security_status": result['ssl_status'],
        }

    # 설정되지 않은 경우 기본값 반환
    return {
        "domain_name": "없음",
        "email": "",
        "security_status": "HTTP",
    }


def update_domain_security_config(admin_id: str, domain_name: str, ssl_status: str, email: str = "") -> bool:
    """
    주어진 관리자 ID의 도메인, 이메일 및 보안 정보를 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO domain_security (admin_id, domain_name, email, ssl_status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                domain_name = excluded.domain_name,
                email = excluded.email,
                ssl_status = excluded.ssl_status
            """,
            (admin_id, domain_name, email, ssl_status)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 도메인 정보 업데이트 오류: {e}")
        return False
    finally:
        conn.close()

def delete_domain_security_config(admin_id: str) -> bool:
    """
    주어진 관리자 ID의 도메인 및 보안 정보를 삭제합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM domain_security WHERE admin_id = ?",
            (admin_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB 도메인 정보 삭제 오류: {e}")
        return False
    finally:
        conn.close()

# -------------------------------------------------------------
# 🟢 [신규] 디스코드 메신저 정보 관리 함수
# -------------------------------------------------------------

def get_discord_webhook_url(admin_id: str) -> Optional[str]:
    """
    주어진 관리자 ID의 디스코드 Webhook URL을 DB에서 조회합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT discord_webhook_url FROM messenger WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result['discord_webhook_url']:
        return result['discord_webhook_url']
    return None


def update_discord_webhook_url(admin_id: str, webhook_url: str) -> bool:
    """
    주어진 관리자 ID의 디스코드 Webhook URL을 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO messenger (admin_id, discord_webhook_url)
            VALUES (?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                discord_webhook_url = excluded.discord_webhook_url
            """,
            (admin_id, webhook_url)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 디스코드 Webhook URL 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def delete_discord_webhook_url(admin_id: str) -> bool:
    """
    주어진 관리자 ID의 디스코드 Webhook URL을 삭제합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE messenger SET discord_webhook_url = NULL WHERE admin_id = ?
            """,
            (admin_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB 디스코드 Webhook URL 삭제 오류: {e}")
        return False
    finally:
        conn.close()


# -------------------------------------------------------------
# 🟢 [신규] 국내 거래소 (업비트) API 키 관리 함수
# -------------------------------------------------------------

def get_upbit_api_keys(admin_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    주어진 관리자 ID의 업비트 API 키와 시크릿 키를 DB에서 조회합니다.

    Returns:
        Tuple[Optional[str], Optional[str]]: (api_key, secret_key)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT upbit_api_key, upbit_secret_key FROM korean_exchange WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return (result['upbit_api_key'], result['upbit_secret_key'])
    return (None, None)


def update_upbit_api_keys(admin_id: str, api_key: str, secret_key: str) -> bool:
    """
    주어진 관리자 ID의 업비트 API 키와 시크릿 키를 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO korean_exchange (admin_id, upbit_api_key, upbit_secret_key)
            VALUES (?, ?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                upbit_api_key = excluded.upbit_api_key,
                upbit_secret_key = excluded.upbit_secret_key
            """,
            (admin_id, api_key, secret_key)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 업비트 API 키 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def delete_upbit_api_keys(admin_id: str) -> bool:
    """
    주어진 관리자 ID의 업비트 API 키를 삭제합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM korean_exchange WHERE admin_id = ?
            """,
            (admin_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB 업비트 API 키 삭제 오류: {e}")
        return False
    finally:
        conn.close()


# -------------------------------------------------------------
# 🟢 [신규] 웹훅 설정 (WEBHOOK_PASSWORD) 관리 함수
# -------------------------------------------------------------

def get_webhook_password(admin_id: str) -> Optional[str]:
    """
    주어진 관리자 ID의 웹훅 패스워드를 DB에서 조회합니다.

    Returns:
        Optional[str]: 웹훅 패스워드 (없으면 None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT webhook_password FROM webhook_config WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result['webhook_password']:
        return result['webhook_password']
    return None


def get_webhook_endpoint(admin_id: str) -> Optional[str]:
    """
    주어진 관리자 ID의 웹훅 엔드포인트를 DB에서 조회합니다.

    Returns:
        Optional[str]: 웹훅 엔드포인트 (없으면 None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT webhook_endpoint FROM webhook_config WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result['webhook_endpoint']:
        return result['webhook_endpoint']
    return None


def update_webhook_endpoint(admin_id: str, webhook_endpoint: str) -> bool:
    """
    주어진 관리자 ID의 웹훅 엔드포인트를 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO webhook_config (admin_id, webhook_endpoint)
            VALUES (?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                webhook_endpoint = excluded.webhook_endpoint
            """,
            (admin_id, webhook_endpoint)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 웹훅 엔드포인트 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def get_allowed_ips(admin_id: str) -> Optional[str]:
    """
    주어진 관리자 ID의 허용 IP 목록을 DB에서 조회합니다.

    Returns:
        Optional[str]: 허용 IP 목록 (쉼표로 구분, 없으면 None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT allowed_ips FROM webhook_config WHERE admin_id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result['allowed_ips']:
        return result['allowed_ips']
    return None


def update_allowed_ips(admin_id: str, allowed_ips: str) -> bool:
    """
    주어진 관리자 ID의 허용 IP 목록을 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO webhook_config (admin_id, allowed_ips)
            VALUES (?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                allowed_ips = excluded.allowed_ips
            """,
            (admin_id, allowed_ips)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 허용 IP 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def get_admin_ip(admin_id: str) -> Optional[str]:
    """
    주어진 관리자 ID의 관리자 IP를 DB에서 조회합니다.

    Returns:
        Optional[str]: 관리자 IP (없으면 None)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT home_ip FROM admin WHERE id = ?", (admin_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result['home_ip']:
        return result['home_ip']
    return None


def update_admin_ip(admin_id: str, admin_ip: str) -> bool:
    """
    주어진 관리자 ID의 관리자 IP를 DB에 업데이트합니다.

    Args:
        admin_id: 관리자 ID
        admin_ip: 설정할 관리자 IP

    Returns:
        bool: 성공 여부
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE admin SET home_ip = ? WHERE id = ?",
            (admin_ip, admin_id)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 관리자 IP 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def update_webhook_password(admin_id: str, webhook_password: str) -> bool:
    """
    주어진 관리자 ID의 웹훅 패스워드를 DB에 저장하거나 업데이트합니다 (UPSERT).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO webhook_config (admin_id, webhook_password)
            VALUES (?, ?)
            ON CONFLICT(admin_id) DO UPDATE SET
                webhook_password = excluded.webhook_password
            """,
            (admin_id, webhook_password)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DB 웹훅 패스워드 업데이트 오류: {e}")
        return False
    finally:
        conn.close()


def delete_webhook_password(admin_id: str) -> bool:
    """
    주어진 관리자 ID의 웹훅 패스워드를 삭제합니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM webhook_config WHERE admin_id = ?
            """,
            (admin_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"DB 웹훅 패스워드 삭제 오류: {e}")
        return False
    finally:
        conn.close()
