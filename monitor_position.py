from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

from src.connectors.swap.bybit_swap_connector import BybitSwapConnector
from src.helpers.logger import logger_instance
from src.helpers.spread_helper import get_execution_price

PAUSE_INTERVAL_IN_SECONDS = 30
# size per leg
AMOUNT_SIZE_USD_PER_SIDE = 50

class Direction(Enum):
    SHORT = 1
    LONG = 2

# where spread B/A
@dataclass
class PositionInfo:
    ticker_a: str
    ticker_b: str
    coins_a: float
    coins_b: float
    stop_loss_price: float
    take_profit_price: float
    close_direction: Direction
    is_closed: bool

# Load keys from .env
load_dotenv()
# change bybit keys
exchange = BybitSwapConnector(True)

def close_position(position: PositionInfo):
    if position.close_direction == Direction.LONG:
        exchange.create_market_buy_order(position.ticker_b, position.coins_b)  # Откупаем B
        exchange.create_market_sell_order(position.ticker_a, position.coins_a)  # Продаем A
    if position.close_direction == Direction.SHORT:
        exchange.create_market_sell_order(position.ticker_b, position.coins_b)  # Продаем B
        exchange.create_market_buy_order(position.ticker_a, position.coins_a)  # Откупаем A

def get_current_spread(position: PositionInfo):
    orderbook_a = exchange.get_order_book(position.ticker_a)
    orderbook_b = exchange.get_order_book(position.ticker_b)
    price_a_buy = get_execution_price(orderbook_a, AMOUNT_SIZE_USD_PER_SIDE, 'buy')
    price_a_sell = get_execution_price(orderbook_a, AMOUNT_SIZE_USD_PER_SIDE, 'sell')
    price_b_buy = get_execution_price(orderbook_b, AMOUNT_SIZE_USD_PER_SIDE, 'buy')
    price_b_sell = get_execution_price(orderbook_b, AMOUNT_SIZE_USD_PER_SIDE, 'sell')
    if position.close_direction == Direction.LONG:
    # return when for close position we need long
        return price_b_buy / price_a_sell
    # return when for close position we need short
    return price_b_sell / price_a_buy

def close_position_by_take_or_stop(position: PositionInfo, current_spread: float) -> bool:
    if position.close_direction == Direction.LONG:
        logger_instance.info(f"Current long spread: {current_spread}")
        if current_spread >= position.stop_loss_price:
            logger_instance.info("Execute stop loss")
            close_position(position)
            return True
        if current_spread <= position.take_profit_price:
            logger_instance.info("Execute take profit")
            close_position(position)
            return True

    if position.close_direction == Direction.SHORT:
        logger_instance.info(f"Current short spread: {current_spread}")
        if current_spread <= position.stop_loss_price:
            logger_instance.info("Execute stop loss")
            close_position(position)
            return True
        if current_spread >= position.take_profit_price:
            logger_instance.info("Execute take profit")
            close_position(position)
            return True

    return False

def monitor_positions(_positions: list[PositionInfo]):
    while True:
        for position in _positions:
            if position.is_closed:
                logger_instance.info(f"Position (ticker A: {position.ticker_a}, ticker B: {position.ticker_b}) already closed")
                continue
            logger_instance.info(f"Checking position (ticker A: {position.ticker_a}, ticker B: {position.ticker_b})...")
            try:
                current_spread = get_current_spread(position)
                is_position_closed = close_position_by_take_or_stop(position, current_spread)
                position.is_closed = is_position_closed
            except Exception as e:
                logger_instance.info(e)
            time.sleep(1)
        logger_instance.info("Waiting...")
        time.sleep(PAUSE_INTERVAL_IN_SECONDS)

# ------------------ Main ---------------------------------

positions = [
    PositionInfo(
        ticker_a='JELLYJELLY/USDT:USDT',
        ticker_b='ANIME/USDT:USDT',
        coins_a=220.0,
        coins_b=1990.0,
        stop_loss_price=0.11050000,
        take_profit_price=0.10553326,
        close_direction=Direction.LONG,
        is_closed=True
    )
]
monitor_positions(positions)
