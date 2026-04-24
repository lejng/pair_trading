from typing import Literal

from ccxt.base.types import OrderBook

from src.helpers.logger import logger_instance

def get_execution_price(order_book: OrderBook, amount_in_currency, side: Literal['buy', 'sell'], slippage_buffer = 1.2):
    """Считает среднюю цену исполнения с учетом глубины стакана"""
    try:
        orders = order_book['asks'] if side == 'buy' else order_book['bids']

        total_qty = 0.0
        total_spent = 0.0
        amount_in_currency_adjusted = slippage_buffer * amount_in_currency

        for order in orders:
            price = float(order[0])
            qty = float(order[1])
            level_vol_usd = price * qty

            needed_usd = amount_in_currency_adjusted - total_spent

            if level_vol_usd >= needed_usd:
                # Этот уровень полностью закрывает остаток
                fill_qty = needed_usd / price
                total_qty += fill_qty
                total_spent += needed_usd
                return total_spent / total_qty
            else:
                # Забираем весь уровень и идем глубже
                total_qty += qty
                total_spent += level_vol_usd

        return None  # Недостаточно ликвидности в топ-20
    except Exception as e:
        logger_instance.error(f"Error during processing orderbook: {e}")
        return None
