import sys
from time import sleep

import argparse
import datetime
import logging
import os
import pandas
import random
from trading_platform.analytics.profit_service import ProfitService
from trading_platform.exchanges.backtest import backtest_subclasses
from trading_platform.exchanges.backtest.backtest_exchange_service import BacktestExchangeService
from trading_platform.exchanges.data.pair import Pair
from trading_platform.exchanges.data.ticker import Ticker
from trading_platform.exchanges.live.live_exchange_service import LiveExchangeService
from trading_platform.exchanges.ticker_service import TickerService
from typing import Callable, Dict, List, Optional

sys.path.append(os.getcwd())

from examples.cycle.cycle_properties import CycleProperties
from examples.cycle.cycle_strategy_executer_service import CycleStrategyExecuterService


import daemon
from trading_platform.aws_utils.parameter_store_service import ParameterStoreService
from trading_platform.core.services.logging_service import LoggingService
from trading_platform.exchanges.exchange_service_abc import ExchangeServiceAbc
from trading_platform.exchanges.live import live_subclasses
from trading_platform.exchanges.order_execution_service import OrderExecutionService
from trading_platform.properties.env_properties import EnvProperties, DatabaseProperties, OrderExecutionProperties
from trading_platform.storage.daos.order_dao import OrderDao
from trading_platform.storage.daos.strategy_execution_dao import StrategyExecutionDao
from trading_platform.storage.sql_alchemy_dtos import table_classes
from trading_platform.storage.sql_alchemy_engine import SqlAlchemyEngine
from trading_platform.utils.datetime_operations import datetime_now_with_utc_offset, strftime_minutes


def main(logger: logging.Logger, live: bool, ticker_dir: str, profit_summary_dir: str):
    mode_name: str = 'live' if live else 'backtest_results'
    logger.info('running cycle strategy in {0} mode'.format(mode_name))

    table_classes.exchange_data_tables()

    if EnvProperties.is_prod:
        ParameterStoreService.load_properties_from_parameter_store_and_set('database_credentials')
        engine_maker_method: Callable = SqlAlchemyEngine.rds_engine
    else:
        engine_maker_method: Callable = SqlAlchemyEngine.local_engine_maker

    DatabaseProperties.set_properties_from_env_variables()
    engine = engine_maker_method()
    engine.add_engine_pidguard()
    engine.update_tables()

    if live:
        exchanges_by_id: Dict[int, ExchangeServiceAbc] = live_subclasses.instantiate(
            subclasses=live_subclasses.all_live())
    else:
        exchanges_by_id: Dict[int, ExchangeServiceAbc] = backtest_subclasses.instantiate()

    order_execution_service: OrderExecutionService = OrderExecutionService(**{
        'logger': logger,
        'exchanges_by_id': exchanges_by_id,
        'order_dao': OrderDao(),
        'multithreaded': False,
        'num_order_status_checks': OrderExecutionProperties.num_order_status_checks,
        'sleep_time_sec_between_order_checks': OrderExecutionProperties.sleep_time_sec_between_order_checks,
        'scoped_session_maker': engine.scoped_session_maker
    })

    pair: Pair = Pair(base=CycleProperties.base_currency, quote=CycleProperties.quote_currency)
    cycle_strategy_executer_service: CycleStrategyExecuterService = CycleStrategyExecuterService(**{
        'order_execution_service': order_execution_service,
        'strategy_execution_dao': StrategyExecutionDao(),
        'scoped_session_maker': engine.scoped_session_maker,

        'pair': pair,

        'buy_window': (CycleProperties.buy_window_utc_hour_start, CycleProperties.buy_window_utc_hour_end),
        'sell_window': (CycleProperties.sell_window_utc_hour_start, CycleProperties.sell_window_utc_hour_end),

        'balance_percent_per_trade': CycleProperties.balance_percent_per_trade,
        'order_padding_percent': CycleProperties.order_padding_percent,
    })

    # Example: cycle_strategy_btc_usd_buy_7_9_sell_20_22_6172
    # Include a random int in case a strategy with the same properties is run multiple times.
    strategy_id = '{0}_{1}_buy_{2}_{3}_sell_{4}_{5}_{6}'.format(
        CycleStrategyExecuterService.strategy_base_id, pair.name, CycleProperties.buy_window_utc_hour_start,
        CycleProperties.buy_window_utc_hour_end, CycleProperties.sell_window_utc_hour_start,
        CycleProperties.sell_window_utc_hour_end, random.randint(0, 100000)
    )
    cycle_strategy_executer_service.initialize(strategy_id)

    exchange: ExchangeServiceAbc = exchanges_by_id.get(CycleProperties.exchange_id_to_trade)
    profit_summary_filepath: str = os.path.join(profit_summary_dir, '{0}.csv'.format(strategy_id))
    logger.info('writing profit summary to {0}'.format(profit_summary_filepath))
    if live:
        exchanges_to_trade: Dict[int, LiveExchangeService] = {exchange.exchange_id: exchange}
        initial_tickers: Dict[str, Ticker] = exchange.get_tickers()
        initial_datetime: datetime.datetime = list(initial_tickers.values())[0].app_create_timestamp
        profit_service: ProfitService = ProfitService(exchanges_to_trade, initial_datetime=initial_datetime,
                                                      initial_tickers=initial_tickers)
        while True:
            cycle_strategy_executer_service.step(**{
                'exchange': exchange,
                'now_datetime': datetime_now_with_utc_offset(),
                'check_if_order_filled': True
            })
            # Exchange tickers and balances are updated by side effect during step()
            profit_service.save_profit_history(profit_summary_filepath)
            sleep(3600 / CycleProperties.executions_per_hour)
    else:
        ticker_filenames: List[str] = os.listdir(ticker_dir)
        ticker_filenames.sort()

        exchange.deposit_immediately(CycleProperties.base_currency, CycleProperties.initial_base_capital)
        exchanges_to_trade: Dict[int, BacktestExchangeService] = {exchange.exchange_id: exchange}
        are_initial_tickers_set: bool = False
        profit_service: Optional[ProfitService] = None
        for ticker_filename in ticker_filenames:
            print(ticker_filename)
            ticker_df = pandas.read_csv(os.path.join(ticker_dir, ticker_filename), parse_dates=['app_create_timestamp'])
            ticker_df['app_create_timestamp_min'] = ticker_df['app_create_timestamp'].dt.round('min')
            ticker_df.set_index('app_create_timestamp_min', inplace=True)

            for ticker_period in ticker_df.index.unique():
                if not are_initial_tickers_set:
                    print('initial_tickers')
                    tickers = ticker_df.loc[ticker_period]
                    TickerService.set_latest_tickers_from_file(exchanges_to_trade, tickers)
                    # The dtype of numerical fields in the DataFrame is float. The application code expected the
                    # FinancialData dtype. Convert the ticker fields from float to FinancialData only if necessary.
                    exchange.set_tickers(TickerService.tickers_with_converted_numerical_fields(exchange.get_tickers()))

                    initial_tickers: Dict[str, Ticker] = TickerService.tickers_with_converted_numerical_fields(
                        exchange.get_tickers())
                    initial_datetime: datetime.datetime = (
                        list(initial_tickers.values())[0].app_create_timestamp).to_pydatetime()
                    profit_service: ProfitService = ProfitService(exchanges_to_trade, initial_datetime=initial_datetime,
                                                                  initial_tickers=initial_tickers)
                    are_initial_tickers_set: bool = True

                # 60 minute-level ticker files per hour. Execute the strategy a certain number of times per hour.
                if random.randint(0, 60 / CycleProperties.executions_per_hour) == 0:
                    tickers = ticker_df.loc[ticker_period]
                    TickerService.set_latest_tickers_from_file(exchanges_to_trade, tickers)
                    # The dtype of numerical fields in the DataFrame is float. The application code expected the
                    # FinancialData dtype. Convert the ticker fields from float to FinancialData only if necessary.
                    exchange.set_tickers(TickerService.tickers_with_converted_numerical_fields(exchange.get_tickers()))

                    cycle_strategy_executer_service.step(**{
                        'exchange': exchange,
                        'now_datetime': ticker_period.to_pydatetime(),
                        'check_if_order_filled': False
                    })
                    if len(exchange.get_tickers().values()) > 0:
                        ticker_datetime: datetime.datetime = (
                            list(exchange.get_tickers().values())[0].app_create_timestamp).to_pydatetime()
                        profit_service.profit_summary(ticker_datetime, exchange.get_tickers())

            # Checkpoint the profit history after every aggregation file
            profit_service.save_profit_history(profit_summary_filepath)


def get_cli_args() -> Dict:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_daemon', help='Whether to run the script as a daemon. Can be "True" or "False".')
    parser.add_argument('--live',
                        help='Whether to run the strategy in live or backtest_results mode. Can be "True" or "False".')
    parser.add_argument('--ticker_dir',
                        help='Absolute path of the ticker directory. For use in backtest_results mode only.')
    arg_dict: Dict = vars(parser.parse_args())
    arg_dict['live'] = arg_dict['live'] == 'True'
    arg_dict['run_daemon'] = arg_dict['run_daemon'] == 'True'
    arg_dict['profit_summary_dir'] = arg_dict.get('profit_summary_dir',
                                                  os.path.dirname(__file__).replace('cycle/cycle',
                                                                                    'cycle/backtest_results'))
    arg_dict['logfile_path'] = arg_dict.get('logfile_path',
                                            os.path.dirname(__file__).replace('cycle/cycle', 'cycle/logs'))
    return arg_dict


if __name__ == '__main__':
    arg_dict = get_cli_args()
    file: str = os.path.join(arg_dict.get('logfile_path'),
                             'cycle_{0}.log'.format(datetime_now_with_utc_offset().strftime(strftime_minutes)))
    print('Logging to {0}'.format(file))
    file_handler: logging.FileHandler = logging.FileHandler(filename=file, mode='w+')
    file_handler.setFormatter(LoggingService.get_default_formatter())
    logger: logging.Logger = LoggingService.set_logger(name=None, handler=file_handler)

    if arg_dict.get('run_daemon'):
        with daemon.DaemonContext(files_preserve=[file_handler.stream]):
            main(logger, arg_dict.get('live'), arg_dict.get('ticker_dir'), arg_dict.get('profit_summary_dir'))
    else:
        main(logger, arg_dict.get('live'), arg_dict.get('ticker_dir'), arg_dict.get('profit_summary_dir'))
