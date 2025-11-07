"""
Caddy Admin API를 통한 도메인 및 보안 관리 유틸리티

이 모듈은 Caddy의 Admin API를 사용하여 도메인 등록/해제 및
SSL/TLS 인증서 상태를 관리합니다.
"""

import requests
import time
import json
from typing import Tuple, Dict, Optional, Generator

# Caddy Admin API 기본 URL
CADDY_API_URL = "http://127.0.0.1:2019"

# 고정 IP 주소 (내집 IP)
MY_IP = "61.85.61.62"


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


def register_domain_with_progress(domain: str) -> Generator[Dict[str, str], None, None]:
    """
    도메인을 등록하고 진행 상황을 실시간으로 yield합니다. (SSE용)

    Args:
        domain: 등록할 도메인

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    try:
        # 1단계: Caddyfile 업데이트 시작
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
                                # IP 제한 라우트 (HTTP)
                                {
                                    "@id": "ip_matcher",
                                    "match": [{
                                        "remote_ip": {
                                            "ranges": [f"{MY_IP}/32"]
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
                                        "email": "admin@example.com"
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

        if response.status_code not in [200, 204]:
            yield {
                "status": "error",
                "message": f"❌ Caddy 설정 적용 실패: {response.text}"
            }
            return

        time.sleep(1)

        # 3단계: SSL/TLS 인증서 발급 요청 확인
        yield {
            "status": "progress",
            "message": f"⏳ {domain}에 대한 SSL/TLS 인증서 발급 요청 중...",
            "step": "3/5"
        }

        time.sleep(2)

        # 4단계: Let's Encrypt 인증서 검증 중 (최대 30초 대기)
        yield {
            "status": "progress",
            "message": "⏳ Let's Encrypt 인증서 검증 중 (최대 30초 소요)...",
            "step": "4/5"
        }

        # 인증서 발급 완료 대기 (최대 30초)
        max_wait_time = 30
        check_interval = 2
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
            yield {
                "status": "success",
                "message": f"✅ HTTPS 인증 완료! {domain}으로 안전하게 접속할 수 있습니다.",
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }
        else:
            # 인증서가 아직 발급 중이지만 설정은 완료됨
            yield {
                "status": "success",
                "message": f"✅ 도메인 설정 완료! 인증서는 백그라운드에서 발급됩니다. (최대 1분 소요)",
                "step": "5/5",
                "domain_name": domain,
                "security_status": "HTTPS"
            }

    except Exception as e:
        yield {
            "status": "error",
            "message": f"❌ 오류 발생: {str(e)}"
        }


def release_domain_with_progress(ip_address: str) -> Generator[Dict[str, str], None, None]:
    """
    도메인을 해제하고 IP만 남기며, 진행 상황을 실시간으로 yield합니다. (SSE용)

    Args:
        ip_address: 현재 서버 IP 주소

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    try:
        # 1단계: 도메인 설정 제거 시작
        yield {
            "status": "progress",
            "message": "⏳ 도메인 설정 제거 중...",
            "step": "1/3"
        }

        # IP만 허용하는 설정 (HTTP만)
        config = {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":80"],
                            "routes": [
                                # IP 제한 라우트만 유지
                                {
                                    "match": [{
                                        "remote_ip": {
                                            "ranges": [f"{MY_IP}/32"]
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

        time.sleep(0.5)

        # 2단계: Admin API로 설정 적용
        yield {
            "status": "progress",
            "message": "⏳ HTTP 전용 설정 적용 중...",
            "step": "2/3"
        }

        response = requests.post(
            f"{CADDY_API_URL}/load",
            json=config,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code not in [200, 204]:
            yield {
                "status": "error",
                "message": f"❌ Caddy 설정 적용 실패: {response.text}"
            }
            return

        time.sleep(1)

        # 3단계: 완료
        yield {
            "status": "success",
            "message": f"✅ 도메인 해제 완료! IP ({ip_address})로 HTTP 접근이 가능합니다.",
            "step": "3/3",
            "domain_name": "없음",
            "security_status": "HTTP"
        }

    except Exception as e:
        yield {
            "status": "error",
            "message": f"❌ 오류 발생: {str(e)}"
        }


def register_domain(domain: str) -> Tuple[bool, str]:
    """
    도메인을 등록합니다. (비-SSE 버전, 백업용)

    Args:
        domain: 등록할 도메인

    Returns:
        (성공 여부, 메시지)
    """
    try:
        for progress in register_domain_with_progress(domain):
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
