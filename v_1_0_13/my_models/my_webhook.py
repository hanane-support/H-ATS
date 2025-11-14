# my_models.py
# 트레이딩 시스템의 데이터 모델 정의

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderData:
    """트레이딩뷰 웹훅 데이터를 담는 모델"""
    id: str
    comment: str
    alert_time: str
    exchange: str
    ticker: str
    prev_market_position: str
    action: str
    market_position: str
    order: str
    price: float
    contracts: float

    def __post_init__(self):
        """데이터 타입 변환 및 검증"""
        # 문자열을 float로 변환
        if isinstance(self.price, str):
            self.price = float(self.price)
        if isinstance(self.contracts, str):
            self.contracts = float(self.contracts)

        # 기본 검증
        if not self.ticker:
            raise ValueError("ticker는 필수입니다")
        if self.price <= 0:
            raise ValueError("price는 0보다 커야 합니다")
        if self.contracts <= 0:
            raise ValueError("contracts는 0보다 커야 합니다")


@dataclass
class OrderResult:
    """주문 결과를 담는 모델"""
    success: bool
    order_id: Optional[str] = None
    comment: Optional[str] = None  # 주문 코멘트 추가
    symbol: Optional[str] = None
    order_type: Optional[str] = None  # "매수" or "매도"
    price: Optional[float] = None
    amount: Optional[float] = None
    cost: Optional[float] = None
    time: Optional[str] = None
    failure_message: Optional[str] = None
    note: Optional[str] = None  # 경고 메시지 등 추가 안내사항

    def to_dict(self) -> dict:
        """
        디스코드 전송용 딕셔너리로 변환
        기존 my_discord.py의 send_discord() 함수와 100% 호환
        """
        if self.success:
            return {
                "id": self.order_id,
                "comment": self.comment,
                "time": self.time,
                "exchange": "UPBIT",
                "symbol": self.symbol,
                "order_type": self.order_type,
                "price": self.price,
                "amount": self.amount,
                "cost": self.cost,
                "success": True
            }
        else:
            return {
                "success": False,
                "failure_message": self.failure_message
            }
