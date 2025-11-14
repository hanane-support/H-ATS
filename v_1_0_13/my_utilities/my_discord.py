# my_discord.py
# 디스코드 메시지 전송 유틸리티

import requests
from typing import Optional


def send_discord_message(webhook_url: str, title: str, message: str, color: int = 0x00FF00) -> dict:
    """
    디스코드 Webhook URL로 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL
        title: 메시지 제목
        message: 메시지 내용
        color: 임베드 색상 (기본값: 초록색 0x00FF00)

    Returns:
        dict: {"success": bool, "message": str}
    """
    if not webhook_url:
        return {"success": False, "message": "디스코드 Webhook URL이 설정되지 않았습니다."}

    # 디스코드 임베드 메시지 형식
    message_format = {
        "title": title,
        "color": color,
        "description": message,
    }

    discord_embeds = {"embeds": [message_format]}

    try:
        response = requests.post(webhook_url, json=discord_embeds, timeout=10)
        print(f"디스코드 전송 요청 보냄: {discord_embeds}")
        print(f"응답 상태 코드: {response.status_code}, 응답 텍스트: {response.text}")

        if response.status_code == 204:
            print("✅ 디스코드 전송 성공")
            return {"success": True, "message": "디스코드 메시지 전송 성공"}
        else:
            print("❌ 디스코드 전송 실패")
            return {"success": False, "message": f"디스코드 전송 실패: {response.status_code}"}

    except requests.exceptions.Timeout:
        print("🚨 디스코드 전송 시간 초과")
        return {"success": False, "message": "디스코드 전송 시간 초과"}
    except Exception as e:
        print(f"🚨 디스코드 전송 중 예외 발생: {e}")
        return {"success": False, "message": f"디스코드 전송 오류: {str(e)}"}


def send_console_connection_success(webhook_url: str) -> dict:
    """
    관리자 콘솔 연동 성공 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL

    Returns:
        dict: {"success": bool, "message": str}
    """
    title = "관리자 콘솔 연동 성공"
    message = "H-AST 관리자 콘솔 연동이 성공하였습니다."
    color = 0x00FF00  # 초록색

    return send_discord_message(webhook_url, title, message, color)


def send_console_connection_failure(webhook_url: str, error_message: str = "") -> dict:
    """
    관리자 콘솔 연동 실패 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL
        error_message: 오류 메시지 (선택)

    Returns:
        dict: {"success": bool, "message": str}
    """
    title = "관리자 콘솔 연동 실패"
    message = f"H-AST 관리자 콘솔 연동이 실패하였습니다."

    if error_message:
        message += f"\n\n오류 내용: {error_message}"

    color = 0xFF0000  # 빨간색

    return send_discord_message(webhook_url, title, message, color)


def send_console_disconnection(webhook_url: str) -> dict:
    """
    관리자 콘솔 연동 해제 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL

    Returns:
        dict: {"success": bool, "message": str}
    """
    title = "관리자 콘솔 연동 해제"
    message = "H-AST 관리자 콘솔 연동이 해제되었습니다."
    color = 0xFFFF00  # 노란색

    return send_discord_message(webhook_url, title, message, color)


def send_upbit_api_registered(webhook_url: str) -> dict:
    """
    업비트 API 키 등록 성공 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL

    Returns:
        dict: {"success": bool, "message": str}
    """
    title = "업비트 API 키 등록 완료"
    message = "업비트 API 키가 성공적으로 등록되었습니다.\n이제 자동매매 기능을 사용할 수 있습니다."
    color = 0x00FF00  # 초록색

    return send_discord_message(webhook_url, title, message, color)


def send_upbit_api_released(webhook_url: str) -> dict:
    """
    업비트 API 키 해제 메시지를 전송합니다.

    Args:
        webhook_url: 디스코드 Webhook URL

    Returns:
        dict: {"success": bool, "message": str}
    """
    title = "업비트 API 키 해제 완료"
    message = "업비트 API 키가 해제되었습니다.\n더 이상 업비트 계정에 접근할 수 없습니다."
    color = 0xFFFF00  # 노란색

    return send_discord_message(webhook_url, title, message, color)


# =====================================================================
# 트레이딩뷰 웹훅 관련 함수들
# =====================================================================

def send_discord_server_start(message: str):
    """
    서버 시작 메시지를 Embed 포맷으로 전송합니다.

    Args:
        message: 전송할 메시지
    """
    # 환경변수에서 디스코드 웹훅 URL 가져오기
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=BASE_DIR / ".env")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

    if not DISCORD_WEBHOOK_URL:
        print("🚨 DISCORD_WEBHOOK_URL이 설정되지 않았습니다.")
        return

    title = "HNAT 서버"
    color_hex = 0x00FF00  # 녹색 (성공)

    # Embed 구조 생성
    message_format = {
        "title": title,
        "color": color_hex,
        "description": message,
    }

    discord_embeds = {"embeds": [message_format]}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=discord_embeds, timeout=10)
        print(f"디스코드 서버 시작 알림 전송: {title}")

        if response.status_code == 204:
            print("✅ 서버 시작 알림 전송 성공")
        else:
            print(f"❌ 디스코드 전송 실패. 상태 코드: {response.status_code}")

    except Exception as e:
        print("🚨 디스코드 전송 중 예외 발생:", e)


def send_discord_server_shutdown(message: str):
    """
    서버 종료 메시지를 Embed 포맷으로 전송합니다.

    Args:
        message: 전송할 메시지
    """
    # 환경변수에서 디스코드 웹훅 URL 가져오기
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=BASE_DIR / ".env")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

    if not DISCORD_WEBHOOK_URL:
        print("🚨 DISCORD_WEBHOOK_URL이 설정되지 않았습니다.")
        return

    title = "HNAT 서버"
    color_hex = 0xFF0000  # 빨간색 (종료/경고)

    # Embed 구조 생성
    message_format = {
        "title": title,
        "color": color_hex,
        "description": message,
    }

    discord_embeds = {"embeds": [message_format]}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=discord_embeds, timeout=10)
        print(f"디스코드 서버 종료 알림 전송: {title}")

        if response.status_code == 204:
            print("✅ 서버 종료 알림 전송 성공")
        else:
            print(f"❌ 디스코드 전송 실패. 상태 코드: {response.status_code}")

    except Exception as e:
        print("🚨 디스코드 전송 중 예외 발생:", e)


def send_discord(order_info: dict, title: str, note: str = "", admin_id: str = None):
    """
    트레이딩뷰 웹훅 주문 결과를 디스코드로 전송합니다.

    Args:
        order_info: 주문 정보 딕셔너리
        title: 메시지 제목
        note: 추가 안내사항 (선택)
        admin_id: 관리자 ID (선택, order_info에 없으면 필수)
    """
    # DB에서 디스코드 웹훅 URL 가져오기
    from my_utilities.my_db import get_discord_webhook_url

    # admin_id 추출 (함수 인자 또는 order_info에서)
    if not admin_id:
        admin_id = order_info.get("admin_id")

    if not admin_id:
        print("🚨 admin_id가 제공되지 않았습니다.")
        return

    DISCORD_WEBHOOK_URL = get_discord_webhook_url(admin_id)

    if not DISCORD_WEBHOOK_URL:
        print(f"🚨 admin_id '{admin_id}'의 DISCORD_WEBHOOK_URL이 DB에 설정되지 않았습니다.")
        return

    # 필드 값이 없는 경우 기본값 대체
    time = order_info.get("time", "알 수 없음")
    exchange = order_info.get("exchange", "알 수 없음")
    symbol = order_info.get("symbol", "알 수 없음")
    order_type = order_info.get("order_type", "알 수 없음")
    id_val = order_info.get("id", "알 수 없음")
    comment = order_info.get("comment", "알 수 없음")
    price = str(order_info.get("price", "알 수 없음"))
    amount = str(order_info.get("amount", "알 수 없음"))
    cost = str(order_info.get("cost", "알 수 없음"))
    success = order_info.get("success")
    failure_message = order_info.get("failure_message")

    space = "\u2002"

    # 조건에 따라 메시지 내용과 색상을 변경
    # 1. 성공 메시지
    if success is True:
        status_text = "주문이 체결되었습니다!"

        if title == "매수":
            color_hex = 0x00FF00  # 초록색 (성공)
        else:
            color_hex = 0x9B59B6  # 연한 보라색

        if note:
            order_history = (
                f"{status_text}\n\n"
                f"**일시**{space * 3}: {space}{time}\n"
                f"**거래소**{space * 1}: {space}{exchange}\n"
                f"**심볼**{space * 3}: {space}{symbol}\n"
                f"**주문**{space * 3}: {space}{order_type}\n"
                f"**ID**{space * 5}: {space}{id_val}\n"
                f"**코멘트**{space * 1}: {space}{comment}\n"
                f"**체결가**{space * 1}: {space}{price}\n"
                f"**수량**{space * 3}: {space}{amount}\n"
                f"**비용**{space * 3}: {space}{cost}\n\n"
                f"**안내**{space * 3}:\n{note}"
            )
        else:
            order_history = (
                f"{status_text}\n\n"
                f"**일시**{space * 3}: {space}{time}\n"
                f"**거래소**{space * 1}: {space}{exchange}\n"
                f"**심볼**{space * 3}: {space}{symbol}\n"
                f"**주문**{space * 3}: {space}{order_type}\n"
                f"**ID**{space * 5}: {space}{id_val}\n"
                f"**코멘트**{space * 1}: {space}{comment}\n"
                f"**체결가**{space * 1}: {space}{price}\n"
                f"**수량**{space * 3}: {space}{amount}\n"
                f"**비용**{space * 3}: {space}{cost}"
            )

    # 2. 실패 메시지
    else:
        status_text = "주문이 체결되지 않았습니다."
        color_hex = 0xFFFF00  # 노란색 (실패/경고)

        order_history = (
            f"{status_text}\n\n"
            f"{failure_message}"
        )

    # 제목과 색상 적용
    message_format = {
        "title": f"{title}",
        "color": color_hex,
        "description": order_history,
    }

    discord_embeds = {"embeds": [message_format]}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=discord_embeds, timeout=10)
        print("디스코드 전송 요청 보냄:", discord_embeds)
        print("응답 상태 코드:", response.status_code, "응답 텍스트:", response.text)

        if response.status_code == 204:
            print("✅ 디스코드 전송 성공")
        else:
            print("❌ 디스코드 전송 실패")

    except Exception as e:
        print("🚨 디스코드 전송 중 예외 발생:", e)
