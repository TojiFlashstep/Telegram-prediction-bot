import requests
import csv
import os
from datetime import datetime
import pandas as pd

# ======================
# CONFIG
# ======================
TOKEN = "8960266220:AAFeztdi8gZ8Io51J4_Odm5lI5M0s0HwKo8"
CHAT_ID = "5614419481"
LOG_FILE = "predictions_log.csv"


# ======================
# INIT LOG
# ======================
def init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "home",
                "away",
                "predicted_total",
                "actual_total"
            ])


# ======================
# LAYER 1: CORE XG MODEL
# ======================
def expected_goals(scored, conceded):
    return (scored + conceded) / 2


# ======================
# LAYER 2: TOP vs BOTTOM INTERACTION (YOUR THEORY)
# ======================
def interaction_layer(hs, hc, as_, ac):
    """
    Measures imbalance vs mutual contribution
    """

    top_pressure = (hs + ac)
    bottom_resistance = (as_ + hc)

    balance = bottom_resistance - top_pressure

    interaction = (hs + as_) / (hc + ac + 0.1)

    return interaction, balance


# ======================
# LAYER 3: MULTI-DIRECTIONAL ENVIRONMENT
# ======================
def multi_directional_index(hs, hc, as_, ac):

    attack_flow = (hs + as_) / 2
    defensive_leak = (hc + ac) / 2

    index = attack_flow + defensive_leak

    if index > 3.0:
        return "VERY OPEN"
    elif index > 2.4:
        return "OPEN"
    elif index > 1.8:
        return "CONTROLLED"
    return "LOW EVENT"


def btts_environment(hs, hc, as_, ac):

    score_pressure = (hs + as_) / 2
    defensive_gap = (hc + ac) / 2

    score = score_pressure + defensive_gap

    if score > 2.8:
        return "HIGH BTTS"
    elif score > 2.2:
        return "MEDIUM BTTS"
    return "LOW BTTS"


# ======================
# LAYER 4: ODDS STRUCTURE (SIMPLIFIED INPUT MODEL)
# ======================
def odds_structure_signal(home_odds, over_odds, btts_odds):

    signal = 0

    # medium favorite zone (best BTTS environment historically)
    if 1.70 <= home_odds <= 2.20:
        signal += 1

    # over price not too compressed
    if 1.70 <= over_odds <= 1.95:
        signal += 1

    # BTTS not over-inflated
    if 1.75 <= btts_odds <= 2.05:
        signal += 1

    if signal == 3:
        return "UNDERVALUED MULTI-DIRECTIONAL"
    elif signal == 2:
        return "PARTIAL VALUE"
    return "NO EDGE / PRICED IN"


# ======================
# REGIME CLASSIFICATION
# ======================
def regime(total, md_status, interaction):

    if total >= 3.2 and md_status == "VERY OPEN":
        return "HIGH MULTI-DIRECTIONAL (STRONG OVER + BTTS)"

    if total >= 2.7 and md_status in ["OPEN", "VERY OPEN"]:
        return "BALANCED OPEN (BTTS + OVER LIVE)"

    if interaction > 1.2 and md_status == "CONTROLLED":
        return "ONE-DIRECTIONAL FAVORITE DOMINANCE"

    return "LOW SCORING / AVOID OVER"


# ======================
# FULL MATCH MODEL
# ======================
def predict_match(home, away, hs, hc, as_, ac, home_odds, over_odds, btts_odds):

    home_xg = expected_goals(hs, ac)
    away_xg = expected_goals(as_, hc)

    total = home_xg + away_xg

    interaction, balance = interaction_layer(hs, hc, as_, ac)

    md_status = multi_directional_index(hs, hc, as_, ac)

    btts = btts_environment(hs, hc, as_, ac)

    odds_signal = odds_structure_signal(home_odds, over_odds, btts_odds)

    regime_state = regime(total, md_status, interaction)

    if total > 2.8 and md_status in ["OPEN", "VERY OPEN"]:
        label = "OVER 2.5 STRONG"
    elif total > 2.5:
        label = "OVER 2.5 LEAN"
    else:
        label = "UNDER / AVOID"

    return {
        "home_xg": home_xg,
        "away_xg": away_xg,
        "total": total,
        "interaction": interaction,
        "md_status": md_status,
        "btts": btts,
        "odds_signal": odds_signal,
        "regime": regime_state,
        "prediction": label
    }


# ======================
# MOMENTUM SHIFT DETECTOR (FINAL VERSION)
# ======================
def momentum_shift():

    if not os.path.exists(LOG_FILE):
        return {"status": "NO DATA"}

    df = pd.read_csv(LOG_FILE).dropna()

    if len(df) < 12:
        return {"status": "NOT ENOUGH DATA"}

    df["actual_total"] = pd.to_numeric(df["actual_total"], errors="coerce")
    df = df.dropna()

    short = df.tail(3)
    long = df.tail(10)

    short_avg = short["actual_total"].mean()
    long_avg = long["actual_total"].mean()

    short_vol = short["actual_total"].std()
    long_vol = long["actual_total"].std()

    avg_shift = short_avg - long_avg
    vol_shift = short_vol - long_vol

    score = 0

    if avg_shift > 0.5 or avg_shift < -0.5:
        score += 1

    if vol_shift > 0.5:
        score += 1

    if score >= 2:
        return {"status": "ACTIVE SHIFT (DO NOT TRUST LAST 5 GAMES)"}

    if score == 1:
        return {"status": "EARLY SHIFT WARNING"}

    return {"status": "STABLE ENVIRONMENT"}


# ======================
# TELEGRAM
# ======================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})


# ======================
# LOGGING
# ======================
def log_match(home, away, total, actual=None):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), home, away, total, actual])


# ======================
# MESSAGE BUILDER
# ======================
def build_message(home, away, result, shift):

    return f"""
{home} vs {away}

Home xG: {result['home_xg']:.2f}
Away xG: {result['away_xg']:.2f}
Total: {result['total']:.2f}

Multi-Directional: {result['md_status']}
BTTS: {result['btts']}
Odds Signal: {result['odds_signal']}
Regime: {result['regime']}

Prediction: {result['prediction']}

MOMENTUM: {shift['status']}
"""


# ======================
# RUN SYSTEM
# ======================
matches = [
    # home, away, hs, hc, as_, ac, home_odds, over_odds, btts_odds
    ["Arsenal", "Chelsea", 2.1, 1.5, 1.7, 1.2, 1.85, 1.80, 1.75],
    ["Liverpool", "City", 2.4, 1.3, 2.0, 1.1, 2.10, 1.85, 1.78],
    ["Barcelona", "Madrid", 2.2, 1.6, 2.1, 1.4, 2.05, 1.90, 1.82]
]

init_log()

shift = momentum_shift()

for m in matches:

    result = predict_match(*m)

    message = build_message(m[0], m[1], result, shift)

    send_telegram(message)

    log_match(m[0], m[1], result["total"])

    print(f"Sent: {m[0]} vs {m[1]}")
