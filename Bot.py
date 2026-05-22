
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

