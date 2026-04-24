from abc import ABC, abstractmethod

import pandas as pd
from ccxt import Exchange
from ccxt.base.types import OrderBook, Order

from src.helpers.logger import logger_instance


class CommonConnector(ABC):

    def __init__(self):
        self.logger = logger_instance

    def get_markets(self, reload=False) -> dict[str, dict]:
        try:
            markets = self.get_exchange().load_markets(reload=reload)
            return markets
        except Exception as e:
            self.logger.error(f"Error during load markets, exchange: {self.get_exchange_name()}, error: {e}")
            return {}

    def get_symbols_by_quote(self, quote: str = 'EUR') -> list[str]:
        markets = self.get_markets()
        return [symbol for symbol, info in markets.items() if info['quote'] == quote]

    def get_symbol_by_base_and_quote(self, base: str = 'BTC', quote: str = 'USDT') -> str | None:
        markets = self.get_markets()
        for symbol, info in markets.items():
            if info['quote'] == quote and info['base'] == base:
                return symbol
        return None

    def get_symbols(self) -> list[str]:
        return list(self.get_markets().keys())

    def get_ohlcv(self, symbol: str, timeframe='1h', limit=500) -> pd.DataFrame:
        try:
            data = self.get_exchange().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            self.logger.error(f"Error during getting ohlcv data, exchange: {self.get_exchange_name()}, symbol: {symbol}, error: {e}")
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df.set_index('timestamp')

    def get_order_book(self, symbol: str, limit=100) -> OrderBook | None:
        try:
            order_book = self.get_exchange().fetch_order_book(symbol, limit=limit)
            return order_book
        except Exception as e:
            self.logger.error(f"Error during getting orderbook for symbol: {symbol} on exchange: {self.get_exchange_name()}, error: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int = 1):
        try:
            self.get_exchange().set_leverage(leverage, symbol)
        except Exception as e:
            self.logger.error(f"Error during setting leverage for symbol: {symbol} on exchange: {self.get_exchange_name()}, error: {e}")

    def calculate_contracts(self, symbol: str, coins: float):
        try:
            contract_size = self.get_exchange().market(symbol).get('contractSize', 1)
            contracts = coins / contract_size
            qty_contracts = self.get_exchange().amount_to_precision(symbol, contracts)
            self.logger.info(f"{coins} coins is {qty_contracts} contracts for symbol: {symbol} on exchange: {self.get_exchange_name()}")
            if float(qty_contracts) <= 0:
                return None
            return qty_contracts
        except Exception as e:
            self.logger.error(f"Error during calculation contracts for symbol: {symbol} on exchange: {self.get_exchange_name()}, coins: {coins}, error: {e}")
            return None

    def create_market_buy_order(self, symbol: str, coins: float, leverage: int = 1) -> Order | None:
        self.set_leverage(symbol, leverage)
        try:
            qty_contracts = self.calculate_contracts(symbol, coins)
            if qty_contracts:
                return self.get_exchange().create_market_buy_order(symbol, qty_contracts)
        except Exception as e:
            self.logger.error(f"Error during create market buy order for symbol: {symbol} on exchange: {self.get_exchange_name()}, coins: {coins}, error: {e}")
        return None

    def create_market_sell_order(self, symbol: str, coins: float, leverage: int = 1) -> Order | None:
        self.set_leverage(symbol, leverage)
        try:
            qty_contracts = self.calculate_contracts(symbol, coins)
            if qty_contracts:
                return self.get_exchange().create_market_sell_order(symbol, qty_contracts)
        except Exception as e:
            self.logger.error(f"Error during create market sell order for symbol: {symbol} on exchange: {self.get_exchange_name()}, coins: {coins}, error: {e}")
        return None

    @abstractmethod
    def get_exchange(self) -> Exchange:
        pass

    @abstractmethod
    def get_exchange_name(self) -> str:
        pass