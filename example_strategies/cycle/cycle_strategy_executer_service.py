import datetime
from typing import Tuple, Optional

from sqlalchemy.orm import scoped_session, Session
from trading_platform.exchanges.data.enums.order_side import OrderSide
from trading_platform.exchanges.data.enums.order_status import OrderStatus
from trading_platform.exchanges.data.financial_data import FinancialData, one, zero
from trading_platform.exchanges.data.order import Order
from trading_platform.exchanges.data.pair import Pair
from trading_platform.exchanges.exchange_service_abc import ExchangeServiceAbc
from trading_platform.exchanges.order_execution_service import OrderExecutionService
from trading_platform.storage.daos.strategy_execution_dao import StrategyExecutionDao
from trading_platform.strategy.services.strategy_executer_service_abc import StrategyExecuterServiceAbc
from trading_platform.strategy.strategy_execution import StrategyExecution


class CycleStrategyExecuterService(StrategyExecuterServiceAbc):
    strategy_base_id: str = 'cycle_strategy'

    def __init__(self, **kwargs):
        self.logger = kwargs.get('logger')
        self.order_execution_service: OrderExecutionService = kwargs.get('order_execution_service')
        self.scoped_session_maker: scoped_session = kwargs.get('scoped_session_maker')
        self.strategy_execution_dao: StrategyExecutionDao = kwargs.get('strategy_execution_dao')

        self.strategy_execution: Optional[StrategyExecution] = None
        self.buy_window: Tuple[float, float] = kwargs.get('buy_window')
        self.sell_window: Tuple[float, float] = kwargs.get('sell_window')
        self.pair: Pair = kwargs.get('pair')
        self.order_padding_percent: FinancialData = kwargs.get('order_padding_percent')
        self.balance_percent_per_trade: FinancialData = kwargs.get('balance_percent_per_trade')

    def refresh_state(self, repeat: bool, refresh_freq_sec: int):
        """
        Preload the exchange state for faster trade execution.

        Args:
            repeat:
            refresh_freq_sec:

        Returns:

        """

    def initialize(self, strategy_id: str):
        strategy_execution: StrategyExecution = StrategyExecution(**{
            'strategy_id': strategy_id,
            'state': {
                'buy_order_count': 0,
                'sell_order_count': 0
            }
        })
        self.strategy_execution = self.strategy_execution_dao.save(self.scoped_session_maker(),
                                                                   popo=strategy_execution, commit=True)

    def step(self, **kwargs):
        """
        Args:
         kwargs: Dict
            exchange: ExchangeServiceAbc
            now_datetime: datetime.datetime
            check_if_order_filled: bool

        """
        exchange: ExchangeServiceAbc = kwargs.get('exchange')
        now: datetime.datetime = kwargs.get('now_datetime')
        now_hour = now.hour
        order_side: Optional[int] = None
        if self.buy_window[0] <= now_hour < self.buy_window[1]:
            order_side = OrderSide.buy
        elif self.sell_window[0] <= now_hour < self.sell_window[1]:
            order_side = OrderSide.sell

        if order_side is not None:
            exchange.fetch_balances()
            exchange.fetch_latest_tickers()

            if order_side == OrderSide.buy:
                order_price: FinancialData = FinancialData(exchange.get_ticker(self.pair.name).ask) * (
                        one + self.order_padding_percent)
                order_amount: FinancialData = self.balance_percent_per_trade * exchange.get_balance(
                    self.pair.base).free / order_price
            else:
                order_amount: FinancialData = self.balance_percent_per_trade * exchange.get_balance(
                    self.pair.quote).free
                order_price: FinancialData = FinancialData(exchange.get_ticker(self.pair.name).bid) * (
                        one - self.order_padding_percent)

            if order_amount > zero:
                if order_side == OrderSide.buy:
                    self.strategy_execution.state['buy_order_count'] += 1
                else:
                    self.strategy_execution.state['sell_order_count'] += 1
                session: Session = self.scoped_session_maker()
                order: Order = Order(**{
                    'exchange_id': exchange.exchange_id,

                    'amount': order_amount,
                    'price': order_price,

                    'base': self.pair.base,
                    'quote': self.pair.quote,
                    'order_side': order_side,
                    'order_status': OrderStatus.open
                })
                self.order_execution_service.execute_order(order, session=session, write_pending_order=True,
                                                           check_if_order_filled=kwargs.get('check_if_order_filled'))
                self.strategy_execution_dao.update_fetch_by_column(
                    session=session, column_name='strategy_execution_id',
                    column_value=self.strategy_execution.strategy_execution_id,
                    update_dict={
                        'state': self.strategy_execution.state
                    },
                    commit=True)
