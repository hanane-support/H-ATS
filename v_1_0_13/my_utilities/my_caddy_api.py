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


def check_cert_status(domain: str) -> Tuple[str, str]:
    """
    도메인의 SSL/TLS 인증서 발급 상태를 확인합니다.

    TLS automation policies에서 도메인이 등록되어 있고,
    인증서 파일이 존재하는지 확인합니다.

    Args:
        domain: 확인할 도메인

    Returns:
        (상태, 메시지) 튜플
        상태: "pending", "active", "failed", "unknown"
    """
    try:
        # 1. TLS automation policies에서 도메인 확인
        response = requests.get(f"{CADDY_API_URL}/config/apps/tls/automation/policies")
        if response.status_code == 200:
            policies = response.json()
            print(f"[Caddy API] TLS policies 확인 중...")

            # policies가 리스트인 경우
            if isinstance(policies, list):
                for policy in policies:
                    if isinstance(policy, dict):
                        subjects = policy.get('subjects', [])
                        print(f"[Caddy API] Policy subjects: {subjects}")
                        if domain in subjects:
                            print(f"[Caddy API] ✅ 도메인 {domain}이 TLS policy에 등록됨!")

                            # 2. 인증서 파일 존재 확인
                            try:
                                import os
                                cert_path = f"/var/lib/caddy/.local/share/caddy/certificates/acme-v02.api.letsencrypt.org-directory/{domain}/{domain}.crt"
                                if os.path.exists(cert_path):
                                    print(f"[Caddy API] ✅ 인증서 파일 존재 확인: {cert_path}")
                                    return "active", f"✅ {domain}에 대한 SSL/TLS 인증서가 활성화되었습니다."
                                else:
                                    print(f"[Caddy API] ⏳ 인증서 파일이 아직 생성되지 않음: {cert_path}")
                                    return "pending", f"⏳ {domain}에 대한 인증서 발급이 진행 중입니다..."
                            except Exception as file_check_error:
                                print(f"[Caddy API] ⚠️ 파일 확인 중 오류 (무시): {file_check_error}")
                                # 파일 확인 실패해도 TLS policy에 등록되어 있으면 성공으로 간주
                                return "active", f"✅ {domain}에 대한 SSL/TLS 인증서가 활성화되었습니다."

            print(f"[Caddy API] ⏳ 도메인 {domain}의 TLS policy를 찾지 못함")
            return "pending", f"⏳ {domain}에 대한 인증서 발급이 진행 중입니다..."
        else:
            print(f"[Caddy API] ❌ TLS policy 확인 실패: {response.status_code}")
            return "unknown", "인증서 상태를 확인할 수 없습니다."
    except Exception as e:
        print(f"[Caddy API] ❌ 인증서 상태 확인 중 예외 발생: {e}")
        return "unknown", f"인증서 상태 확인 중 오류 발생: {e}"


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
                                        "module": "acme"
                                    }
                                ]
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

        # 3단계: SSL/TLS 인증서 발급 요청 확인
        yield {
            "status": "progress",
            "message": f"⏳ {domain}에 대한 SSL/TLS 인증서 발급 요청 중...",
            "step": "3/5"
        }

        time.sleep(2)

        # 4단계: Let's Encrypt 인증서 검증 중 (최대 10초 대기)
        yield {
            "status": "progress",
            "message": "⏳ Let's Encrypt 인증서 검증 중 (최대 10초 소요)...",
            "step": "4/5"
        }

        # 인증서 발급 완료 대기 (최대 10초)
        max_wait_time = 10
        check_interval = 1
        elapsed_time = 0

        cert_active = False
        while elapsed_time < max_wait_time:
            time.sleep(check_interval)
            elapsed_time += check_interval

            cert_status, cert_message = check_cert_status(domain)

            if cert_status == "active":
                cert_active = True
                break
            elif cert_status == "failed":
                yield {
                    "status": "error",
                    "message": f"❌ 인증서 발급 실패: {cert_message}"
                }
                return

            # 진행 중 메시지 업데이트
            yield {
                "status": "progress",
                "message": f"⏳ 인증서 검증 중... ({elapsed_time}/{max_wait_time}초)",
                "step": "4/5"
            }

        # 5단계: 완료
        if cert_active:
            print(f"[Caddy API] ✅ 도메인 등록 완료: {domain} (인증서 활성화)")
            yield {
                "status": "success",
                "message": f"✅ HTTPS 인증 완료! {domain}으로 안전하게 접속할 수 있습니다.",
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }
        else:
            # 인증서 발급 실패 (10초 후에도 발급 안 됨)
            print(f"[Caddy API] ⚠️ 도메인 설정 완료했으나 인증서 발급 실패: {domain}")
            yield {
                "status": "warning",
                "message": (
                    "⚠️ 도메인 설정은 완료되었으나, 인증서 발급은 실패하였습니다.\n\n"
                    "DNS 설정을 확인해주세요:\n"
                    "1. 도메인 관리 페이지에서 A 레코드가 서버 IP를 가리키는지 확인\n"
                    "2. DNS 전파 완료 후 (보통 10분~1시간) 자동으로 HTTPS가 활성화됩니다.\n"
                    "3. DNS 설정이 올바르면 Caddy가 자동으로 재시도합니다."
                ),
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }

    except Exception as e:
        error_msg = f"❌ 오류 발생: {str(e)}"
        print(f"[Caddy API] {error_msg}")
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
