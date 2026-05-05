"""
Loan Portfolio Summary Report Generator (v7)
- Product breakdown follows day/month dropdown filter
- Download report as CSV
"""

import os, sys, json
import pandas as pd
from datetime import datetime, timedelta

LOAN_CONTRACT_FILE = "LOAN_CONTRACT.csv"
CLOSED_LOAN_FILE   = "CLOSED_LOAN.csv"
OUTPUT_FILE        = "loan_summary_report.html"

LOAN_PRODUCT_NAMES = {
    101: "HP AT",
    102: "HP MO",
    103: "HP BB",
    104: "HP TU",
    105: "PL",
    106: "HP MO-S",
    107: "HP MO-M",
    108: "HP MO-L",
    109: "PawnShop-MC Monthly",
    110: "HP Locked Phone",
}

PRODUCT_COLORS = [
    "#3b82f6","#7c3aed","#16a34a","#f59e0b",
    "#ef4444","#06b6d4","#ec4899","#84cc16",
    "#f97316","#6366f1",
]


def load(folder):
    lc_p = os.path.join(folder, LOAN_CONTRACT_FILE)
    cl_p = os.path.join(folder, CLOSED_LOAN_FILE)
    miss = [p for p in [lc_p, cl_p] if not os.path.exists(p)]
    if miss:
        print("❌ ไม่พบไฟล์:"); [print(f"    {m}") for m in miss]; sys.exit(1)
    print(f"✅ {LOAN_CONTRACT_FILE}", end=" ... ")
    lc = pd.read_csv(lc_p); print(f"{len(lc):,} rows")
    print(f"✅ {CLOSED_LOAN_FILE}",  end=" ... ")
    cl = pd.read_csv(cl_p); print(f"{len(cl):,} rows")
    lc["ValueDate"]  = pd.to_datetime(lc["ValueDate"],  dayfirst=True, errors="coerce")
    cl["ClosedDate"] = pd.to_datetime(cl["ClosedDate"], dayfirst=True, errors="coerce")
    return lc, cl


def plabel(code):
    try:
        return LOAN_PRODUCT_NAMES.get(int(code), f"Product {int(code)}")
    except Exception:
        return "Unknown"


def build_daily(lc, cl):
    new_d = lc.groupby(lc["ValueDate"].dt.date).agg(
        new_count    =("ID","count"),
        new_disbursed=("Disbursed","sum"),
    ).reset_index()
    new_d.columns = ["date","new_count","new_disbursed"]
    cl2 = cl.copy(); cl2["date"] = cl2["ClosedDate"].dt.date
    cls_d = cl2.groupby("date").agg(
        closed_count    =("ID","count"),
        closed_disbursed=("Disbursed","sum"),
    ).reset_index()
    daily = (pd.merge(new_d, cls_d, on="date", how="outer")
               .fillna(0).sort_values("date").reset_index(drop=True))
    daily["date"] = daily["date"].astype(str)
    daily["net"]  = daily["new_count"] - daily["closed_count"]
    return daily


def build_monthly(lc, cl):
    lc2 = lc.copy(); cl2 = cl.copy()
    lc2["YM_key"] = lc2["ValueDate"].dt.to_period("M")
    cl2["YM_key"] = cl2["ClosedDate"].dt.to_period("M")
    nm = lc2.groupby("YM_key").agg(new_count=("ID","count"), new_disbursed=("Disbursed","sum")).reset_index()
    cm = cl2.groupby("YM_key").agg(closed_count=("ID","count"), closed_disbursed=("Disbursed","sum")).reset_index()
    m = pd.merge(nm, cm, on="YM_key", how="outer").fillna(0).sort_values("YM_key")
    m["YM"]  = m["YM_key"].astype(str)
    m["net"] = (m["new_count"] - m["closed_count"]).astype(int)
    return m[["YM","new_count","new_disbursed","closed_count","closed_disbursed","net"]]


def build_daily_prod_lookup(lc, cl, date_range):
    lc2 = lc.copy(); cl2 = cl.copy()
    lc2["date"] = lc2["ValueDate"].dt.date.astype(str)
    cl2["date"] = cl2["ClosedDate"].dt.date.astype(str)
    lc2["prod"] = lc2["LoanProduct"].apply(plabel)
    cl2["prod"] = cl2["LoanProduct"].apply(plabel)
    ng = lc2.groupby(["date","prod"]).agg(cnt=("ID","count"), dis=("Disbursed","sum")).reset_index()
    cg = cl2.groupby(["date","prod"]).agg(cnt=("ID","count"), dis=("Disbursed","sum")).reset_index()
    lookup = {}
    for d in date_range:
        ds = str(d)
        rn = ng[ng["date"]==ds]; rc = cg[cg["date"]==ds]
        prods = {}
        for p in LOAN_PRODUCT_NAMES.values():
            n = rn[rn["prod"]==p]; c = rc[rc["prod"]==p]
            nc = int(n["cnt"].values[0]) if len(n) else 0
            nd = float(n["dis"].values[0]) if len(n) else 0.0
            cc = int(c["cnt"].values[0]) if len(c) else 0
            cd = float(c["dis"].values[0]) if len(c) else 0.0
            if nc or cc:
                prods[p] = {"nc":nc,"nd":nd,"cc":cc,"cd":cd}
        lookup[ds] = prods
    return lookup


def build_monthly_prod_lookup(lc, cl, ym_list):
    lc2 = lc.copy(); cl2 = cl.copy()
    lc2["YM"] = lc2["ValueDate"].dt.to_period("M").astype(str)
    cl2["YM"] = cl2["ClosedDate"].dt.to_period("M").astype(str)
    lc2["prod"] = lc2["LoanProduct"].apply(plabel)
    cl2["prod"] = cl2["LoanProduct"].apply(plabel)
    ng = lc2.groupby(["YM","prod"]).agg(cnt=("ID","count"), dis=("Disbursed","sum")).reset_index()
    cg = cl2.groupby(["YM","prod"]).agg(cnt=("ID","count"), dis=("Disbursed","sum")).reset_index()
    lookup = {}
    for ym in ym_list:
        rn = ng[ng["YM"]==ym]; rc = cg[cg["YM"]==ym]
        prods = {}
        for p in LOAN_PRODUCT_NAMES.values():
            n = rn[rn["prod"]==p]; c = rc[rc["prod"]==p]
            nc = int(n["cnt"].values[0]) if len(n) else 0
            nd = float(n["dis"].values[0]) if len(n) else 0.0
            cc = int(c["cnt"].values[0]) if len(c) else 0
            cd = float(c["dis"].values[0]) if len(c) else 0.0
            if nc or cc:
                prods[p] = {"nc":nc,"nd":nd,"cc":cc,"cd":cd}
        lookup[ym] = prods
    return lookup


def jl(series):
    vals = series.tolist()
    return json.dumps([round(v,2) if isinstance(v,float) else v for v in vals])


def render_html(lc, cl, daily, monthly):
    active_loans = len(lc)
    closed_loans = len(cl)

    d30       = daily.tail(30)
    d_labels  = json.dumps(d30["date"].tolist())
    d_new_cnt = jl(d30["new_count"])
    d_cls_cnt = jl(d30["closed_count"])

    month_rows = ""
    for _, r in monthly.iterrows():
        nc,cc,net = int(r["new_count"]),int(r["closed_count"]),int(r["net"])
        nd,cd = r["new_disbursed"],r["closed_disbursed"]
        nc_col = "color:#16a34a" if net>=0 else "color:#dc2626"
        month_rows += (f"<tr><td>{r['YM']}</td>"
            f"<td class='r'>{nc:,}</td><td class='r'>${nd:,.0f}</td>"
            f"<td class='r'>{cc:,}</td><td class='r'>${cd:,.0f}</td>"
            f"<td class='r' style='{nc_col};font-weight:600'>{net:+,}</td></tr>")

    today_dt      = datetime.now().date()
    date_range_14 = [today_dt - timedelta(days=i) for i in range(13,-1,-1)]

    daily_lookup = {}
    for d in date_range_14:
        ds = str(d); row = daily[daily["date"]==ds]
        if not row.empty:
            r = row.iloc[0]
            daily_lookup[ds] = {"new_cnt":int(r["new_count"]),"cls_cnt":int(r["closed_count"]),
                                 "new_dis":float(r["new_disbursed"]),"cls_dis":float(r["closed_disbursed"])}
        else:
            daily_lookup[ds] = {"new_cnt":0,"cls_cnt":0,"new_dis":0.0,"cls_dis":0.0}

    monthly_lookup = {
        str(r["YM"]): {"new_cnt":int(r["new_count"]),"cls_cnt":int(r["closed_count"]),
                       "new_dis":float(r["new_disbursed"]),"cls_dis":float(r["closed_disbursed"]),
                       "net":int(r["net"])}
        for _,r in monthly.iterrows()
    }

    ym_list             = monthly["YM"].tolist()
    daily_prod_lookup   = build_daily_prod_lookup(lc, cl, date_range_14)
    monthly_prod_lookup = build_monthly_prod_lookup(lc, cl, ym_list)

    all_products = list(LOAN_PRODUCT_NAMES.values())
    prod_colors  = json.dumps(PRODUCT_COLORS[:len(all_products)])

    dropdown_options = "".join([
        f'<option value="{str(d)}">{d.strftime("%d/%m/%Y")}</option>'
        for d in reversed(date_range_14)
    ])
    TH_MONTHS = ["","ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]
    month_dropdown_options = ""
    for ym in sorted(ym_list, reverse=True):
        y,mo = ym.split("-")
        month_dropdown_options += f'<option value="{ym}">{TH_MONTHS[int(mo)]} {y}</option>'

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loan Portfolio Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Sarabun','Segoe UI',sans-serif;background:#eef0f5;color:#1e293b;font-size:14px}}
.topbar{{background:linear-gradient(135deg,#1e3a8a 0%,#1d4ed8 100%);color:#fff;padding:1.2rem 2rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.8rem}}
.topbar h1{{font-size:20px;font-weight:600}}
.page{{max-width:1400px;margin:0 auto;padding:1.2rem 1.5rem}}
.card{{background:#fff;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card-title{{font-size:14px;font-weight:700;color:#1e3a8a;border-bottom:2px solid #e0e7ff;padding-bottom:.55rem;margin-bottom:1rem;display:flex;align-items:center;gap:8px;justify-content:space-between;flex-wrap:wrap}}
.kpi{{background:#f8faff;border:1px solid #e0e7ff;border-radius:10px;padding:.9rem 1rem}}
.kpi-label{{font-size:11px;color:#64748b;margin-bottom:5px}}
.kpi-value{{font-size:21px;font-weight:700}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}}
.g2b{{display:grid;grid-template-columns:1fr 1.5fr;gap:1.2rem}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#eef2ff;color:#3730a3;padding:7px 10px;text-align:left;position:sticky;top:0;z-index:1}}
td{{padding:6px 10px;border-bottom:1px solid #f1f5f9}}
td.r{{text-align:right}}
tr:hover td{{background:#f8faff}}
.tscroll{{max-height:320px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px}}
select{{font-size:12px;padding:3px 8px;border-radius:6px;border:1px solid #c7d2fe;background:#fff}}
.btn{{border:none;border-radius:8px;padding:7px 16px;font-size:13px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;transition:background .15s}}
.btn-white{{background:#fff;color:#1e3a8a}}.btn-white:hover{{background:#dbeafe}}
.btn-green{{background:#16a34a;color:#fff}}.btn-green:hover{{background:#15803d}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}}
.empty{{text-align:center;padding:24px;color:#94a3b8;font-size:13px}}
</style>
</head>
<body>
<div class="topbar">
  <div><h1>📊 Loan Portfolio Dashboard</h1><p style="font-size:12px;opacity:.8">สร้างเมื่อ {now}</p></div>
  <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
    <div style="text-align:right;font-size:13px">Active: <b>{active_loans:,}</b> &nbsp;|&nbsp; Closed: <b>{closed_loans:,}</b></div>
    <button class="btn btn-green" onclick="downloadCSV()">⬇️ Download CSV</button>
  </div>
</div>

<div class="page">

<!-- Row 1: Daily & Monthly cards -->
<div class="g2">
  <div class="card" style="border-top:5px solid #1d4ed8">
    <div class="card-title">
      <span>☀️ รายวัน — <span id="dLabel">-</span></span>
      <select id="dateFilter" onchange="onDateChange(this.value)">{dropdown_options}</select>
    </div>
    <div style="height:150px"><canvas id="todayPie"></canvas></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
      <div class="kpi"><div class="kpi-label">ใหม่</div><div class="kpi-value" id="d-nc">0</div><div style="font-size:10px">$<span id="d-nd">0</span></div></div>
      <div class="kpi"><div class="kpi-label">ปิด</div><div class="kpi-value" id="d-cc">0</div><div style="font-size:10px">$<span id="d-cd">0</span></div></div>
    </div>
  </div>

  <div class="card" style="border-top:5px solid #7c3aed">
    <div class="card-title">
      <span>📆 รายเดือน — <span id="mLabel">-</span></span>
      <select id="monthFilter" onchange="onMonthChange(this.value)">{month_dropdown_options}</select>
    </div>
    <div style="height:150px"><canvas id="monthPie"></canvas></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
      <div class="kpi"><div class="kpi-label">ใหม่</div><div class="kpi-value" id="m-nc">0</div><div style="font-size:10px">$<span id="m-nd">0</span></div></div>
      <div class="kpi"><div class="kpi-label">ปิด</div><div class="kpi-value" id="m-cc">0</div><div style="font-size:10px">$<span id="m-cd">0</span></div></div>
    </div>
  </div>
</div>

<!-- Row 2: Product breakdown — follows both dropdowns -->
<div class="g2b">
  <div class="card" style="border-top:5px solid #06b6d4">
    <div class="card-title" style="flex-direction:column;align-items:flex-start;gap:6px">
      <span>🏷️ Loan Product — <span id="prodDLabel" style="color:#0891b2"></span></span>
      <span style="font-size:11px;color:#64748b">📆 <span id="prodMLabel" style="color:#7c3aed"></span></span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
      <div>
        <p style="font-size:10px;color:#64748b;font-weight:600;text-align:center;margin-bottom:2px">สัญญาใหม่</p>
        <div style="height:190px"><canvas id="prodNewPie"></canvas></div>
      </div>
      <div>
        <p style="font-size:10px;color:#64748b;font-weight:600;text-align:center;margin-bottom:2px">สัญญาปิด</p>
        <div style="height:190px"><canvas id="prodClsPie"></canvas></div>
      </div>
    </div>
  </div>

  <div class="card" style="border-top:5px solid #06b6d4">
    <div class="card-title">📋 รายละเอียด Loan Product</div>
    <div class="tscroll">
      <table>
        <thead><tr>
          <th>Product</th>
          <th class="r">ใหม่</th><th class="r">มูลค่า (USD)</th>
          <th class="r">ปิด</th><th class="r">มูลค่า (USD)</th>
          <th class="r">Net</th>
        </tr></thead>
        <tbody id="prodBody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- Row 3: Daily bar -->
<div class="card">
  <div class="card-title">📅 จำนวนสัญญารายวัน (30 วันล่าสุด)</div>
  <div style="height:240px"><canvas id="dBar"></canvas></div>
</div>

<!-- Row 4: Monthly table -->
<div class="card">
  <div class="card-title">📋 สรุปรายเดือน</div>
  <div class="tscroll">
    <table>
      <thead><tr>
        <th>เดือน</th>
        <th class="r">สัญญาใหม่</th><th class="r">มูลค่า (USD)</th>
        <th class="r">สัญญาปิด</th><th class="r">มูลค่า (USD)</th>
        <th class="r">Net</th>
      </tr></thead>
      <tbody>{month_rows}</tbody>
    </table>
  </div>
</div>

</div>

<script>
// ── data ──────────────────────────────────────────────────
const DL  = {json.dumps(daily_lookup)};
const ML  = {json.dumps(monthly_lookup)};
const DPL = {json.dumps(daily_prod_lookup)};
const MPL = {json.dumps(monthly_prod_lookup)};
const ALL_PRODS  = {json.dumps(all_products)};
const COLORS      = {prod_colors};

let curDate='', curMonth='';
let todayChart, monthChart, newChart, clsChart;

const fmt  = n => Number(n).toLocaleString();
const fmtD = n => '$'+Number(n).toLocaleString(undefined,{{maximumFractionDigits:0}});

// ── update product section (called after either dropdown changes) ──
function updateProd() {{
  // daily side
  const dp = DPL[curDate] || {{}};
  document.getElementById('prodDLabel').textContent = curDate || '-';

  // monthly side
  const mp = MPL[curMonth] || {{}};
  document.getElementById('prodMLabel').textContent = curMonth || '-';

  // merge: show union of products that appear in either filter
  const keys = [...new Set([...Object.keys(dp),...Object.keys(mp)])];
  const active = ALL_PRODS.filter(p => keys.includes(p));
  const colors = active.map(p => COLORS[ALL_PRODS.indexOf(p)]);

  const newD = active.map(p => (dp[p]||{{}}).nc||0);
  const clsD = active.map(p => (mp[p]||{{}}).cc||0);

  // donut new (from daily filter)
  newChart.data.labels = active;
  newChart.data.datasets[0].data = active.map(p=>(dp[p]||{{}}).nc||0);
  newChart.data.datasets[0].backgroundColor = colors;
  newChart.update();

  // donut closed (from monthly filter)
  clsChart.data.labels = active;
  clsChart.data.datasets[0].data = active.map(p=>(mp[p]||{{}}).cc||0);
  clsChart.data.datasets[0].backgroundColor = colors;
  clsChart.update();

  // table — show all products that appear in either
  const tbody = document.getElementById('prodBody');
  const rows = ALL_PRODS.map((p,i) => {{
    const d=dp[p]||{{nc:0,nd:0,cc:0,cd:0}};
    const m=mp[p]||{{nc:0,nd:0,cc:0,cd:0}};
    if(!d.nc&&!d.nd&&!m.cc&&!m.cd) return null;
    const net=d.nc-m.cc;
    const nc=net>=0?'color:#16a34a':'color:#dc2626';
    return `<tr>
      <td><span class="dot" style="background:${{COLORS[i]}}"></span><b>${{p}}</b></td>
      <td class="r">${{fmt(d.nc)}}</td><td class="r">${{fmtD(d.nd)}}</td>
      <td class="r">${{fmt(m.cc)}}</td><td class="r">${{fmtD(m.cd)}}</td>
      <td class="r" style="${{nc}};font-weight:600">${{net>=0?'+':''}}${{fmt(net)}}</td>
    </tr>`;
  }}).filter(Boolean);
  tbody.innerHTML = rows.length
    ? rows.join('')
    : '<tr><td colspan="6" class="empty">ไม่มีข้อมูลในช่วงที่เลือก</td></tr>';
}}

function onDateChange(v) {{
  curDate = v;
  const d = DL[v]||{{new_cnt:0,cls_cnt:0,new_dis:0,cls_dis:0}};
  document.getElementById('dLabel').textContent = v;
  document.getElementById('d-nc').textContent = fmt(d.new_cnt);
  document.getElementById('d-cc').textContent = fmt(d.cls_cnt);
  document.getElementById('d-nd').textContent = fmt(d.new_dis);
  document.getElementById('d-cd').textContent = fmt(d.cls_dis);
  todayChart.data.datasets[0].data = [d.new_cnt,d.cls_cnt];
  todayChart.update();
  updateProd();
}}

function onMonthChange(v) {{
  curMonth = v;
  const d = ML[v]||{{new_cnt:0,cls_cnt:0,new_dis:0,cls_dis:0}};
  document.getElementById('mLabel').textContent = v;
  document.getElementById('m-nc').textContent = fmt(d.new_cnt);
  document.getElementById('m-cc').textContent = fmt(d.cls_cnt);
  document.getElementById('m-nd').textContent = fmt(d.new_dis);
  document.getElementById('m-cd').textContent = fmt(d.cls_dis);
  monthChart.data.datasets[0].data = [d.new_cnt,d.cls_cnt];
  monthChart.update();
  updateProd();
}}

// ── CSV download ──────────────────────────────────────────
function downloadCSV() {{
  const rows = [];
  // Section 1: monthly summary
  rows.push(['=== สรุปรายเดือน ===']);
  rows.push(['เดือน','สัญญาใหม่ (จำนวน)','มูลค่าใหม่ (USD)','สัญญาปิด (จำนวน)','มูลค่าปิด (USD)','Net']);
  for(const [ym,d] of Object.entries(ML)){{
    rows.push([ym,d.new_cnt,d.new_dis,d.cls_cnt,d.cls_dis,d.net]);
  }}
  rows.push([]);

  // Section 2: product daily (selected date)
  const dp = DPL[curDate]||{{}};
  rows.push([`=== Loan Product รายวัน (${{curDate}}) ===`]); // แก้ตรงนี้ให้เป็น {{curDate}}
  rows.push(['Product','สัญญาใหม่','มูลค่าใหม่ (USD)']);
  ALL_PRODS.forEach(p=>{{
    const d=dp[p]||{{nc:0,nd:0}};
    if(d.nc||d.nd) rows.push([p,d.nc,d.nd]);
  }});
  rows.push([]);

  // Section 3: product monthly (selected month)
  const mp = MPL[curMonth]||{{}};
  rows.push([`=== Loan Product รายเดือน (${{curMonth}}) ===`]); // แก้ตรงนี้ให้เป็น {{curMonth}}
  rows.push(['Product','สัญญาปิด','มูลค่าปิด (USD)']);
  ALL_PRODS.forEach(p=>{{
    const d=mp[p]||{{cc:0,cd:0}};
    if(d.cc||d.cd) rows.push([p,d.cc,d.cd]);
  }});

  const csv = rows.map(r=>r.map(c=>`"${{String(c).replace(/"/g,'""')}}"`).join(',')).join('\\n');
  const bom  = '\\uFEFF'; // UTF-8 BOM for Excel Thai
  const blob = new Blob([bom+csv],{{type:'text/csv;charset=utf-8'}});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `loan_report_${{curDate||'all'}}.csv`; // แก้ตรงนี้ให้เป็น {{curDate}}
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}}

// ── init ──────────────────────────────────────────────────
window.onload = () => {{
  const doOpts = cut => ({{
    maintainAspectRatio:false, cutout:cut,
    plugins:{{ legend:{{ position:'bottom', labels:{{ font:{{size:10}}, boxWidth:10, padding:4 }} }} }}
  }});

  todayChart = new Chart(document.getElementById('todayPie'),{{
    type:'doughnut',
    data:{{ labels:['ใหม่','ปิด'], datasets:[{{data:[0,0],backgroundColor:['#3b82f6','#16a34a']}}] }},
    options:doOpts('70%')
  }});
  monthChart = new Chart(document.getElementById('monthPie'),{{
    type:'doughnut',
    data:{{ labels:['ใหม่','ปิด'], datasets:[{{data:[0,0],backgroundColor:['#7c3aed','#f59e0b']}}] }},
    options:doOpts('70%')
  }});
  newChart = new Chart(document.getElementById('prodNewPie'),{{
    type:'doughnut',
    data:{{ labels:[], datasets:[{{data:[],backgroundColor:[]}}] }},
    options:doOpts('55%')
  }});
  clsChart = new Chart(document.getElementById('prodClsPie'),{{
    type:'doughnut',
    data:{{ labels:[], datasets:[{{data:[],backgroundColor:[]}}] }},
    options:doOpts('55%')
  }});

  onDateChange(document.getElementById('dateFilter').value);
  onMonthChange(document.getElementById('monthFilter').value);

  new Chart(document.getElementById('dBar'),{{
    type:'bar',
    data:{{
      labels:{d_labels},
      datasets:[
        {{label:'ใหม่',data:{d_new_cnt},backgroundColor:'#3b82f6'}},
        {{label:'ปิด', data:{d_cls_cnt},backgroundColor:'#16a34a'}}
      ]
    }},
    options:{{maintainAspectRatio:false}}
  }});
}};
</script>
</body></html>"""


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    print("="*55)
    print(" Loan Portfolio Dashboard Generator v7")
    print("="*55)
    lc, cl = load(folder)
    print("📊 วิเคราะห์...")
    daily   = build_daily(lc, cl)
    monthly = build_monthly(lc, cl)
    print("📝 สร้าง HTML...")
    html = render_html(lc, cl, daily, monthly)
    out  = os.path.join(folder, OUTPUT_FILE)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ บันทึกที่: {out}")
    print("="*55)

if __name__ == "__main__":
    main()
