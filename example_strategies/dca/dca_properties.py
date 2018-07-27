import os

from trading_platform.exchanges.data.enums import exchange_ids
from trading_platform.exchanges.data.financial_data import FinancialData


class DcaProperties:
    # How many times per day to check for a trade
    executions_per_month: int = int(os.environ.get('EXECUTIONS_PER_MONTH', 4))
    # Add padding to the orders to increase the likelihood the orders will get filled
    order_padding_percent: FinancialData = FinancialData(os.environ.get('ORDER_PADDING_PERCENT', 0.02))
    balance_percent_per_trade: FinancialData = FinancialData(os.environ.get('BALANCE_PERCENT_PER_TRADE', 0.1))

    base_currency: str = os.environ.get('BASE_CURRENCY', 'USDT')
    quote_currency: str = os.environ.get('QUOTE_CURRENCY', 'BTC')
    initial_base_capital: FinancialData = FinancialData(os.environ.get('INITIAL_BASE_CAPITAL', 10000))

    # id of exchange on which to trade
    exchange_id_to_trade: int = int(os.environ.get('EXCHANGE_ID_TO_TRADE', exchange_ids.binance))
