# my_utilities/my_encrypt.py (파일명 변경)

import bcrypt

# bcrypt 해싱을 위한 솔트(salt) 생성 횟수
BCRYPT_ROUNDS = 12 

def encrypt_password(password: str) -> str:
    """
    주어진 비밀번호 문자열을 bcrypt 해시로 암호화하여 반환합니다.
    (hash_password 함수를 encrypt_password로 변경)
    
    Args:
        password: 암호화할 일반 텍스트 비밀번호.
        
    Returns:
        bcrypt 해시 문자열.
    """
    # 1. 비밀번호 문자열을 바이트로 인코딩
    password_bytes = password.encode('utf-8')
    
    # 2. 솔트와 해싱 라운드를 사용하여 해시 생성
    hashed_bytes = bcrypt.hashpw(
        password_bytes, 
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    )
    
    # 3. 해시 바이트를 문자열로 디코드하여 저장 준비
    return hashed_bytes.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """
    일반 텍스트 비밀번호와 저장된 해시 비밀번호가 일치하는지 확인합니다.
    """
    try:
        # 일반 텍스트와 해시된 비밀번호 모두 바이트로 인코딩하여 검증
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False