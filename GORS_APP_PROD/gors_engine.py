from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

START="2020-01-01"; INITIAL=100_000.0; LOOKBACK=126; TOP_N=3; RSI_EXIT=85; RSI_FULL_EXIT=100; HOLD_RANK=5; DD_TRIGGER=.08; RECOVERY_FRACTION=.75; RISK_OFF_EXPOSURE=.50; PRODUCTION_COST=.0025
TICKERS={"MOM30":"MOM30IETF.NS","MOM50":"MOMENTUM50.NS","MIDMOM":"MOMIDMTM.NS","SMALLMOM":"SMALLCAP.NS","MON100":"MON100.NS","NIFTY":"NIFTYBEES.NS","GOLD":"GOLDBEES.NS","SILVER":"SILVERBEES.NS"}

@dataclass(frozen=True)
class ManualAction:
    etf:str; action:str; quantity:int|None; approximate_value:float|None; reason:str; signal_date:str

def rsi(s,period=14):
    d=s.diff(); g=d.clip(lower=0); l=-d.clip(upper=0); ag=g.ewm(alpha=1/period,adjust=False,min_periods=period).mean(); al=l.ewm(alpha=1/period,adjust=False,min_periods=period).mean(); out=100-100/(1+ag/al.replace(0,np.nan)); return out.where(~((al==0)&(ag>0)),100.)

def monthly_dates(idx):
    idx=pd.DatetimeIndex(idx); return list(pd.Series(idx,index=idx).groupby(idx.to_period("M")).last())

def eligible(panel,date):
    loc=panel.index.get_loc(date)
    if loc<LOOKBACK:return {}
    old=panel.index[loc-LOOKBACK]; return {c:float(panel.at[date,c]/panel.at[old,c]-1) for c in panel.columns if pd.notna(panel.at[date,c]) and pd.notna(panel.at[old,c]) and panel.at[date,c]>0 and panel.at[old,c]>0}

def monthly_holdrank_selection(panel,cutoff,hold_rank=HOLD_RANK,top_n=TOP_N):
    dates=[d for d in monthly_dates(panel.index) if d<=cutoff and len(eligible(panel,d))>=top_n]
    if not dates: raise RuntimeError("No monthly rebalance date has enough eligible ETFs.")
    holdings=[]; history=[]
    for d in dates:
        scores=eligible(panel,d); ranked=sorted(scores.items(),key=lambda z:z[1],reverse=True); ranks={n:i+1 for i,(n,_) in enumerate(ranked)}; previous=list(holdings)
        selected=[n for n in previous if ranks.get(n,10**9)<=hold_rank]
        for n,_ in ranked:
            if len(selected)>=top_n: break
            if n not in selected:selected.append(n)
        for n in previous:
            if n not in selected: history.append({"Date":d,"ETF":n,"Rank":ranks.get(n),"Action":"REPLACE"})
        for n in selected: history.append({"Date":d,"ETF":n,"Rank":ranks.get(n),"Action":"KEEP" if n in previous else "NEW"})
        holdings=selected
    d=dates[-1]; scores=eligible(panel,d); ranked=sorted(scores.items(),key=lambda z:z[1],reverse=True); return holdings,d,scores,{n:i+1 for i,(n,_) in enumerate(ranked)},history

def latest_completed_common_date(panel,as_of=None):
    a=pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now(); idx=panel.index[panel.index<a.normalize()]; return idx[-1] if len(idx) else None

def calculate_rsi_exit_actions(panel,holdings,cutoff):
    """Daily RSI exit rules: >=85 sells 50%; >=100 exits the remainder."""
    out=[]
    for etf,quantity in holdings.items():
        if quantity<=0 or etf not in panel.columns: continue
        value=float(panel.loc[cutoff,etf]); rv=rsi(panel[etf]).loc[cutoff]
        if pd.isna(rv): continue
        if rv>=RSI_FULL_EXIT: out.append({"ETF":etf,"Action":"SELL_ALL","Fraction":1.0,"Quantity":int(quantity),"RSI":float(rv),"Reason":"RSI >= 100"})
        elif rv>=RSI_EXIT: out.append({"ETF":etf,"Action":"SELL_HALF","Fraction":0.5,"Quantity":int(np.ceil(quantity*0.5)),"RSI":float(rv),"Reason":"RSI >= 85"})
    return out

def calculate_gors_signal(panel,as_of=None):
    cutoff=latest_completed_common_date(panel,as_of)
    if cutoff is None: raise RuntimeError("FINAL STOPPED: no completed common market-data date exists.")
    target_ranked,ranking_date,scores,rank_map,history=monthly_holdrank_selection(panel,cutoff); holdings={x:1 for x in target_ranked}; prices={c:float(panel.loc[cutoff,c]) for c in panel.columns}; exits=calculate_rsi_exit_actions(panel,holdings,cutoff)
    # RSI exits are daily position actions; monthly Top-3 selection itself remains governed by ranking_date/HoldRank.
    return {"signal_date":cutoff.date().isoformat(),"ranking_date":ranking_date.date().isoformat(),"top3":target_ranked,"holdings":holdings,"prices":prices,"rsi_exit_actions":exits,"top3_table":[{"Rank":rank_map.get(n),"ETF":n,"Signal/Score":scores.get(n),"RSI":float(rsi(panel[n]).loc[cutoff]),"Price":prices[n]} for n in target_ranked],"selection_history":history}

def build_holdings_table(kite_rows,prices):
    rows=[]
    for row in kite_rows:
        e=row["etf"]; q=float(row.get("quantity") or 0); p=float(prices.get(e) or row.get("last_price") or 0); rows.append({"ETF":e,"Quantity":q,"Price":p,"Portfolio Value":q*p})
    df=pd.DataFrame(rows)
    if df.empty:return pd.DataFrame(columns=["ETF","Quantity","Price","Portfolio Value","Weight"])
    total=float(df["Portfolio Value"].sum()); df["Weight"]=df["Portfolio Value"]/total if total else 0.; return df

def build_manual_actions(signal,kite_rows,cash):
    target=signal.get("holdings",{}); prices=signal["prices"]; current={r["etf"]:float(r.get("quantity") or 0) for r in kite_rows}; actions=[]
    for x in signal.get("rsi_exit_actions",[]):
        if current.get(x["ETF"],0)>0: actions.append(ManualAction(x["ETF"],"SELL",x["Quantity"],x["Quantity"]*prices[x["ETF"]],x["Reason"],signal["signal_date"]))
    for etf,target_qty in target.items():
        if any(x["ETF"]==etf for x in signal.get("rsi_exit_actions",[])): continue
        price=float(prices.get(etf) or 0); diff=float(target_qty)-current.get(etf,0)
        if price>0 and abs(diff)>=1: actions.append(ManualAction(etf,"BUY" if diff>0 else "SELL",int(abs(diff)),int(abs(diff))*price,"Match monthly GORS target holding.",signal["signal_date"]))
    for etf,qty in current.items():
        if etf not in target and qty>=1:
            price=float(prices.get(etf) or 0); actions.append(ManualAction(etf,"SELL",int(qty),int(qty)*price if price else None,"ETF is no longer in target holdings.",signal["signal_date"]))
    return actions
