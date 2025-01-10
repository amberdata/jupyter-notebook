import pandas as pd
import requests
# from pprint import pprint
import os
import time
import json
import traceback
import plotly.express as px
import numpy as np

from itertools import zip_longest

"""
Good YouTube video to watch for context: https://www.youtube.com/watch?v=BJt6PGKeO9I

Crypto context: https://medium.com/coinmonks/liquidity-and-order-book-distribution-908e4ebd9173
"""


def http_ok_next_page_url_extractor(page):
    """
    Function that extracts the next page url from the current page of data

    Parameters
    ----------
    page: dict

    Returns
    -------
    next_page_url: str
    """
    if "payload" in page and page["payload"] is not None:
        payload = page["payload"]
        if "metadata" in payload and payload["metadata"] is not None:
            metadata = payload["metadata"]
            if "next" in metadata and metadata["next"] is not None:
                next_page_url = metadata["next"]
                return next_page_url
    return ""


PRODUCTION_BASE_URL = "https://api.amberdata.com"


def get_full_api_url(api_path: str):
    """
    Parameters
    ----------
    api_path: str
        The API resource that is of interest i.e. /markets/spot/trades/btc_usd. Assumes that path parameters have already been inserted into the resource path.
    """
    return f"{PRODUCTION_BASE_URL}{api_path}"


class AmberdataResponse:
    def __init__(self, data, status, duration_seconds, request_url):
        self.data = data
        self.status = status
        self.duration_seconds = duration_seconds
        self.request_url = request_url
        self.attempts = 0

    def increment_attempt(self, by: int = None):
        if by is not None:
            self.attempts += by
        else:
            self.attempts += 1


"""
Type Hints
"""
AmberdataResponseStack = list[AmberdataResponse]


class EndpointCaller:
    def __init__(self, amberdata_api_key):
        self.x_api_key = amberdata_api_key

    def call_endpoint_and_get_data_as_json(
        self, path: str, query: dict, headers: dict, retry_message: str = None
    ):
        headers_with_api_key = {**headers, "x-api-key": self.x_api_key}

        if path.startswith(PRODUCTION_BASE_URL):
            """
            When the next page URL is pre-formed and can be used as-is.
            """
            full_api_url = path
        else:
            full_api_url = get_full_api_url(path)

        start_time = time.time()
        request = None
        try:
            request = requests.get(
                full_api_url, params=query, headers=headers_with_api_key
            )
            print(
                f"Making HTTP call for: {request.url}"
                if retry_message is None
                else f"{retry_message} for: {request.url}"
            )
            end_time = time.time()
            duration = end_time - start_time
            if request.status_code == 200:
                json_data = request.json()
                return AmberdataResponse(json_data, 200, duration, request.url)
            else:
                return AmberdataResponse(
                    request.text, request.status_code, duration, request.url
                )
        except Exception as exc:
            print(exc)
            as_5xx_error_json = {
                "status": 500,  # default to 500 error
                "message": "Failed to complete HTTP request.",
            }

            end_time = time.time()
            duration = end_time - start_time
            return AmberdataResponse(json.dumps(as_5xx_error_json), 500, duration, None)

    def call_endpoint_and_get_all_pages(
        self, path: str, query: dict, headers: dict, http_ok_next_page_url_extractor
    ):
        """
        Iterative, non-recursive way to get all the pages given an initial URL.

        Avoids Python's max recursion depth (~1000).

        This is a generator function and should be used accordingly.

        Parameters
        ----------
        path: str
            The endpoint path with the path parameters inserted i.e if the path is `/market/defi/trades/{pool}/historical/` then provide `/market/defi/trades/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640/historical`
        query: dict
            The query parameters in a dict i.e `{'startDate': '2023-05-20', 'endDate': '2023-05-21'}`
        headers: dict
            The request headers in a dict, you do not have to pass in the API key because the `EndpointCaller` class is intialized with it
        http_ok_next_page_url_extractor: function
            The function that extracts the next page url from a given API response

        Returns
        -------
        api_response: AmberdataResponse
            Individual page from the calling the endpoint

        """
        stack: AmberdataResponseStack = []
        current_page_response = self.call_endpoint_and_get_data_as_json(
            path, query, headers
        )
        current_page_response.increment_attempt()
        stack.append(current_page_response)
        while len(stack) > 0:
            response = stack.pop()
            if response.status == 200:
                next_page_url = http_ok_next_page_url_extractor(response.data)
                if len(next_page_url) > 0:
                    next_page_response = self.call_endpoint_and_get_data_as_json(
                        next_page_url, None, headers
                    )
                    next_page_response.increment_attempt()
                    stack.append(next_page_response)
                yield response
            else:
                if response.attempts < 3 and response.request_url is not None:
                    retried_page_response = self.call_endpoint_and_get_data_as_json(
                        response.request_url,
                        None,
                        headers,
                        retry_message="Retrying HTTP call",
                    )
                    retried_page_response.increment_attempt(by=response.attempts + 1)
                    stack.append(retried_page_response)
                else:
                    yield response

        assert (
            len(stack) == 0
        ), "Stack is not empty, more pages need to be retrieved. # of remaining pages is {}".format(
            len(stack)
        )
        return AmberdataResponse("DONE", -1, 0, "")


def find_mid_price(ask: list, bid: list):
    best_ask = ask[0]["price"]
    best_bid = bid[0]["price"]
    mid = (best_ask + best_bid) / 2
    return mid


def format_json_response(
    ask_aggregates: list,
    bid_aggregates: list,
    instrument: str,
    timestamp,
    exchange: str,
):
    """
    Formats the calculation into an easy to parse response
    """
    zipped = list(zip_longest(ask_aggregates, bid_aggregates))
    cleaned = []
    try:
        cleaned = [
            {
                "basisPointsFromMid": t[0]["basisPointsFromMid"]
                if t[0] is not None
                else t[1]["basisPointsFromMid"],
                "askLiquidityNative": t[0]["liquidity"] if t[0] is not None else None,
                "askLiquidityFiat": t[0]["liquidityUSD"] if t[0] is not None else None,
                "askLiquidityCumulativeNative": t[0]["cumulativeLiquidity"]
                if t[0] is not None
                else None,
                "askLiquidityCumulativeFiat": t[0]["cumulativeLiquidityUSD"]
                if t[0] is not None
                else None,
                "bidLiquidityNative": t[1]["liquidity"] if t[1] is not None else None,
                "bidLiquidityFiat": t[1]["liquidityUSD"] if t[1] is not None else None,
                "bidLiquidityCumulativeNative": t[1]["cumulativeLiquidity"]
                if t[1] is not None
                else None,
                "bidLiquidityCumulativeFiat": t[1]["cumulativeLiquidityUSD"]
                if t[1] is not None
                else None,
                "currency": "USD",
            }
            for t in zipped
        ]
    except Exception as e:
        # In case there is an aggregation issue, we don't have to stop the complete pipeline, trace the issue, return an empty collect and resume the pipeline
        stack_trace = "".join(traceback.TracebackException.from_exception(e).format())
        print(stack_trace)
        raise e

    """
    To enhance this when aggregating ACROSS EXCHANGES for an instrument at a specific minute, just join on `basisPointsFromMid` and sum(askLiquidity) and sum(bidLiquidity)

    """

    return [
        {
            "exchange": exchange,
            "instrument": instrument,
            "timestamp": timestamp,
            "liquidity": cleaned,
        }
    ]


def get_spot_ob_snapshot_for_instrument(
    instrument: str, exchange: str, endpoint_caller: EndpointCaller
):
    """
    Parameters

    instrument - required
        The spot instrument in {base}_{quote} form i.e. btc_usd
    exchange - required
        The name of the exchange supported by Amberdata
    x_api_key - required
        Your Amberdata API key
    """
    additional_headers = {
        "Accept-Encoding": "gzip, deflate, br",
    }
    query_params = {
        "exchange": exchange,
        "timeFormat": "hr",  # change this to whatever format is desired for timestamps
        # "startDate": "2025-01-01T00:00:00", # un-comment and change these dates as desired
        # "endDate": "2025-01-09T00:00:00" #un-comment and change these dates as desired
    }
    yield from endpoint_caller.call_endpoint_and_get_all_pages(
        f"/markets/spot/order-book-snapshots/{instrument}",
        query_params,
        additional_headers,
        http_ok_next_page_url_extractor,
    )


def plot_liquidity_histogram(aggregation: dict):
    """
    aggregation is of format

    [{'exchange': 'bitfinex',
        'instrument': 'eth_usd',
        'liquidity': [{'askLiquidityCumulativeFiat': np.float64(3627709.9561665184),
                       'askLiquidityCumulativeNative': np.float64(1092.13311967),
                       'askLiquidityFiat': np.float64(3627709.9561665184),
                       'askLiquidityNative': np.float64(1092.13311967),
                       'basisPointsFromMid': 100.0,
                       'bidLiquidityCumulativeFiat': np.float64(3825917.910936735),
                       'bidLiquidityCumulativeNative': np.float64(1163.57595828),
                       'bidLiquidityFiat': np.float64(3825917.910936735),
                       'bidLiquidityNative': np.float64(1163.57595828),
                       'currency': 'USD'},
                      {'askLiquidityCumulativeFiat': np.float64(6238534.04097278),
                       'askLiquidityCumulativeNative': np.float64(1872.8269035),
                       'askLiquidityFiat': np.float64(2610824.084806262),
                       'askLiquidityNative': np.float64(780.69378383),
                       'basisPointsFromMid': 200.0,
                       'bidLiquidityCumulativeFiat': np.float64(15232741.731143385),
                       'bidLiquidityCumulativeNative': np.float64(4667.10994671),
                       'bidLiquidityFiat': np.float64(11406823.82020665),
                       'bidLiquidityNative': np.float64(3503.53398843),
                       'currency': 'USD'}],
        'timestamp': '2025-01-09 15:43:00 000'}]
    """

    df_records = []
    liquidity: list = aggregation[0]["liquidity"]
    for by_basis_point in liquidity:
        element_ask = {
            "x": by_basis_point["basisPointsFromMid"],
            "y": by_basis_point["askLiquidityFiat"],
        }
        element_bid = {
            "x": by_basis_point["basisPointsFromMid"] * -1,
            "y": by_basis_point["bidLiquidityFiat"],
        }
        df_records.append(element_ask)
        df_records.append(element_bid)
    df = pd.DataFrame.from_records(df_records)

    df["Color"] = np.where(df["x"] >= 0, "Ask", "Bid")
    fig = px.bar(
        df,
        x="x",
        y="y",
        title=f'Liquidity for {aggregation[0]["instrument"]} on {aggregation[0]["exchange"]} at {aggregation[0]["timestamp"]}',
        color="Color",
        labels={"y": "Amount ($)", "x": "Basis Points from Mid"},
        text="y",
        template="plotly_dark",
        color_discrete_map={"Ask": "#2ecc71", "Bid": "#e74c3c"},
    )

    fig.show()


if __name__ == "__main__":
    endpoint_caller = EndpointCaller(os.getenv("PRODUCTION_API_KEY"))
    spot_ob_snapshot = get_spot_ob_snapshot_for_instrument(
        "eth_usd", "bitfinex", endpoint_caller
    )

    aggregation_outputs: list[dict] = []
    aggregation_start_time = time.time()

    for response_page in spot_ob_snapshot:
        amberdata_json_contents = response_page.data
        payload_data = amberdata_json_contents["payload"]["data"]

        for minutely_snapshot in payload_data:
            asks = minutely_snapshot["ask"]
            bids = minutely_snapshot["bid"]
            mid = find_mid_price(asks, bids)

            increment = mid / 100  # this is 1%
            # increment = mid / 100 / 100  # this is 1 basis point (bps) i.e. 0.01%

            """
            Using the mid price, for the ask levels, we compute liquidity at 1% increments.
            """
            ask_df = pd.DataFrame.from_records(asks)
            start = mid + increment
            end = ask_df.tail(1).iloc[0]["price"] + increment
            ask_aggregates = []
            while start <= end:
                bucket = ask_df[
                    (ask_df["price"] <= start) & (ask_df["price"] > start - increment)
                ]
                liquidity = bucket["volume"].sum()
                liquidityUSD = 0
                for idx, row in bucket.iterrows():
                    liquidityUSD += row["price"] * row["volume"]
                ask_aggregates.append(
                    {
                        "basisPointsFromMid": abs(
                            round((start - mid) / mid, 4) * 10000
                        ),
                        "liquidity": liquidity,
                        "liquidityUSD": liquidityUSD,
                    }
                )
                start += increment

            for idx, item in enumerate(ask_aggregates):
                if idx == 0:
                    item["cumulativeLiquidity"] = item["liquidity"]
                    item["cumulativeLiquidityUSD"] = item["liquidityUSD"]
                else:
                    item["cumulativeLiquidity"] = (
                        item["liquidity"] + ask_aggregates[idx - 1]["liquidity"]
                    )
                    item["cumulativeLiquidityUSD"] = (
                        item["liquidityUSD"] + ask_aggregates[idx - 1]["liquidityUSD"]
                    )

            """
            Using the mid price, for the bid levels, we compute liquidity at 1% decrements.
            """
            bid_df = pd.DataFrame.from_records(bids)
            start = mid - increment
            end = bid_df.tail(1).iloc[0]["price"] - increment
            bid_aggregates = []
            while start >= end:
                bucket = bid_df[
                    (bid_df["price"] >= start) & (bid_df["price"] < start + increment)
                ]
                liquidity = bucket["volume"].sum()
                liquidityUSD = 0
                for idx, row in bucket.iterrows():
                    liquidityUSD += row["price"] * row["volume"]
                bid_aggregates.append(
                    {
                        "basisPointsFromMid": abs(
                            round((start - mid) / mid, 4) * 10000
                        ),
                        "liquidity": liquidity,
                        "liquidityUSD": liquidityUSD,
                    }
                )
                start -= increment

            for idx, item in enumerate(bid_aggregates):
                if idx == 0:
                    item["cumulativeLiquidity"] = item["liquidity"]
                    item["cumulativeLiquidityUSD"] = item["liquidityUSD"]
                else:
                    item["cumulativeLiquidity"] = (
                        item["liquidity"] + bid_aggregates[idx - 1]["liquidity"]
                    )
                    item["cumulativeLiquidityUSD"] = (
                        item["liquidityUSD"] + bid_aggregates[idx - 1]["liquidityUSD"]
                    )

            minutely_liquidity_aggregate = format_json_response(
                ask_aggregates,
                bid_aggregates,
                minutely_snapshot["instrument"],
                minutely_snapshot["timestamp"],
                minutely_snapshot["exchange"],
            )
            aggregation_outputs.append(minutely_liquidity_aggregate)

    aggregation_end_time = time.time()
    print(
        f"Total time elapsed: {(aggregation_end_time - aggregation_start_time)/60} minutes"
    )
    # pprint(aggregation_outputs)
    plot_liquidity_histogram(aggregation_outputs[0])
