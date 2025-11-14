

# my_parsing.py
# 트레이딩뷰 웹훅에서 받은 데이터를 파싱하고 처리하는 파일

from datetime import datetime
from my_utilities.my_order import my_order
from my_models.my_webhook import OrderData, OrderResult
from my_exchange.my_upbit import UpbitTrader
from my_utilities.my_discord import send_discord
from my_utilities.my_db import get_webhook_password


def my_parsing(_my_tradingview_alert_message: dict):
    """
    my_server.py에서 받은 웹훅 데이터를 처리하는 함수.

    _my_tradingview_alert_message: dict — 트레이딩뷰에서 수신한 전체 딕셔너리 데이터

    ⚠️ 필수 파라미터:
    - admin_id: DB에서 설정을 조회하기 위한 관리자 ID (필수!)
    - webhook_password: 웹훅 인증용 패스워드 (필수!)
    """

    # 데이터에서 필요한 정보 추출
    webhook_password = _my_tradingview_alert_message.get('webhook_password') # 웹훅에 포함된 패스워드
    admin_id = _my_tradingview_alert_message.get('admin_id') # 웹훅에서 admin_id 추출 (필수!)

    # admin_id 검증
    if not admin_id:
        error_msg = "❌ admin_id가 웹훅 페이로드에 포함되지 않았습니다. 트레이딩뷰 알림 메시지에 'admin_id'를 추가하세요."
        print(error_msg)
        send_discord({
            "success": False,
            "failure_message": error_msg,
            "admin_id": admin_id
        }, "주문 실패", admin_id=admin_id)
        return

    id = _my_tradingview_alert_message.get('id') # 주문 ID (예: "long", "Close entry(s) order strategy.close_0")
    comment = _my_tradingview_alert_message.get('comment') # 주문 코멘트 (예: "long", "Close entry(s) order long")
    alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # 웹훅을 받은 시점의 시간 (예: "2023-10-01 12:34:56")
    exchange = _my_tradingview_alert_message.get('exchange') # 거래소 이름 (예: "BINANCE", "UPBIT")
    ticker = _my_tradingview_alert_message.get('ticker') # 종목 심볼 (예: "BTCUSDT.P", "USDTKRW")
    prev_market_position = _my_tradingview_alert_message.get('prev_market_position') # 이전 포지션 상태 ("flat", "long", "short")
    action = _my_tradingview_alert_message.get('action') # 주문 방향 ("buy" or "sell")
    market_position = _my_tradingview_alert_message.get('market_position') # 현재 포지션 상태 ("flat", "long", "short")
    order = my_order(prev_market_position, action, market_position) # 주문 로직 판단 함수 호출
    price = _my_tradingview_alert_message.get('price') # 신호가 발생한 시점의 가격
    contracts = _my_tradingview_alert_message.get('contracts') # 신호가 발생한 시점의 수량

    # 파싱 결과 출력
    print("──────────────────────────────")
    print(f"admin_id: {admin_id}")
    print(f"webhook_password: {webhook_password}")
    print(f"id: {id}")
    print(f"comment: {comment}")
    print(f"alert_time: {alert_time}")
    print(f"exchange: {exchange}")
    print(f"ticker: {ticker}")
    print(f"prev_market_position: {prev_market_position}")
    print(f"action: {action.upper()}")
    print(f"market_position: {market_position}")
    print(f"order: {order}")
    print(f"price: {price}")
    print(f"contracts: {contracts}")
    print("✅  [my_parsing] 데이터 처리 완료!")
    print("──────────────────────────────")

    # 패스워드 검증 (DB에서 조회)
    stored_password = get_webhook_password(admin_id)

    if not stored_password:
        error_msg = f"❌ admin_id '{admin_id}'에 대한 웹훅 패스워드가 DB에 설정되지 않았습니다."
        print(error_msg)
        send_discord({
            "success": False,
            "failure_message": error_msg,
            "admin_id": admin_id
        }, "주문 실패", admin_id=admin_id)
        return

    if webhook_password and webhook_password == stored_password:
        print("✅ 웹훅 패스워드가 일치합니다.")

        # OrderData 생성 (데이터 검증 자동)
        try:
            order_data = OrderData(
                id=id,
                comment=comment,
                alert_time=alert_time,
                exchange=exchange,
                ticker=ticker,
                prev_market_position=prev_market_position,
                action=action,
                market_position=market_position,
                order=order,
                price=price,
                contracts=contracts
            )
            print("✅ OrderData 생성 완료")

        except Exception as e:
            error_msg = f"❌ OrderData 생성 실패: {e}"
            print(error_msg)
            send_discord({
                "success": False,
                "failure_message": error_msg,
                "admin_id": admin_id
            }, "주문 실패", admin_id=admin_id)
            return

        # 거래소별 처리
        if exchange == "UPBIT":
            # UpbitTrader 인스턴스 생성 (admin_id 기반)
            try:
                upbit_trader = UpbitTrader(admin_id)
            except ValueError as ve:
                error_msg = f"❌ UpbitTrader 초기화 실패: {ve}"
                print(error_msg)
                send_discord({
                    "success": False,
                    "failure_message": error_msg,
                    "admin_id": admin_id
                }, "주문 실패", admin_id=admin_id)
                return

            # UpbitTrader로 주문 실행
            result: OrderResult = upbit_trader.execute_order(order_data)

            # 결과를 디스코드로 전송
            if result.success:
                # note가 있으면 함께 전달
                send_discord(
                    result.to_dict(),
                    "매수" if result.order_type == "매수" else "매도",
                    note=result.note if result.note else "",
                    admin_id=admin_id
                )
                print(f"✅ {result.order_type} 주문 성공!")
            else:
                send_discord(result.to_dict(), "주문 실패", admin_id=admin_id)
                print(f"❌ 주문 실패: {result.failure_message}")

        else:
            print(f"⚠️ 경고: 지원하지 않는 거래소 ({exchange})입니다.")
            send_discord({
                "success": False,
                "failure_message": f"지원하지 않는 거래소: {exchange}",
                "admin_id": admin_id
            }, "주문 실패", admin_id=admin_id)

    else:
        # 패스워드 불일치
        print("❌ 웹훅 패스워드가 일치하지 않습니다.")
        order_info = {
            "success": False,
            "failure_message": """웹훅 패스워드가 일치하지 않습니다.
            트레이딩뷰 - 얼러트 편집 - 메세지 - webhook_password 를 확인 하세요""",
            "admin_id": admin_id
        }
        send_discord(order_info, "주문 실패", admin_id=admin_id)

















