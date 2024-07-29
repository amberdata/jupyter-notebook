import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from lib import pandas_long, get_data, hist


def all_liqs(
    liq: pd.DataFrame,
    eth: pd.Series,
    fees: pd.Series,
    show_graph: bool = False,
) -> pd.DataFrame:
    liq = liq[~liq["timestamp"].index.duplicated()]
    fees = fees[~fees.index.duplicated()]

    liq["timestamp"] = pd.to_datetime(liq["timestamp"], errors="raise")

    df = pd.DataFrame(
        {
            "timestamp": liq["timestamp"],
            "liquidator": liq["liquidator"].apply(lambda x: f"{x[:6]}…{x[-4:]}"),  # type:ignore
            "eth_price": liq["timestamp"].dt.floor("min").map(eth),  # type:ignore
            "debt_asset": liq["debt_asset"],  # type:ignore
            "debt_covered": liq["debt_to_cover"],
            "collat_received": liq["liquidated_collateral_amount"],
            "fees_usd": fees * liq["timestamp"].dt.floor("min").map(eth),
        }
    )

    df["collat_value_usd"] = df["collat_received"] * df["eth_price"]
    df["raw_profit_usd"] = df["collat_value_usd"] - df["debt_covered"]
    df["raw_return_pct"] = ((df["collat_value_usd"] / df["debt_covered"]) - 1).round(4)
    df["raw_effective_eth_price"] = df["debt_covered"] / df["collat_received"]

    df["profit_usd"] = df["raw_profit_usd"] - df["fees_usd"]
    df["return_pct"] = (
        ((df["collat_value_usd"] - df["fees_usd"]) / df["debt_covered"]) - 1
    ).round(4)
    df["effective_eth_price"] = (
        df["debt_covered"] / (df["collat_value_usd"] - df["fees_usd"])
    ) * df["eth_price"]

    df = df.dropna()
    df = df.sort_values("timestamp")

    df = df[
        df["debt_asset"].apply(  # type:ignore
            lambda x: x
            in [
                "USDT",
                "DAI",
                "USDC",
                "BUSD",
                "TUSD",
                "sUSD",
                "GUSD",
                "PAX",
            ]
        )
    ]

    print("pct of loans that loss: ", len(df[df["return_pct"] < 0]) / len(df))
    print("pct of loans between 0 and 0.1: ", df["return_pct"].between(0, 0.1).mean())
    print(
        "pct of loans between 0.03 and 0.07: ",
        df["return_pct"].between(0.03, 0.07).mean(),
    )

    df = df[(-0.03 < df["return_pct"]) & (df["return_pct"] < 0.1)]
    # df = df[df["timestamp"].dt.date != pd.Timestamp("5/3/2021").date()]
    # df = df[df["liquidator"].apply(lambda x: x in vc.head(7).index)]

    # print(df)
    # exit(1)

    print("liquidator profit description: \n", df["profit_usd"].describe())
    print("profit sum: ", df["profit_usd"].sum())
    print("profit sum/3: ", df["profit_usd"].sum() / 3)
    print("return desc: \n", df["return_pct"].describe())

    lr_stats = pd.DataFrame(
        {
            "num_liqs": df["liquidator"].value_counts(),
            "avg_return_pct": df.groupby("liquidator")["return_pct"].mean(),
            "total_profit": df.groupby("liquidator")["profit_usd"].sum(),
        }
    )

    nl = lr_stats.copy()
    nl = nl.sort_values("total_profit", ascending=False)
    print(
        "top 10% liqs by profit: \n",
        nl[nl["total_profit"] > nl["total_profit"].quantile(0.9)],
    )
    print(
        "top10liqs by profit % of total profit: ",
        (
            nl[nl["total_profit"] > nl["total_profit"].quantile(0.9)][
                "total_profit"
            ].sum()
        )
        / df["profit_usd"].sum(),
    )
    # exit(1)

    lr_stats = lr_stats[lr_stats["num_liqs"] > 10]
    lr_stats = lr_stats[lr_stats["total_profit"] > 0]
    lr_stats["profit_per_liq"] = lr_stats["total_profit"] / lr_stats["num_liqs"]
    lr_stats = lr_stats.sort_values("profit_per_liq", ascending=False)
    print("profitable liqs more than 10 trades: \n", lr_stats)
    print("desc: \n", lr_stats.describe())
    # exit(1)
    # lr_stats = lr_stats.head(40).sort_values("total_profit", ascending=False)
    # print(lr_stats.head())

    if show_graph:
        ## DISCOUNT GRAPH
        fig = px.scatter(
            data_frame=df,
            x="timestamp",
            y="effective_eth_price",
            color="debt_asset",
            hover_data=df.columns,
        )
        fig.add_trace(
            go.Scatter(
                x=eth.index,
                y=eth,
                line=dict(
                    color="black",
                ),
                name="ETH Price",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=eth.index,
                y=eth * 0.95,
                line=dict(
                    color="red",
                    width=1,
                ),
                name="ETH Price - 5%",
            )
        )
        fig.update_layout(
            xaxis=dict(
                title="Date",
            ),
            yaxis=dict(
                title="ETH Price (US$)",
            ),
            legend_title_text="Debt Asset",
        )
        fig.show(renderer="chromium")
        ##

        ## RETURNS GRAPH
        fig = px.scatter(
            data_frame=df,
            x="timestamp",
            y="return_pct",
            color="debt_asset",
            size="debt_covered",
            size_max=25,
            hover_data=df.columns,
        )
        fig.update_traces(
            marker=dict(
                sizemin=3.5,
            ),
        )
        fig.add_hline(y=0.05, line_dash="solid", line_color="red")
        fig.add_hline(y=0, line_dash="solid", line_color="black")
        fig.update_layout(
            xaxis=dict(
                title="Date",
            ),
            yaxis=dict(
                side="right",
                title="Liquidation Return (%)",
            ),
            yaxis2=dict(
                overlaying="y",
                side="left",
                title="ETH Price (US$)",
            ),
            legend_title_text="Debt Asset",
        )
        fig.add_trace(
            go.Scatter(
                x=eth.index,
                y=eth,
                yaxis="y2",
                line=dict(
                    color="black",
                ),
                name="ETH Price",
            )
        )
        fig.show(renderer="chromium")
        ##

        h = hist(df["return_pct"])
        h.show(renderer="chromium")

        profit_per_liq = go.Bar(
            x=lr_stats.index,
            y=lr_stats["profit_per_liq"],
            hovertext=lr_stats[lr_stats.columns],
            name="Avg Profit per Liquidation (US$)",
        )
        num_liqs = go.Bar(
            x=lr_stats.index,
            y=lr_stats["num_liqs"],
            hovertext=lr_stats,
            name="Number of Liquidations",
        )
        total_profit = go.Bar(
            x=lr_stats.index,
            y=lr_stats["total_profit"],
            hovertext=lr_stats,
            name="Total Profit (US$)",
        )
        layout = go.Layout(
            barmode="group",
            bargap=0.2,
            xaxis=dict(
                title="Liquidator Address",
            ),
            yaxis=dict(
                type="log",
            ),
            legend=dict(
                # orientation="h",  # Horizontal legend
                yanchor="top",
                y=1,
                xanchor="right",
                x=1,
            ),
        )
        fig = go.Figure(data=[profit_per_liq, total_profit, num_liqs], layout=layout)
        for i in range(len(lr_stats)):
            if i % 2 == 1:  # Alternate every other group
                fig.add_shape(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=i - 0.5,
                    y0=-0.15,
                    x1=i + 0.5,
                    y1=1,
                    fillcolor="rgba(0,0,0,0.1)",  # Adjust opacity and color as needed
                    layer="below",
                    line_width=0,
                )
        fig.show(renderer="chromium")

    return df  # type:ignore


def main():
    pandas_long()

    data = get_data("1/1/2021", "1/1/2024")

    liq = data["liq"]
    eth = pd.Series(data["eth"]["price"])
    fees = data["fees"]

    all_liqs(liq, eth, fees, show_graph=True)


if __name__ == "__main__":
    main()
