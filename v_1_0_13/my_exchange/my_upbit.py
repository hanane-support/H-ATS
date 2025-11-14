# my_upbit.py
# 업비트 거래소 API 연동 및 주문 실행

import ccxt
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

# TYPE_CHECKING을 사용하여 순환 import 방지
if TYPE_CHECKING:
    from my_models.my_webhook import OrderResult

# DB 유틸리티 임포트
from my_utilities.my_db import get_upbit_api_keys


def create_upbit_exchange(admin_id: str) -> Optional[ccxt.upbit]:
    """
    DB에서 사용자의 업비트 API 키를 조회하여 거래소 인스턴스를 생성합니다.

    Args:
        admin_id: 관리자 사용자 ID

    Returns:
        ccxt.upbit: 거래소 인스턴스 (API 키가 없으면 None)
    """
    # DB에서 API 키 조회
    api_key, secret_key = get_upbit_api_keys(admin_id)

    if not api_key or not secret_key:
        print("⚠️ 업비트 API 키가 DB에 등록되어 있지 않습니다.")
        return None

    # Upbit exchange 인스턴스 생성
    return ccxt.upbit({
        "apiKey": api_key,
        "secret": secret_key,
        "options": {
            'defaultType': 'spot',
        },
    })


# =============================================================================
# 예외 클래스
# =============================================================================

class InsufficientFundsError(Exception):
    """잔고 부족 예외"""
    pass


# =============================================================================
# 잔고 관리 클래스
# =============================================================================

class UpbitBalance:
    """업비트 잔고 관리 클래스 (캐싱 포함)"""

    def __init__(self, exchange):
        self.exchange = exchange
        self._balance = None
        self._last_fetch_time = None
        self._cache_duration = 5  # 5초 캐싱

    def get_balance(self, force_refresh=False) -> dict:
        """
        잔고 조회 (5초 캐싱)

        Args:
            force_refresh: True면 캐시 무시하고 강제 갱신

        Returns:
            dict: ccxt의 fetch_balance() 반환값
        """
        now = time.time()

        if force_refresh or not self._balance or (now - self._last_fetch_time) > self._cache_duration:
            self._balance = self.exchange.fetch_balance()
            self._last_fetch_time = now
            print("🔄 잔고 정보 갱신됨")

        return self._balance

    def get_free_balance(self, currency: str) -> float:
        """
        특정 통화의 사용 가능 잔고

        Args:
            currency: 통화 코드 (예: "KRW", "BTC", "USDT")

        Returns:
            float: 사용 가능한 잔고
        """
        balance = self.get_balance()
        return balance['free'].get(currency, 0) or 0.0


# =============================================================================
# 마켓 정보 클래스
# =============================================================================

class UpbitMarketInfo:
    """업비트 마켓 정보 및 최소 주문 금액"""

    FEE_RATE = 0.001  # 0.1%
    MIN_ORDER_KRW = 5000

    @classmethod
    def get_fee_multiplier(cls) -> float:
        """수수료 배율 (1.001)"""
        return 1 + cls.FEE_RATE

    @classmethod
    def get_min_order_krw(cls) -> float:
        """KRW 최소 주문 금액 (수수료 포함)"""
        return cls.MIN_ORDER_KRW * cls.get_fee_multiplier()

    @classmethod
    def get_min_order_btc(cls, exchange) -> float:
        """BTC 최소 주문 금액 (KRW 환산)"""
        ticker = exchange.fetch_ticker('BTC/KRW')
        btc_price = ticker['last']
        min_krw = cls.get_min_order_krw()
        return min_krw / btc_price

    @classmethod
    def get_min_order_usdt(cls, exchange) -> float:
        """USDT 최소 주문 금액 (KRW 환산)"""
        ticker = exchange.fetch_ticker('USDT/KRW')
        usdt_price = ticker['last']
        min_krw = cls.get_min_order_krw()
        return min_krw / usdt_price


# =============================================================================
# 티커 변환 유틸리티 클래스
# =============================================================================

class UpbitTickerConverter:
    """티커 변환 유틸리티"""

    @staticmethod
    def to_ccxt_format(ticker: str) -> str:
        """
        업비트 티커를 CCXT 형식으로 변환

        Args:
            ticker: 업비트 형식 티커 (예: "BTCKRW", "ETHBTC")

        Returns:
            str: CCXT 형식 티커 (예: "BTC/KRW", "ETH/BTC")
        """
        if "/" in ticker:
            return ticker

        if ticker.endswith("KRW"):
            base = ticker.removesuffix("KRW")
            return f"{base}/KRW"
        elif ticker.endswith("BTC"):
            base = ticker.removesuffix("BTC")
            return f"{base}/BTC"
        elif ticker.endswith("USDT"):
            base = ticker.removesuffix("USDT")
            return f"{base}/USDT"
        else:
            raise ValueError(f"인식할 수 없는 티커 형식: {ticker}")

    @staticmethod
    def get_quote_currency(ticker: str) -> str:
        """
        결제 통화 추출 (KRW, BTC, USDT)

        Args:
            ticker: 티커 (예: "BTCKRW")

        Returns:
            str: 결제 통화 (예: "KRW")
        """
        ccxt_ticker = UpbitTickerConverter.to_ccxt_format(ticker)
        return ccxt_ticker.split('/')[-1]

    @staticmethod
    def get_base_currency(ticker: str) -> str:
        """
        거래 통화 추출 (BTC, ETH 등)

        Args:
            ticker: 티커 (예: "BTCKRW")

        Returns:
            str: 거래 통화 (예: "BTC")
        """
        ccxt_ticker = UpbitTickerConverter.to_ccxt_format(ticker)
        return ccxt_ticker.split('/')[0]


# =============================================================================
# UpbitTrader 클래스 - 통합 주문 실행
# =============================================================================

class UpbitTrader:
    """
    업비트 주문 실행을 담당하는 통합 트레이더 클래스

    OrderData를 받아 매수/매도를 실행하고 OrderResult를 반환합니다.
    """

    def __init__(self, admin_id: str):
        """
        Args:
            admin_id: 관리자 사용자 ID (DB에서 API 키를 조회하기 위해 필요)
        """
        self.admin_id = admin_id
        self.exchange = create_upbit_exchange(admin_id)

        if not self.exchange:
            raise ValueError(f"업비트 API 키가 DB에 등록되어 있지 않습니다. (admin_id: {admin_id})")

        self.balance_manager = UpbitBalance(self.exchange)
        self.market_info = UpbitMarketInfo()
        self.ticker_converter = UpbitTickerConverter()

    def execute_order(self, order_data) -> 'OrderResult':
        """
        주문 데이터를 받아 매수/매도 실행

        Args:
            order_data: OrderData 인스턴스 또는 dict

        Returns:
            OrderResult: 주문 결과
        """
        from my_models.my_webhook import OrderResult

        # dict를 OrderData로 변환 (하위 호환성)
        if isinstance(order_data, dict):
            from my_models.my_webhook import OrderData
            try:
                order_data = OrderData(**order_data)
            except Exception as e:
                return OrderResult(
                    success=False,
                    failure_message=f"OrderData 변환 실패: {e}"
                )

        order_type = order_data.order

        # 매수 주문
        if order_type in ("open_long", "split_open_long", "reverse_open_long"):
            return self._execute_buy_order(order_data)

        # 매도 주문
        elif order_type in ("close_long", "split_close_long", "open_short", "reverse_open_short"):
            return self._execute_sell_order(order_data)

        else:
            return OrderResult(
                success=False,
                failure_message=f"알 수 없는 주문 유형: {order_type}"
            )

    def _execute_buy_order(self, order_data) -> 'OrderResult':
        """
        매수 주문 실행

        Args:
            order_data: OrderData 인스턴스

        Returns:
            OrderResult: 주문 결과
        """
        from my_models.my_webhook import OrderResult

        try:
            # 1. 티커 변환
            ccxt_symbol = self.ticker_converter.to_ccxt_format(order_data.ticker)
            quote_currency = self.ticker_converter.get_quote_currency(order_data.ticker)

            # 2. 잔고 확인
            available_balance = self.balance_manager.get_free_balance(quote_currency)

            # 3. 최소 주문 금액 계산
            if quote_currency == "KRW":
                min_order_amount = self.market_info.get_min_order_krw()
            elif quote_currency == "BTC":
                min_order_amount = self.market_info.get_min_order_btc(self.exchange)
            elif quote_currency == "USDT":
                min_order_amount = self.market_info.get_min_order_usdt(self.exchange)
            else:
                raise ValueError(f"지원하지 않는 결제 통화: {quote_currency}")

            # 4. 주문 금액 계산 (가격 × 수량)
            order_cost = order_data.price * order_data.contracts

            print(f"💰 주문 금액: {order_cost:,.4f} {quote_currency}")
            print(f"🏦 사용 가능 잔고: {available_balance:,.4f} {quote_currency}")
            print(f"📊 최소 주문 금액: {min_order_amount:,.4f} {quote_currency}")

            # 5. 잔고 검증
            if available_balance < min_order_amount:
                raise InsufficientFundsError(
                    f"잔고 부족: {available_balance:,.4f} < {min_order_amount:,.4f} {quote_currency}"
                )

            if order_cost > available_balance:
                raise InsufficientFundsError(
                    f"주문 금액이 잔고를 초과: {order_cost:,.4f} > {available_balance:,.4f} {quote_currency}"
                )

            # 6. 매수 주문 실행
            print(f"🔵 매수 주문 실행: {ccxt_symbol}, 금액: {order_cost:,.4f} {quote_currency}")

            buy_order = self.exchange.create_market_buy_order(
                symbol=ccxt_symbol,
                amount=order_cost,
                params={'cost': order_cost}
            )

            order_id = buy_order.get('id')
            print(f"✅ 주문 접수 완료: {order_id}")

            # 7. 체결 확인
            filled_order = self._wait_for_fill(order_id, ccxt_symbol)

            # 8. 결과 반환
            avg_price = filled_order.get('average', 0.0)
            filled_amount = filled_order.get('filled', 0.0)
            filled_cost = filled_order.get('cost', 0.0)
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if filled_amount == 0.0:
                return OrderResult(
                    success=False,
                    failure_message=f"체결 실패: 주문 ID {order_id}, 체결 수량 0.0"
                )

            print(f"✅ 매수 체결 완료: 수량 {filled_amount:,.8f}, 평균가 {avg_price:,.4f}")

            return OrderResult(
                success=True,
                order_id=order_data.id,
                comment=order_data.comment,
                symbol=ccxt_symbol,
                order_type="매수",
                price=avg_price,
                amount=filled_amount,
                cost=filled_cost,
                time=current_time
            )

        except InsufficientFundsError as e:
            error_msg = f"💰 잔고 부족: {e}"
            print(error_msg)
            return OrderResult(success=False, failure_message=error_msg)

        except Exception as e:
            error_msg = f"❌ 매수 주문 실패: {e}"
            print(error_msg)
            return OrderResult(success=False, failure_message=error_msg)

    def _execute_sell_order(self, order_data) -> 'OrderResult':
        """
        매도 주문 실행 (분할 매도 버그 수정 포함)

        Args:
            order_data: OrderData 인스턴스

        Returns:
            OrderResult: 주문 결과
        """
        from my_models.my_webhook import OrderResult

        try:
            # 1. 티커 변환
            ccxt_symbol = self.ticker_converter.to_ccxt_format(order_data.ticker)
            base_currency = self.ticker_converter.get_base_currency(order_data.ticker)
            quote_currency = self.ticker_converter.get_quote_currency(order_data.ticker)

            # 2. 보유 자산 확인
            available_balance = self.balance_manager.get_free_balance(base_currency)

            if available_balance == 0.0:
                raise InsufficientFundsError(
                    f"매도 불가\n{base_currency} 보유 자산이 0 입니다."
                )

            # 3. 최소 주문 금액 계산 (결제 통화 기준)
            if quote_currency == "KRW":
                min_order_amount = self.market_info.get_min_order_krw()
            elif quote_currency == "BTC":
                min_order_amount = self.market_info.get_min_order_btc(self.exchange)
            elif quote_currency == "USDT":
                min_order_amount = self.market_info.get_min_order_usdt(self.exchange)
            else:
                raise ValueError(f"지원하지 않는 결제 통화: {quote_currency}")

            # 4. 현재가 조회 (매도 후 잔량 검증용)
            ticker_info = self.exchange.fetch_ticker(ccxt_symbol)
            current_price = ticker_info['last']

            # 5. 매도 수량 결정 로직
            request_amount = order_data.contracts
            order_type = order_data.order

            final_sell_amount = 0.0
            warning_note = ""  # 경고 메시지 저장용

            if order_type == "close_long":
                # 전체 청산
                final_sell_amount = available_balance
                print(f"🔴 전체 청산: {final_sell_amount:,.8f} {base_currency}")

            elif order_type in ("open_short", "reverse_open_short"):
                # 포지션 전환 (전체 매도)
                final_sell_amount = available_balance
                print(f"🔴 포지션 전환 (전체 매도): {final_sell_amount:,.8f} {base_currency}")

            elif order_type == "split_close_long":
                # 분할 매도 로직 (버그 수정)
                remaining_amount = available_balance - request_amount
                remaining_value = remaining_amount * current_price

                print(f"📊 현재가: {current_price:,.4f} {quote_currency}")
                print(f"📦 보유 수량: {available_balance:,.8f} {base_currency}")
                print(f"📤 요청 수량: {request_amount:,.8f} {base_currency}")
                print(f"📉 매도 후 남을 수량: {remaining_amount:,.8f} {base_currency}")
                print(f"💵 매도 후 남을 금액: {remaining_value:,.4f} {quote_currency}")
                print(f"⚖️ 최소 주문 금액: {min_order_amount:,.4f} {quote_currency}")

                if remaining_value < min_order_amount:
                    # 매도 후 잔량이 최소 주문 금액 미달 → 전체 매도
                    final_sell_amount = available_balance
                    print(f"⚠️ 잔량 미달 방지: 강제 전체 매도 ({final_sell_amount:,.8f} {base_currency})")

                    space = "\u2002"
                    # 경고 메시지 생성 (원래 상세한 메시지 유지)
                    warning_note = (
                        f"매도 후 최소 주문 금액 {min_order_amount:,.4f} {quote_currency} 보다 낮은,\n"
                        f"{remaining_value:,.4f} {quote_currency} 의 남는 잔량이 감지되었습니다.\n"
                        f"최소 주문 금액 미충족 오류를 방지하기 위해\n"
                        f"강제로 전체 매도를 실행하였습니다.\n\n"
                        f"**보유 수량**{space * 7}:{space}{available_balance:,.8f} {base_currency}\n"
                        f"**요청 수량**{space * 7}:{space}{request_amount:,.8f} {base_currency}\n"
                        f"**매도 후 남는 금액**{space * 1}:{space}{remaining_value:,.4f} {quote_currency}\n"
                        f"**최소 주문 금액**{space * 3}:{space}{min_order_amount:,.4f} {quote_currency}\n\n"
                        f"**주문 판단 결과**\n"
                        f"**강제 전체 매도**{space * 3}:{space}{final_sell_amount:,.8f} {base_currency}"
                    )
                else:
                    # 분할 매도
                    final_sell_amount = request_amount
                    print(f"✅ 분할 매도: {final_sell_amount:,.8f} {base_currency}")

            else:
                raise ValueError(f"알 수 없는 매도 주문 유형: {order_type}")

            # 6. 최종 검증
            if final_sell_amount <= 0.0:
                raise ValueError(f"매도 수량이 0 이하: {final_sell_amount}")

            if final_sell_amount > available_balance:
                raise InsufficientFundsError(
                    f"매도 수량이 보유량 초과: {final_sell_amount:,.8f} > {available_balance:,.8f}"
                )

            # 7. 매도 주문 실행
            print(f"🔴 매도 주문 실행: {ccxt_symbol}, 수량: {final_sell_amount:,.8f} {base_currency}")

            sell_order = self.exchange.create_market_sell_order(
                symbol=ccxt_symbol,
                amount=final_sell_amount
            )

            order_id = sell_order.get('id')
            print(f"✅ 주문 접수 완료: {order_id}")

            # 8. 체결 확인
            filled_order = self._wait_for_fill(order_id, ccxt_symbol)

            # 9. 결과 반환
            avg_price = filled_order.get('average', 0.0)
            filled_amount = filled_order.get('filled', 0.0)
            filled_cost = filled_order.get('cost', 0.0)
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if filled_amount == 0.0:
                return OrderResult(
                    success=False,
                    failure_message=f"체결 실패: 주문 ID {order_id}, 체결 수량 0.0"
                )

            print(f"✅ 매도 체결 완료: 수량 {filled_amount:,.8f}, 평균가 {avg_price:,.4f}")

            return OrderResult(
                success=True,
                order_id=order_data.id,
                comment=order_data.comment,
                symbol=ccxt_symbol,
                order_type="매도",
                price=avg_price,
                amount=filled_amount,
                cost=filled_cost,
                time=current_time,
                note=warning_note if warning_note else None
            )

        except InsufficientFundsError as e:
            error_msg = f"💰 자산 부족: {e}"
            print(error_msg)
            return OrderResult(success=False, failure_message=error_msg)

        except Exception as e:
            error_msg = f"❌ 매도 주문 실패: {e}"
            print(error_msg)
            return OrderResult(success=False, failure_message=error_msg)

    def _wait_for_fill(self, order_id: str, symbol: str, max_retries: int = 5, wait_time: float = 1.0) -> dict:
        """
        주문 체결 확인 (Polling 방식)

        Args:
            order_id: 주문 ID
            symbol: 심볼 (CCXT 형식)
            max_retries: 최대 재시도 횟수
            wait_time: 재시도 간격 (초)

        Returns:
            dict: 체결된 주문 정보 (ccxt.fetch_order 결과)
        """
        filled_order = None

        for i in range(max_retries):
            filled_order = self.exchange.fetch_order(id=order_id, symbol=symbol)

            status = filled_order.get('status')
            filled_amount = filled_order.get('filled', 0.0)

            if status == 'closed' or filled_amount > 0:
                print(f"✅ 체결 확인 완료: {order_id} (시도 {i+1}/{max_retries})")
                break

            print(f"⌛ 체결 대기 중... ({i+1}/{max_retries})")
            time.sleep(wait_time)

        return filled_order
