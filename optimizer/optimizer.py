"""Optimize allocations for a given date.

General strategy is:
    1) Fork several worker processes with copies of the filtered data.
    2) From some arbitrary starting point, create a queue of all potential
        single trade deviations.
    3) Have workers process the queue, and send results back via queue.
    4) Have the master process the results, choosing the best one.
    5a) If a better allocation is found, restart #3 with that allocation as the
        starting point.
    5b) If no better allocation is found, halve the trading amount and restart
        #2 with the current allocation and new trade amount.
    6) Once a lower limit of trade amount is found, return the allocaiton.
"""
import functools
import numpy as np
from scipy.stats.mstats import gmean
import time


def _initializeProcess(data):
    """Initialize a process with necessary data."""
    global data_matrix
    data_matrix = data


def _unwrapAndScore(data_dict):
    return _scoreAllocation(
            data_dict['allocation_array'],
            data_dict['required_return'],
            data_dict['expense_array'],
            use_downside_correl = data_dict['use_downside_correl'])


def _scoreAllocation(allocation_array, required_return, expense_array, use_downside_correl=False):
    """Determine the score of a given allocation.

    Args:
        data_matrix: See _convertTickerDataToMatrix.
        allocation_array: An array of percent allocations.
        required_return: What daily return is desired.
    Returns:
        score: A modified Sortino Ratio for the allocation.
    """
    daily_returns = np.matmul(data_matrix, allocation_array)
    expenses = pow(1 - np.matmul(allocation_array, expense_array), 1 / 253)
    daily_returns *= expenses
    mean_return = gmean(daily_returns)

    # Short-circuit score calculation when mean_return < required_return.
    # Otherwise, with a negative denominator, the code will push for a
    # large denominator to maximize the overall score.
    if mean_return < required_return:
        return {
                'score': mean_return - required_return,
                'allocation_array': allocation_array}

    filtered_returns = np.copy(daily_returns)
    filtered_returns -= required_return
    filtered_returns = np.clip(filtered_returns, None, 0)
    filtered_returns *= filtered_returns
    downside_risk = np.sqrt(filtered_returns.mean())

    if not use_downside_correl:
        downside_correl = 1
    elif len(allocation_array) > 1:
        below_desired = daily_returns < required_return
        filtered_returns = [
            data_matrix[x]
            for x in range(len(below_desired)) if below_desired[x]]
        downside_correl = np.matmul(
            np.matmul(
                allocation_array,
               np.corrcoef(filtered_returns, rowvar=False)),
            allocation_array)
    else:
        downside_correl = 1

    return {
            'score': (mean_return - required_return) / (downside_risk * downside_correl),
            'allocation_array': allocation_array}


def findOptimalAllocation(data_matrix, ticker_tuple, required_return, expense_array, use_downside_correl=True):
    """Find the optimal allocation.

    Args:
         data_matrix: Rows = days, columns = tickers, values = % price changes.
            Tickers are ordered alphabetically.
        ticker_tuple: Tuple of tickers in the matrix, in the same order.
        required_return: What daily return is desired.
    Returns:
        allocations: Dict of percent allocations by ticker.
    """
    # Initialize global data for master.
    _initializeProcess(data_matrix)

    best = np.zeros(len(ticker_tuple), dtype=np.float64)
    best[0] = 1.0
    best_score = _scoreAllocation(best, required_return, expense_array, use_downside_correl)['score']

    trading_increment = 1.0
    start = time.time()

    # TODO: Remove magic number. Currently ~1 basis point.
    while trading_increment >= 1 / 128:
        map_iterable = []
        for sell_id in range(len(ticker_tuple)):
            if best[sell_id] < trading_increment: continue

            for buy_id in range(len(ticker_tuple)):
                if buy_id == sell_id: continue

                curr = np.copy(best)
                curr[sell_id] -= trading_increment
                curr[buy_id] += trading_increment

                map_iterable.append({
                    'allocation_array': curr, 
                    'required_return': required_return, 
                    'use_downside_correl': use_downside_correl,
                    'expense_array': expense_array})

        # TODO: Test different chunksizes.
        results = map(_unwrapAndScore, map_iterable)
        best_result = functools.reduce(
            lambda x, y: x if x['score'] > y['score'] else y,
            results,
            {'score': -float('inf')})
        
        if best_result['score'] > best_score:
            best = best_result['allocation_array']
            best_score = best_result['score']
        else:
            print('Trading increment %.2f%% took %.2fs, score is %.4f' % (
                trading_increment * 100,
                time.time() - start,
                best_score))
            print({ticker_tuple[i]: best[i] for i in range(len(ticker_tuple)) if best[i] > 0})
            start = time.time()
            trading_increment /= 2.0
   
    allocation_map = {ticker_tuple[i]: best[i] for i in range(len(ticker_tuple))}

    return (best_score, allocation_map)
