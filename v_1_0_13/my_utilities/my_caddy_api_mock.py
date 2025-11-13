"""
Caddy API 모의(Mock) 테스트 모듈

실제 Caddy API를 호출하지 않고 Windows 로컬 환경에서
도메인 등록/해제 기능을 테스트할 수 있는 가상 구현입니다.
"""

import time
from typing import Dict, Generator


def register_domain_with_progress_mock(domain: str, email: str = "") -> Generator[Dict[str, str], None, None]:
    """
    도메인 등록을 가상으로 시뮬레이션합니다. (SSE용)

    실제 Caddy API를 호출하지 않고, 진행 상황을 모의로 생성합니다.

    Args:
        domain: 등록할 도메인 (테스트용)
        email: Let's Encrypt 알림용 이메일 (테스트용, 선택사항)

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    print(f"[Mock Caddy API] 🎭 모의 도메인 등록 시작: {domain}")

    # 1단계: Caddyfile 업데이트 시작
    print(f"[Mock Caddy API] 📋 1단계: 가상 Caddy 설정 생성 중...")
    yield {
        "status": "progress",
        "message": "⏳ [모의] Caddy 설정 업데이트 중...",
        "step": "1/5"
    }
    time.sleep(0.5)

    # 2단계: Admin API로 설정 적용
    print(f"[Mock Caddy API] 📋 2단계: 가상 Caddy Admin API로 설정 전송 중...")
    yield {
        "status": "progress",
        "message": "⏳ [모의] Caddy에 새 설정 적용 중...",
        "step": "2/5"
    }
    time.sleep(0.7)
    print(f"[Mock Caddy API] ✅ 가상 Caddy 설정 적용 성공")

    # 3단계: SSL/TLS 인증서 발급 요청 확인
    yield {
        "status": "progress",
        "message": f"⏳ [모의] {domain}에 대한 SSL/TLS 인증서 발급 요청 중...",
        "step": "3/5"
    }
    time.sleep(0.8)

    # 4단계: Let's Encrypt 인증서 검증 중
    yield {
        "status": "progress",
        "message": "⏳ [모의] Let's Encrypt 인증서 검증 중 (최대 5초 소요)...",
        "step": "4/5"
    }

    # 가상 인증서 발급 대기 (5초)
    max_wait_time = 5
    for i in range(1, max_wait_time + 1):
        time.sleep(1)
        yield {
            "status": "progress",
            "message": f"⏳ [모의] 인증서 검증 중... ({i}/{max_wait_time}초)",
            "step": "4/5"
        }

    # 5단계: 완료
    print(f"[Mock Caddy API] ✅ 가상 도메인 등록 완료: {domain}")
    yield {
        "status": "success",
        "message": f"✅ [모의 테스트 성공] HTTPS 인증 완료! {domain}으로 안전하게 접속할 수 있습니다.",
        "step": "5/5",
        "domain_name": domain,
        "security_status": "HTTPS"
    }


def release_domain_with_progress_mock(ip_address: str) -> Generator[Dict[str, str], None, None]:
    """
    도메인 해제를 가상으로 시뮬레이션합니다. (SSE용)

    실제 Caddy API를 호출하지 않고, 진행 상황을 모의로 생성합니다.

    Args:
        ip_address: 현재 서버 IP 주소 (테스트용, 메시지 출력용)

    Yields:
        {"status": "progress/success/error", "message": "메시지"} 형식의 딕셔너리
    """
    print(f"[Mock Caddy API] 🎭 모의 도메인 해제 시작: IP={ip_address}")

    # 1단계: 현재 설정 가져오기
    yield {
        "status": "progress",
        "message": "⏳ [모의] 현재 Caddy 설정 확인 중...",
        "step": "1/5"
    }
    time.sleep(0.5)
    print(f"[Mock Caddy API] ✅ 가상 설정 가져오기 성공")

    # 2단계: TLS 설정 삭제
    yield {
        "status": "progress",
        "message": "⏳ [모의] SSL/TLS 인증서 설정 제거 중...",
        "step": "2/5"
    }
    time.sleep(0.6)
    print(f"[Mock Caddy API] ✅ 가상 TLS 정책 삭제 성공")

    # 3단계: HTTPS 리스너 제거
    yield {
        "status": "progress",
        "message": "⏳ [모의] HTTPS 포트 비활성화 중...",
        "step": "3/5"
    }
    time.sleep(0.5)
    print(f"[Mock Caddy API] ✅ 가상 HTTPS 포트 비활성화 성공")

    # 4단계: 도메인 라우트 삭제
    yield {
        "status": "progress",
        "message": "⏳ [모의] 도메인 라우트 제거 중...",
        "step": "4/5"
    }
    time.sleep(0.7)
    print(f"[Mock Caddy API] ✅ 가상 도메인 라우트 삭제 성공")

    # 5단계: HOME IP 전용 설정으로 초기화
    yield {
        "status": "progress",
        "message": "⏳ [모의] HOME IP 전용 설정 적용 중...",
        "step": "5/5"
    }
    time.sleep(0.8)
    print(f"[Mock Caddy API] ✅ 가상 HOME IP 전용 설정 적용 성공")

    # 완료
    mock_home_ip = "127.0.0.1"  # Windows 로컬 테스트용
    print(f"[Mock Caddy API] ✅ 가상 도메인 해제 완료: IP={ip_address}")
    yield {
        "status": "success",
        "message": f"✅ [모의 테스트 성공] 도메인 해제 완료! HOME IP ({mock_home_ip})로만 HTTP 접근이 가능합니다.",
        "step": "5/5",
        "domain_name": "없음",
        "security_status": "HTTP"
    }


def check_cert_status_mock(domain: str) -> tuple[str, str]:
    """
    가상 인증서 상태 확인

    Args:
        domain: 확인할 도메인

    Returns:
        (상태, 메시지) 튜플 - 항상 "active" 반환
    """
    return "active", f"✅ [모의] {domain}에 대한 SSL/TLS 인증서가 활성화되었습니다."


def get_current_config_mock() -> Dict:
    """
    가상 Caddy 설정 반환

    Returns:
        가상 설정 딕셔너리
    """
    return {
        "apps": {
            "http": {
                "servers": {
                    "srv0": {
                        "listen": [":80"],
                        "routes": []
                    }
                }
            }
        }
    }
