"""Phase 0 throwaway test send. Delete after Phase 0 gate is met.

Pulls ~5 numbers from yfinance, builds a minimal HTML table, and sends it via
SMTP over STARTTLS (port 587) using env-var credentials. No real error handling
beyond printing failures: the point is to prove delivery, runner-IP behavior, and
scheduler timing on GitHub Actions, not to be robust.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText

import yfinance as yf

TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow": "^DJI",
    "Russell 2000": "^RUT",
    "10-Year (^TNX)": "^TNX",
}


def latest_close(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            return "NO DATA"
        return f"{hist['Close'].iloc[-1]:.2f}"
    except Exception as exc:  # noqa: BLE001 - throwaway, just surface it
        print(f"pull failed for {symbol}: {exc}")
        return "ERROR"


def build_html():
    rows = "".join(
        f"<tr><td>{name}</td><td>{latest_close(sym)}</td></tr>"
        for name, sym in TICKERS.items()
    )
    return f"<h3>Phase 0 test send</h3><table border='1' cellpadding='6'>{rows}</table>"


def main():
    host = os.environ["SMTP_HOST"]
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    sender = os.environ["EMAIL_FROM"]
    recipient = os.environ["EMAIL_TO"]

    msg = MIMEText(build_html(), "html")
    msg["Subject"] = "Market Brief - Phase 0 test send"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(host, 587) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, password)
            server.sendmail(sender, [recipient], msg.as_string())
        print(f"sent to {recipient}")
    except Exception as exc:  # noqa: BLE001 - throwaway, just surface it
        print(f"send failed: {exc}")
        raise


if __name__ == "__main__":
    main()
