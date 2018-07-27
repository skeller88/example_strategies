import os

from trading_platform.exchanges.data.enums import exchange_ids
from trading_platform.exchanges.data.financial_data import FinancialData


class CycleProperties:
    # How many times per hour to check for a trade
    executions_per_hour: int = int(os.environ.get('EXECUTIONS_PER_HOUR', 1))
    # How many orders to execute per hour, if within the buy or sell window
    orders_per_hour: int = int(os.environ.get('ORDERS_PER_HOUR', 60))
    # Add padding to the orders to increase the likelihood the orders will get filled
    order_padding_percent: FinancialData = FinancialData(os.environ.get('ORDER_PADDING_PERCENT', 0.02))
    balance_percent_per_trade: FinancialData = FinancialData(os.environ.get('BALANCE_PERCENT_PER_TRADE', 0.25))

    base_currency: str = os.environ.get('BASE_CURRENCY', 'USDT')
    quote_currency: str = os.environ.get('QUOTE_CURRENCY', 'BTC')
    initial_base_capital: FinancialData = FinancialData(os.environ.get('INITIAL_BASE_CAPITAL', 10000))

    # id of exchange on which to trade
    exchange_id_to_trade: int = int(os.environ.get('EXCHANGE_ID_TO_TRADE', exchange_ids.binance))
    # hour start of buy window in UTC
    buy_window_utc_hour_start: int = int(os.environ.get('BUY_WINDOW_UTC_HOUR_START', 20))
    # hour end of buy window in UTC
    buy_window_utc_hour_end: int = int(os.environ.get('BUY_WINDOW_UTC_HOUR_END', 22))

    # hour start of sell window in UTC
    sell_window_utc_hour_start: int = int(os.environ.get('SELL_WINDOW_UTC_HOUR_START', 11))
    # hour end of sell window in UTC
    sell_window_utc_hour_end: int = int(os.environ.get('SELL_WINDOW_UTC_HOUR_END', 13))
