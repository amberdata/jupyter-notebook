# ======================================================================================================================
# IMPORTS
# ======================================================================================================================

import backtrader as bt
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import pandas as pd
import requests

# ======================================================================================================================
# CONFIGURATION
# ======================================================================================================================

# Set your Amberdata API_KEY here
Amberdata_API_KEY = 'YOUR_API_KEY'

# Set initial capital
icap = 100000

# Set position size - Percent of capital to deploy per trade
PercSize = 100

# Set percent trailing stop
PercTrail = 0.40

# Timeframe for the analysis
start_date = "2015-04-21"
end_date = "2020-05-09"


# ======================================================================================================================
# HELPERS - DATA SOURCES
# ======================================================================================================================

class CustomPandas(bt.feeds.PandasData):
    # Add a 'stf' line to the inherited ones from the base class
    lines = ('stf',)

    # openinterest in GenericCSVData has index 7 ... add 1
    # add the parameter to the parameters inherited from the base class
    #params = (('stf2sd', 8),)
    params = (('stf', 8),)

# Call Amberdata's API
def amberdata(url, queryString, apiKey):
    try:
        headers = {'x-api-key': apiKey}
        response = requests.request("GET", url, headers=headers, params=queryString)
        return response.text
    except Exception as e:
        raise e

# Get Market data from Amberdata
def amberdata_ohlcv(exchange, symbol, startDate, endDate):
    format = "%Y-%m-%dT%H:%M:%S"
    startTimestamp = datetime.strptime(startDate, '%Y-%m-%d')
    endTimestamp = datetime.strptime(endDate, '%Y-%m-%d')

    current = startTimestamp
    next = current
    fields = "timestamp,open,high,low,close,volume"
    payload = fields
    while (current < endTimestamp):
        next += relativedelta(years=1)
        if (next > endTimestamp):
            next = endTimestamp
        print('Retrieving OHLCV between', current, ' and ', next)
        result = amberdata(
            "https://web3api.io/api/v2/market/ohlcv/" + symbol + "/historical",
            {"exchange": exchange, "timeInterval": "days", "timeFormat": "iso", "format": "raw_csv", "fields": fields, "startDate": current.strftime(format), "endDate": next.strftime(format)},
            Amberdata_API_KEY
        )
        payload += "\n" + result
        current = next

    return payload

# Get On-chain data from Amberdata - Stock to flow valuation model
def amberdata_stf(symbol, startDate, endDate):
    print('Retrieving STF between', startDate, ' and ', endDate)
    return amberdata(
        "https://web3api.io/api/v2/market/metrics/" + symbol + "/valuations/historical",
        {"format": "csv", "timeFrame": "day", "startDate": startDate, "endDate": endDate},
        Amberdata_API_KEY
    )

def to_pandas(csv):
    return pd.read_csv(io.StringIO(csv), index_col='timestamp', parse_dates=True)


# ======================================================================================================================
# HELPERS - TRADING
# ======================================================================================================================

def pretty_print(format, *args):
    print(format.format(*args))

def printTradeAnalysis(cerebro, analyzers):

    print('Backtesting Results')
    format = "  {:<24} : {:<24}"
    ta = analyzers.ta.get_analysis()
    pretty_print(format, 'Open Positions',           ta.total.open)
    #pretty_print(format, 'Closed Trades',            ta.total.closed)
    #pretty_print(format, 'Winning Trades',           ta.won.total)
    #pretty_print(format, 'Loosing Trades',           ta.lost.total)
    #print('\n')
    #pretty_print(format, 'Longest Winning Streak',   ta.streak.won.longest)
    #pretty_print(format, 'Longest Loosing Streak',   ta.streak.lost.longest)
    #pretty_print(format, 'Strike Rate (Win/closed)', (ta.won.total / ta.total.closed) * 100)
    print('\n')
    pretty_print(format, 'Inital Portfolio Value',   '${}'.format(icap))
    pretty_print(format, 'Final Portfolio Value',    '${}'.format(cerebro.broker.getvalue()))
    #pretty_print(format, 'Net P/L',                  '${}'.format(round(ta.pnl.net.total, 2)))
    #pretty_print(format, 'P/L Average per trade',    '${}'.format(round(ta.pnl.net.average, 2)))
    print('\n')

    if hasattr(analyzers, 'drawdown'):
        pretty_print(format, 'Drawdown', '${}'.format(analyzers.drawdown.get_analysis()['drawdown']))
    if hasattr(analyzers, 'sharpe'):
        pretty_print(format, 'Sharpe Ratio:', analyzers.sharpe.get_analysis()['sharperatio'])
    if hasattr(analyzers, 'vwr'):
        pretty_print(format, 'VRW', analyzers.vwr.get_analysis()['vwr'])
    if hasattr(analyzers, 'sqn'):
        pretty_print(format, 'SQN', analyzers.sqn.get_analysis()['sqn'])
    print('\n')

    print('Transactions')
    format = "  {:<24} {:<24} {:<16} {:<8} {:<8} {:<16}"
    pretty_print(format, 'Date', 'Amount', 'Price', 'SID', 'Symbol', 'Value')
    for key, value in analyzers.txn.get_analysis().items():
        pretty_print(format, key.strftime("%Y/%m/%d %H:%M:%S"), value[0][0], value[0][1], value[0][2], value[0][3], value[0][4])


# ======================================================================================================================
# STRATEGY
# ======================================================================================================================

class Strategy(bt.Strategy):

    def next(self):
        if not self.position:  # not in the market
            self.order = self.buy()
            self.order = 'none'

# ======================================================================================================================
# MAIN
# ======================================================================================================================

# Create an instance of cerebro
cerebro = bt.Cerebro(stdstats=False)

# Be selective about what we chart
#cerebro.addobserver(bt.observers.Broker)
cerebro.addobserver(bt.observers.BuySell)
cerebro.addobserver(bt.observers.Value)
cerebro.addobserver(bt.observers.DrawDown)
cerebro.addobserver(bt.observers.Trades)

# Set the investment capital
cerebro.broker.setcash(icap)

# Set position size
cerebro.addsizer(bt.sizers.PercentSizer, percents=PercSize)

# Add our strategy
cerebro.addstrategy(Strategy)

# Read market and on-chain data into dataframe
btc = to_pandas(amberdata_ohlcv("gdax", "btc_usd", start_date, end_date))
btc_stf = to_pandas(amberdata_stf("btc", start_date, end_date))
btc['stf'] = btc_stf['stockToFlow_price']

# Feed Cerebro our data
#cerebro.adddata(CustomPandas(dataname=btc, openinterest=None, stf2sd='stf2sd'))
cerebro.adddata(CustomPandas(dataname=btc, openinterest=None, stf='stf'))

# Add analyzers
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='ta')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0, annualize=True, timeframe=bt.TimeFrame.Days)
cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')
cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')

# Run our Backtest
backtest = cerebro.run()
backtest_results = backtest[0]

# Print some analytics
printTradeAnalysis(cerebro, backtest_results.analyzers)

# Finally plot the end results
cerebro.plot(style='candlestick', volume=False)

# ======================================================================================================================
