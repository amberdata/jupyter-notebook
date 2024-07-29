import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from os import environ
from typing import Any, Optional

import pandas as pd
import requests as rq
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

from lib import pandas_long


def get_date_pairs(hours_delta: int) -> list[tuple[str, str]]:
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2024, 1, 1)

    date_list = []

    current_date = start_date
    while current_date < end_date:
        date_list.append(current_date.isoformat())
        current_date += relativedelta(hours=hours_delta)

    if not date_list[-1] == end_date.isoformat():
        date_list.append(end_date.isoformat())

    date_pairs = [(a, b) for a, b in zip(date_list, date_list[1:])]

    return date_pairs


class Progress:
    num_calls: int
    current_call: int
    lock: threading.Lock

    def __init__(self, num_calls: int):
        self.num_calls = num_calls
        self.current_call = 0
        self.lock = threading.Lock()

    def next(self):
        with self.lock:
            self.current_call += 1
            sys.stdout.write(f"\r[{self.current_call}/{self.num_calls}]")
            sys.stdout.flush()


def call_api(
    endpoint: str, params: dict[str, str], progress: Optional[Progress]
) -> Any:
    headers = {
        "accept": "application/json",
        "x-api-key": environ["API_KEY"],
    }

    param_string = "&".join(f"{key}={value}" for key, value in params.items())

    url = f"{endpoint}?{param_string}"

    while True:
        response = rq.get(url, headers=headers)
        json = response.json()

        if "message" in json:
            if json["message"] == "Too Many Requests":
                continue

        status = response.json()["status"]
        if not status == 200:
            print(f"error calling GET {url}")
            return dict()

        if progress:
            progress.next()
        return response.json()["payload"]


def parallel_api(
    endpoints_params: list[tuple[str, dict[str, str]]],
    max_workers: int = 5,
) -> list[Any]:
    payloads = []
    prog = Progress(len(endpoints_params))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(call_api, endpoint, params, prog): (endpoint, params)
            for endpoint, params in endpoints_params
        }

        for future in as_completed(futures):
            try:
                payload = future.result()
                if payload:
                    payloads.append(payload)
            except Exception as e:
                print(f"exception {e}")

    print()

    return payloads


def get_liq_calls() -> pd.DataFrame:
    endpoint = "https://api.amberdata.com/defi/lending/aavev2/assets/WETH"
    dates = get_date_pairs(hours_delta=6)
    endpoints_params = [
        (
            endpoint,
            {
                "startDate": start,
                "endDate": end,
                "timeFormat": "ms",
                "action": "LiquidationCall",
                "size": "990",
            },
        )
        for start, end in dates
    ]

    print("collecting liquidation data")
    payloads = parallel_api(endpoints_params, max_workers=11)

    df = pd.concat([pd.DataFrame(p["data"]) for p in payloads], ignore_index=True)

    new = pd.DataFrame(
        {
            "transaction_hash": df["transactionHash"],
            "timestamp": pd.to_datetime(df["timestamp"] * 10**6),
            "debt_asset": df["principalAssetSymbol"],
            "debt_to_cover": df["principalAmountNative"],
            "collateral_asset": df["collateralAssetId"],
            "liquidated_collateral_amount": df["collateralAmountNative"],
            "liquidator": df["liquidator"],
        }
    )
    return new


def get_eth_minutely() -> pd.DataFrame:
    endpoint = "https://api.amberdata.com/market/spot/prices/assets/eth/historical/"
    dates = get_date_pairs(hours_delta=24)
    endpoints_params = [
        (
            endpoint,
            {
                "startDate": start,
                "endDate": end,
                "timeFormat": "ms",
                "timeInterval": "minute",
            },
        )
        for start, end in dates
    ]

    print("collecting ethereum price data")
    payloads = parallel_api(endpoints_params, max_workers=11)

    df = pd.concat([pd.DataFrame(p["data"]) for p in payloads], ignore_index=True)

    new = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df["timestamp"] * 10**6),
            "price": df["price"],
        }
    )
    return new


def get_tx_fees(txs: pd.Series) -> pd.DataFrame:
    endpoints_params = [
        (f"https://api.amberdata.com/blockchains/transactions/{tx}", dict())
        for tx in txs
    ]

    print("collecting transaction fee data")
    payloads = parallel_api(endpoints_params, max_workers=11)

    df = pd.concat(
        [pd.DataFrame([p]) for p in payloads],
        ignore_index=True,
    )

    new = pd.DataFrame(
        {
            "hash": df["hash"],
            "gasUsed": df["gasUsed"],
            "gasPrice": df["gasPrice"],
        }
    )

    return new


def main():
    pandas_long()
    load_dotenv()

    liqs = get_liq_calls()
    liqs.to_csv("data/liquidations.csv", index=False)

    fees = get_tx_fees(
        pd.Series(liqs[~liqs["transaction_hash"].duplicated()]["transaction_hash"])
    )
    fees.to_csv("data/transaction_fees.csv", index=False)

    eth = get_eth_minutely()
    eth.to_csv("data/ether_price.csv", index=False)


if __name__ == "__main__":
    main()
