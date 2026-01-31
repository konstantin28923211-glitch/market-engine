# run_eurusd_m30_from_m1.py
# Backtest M30 strategy built from M1 data with trailing stop and risk management

import pandas as pd
from datetime import datetime, timedelta

# ================== НАСТРОЙКИ ==================
CSV_PATH = "data/EURUSD_M1.csv"

INITIAL_DEPOSIT = 10_000.0
RISK_PER_TRADE = 0.015        # 1.5% риска
PIP_VALUE_PER_LOT = 10.0     # для EURUSD
POINT = 0.0001

SL_PIPS = 15                 # начальный SL
TRAIL_START_PIPS = 10        # с какого профита тянуть
TRAIL_STEP_PIPS = 5          # шаг трейлинга

BLOCK_AFTER_LOSSES = 2       # блок после 2 лосей
# ===============================================


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def resample_m30(df_m1: pd.DataFrame) -> pd.DataFrame:
    df = df_m1.set_index("time")
    m30 = df.resample("30min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna().reset_index()
    return m30


def calc_lot(balance: float, sl_pips: float) -> float:
    risk_money = balance * RISK_PER_TRADE
    lot = risk_money / (sl_pips * PIP_VALUE_PER_LOT)
    return round(lot, 2)


def backtest(df_m1: pd.DataFrame, df_m30: pd.DataFrame):
    balance = INITIAL_DEPOSIT
    equity = balance

    trades = []
    losses_in_row = 0
    blocked_until = None

    open_trade = None

    m1_iter = df_m1.iterrows()
    m30_index = 0

    for i, row in m1_iter:
        time = row["time"]

        # обновляем текущую M30 свечу
        if m30_index + 1 < len(df_m30) and time >= df_m30.loc[m30_index + 1, "time"]:
            m30_index += 1

        m30 = df_m30.loc[m30_index]

        # === ЗАКРЫТИЕ СДЕЛКИ ===
        if open_trade:
            price = row["close"]

            # trailing stop
            if open_trade["direction"] == "buy":
                profit_pips = (price - open_trade["open_price"]) / POINT
                if profit_pips >= TRAIL_START_PIPS:
                    new_sl = price - TRAIL_STEP_PIPS * POINT
                    if new_sl > open_trade["sl"]:
                        open_trade["sl"] = new_sl

                # stop loss
                if row["low"] <= open_trade["sl"]:
                    result = (open_trade["sl"] - open_trade["open_price"]) / POINT
                else:
                    continue

            else:  # sell
                profit_pips = (open_trade["open_price"] - price) / POINT
                if profit_pips >= TRAIL_START_PIPS:
                    new_sl = price + TRAIL_STEP_PIPS * POINT
                    if new_sl < open_trade["sl"]:
                        open_trade["sl"] = new_sl

                if row["high"] >= open_trade["sl"]:
                    result = (open_trade["open_price"] - open_trade["sl"]) / POINT
                else:
                    continue

            money = result * PIP_VALUE_PER_LOT * open_trade["lot"]
            balance += money

            trades.append({
                "time": time,
                "direction": open_trade["direction"],
                "pips": round(result, 1),
                "money": round(money, 2),
                "balance": round(balance, 2)
            })

            if result < 0:
                losses_in_row += 1
                if losses_in_row >= BLOCK_AFTER_LOSSES:
                    blocked_until = time + timedelta(minutes=30)
            else:
                losses_in_row = 0

            open_trade = None
            continue

        # === БЛОК ТОРГОВЛИ ===
        if blocked_until and time < blocked_until:
            continue

        # === ВХОД ПО M30 ===
        if time.minute not in (0, 30):
            continue

        body = abs(m30["close"] - m30["open"])

        if body < 5 * POINT:
            continue

        lot = calc_lot(balance, SL_PIPS)

        if m30["close"] > m30["open"]:
            open_trade = {
                "direction": "buy",
                "open_price": row["open"],
                "sl": row["open"] - SL_PIPS * POINT,
                "lot": lot
            }
        else:
            open_trade = {
                "direction": "sell",
                "open_price": row["open"],
                "sl": row["open"] + SL_PIPS * POINT,
                "lot": lot
            }

    return trades, balance


def main():
    df_m1 = load_data(CSV_PATH)
    df_m30 = resample_m30(df_m1)

    trades, final_balance = backtest(df_m1, df_m30)

    print(f"Trades: {len(trades)}")
    if trades:
        wins = sum(1 for t in trades if t["pips"] > 0)
        losses = len(trades) - wins
        print(f"Wins: {wins}, Losses: {losses}")
    print(f"Final balance: {round(final_balance, 2)}")

    pd.DataFrame(trades).to_csv("report_m30.csv", index=False)


if __name__ == "__main__":
    main()
