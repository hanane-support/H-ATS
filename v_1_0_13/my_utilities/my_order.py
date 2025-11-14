

# my_order.py
# 트레이딩뷰 웹훅에서 받은 포지션 정보를 기반으로 주문 로직을 판단하는 파일


def my_order(
    _prev_market_position: str,
    _action: str,
    _market_position: str,
) -> str:
    """
    웹훅에서 받은 포지션 정보로 현재 주문 동작을 판단하는 함수.
    (Args 및 Returns 설명 생략)
    """
    
    # 🌟 초기화: 매칭되는 조건이 없을 경우의 기본값
    order = "none"
    
    try:
        # ✅ 입력값 검증
        valid_positions = {"flat", "long", "short"}
        valid_actions = {"buy", "sell"}

        if _prev_market_position not in valid_positions:
            raise ValueError(f"잘못된 prev_market_position 값: {_prev_market_position}")
        if _market_position not in valid_positions:
            raise ValueError(f"잘못된 market_position 값: {_market_position}")
        if _action not in valid_actions:
            raise ValueError(f"잘못된 action 값: {_action}")

        # --- 디버깅용 출력 ---
        print("──────────────────────────────")
        print("📩 my_order 호출 정보:")
        print(f"     prev_market_position: {_prev_market_position}")
        print(f"     action: {_action}")
        print(f"     market_position: {_market_position}")

        # 🔹 롱 관련 로직
        if _prev_market_position == "flat" and _action == "buy" and _market_position == "long":
            order = "open_long"  # 롱 진입
        elif _prev_market_position == "long" and _action == "buy" and _market_position == "long":
            order = "split_open_long"  # 롱 추가 진입
        elif _prev_market_position == "long" and _action == "sell" and _market_position == "long":
            order = "split_close_long"  # 롱 분할 종료
        elif _prev_market_position == "long" and _action == "sell" and _market_position == "flat":
            order = "close_long"  # 롱 종료
        elif _prev_market_position == "long" and _action == "sell" and _market_position == "short":
            order = "reverse_open_short"  # 롱 종료 + 숏 진입

        # 🔹 숏 관련 로직
        elif _prev_market_position == "flat" and _action == "sell" and _market_position == "short":
            order = "open_short"  # 숏 진입
        elif _prev_market_position == "short" and _action == "sell" and _market_position == "short":
            order = "split_open_short"  # 숏 추가 진입
        elif _prev_market_position == "short" and _action == "buy" and _market_position == "short":
            order = "split_close_short"  # 숏 분할 종료
        elif _prev_market_position == "short" and _action == "buy" and _market_position == "flat":
            order = "close_short"  # 숏 종료
        elif _prev_market_position == "short" and _action == "buy" and _market_position == "long":
            order = "reverse_open_long"  # 숏 종료 + 롱 진입
        
        
        # 🌟 이제 order 변수에 값이 할당되었으므로, 프린트할 수 있습니다.
        print("✅  주문 판단 결과:", order)
        print("──────────────────────────────")

        # 🔹 최종 결과를 반환
        return order

    except ValueError as ve:
         # 입력값 검증 오류
        print("🚨 my_order 입력값 오류 발생!")
        print(f"❗ 오류 내용: {ve}")
        # 오류 발생 시 기본값 반환
        return "none"
        
    except Exception as e:
        # 예기치 않은 오류가 발생했을 경우 안전하게 처리
        print("🚨 my_order 실행 중 예기치 않은 오류 발생!")
        print(f"❗ 오류 내용: {e}")
        return "none"











# # my_logic.py
# # 트레이딩뷰 웹훅에서 받은 포지션 정보를 기반으로 주문 로직을 판단하는 파일

# def my_order(
#     prev_market_position: str,
#     action: str,
#     market_position: str,
#     # exchange: Optional[str] = None,
#     # ticker: Optional[str] = None,
#     # price: Optional[float] = None,
#     # contracts: Optional[float] = None
# ) -> str:
#     """
#     웹훅에서 받은 포지션 정보로 현재 주문 동작을 판단하는 함수.

#     Args:
#         prev_market_position (str): 이전 포지션 상태 ("flat", "long", "short")
#         action (str): 트레이딩뷰의 주문 방향 ("buy" or "sell")
#         market_position (str): 현재 포지션 상태 ("flat", "long", "short")

#     Returns:
#         str: 수행해야 할 동작 ("open_long", "split_open_long", "split_close_long", "close_long", 
#              "reverse_open_short", "open_short", "add_open_short", "split_close_short", 
#              "close_short", "reverse_open_long", "none")
#     """

#     # --- 디버깅용 출력 ---
#     print("──────────────────────────────")
#     print("📩 my_order 호출 정보:")
#     print(f"    prev_market_position: {prev_market_position}")
#     print(f"    action: {action}")
#     print(f"    market_position: {market_position}")
#     print("──────────────────────────────")

#     # 🔹 롱 관련 로직
#     if prev_market_position == "flat" and action == "buy" and market_position == "long":
#         return "open_long"  # 롱 진입
#     elif prev_market_position == "long" and action == "buy" and market_position == "long":
#         return "split_open_long"  # 롱 추가 진입
#     elif prev_market_position == "long" and action == "sell" and market_position == "long":
#         return "split_close_long"  # 롱 분할 종료
#     elif prev_market_position == "long" and action == "sell" and market_position == "flat":
#         return "close_long"  # 롱 종료
#     elif prev_market_position == "long" and action == "sell" and market_position == "short":
#         return "reverse_open_short"  # 롱 종료 + 숏 진입

#     # 🔹 숏 관련 로직
#     elif prev_market_position == "flat" and action == "sell" and market_position == "short":
#         return "open_short"  # 숏 진입
#     elif prev_market_position == "short" and action == "sell" and market_position == "short":
#         return "add_open_short"  # 숏 추가 진입
#     elif prev_market_position == "short" and action == "buy" and market_position == "short":
#         return "split_close_short"  # 숏 분할 종료
#     elif prev_market_position == "short" and action == "buy" and market_position == "flat":
#         return "close_short"  # 숏 종료
#     elif prev_market_position == "short" and action == "buy" and market_position == "long":
#         return "reverse_open_long"  # 숏 종료 + 롱 진입

#     # 🔹 매치되는 조건이 없을 때
#     print("⚠️ 조건에 맞는 주문 로직이 없습니다.")
#     return "none"
