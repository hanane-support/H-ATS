"""
Caddy Admin API를 통한 도메인 및 보안 관리 유틸리티

이 모듈은 Caddy의 Admin API를 사용하여 도메인 등록/해제 및
SSL/TLS 인증서 상태를 관리합니다.

환경 변수:
    CADDY_MOCK_MODE: "true"로 설정하면 모의(mock) 테스트 모드로 동작
                      실제 Caddy API를 호출하지 않고 가상 응답을 생성합니다.
                      Windows 로컬 테스트에 유용합니다.
"""

import requests
import time
import json
import os
from typing import Tuple, Dict, Optional, Generator
from pathlib import Path

# DB 함수 임포트
from my_utilities.my_db import get_admin_ip, get_allowed_ips

# 모의(Mock) 테스트 모드 확인
# Windows 로컬 테스트: set CADDY_MOCK_MODE=true
# Vultr 프로덕션: 환경 변수 설정 안 함 (기본값 false)
MOCK_MODE = os.environ.get("CADDY_MOCK_MODE", "false").lower() == "true"

# Caddy Admin API 기본 URL
CADDY_API_URL = "http://127.0.0.1:2019"

# 모의 모드 알림
if MOCK_MODE:
    print("=" * 60)
    print("🎭 [CADDY MOCK MODE 활성화]")
    print("   실제 Caddy API를 호출하지 않습니다.")
    print("   Windows 로컬 테스트 모드로 동작합니다.")
    print("=" * 60)


def get_current_config() -> Optional[Dict]:
    """
    현재 Caddy 설정을 가져옵니다.

    Returns:
        현재 설정 딕셔너리 또는 None (실패 시)
    """
    try:
        response = requests.get(f"{CADDY_API_URL}/config/")
        if response.status_code == 200:
            return response.json()
        else:
            print(f">> Caddy 설정 가져오기 실패: {response.status_code}")
            return None
    except Exception as e:
        print(f">> Caddy API 연결 실패: {e}")
        return None


def get_domain_from_caddy() -> Optional[str]:
    """
    Caddy Admin API에서 현재 등록된 도메인을 조회합니다.

    Returns:
        등록된 도메인 문자열 또는 None (도메인이 없거나 조회 실패 시)
    """
    if MOCK_MODE:
        print("[MOCK] get_domain_from_caddy() 호출 - None 반환")
        return None

    try:
        response = requests.get(f"{CADDY_API_URL}/config/apps/http/servers/srv0/routes")
        if response.status_code == 200:
            routes = response.json()

            # 라우트 목록에서 host matcher가 있는 도메인 찾기
            for route in routes:
                if "match" in route:
                    for match in route["match"]:
                        if "host" in match and match["host"]:
                            domain = match["host"][0]
                            print(f"[Caddy API] 🔍 Caddy에서 도메인 발견: {domain}")
                            return domain

            print("[Caddy API] ℹ️ Caddy에 등록된 도메인 없음")
            return None
        else:
            print(f"[Caddy API] ⚠️ Caddy 라우트 조회 실패: {response.status_code}")
            return None
    except Exception as e:
        print(f"[Caddy API] ❌ Caddy 도메인 조회 중 오류: {e}")
        return None


def check_if_https_active(domain: str) -> bool:
    """
    도메인의 HTTPS 활성화 여부를 확인합니다.

    Args:
        domain: 확인할 도메인

    Returns:
        True: HTTPS 활성화 (443 포트 리스너 + 인증서 존재)
        False: HTTPS 비활성화
    """
    if MOCK_MODE:
        print(f"[MOCK] check_if_https_active({domain}) 호출 - False 반환")
        return False

    try:
        # 1. 443 포트 리스너 확인
        response = requests.get(f"{CADDY_API_URL}/config/apps/http/servers/srv0/listen")
        if response.status_code == 200:
            listeners = response.json()
            if ":443" not in listeners:
                print(f"[Caddy API] ℹ️ 443 포트 리스너 없음 (현재: {listeners})")
                return False
        else:
            print(f"[Caddy API] ⚠️ 리스너 조회 실패: {response.status_code}")
            return False

        # 2. 인증서 확인
        cert_status, _ = check_cert_status(domain)
        is_active = cert_status == "active"

        if is_active:
            print(f"[Caddy API] ✅ {domain} HTTPS 활성화됨")
        else:
            print(f"[Caddy API] ℹ️ {domain} 인증서 상태: {cert_status}")

        return is_active
    except Exception as e:
        print(f"[Caddy API] ❌ HTTPS 상태 확인 중 오류: {e}")
        return False


def get_acme_errors(domain: str) -> Optional[str]:
    """
    Caddy Admin API에서 ACME 관련 에러 로그를 조회합니다.

    Args:
        domain: 확인할 도메인

    Returns:
        ACME 에러 메시지 문자열 또는 None
    """
    if MOCK_MODE:
        print(f"[MOCK] get_acme_errors({domain}) 호출 - None 반환")
        return None

    try:
        # Caddy의 TLS automation 상태 확인
        response = requests.get(f"{CADDY_API_URL}/config/apps/tls/automation")
        if response.status_code == 200:
            automation_config = response.json()

            # ACME 정책에서 에러 확인 (실제 구조는 Caddy 버전에 따라 다를 수 있음)
            # 여기서는 최근 에러를 찾으려고 시도
            if isinstance(automation_config, dict):
                policies = automation_config.get('policies', [])
                for policy in policies:
                    if isinstance(policy, dict):
                        subjects = policy.get('subjects', [])
                        if domain in subjects:
                            # 정책에 에러 정보가 있는지 확인
                            error_info = policy.get('error', policy.get('last_error'))
                            if error_info:
                                print(f"[Caddy API] 🔍 ACME 정책 에러 발견: {error_info}")
                                return str(error_info)

        # Caddy 로그 엔드포인트 확인 (있는 경우)
        try:
            log_response = requests.get(f"{CADDY_API_URL}/logs")
            if log_response.status_code == 200:
                logs = log_response.text
                # 로그에서 도메인 관련 ACME 에러 찾기
                if domain in logs and ('acme' in logs.lower() or 'rate' in logs.lower()):
                    # 관련 로그 라인 추출 (간단한 구현)
                    log_lines = logs.split('\n')
                    for line in log_lines:
                        if domain in line and ('error' in line.lower() or 'rate' in line.lower()):
                            print(f"[Caddy API] 🔍 로그에서 에러 발견: {line}")
                            return line
        except:
            pass

        print(f"[Caddy API] ℹ️ {domain}에 대한 ACME 에러 없음")
        return None
    except Exception as e:
        print(f"[Caddy API] ⚠️ ACME 에러 조회 중 오류: {e}")
        return None


def check_cert_status(domain: str) -> Tuple[str, str]:
    """
    도메인의 SSL/TLS 인증서 발급 상태를 확인합니다.

    Args:
        domain: 확인할 도메인

    Returns:
        (상태, 메시지) 튜플
        상태: "pending", "active", "failed", "unknown"
    """
    try:
        response = requests.get(f"{CADDY_API_URL}/config/apps/tls/certificates")
        if response.status_code == 200:
            certs = response.json()

            # 인증서 목록에서 도메인 찾기
            for cert_info in certs:
                if isinstance(cert_info, dict) and 'subjects' in cert_info:
                    if domain in cert_info.get('subjects', []):
                        return "active", f"✅ {domain}에 대한 SSL/TLS 인증서가 활성화되었습니다."

            return "pending", f"⏳ {domain}에 대한 인증서 발급이 진행 중입니다..."
        else:
            return "unknown", "인증서 상태를 확인할 수 없습니다."
    except Exception as e:
        return "unknown", f"인증서 상태 확인 중 오류 발생: {e}"


def parse_rate_limit_error(error_text: str) -> Optional[Dict]:
    """
    Let's Encrypt Rate Limit 에러를 파싱하여 상세 정보를 추출합니다.

    Args:
        error_text: Caddy 또는 ACME 에러 메시지

    Returns:
        Rate Limit 정보 딕셔너리 또는 None
        - is_rate_limited: True/False
        - limit_type: "certificates_per_domain", "duplicate_certificate", etc.
        - retry_after: 재시도 가능 일시 (ISO 8601 형식)
        - message: 사용자 친화적 메시지
    """
    import re
    from datetime import datetime, timedelta

    if not error_text:
        return None

    error_lower = error_text.lower()

    # Let's Encrypt Rate Limit 관련 키워드 확인
    rate_limit_keywords = [
        "too many certificates",
        "rate limit",
        "ratelimit",
        "too many failed authorizations",
        "too many registrations"
    ]

    is_rate_limited = any(keyword in error_lower for keyword in rate_limit_keywords)

    if not is_rate_limited:
        return None

    # Rate Limit 타입 판단
    limit_type = "unknown"
    retry_days = 7  # 기본값: 7일

    if "too many certificates" in error_lower or "certificates per domain" in error_lower:
        limit_type = "certificates_per_domain"
        retry_days = 7
    elif "duplicate certificate" in error_lower:
        limit_type = "duplicate_certificate"
        retry_days = 7
    elif "too many failed authorizations" in error_lower:
        limit_type = "failed_validations"
        retry_days = 1
    elif "too many registrations" in error_lower:
        limit_type = "registrations"
        retry_days = 1

    # Retry-After 날짜 파싱 시도
    retry_after = None

    # "Retry after YYYY-MM-DD" 형식 찾기
    retry_pattern = r"retry after (\d{4}-\d{2}-\d{2})"
    match = re.search(retry_pattern, error_lower)
    if match:
        retry_after = f"{match.group(1)}T00:00:00Z"
    else:
        # 날짜를 찾지 못하면 현재 시간 + retry_days로 계산
        future_date = datetime.utcnow() + timedelta(days=retry_days)
        retry_after = future_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 사용자 친화적 메시지 생성
    messages = {
        "certificates_per_domain": f"도메인당 인증서 발급 제한 (주당 50개)에 도달했습니다.",
        "duplicate_certificate": "동일한 인증서를 너무 자주 요청했습니다.",
        "failed_validations": "인증 실패 횟수가 너무 많습니다.",
        "registrations": "계정 등록 횟수가 너무 많습니다.",
        "unknown": "Let's Encrypt 발급 제한에 도달했습니다."
    }

    return {
        "is_rate_limited": True,
        "limit_type": limit_type,
        "retry_after": retry_after,
        "retry_days": retry_days,
        "message": messages.get(limit_type, messages["unknown"])
    }


def check_cert_in_disk_storage(domain: str) -> bool:
    """
    Caddy의 디스크 저장소에서 도메인 인증서 파일이 존재하는지 확인합니다.
    (메모리에 로드되지 않았어도 디스크에는 있을 수 있음)

    Returns:
        디스크에 인증서 존재 여부
    """
    if MOCK_MODE:
        print(f"[MOCK] check_cert_in_disk_storage({domain}) 호출 - False 반환")
        return False

    try:
        # Caddy 기본 데이터 디렉토리 경로들
        possible_paths = [
            Path("/var/lib/caddy/.local/share/caddy/certificates"),
            Path("/root/.local/share/caddy/certificates"),
            Path("~/.local/share/caddy/certificates").expanduser(),
        ]

        for base_path in possible_paths:
            if not base_path.exists():
                continue

            # acme-v02.api.letsencrypt.org-directory 하위 도메인 폴더 확인
            acme_dir = base_path / "acme-v02.api.letsencrypt.org-directory"
            if acme_dir.exists():
                domain_dir = acme_dir / domain
                if domain_dir.exists() and domain_dir.is_dir():
                    # .crt 또는 .key 파일이 있는지 확인
                    cert_files = list(domain_dir.glob("*.crt")) + list(domain_dir.glob("*.key"))
                    if cert_files:
                        print(f"[Caddy API] 🔐 디스크 저장소에서 인증서 발견: {domain_dir}")
                        return True

        print(f"[Caddy API] ℹ️ 디스크 저장소에 {domain} 인증서 없음")
        return False
    except Exception as e:
        print(f"[Caddy API] ⚠️ 디스크 저장소 확인 중 오류: {e}")
        return False


def check_cert_history_external(domain: str) -> Tuple[bool, int]:
    """
    외부 API (crt.sh)를 통해 도메인의 인증서 발급 이력을 확인합니다.
    최근 7일 이내 인증서 발급이 있었는지 확인하여 Rate Limit 가능성을 판단합니다.

    Returns:
        (최근 7일 이내 인증서 발급 이력 존재 여부, 발급 개수)
    """
    if MOCK_MODE:
        print(f"[MOCK] check_cert_history_external({domain}) 호출 - (False, 0) 반환")
        return False, 0

    try:
        from datetime import datetime, timedelta

        # crt.sh API 호출
        url = f"https://crt.sh/?q={domain}&output=json"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            print(f"[Caddy API] ⚠️ crt.sh API 호출 실패: {response.status_code}")
            return False, 0

        certs = response.json()
        if not isinstance(certs, list) or len(certs) == 0:
            print(f"[Caddy API] ℹ️ crt.sh에 {domain} 인증서 이력 없음")
            return False, 0

        # 최근 7일 기준
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_count = 0

        for cert in certs:
            # entry_timestamp 파싱 (ISO 8601 형식)
            entry_time_str = cert.get("entry_timestamp", "")
            if entry_time_str:
                try:
                    # "2025-11-13T06:51:33.768" 형식 파싱
                    entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                    if entry_time > seven_days_ago:
                        recent_count += 1
                except:
                    pass

        if recent_count >= 5:
            print(f"[Caddy API] 🚫 crt.sh 확인: 최근 7일 내 {recent_count}개 인증서 발급됨 (Rate Limit 가능성 높음)")
            return True, recent_count
        elif recent_count > 0:
            print(f"[Caddy API] ℹ️ crt.sh 확인: 최근 7일 내 {recent_count}개 인증서 발급됨")
            return True, recent_count
        else:
            print(f"[Caddy API] ✅ crt.sh 확인: 최근 7일 내 인증서 발급 없음")
            return False, 0

    except Exception as e:
        print(f"[Caddy API] ⚠️ crt.sh 조회 중 오류: {e}")
        return False, 0


def check_rate_limit_from_logs(domain: str) -> Tuple[bool, Optional[str]]:
    """
    Caddy 시스템 로그(journalctl)에서 Rate Limit 에러를 확인합니다.

    Returns:
        (Rate Limit 감지 여부, 에러 메시지)
    """
    if MOCK_MODE:
        print(f"[MOCK] check_rate_limit_from_logs({domain}) 호출 - (False, None) 반환")
        return False, None

    try:
        import subprocess
        import platform

        # Windows에서는 journalctl을 사용할 수 없음
        if platform.system() == "Windows":
            print(f"[Caddy API] ℹ️ Windows 환경: journalctl 사용 불가")
            return False, None

        # 최근 100줄의 Caddy 로그 조회
        result = subprocess.run(
            ["journalctl", "-u", "caddy", "-n", "100", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            print(f"[Caddy API] ⚠️ journalctl 실행 실패: {result.stderr}")
            return False, None

        logs = result.stdout

        # Let's Encrypt Rate Limit 에러 패턴
        rate_limit_patterns = [
            "too many certificates",
            "rateLimited",
            "urn:ietf:params:acme:error:rateLimited",
            "HTTP 429",
            "too many failed authorizations",
            "rate limit"
        ]

        # 도메인 관련 로그에서 Rate Limit 패턴 찾기
        for line in logs.split('\n'):
            if domain in line:
                for pattern in rate_limit_patterns:
                    if pattern.lower() in line.lower():
                        print(f"[Caddy API] 🚫 로그에서 Rate Limit 감지: {line[:200]}")
                        return True, line.strip()

        print(f"[Caddy API] ℹ️ 로그에서 {domain} Rate Limit 에러 없음")
        return False, None

    except subprocess.TimeoutExpired:
        print(f"[Caddy API] ⚠️ journalctl 타임아웃")
        return False, None
    except FileNotFoundError:
        print(f"[Caddy API] ⚠️ journalctl 명령어 없음 (systemd 미사용 환경)")
        return False, None
    except Exception as e:
        print(f"[Caddy API] ⚠️ 로그 조회 중 오류: {e}")
        return False, None


def pre_check_rate_limit(domain: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    인증서 발급 시도 전에 Rate Limit 가능성을 사전 확인합니다.
    여러 소스를 체크하여 빠르게 Rate Limit 여부를 판단합니다.

    Returns:
        (rate_limited, reason, cert_count)
        - rate_limited: Rate Limit 감지 여부
        - reason: 감지 근거
        - cert_count: 최근 발급 개수 (있을 경우)
    """
    print(f"[Caddy API] 🔍 Rate Limit 사전 체크 시작: {domain}")

    # 1. 디스크 저장소 확인 (가장 빠름, 로컬)
    if check_cert_in_disk_storage(domain):
        print(f"[Caddy API] 🔐 디스크에 기존 인증서 발견 → Rate Limit 가능성 있음")
        return True, "디스크에 기존 인증서 발견", None

    # 2. Caddy 로그 확인 (빠름, 정확함)
    is_rate_limited, log_msg = check_rate_limit_from_logs(domain)
    if is_rate_limited:
        print(f"[Caddy API] 🚫 로그에서 Rate Limit 확인")
        return True, f"Caddy 로그에서 확인: {log_msg[:100]}", None

    # 3. 외부 API 확인 (느림, 하지만 확실함)
    has_history, cert_count = check_cert_history_external(domain)
    if has_history and cert_count >= 5:
        print(f"[Caddy API] 🚫 외부 API에서 Rate Limit 확인 (최근 {cert_count}개 발급)")
        return True, f"최근 7일 내 {cert_count}개 인증서 발급", cert_count
    elif has_history and cert_count > 0:
        print(f"[Caddy API] ⚠️ 외부 API에서 최근 발급 이력 확인 ({cert_count}개)")
        # 5개 미만이면 Rate Limit은 아니지만, 경고 표시
        return False, None, cert_count

    print(f"[Caddy API] ✅ Rate Limit 사전 체크 통과")
    return False, None, None


def check_cert_exists_in_storage(domain: str) -> Tuple[bool, Optional[Dict]]:
    """
    Caddy의 인증서 저장소에 해당 도메인의 인증서가 이미 존재하는지 확인합니다.
    (Let's Encrypt에서 이전에 발급받은 인증서가 있는지 확인)

    Returns:
        (존재 여부, 인증서 정보) 튜플
        - 인증서 정보: {"subjects": [...], "issuer": "...", "not_after": "...", "hash": "..."}
    """
    if MOCK_MODE:
        print(f"[MOCK] check_cert_exists_in_storage({domain}) 호출 - (False, None) 반환")
        return False, None

    try:
        response = requests.get(f"{CADDY_API_URL}/config/apps/tls/certificates")
        if response.status_code == 200:
            certs = response.json()

            # 인증서 목록에서 도메인 찾기
            for cert_info in certs:
                if isinstance(cert_info, dict) and 'subjects' in cert_info:
                    if domain in cert_info.get('subjects', []):
                        print(f"[Caddy API] 🔐 인증서 저장소에서 발견: {domain}")
                        return True, {
                            "subjects": cert_info.get('subjects', []),
                            "issuer": cert_info.get('issuer', {}).get('common_name', 'Unknown'),
                            "not_after": cert_info.get('not_after', ''),
                            "hash": cert_info.get('hash', '')
                        }

            print(f"[Caddy API] ℹ️ 인증서 저장소에 {domain} 없음")
            return False, None
        else:
            print(f"[Caddy API] ⚠️ 인증서 조회 실패: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"[Caddy API] ❌ 인증서 조회 중 오류: {e}")
        return False, None


def register_domain_with_progress(domain: str, email: str = "", admin_id: str = None) -> Generator[Dict[str, str], None, None]:
    """
    도메인을 등록하고 진행 상황을 실시간으로 yield합니다. (SSE용)

    환경 변수 CADDY_MOCK_MODE=true로 설정하면 모의 테스트 모드로 동작합니다.

    Args:
        domain: 등록할 도메인
        email: Let's Encrypt 알림용 이메일 (선택사항)
        admin_id: 관리자 ID (DB에서 관리자 IP 및 allowed_ips 조회용)

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    # 모의 모드일 경우 mock 함수 사용
    if MOCK_MODE:
        from my_utilities.my_caddy_api_mock import register_domain_with_progress_mock
        yield from register_domain_with_progress_mock(domain, email)
        return

    print(f"[Caddy API] 🚀 도메인 등록 함수 시작: {domain}")

    # DB에서 관리자 IP 조회
    admin_ip = get_admin_ip(admin_id) if admin_id else None
    if not admin_ip:
        yield {
            "status": "error",
            "message": "❌ 관리자 IP를 DB에서 찾을 수 없습니다. 관리자 설정을 확인해주세요."
        }
        return

    # DB에서 허용 IP 목록 조회 (쉼표로 구분된 문자열)
    allowed_ips_str = get_allowed_ips(admin_id) if admin_id else ""
    # 쉼표로 분리하고 공백 제거
    allowed_ips_list = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()] if allowed_ips_str else []

    # 관리자 IP를 리스트 맨 앞에 추가
    all_allowed_ips = [admin_ip] + allowed_ips_list

    print(f"[Caddy API] 🏠 관리자 IP: {admin_ip}")
    print(f"[Caddy API] 🌐 허용 IP 목록: {all_allowed_ips}")

    # ==========================================================
    # 📋 0단계: Rate Limit 사전 체크 (중복 발급 방지)
    # ==========================================================
    yield {
        "status": "progress",
        "message": "🔍 인증서 발급 가능 여부 확인 중...",
        "step": "0/5"
    }

    is_rate_limited, rate_limit_reason, cert_count = pre_check_rate_limit(domain)

    if is_rate_limited:
        print(f"[Caddy API] 🚫 Rate Limit 사전 감지: {rate_limit_reason}")

        # 기존 인증서 확인 (메모리)
        cert_exists, cert_info = check_cert_exists_in_storage(domain)

        # 디스크에서도 확인
        has_disk_cert = check_cert_in_disk_storage(domain)

        if cert_exists or has_disk_cert:
            # 기존 인증서로 HTTPS 활성화 시도
            yield {
                "status": "progress",
                "message": "🔐 기존 인증서 발견. 재사용을 시도합니다...",
                "step": "0/5"
            }

            # Caddy 설정을 적용하여 기존 인증서 로드 (아래에서 진행)
            # 일단 계속 진행
        else:
            # 기존 인증서도 없고 Rate Limit에 걸림
            detail_msg = ""
            if cert_count and cert_count >= 5:
                detail_msg = (
                    f"📊 최근 7일 내에 {cert_count}개의 인증서가 발급되었습니다.\n"
                    f"Let's Encrypt는 같은 도메인에 대해 주당 5개 제한을 적용합니다.\n\n"
                )
            else:
                detail_msg = f"📋 사유: {rate_limit_reason}\n\n"

            yield {
                "status": "rate_limited",
                "message": (
                    "🚫 Let's Encrypt 인증서 발급 제한 감지\n\n"
                    f"{detail_msg}"
                    "💡 해결 방법:\n"
                    "1. 약 1주일(168시간) 후 다시 시도해주세요.\n"
                    "2. 급한 경우 다른 도메인을 사용해주세요.\n"
                    "3. 기존 인증서가 있다면 재사용을 시도합니다.\n\n"
                    "ℹ️ 자세한 정보: https://letsencrypt.org/docs/rate-limits/"
                ),
                "step": "0/5",
                "domain_name": domain,
                "security_status": "HTTP"
            }
            return

    # 기존 인증서 확인 (Rate Limit이 아닌 경우에도 확인)
    cert_exists, cert_info = check_cert_exists_in_storage(domain)
    if cert_exists:
        print(f"[Caddy API] 🔐 기존 인증서 발견! 재사용합니다: {domain}")
        print(f"[Caddy API] 인증서 정보: {cert_info}")
        yield {
            "status": "progress",
            "message": f"🔐 기존 인증서를 발견했습니다. 재사용합니다.",
            "step": "0/5"
        }
        time.sleep(1)

    try:
        # 1단계: Caddyfile 업데이트 시작
        print(f"[Caddy API] 📋 1단계: Caddy 설정 생성 중...")
        yield {
            "status": "progress",
            "message": "⏳ Caddy 설정 업데이트 중...",
            "step": "1/5"
        }

        # Caddy 설정 생성 (도메인 + IP 제한)
        config = {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":80", ":443"],
                            "routes": [
                                # 도메인 라우트 (HTTPS 자동 인증)
                                {
                                    "match": [{"host": [domain]}],
                                    "handle": [{
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": "127.0.0.1:8000"}]
                                    }],
                                    "terminal": True
                                },
                                # IP 제한 라우트 (관리자 IP + 허용 IP 목록)
                                {
                                    "@id": "ip_matcher",
                                    "match": [{
                                        "remote_ip": {
                                            "ranges": [f"{ip}/32" for ip in all_allowed_ips]
                                        }
                                    }],
                                    "handle": [{
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": "127.0.0.1:8000"}]
                                    }],
                                    "terminal": True
                                },
                                # 기타 모든 요청 거부
                                {
                                    "handle": [{
                                        "handler": "static_response",
                                        "status_code": 403,
                                        "body": "Access Denied"
                                    }]
                                }
                            ]
                        }
                    }
                },
                "tls": {
                    "automation": {
                        "policies": [
                            {
                                "subjects": [domain],
                                "issuers": [
                                    {
                                        "module": "acme",
                                        "ca": "https://acme-v02.api.letsencrypt.org/directory"
                                    }
                                ],
                                "on_demand": False,
                                "reuse_private_keys": True
                            }
                        ]
                    }
                }
            }
        }

        time.sleep(0.5)

        # 2단계: Admin API로 설정 적용
        print(f"[Caddy API] 📋 2단계: Caddy Admin API로 설정 전송 중... (URL: {CADDY_API_URL}/load)")
        yield {
            "status": "progress",
            "message": "⏳ Caddy에 새 설정 적용 중...",
            "step": "2/5"
        }

        response = requests.post(
            f"{CADDY_API_URL}/load",
            json=config,
            headers={"Content-Type": "application/json"}
        )

        print(f"[Caddy API] 📡 Caddy 응답 코드: {response.status_code}")
        if response.status_code not in [200, 204]:
            error_msg = f"❌ Caddy 설정 적용 실패: {response.text}"
            print(f"[Caddy API] {error_msg}")
            yield {
                "status": "error",
                "message": error_msg
            }
            return

        print(f"[Caddy API] ✅ Caddy 설정 적용 성공")

        time.sleep(1)

        # 2.5단계: 디스크에 저장된 기존 인증서 확인 및 로드 시도
        if cert_exists or check_cert_in_disk_storage(domain):
            print(f"[Caddy API] 🔐 기존 인증서 발견, Caddy 재로드 시도")
            try:
                # Caddy에게 인증서를 다시 로드하도록 요청 (설정 재적용)
                reload_response = requests.post(
                    f"{CADDY_API_URL}/load",
                    json=config,
                    headers={"Content-Type": "application/json"}
                )
                if reload_response.status_code in [200, 204]:
                    print(f"[Caddy API] ✅ 기존 인증서 로드 시도 완료")
                time.sleep(1)
            except Exception as e:
                print(f"[Caddy API] ⚠️ 인증서 재로드 중 오류: {e}")

        # 3단계: SSL/TLS 인증서 발급 요청 확인
        yield {
            "status": "progress",
            "message": f"⏳ {domain}에 대한 SSL/TLS 인증서 발급 요청 중...",
            "step": "3/5"
        }

        time.sleep(2)

        # 4단계: Let's Encrypt 인증서 발급 요청 완료
        yield {
            "status": "progress",
            "message": "⏳ Let's Encrypt 인증서 발급 중...",
            "step": "4/5"
        }

        time.sleep(2)

        # 5단계: 완료 (Caddy가 자동으로 인증서 발급 처리)
        cert_status, cert_message = check_cert_status(domain)

        if cert_status == "active":
            print(f"[Caddy API] ✅ 도메인 등록 완료: {domain} (인증서 활성화)")
            yield {
                "status": "success",
                "message": f"✅ HTTPS 인증 완료! {domain}으로 안전하게 접속할 수 있습니다.",
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }
        else:
            # 인증서 즉시 확인 안 됨 (Caddy가 백그라운드에서 처리 중)
            print(f"[Caddy API] ⏳ 도메인 설정 완료, HTTPS는 백그라운드에서 활성화됩니다: {domain}")
            yield {
                "status": "success",
                "message": f"✅ 도메인 등록 완료! {domain}으로 곧 HTTPS 접속이 가능합니다.",
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }

    except Exception as e:
        error_msg = f"❌ 오류 발생: {str(e)}"
        print(f"[Caddy API] {error_msg}")

        # Exception 메시지에서도 Rate Limit 확인
        rate_limit_info = parse_rate_limit_error(str(e))

        if rate_limit_info and rate_limit_info.get("is_rate_limited"):
            print(f"[Caddy API] 🚫 Rate Limit 감지 (Exception): {rate_limit_info}")
            yield {
                "status": "rate_limited",
                "message": (
                    "🚫 Let's Encrypt 인증서 발급 제한\n\n"
                    f"사유: {rate_limit_info['message']}\n"
                    f"재시도 가능 일시: {rate_limit_info['retry_after']}\n\n"
                    "💡 해결 방법:\n"
                    "1. 기존 인증서가 있다면 재사용됩니다.\n"
                    "2. 발급 제한이 해제될 때까지 기다려주세요.\n"
                    "3. 다른 도메인으로 시도하거나, 기존 도메인을 유지해주세요."
                ),
                "rate_limit_info": rate_limit_info
            }
        else:
            yield {
                "status": "error",
                "message": error_msg
            }


def release_domain_with_progress(admin_id: str = None) -> Generator[Dict[str, str], None, None]:
    """
    도메인을 해제하고 HOME IP로 초기화하며, 진행 상황을 실시간으로 yield합니다. (SSE용)

    환경 변수 CADDY_MOCK_MODE=true로 설정하면 모의 테스트 모드로 동작합니다.

    Caddy Admin API의 DELETE를 사용하여 도메인 라우트와 TLS 설정을 제거합니다.

    Args:
        admin_id: 관리자 ID (DB에서 관리자 IP 조회용)

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    # 모의 모드일 경우 mock 함수 사용
    if MOCK_MODE:
        from my_utilities.my_caddy_api_mock import release_domain_with_progress_mock
        yield from release_domain_with_progress_mock("")
        return

    print(f"[Caddy API] 🚀 도메인 해제 함수 시작")

    # DB에서 관리자 IP 조회
    admin_ip = get_admin_ip(admin_id) if admin_id else None
    if not admin_ip:
        yield {
            "status": "error",
            "message": "❌ 관리자 IP를 DB에서 찾을 수 없습니다. 관리자 설정을 확인해주세요."
        }
        return

    print(f"[Caddy API] 🏠 관리자 IP: {admin_ip}")
    try:
        # 1단계: 현재 설정 가져오기
        yield {
            "status": "progress",
            "message": "⏳ 현재 Caddy 설정 확인 중...",
            "step": "1/5"
        }

        current_config = get_current_config()
        if not current_config:
            yield {
                "status": "error",
                "message": "❌ Caddy 설정을 가져올 수 없습니다. Caddy가 실행 중인지 확인하세요."
            }
            return

        print(f"[Caddy API] ✅ 현재 설정 가져오기 성공")
        time.sleep(0.5)

        # 2단계: TLS 설정 삭제 (도메인 인증서 제거)
        yield {
            "status": "progress",
            "message": "⏳ SSL/TLS 인증서 설정 제거 중...",
            "step": "2/5"
        }

        try:
            # TLS automation policies 삭제
            response = requests.delete(f"{CADDY_API_URL}/config/apps/tls/automation/policies")
            if response.status_code not in [200, 204]:
                print(f"[Caddy API] ⚠️ TLS 정책 삭제 실패 (무시 가능): {response.status_code}")
            else:
                print(f"[Caddy API] ✅ TLS 정책 삭제 성공")
        except Exception as e:
            print(f"[Caddy API] ⚠️ TLS 정책 삭제 중 오류 (무시 가능): {e}")

        time.sleep(0.5)

        # 3단계: HTTPS 리스너 제거 (포트 443 비활성화)
        yield {
            "status": "progress",
            "message": "⏳ HTTPS 포트 비활성화 중...",
            "step": "3/5"
        }

        # HTTP만 사용하도록 listen 배열 업데이트
        try:
            response = requests.patch(
                f"{CADDY_API_URL}/config/apps/http/servers/srv0/listen",
                json=[":80"],
                headers={"Content-Type": "application/json"}
            )
            if response.status_code not in [200, 204]:
                print(f"[Caddy API] ⚠️ HTTPS 포트 비활성화 실패: {response.status_code}")
            else:
                print(f"[Caddy API] ✅ HTTPS 포트 비활성화 성공")
        except Exception as e:
            print(f"[Caddy API] ⚠️ HTTPS 포트 비활성화 중 오류: {e}")

        time.sleep(0.5)

        # 4단계: 도메인 라우트 삭제 (첫 번째 라우트)
        yield {
            "status": "progress",
            "message": "⏳ 도메인 라우트 제거 중...",
            "step": "4/5"
        }

        try:
            # 첫 번째 라우트(도메인 라우트) 삭제
            response = requests.delete(f"{CADDY_API_URL}/config/apps/http/servers/srv0/routes/0")
            if response.status_code not in [200, 204]:
                print(f"[Caddy API] ⚠️ 도메인 라우트 삭제 실패: {response.status_code} - {response.text}")
                # 실패해도 계속 진행 (이미 없을 수도 있음)
            else:
                print(f"[Caddy API] ✅ 도메인 라우트 삭제 성공")
        except Exception as e:
            print(f"[Caddy API] ⚠️ 도메인 라우트 삭제 중 오류: {e}")

        time.sleep(0.5)

        # 5단계: HOME IP 전용 설정으로 초기화
        yield {
            "status": "progress",
            "message": "⏳ HOME IP 전용 설정 적용 중...",
            "step": "5/5"
        }

        # HOME IP만 허용하는 최소 설정
        config = {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":80"],
                            "routes": [
                                # HOME IP 제한 라우트만 유지
                                {
                                    "match": [{
                                        "remote_ip": {
                                            "ranges": [f"{admin_ip}/32"]
                                        }
                                    }],
                                    "handle": [{
                                        "handler": "reverse_proxy",
                                        "upstreams": [{"dial": "127.0.0.1:8000"}]
                                    }],
                                    "terminal": True
                                },
                                # 기타 모든 요청 거부
                                {
                                    "handle": [{
                                        "handler": "static_response",
                                        "status_code": 403,
                                        "body": "Access Denied"
                                    }]
                                }
                            ]
                        }
                    }
                }
            }
        }

        response = requests.post(
            f"{CADDY_API_URL}/load",
            json=config,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code not in [200, 204]:
            error_msg = f"❌ HOME IP 설정 적용 실패: {response.text}"
            print(f"[Caddy API] {error_msg}")
            yield {
                "status": "error",
                "message": error_msg
            }
            return

        print(f"[Caddy API] ✅ HOME IP 전용 설정 적용 성공")
        time.sleep(1)

        # 완료
        print(f"[Caddy API] ✅ 도메인 해제 완료: HOME IP={admin_ip}")
        yield {
            "status": "success",
            "message": f"✅ 도메인 해제 완료! HOME IP ({admin_ip})로만 HTTP 접근이 가능합니다.",
            "step": "5/5",
            "domain_name": "없음",
            "security_status": "HTTP"
        }

    except Exception as e:
        error_msg = f"❌ 오류 발생: {str(e)}"
        print(f"[Caddy API] {error_msg}")
        yield {
            "status": "error",
            "message": error_msg
        }


def register_domain(domain: str, email: str = "admin@hanane.kr") -> Tuple[bool, str]:
    """
    도메인을 등록합니다. (비-SSE 버전, 백업용)

    Args:
        domain: 등록할 도메인
        email: Let's Encrypt 알림용 이메일 (기본값: admin@hanane.kr)

    Returns:
        (성공 여부, 메시지)
    """
    try:
        for progress in register_domain_with_progress(domain, email):
            if progress["status"] == "error":
                return False, progress["message"]
            elif progress["status"] == "success":
                return True, progress["message"]

        return False, "알 수 없는 오류 발생"
    except Exception as e:
        return False, f"도메인 등록 실패: {e}"


def release_domain(ip_address: str) -> Tuple[bool, str]:
    """
    도메인을 해제합니다. (비-SSE 버전, 백업용)

    Args:
        ip_address: 현재 서버 IP 주소

    Returns:
        (성공 여부, 메시지)
    """
    try:
        for progress in release_domain_with_progress(ip_address):
            if progress["status"] == "error":
                return False, progress["message"]
            elif progress["status"] == "success":
                return True, progress["message"]

        return False, "알 수 없는 오류 발생"
    except Exception as e:
        return False, f"도메인 해제 실패: {e}"
