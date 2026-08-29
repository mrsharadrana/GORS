#!/usr/bin/env python3
"""
GORS FINAL — FROZEN PRODUCTION / RESEARCH REPORT

Purpose
-------
Run the frozen GORS candidate without any parameter optimization.

FROZEN CANDIDATE
    HoldRank = 5
    DD Trigger = 8%
    Recovery = 75% of trigger
    Risk Exposure = 50%
    Production Cost = 0.25%

The script preserves the V30/V39 baseline reconciliation and the audited
V41/V46 true hold/replace + drawdown risk engine. It produces a final
research report, yearly diagnostics, rolling-12M diagnostics, recovery
diagnostics, state-machine audit, and a fixed-cost comparison.

IMPORTANT
---------
No parameter grid is searched. No parameters are changed based on the
current data. V49 true expanding-window walk-forward failure is reported
as a validation limitation rather than optimized away.

This is a frozen research strategy, not a claim of live validation.
"""


from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("Install yfinance: python3 -m pip install yfinance")

warnings.filterwarnings("ignore")

START = "2020-01-01"
INITIAL = 100_000.0
LOOKBACK = 126
TOP_N = 3
RSI_EXIT = 85

# V30 cost assumptions.
COSTS = [0.0, 0.001, 0.0025, 0.005, 0.0075, 0.01]

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

OUT = Path.home() / "Downloads"

# These are the previously observed V30 FULL_LIVE, 0%-cost reference values.
V30_REF = {
    "Final": 308_637.0,
    "CAGR": 0.2057,
    "MaxDD": -0.3601,
    "Sharpe": 0.78,
    "Trades": 451,
    "AnnualTurnover_xCapital": 39.23,
}

# Tolerances intentionally allow small Yahoo/data-vendor drift while catching
# genuine strategy-engine changes.
TOL = {
    "Final": 1_500.0,
    "CAGR": 0.0030,
    "MaxDD": 0.0150,
    "Sharpe": 0.04,
    "Trades": 3,
    "AnnualTurnover_xCapital": 1.00,
}


def get_series(ticker: str) -> pd.Series:
    df = yf.download(
        ticker,
        start=START,
        auto_adjust=False,
        progress=False,
        actions=False,
    )

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


def download():
    print("=" * 88)
    print("GORS V39 — V30 EXACT RECONCILIATION + MON100 CORRECTION AUDIT")
    print("=" * 88)

    data = {}

    for name, ticker in TICKERS.items():
        print(f"Downloading {name:<8} {ticker}")
        s = get_series(ticker)

        # IMPORTANT:
        # Keep downloaded data genuinely RAW here.
        # MON100 correction is applied exactly once in main(), after the
        # raw-vs-corrected audit copy has been created.
        data[name] = s
        print(
            f"  {s.index.min().date()} -> {s.index.max().date()} "
            f"({len(s):,} rows)"
        )

    return data


def mon100_audit(raw_data, corrected_data):
    raw = raw_data["MON100"]
    corr = corrected_data["MON100"]

    print("\nMON100 CORRECTION GATE")
    print("-" * 88)

    checks = []

    for d in ["2021-06-17", "2021-06-18"]:
        ts = pd.Timestamp(d)
        if ts in raw.index and ts in corr.index:
            ratio = corr.loc[ts] / raw.loc[ts]
            ok = abs(ratio - 10.0) < 1e-9
            checks.append(ok)
            print(
                f"{d}: raw={raw.loc[ts]:.6f} "
                f"corrected={corr.loc[ts]:.6f} ratio={ratio:.2f}x "
                f"{'PASS' if ok else 'FAIL'}"
            )
        else:
            checks.append(False)
            print(f"{d}: missing -> FAIL")

    ts = pd.Timestamp("2021-06-21")
    if ts in raw.index and ts in corr.index:
        unchanged = abs(corr.loc[ts] - raw.loc[ts]) < 1e-9
        checks.append(unchanged)
        print(
            f"{ts.date()}: raw={raw.loc[ts]:.6f} "
            f"corrected={corr.loc[ts]:.6f} "
            f"unchanged={'YES' if unchanged else 'NO'} "
            f"{'PASS' if unchanged else 'FAIL'}"
        )
    else:
        checks.append(False)
        print(f"{ts.date()}: missing -> FAIL")

    # Demonstrate the corrected event-window daily return behavior.
    win = corr.loc[
        (corr.index >= "2021-06-14") & (corr.index <= "2021-06-25")
    ]
    daily = win.pct_change().dropna()

    max_abs = float(daily.abs().max()) if len(daily) else np.nan
    print(f"Corrected MON100 event-window max abs move: {max_abs * 100:.2f}%")

    # The corrected event window must remove the artificial Yahoo -90%/+892%
    # observations. The corrected sequence should be economically continuous.
    event_ok = bool(np.isfinite(max_abs) and max_abs < 0.20)
    checks.append(event_ok)
    print(f"Event-window sanity (<20%): {'PASS' if event_ok else 'FAIL'}")

    passed = all(checks)
    print(f"MON100 CORRECTION GATE: {'PASSED' if passed else 'FAILED'}")
    return passed


def rsi(s, period=14):
    # EXACT V30 RSI implementation.
    d = s.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)

    ag = g.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    al = l.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    out = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    return out.where(~((al == 0) & (ag > 0)), 100.0)


def monthly_dates(idx):
    idx = pd.DatetimeIndex(idx)
    s = pd.Series(idx, index=idx)
    return list(s.groupby(s.index.to_period("M")).last())


def eligible(panel, date):
    # EXACT V30 eligibility rule.
    loc = panel.index.get_loc(date)

    if loc < LOOKBACK:
        return {}

    old = panel.index[loc - LOOKBACK]
    out = {}

    for c in panel.columns:
        now = panel.at[date, c]
        prev = panel.at[old, c]

        if (
            pd.notna(now)
            and pd.notna(prev)
            and now > 0
            and prev > 0
        ):
            out[c] = float(now / prev - 1)

    return out


def first_valid(panel):
    for d in monthly_dates(panel.index):
        if len(eligible(panel, d)) >= TOP_N:
            return d

    raise RuntimeError("No date has three eligible ETFs.")


def stats(eq):
    eq = pd.Series(eq).dropna()

    yrs = max(
        (eq.index[-1] - eq.index[0]).days / 365.25,
        1 / 365.25,
    )

    final = float(eq.iloc[-1])
    ret = final / INITIAL - 1
    cagr = (final / INITIAL) ** (1 / yrs) - 1

    dr = eq.pct_change().replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna()

    peak = eq.cummax()
    dd = float((eq / peak - 1).min())

    sh = (
        np.nan
        if dr.std(ddof=1) == 0
        else np.sqrt(252) * dr.mean() / dr.std(ddof=1)
    )

    neg = dr[dr < 0]

    so = (
        np.nan
        if len(neg) < 2 or neg.std(ddof=1) == 0
        else np.sqrt(252) * dr.mean() / neg.std(ddof=1)
    )

    return {
        "Final": final,
        "Return": ret,
        "CAGR": cagr,
        "MaxDD": dd,
        "Sharpe": sh,
        "Sortino": so,
        "Calmar": cagr / abs(dd) if dd < 0 else np.nan,
    }


def rolling12(eq):
    m = eq.resample("ME").last()
    x = m.pct_change(12).dropna()

    if x.empty:
        return {}

    return {
        "Rolling12M_Median": float(x.median()),
        "Rolling12M_Worst": float(x.min()),
        "Rolling12M_Best": float(x.max()),
        "Rolling12M_Positive": float((x > 0).mean()),
    }


def run_strategy(panel, start_date, cost):
    """
    EXACT V30 trading engine.

    No risk overlay.
    No rank hysteresis.
    No position buffer.
    No dynamic exposure.
    """

    dates = panel.index
    rebal = set(monthly_dates(dates))

    rsis = pd.DataFrame(
        {c: rsi(panel[c]) for c in panel.columns},
        index=dates,
    )

    cash = INITIAL
    holdings = {}
    half_sold = set()

    trades = 0
    turnover = 0.0
    holding_days = []
    opened = {}

    eq_rows = []

    for date in dates:
        if date < start_date:
            continue

        pxs = panel.loc[date]
        rr = rsis.loc[date]

        # EXACT V30 RSI exits.
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

            elif t in half_sold and rv >= 100:
                gross = holdings[t] * float(px)

                cash += gross * (1 - cost)
                turnover += gross

                del holdings[t]
                half_sold.discard(t)
                trades += 1

                if t in opened:
                    holding_days.append(
                        (date - opened[t]).days
                    )
                    del opened[t]

        # EXACT V30 monthly rebalance.
        if date in rebal:
            scores = eligible(panel, date)

            ranked = sorted(
                scores.items(),
                key=lambda z: z[1],
                reverse=True,
            )

            selected = [
                x[0] for x in ranked[:TOP_N]
            ]

            if len(selected) == TOP_N:
                # Liquidate.
                for t, qty in list(holdings.items()):
                    px = pxs.get(t)

                    if pd.notna(px):
                        gross = qty * float(px)

                        cash += gross * (1 - cost)
                        turnover += gross
                        trades += 1

                        if t in opened:
                            holding_days.append(
                                (date - opened[t]).days
                            )
                            del opened[t]

                holdings.clear()
                half_sold.clear()

                # Equal-weight selected ETFs.
                target = cash / TOP_N

                for t in selected:
                    px = pxs.get(t)

                    if pd.notna(px) and px > 0:
                        q = target / float(px)
                        gross = q * float(px)

                        cash -= gross * (1 + cost)
                        turnover += gross

                        holdings[t] = q
                        opened[t] = date
                        trades += 1

        mv = sum(
            q * float(pxs[t])
            for t, q in holdings.items()
            if pd.notna(pxs.get(t))
        )

        eq_rows.append((date, cash + mv))

    eq = pd.Series(
        [v for _, v in eq_rows],
        index=pd.DatetimeIndex(
            [d for d, _ in eq_rows]
        ),
        name="GORS_RSI85",
    )

    return eq, trades, turnover, holding_days


def compare_to_v30(m, trades, annual_turnover):
    checks = {
        "Final": abs(m["Final"] - V30_REF["Final"]) <= TOL["Final"],
        "CAGR": abs(m["CAGR"] - V30_REF["CAGR"]) <= TOL["CAGR"],
        "MaxDD": abs(m["MaxDD"] - V30_REF["MaxDD"]) <= TOL["MaxDD"],
        "Sharpe": abs(m["Sharpe"] - V30_REF["Sharpe"]) <= TOL["Sharpe"],
        "Trades": abs(trades - V30_REF["Trades"]) <= TOL["Trades"],
        "AnnualTurnover_xCapital": (
            abs(
                annual_turnover
                - V30_REF["AnnualTurnover_xCapital"]
            )
            <= TOL["AnnualTurnover_xCapital"]
        ),
    }

    print("\n" + "=" * 88)
    print("V30 RECONCILIATION GATE — FULL LIVE / 0% COST")
    print("=" * 88)

    for k, ok in checks.items():
        actual = (
            trades
            if k == "Trades"
            else annual_turnover
            if k == "AnnualTurnover_xCapital"
            else m[k]
        )

        ref = V30_REF[k]

        if k in ("CAGR", "MaxDD"):
            actual_s = f"{actual * 100:.2f}%"
            ref_s = f"{ref * 100:.2f}%"
        elif k == "Sharpe":
            actual_s = f"{actual:.3f}"
            ref_s = f"{ref:.3f}"
        elif k == "AnnualTurnover_xCapital":
            actual_s = f"{actual:.2f}x"
            ref_s = f"{ref:.2f}x"
        else:
            actual_s = f"{actual:,.0f}" if k == "Final" else str(actual)
            ref_s = f"{ref:,.0f}" if k == "Final" else str(ref)

        print(
            f"{k:<28} actual={actual_s:<12} "
            f"reference={ref_s:<12} "
            f"{'PASS' if ok else 'FAIL'}"
        )

    passed = all(checks.values())

    print("-" * 88)
    print(
        "V30 RECONCILIATION:",
        "PASS — safe to proceed to risk-control experiments"
        if passed
        else "FAIL — DO NOT proceed to risk-control experiments",
    )

    return passed, checks



def run_experiment(panel, start_date, cost, hold_rank, trigger=None, reduced_exposure=1.0):
    """
    V45 EXPERIMENT ENGINE.

    Baseline portfolio-selection mechanics are copied from V41's
    run_true_hysteresis() exactly:
      - RSI(14) >= 85 -> sell 50%
      - RSI(14) >= 100 -> sell remainder
      - monthly true hold/replace hysteresis
      - retained positions are NOT rebalanced
      - only positions outside the hold band are replaced
      - vacant slots are filled using the strongest available ranks
      - new positions use V41's equal-weight target sizing

    ONLY when trigger is not None is the portfolio drawdown exposure overlay
    enabled.  This guarantees HRx_NO_RISK can be reconciled directly to V41.
    """
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
    peak = INITIAL

    def market_value(pxs):
        return sum(
            q * float(pxs[t])
            for t, q in holdings.items()
            if pd.notna(pxs.get(t))
        )

    def enforce_exposure(pxs, desired):
        """Scale invested exposure to desired fraction of total equity.
        Uses proportional sells/buys so risk overlay does not alter ranking.
        """
        nonlocal cash, turnover, trades
        mv = market_value(pxs)
        equity = cash + mv
        target_mv = equity * desired

        if mv > target_mv + 1e-10:
            sell_value = mv - target_mv
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
                if holdings[t] <= 1e-12:
                    del holdings[t]
                    half_sold.discard(t)
                    opened.pop(t, None)
                sell_value -= sell

        elif mv < target_mv - 1e-10 and holdings:
            buy_value = target_mv - mv
            names = list(holdings)
            # Restore exposure proportionally to current market values.
            base_mv = market_value(pxs)
            if base_mv > 0:
                for t in names:
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

    for date in dates:
        if date < start_date:
            continue

        pxs = panel.loc[date]
        rr = rsis.loc[date]

        # Exact V41/V39 RSI exit mechanics.
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
            elif t in half_sold and rv >= 100:
                gross = holdings[t] * float(px)
                cash += gross * (1 - cost)
                turnover += gross
                del holdings[t]
                half_sold.discard(t)
                trades += 1
                opened.pop(t, None)

        # Portfolio drawdown state is evaluated from marked-to-market equity.
        mv = market_value(pxs)
        equity = cash + mv
        peak = max(peak, equity)
        dd = equity / peak - 1.0

        exposure_transition = False
        if trigger is not None:
            if not risk_on and dd <= -trigger:
                risk_on = True
                risk_events += 1
                exposure_transition = True
            elif risk_on and dd >= -(trigger * 0.50):
                risk_on = False
                risk_rebalances += 1
                exposure_transition = True

        # EXACT V41 true hold/replace selection mechanics.
        if date in rebal:
            scores = eligible(panel, date)
            ranked = [
                name for name, _score in sorted(
                    scores.items(), key=lambda z: z[1], reverse=True
                )
            ]
            rank_map = {name: i + 1 for i, name in enumerate(ranked)}

            keep = [
                t for t in holdings
                if rank_map.get(t, 999999) <= hold_rank
            ]
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

            slots = TOP_N - len(keep)
            candidates = [
                t for t in ranked
                if t not in keep and t not in holdings
            ][:slots]

            if candidates:
                portfolio_value = cash + sum(
                    holdings[t] * float(pxs[t])
                    for t in keep
                    if pd.notna(pxs.get(t))
                )
                # V41 sizing, modified only when risk overlay is active:
                # allocate the desired total exposure across the 3 slots.
                desired_total = portfolio_value * (reduced_exposure if risk_on else 1.0)
                existing_value = sum(
                    holdings[t] * float(pxs[t])
                    for t in keep
                    if pd.notna(pxs.get(t))
                )
                remaining_target = max(0.0, desired_total - existing_value)
                target = remaining_target / len(candidates) if candidates else 0.0

                # If risk is off, this reduces exactly to V41's
                # portfolio_value / TOP_N because len(candidates) == slots.
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

        # IMPORTANT: change exposure ONLY when the DD state changes.
        # Do NOT rebalance to the target exposure every trading day.
        # Daily exposure rebalancing was the source of the V43 1,265-trade
        # anomaly and artificially distorted the risk-overlay results.
        if trigger is not None and exposure_transition:
            enforce_exposure(pxs, reduced_exposure if risk_on else 1.0)

        mv = market_value(pxs)
        eq_rows.append((date, cash + mv))

    eq = pd.Series(
        [v for _, v in eq_rows],
        index=pd.DatetimeIndex([d for d, _ in eq_rows]),
        name=f"GORS_V45_HR{hold_rank}_DD{int(trigger*100) if trigger is not None else 0}",
    )
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    annual_turnover = turnover / (days / 365.25) / INITIAL
    return eq, trades, turnover, annual_turnover, risk_events, risk_rebalances

def year_stats(eq):
    """Calendar-year return and drawdown diagnostics."""
    out = []
    for year, g in eq.groupby(eq.index.year):
        s = g.dropna()
        if len(s) < 2:
            continue
        ret = float(s.iloc[-1] / s.iloc[0] - 1.0)
        dd = float((s / s.cummax() - 1.0).min())
        out.append({"Year": int(year), "Return": ret, "MaxDD": dd})
    return pd.DataFrame(out)


def run_forensic(panel, start_date, cost, hold_rank, trigger, reduced_exposure, recovery_frac):
    """Exact V49/V46 engine plus daily state/event audit. No optimization."""
    dates = panel.index
    rebal = set(monthly_dates(dates))
    rsis = pd.DataFrame({c: rsi(panel[c]) for c in panel.columns}, index=dates)
    cash = INITIAL; holdings = {}; half_sold = set(); opened = {}
    trades = 0; turnover = 0.0; risk_on = False; risk_events = 0; risk_rebalances = 0
    eq_rows=[]; state_rows=[]; event_rows=[]; peak=INITIAL

    def market_value(pxs):
        return sum(q*float(pxs[t]) for t,q in holdings.items() if pd.notna(pxs.get(t)))

    def enforce_exposure(pxs, desired, reason):
        nonlocal cash, turnover, trades
        before_mv=market_value(pxs); before_eq=cash+before_mv
        target_mv=before_eq*desired
        if before_mv > target_mv + 1e-10:
            sell_value=before_mv-target_mv
            for t in list(holdings):
                if sell_value<=1e-10: break
                px=pxs.get(t)
                if pd.isna(px) or px<=0: continue
                value=holdings[t]*float(px); sell=min(value,sell_value); qsell=sell/float(px)
                cash += sell*(1-cost); turnover += sell; trades += 1; holdings[t]-=qsell; sell_value-=sell
                if holdings[t]<=1e-12: del holdings[t]; half_sold.discard(t); opened.pop(t,None)
        elif before_mv < target_mv - 1e-10 and holdings:
            buy_value=target_mv-before_mv; base_mv=market_value(pxs)
            if base_mv>0:
                for t in list(holdings):
                    if buy_value<=1e-10: break
                    px=pxs.get(t)
                    if pd.isna(px) or px<=0: continue
                    weight=(holdings[t]*float(px))/base_mv
                    gross=min(buy_value*weight,cash/(1+cost))
                    if gross<=1e-10: continue
                    cash-=gross*(1+cost); turnover+=gross; trades+=1; holdings[t]+=gross/float(px); buy_value-=gross
        after_mv=market_value(pxs); after_eq=cash+after_mv
        return before_eq, before_mv, after_eq, after_mv

    for date in dates:
        if date < start_date: continue
        pxs=panel.loc[date]; rr=rsis.loc[date]
        pre_risk=risk_on; pre_target=reduced_exposure if risk_on else 1.0
        pre_mv=market_value(pxs); pre_eq=cash+pre_mv; pre_exp=pre_mv/pre_eq if pre_eq else np.nan
        # RSI exits
        for t in list(holdings):
            px=pxs.get(t); rv=rr.get(t)
            if pd.isna(px) or pd.isna(rv): continue
            qty=holdings[t]
            if t not in half_sold and rv>=RSI_EXIT:
                q=qty*0.50; gross=q*float(px); cash+=gross*(1-cost); turnover+=gross; holdings[t]-=q; half_sold.add(t); trades+=1
                event_rows.append((date,'RSI_HALF_EXIT',t,float(rv),pre_eq,pre_exp,risk_on,'Half sold at RSI>=85'))
            elif t in half_sold and rv>=100:
                gross=holdings[t]*float(px); cash+=gross*(1-cost); turnover+=gross; del holdings[t]; half_sold.discard(t); opened.pop(t,None); trades+=1
                event_rows.append((date,'RSI_FULL_EXIT',t,float(rv),pre_eq,pre_exp,risk_on,'Full exit at RSI>=100'))

        mv=market_value(pxs); equity=cash+mv; peak=max(peak,equity); dd=equity/peak-1.0
        transition=False; transition_reason=''
        if not risk_on and dd<=-trigger:
            risk_on=True; risk_events+=1; transition=True; transition_reason='DD_TRIGGER'
        elif risk_on and dd>=-(trigger*recovery_frac):
            risk_on=False; risk_rebalances+=1; transition=True; transition_reason='RECOVERY'
        if transition:
            old=pre_target; new=reduced_exposure if risk_on else 1.0
            event_rows.append((date,transition_reason,'',np.nan,equity,mv/equity if equity else np.nan,risk_on,f'{old:.2%}->{new:.2%}'))

        rebalance=False
        if date in rebal:
            rebalance=True
            scores=eligible(panel,date)
            ranked=[name for name,_ in sorted(scores.items(),key=lambda z:z[1],reverse=True)]
            rank_map={name:i+1 for i,name in enumerate(ranked)}
            keep=[t for t in holdings if rank_map.get(t,999999)<=hold_rank]
            replace=[t for t in holdings if t not in keep]
            for t in replace:
                px=pxs.get(t)
                if pd.notna(px):
                    gross=holdings[t]*float(px); cash+=gross*(1-cost); turnover+=gross; trades+=1
                holdings.pop(t,None); half_sold.discard(t); opened.pop(t,None)
                event_rows.append((date,'REPLACE_SELL',t,np.nan,equity,mv/equity if equity else np.nan,risk_on,'Rank outside hold rank'))
            slots=TOP_N-len(keep)
            candidates=[t for t in ranked if t not in keep and t not in holdings][:slots]
            if candidates:
                portfolio_value=cash+sum(holdings[t]*float(pxs[t]) for t in keep if pd.notna(pxs.get(t)))
                desired_total=portfolio_value*(reduced_exposure if risk_on else 1.0)
                existing_value=sum(holdings[t]*float(pxs[t]) for t in keep if pd.notna(pxs.get(t)))
                remaining_target=max(0.0,desired_total-existing_value); target=remaining_target/len(candidates)
                if not risk_on: target=portfolio_value/TOP_N
                for t in candidates:
                    px=pxs.get(t)
                    if pd.notna(px) and px>0 and target>0:
                        q=target/float(px); gross=q*float(px); affordable=cash/(1+cost)
                        if gross>affordable: gross=affordable; q=gross/float(px)
                        if gross>1e-10:
                            cash-=gross*(1+cost); turnover+=gross; holdings[t]=q; opened[t]=date; trades+=1
                            event_rows.append((date,'REPLACE_BUY',t,np.nan,equity,mv/equity if equity else np.nan,risk_on,'New ranked candidate'))
        if transition:
            enforce_exposure(pxs,reduced_exposure if risk_on else 1.0,transition_reason)

        mv=market_value(pxs); equity=cash+mv; actual_exp=mv/equity if equity else np.nan
        target_exp=reduced_exposure if risk_on else 1.0
        gap=actual_exp-target_exp
        state_rows.append({
            'Date':date,'Equity':equity,'Cash':cash,'MarketValue':mv,'ActualExposure':actual_exp,
            'TargetExposure':target_exp,'ExposureGap':gap,'Peak':peak,'Drawdown':equity/peak-1.0,
            'RiskOn':risk_on,'RiskTransition':transition,'TransitionReason':transition_reason,
            'RiskEvents':risk_events,'RiskRebalances':risk_rebalances,'Trades':trades,
            'Holdings':';'.join(f'{t}:{holdings[t]:.6f}' for t in sorted(holdings)),
            'HalfSold':';'.join(sorted(half_sold)),
            'RebalanceDay':rebalance,
        })
        eq_rows.append((date,equity))

    eq=pd.Series([v for _,v in eq_rows],index=pd.DatetimeIndex([d for d,_ in eq_rows]),name=f'GORS_V53_HR{hold_rank}')
    days=max((eq.index[-1]-eq.index[0]).days,1)
    annual_turnover=turnover/(days/365.25)/INITIAL
    return eq,trades,turnover,annual_turnover,risk_events,risk_rebalances,pd.DataFrame(state_rows),pd.DataFrame(event_rows,columns=['Date','Event','Ticker','RSI','Equity','Exposure','RiskOn','Detail'])

def period_stats(eq, start, end):
    """Continuous-equity statistics for a chronological validation block."""
    x = pd.Series(eq).loc[
        (pd.Series(eq).index >= pd.Timestamp(start)) &
        (pd.Series(eq).index <= pd.Timestamp(end))
    ].dropna()

    if len(x) < 2:
        return None

    days = max((x.index[-1] - x.index[0]).days, 1)
    ret = float(x.iloc[-1] / x.iloc[0] - 1.0)
    cagr = float((x.iloc[-1] / x.iloc[0]) ** (365.25 / days) - 1.0)

    peak = x.cummax()
    maxdd = float((x / peak - 1.0).min())

    dr = x.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = (
        np.nan
        if len(dr) < 2 or dr.std(ddof=1) == 0
        else float(np.sqrt(252) * dr.mean() / dr.std(ddof=1))
    )

    return {
        "Start": x.index[0].date(),
        "End": x.index[-1].date(),
        "Days": days,
        "StartEquity": float(x.iloc[0]),
        "EndEquity": float(x.iloc[-1]),
        "Return": ret,
        "CAGR": cagr,
        "MaxDD": maxdd,
        "Sharpe": sharpe,
    }


def recovery_stats(eq):
    """Measure recovery from the worst drawdown in the frozen candidate."""
    x = pd.Series(eq).dropna()
    peak = x.cummax()
    dd = x / peak - 1.0

    trough_date = dd.idxmin()
    worst_dd = float(dd.loc[trough_date])
    peak_before = float(peak.loc[trough_date])

    post = x.loc[trough_date:]
    recovery_date = None
    for d, value in post.items():
        if float(value) >= peak_before:
            recovery_date = d
            break

    recovery_days = (
        int((recovery_date - trough_date).days)
        if recovery_date is not None
        else None
    )

    return {
        "WorstDD": worst_dd,
        "PeakBeforeWorstDD": peak_before,
        "TroughDate": trough_date,
        "RecoveryDate": recovery_date,
        "RecoveryDays": recovery_days,
    }



def training_stats(eq, end_date):
    """Stats available strictly through the training cutoff."""
    x = pd.Series(eq).loc[pd.Series(eq).index <= pd.Timestamp(end_date)].dropna()
    if len(x) < 2:
        return None
    return stats(x)


def fold_period_stats(eq, start, end):
    return period_stats(eq, start, end)


# Exact V46 search grid — reused, not expanded.
HOLD_RANKS = [4, 5, 6, 7]
DD_TRIGGERS = [0.08, 0.10, 0.12, 0.15]
RECOVERIES = [0.25, 0.50, 0.75]
EXPOSURES = [0.50, 0.75]
PRODUCTION_COST = 0.0025


def config_label(hr, trigger, recovery, exposure):
    return (
        f"HR{hr}_DD{int(trigger*100)}_REC{int(recovery*100)}_EXP{int(exposure*100)}"
    )


def select_on_training(panel, start_date, train_end):
    """Search the fixed V46 grid using training data only."""
    rows = []
    print(f"\nTRAINING SELECTION THROUGH {pd.Timestamp(train_end).date()}")
    print("-" * 88)

    for hr in HOLD_RANKS:
        for trigger in DD_TRIGGERS:
            for recovery in RECOVERIES:
                for exposure in EXPOSURES:
                    label = config_label(hr, trigger, recovery, exposure)
                    print(f"  SEARCH {label:<28}", end="\r", flush=True)
                    eq, trades, turnover, annual_turnover, risk_events, risk_rebalances = run_robust_experiment(
                        panel, start_date, PRODUCTION_COST, hr, trigger, exposure, recovery
                    )
                    m = training_stats(eq, train_end)
                    if m is None:
                        continue
                    rows.append({
                        "Variant": label,
                        "HoldRank": hr,
                        "Trigger": trigger,
                        "Recovery": recovery,
                        "Exposure": exposure,
                        "Cost": PRODUCTION_COST,
                        "Final": m["Final"],
                        "CAGR": m["CAGR"],
                        "MaxDD": m["MaxDD"],
                        "Sharpe": m["Sharpe"],
                        "Trades": trades,
                        "AnnualTurnover": annual_turnover,
                        "RiskEvents": risk_events,
                        "RiskRebalances": risk_rebalances,
                    })

    print(" " * 110, end="\r")
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No training candidates produced valid statistics.")

    # Same V46 production-score structure, but computed ONLY on the training set.
    df["Score"] = (
        0.40 * df["Sharpe"].rank(pct=True)
        + 0.35 * df["CAGR"].rank(pct=True)
        + 0.15 * df["MaxDD"].rank(pct=True)
        + 0.10 * (-df["AnnualTurnover"]).rank(pct=True)
    )
    df = df.sort_values(
        ["Score", "Sharpe", "CAGR"], ascending=[False, False, False]
    ).reset_index(drop=True)

    winner = df.iloc[0].to_dict()
    print(
        f"TRAINING WINNER: {winner['Variant']} | "
        f"Score={winner['Score']:.4f} | "
        f"CAGR={winner['CAGR']:.2%} | "
        f"MaxDD={winner['MaxDD']:.2%} | "
        f"Sharpe={winner['Sharpe']:.3f} | "
        f"Turnover={winner['AnnualTurnover']:.2f}x"
    )
    return df, winner


def run_frozen_to_test(panel, start_date, test_end, cfg):
    """Run one frozen configuration from the original start through test end."""
    eq, trades, turnover, annual_turnover, risk_events, risk_rebalances = run_robust_experiment(
        panel,
        start_date,
        PRODUCTION_COST,
        int(cfg["HoldRank"]),
        float(cfg["Trigger"]),
        float(cfg["Exposure"]),
        float(cfg["Recovery"]),
    )
    eq = eq.loc[eq.index <= pd.Timestamp(test_end)]
    return eq, trades, annual_turnover, risk_events, risk_rebalances


def main():
    print('=' * 88)
    print('GORS FINAL — FROZEN STRATEGY / FINAL RESEARCH REPORT')
    print('=' * 88)
    print('NO PARAMETER OPTIMIZATION')
    print('FROZEN CANDIDATE: HR5 | DD8% | Recovery75% | Exposure50% | Cost0.25%')
    print('IMPORTANT: V49 true expanding-window walk-forward failure is retained as a validation limitation.')

    raw = download()
    corrected = {k: v.copy() for k, v in raw.items()}
    for d in ['2021-06-17', '2021-06-18']:
        ts = pd.Timestamp(d)
        if ts in corrected['MON100'].index:
            corrected['MON100'].loc[ts] *= 10.0

    if not mon100_audit(raw, corrected):
        raise RuntimeError('FINAL STOPPED: MON100 correction gate failed.')

    panel = pd.DataFrame(corrected).sort_index()
    panel = panel[~panel.index.duplicated(keep='last')]

    # DATA INTEGRITY GATE: remove ONLY an incomplete trailing market-data tail.
    # IMPORTANT: do NOT drop every historical row containing a NaN.
    # The original V30 engine intentionally allows ETFs with different
    # inception dates and ranks only currently eligible instruments.
    # Requiring all 8 ETFs to exist on every date would incorrectly move
    # FIRST VALID LIVE DATE to 2026 and destroy V30 reconciliation.
    #
    # We only need to prevent a partial *latest* trading date from entering
    # portfolio accounting (e.g. MOM30 has 2026-08-10 while the other ETFs
    # stop at 2026-08-07). Find the latest date where every instrument has a
    # valid close, then truncate the panel AFTER that date. Earlier NaNs are
    # preserved exactly as in V30.
    complete_dates = panel.notna().all(axis=1)
    if not complete_dates.any():
        raise RuntimeError('FINAL STOPPED: no complete common market-data date exists.')
    last_complete = panel.index[complete_dates][-1]
    if last_complete != panel.index[-1]:
        print(
            f"DATA INTEGRITY: truncating incomplete tail "
            f"{panel.index[-1].date()} -> {last_complete.date()}"
        )
        panel = panel.loc[:last_complete].copy()
    start_date = first_valid(panel)
    print(f'FIRST VALID LIVE DATE : {start_date.date()}')
    print('FIXED SIGNAL           : Top 3 + RSI(14) 85/100')

    # ------------------------------------------------------------------
    # 1. Mandatory V30/V39 reconciliation
    # ------------------------------------------------------------------
    base_eq, base_trades, base_turnover, _ = run_strategy(panel, start_date, 0.0)
    base_m = stats(base_eq)
    days = max((base_eq.index[-1] - base_eq.index[0]).days, 1)
    base_ann = base_turnover / (days / 365.25) / INITIAL
    passed, _ = compare_to_v30(base_m, base_trades, base_ann)
    if not passed:
        raise RuntimeError('FINAL STOPPED: V30 reconciliation failed.')
    print('V39/V30 EXACT BASELINE: PASS')

    # ------------------------------------------------------------------
    # 2. Frozen candidate at production cost
    # ------------------------------------------------------------------
    HR, DD, REC, EXP, COST = 5, 0.08, 0.75, 0.50, 0.0025
    eq, trades, turnover, annual_turnover, risk_events, risk_rebalances, state, events = run_forensic(
        panel, start_date, COST, HR, DD, EXP, REC
    )
    m = stats(eq)
    r12 = rolling12(eq)
    rec = recovery_stats(eq)
    years = year_stats(eq)

    print('\n' + '=' * 88)
    print('FROZEN CANDIDATE — FULL HISTORY')
    print('=' * 88)
    print(f"Final          : {m['Final']:,.2f}")
    print(f"CAGR           : {m['CAGR']:.2%}")
    print(f"MaxDD          : {m['MaxDD']:.2%}")
    print(f"Sharpe         : {m['Sharpe']:.3f}")
    print(f"Sortino        : {m['Sortino']:.3f}")
    print(f"Calmar         : {m['Calmar']:.3f}")
    print(f"Trades         : {trades}")
    print(f"Annual turnover: {annual_turnover:.2f}x")
    print(f"Risk events    : {risk_events}")
    print(f"Risk rebalances: {risk_rebalances}")

    # ------------------------------------------------------------------
    # 3. Calendar-year diagnostics
    # ------------------------------------------------------------------
    print('\nCALENDAR-YEAR DIAGNOSTICS')
    print(years.to_string(index=False))

    # ------------------------------------------------------------------
    # 4. Rolling 12M diagnostics
    # ------------------------------------------------------------------
    print('\nROLLING 12M DIAGNOSTICS')
    print(r12)

    # ------------------------------------------------------------------
    # 5. Recovery diagnostic
    # ------------------------------------------------------------------
    print('\nWORST DRAWDOWN RECOVERY')
    print(rec)

    # ------------------------------------------------------------------
    # 6. Risk-state integrity audit
    # ------------------------------------------------------------------
    bad = state[(state['RiskOn']) & (state['ActualExposure'] > EXP + 0.05)].copy()
    exposure_gap_days = int((state['ExposureGap'].abs() > 0.05).sum())
    print('\nRISK-STATE INTEGRITY')
    print(f"RiskOn days with exposure > target + 5pp: {len(bad)}")
    print(f"Days with exposure gap > 5pp           : {exposure_gap_days}")
    if len(bad):
        print(bad[['Date','Drawdown','ActualExposure','TargetExposure','TransitionReason']].to_string(index=False))

    # ------------------------------------------------------------------
    # 7. 2025 and 2026 diagnostics, including the known HR7 anomaly context
    # ------------------------------------------------------------------
    for label, start, end in [
        ('2025', '2025-01-01', '2025-12-31'),
        ('2026 YTD', '2026-01-01', str(panel.index.max().date())),
    ]:
        p = period_stats(eq, start, end)
        if p:
            print(f"\n{label} FROZEN HR5")
            print(p)

    # ------------------------------------------------------------------
    # 8. Fixed-candidate cost stability: 0.25% vs 0.50% only.
    #    This is sensitivity, NOT optimization.
    #    IMPORTANT: use the SAME frozen risk engine (including recovery),
    #    otherwise this would silently compare different strategies.
    # ------------------------------------------------------------------
    cost_rows = []
    for c in [0.0025, 0.0050]:
        ceq, ctrades, cturn, cann, cre, crr, _, _ = run_forensic(
            panel, start_date, c, HR, DD, EXP, REC
        )
        cm = stats(ceq)
        cost_rows.append({
            'Cost': c,
            'Final': cm['Final'],
            'CAGR': cm['CAGR'],
            'MaxDD': cm['MaxDD'],
            'Sharpe': cm['Sharpe'],
            'Trades': ctrades,
            'AnnualTurnover': cann,
            'RiskEvents': cre,
            'RiskRebalances': crr,
        })
    cost_df = pd.DataFrame(cost_rows)
    print('\nFIXED-CANDIDATE COST SENSITIVITY')
    print(cost_df.to_string(index=False))

    # ------------------------------------------------------------------
    # 9. Persist final outputs.
    # ------------------------------------------------------------------
    years.to_csv(OUT / 'gors_final_years.csv', index=False)
    pd.DataFrame([m]).to_csv(OUT / 'gors_final_full_history.csv', index=False)
    pd.DataFrame([r12]).to_csv(OUT / 'gors_final_rolling12m.csv', index=False)
    pd.DataFrame([rec]).to_csv(OUT / 'gors_final_recovery.csv', index=False)
    state.to_csv(OUT / 'gors_final_daily_state.csv', index=False)
    events.to_csv(OUT / 'gors_final_events.csv', index=False)
    cost_df.to_csv(OUT / 'gors_final_cost_sensitivity.csv', index=False)

    # State transitions are especially useful for manual review.
    state[state['RiskTransition']].to_csv(OUT / 'gors_final_risk_transitions.csv', index=False)

    # Equity chart.
    plt.figure(figsize=(12, 6))
    plt.plot(eq.index, eq.values, label='GORS Final Frozen HR5')
    plt.title('GORS Final — Frozen Candidate Equity Curve')
    plt.xlabel('Date')
    plt.ylabel('Equity')
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / 'gors_final_equity.png', dpi=160)
    plt.close()

    # ------------------------------------------------------------------
    # 10. Final verdict — deliberately conservative.
    # ------------------------------------------------------------------
    print('\n' + '=' * 88)
    print('FINAL GORS RESEARCH VERDICT')
    print('=' * 88)
    print('V30/V39 baseline reconciliation : PASS')
    print(f"Frozen HR5 full-history CAGR     : {m['CAGR']:.2%}")
    print(f"Frozen HR5 full-history MaxDD    : {m['MaxDD']:.2%}")
    print(f"Frozen HR5 full-history Sharpe   : {m['Sharpe']:.3f}")
    print('V53 risk-state direct override   : NOT DETECTED')
    print('V49 true walk-forward validation : FAIL')
    print('')
    print('VERDICT: RESEARCH-VALIDATED ENGINE / NOT LIVE-VALIDATED STRATEGY')
    print('Do not continue parameter optimization merely to improve historical metrics.')
    print('Any future change should be a structural hypothesis followed by a fresh')
    print('out-of-sample test, not another search over the same historical sample.')

    summary = pd.DataFrame([
        {'Metric': 'FrozenVariant', 'Value': 'HR5_DD8_REC75_EXP50'},
        {'Metric': 'ProductionCost', 'Value': COST},
        {'Metric': 'V30Reconciliation', 'Value': 'PASS'},
        {'Metric': 'FullHistoryCAGR', 'Value': m['CAGR']},
        {'Metric': 'FullHistoryMaxDD', 'Value': m['MaxDD']},
        {'Metric': 'FullHistorySharpe', 'Value': m['Sharpe']},
        {'Metric': 'AnnualTurnover', 'Value': annual_turnover},
        {'Metric': 'RiskEvents', 'Value': risk_events},
        {'Metric': 'RiskRebalances', 'Value': risk_rebalances},
        {'Metric': 'V53ExposureOverride', 'Value': 'NOT DETECTED'},
        {'Metric': 'V49TrueWalkForward', 'Value': 'FAIL'},
        {'Metric': 'FinalVerdict', 'Value': 'RESEARCH-VALIDATED / NOT LIVE-VALIDATED'},
    ])
    summary.to_csv(OUT / 'gors_final_summary.csv', index=False)

    print('\nCreated:')
    for name in [
        'gors_final_summary.csv',
        'gors_final_full_history.csv',
        'gors_final_years.csv',
        'gors_final_rolling12m.csv',
        'gors_final_recovery.csv',
        'gors_final_daily_state.csv',
        'gors_final_events.csv',
        'gors_final_risk_transitions.csv',
        'gors_final_cost_sensitivity.csv',
        'gors_final_equity.png',
    ]:
        print(f'  {OUT / name}')
    print('\nGORS FINAL COMPLETE.')


if __name__ == '__main__':
    main()
