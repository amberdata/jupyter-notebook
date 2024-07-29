import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px


def filter_dates(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    df = pd.DataFrame(df[df.index > pd.to_datetime(start)])
    df = pd.DataFrame(df[df.index < pd.to_datetime(end)])
    return df


def get_data(
    start_date: str = "6/1/2021", end_date: str = "6/1/2022"
) -> dict[str, pd.DataFrame | pd.Series]:
    eth = pd.read_csv(
        "data/ether_price.csv", parse_dates=True, index_col=0
    ).sort_index()
    eth["percent_change"] = eth["price"].pct_change()
    eth = eth[
        (eth["percent_change"].quantile(0.01) < eth["percent_change"])
        & (eth["percent_change"] < eth["percent_change"].quantile(0.99))
    ]

    fees = pd.read_csv("data/transaction_fees.csv")
    fees = fees.set_index("hash")
    fees = pd.Series((fees["gasUsed"] * fees["gasPrice"]) / 10**18)

    liq = pd.read_csv("data/liquidations.csv")
    liq = liq.set_index("transaction_hash")

    eth = filter_dates(eth, start_date, end_date)

    return {"eth": eth, "fees": fees, "liq": liq}


def pandas_long():
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", None)
    pd.set_option("display.width", None)
    pd.set_option("display.float_format", lambda x: f"{x:.6f}")


def pandas_short():
    pd.reset_option("display.max_rows")
    pd.reset_option("display.max_columns")
    pd.reset_option("display.max_colwidth")
    pd.reset_option("display.width")
    pd.reset_option("display.float_format")


def normalize(df: pd.Series) -> pd.Series:
    return (df - df.min()) / (df.max() - df.min())


def fix_pcts(backtesting_stats: pd.Series):
    """Divide all percentages by 100 so you can use them in other software.
    Returns a new Series (does not modify the one passed in).
    """
    ret = backtesting_stats.copy()

    ret["Exposure Time [%]"] /= 100
    ret["Return [%]"] /= 100
    ret["Buy & Hold Return [%]"] /= 100
    ret["Return (Ann.) [%]"] /= 100
    ret["Volatility (Ann.) [%]"] /= 100
    ret["Max. Drawdown [%]"] /= 100
    ret["Avg. Drawdown [%]"] /= 100
    ret["Win Rate [%]"] /= 100
    ret["Best Trade [%]"] /= 100
    ret["Worst Trade [%]"] /= 100
    ret["Avg. Trade [%]"] /= 100
    ret["Expectancy [%]"] /= 100

    return ret


def plot(
    results: pd.Series,
    asset_price: pd.Series,
    other_cols: dict[str, pd.Series] = dict(),
) -> go.Figure:
    equity = results["_equity_curve"]
    trades = results["_trades"]

    price = go.Scatter(
        x=asset_price.index,
        y=asset_price.values,
        mode="lines",
        line=dict(
            color="black",
        ),
        name="Price",
    )

    traces_main = [price]
    for _, row in trades.iterrows():
        color = "red"
        if row["PnL"] > 0:
            color = "green"

        trade = go.Scatter(
            x=[row["EntryTime"], row["ExitTime"]],
            y=[row["EntryPrice"], row["ExitPrice"]],
            mode="markers+lines",
            marker=dict(
                symbol=["circle-open", "circle"],
                color=[color, color],
                size=12,
            ),
            line=dict(dash="dot", width=2.5, color=color),
            text=f"PnL: {row["PnL"]:0.2f}<br>Pct Rtrn: {row["ReturnPct"]:0.2f}<br>Duration: {row["Duration"]}",
            hoverinfo="text+x+y",
            showlegend=False,
        )

        traces_main.append(trade)

    account_value = go.Scatter(
        x=equity.index,  # type:ignore
        y=equity["Equity"],
        mode="lines",
        line=dict(
            color="blue",
        ),
        name="Account Value",
    )

    traces_secondary = [account_value]

    for key, value in other_cols.items():
        traces_main.append(
            go.Scatter(
                x=value.index,
                y=value.values,
                mode="lines",
                name=key,
            )
        )

    layout = go.Layout(
        showlegend=True,
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.8, 0.2],
        vertical_spacing=0.05,
        shared_xaxes=True,
        subplot_titles=["Price, Trades, & Indicators", "Account Value"],
    )

    for t in traces_main:
        fig.add_trace(t, row=1, col=1)

    for t in traces_secondary:
        fig.add_trace(t, row=2, col=1)

    fig.update_layout(layout)

    return fig


def hist(data: pd.Series) -> go.Figure:
    mn = data.mean()
    std = data.std()

    fig = px.histogram(
        x=data,
    )

    # Add mean line
    fig.add_vline(
        x=mn,
        line_dash="dash",
        line_width=2,
        line_color="red",
        annotation_text=f"Mean: {mn:.2f}",
        annotation_position="top left",
    )

    # Add standard deviation lines
    fig.add_vline(
        x=mn + std,
        line_dash="dash",
        line_width=1,
        line_color="green",
        annotation_text=f"Std Dev: {std:.2f}",
        annotation_position="bottom right",
    )
    fig.add_vline(
        x=mn - std,
        line_dash="dash",
        line_width=1,
        line_color="green",
        annotation_text=f"Std Dev: {std:.2f}",
        annotation_position="bottom left",
    )

    fig.add_vline(x=0, line_dash="solid", line_color="black")
    fig.add_vline(x=0.05, line_dash="solid", line_color="red")

    fig.update_layout(
        xaxis=dict(
            title="Liquidation Return (%)",
            range=[-0.03, 0.1],
        ),
        yaxis=dict(
            title="Count",
        ),
    )

    return fig


def correl(data1: pd.Series, data2: pd.Series) -> go.Figure:
    d1norm = normalize(pd.Series(data1))
    d2norm = normalize(pd.Series(data2))

    fig = px.scatter(
        x=d2norm,
        y=d1norm,
        trendline="ols",
        labels={"x": "data1 norm", "y": "data2 norm"},
    )

    fig.update_layout(
        autosize=False,
        width=500,  # Adjust width as needed
        height=500,  # Adjust height as needed
        yaxis=dict(range=[0, 1]),
        xaxis=dict(range=[0, 1]),
    )

    return fig


def heatplot(df: pd.DataFrame, col_label: str, row_label: str, title: str):
    hm = go.Heatmap(
        x=df.columns,
        y=df.index,
        z=df.values,
        colorscale="Viridis",
    )

    layout = go.Layout(
        title=title,
        xaxis=dict(
            title=col_label,
            dtick=1,
        ),
        yaxis=dict(
            title=row_label,
            dtick=1,
        ),
    )

    fig = go.Figure(data=[hm], layout=layout)
    fig.show(renderer="chromium")
