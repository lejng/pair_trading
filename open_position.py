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
    open_direction: Direction
    leverage: int = 1

# Load keys from .env
load_dotenv()
# change bybit keys
exchange = BybitSwapConnector(True)

def open_position(_position: OpenPositionInfo):
    if _position.open_direction == Direction.LONG:
        exchange.create_market_buy_order(_position.ticker_b, _position.coins_b, _position.leverage)  # Откупаем B
        exchange.create_market_sell_order(_position.ticker_a, _position.coins_a, _position.leverage)  # Продаем A
    if _position.open_direction == Direction.SHORT:
        exchange.create_market_sell_order(_position.ticker_b, _position.coins_b, _position.leverage)  # Продаем B
        exchange.create_market_buy_order(_position.ticker_a, _position.coins_a, _position.leverage)  # Откупаем A

position = OpenPositionInfo(
                ticker_a='JASMY/USDT:USDT',
                ticker_b='DOGE/USDT:USDT',
                coins_a=2665.0,
                coins_b=137.0,
                open_direction=Direction.SHORT,
                #open_direction=Direction.LONG,
            )

open_position(position)