"""Control the gathering and caching of stock data.

General strategy is:
    1) For every given ticker, check the cache folder for that ticker's file.
    2) Add all tickers to a priority queue, sorted by modification timestamp..
    3) For all tickers that are outdated (or 1% of tickers, whichever is
        greater), load them async via the API and re-write them.
    4) For all other tickers, async load their files.
"""

import bz2
import datetime
import json
import requests
import time


def _callApi(request, required_key):
    """Call a given AlphaVantage API with controlled retries until successful.

    Args:
        request: String request to make.
        required_key: A key that must be present in the response.
    Returns:
        result: A partially validated response.
    """
    attempts = 0
    aggregated_results = {}
    while True:
        time.sleep(1)

        attempts += 1
        if attempts >= 120:
            print(aggregated_results)
            raise IOError('Too many attempts for request %s' % request)

        raw_result = requests.get(request)

        # Retry w/o error if server is swamped.
        if raw_result.status_code == 503:
            continue

        if raw_result.status_code != 200:
            print(request)
            print(raw_result)
            raise IOError('Recived %d status code for request %s.' % (
                raw_result.status_code, request))

        try:
            result = raw_result.json()
        except ValueError as e:
            print(request)
            print(raw_result)
            raise e

        if 'Error Message' in result:
            raise IOError('Received error %s for request %s.' % (
                result['Error Message'], request))

        if required_key not in result:
            aggregated_results.update(result)
            continue

        return result


def _callSearchApi(ticker, api_key):
    """Call the AlphaVantage Search API for a list of tickers.

    Args:
        ticker: Ticker string.
        api_key: String API key for authentication.
    Returns:
        name: String name of this ticker.
    """
    base_request = 'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords=%s&apikey=%s'

    request = base_request % (ticker, api_key)
    result = _callApi(request, 'bestMatches')

    for match in result['bestMatches']:
        if match['1. symbol'] == ticker:
            return match['2. name']

    raise IOError('Couldn\'t find ticker %s' % ticker)



def _callDailyAdjustedApi(ticker, api_key):
    """Call the AlphaVantage Daily Adjusted API for a list of tickers.

    Args:
        ticker: Ticker string.
        api_key: String API key for authentication.
    Returns:
        price_data: Dict of integer dates (days since epoch), to prices
            (floats).
    """
    base_request = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=%s&outputsize=full&apikey=%s'
    epoch = datetime.datetime.utcfromtimestamp(0)

    request = base_request % (ticker, api_key)
    result = _callApi(request, 'Time Series (Daily)')

    price_data = {}
    for date_str, data in result['Time Series (Daily)'].items():
        date_int = (datetime.datetime.strptime(date_str, '%Y-%m-%d') - epoch).days
        price_float = float(data['5. adjusted close'])
        price_data[date_int] = price_float

    return price_data


def _getAllApiData(ticker, api_key):
    """Get data from AlphaVantage APIs.

    Args:
        ticker: Ticker string.
        api_key: String API key for authentication.
    Returns:
        ticker_data: Nested dict of data about this ticker.
            {
                ticker<string>: {
                    'name': name<string>,
                    'price_data': {
                        date<int>: price<float>
                    }
                }
            }
    """
    name = _callSearchApi(ticker, api_key)
    price_data = _callDailyAdjustedApi(ticker, api_key)

    ticker_data = {
        ticker: {
            'name': name,
            'price_data': price_data}}

    return ticker_data


def _getAndCacheApiData(tickers, api_key):
    """Get API data for all tickers, cache it, and return it.

    Args:
        tickers: Iterable of ticker strings.
        api_key: String API key for authentication.
    Returns:
        ticker_data: See _getAllApiData for format.
    """
    for ticker in tickers:
        data = _getAllApiData(ticker, api_key)
        data_json = json.dumps(data)
        filename = cache_folder + '/' + ticker + '.json.bz2'
        with bz2.BZ2File(filename, 'wb') as f:
            f.write(data_json)

    return ticker_data

