
# my_server.py
# 트레이딩뷰 웹훅에서 받은 데이터를 처리하는 라우터 파일

from fastapi import APIRouter, Request
from my_utilities.my_parsing import my_parsing
from my_utilities.my_discord import send_discord_server_start, send_discord_server_shutdown


# APIRouter 인스턴스 생성
router = APIRouter()


# POST 메서드로 '/webhook' 경로에 요청이 오면 실행되는 함수 정의
@router.post("/webhook")
async def my_tradingview_alert_message(request: Request):
    """
    트레이딩뷰에서 보내는 웹훅 POST 요청을 처리하는 비동기 함수
    request: Request — 요청 객체를 통해 JSON 데이터 읽기
    """

    try:
        # 요청 바디에서 JSON 데이터 비동기적으로 읽음
        my_tradingview_alert_message = await request.json()

        # 받은 데이터 콘솔에 출력 (디버깅용)
        print("──────────────────────────────")
        print("📩 트레이딩뷰에서 받은 얼러트 메세지:")
        print(my_tradingview_alert_message)

        # 받은 데이터를 처리하기 위해 'my_parsing' 함수 호출하고 전달
        my_parsing(my_tradingview_alert_message)

        # 처리 완료 후 성공 메시지 반환
        return {"status": "success", "message": "성공적으로 웹훅을 처리했습니다."}

    except Exception as e:
        # 예외 발생 시 오류 메시지 출력
        print("웹훅 처리 중 오류 발생:", e)

        # 에러 응답을 JSON 형태로 반환
        return {
            "status": "error",
            "message": f"웹훅 처리 중 오류가 발생했습니다: {e}"
        }
