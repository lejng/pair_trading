import os

import ccxt
from ccxt import Exchange

from src.connectors.common_connector import CommonConnector


class BybitSwapConnector(CommonConnector):

    def __init__(self, use_auth: bool = True, api_key_name = 'BYBIT_API_KEY', secret_key_name = 'BYBIT_API_SECRET'):
        super().__init__()
        config = {
            'enableRateLimit': True,
            'options': {
                'createMarketBuyOrderRequiresPrice': False,
                'enableUnifiedAccount': True,
                'defaultType': 'swap',
                'fetchMarkets': {
                    'types': ['linear']
                }
            }
        }
        if use_auth:
            config.update({
                'apiKey': os.getenv(api_key_name),
                'secret': os.getenv(secret_key_name),
            })
        self.exchange = ccxt.bybit(config)

    def get_exchange(self) -> Exchange:
        return self.exchange

    def get_exchange_name(self) -> str:
        return 'bybit_swap'

