from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

from src.connectors.swap.bybit_swap_connector import BybitSwapConnector

PAUSE_INTERVAL_IN_SECONDS = 30
# size per leg
AMOUNT_SIZE_USD_PER_SIDE = 50

class Direction(Enum):
    SHORT = 1
    LONG = 2

# where spread B/A
@dataclass
class OpenPositionInfo:
    ticker_a: str
    ticker_b: str
    coins_a: float
    coins_b: float
    close_direction: Direction

# Load keys from .env
load_dotenv()
# change bybit keys
exchange = BybitSwapConnector(True)

def open_position(_position: OpenPositionInfo):
    if _position.close_direction == Direction.LONG:
        exchange.create_market_buy_order(_position.ticker_b, _position.coins_b)  # Откупаем B
        exchange.create_market_sell_order(_position.ticker_a, _position.coins_a)  # Продаем A
    if _position.close_direction == Direction.SHORT:
        exchange.create_market_sell_order(_position.ticker_b, _position.coins_b)  # Продаем B
        exchange.create_market_buy_order(_position.ticker_a, _position.coins_a)  # Откупаем A

position = OpenPositionInfo(
        ticker_a='JELLYJELLY/USDT:USDT',
        ticker_b='ANIME/USDT:USDT',
        coins_a=220.0,
        coins_b=1990.0,
        close_direction=Direction.SHORT,
    )
open_position(position)