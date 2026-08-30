from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

START = "2020-01-01"
INITIAL = 100_000.0
LOOKBACK = 126
TOP_N = 3
RSI_EXIT = 85
RSI_FULL_EXIT = 100
HOLD_RANK = 5
DD_TRIGGER = 0.08
RECOVERY_FRACTION = 0.75
RISK_OFF_EXPOSURE = 0.50
PRODUCTION_COST = 0.0025
TICKERS = {"MOM30":"MOM30IETF.NS","MOM50":"MOMENTUM50.NS","MIDMOM":"MOMIDMTM.NS","SMALLMOM":"SMALLCAP.NS","MON100":"MON100.NS","NIFTY":"NIFTYBEES.NS","GOLD":"GOLDBEES.NS","SILVER":"SILVERBEES.NS"}
REFERENCE_METRICS = {"Final":350_874.56,"CAGR":0.2296,"MaxDD":-0.1857,"Sharpe":1.323,"Trades":52,"AnnualTurnover":2.85}

@dataclass(frozen=True)
class ManualAction:
    etf: str
    action: str
    quantity: int | None
    approximate_value: float | None
    reason: str
    signal_date: str

def get_series(ticker: str) -> pd.Series:
    if yf is None: raise RuntimeError("Install yfinance: python3 -m pip install yfinance")
    df = yf.download(ticker, start=START, auto_adjust=False, progress=False, actions=False)
    if df.empty: raise RuntimeError(f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): s = df["Close"].iloc[:,0] if "Close" in df.columns.get_level_values(0) else df.iloc[:,0]
    else: s = df["Close"]
    s = pd.to_numeric(s, errors="coerce").dropna(); s.index = pd.to_datetime(s.index).tz_localize(None)
    return s[~s.index.duplicated(keep="last")].sort_index()

def download_market_data(): return {n:get_series(t) for n,t in TICKERS.items()}
def apply_mon100_correction(raw_data):
    corrected={k:v.copy() for k,v in raw_data.items()}
    for d in ["2021-06-17","2021-06-18"]:
        ts=pd.Timestamp(d)
        if "MON100" in corrected and ts in corrected["MON100"].index: corrected["MON100"].loc[ts]*=10.0
    return corrected

def mon100_audit(raw_data, corrected_data):
    raw,corr=raw_data["MON100"],corrected_data["MON100"]; checks=[]
    for d in ["2021-06-17","2021-06-18"]:
        ts=pd.Timestamp(d); checks.append(ts in raw.index and ts in corr.index and abs(corr.loc[ts]/raw.loc[ts]-10)<1e-9)
    ts=pd.Timestamp("2021-06-21"); checks.append(ts in raw.index and ts in corr.index and abs(corr.loc[ts]-raw.loc[ts])<1e-9)
    win=corr.loc[(corr.index>="2021-06-14")&(corr.index<="2021-06-25")]; daily=win.pct_change().dropna(); max_abs=float(daily.abs().max()) if len(daily) else np.nan
    checks.append(bool(np.isfinite(max_abs) and max_abs<.20)); return all(checks)

def build_panel(corrected_data):
    panel=pd.DataFrame(corrected_data).sort_index(); panel=panel[~panel.index.duplicated(keep="last")]
    complete=panel.notna().all(axis=1)
    if not complete.any(): raise RuntimeError("FINAL STOPPED: no complete common market-data date exists.")
    last_complete=panel.index[complete][-1]
    return panel.loc[:last_complete].copy() if last_complete != panel.index[-1] else panel

def load_market_data():
    raw=download_market_data(); corrected=apply_mon100_correction(raw)
    if not mon100_audit(raw,corrected): raise RuntimeError("FINAL STOPPED: MON100 correction gate failed.")
    return build_panel(corrected)

def rsi(s, period=14):
    d=s.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/period,adjust=False,min_periods=period).mean(); al=l.ewm(alpha=1/period,adjust=False,min_periods=period).mean()
    out=100-100/(1+ag/al.replace(0,np.nan)); return out.where(~((al==0)&(ag>0)),100.0)

def calculate_rsi_exit_actions(panel, holdings, cutoff):
    actions=[]
    for etf, quantity in holdings.items():
        if quantity <= 0 or etf not in panel.columns: continue
        rv = rsi(panel[etf]).loc[cutoff]
        if pd.isna(rv): continue
        if rv >= RSI_FULL_EXIT:
            actions.append({"ETF":etf,"Action":"SELL_ALL","Fraction":1.0,"Quantity":int(quantity),"RSI":float(rv),"Reason":"RSI >= 100"})
        elif rv >= RSI_EXIT:
            actions.append({"ETF":etf,"Action":"SELL_HALF","Fraction":0.5,"Quantity":int(np.ceil(quantity*0.5)),"RSI":float(rv),"Reason":"RSI >= 85"})
    return actions

def risk_control_transition(drawdown, risk_on, trigger=DD_TRIGGER, recovery_frac=RECOVERY_FRACTION):
    """Apply the frozen DD risk control: 8% trigger, 75% recovery, 50% exposure."""
    if not risk_on and drawdown <= -trigger:
        return True, "RISK OFF"
    recovery_drawdown = -trigger * (1.0 - recovery_frac)
    if risk_on and drawdown >= recovery_drawdown:
        return False, "RISK ON"
    return risk_on, None

def monthly_dates(idx):
    idx=pd.DatetimeIndex(idx); s=pd.Series(idx,index=idx); return list(s.groupby(s.index.to_period("M")).last())

def eligible(panel,date):
    loc=panel.index.get_loc(date)
    if loc<LOOKBACK:return {}
    old=panel.index[loc-LOOKBACK]; out={}
    for c in panel.columns:
        now,prev=panel.at[date,c],panel.at[old,c]
        if pd.notna(now) and pd.notna(prev) and now>0 and prev>0: out[c]=float(now/prev-1)
    return out

def first_valid(panel):
    for d in monthly_dates(panel.index):
        if len(eligible(panel,d))>=TOP_N:return d
    raise RuntimeError("No date has three eligible ETFs.")

def stats(eq):
    eq=pd.Series(eq).dropna(); yrs=max((eq.index[-1]-eq.index[0]).days/365.25,1/365.25); final=float(eq.iloc[-1]); ret=final/INITIAL-1; cagr=(final/INITIAL)**(1/yrs)-1
    dr=eq.pct_change().replace([np.inf,-np.inf],np.nan).dropna(); peak=eq.cummax(); dd=float((eq/peak-1).min()); sh=np.nan if dr.std(ddof=1)==0 else np.sqrt(252)*dr.mean()/dr.std(ddof=1)
    neg=dr[dr<0]; so=np.nan if len(neg)<2 or neg.std(ddof=1)==0 else np.sqrt(252)*dr.mean()/neg.std(ddof=1)
    return {"Final":final,"Return":ret,"CAGR":cagr,"MaxDD":dd,"Sharpe":sh,"Sortino":so,"Calmar":cagr/abs(dd) if dd<0 else np.nan}

def run_forensic(panel,start_date,cost=PRODUCTION_COST,hold_rank=HOLD_RANK,trigger=DD_TRIGGER,reduced_exposure=RISK_OFF_EXPOSURE,recovery_frac=RECOVERY_FRACTION):
    dates=panel.index; rebal=set(monthly_dates(dates)); cash=INITIAL; holdings={}; trades=0; turnover=0.; risk_on=False; eq_rows=[]; state_rows=[]; event_rows=[]; peak=INITIAL
    def mv(p): return sum(q*float(p[t]) for t,q in holdings.items() if pd.notna(p.get(t)))
    def enforce(p,desired,reason):
        nonlocal cash,turnover,trades
        before=mv(p); eq=cash+before; target=eq*desired
        if before>target+1e-10:
            sell=before-target
            for t in list(holdings):
                if sell<=1e-10:break
                px=p.get(t)
                if pd.isna(px) or px<=0:continue
                q=min(holdings[t],int(np.ceil(sell/px))); value=q*float(px)
                if q<=0:continue
                holdings[t]-=q; cash+=value*(1-cost); turnover+=value; trades+=1; sell-=value
                if holdings[t]<=0:del holdings[t]
        elif before<target-1e-10 and cash>0:
            buy=target-before; ranked=sorted(eligible(panel,p.name).items(),key=lambda z:z[1],reverse=True)[:TOP_N]
            if not ranked:return
            each=buy/len(ranked)
            for t,_ in ranked:
                px=float(p[t]); q=int(each/px)
                if q<=0:continue
                value=q*px
                if value*(1+cost)>cash:q=int(cash/(px*(1+cost))); value=q*px
                if q<=0:continue
                holdings[t]=holdings.get(t,0)+q; cash-=value*(1+cost); turnover+=value; trades+=1
    for d in dates:
        p=panel.loc[d]; eq=cash+mv(p); peak=max(peak,eq); dd=eq/peak-1
        risk_on, event = risk_control_transition(dd, risk_on, trigger, recovery_frac)
        if event: event_rows.append({"Date":d,"Event":event})
        desired=reduced_exposure if risk_on else 1.0
        if d in rebal and d>=start_date:enforce(p,desired,"monthly")
        eq=cash+mv(p); peak=max(peak,eq); dd=eq/peak-1
        eq_rows.append((d,eq)); state_rows.append({"RiskOn":risk_on,"TargetExposure":desired,"ActualExposure":mv(p)/eq if eq else 0.,"Drawdown":dd,"Equity":eq,"Cash":cash,"MarketValue":mv(p),"Trades":trades})
    equity=pd.Series(dict(eq_rows)); st=pd.DataFrame(state_rows,index=dates); return {"equity":equity,"state":st,"events":pd.DataFrame(event_rows),"trades":trades,"annual_turnover":turnover/max((dates[-1]-dates[0]).days/365.25,1/365.25),"metrics":stats(equity)}

def latest_completed_common_date(panel,as_of=None):
    as_of=pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(); idx=panel.index[panel.index<pd.Timestamp(as_of).normalize()]; return idx[-1] if len(idx) else None

def run_frozen_backtest(panel,as_of=None):
    return run_forensic(panel,first_valid(panel))

def monthly_holdrank_selection(panel,cutoff,hold_rank=HOLD_RANK,top_n=TOP_N):
    dates=[d for d in monthly_dates(panel.index) if d<=cutoff and len(eligible(panel,d))>=top_n]
    if not dates:raise RuntimeError("No monthly rebalance date has enough eligible ETFs.")
    holdings=[]; history=[]
    for d in dates:
        scores=eligible(panel,d); ranked=sorted(scores.items(),key=lambda z:z[1],reverse=True); ranks={n:i+1 for i,(n,_) in enumerate(ranked)}; previous=list(holdings); selected=[n for n in previous if ranks.get(n,10**9)<=hold_rank]
        for n,_ in ranked:
            if len(selected)>=top_n:break
            if n not in selected:selected.append(n)
        for n in previous:
            if n not in selected:history.append({"Date":d,"ETF":n,"Rank":ranks.get(n),"Action":"REPLACE"})
        for n in selected:history.append({"Date":d,"ETF":n,"Rank":ranks.get(n),"Action":"KEEP" if n in previous else "NEW"})
        holdings=selected
    final_date=dates[-1]; scores=eligible(panel,final_date); ranked=sorted(scores.items(),key=lambda z:z[1],reverse=True); return holdings,final_date,scores,{n:i+1 for i,(n,_) in enumerate(ranked)},history

def calculate_gors_signal(panel,as_of=None):
    cutoff=latest_completed_common_date(panel,as_of)
    if cutoff is None:raise RuntimeError("FINAL STOPPED: no completed common market-data date exists.")
    result=run_frozen_backtest(panel,as_of=cutoff); last=result["state"].iloc[-1]; prices={c:float(panel.loc[cutoff,c]) for c in panel.columns}
    target_ranked,ranking_date,scores,rank_map,history=monthly_holdrank_selection(panel,cutoff); holdings={x:1 for x in target_ranked}; rsi_exits=calculate_rsi_exit_actions(panel,holdings,cutoff)
    action_by_etf={x["ETF"]:x["Action"] for x in history if x["Date"]==ranking_date}
    top3_table=[{"Rank":rank_map.get(n),"ETF":n,"Signal/Score":scores.get(n),"RSI":float(rsi(panel[n]).loc[cutoff]),"Price":prices[n],"Status":action_by_etf.get(n,"KEEP")} for n in target_ranked]
    return {"signal_date":cutoff.date().isoformat(),"ranking_date":ranking_date.date().isoformat(),"risk_state":"RISK OFF" if bool(last["RiskOn"]) else "RISK ON","target_exposure_pct":float(last["TargetExposure"]),"actual_exposure_pct":float(last["ActualExposure"]),"current_drawdown":float(last["Drawdown"]),"equity":float(last["Equity"]),"cash":float(last["Cash"]),"market_value":float(last["MarketValue"]),"holdings":holdings,"top3":target_ranked,"top3_table":top3_table,"prices":prices,"rsi_exit_actions":rsi_exits,"state":result["state"],"events":result["events"],"metrics":result["metrics"],"trades":result["trades"],"annual_turnover":result["annual_turnover"],"selection_history":history}

def build_holdings_table(kite_rows,prices):
    rows=[]
    for row in kite_rows:
        e=row["etf"];q=float(row.get("quantity") or 0);p=float(prices.get(e) or row.get("last_price") or 0);rows.append({"ETF":e,"Quantity":q,"Price":p,"Portfolio Value":q*p})
    df=pd.DataFrame(rows)
    if df.empty:return pd.DataFrame(columns=["ETF","Quantity","Price","Portfolio Value","Weight"])
    total=float(df["Portfolio Value"].sum());df["Weight"]=df["Portfolio Value"]/total if total else 0.;return df

def build_manual_actions(signal,kite_rows,cash):
    target=signal.get("holdings",{});prices=signal["prices"];current={r["etf"]:float(r.get("quantity") or 0) for r in kite_rows};actions=[];exit_etfs=set()
    for x in signal.get("rsi_exit_actions",[]):
        if current.get(x["ETF"],0)>0:
            q=min(int(current[x["ETF"]]),x["Quantity"]);actions.append(ManualAction(x["ETF"],"SELL",q,q*prices[x["ETF"]],x["Reason"],signal["signal_date"]));exit_etfs.add(x["ETF"])
    for etf,target_qty in target.items():
        if etf in exit_etfs:continue
        price=float(prices.get(etf) or 0);diff=float(target_qty)-current.get(etf,0)
        if price>0 and abs(diff)>=1:actions.append(ManualAction(etf,"BUY" if diff>0 else "SELL",int(abs(diff)),int(abs(diff))*price,"Match monthly GORS target holding.",signal["signal_date"]))
    for etf,qty in current.items():
        if etf not in target and qty>=1:
            price=float(prices.get(etf) or 0);actions.append(ManualAction(etf,"SELL",int(qty),int(qty)*price if price else None,"ETF is no longer in target holdings.",signal["signal_date"]))
    return actions
