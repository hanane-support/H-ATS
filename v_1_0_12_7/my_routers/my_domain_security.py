# Caddy Admin API를 사용한 도메인 보안 관리 라우터

import sys
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from my_utilities.my_db import get_domain_security_config, update_domain_security_config
from my_utilities.my_caddy_api import (
    register_domain_with_progress,
    release_domain_with_progress
)
from .my_index import get_server_info

# 템플릿 디렉토리가 'my_templates'에 있다고 가정합니다. (환경에 따라 수정 필요)
templates = Jinja2Templates(directory="my_templates")

# 라우터 객체 설정
domain_security_router = APIRouter()


# ==========================================================
# 🚨 SSE용 이벤트 생성 헬퍼 함수
# ==========================================================

def sse_event(data: dict) -> str:
    """
    Server-Sent Events 형식으로 데이터를 변환합니다.

    Args:
        data: 전송할 데이터 딕셔너리

    Returns:
        SSE 형식의 문자열
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# ==========================================================
# 1. 템플릿 렌더링 (GET)
# ==========================================================

# 최종 경로는 /admin/domain_security
@domain_security_router.get("/domain_security", response_class=HTMLResponse)
async def domain_security_manager(request: Request):
    """
    도메인 보안 설정 페이지(my_domain_security.html)를 렌더링하고,
    DB에 저장된 현재 도메인 및 보안 상태를 전달합니다.
    """
    admin_id = request.session.get("user_id")
    if not admin_id:
        # admin_id가 없으면 로그인 페이지로 리디렉션 (또는 오류 처리)
        # 이 부분은 실제 앱의 인증 정책에 맞게 수정해야 합니다.
        # 여기서는 간단히 빈 컨텍스트로 렌더링하거나, 기본값을 사용합니다.
        domain_config = {"domain_name": "없음", "security_status": "HTTP"}
    else:
        # DB에서 현재 도메인 및 보안 상태를 가져옵니다.
        domain_config = get_domain_security_config(admin_id)

    # 서버 정보 가져오기
    server_info = get_server_info(request)

    context = {
        "request": request,
        "domain_name": domain_config.get("domain_name", "없음"),
        "email": domain_config.get("email", ""),
        "security_status": domain_config.get("security_status", "HTTP"),
        **server_info  # 서버 정보 추가
    }

    return templates.TemplateResponse(
        "my_domain_security.html",
        context
    )

# ==========================================================
# 2. 보안 적용 로직 (SSE) - Caddy Admin API 사용
# ==========================================================

@domain_security_router.post("/domain_security/apply_security")
async def apply_security(request: Request):
    """
    SSE를 통해 도메인 등록 진행 상황을 실시간으로 스트리밍합니다.
    """
    admin_id = request.session.get("user_id")
    if not admin_id:
        print("❌ 인증되지 않은 요청: admin_id가 없습니다.")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "인증되지 않은 요청입니다."}
        )

    domain_to_register = None
    email_address = None
    try:
        data = await request.json()
        domain_to_register = data.get("domain")
        email_address = data.get("email")

        if not domain_to_register:
            print("❌ 요청 본문에 도메인 정보가 없습니다.")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "도메인 정보가 요청 본문에 포함되어 있지 않습니다."}
            )

        if not email_address:
            print("❌ 요청 본문에 이메일 정보가 없습니다.")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "이메일 정보가 요청 본문에 포함되어 있지 않습니다."}
            )

        print(f"✅ 클라이언트에서 받은 도메인: {domain_to_register}")
        print(f"✅ 클라이언트에서 받은 이메일: {email_address}")
        print(f"✅ 관리자 ID: {admin_id}")
    except json.JSONDecodeError:
        print("❌ JSON 디코딩 오류")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
        )
    except Exception as e:
        print(f"❌ 요청 처리 중 오류 발생: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"요청 처리 중 오류 발생: {e}"}
        )

    # SSE 스트림 생성
    async def event_stream():
        """도메인 등록 진행 상황을 SSE로 스트리밍"""
        print(f"🚀 도메인 등록 시작: {domain_to_register}, 이메일: {email_address}")
        for progress in register_domain_with_progress(domain_to_register, email_address):
            print(f"📡 SSE 전송: {progress}")
            yield sse_event(progress)

            # 최종 상태일 때 DB 업데이트
            if progress["status"] == "success":
                print(f"💾 DB 업데이트 시도: admin_id={admin_id}, domain={domain_to_register}, email={email_address}")
                db_success = update_domain_security_config(
                    admin_id,
                    domain_to_register,
                    'HTTPS',
                    email_address
                )
                if not db_success:
                    print("⚠️ DB 업데이트 실패")
                    yield sse_event({
                        "status": "warning",
                        "message": "⚠️ Caddy 설정은 완료되었으나 DB 업데이트 실패"
                    })
                else:
                    print("✅ DB 업데이트 성공")
                break
            elif progress["status"] == "error":
                print(f"❌ 도메인 등록 실패: {progress.get('message')}")
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ==========================================================
# 3. 도메인 해제 로직 (SSE) - Caddy Admin API 사용
# ==========================================================

@domain_security_router.post("/domain_security/release_security")
async def release_security(request: Request):
    """
    SSE를 통해 도메인 해제 진행 상황을 실시간으로 스트리밍합니다.
    """
    admin_id = request.session.get("user_id")
    if not admin_id:
        print("❌ 인증되지 않은 요청: admin_id가 없습니다.")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "인증되지 않은 요청입니다."}
        )

    ip_address = None
    try:
        data = await request.json()
        ip_address = data.get("ip")
        if not ip_address:
            print("❌ 요청 본문에 IP 주소 정보가 없습니다.")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "IP 주소 정보가 요청 본문에 포함되어 있지 않습니다."}
            )
        print(f"✅ 클라이언트에서 받은 해제 요청 IP: {ip_address}")
        print(f"✅ 관리자 ID: {admin_id}")
    except json.JSONDecodeError:
        print("❌ JSON 디코딩 오류")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "유효하지 않은 JSON 형식입니다."}
        )
    except Exception as e:
        print(f"❌ 요청 처리 중 오류 발생: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"요청 처리 중 오류 발생: {e}"}
        )

    # SSE 스트림 생성
    async def event_stream():
        """도메인 해제 진행 상황을 SSE로 스트리밍"""
        print(f"🚀 도메인 해제 시작: IP={ip_address}")
        for progress in release_domain_with_progress(ip_address):
            print(f"📡 SSE 전송: {progress}")
            yield sse_event(progress)

            # 최종 상태일 때 DB 업데이트
            if progress["status"] == "success":
                print(f"💾 DB 업데이트 시도: admin_id={admin_id}, domain=없음, email=''")
                db_success = update_domain_security_config(
                    admin_id,
                    "없음",
                    'HTTP',
                    ""  # 이메일도 초기화
                )
                if not db_success:
                    print("⚠️ DB 업데이트 실패")
                    yield sse_event({
                        "status": "warning",
                        "message": "⚠️ Caddy 설정은 완료되었으나 DB 업데이트 실패"
                    })
                else:
                    print("✅ DB 업데이트 성공")
                break
            elif progress["status"] == "error":
                print(f"❌ 도메인 해제 실패: {progress.get('message')}")
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
