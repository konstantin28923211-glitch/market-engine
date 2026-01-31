# Хороший x20 для EURUSD без кросса

import pandas as pd
import numpy as np

# ================== НАСТРОЙКИ ==================
START_BALANCE = 100.0
RISK_PCT = 0.015          # 1.5% риск
STOP_PIPS = 20
TRAIL_START = 15
TRAIL_LOCK = 5
TRAIL_STEP = 5
PIP = 0.0001

M1_FILE  = "data/EURUSD_M1.csv"
M30_FILE = "data/eurusd_m30.csv"
# ===============================================

# ===== ЗАГРУЗКА ДАННЫХ =====
m1 = pd.read_csv(M1_FILE, parse_dates=["time"])
m30 = pd.read_csv(M30_FILE, parse_dates=["time"])

m1.columns = m1.columns.str.lower()
m30.columns = m30.columns.str.lower()

# ===== СОСТОЯНИЕ =====
balance = START_BALANCE
max_balance = balance
max_dd = 0

in_trade = False
direction = None
entry = sl = size = 0.0

used_m30_time = None
m30_index = 0

trades = wins = losses = 0
profit_sum = loss_sum = 0.0

cur_loss_streak = 0
max_loss_streak = 0
block_until_new_m30 = False

# ================== ОСНОВНОЙ ЦИКЛ ==================
for i in range(len(m1)):
    candle = m1.iloc[i]
    time = candle.time

    # обновление M30
    while m30_index + 1 < len(m30) and time >= m30.iloc[m30_index + 1].time:
        m30_index += 1
        block_until_new_m30 = False
        cur_loss_streak = 0

    m30_candle = m30.iloc[m30_index]

    # ===== ВХОД =====
    if not in_trade and not block_until_new_m30:
        if used_m30_time == m30_candle.time:
            continue

        direction = "buy" if m30_candle.close > m30_candle.open else "sell"
        entry = candle.close

        if direction == "buy":
            sl = entry - STOP_PIPS * PIP
            risk = entry - sl
        else:
            sl = entry + STOP_PIPS * PIP
            risk = sl - entry

        if risk <= 0:
            continue

        risk_money = balance * RISK_PCT
        size = risk_money / risk

        if not np.isfinite(size) or size <= 0:
            continue

        in_trade = True
        used_m30_time = m30_candle.time
        continue

    # ===== ВЕДЕНИЕ =====
    if in_trade:
        if direction == "buy":
            move = (candle.high - entry) / PIP
            if move >= TRAIL_START:
                sl = max(sl, entry + TRAIL_LOCK * PIP)
                sl = max(sl, candle.high - TRAIL_STEP * PIP)

            if candle.low <= sl:
                profit = (sl - entry) * size
                in_trade = False
        else:
            move = (entry - candle.low) / PIP
            if move >= TRAIL_START:
                sl = min(sl, entry - TRAIL_LOCK * PIP)
                sl = min(sl, candle.low + TRAIL_STEP * PIP)

            if candle.high >= sl:
                profit = (entry - sl) * size
                in_trade = False

    # ===== ЗАКРЫТИЕ =====
    if not in_trade and 'profit' in locals():
        trades += 1
        balance += profit

        if profit > 0:
            wins += 1
            profit_sum += profit
            cur_loss_streak = 0
        else:
            losses += 1
            loss_sum += profit
            cur_loss_streak += 1
            max_loss_streak = max(max_loss_streak, cur_loss_streak)

            if cur_loss_streak >= 2:
                block_until_new_m30 = True

        max_balance = max(max_balance, balance)
        max_dd = min(max_dd, balance - max_balance)

        del profit

        if balance <= 0:
            break

# ================== ОТЧЁТ ==================
winrate = wins / trades * 100 if trades > 0 else 0

print("===== FINAL REPORT (EURUSD SOLO M30 → M1) =====")
print(f"Start balance: {START_BALANCE:.2f}")
print(f"Final balance: {balance:.2f}")
print(f"Trades: {trades}")
print(f"Wins / Losses: {wins} / {losses}")
print(f"Winrate: {winrate:.2f}%")
print(f"Profit sum: {profit_sum:.2f}")
print(f"Loss sum: {loss_sum:.2f}")
print(f"Max DD: {max_dd:.2f}")
print(f"Max loss streak (all trades): {max_loss_streak}")
print("RESULT:", "SURVIVED" if balance > 0 else "BLOWN")
