from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised only in missing optional dependency environments
    yf = None

START = "2020-01-01"
INITIAL = 100_000.0
LOOKBACK = 126
TOP_N = 3
RSI_EXIT = 85
HOLD_RANK = 5
DD_TRIGGER = 0.08
RECOVERY_FRACTION = 0.75
RISK_OFF_EXPOSURE = 0.50
PRODUCTION_COST = 0.0025
RSI_FULL_EXIT = 100

TICKERS = {
    "MOM30": "MOM30IETF.NS",
    "MOM50": "MOMENTUM50.NS",
    "MIDMOM": "MOMIDMTM.NS",
    "SMALLMOM": "SMALLCAP.NS",
    "MON100": "MON100.NS",
    "NIFTY": "NIFTYBEES.NS",
    "GOLD": "GOLDBEES.NS",
    "SILVER": "SILVERBEES.NS",
}

REFERENCE_METRICS = {
    "Final": 350_874.56,
    "CAGR": 0.2296,
    "MaxDD": -0.1857,
    "Sharpe": 1.323,
    "Trades": 52,
    "AnnualTurnover": 2.85,
}


@dataclass(frozen=True)
class ManualAction:
    etf: str
    action: str
    quantity: int | None
    approximate_value: float | None
    reason: str
    signal_date: str


def get_series(ticker: str) -> pd.Series:
    if yf is None:
        raise RuntimeError("Install yfinance: python3 -m pip install yfinance")
    df = yf.download(ticker, start=START, auto_adjust=False, progress=False, actions=False)
    if df.empty:
        raise RuntimeError(f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            s = df["Close"].iloc[:, 0]
        else:
            s = df.iloc[:, 0]
    else:
        s = df["Close"]
    s = pd.to_numeric(s, errors="coerce").dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def download_market_data() -> dict[str, pd.Series]:
    return {name: get_series(ticker) for name, ticker in TICKERS.items()}


def apply_mon100_correction(raw_data: dict[str, pd.Series]) -> dict[str, pd.Series]:
    corrected = {k: v.copy() for k, v in raw_data.items()}
    for d in ["2021-06-17", "2021-06-18"]:
        ts = pd.Timestamp(d)
        if "MON100" in corrected and ts in corrected["MON100"].index:
            corrected["MON100"].loc[ts] *= 10.0
    return corrected


def mon100_audit(raw_data: dict[str, pd.Series], corrected_data: dict[str, pd.Series]) -> bool:
    raw = raw_data["MON100"]
    corr = corrected_data["MON100"]
    checks = []
    for d in ["2021-06-17", "2021-06-18"]:
        ts = pd.Timestamp(d)
        checks.append(ts in raw.index and ts in corr.index and abs(corr.loc[ts] / raw.loc[ts] - 10.0) < 1e-9)
    ts = pd.Timestamp("2021-06-21")
    checks.append(ts in raw.index and ts in corr.index and abs(corr.loc[ts] - raw.loc[ts]) < 1e-9)
    win = corr.loc[(corr.index >= "2021-06-14") & (corr.index <= "2021-06-25")]
    daily = win.pct_change().dropna()
    max_abs = float(daily.abs().max()) if len(daily) else np.nan
    checks.append(bool(np.isfinite(max_abs) and max_abs < 0.20))
    return all(checks)


def build_panel(corrected_data: dict[str, pd.Series]) -> pd.DataFrame:
    panel = pd.DataFrame(corrected_data).sort_index()
    panel = panel[~panel.index.duplicated(keep="last")]
    complete_dates = panel.notna().all(axis=1)
    if not complete_dates.any():
        raise RuntimeError("FINAL STOPPED: no complete common market-data date exists.")
    last_complete = panel.index[complete_dates][-1]
    if last_complete != panel.index[-1]:
        panel = panel.loc[:last_complete].copy()
    return panel


def load_market_data() -> pd.DataFrame:
    raw = download_market_data()
    corrected = apply_mon100_correction(raw)
    if not mon100_audit(raw, corrected):
        raise RuntimeError("FINAL STOPPED: MON100 correction gate failed.")
    return build_panel(corrected)


def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    d = s.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    al = l.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    out = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    return out.where(~((al == 0) & (ag > 0)), 100.0)


def monthly_dates(idx) -> list[pd.Timestamp]:
    idx = pd.DatetimeIndex(idx)
    s = pd.Series(idx, index=idx)
    return list(s.groupby(s.index.to_period("M")).last())


def eligible(panel: pd.DataFrame, date: pd.Timestamp) -> dict[str, float]:
    loc = panel.index.get_loc(date)
    if loc < LOOKBACK:
        return {}
    old = panel.index[loc - LOOKBACK]
    out = {}
    for c in panel.columns:
        now = panel.at[date, c]
        prev = panel.at[old, c]
        if pd.notna(now) and pd.notna(prev) and now > 0 and prev > 0:
            out[c] = float(now / prev - 1)
    return out


def first_valid(panel: pd.DataFrame) -> pd.Timestamp:
    for d in monthly_dates(panel.index):
        if len(eligible(panel, d)) >= TOP_N:
            return d
    raise RuntimeError("No date has three eligible ETFs.")


def stats(eq: pd.Series) -> dict[str, float]:
    eq = pd.Series(eq).dropna()
    yrs = max((eq.index[-1] - eq.index[0]).days / 365.25, 1 / 365.25)
    final = float(eq.iloc[-1])
    ret = final / INITIAL - 1
    cagr = (final / INITIAL) ** (1 / yrs) - 1
    dr = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    peak = eq.cummax()
    dd = float((eq / peak - 1).min())
    sh = np.nan if dr.std(ddof=1) == 0 else np.sqrt(252) * dr.mean() / dr.std(ddof=1)
    neg = dr[dr < 0]
    so = np.nan if len(neg) < 2 or neg.std(ddof=1) == 0 else np.sqrt(252) * dr.mean() / neg.std(ddof=1)
    return {
        "Final": final,
        "Return": ret,
        "CAGR": cagr,
        "MaxDD": dd,
        "Sharpe": sh,
        "Sortino": so,
        "Calmar": cagr / abs(dd) if dd < 0 else np.nan,
    }


def run_forensic(panel: pd.DataFrame, start_date: pd.Timestamp, cost: float = PRODUCTION_COST,
                 hold_rank: int = HOLD_RANK, trigger: float = DD_TRIGGER,
                 reduced_exposure: float = RISK_OFF_EXPOSURE,
                 recovery_frac: float = RECOVERY_FRACTION):
    dates = panel.index
    rebal = set(monthly_dates(dates))
    rsis = pd.DataFrame({c: rsi(panel[c]) for c in panel.columns}, index=dates)
    cash = INITIAL
    holdings = {}
    half_sold = set()
    opened = {}
    trades = 0
    turnover = 0.0
    risk_on = False
    risk_events = 0
    risk_rebalances = 0
    eq_rows = []
    state_rows = []
    event_rows = []
    peak = INITIAL

    def market_value(pxs):
        return sum(q * float(pxs[t]) for t, q in holdings.items() if pd.notna(pxs.get(t)))

    def enforce_exposure(pxs, desired, reason):
        nonlocal cash, turnover, trades
        before_mv = market_value(pxs)
        before_eq = cash + before_mv
        target_mv = before_eq * desired
        if before_mv > target_mv + 1e-10:
            sell_value = before_mv - target_mv
            for t in list(holdings):
                if sell_value <= 1e-10:
                    break
                px = pxs.get(t)
                if pd.isna(px) or px <= 0:
                    continue
                value = holdings[t] * float(px)
                sell = min(value, sell_value)
                qsell = sell / float(px)
                cash += sell * (1 - cost)
                turnover += sell
                trades += 1
                holdings[t] -= qsell
                sell_value -= sell
                if holdings[t] <= 1e-12:
                    del holdings[t]
                    half_sold.discard(t)
                    opened.pop(t, None)
        elif before_mv < target_mv - 1e-10 and holdings:
            buy_value = target_mv - before_mv
            base_mv = market_value(pxs)
            if base_mv > 0:
                for t in list(holdings):
                    if buy_value <= 1e-10:
                        break
                    px = pxs.get(t)
                    if pd.isna(px) or px <= 0:
                        continue
                    weight = (holdings[t] * float(px)) / base_mv
                    gross = min(buy_value * weight, cash / (1 + cost))
                    if gross <= 1e-10:
                        continue
                    cash -= gross * (1 + cost)
                    turnover += gross
                    trades += 1
                    holdings[t] += gross / float(px)
                    buy_value -= gross
        after_mv = market_value(pxs)
        after_eq = cash + after_mv
        return before_eq, before_mv, after_eq, after_mv

    for date in dates:
        if date < start_date:
            continue
        pxs = panel.loc[date]
        rr = rsis.loc[date]
        pre_target = reduced_exposure if risk_on else 1.0
        pre_mv = market_value(pxs)
        pre_eq = cash + pre_mv
        pre_exp = pre_mv / pre_eq if pre_eq else np.nan

        for t in list(holdings):
            px = pxs.get(t)
            rv = rr.get(t)
            if pd.isna(px) or pd.isna(rv):
                continue
            qty = holdings[t]
            if t not in half_sold and rv >= RSI_EXIT:
                q = qty * 0.50
                gross = q * float(px)
                cash += gross * (1 - cost)
                turnover += gross
                holdings[t] -= q
                half_sold.add(t)
                trades += 1
                event_rows.append((date, "RSI_HALF_EXIT", t, float(rv), pre_eq, pre_exp, risk_on, "Half sold at RSI>=85"))
            elif t in half_sold and rv >= RSI_FULL_EXIT:
                gross = holdings[t] * float(px)
                cash += gross * (1 - cost)
                turnover += gross
                del holdings[t]
                half_sold.discard(t)
                opened.pop(t, None)
                trades += 1
                event_rows.append((date, "RSI_FULL_EXIT", t, float(rv), pre_eq, pre_exp, risk_on, "Full exit at RSI>=100"))

        mv = market_value(pxs)
        equity = cash + mv
        peak = max(peak, equity)
        dd = equity / peak - 1.0
        transition = False
        transition_reason = ""
        if not risk_on and dd <= -trigger:
            risk_on = True
            risk_events += 1
            transition = True
            transition_reason = "DD_TRIGGER"
        elif risk_on and dd >= -(trigger * recovery_frac):
            risk_on = False
            risk_rebalances += 1
            transition = True
            transition_reason = "RECOVERY"
        if transition:
            old = pre_target
            new = reduced_exposure if risk_on else 1.0
            event_rows.append((date, transition_reason, "", np.nan, equity, mv / equity if equity else np.nan, risk_on, f"{old:.2%}->{new:.2%}"))

        rebalance = False
        if date in rebal:
            rebalance = True
            scores = eligible(panel, date)
            ranked = [name for name, _score in sorted(scores.items(), key=lambda z: z[1], reverse=True)]
            rank_map = {name: i + 1 for i, name in enumerate(ranked)}
            keep = [t for t in holdings if rank_map.get(t, 999999) <= hold_rank]
            replace = [t for t in holdings if t not in keep]
            for t in replace:
                px = pxs.get(t)
                if pd.notna(px):
                    gross = holdings[t] * float(px)
                    cash += gross * (1 - cost)
                    turnover += gross
                    trades += 1
                holdings.pop(t, None)
                half_sold.discard(t)
                opened.pop(t, None)
                event_rows.append((date, "REPLACE_SELL", t, np.nan, equity, mv / equity if equity else np.nan, risk_on, "Rank outside hold rank"))
            slots = TOP_N - len(keep)
            candidates = [t for t in ranked if t not in keep and t not in holdings][:slots]
            if candidates:
                portfolio_value = cash + sum(holdings[t] * float(pxs[t]) for t in keep if pd.notna(pxs.get(t)))
                desired_total = portfolio_value * (reduced_exposure if risk_on else 1.0)
                existing_value = sum(holdings[t] * float(pxs[t]) for t in keep if pd.notna(pxs.get(t)))
                remaining_target = max(0.0, desired_total - existing_value)
                target = remaining_target / len(candidates)
                if not risk_on:
                    target = portfolio_value / TOP_N
                for t in candidates:
                    px = pxs.get(t)
                    if pd.notna(px) and px > 0 and target > 0:
                        q = target / float(px)
                        gross = q * float(px)
                        affordable = cash / (1 + cost)
                        if gross > affordable:
                            gross = affordable
                            q = gross / float(px)
                        if gross > 1e-10:
                            cash -= gross * (1 + cost)
                            turnover += gross
                            holdings[t] = q
                            opened[t] = date
                            trades += 1
                            event_rows.append((date, "REPLACE_BUY", t, np.nan, equity, mv / equity if equity else np.nan, risk_on, "New ranked candidate"))

        if transition:
            enforce_exposure(pxs, reduced_exposure if risk_on else 1.0, transition_reason)

        mv = market_value(pxs)
        equity = cash + mv
        actual_exp = mv / equity if equity else np.nan
        target_exp = reduced_exposure if risk_on else 1.0
        scores = eligible(panel, date) if date in rebal else {}
        ranked_today = [name for name, _score in sorted(scores.items(), key=lambda z: z[1], reverse=True)]
        state_rows.append({
            "Date": date,
            "Equity": equity,
            "Cash": cash,
            "MarketValue": mv,
            "ActualExposure": actual_exp,
            "TargetExposure": target_exp,
            "ExposureGap": actual_exp - target_exp,
            "Peak": peak,
            "Drawdown": equity / peak - 1.0,
            "RiskOn": risk_on,
            "RiskTransition": transition,
            "TransitionReason": transition_reason,
            "RiskEvents": risk_events,
            "RiskRebalances": risk_rebalances,
            "Trades": trades,
            "Holdings": ";".join(f"{t}:{holdings[t]:.6f}" for t in sorted(holdings)),
            "HalfSold": ";".join(sorted(half_sold)),
            "RebalanceDay": rebalance,
            "Top3": ";".join(ranked_today[:TOP_N]),
        })
        eq_rows.append((date, equity))

    eq = pd.Series([v for _, v in eq_rows], index=pd.DatetimeIndex([d for d, _ in eq_rows]), name=f"GORS_V53_HR{hold_rank}")
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    annual_turnover = turnover / (days / 365.25) / INITIAL
    state = pd.DataFrame(state_rows)
    events = pd.DataFrame(event_rows, columns=["Date", "Event", "Ticker", "RSI", "Equity", "Exposure", "RiskOn", "Detail"])
    return eq, trades, turnover, annual_turnover, risk_events, risk_rebalances, state, events


def run_frozen_backtest(panel: pd.DataFrame | None = None):
    panel = load_market_data() if panel is None else panel
    start_date = first_valid(panel)
    eq, trades, turnover, annual_turnover, risk_events, risk_rebalances, state, events = run_forensic(
        panel, start_date, PRODUCTION_COST, HOLD_RANK, DD_TRIGGER, RISK_OFF_EXPOSURE, RECOVERY_FRACTION
    )
    return {
        "panel": panel,
        "start_date": start_date,
        "equity": eq,
        "metrics": stats(eq),
        "trades": trades,
        "turnover": turnover,
        "annual_turnover": annual_turnover,
        "risk_events": risk_events,
        "risk_rebalances": risk_rebalances,
        "state": state,
        "events": events,
    }


def latest_completed_common_date(panel: pd.DataFrame, as_of=None) -> pd.Timestamp:
    if panel.empty:
        raise RuntimeError("Market data is empty.")
    as_of_ts = pd.Timestamp(as_of or datetime.now(timezone.utc).date()).tz_localize(None)
    complete = panel.loc[panel.index < as_of_ts].notna().all(axis=1)
    if not complete.any():
        raise RuntimeError("No completed common market-data date exists before as-of date.")
    return panel.loc[panel.index < as_of_ts].index[complete][-1]


def parse_holdings(value: str) -> dict[str, float]:
    out = {}
    if not isinstance(value, str) or not value:
        return out
    for item in value.split(";"):
        if not item:
            continue
        name, qty = item.split(":", 1)
        out[name] = float(qty)
    return out


def calculate_gors_signal(panel: pd.DataFrame | None = None, as_of=None) -> dict:
    panel = load_market_data() if panel is None else panel
    cutoff = latest_completed_common_date(panel, as_of=as_of)
    result = run_frozen_backtest(panel.loc[:cutoff].copy())
    state = result["state"]
    last = state.iloc[-1]
    holdings = parse_holdings(last["Holdings"])
    prices = {c: float(result["panel"].loc[cutoff, c]) for c in result["panel"].columns if pd.notna(result["panel"].loc[cutoff, c])}
    scores = eligible(result["panel"], cutoff)
    ranked = sorted(scores.items(), key=lambda z: z[1], reverse=True)
    top3_table = []
    rsis = pd.DataFrame({c: rsi(result["panel"][c]) for c in result["panel"].columns}, index=result["panel"].index)
    rank_map = {name: i + 1 for i, (name, _score) in enumerate(ranked)}
    for name in holdings:
        top3_table.append({
            "Rank": rank_map.get(name),
            "ETF": name,
            "Signal/Score": scores.get(name),
            "RSI": float(rsis.loc[cutoff, name]) if name in rsis and pd.notna(rsis.loc[cutoff, name]) else np.nan,
            "Price": prices.get(name),
            "Status": "Held",
        })
    return {
        "signal_date": cutoff.date().isoformat(),
        "risk_state": "RISK OFF" if bool(last["RiskOn"]) else "RISK ON",
        "target_exposure_pct": float(last["TargetExposure"]),
        "actual_exposure_pct": float(last["ActualExposure"]),
        "current_drawdown": float(last["Drawdown"]),
        "equity": float(last["Equity"]),
        "cash": float(last["Cash"]),
        "market_value": float(last["MarketValue"]),
        "holdings": holdings,
        "top3": list(holdings.keys()),
        "top3_table": top3_table,
        "prices": prices,
        "state": state,
        "events": result["events"],
        "metrics": result["metrics"],
        "trades": result["trades"],
        "annual_turnover": result["annual_turnover"],
    }


def build_holdings_table(kite_rows: list[dict], prices: dict[str, float]) -> pd.DataFrame:
    rows = []
    for row in kite_rows:
        etf = row["etf"]
        qty = float(row.get("quantity") or 0)
        price = float(prices.get(etf) or row.get("last_price") or 0)
        value = qty * price
        rows.append({"ETF": etf, "Quantity": qty, "Price": price, "Portfolio Value": value})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["ETF", "Quantity", "Price", "Portfolio Value", "Weight"])
    total = float(df["Portfolio Value"].sum())
    df["Weight"] = df["Portfolio Value"] / total if total else 0.0
    return df


def build_manual_actions(signal: dict, kite_rows: list[dict], cash: float) -> list[ManualAction]:
    target_holdings = signal.get("holdings", {})
    prices = signal["prices"]
    current = {row["etf"]: float(row.get("quantity") or 0) for row in kite_rows}
    actions = []
    for etf, target_qty in target_holdings.items():
        price = float(prices.get(etf) or 0)
        current_qty = current.get(etf, 0.0)
        diff = float(target_qty) - current_qty
        if price <= 0 or abs(diff) < 1.0:
            continue
        action = "BUY" if diff > 0 else "SELL"
        qty = int(abs(diff))
        actions.append(ManualAction(
            etf=etf,
            action=action,
            quantity=qty,
            approximate_value=qty * price,
            reason=f"Match frozen GORS target holding under {signal['risk_state']}.",
            signal_date=signal["signal_date"],
        ))
    for etf, qty in current.items():
        if etf not in target_holdings and abs(qty) >= 1.0:
            price = float(prices.get(etf) or 0)
            actions.append(ManualAction(
                etf=etf,
                action="SELL",
                quantity=int(abs(qty)),
                approximate_value=int(abs(qty)) * price if price > 0 else None,
                reason="ETF is not in frozen GORS target holdings.",
                signal_date=signal["signal_date"],
            ))
    return actions
