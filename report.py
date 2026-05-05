"""
Loan Portfolio Summary Report Generator (v3 - trimmed)
===============================================
วิธีใช้งาน:
  1. วางไฟล์ CSV ทั้ง 2 ในโฟลเดอร์เดียวกับ script นี้
  2. ชื่อไฟล์ต้องตรงตาม LOAN_CONTRACT_FILE / CLOSED_LOAN_FILE
  3. รัน:  python loan_summary_report.py
  4. เปิด  loan_summary_report.html  ในเบราว์เซอร์
"""

import os, sys, json
import pandas as pd
from datetime import datetime, timedelta

# ── CONFIG ──────────────────────────────────────────
LOAN_CONTRACT_FILE = "LOAN_CONTRACT.csv"
CLOSED_LOAN_FILE   = "CLOSED_LOAN.csv"
OUTPUT_FILE        = "loan_summary_report.html"
# ────────────────────────────────────────────────────


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

    lc["ValueDate"]  = pd.to_datetime(lc["ValueDate"],  errors="coerce")
    cl["ClosedDate"] = pd.to_datetime(cl["ClosedDate"], errors="coerce")
    return lc, cl


def build_daily(lc, cl):
    new_d = lc.groupby(lc["ValueDate"].dt.date).agg(
        new_count    =("ID", "count"),
        new_disbursed=("Disbursed", "sum"),
        avg_size     =("Disbursed", "mean"),
    ).reset_index()
    new_d.columns = ["date", "new_count", "new_disbursed", "avg_size"]

    cl2 = cl.copy()
    cl2["date"] = cl2["ClosedDate"].dt.date
    cls_d = cl2.groupby("date").agg(
        closed_count    =("ID", "count"),
        closed_disbursed=("Disbursed", "sum"),
    ).reset_index()

    daily = (pd.merge(new_d, cls_d, on="date", how="outer")
               .fillna(0).sort_values("date").reset_index(drop=True))
    daily["date"] = daily["date"].astype(str)
    daily["net"]  = daily["new_count"] - daily["closed_count"]
    return daily


def build_monthly(lc, cl):
    lc2 = lc.copy()
    cl2 = cl.copy()
    lc2["YM_key"] = lc2["ValueDate"].dt.to_period("M")
    cl2["YM_key"] = cl2["ClosedDate"].dt.to_period("M")

    nm = lc2.groupby("YM_key").agg(
        new_count=("ID", "count"),
        new_disbursed=("Disbursed", "sum")
    ).reset_index()

    cm = cl2.groupby("YM_key").agg(
        closed_count=("ID", "count"),
        closed_disbursed=("Disbursed", "sum")
    ).reset_index()

    m = pd.merge(nm, cm, on="YM_key", how="outer").fillna(0)
    m = m.sort_values("YM_key")
    m["YM"]  = m["YM_key"].astype(str)
    m["net"] = (m["new_count"] - m["closed_count"]).astype(int)
    return m[["YM", "new_count", "new_disbursed", "closed_count", "closed_disbursed", "net"]]


def jl(series, cap=None):
    vals = series.tolist()
    if cap is not None:
        vals = [None if (v and v > cap) else v for v in vals]
    return json.dumps([round(v, 2) if isinstance(v, float) else v for v in vals])


def render_html(lc, cl, daily, monthly):
    active_loans = len(lc)
    closed_loans = len(cl)

    # ── Daily chart data (last 30 days, count only) ──
    d30       = daily.tail(30)
    d_labels  = json.dumps(d30["date"].tolist())
    d_new_cnt = jl(d30["new_count"])
    d_cls_cnt = jl(d30["closed_count"])

    # ── Monthly table ──
    month_rows = ""
    for _, r in monthly.iterrows():
        nc, cc, net = int(r["new_count"]), int(r["closed_count"]), int(r["net"])
        nd, cd = r["new_disbursed"], r["closed_disbursed"]
        ncolor = "color:#16a34a" if net >= 0 else "color:#dc2626"
        month_rows += (
            f"<tr><td>{r['YM']}</td>"
            f"<td class='r'>{nc:,}</td><td class='r'>${nd:,.0f}</td>"
            f"<td class='r'>{cc:,}</td><td class='r'>${cd:,.0f}</td>"
            f"<td class='r' style='{ncolor};font-weight:600'>{net:+,}</td></tr>"
        )

    # ── JS lookup data ──
    today_dt      = datetime.now().date()
    date_range_14 = [today_dt - timedelta(days=i) for i in range(13, -1, -1)]
    daily_lookup  = {}
    for d in date_range_14:
        ds  = str(d)
        row = daily[daily["date"] == ds]
        if not row.empty:
            r = row.iloc[0]
            daily_lookup[ds] = {
                "new_cnt": int(r["new_count"]), "cls_cnt": int(r["closed_count"]),
                "new_dis": float(r["new_disbursed"]), "cls_dis": float(r["closed_disbursed"])
            }
        else:
            daily_lookup[ds] = {"new_cnt": 0, "cls_cnt": 0, "new_dis": 0.0, "cls_dis": 0.0}

    monthly_lookup = {
        str(r["YM"]): {
            "new_cnt": int(r["new_count"]), "cls_cnt": int(r["closed_count"]),
            "new_dis": float(r["new_disbursed"]), "cls_dis": float(r["closed_disbursed"]),
            "net": int(r["net"])
        } for _, r in monthly.iterrows()
    }

    dropdown_options = "".join([
        f'<option value="{str(d)}">{d.strftime("%d/%m/%Y")}</option>'
        for d in reversed(date_range_14)
    ])

    TH_MONTHS = ["","ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]
    month_dropdown_options = ""
    for ym in sorted(monthly["YM"].tolist(), reverse=True):
        y, mo = ym.split("-")
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
.topbar{{background:linear-gradient(135deg,#1e3a8a 0%,#1d4ed8 100%);color:#fff;padding:1.2rem 2rem;display:flex;justify-content:space-between;align-items:center}}
.topbar h1{{font-size:20px;font-weight:600;letter-spacing:.3px}}
.page{{max-width:1400px;margin:0 auto;padding:1.2rem 1.5rem}}
.card{{background:#fff;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.2rem;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card-title{{font-size:14px;font-weight:700;color:#1e3a8a;border-bottom:2px solid #e0e7ff;padding-bottom:.55rem;margin-bottom:1rem;display:flex;align-items:center;gap:8px;justify-content:space-between}}
.kpi{{background:#f8faff;border:1px solid #e0e7ff;border-radius:10px;padding:.9rem 1rem}}
.kpi-label{{font-size:11px;color:#64748b;margin-bottom:5px}}
.kpi-value{{font-size:21px;font-weight:700}}
.chart-wrap{{position:relative;width:100%}}.ch240{{height:240px}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#eef2ff;color:#3730a3;padding:7px 10px;text-align:left;position:sticky;top:0}}
td{{padding:6px 10px;border-bottom:1px solid #f1f5f9}}
td.r{{text-align:right}}
.tscroll{{max-height:340px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px}}
select{{font-size:12px;padding:3px 6px;border-radius:6px;border:1px solid #c7d2fe}}
</style>
</head>
<body>
<div class="topbar">
  <div><h1>📊 Loan Portfolio Dashboard</h1><p>สร้างเมื่อ {now}</p></div>
  <div style="text-align:right">Active: <b>{active_loans:,}</b> | Closed: <b>{closed_loans:,}</b></div>
</div>
<div class="page">

<!-- Daily & Monthly cards -->
<div class="g2">
  <!-- Daily card -->
  <div class="card" style="border-top:5px solid #1d4ed8">
    <div class="card-title">
      <span>☀️ รายวัน — <span id="selectedDateLabel">-</span></span>
      <select id="dateFilter" onchange="updateDayCard(this.value)">{dropdown_options}</select>
    </div>
    <div style="height:160px"><canvas id="todayPie"></canvas></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
      <div class="kpi">
        <div class="kpi-label">ใหม่</div>
        <div class="kpi-value" id="d-new-cnt">0</div>
        <div style="font-size:10px">$<span id="d-new-dis">0</span></div>
      </div>
      <div class="kpi">
        <div class="kpi-label">ปิด</div>
        <div class="kpi-value" id="d-cls-cnt">0</div>
        <div style="font-size:10px">$<span id="d-cls-dis">0</span></div>
      </div>
    </div>
  </div>

  <!-- Monthly card -->
  <div class="card" style="border-top:5px solid #7c3aed">
    <div class="card-title">
      <span>📆 รายเดือน — <span id="selectedMonthLabel">-</span></span>
      <select id="monthFilter" onchange="updateMonthCard(this.value)">{month_dropdown_options}</select>
    </div>
    <div style="height:160px"><canvas id="monthPie"></canvas></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
      <div class="kpi">
        <div class="kpi-label">ใหม่</div>
        <div class="kpi-value" id="m-new-cnt">0</div>
        <div style="font-size:10px">$<span id="m-new-dis">0</span></div>
      </div>
      <div class="kpi">
        <div class="kpi-label">ปิด</div>
        <div class="kpi-value" id="m-cls-cnt">0</div>
        <div style="font-size:10px">$<span id="m-cls-dis">0</span></div>
      </div>
    </div>
  </div>
</div>

<!-- Daily bar chart (count only) -->
<div class="card">
  <div class="card-title">📅 จำนวนสัญญารายวัน (30 วันล่าสุด)</div>
  <div class="chart-wrap ch240"><canvas id="dCnt"></canvas></div>
</div>

<!-- Monthly summary table -->
<div class="card">
  <div class="card-title">📋 สรุปรายเดือน</div>
  <div class="tscroll">
    <table>
      <thead>
        <tr>
          <th>เดือน</th>
          <th class="r">สัญญาใหม่ (จำนวน)</th><th class="r">)มูลค่า (USD)</th>
          <th class="r">สัญญาปิด (จำนวน)</th><th class="r">มูลค่า (USD)</th>
          <th class="r">Net</th>
        </tr>
      </thead>
      <tbody>{month_rows}</tbody>
    </table>
  </div>
</div>

</div><!-- .page -->

<script>
const dailyLookup   = {json.dumps(daily_lookup)};
const monthlyLookup = {json.dumps(monthly_lookup)};
let todayPieChart, monthPieChart;

function fmt(n) {{ return Number(n).toLocaleString(); }}

function updateDayCard(dateKey) {{
  const d = dailyLookup[dateKey] || {{new_cnt:0,cls_cnt:0,new_dis:0,cls_dis:0}};
  document.getElementById('selectedDateLabel').textContent = dateKey;
  document.getElementById('d-new-cnt').textContent = fmt(d.new_cnt);
  document.getElementById('d-cls-cnt').textContent = fmt(d.cls_cnt);
  document.getElementById('d-new-dis').textContent = fmt(d.new_dis);
  document.getElementById('d-cls-dis').textContent = fmt(d.cls_dis);
  if (todayPieChart) {{
    todayPieChart.data.datasets[0].data = [d.new_cnt, d.cls_cnt];
    todayPieChart.update();
  }}
}}

function updateMonthCard(ymKey) {{
  const d = monthlyLookup[ymKey] || {{new_cnt:0,cls_cnt:0,new_dis:0,cls_dis:0}};
  document.getElementById('selectedMonthLabel').textContent = ymKey;
  document.getElementById('m-new-cnt').textContent = fmt(d.new_cnt);
  document.getElementById('m-cls-cnt').textContent = fmt(d.cls_cnt);
  document.getElementById('m-new-dis').textContent = fmt(d.new_dis);
  document.getElementById('m-cls-dis').textContent = fmt(d.cls_dis);
  if (monthPieChart) {{
    monthPieChart.data.datasets[0].data = [d.new_cnt, d.cls_cnt];
    monthPieChart.update();
  }}
}}

window.onload = () => {{
  todayPieChart = new Chart(document.getElementById('todayPie'), {{
    type: 'doughnut',
    data: {{ labels:['ใหม่','ปิด'], datasets:[{{data:[0,0], backgroundColor:['#3b82f6','#16a34a']}}] }},
    options: {{ maintainAspectRatio:false, cutout:'70%' }}
  }});

  monthPieChart = new Chart(document.getElementById('monthPie'), {{
    type: 'doughnut',
    data: {{ labels:['ใหม่','ปิด'], datasets:[{{data:[0,0], backgroundColor:['#7c3aed','#f59e0b']}}] }},
    options: {{ maintainAspectRatio:false, cutout:'70%' }}
  }});

  updateDayCard(document.getElementById('dateFilter').value);
  updateMonthCard(document.getElementById('monthFilter').value);

  new Chart(document.getElementById('dCnt'), {{
    type: 'bar',
    data: {{
      labels: {d_labels},
      datasets: [
        {{ label:'ใหม่', data:{d_new_cnt}, backgroundColor:'#3b82f6' }},
        {{ label:'ปิด',  data:{d_cls_cnt}, backgroundColor:'#16a34a' }}
      ]
    }},
    options: {{ maintainAspectRatio:false }}
  }});
}};
</script>
</body></html>"""


def main():
    folder = os.path.dirname(os.path.abspath(__file__))
    print("="*55)
    print(" Loan Portfolio Dashboard Generator v3 (trimmed)")
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