import hashlib
import io
from datetime import date, datetime

import pandas as pd
import streamlit as st

from gors_db import *
from auth import logout_button, require_google_login
from gors_decision import get_current_gors_decision

# ============================================================
# GORS_APP_PROD — DAILY TRADING COCKPIT
# Strategy/accounting logic is intentionally unchanged from V14.
# This release is a presentation/workflow redesign only.
# ============================================================
st.set_page_config(page_title="GORS_APP_PROD", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
require_google_login()
logout_button()
init_db()
migration_message = migrate_v12_if_needed()
# Protect the permanent DB once per day before any new UI edits/imports.
startup_backup = backup_database_if_needed()

INITIAL_CAPITAL = 300000.0
TOP_ETFS = ["MON100", "SMALLCAP", "GOLDBEES"]
RISK_OFF_EXPOSURE = 0.50
STRATEGY_VERSION = "FROZEN"
APP_VERSION = "PROD"

# -----------------------------
# Styling: compact Pine-inspired cockpit, but cleaner for desktop.
# -----------------------------
st.markdown(
    """<style>
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] {background:#0b0f17;}
.stApp {background:#0b0f17;color:#f8fafc;}
.block-container {padding-top:1.0rem; padding-bottom:2.5rem; padding-left:2.5rem; padding-right:2.5rem; max-width:none; width:100%;}
section[data-testid="stSidebar"] {background:#111827;border-right:1px solid #334155; min-width:285px;}
section[data-testid="stSidebar"] * {font-size:.95rem;color:#e5e7eb;}
.eyebrow {font-size:.82rem;font-weight:850;letter-spacing:.08em;color:#94a3b8;text-transform:uppercase;}
.hero {border:1px solid #334155;border-radius:18px;padding:24px 28px;background:#111827;margin-bottom:18px;box-shadow:0 8px 30px rgba(0,0,0,.22);}
.hero-title {font-size:2.15rem;font-weight:900;line-height:1.15;margin:0;color:#f8fafc;}
.hero-sub {color:#cbd5e1;margin-top:8px;font-size:1.03rem;}
.pill {display:inline-block;border-radius:999px;padding:8px 14px;font-weight:850;font-size:.92rem;margin-right:7px;margin-top:12px;}
.pill-green {background:#063b2a;color:#6ee7a7;border:1px solid #16835b;}
.pill-red {background:#451a1a;color:#fca5a5;border:1px solid #b91c1c;}
.pill-amber {background:#422006;color:#fcd34d;border:1px solid #b45309;}
.pill-gray {background:#1e293b;color:#e2e8f0;border:1px solid #475569;}
.card {border:1px solid #334155;border-radius:16px;padding:22px;background:#151c29;height:100%;box-shadow:0 4px 16px rgba(0,0,0,.16);}
.card-title {font-size:.9rem;font-weight:850;color:#94a3b8;text-transform:uppercase;letter-spacing:.04em;margin-bottom:9px;}
.big {font-size:2.05rem;font-weight:900;line-height:1.15;color:#f8fafc;}
.sub {font-size:.92rem;color:#cbd5e1;margin-top:5px;}
.section-title {font-size:1.55rem;font-weight:900;margin:28px 0 8px;color:#f8fafc;}
.section-sub {font-size:1rem;color:#94a3b8;margin-top:-3px;margin-bottom:14px;}
.buy {color:#6ee7a7;font-weight:900;}.sell {color:#fca5a5;font-weight:900;}.hold {color:#cbd5e1;font-weight:900;}
.kite-box {background:#062e24;border:1px solid #16835b;color:#d1fae5;border-radius:14px;padding:16px 18px;font-size:1rem;}
.ticket {border:1px solid #16835b;border-left:7px solid #22c55e;background:#062e24;color:#ecfdf5;border-radius:10px;padding:15px 18px;margin:9px 0;font-size:1.08rem;font-weight:800;}
.ticket-sell {border-color:#b91c1c;border-left-color:#ef4444;background:#3a1717;color:#fee2e2;}
.ticket-hold {border-color:#475569;border-left-color:#94a3b8;background:#172033;color:#e2e8f0;}
.step {border:1px solid #334155;border-radius:14px;padding:16px;background:#151c29;height:100%;}
.step-num {display:inline-flex;width:32px;height:32px;border-radius:50%;align-items:center;justify-content:center;background:#f8fafc;color:#0f172a;font-weight:900;margin-right:8px;}
.step-title {font-size:1.02rem;font-weight:850;color:#f8fafc;}
.step-text {font-size:.9rem;color:#cbd5e1;margin-top:8px;line-height:1.45;}
.big-action {font-size:1.45rem;font-weight:900;line-height:1.2;}
.footer-note {color:#64748b;font-size:.8rem;border-top:1px solid #334155;padding-top:14px;margin-top:24px;}
[data-testid="stMetric"] {background:#151c29;border:1px solid #334155;padding:16px 18px;border-radius:14px;min-height:96px;}
[data-testid="stMetricLabel"] {color:#94a3b8 !important;font-size:.88rem !important;font-weight:750 !important;}
[data-testid="stMetricValue"] {color:#f8fafc !important;font-weight:900 !important;}
[data-testid="stMetricDelta"] {font-weight:800 !important;}
[data-testid="stDataFrame"] {border:1px solid #334155;border-radius:10px;overflow:hidden;}
[data-testid="stFileUploader"] {background:#111827;border:1px dashed #475569;border-radius:14px;padding:8px;}
button[kind="primary"] {font-size:1rem !important;font-weight:850 !important;min-height:48px;}
.stButton button {min-height:44px;font-weight:800;}
div[data-testid="stExpander"] {border:1px solid #334155;border-radius:12px;background:#111827;}
div[data-testid="stExpander"] summary {color:#f8fafc !important;font-weight:800;}
.stCaption {color:#94a3b8 !important;}
.workflow {display:flex;align-items:center;gap:12px;background:#111827;border:1px solid #334155;border-radius:16px;padding:14px 18px;margin:4px 0 18px;}
.workflow-step {display:flex;align-items:center;gap:10px;min-width:0;}
.workflow-step span {display:inline-flex;width:30px;height:30px;border-radius:50%;align-items:center;justify-content:center;background:#22c55e;color:#052e16;font-weight:900;flex:0 0 auto;}
.workflow-step b {color:#f8fafc;font-size:.95rem;white-space:nowrap;}
.workflow-step small {color:#94a3b8;font-size:.78rem;white-space:nowrap;}
.workflow-arrow {color:#64748b;font-size:1.4rem;font-weight:900;}
.recon-banner {background:#0b2f22;border:1px solid #16835b;border-radius:12px;padding:12px 16px;color:#d1fae5;font-weight:800;margin:12px 0;}
@media (max-width: 900px) {.workflow {flex-wrap:wrap}.workflow-arrow{display:none}.workflow-step{flex:1 1 45%;}}
</style>""",
    unsafe_allow_html=True,
)

def money(x): return f"₹{float(x):,.0f}"
def money2(x): return f"₹{float(x):,.2f}"
def normalize_col(c): return str(c).strip().lower().replace(" ", "_").replace("-", "_")
def parse_num(v):
    if pd.isna(v): return 0.0
    s = str(v).strip().replace(",", "").replace("₹", "")
    if s in ("", "-", "nan", "None"): return 0.0
    return float(s)

def parse_kite_csv(raw):
    df = pd.read_csv(io.BytesIO(raw)); original_columns = list(df.columns); df.columns = [normalize_col(c) for c in df.columns]
    def find_col(candidates):
        for c in candidates:
            if c in df.columns: return c
        return None
    symbol_col = find_col(["instrument", "tradingsymbol", "trading_symbol", "symbol", "trading_symbol_name"])
    qty_col = find_col(["qty.", "qty", "quantity", "t1_quantity", "available_quantity"])
    price_col = find_col(["ltp", "last_price", "price", "current_price"])
    avg_col = find_col(["avg._cost", "avg_cost", "average_cost", "average_price", "avg_price", "buy_price"])
    pnl_col = find_col(["p&l", "pnl", "profit_and_loss", "profit_loss"]); isin_col = find_col(["isin"])
    missing=[]
    if not symbol_col: missing.append("Instrument/tradingsymbol")
    if not qty_col: missing.append("Qty./quantity")
    if not price_col: missing.append("LTP/last_price")
    if missing: raise ValueError("Missing required Kite columns: " + ", ".join(missing) + f". Detected columns: {', '.join(original_columns)}")
    rows=[]; errors=[]
    for i,r in df.iterrows():
        try:
            raw_symbol=r[symbol_col]
            if pd.isna(raw_symbol): continue
            etf=str(raw_symbol).strip().upper()
            if not etf or etf=="NAN": continue
            qty=parse_num(r[qty_col]); ltp=parse_num(r[price_col]); avg=parse_num(r[avg_col]) if avg_col else None; pnl=parse_num(r[pnl_col]) if pnl_col else None
            if qty<0 or ltp<=0: errors.append(f"row {i+2}: invalid quantity/LTP for {etf}"); continue
            rows.append({"etf":etf,"quantity":qty,"average_price":avg,"last_price":ltp,"value":qty*ltp,"pnl":pnl,"isin":str(r[isin_col]).strip() if isin_col and not pd.isna(r[isin_col]) else None})
        except Exception as e: errors.append(f"row {i+2}: {e}")
    if errors: raise ValueError("; ".join(errors[:5]))
    if not rows: raise ValueError("No valid Kite holdings were found in the uploaded CSV.")
    aggregated={}
    for r in rows:
        key=r["etf"]
        if key not in aggregated: aggregated[key]=dict(r); continue
        a=aggregated[key]; old_qty=float(a["quantity"]); new_qty=float(r["quantity"]); total_qty=old_qty+new_qty
        a["quantity"]=total_qty; a["value"]=float(a["value"])+float(r["value"])
        if total_qty>0: a["average_price"]=(float(a["average_price"] or 0)*old_qty+float(r["average_price"] or 0)*new_qty)/total_qty
        a["pnl"]=float(a["pnl"] or 0)+float(r["pnl"] or 0)
        if not a.get("isin"): a["isin"]=r.get("isin")
    return list(aggregated.values()),df

def build_reconciliation(snapshot,kite_rows,target_each):
    by={r["etf"]:r for r in kite_rows}; rows=[]
    for etf in TOP_ETFS:
        r=by.get(etf,{"etf":etf,"quantity":0.0,"average_price":None,"last_price":0.0,"value":0.0,"pnl":None,"isin":None}); current=float(r["value"]); gap=float(target_each-current); price=float(r["last_price"] or 0.0); raw_units=(gap/price) if price>0 else 0.0; trade_units=max(0.0,raw_units) if gap>0 else min(0.0,raw_units); action="BUY" if gap>1 else ("SELL" if gap<-1 else "HOLD")
        rows.append({"ETF":etf,"Kite Units":float(r["quantity"]),"LTP":price,"Current":current,"Target":float(target_each),"Gap":gap,"Target Units":target_each/price if price>0 else 0.0,"Trade Units":trade_units,"Action":action})
    return pd.DataFrame(rows)

def build_execution_ticket(recon):
    rows=[]
    for _,r in recon.iterrows():
        action=r["Action"]; ltp=float(r["LTP"]); gap=float(r["Gap"]); holding=float(r["Kite Units"])
        if action=="BUY" and ltp>0: qty=int(max(0,gap//ltp))
        elif action=="SELL" and ltp>0:
            import math; qty=int(min(holding,math.ceil(abs(gap)/ltp)))
        else: qty=0
        estimated_value=qty*ltp; residual=gap-estimated_value if action=="BUY" else (gap+estimated_value if action=="SELL" else 0.0)
        rows.append({"ETF":r["ETF"],"Action":action,"LTP":ltp,"Whole Units":qty,"Estimated Order Value":estimated_value,"Target Gap":gap,"Residual Gap":residual,"Current Units":holding})
    return pd.DataFrame(rows)

def calculate_gors_decision(capital):
    """Return the frozen engine decision used by the main dashboard.

    The dashboard no longer owns Top-3 or risk-state logic. Those values come
    exclusively from the shared GORS decision service.
    """
    decision = get_current_gors_decision()
    top_etfs = list(decision["top3"])
    risk_state = "RISK-ON" if decision["risk_state"] == "RISK ON" else "RISK-OFF"
    target_exposure = float(capital) * float(decision["target_exposure_pct"])
    target_each = target_exposure / len(top_etfs)
    return {
        "risk_state": risk_state,
        "top_etfs": top_etfs,
        "target_exposure": target_exposure,
        "target_each": target_each,
        "signal": decision["signal"],
        "signal_date": decision["signal_date"],
        "ranking_date": decision["ranking_date"],
        "target_exposure_pct": decision["target_exposure_pct"],
        "current_drawdown": decision["current_drawdown"],
    }

snapshot,kite_rows=latest_kite_snapshot()
latest_market_refresh=get_decisions(limit=1)

with st.sidebar:
    st.markdown("### GORS"); st.caption("Frozen Strategy • Trading Cockpit"); capital=st.number_input("Reference Capital (₹)",min_value=1000.0,value=INITIAL_CAPITAL,step=10000.0)
    if snapshot:
        sidebar_cash=st.number_input("💰 Kite Available Cash (₹)",min_value=0.0,value=float(snapshot["cash"]),step=100.0,key="sidebar_kite_cash",help="Enter the current available cash shown in Kite Funds.")
        if abs(sidebar_cash-float(snapshot["cash"]))>0.001:
            if st.button("💾 Save Kite Cash",type="primary",use_container_width=True): update_kite_cash(snapshot["id"],sidebar_cash); record_integrity("INFO","kite_cash_update",f"Updated Kite cash for snapshot {snapshot['id']} to ₹{sidebar_cash:,.2f}"); st.rerun()
        st.caption(f"Snapshot #{snapshot['id']} • used by Blocks B & C")
    else: st.number_input("💰 Kite Available Cash (₹)",min_value=0.0,value=0.0,step=100.0,key="sidebar_kite_cash",help="Set this before saving your first Kite snapshot."); st.caption("Used when the first Kite snapshot is saved.")
    st.divider(); st.markdown("**Source of truth**"); st.caption("🧠 GORS → Python strategy decision"); st.caption("💰 Kite → actual portfolio + cash"); st.caption("🗄️ Neon PostgreSQL → verified facts + history"); st.divider(); st.markdown("**Frozen parameters**"); st.caption("Top 3 • Hold Rank 5"); st.caption("RSI 14 / 85 / 100"); st.caption("DD 8% • Recovery 75%"); st.caption("Risk-off 50% • Cost 0.25%"); st.divider()
    if st.button("💾 Backup GORS DB",use_container_width=True): p=backup_database(); st.success(f"Backup created: {p}")
    db_path,db_size=db_info(); st.caption(f"DB: {db_path}"); st.caption(f"Size: {db_size:,} bytes")
    if startup_backup: st.caption(f"Daily backup: {startup_backup.name}")

if migration_message: st.info(migration_message)

decision=calculate_gors_decision(capital); risk_state=decision["risk_state"]; TOP_ETFS=decision["top_etfs"]; target_exposure=decision["target_exposure"]; target_each=decision["target_each"]; risk_label="RISK-ON" if risk_state=="RISK-ON" else "RISK-OFF 50%"

def format_market_refresh(value):
    if not value: return "No automated refresh recorded"
    ts=pd.to_datetime(value,utc=True,errors="coerce")
    if pd.isna(ts): return str(value)
    return ts.tz_convert("Asia/Kolkata").strftime("%d-%b-%Y %I:%M:%S %p IST")
market_refresh_text=format_market_refresh(latest_market_refresh[0]["created_at"] if latest_market_refresh else None)

st.markdown(f"""
<div class='hero'>
  <div class='eyebrow'>GORS_APP_PROD • DAILY TRADING COCKPIT</div>
  <div class='hero-title'>Frozen GORS Decision</div>
  <div class='hero-sub'>Python strategy is the source of truth. Kite is the portfolio truth. No broker orders are placed by GORS.</div>
  <div class='hero-sub'><b>🕐 Last Market Refresh:</b> {market_refresh_text}</div>
  <div style='margin-top:14px'><span class='pill pill-green'>🟢 BUY / HOLD</span><span class='pill {{"pill-green" if risk_state == "RISK-ON" else "pill-amber"}}'>{risk_label}</span><span class='pill pill-gray'>TOP 3</span><span class='pill pill-gray'>₹{target_exposure:,.0f} TARGET</span></div>
</div>""",unsafe_allow_html=True)

c1,c2,c3,c4=st.columns(4); c1.metric("Strategy","FROZEN"); c2.metric("Risk State",risk_state); c3.metric("Target Exposure",money(target_exposure)); c4.metric("Target / ETF",money(target_each))

st.markdown("<div class='section-title'>🎯 Today's GORS Top 3</div>",unsafe_allow_html=True); st.markdown("<div class='section-sub'>These are the frozen portfolio targets. The current Kite holdings are reconciled below.</div>",unsafe_allow_html=True)
cols=st.columns(3)
for i,(col,etf) in enumerate(zip(cols,TOP_ETFS),start=1):
    with col: st.markdown(f"""<div class='card'><div class='card-title'>TOP {i} • TARGET</div><div class='big'>{etf}</div><div class='sub'>Target allocation</div><div style='font-size:1.45rem;font-weight:900;margin-top:10px;color:#101828'>{money(target_each)}</div><div style='margin-top:8px'><span class='pill pill-green'>BUY / HOLD</span></div></div>""",unsafe_allow_html=True)

st.markdown("""<div class='workflow'><div class='workflow-step'><span>1</span><b>Load latest Kite snapshot</b><small>Persistent DB</small></div><div class='workflow-arrow'>→</div><div class='workflow-step'><span>2</span><b>Reconcile</b><small>Kite vs GORS</small></div><div class='workflow-arrow'>→</div><div class='workflow-step'><span>3</span><b>Review order ticket</b><small>BUY / SELL / HOLD</small></div><div class='workflow-arrow'>→</div><div class='workflow-step'><span>4</span><b>Execute manually</b><small>Verify in Kite</small></div></div>""",unsafe_allow_html=True)
st.markdown("<div class='section-title'>📥 Step 1 — Kite Portfolio Snapshot</div>",unsafe_allow_html=True); st.markdown("<div class='section-sub'>GORS automatically uses the <b>latest verified Kite snapshot from the persistent database</b>. You only need to upload a new Holdings CSV when your actual Kite portfolio changes (for example, after a trade). Daily runs do not require a new CSV.</div>",unsafe_allow_html=True)
uploaded=st.file_uploader("📄 Upload New Kite Holdings CSV (only after a portfolio change)",type=["csv"],key="kite_csv",help="Optional. Export a fresh Holdings CSV from Kite only when the actual portfolio has changed.")

if uploaded is not None:
    raw=uploaded.getvalue()
    try:
        kite_rows,raw_df=parse_kite_csv(raw); checksum=hashlib.sha256(raw).hexdigest(); portfolio_value=sum(float(r["value"]) for r in kite_rows); top3_rows=[r for r in kite_rows if r["etf"] in TOP_ETFS]
        st.success(f"✅ New Kite CSV validated • {len(raw_df)} CSV rows • {len(kite_rows)} instruments • checksum {checksum[:12]}…")
        preview=pd.DataFrame(top3_rows)[["etf","quantity","last_price","value"]].rename(columns={"etf":"ETF","quantity":"Units","last_price":"LTP","value":"Value"}); st.dataframe(preview,width="stretch",hide_index=True)
        latest_checksum=str(snapshot.get("checksum") or "") if snapshot else ""
        if latest_checksum and checksum==latest_checksum: st.info("ℹ️ This CSV matches the latest saved Kite snapshot. No new DB snapshot is required. If only Kite cash changed, update Kite Available Cash in the left panel.")
        else:
            cash=float(st.session_state.get("sidebar_kite_cash",0.0))
            if st.button("✅ Save New Verified Kite Snapshot",type="primary",use_container_width=True):
                sid=save_kite_snapshot(datetime.now().isoformat(timespec="seconds"),"Kite CSV",uploaded.name,cash,portfolio_value,len(raw_df),checksum,kite_rows,raw_csv=raw); record_integrity("INFO","kite_snapshot",f"Saved complete Kite snapshot {sid}: {len(kite_rows)} instruments, CSV checksum {checksum[:12]}…"); backup=backup_database(); record_integrity("INFO","db_backup",f"Recorded database persistence after Kite snapshot {sid}: {backup.name if backup else 'none'}"); st.success(f"Snapshot #{sid} saved permanently with complete Kite holdings + original CSV. DB backup created."); st.rerun()
    except Exception as e: st.error(f"Kite CSV rejected: {e}")

if snapshot: st.markdown(f"<div class='kite-box'><b>🟢 Latest Kite snapshot automatically loaded from the persistent database</b><br>Snapshot #{snapshot['id']} • {snapshot['snapshot_time']} • {snapshot['file_name']} • checksum {str(snapshot['checksum'])[:12]}…<br><span style='font-size:.9rem'>This saved portfolio is used for Blocks B & C until you upload a newer Kite snapshot.</span></div>",unsafe_allow_html=True)
else: st.warning("🔴 No verified Kite snapshot. Reconciliation and order ticket remain locked.")

st.markdown("<div class='section-title'>🔄 Step 2 — Kite → GORS Reconciliation</div>",unsafe_allow_html=True); st.markdown("<div class='section-sub'>Compare your actual Kite Top 3 holdings with the frozen GORS target. This block answers one question: <b>what do I need to BUY / SELL today?</b></div>",unsafe_allow_html=True)
if snapshot:
    recon=build_reconciliation(snapshot,kite_rows,target_each); current_total=float(recon["Current"].sum()); target_total=float(target_each*len(TOP_ETFS)); cash=float(snapshot["cash"]); buy_value=float(recon.loc[recon["Action"]=="BUY","Gap"].clip(lower=0).sum()); sell_value=float((-recon.loc[recon["Action"]=="SELL","Gap"]).clip(lower=0).sum()); funding_gap=target_total-current_total-cash
    m1,m2,m3,m4=st.columns(4); m1.metric("Kite Top 3 Value",money(current_total)); m2.metric("Kite Cash",money(cash)); m3.metric("GORS Target",money(target_total)); m4.metric("Funding Gap",money(max(0.0,funding_gap)))
    if funding_gap>0.01: st.markdown(f"<div class='recon-banner'>💰 <b>Funding required:</b> {money(funding_gap)} more cash is needed to fully reach the GORS target after using the current Kite cash.</div>",unsafe_allow_html=True)
    elif funding_gap<-0.01: st.markdown(f"<div class='recon-banner'>🟢 <b>Portfolio is fully funded:</b> {money(abs(funding_gap))} remains above the target after including Kite cash.</div>",unsafe_allow_html=True)
    else: st.markdown("<div class='recon-banner'>🟢 <b>Portfolio is fully funded:</b> Kite holdings + cash match the GORS target.</div>",unsafe_allow_html=True)
    rc=st.columns(len(TOP_ETFS))
    for col,(_,r) in zip(rc,recon.iterrows()):
        action=r["Action"]; cls="pill-green" if action=="BUY" else ("pill-red" if action=="SELL" else "pill-gray"); gap=float(r["Gap"]); units=abs(float(r["Trade Units"])); gap_text=f"+{money(gap)}" if gap>0 else money(gap)
        with col: st.markdown(f"""<div class='card'><div class='card-title'>{r['ETF']}</div><div class='big'>{action}</div><div class='sub'>Current <b>{money(r['Current'])}</b></div><div class='sub'>Target <b>{money(r['Target'])}</b></div><div style='font-size:1.2rem;font-weight:900;margin-top:10px'>{gap_text}</div><div class='sub'>Trade <b>{units:,.2f} units</b></div><span class='pill {cls}'>{action}</span></div>""",unsafe_allow_html=True)
    display=recon[["ETF","Kite Units","LTP","Current","Target","Gap","Trade Units","Action"]].copy(); display["LTP"]=display["LTP"].map(lambda x:f"₹{x:,.2f}")
    for c in ["Current","Target","Gap"]: display[c]=display[c].map(lambda x:f"₹{x:,.0f}")
    display["Kite Units"]=display["Kite Units"].map(lambda x:f"{x:,.2f}"); display["Trade Units"]=display["Trade Units"].map(lambda x:f"{x:,.2f}")
    with st.expander("🔎 View exact reconciliation math",expanded=False): st.dataframe(display,width="stretch",hide_index=True)
    checks=[]
    if any(recon["Kite Units"]<0): checks.append(("ERROR","negative_units","Kite snapshot contains negative units."))
    if abs(current_total+recon["Gap"].sum()-target_total)>0.01: checks.append(("ERROR","reconciliation_math","Current holdings + GORS gaps do not reconcile to the target."))
    if cash<0: checks.append(("ERROR","cash","Kite cash cannot be negative."))
    available_for_buys=cash+sell_value
    if buy_value>available_for_buys+0.01: checks.append(("WARNING","cash_capacity",f"BUY value {money(buy_value)} exceeds cash + required SELL proceeds {money(available_for_buys)}."))
    for _,r in recon.iterrows():
        if r["Action"]!="HOLD" and float(r["LTP"])<=0: checks.append(("ERROR","missing_ltp",f"{r['ETF']} has no valid Kite LTP; exact trade quantity cannot be calculated."))
    for sev,name,msg in checks: record_integrity(sev,name,msg)
    if any(sev=="ERROR" for sev,_,_ in checks): st.error("❌ BLOCK 2 FAILED — do not execute the order ticket until the error is resolved.")
    elif any(sev=="WARNING" for sev,_,_ in checks): st.warning("⚠️ GORS target math is correct, but the available Kite cash is not enough to fund the complete rebalance.")
    else: st.success("✅ BLOCK 2 PASSED — Kite holdings, GORS target, prices and trade quantities reconcile correctly.")
    st.markdown("<div class='section-title'>🧾 Step 3 — Today's Order Ticket</div>",unsafe_allow_html=True); st.markdown("<div class='section-sub'>Execution view only: GORS converts the rupee gap into <b>whole ETF units</b>. Review the actual Kite price and available funds before placing orders.</div>",unsafe_allow_html=True)
    ticket_df=build_execution_ticket(recon); ticket_buy=float(ticket_df.loc[ticket_df["Action"]=="BUY","Estimated Order Value"].sum()); ticket_sell=float(ticket_df.loc[ticket_df["Action"]=="SELL","Estimated Order Value"].sum()); ticket_net=ticket_buy-ticket_sell; cash_available=float(snapshot["cash"])+ticket_sell; cash_shortfall=max(0.0,ticket_net-cash_available)
    summary_cols=st.columns(4); summary_cols[0].metric("BUY",money2(ticket_buy)); summary_cols[1].metric("SELL",money2(ticket_sell)); summary_cols[2].metric("NET CASH",money2(ticket_net)); summary_cols[3].metric("Kite Cash Available",money2(float(snapshot["cash"])))
    if cash_shortfall>0.01: st.markdown(f"<div class='recon-banner' style='background:#422006;border-color:#b45309;color:#fef3c7'>⚠️ <b>Additional cash required:</b> {money2(cash_shortfall)}. Do not place the complete BUY ticket until Kite has sufficient funds.</div>",unsafe_allow_html=True)
    else: st.markdown("<div class='recon-banner'>🟢 <b>Execution ticket funded:</b> the rounded BUY orders can be covered by current Kite cash plus required SELL proceeds.</div>",unsafe_allow_html=True)
    for _,r in ticket_df.iterrows():
        action=r["Action"]; qty=int(r["Whole Units"]); ltp=float(r["LTP"]); order_value=float(r["Estimated Order Value"]); residual=float(r["Residual Gap"])
        if action=="BUY" and qty>0: st.markdown(f"<div class='ticket'><div>🟢 <b>BUY {r['ETF']}</b></div><div style='margin-top:6px'>{qty:,} whole units × {money2(ltp)} ≈ <b>{money2(order_value)}</b></div><div style='font-size:.88rem;font-weight:600;color:#a7f3d0;margin-top:5px'>Target gap {money2(abs(r['Target Gap']))} • Residual target gap {money2(abs(residual))}</div></div>",unsafe_allow_html=True)
        elif action=="SELL" and qty>0: st.markdown(f"<div class='ticket ticket-sell'><div>🔴 <b>SELL {r['ETF']}</b></div><div style='margin-top:6px'>{qty:,} whole units × {money2(ltp)} ≈ <b>{money2(order_value)}</b></div><div style='font-size:.88rem;font-weight:600;color:#fecaca;margin-top:5px'>Target gap {money2(abs(r['Target Gap']))} • Residual target gap {money2(abs(residual))}</div></div>",unsafe_allow_html=True)
        else: st.markdown(f"<div class='ticket ticket-hold'>⚪ <b>HOLD {r['ETF']}</b> — no whole-unit adjustment required</div>",unsafe_allow_html=True)
    export_df=ticket_df[["ETF","Action","LTP","Whole Units","Estimated Order Value","Target Gap","Residual Gap"]].copy(); export_df.columns=["ETF","Action","Kite LTP","Whole Units","Estimated Order Value","Target Gap","Residual Gap"]; st.download_button("⬇️ Export Execution Ticket CSV",data=export_df.to_csv(index=False).encode("utf-8"),file_name=f"GORS_Execution_Ticket_{date.today().isoformat()}.csv",mime="text/csv")
    st.caption("Human approval boundary: GORS never places broker orders. In Kite, verify the live LTP, order quantity, order type and available funds immediately before execution.")
else: st.info("Import and save a verified Kite snapshot above to unlock reconciliation and the exact order ticket.")

st.markdown("<div class='section-title'>📊 Strategy & Market Status</div>",unsafe_allow_html=True)
status=pd.DataFrame([["MARKET","NIFTY 200 DMA","Informational only","Does not drive the DD engine"],["RANKING","Monthly","Frozen","GORS selection source"],["MOMENTUM","126 trading days","Frozen","Primary ranking lookback"],["HOLD","Rank ≤ 5","Frozen","Hold/replace hysteresis"],["RSI","14","85 / 100","50% / full exit thresholds"],["RISK","DD trigger","8%","Recovery at 75% of trigger"],["EXPOSURE","Risk-off","50%","Frozen overlay"],["COST","Production assumption","0.25%","Research/backtest assumption"]],columns=["Layer","Parameter","Value","Meaning"]); st.dataframe(status,width="stretch",hide_index=True)
with st.expander("🧠 GORS Decision History",expanded=False):
    dec=get_decisions()
    if dec: st.dataframe(pd.DataFrame(dec),width="stretch",hide_index=True)
    else: st.info("No saved decisions yet.")
with st.expander("📝 GORS Journal",expanded=False):
    with st.form("journal"):
        jd=st.date_input("Date",date.today()); jdec=st.selectbox("Decision",["BUY / HOLD","RISK-OFF","NO ACTION"]); jnote=st.text_area("Note")
        if st.form_submit_button("Save Journal Entry"):
            if jnote.strip(): add_journal(jd.isoformat(),jdec,jnote.strip()); st.success("Saved"); st.rerun()
    journal=get_journal()
    if journal: st.dataframe(pd.DataFrame(journal),width="stretch",hide_index=True)
with st.expander("🛡️ Correctness Log",expanded=False):
    events=get_integrity_events()
    if events: st.dataframe(pd.DataFrame(events),width="stretch",hide_index=True)
    else: st.info("No integrity events recorded.")
with st.expander("🔒 Frozen Strategy / Architecture",expanded=False):
    st.markdown("**GORS = strategy truth**  \n**Kite = actual portfolio and execution truth**  \n**Neon PostgreSQL = persistent memory and verified snapshots**")
    st.json({"Top selection":3,"Hold Rank":5,"RSI":"14 / 85 / 100","Drawdown trigger":"8%","Recovery":"75%","Risk-off exposure":"50%","Transaction cost assumption":"0.25%","Optimization":"OFF","Strategy":"FROZEN"})
st.markdown("<div class='footer-note'>GORS_APP_PROD • Daily Trading Cockpit • Frozen strategy • No broker execution</div>",unsafe_allow_html=True)
