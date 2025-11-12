# app.py

from flask import Flask, request, render_template_string, send_file, jsonify, redirect, url_for, session, flash
import pandas as pd
import numpy as np
import io, json, tempfile, os, csv
from datetime import datetime

# For PDF export (no matplotlib)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

app = Flask(__name__)
app.secret_key = "replace-with-a-strong-secret-key"  # required for sessions

USERS_CSV = "users.csv"

# -------------------- Login HTML --------------------
LOGIN_HTML = r"""
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login | Sales Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background:#0b0e14; color:#e6edf3; }
    .card { background:#0f1624; border:1px solid #1f2a3a; }
    .form-control { background:#0f1624; color:#e6edf3; border-color:#1f2a3a; }
    .btn-primary { background:#2563eb; border-color:#2563eb; }
  </style>
</head>
<body>
  <div class="container py-5">
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card p-4">
          <h4 class="mb-3 text-center">🔐 Login</h4>
          {% with messages = get_flashed_messages() %}
            {% if messages %}
              <div class="alert alert-danger py-2">{{ messages[0] }}</div>
            {% endif %}
          {% endwith %}
          <form method="POST" action="{{ url_for('login') }}">
            <div class="mb-3">
              <label class="form-label">Email</label>
              <input name="email" type="email" class="form-control" placeholder="admin@example.com" required>
            </div>
            <div class="mb-3">
              <label class="form-label">Password</label>
              <input name="password" type="password" class="form-control" placeholder="••••" required>
            </div>
            <button class="btn btn-primary w-100">Login</button>
          </form>
          <p class="text-secondary small mt-3">
            Default user (auto-created if missing): <code>admin@example.com / 1234</code>
          </p>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

# -------------------- Dashboard HTML --------------------
HTML = r"""
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sales Dashboard (Dark)</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { background: #0b0e14; color:#e6edf3; }
    .navbar { background:#111826; }
    .card { background:#0f1624; border:1px solid #1f2a3a; }
    .form-select, .form-control { background:#0f1624; color:#e6edf3; border-color:#1f2a3a; }
    .btn-primary { background:#2563eb; border-color:#2563eb; }
    .btn-outline-info { border-color:#38bdf8; color:#38bdf8; }
    .btn-outline-info:hover { background:#38bdf8; color:#0b0e14; }
    .kpi { font-size:1.25rem; font-weight:600; }
    .kpi-sub { font-size:.9rem; color:#9aa4b2; }
    .chip { display:inline-block; padding:.3rem .6rem; margin:.15rem; border-radius:999px; border:1px solid #1f2a3a; background:#111826; }
    .sticky-top-lite { position: sticky; top: 0; z-index: 1020; background: #0b0e14; padding-top: .5rem; }
    .note { color:#9aa4b2; font-size:.9rem; }
    .mini-kpi { font-size:1.1rem; font-weight:700; }
    .badge-soft { background:#111826; border:1px solid #1f2a3a; color:#9cc0ff; }
    a { text-decoration:none; }
  </style>
</head>
<body>
<nav class="navbar navbar-dark px-3 mb-4">
  <span class="navbar-brand mb-0 h1">📊 Sales Dashboard</span>
  <div class="ms-auto d-flex gap-2">
    <a class="btn btn-outline-info btn-sm" href="{{ url_for('download_template') }}">Download Excel Template</a>
    <a class="btn btn-secondary btn-sm" href="{{ url_for('logout') }}">Logout</a>
  </div>
</nav>

<div class="container">
  {% if not has_data %}
    <div class="row justify-content-center">
      <div class="col-lg-7">
        <div class="card p-4">
          <div class="d-flex align-items-center mb-2">
            <h4 class="mb-0">Upload Excel (.xlsx)</h4>
            <a class="btn btn-outline-info btn-sm ms-auto" href="{{ url_for('download_template') }}">⬇ Download Template</a>
          </div>
          <form action="/dashboard" method="POST" enctype="multipart/form-data">
            <input class="form-control mb-3" type="file" name="excel_file" accept=".xlsx" required>
            <button class="btn btn-primary w-100">Generate Dashboard</button>
          </form>
          <p class="mt-3 text-secondary small">
            Expected columns (fixed): Customer Name, Age, Country, Product, Purchase Date,
            Purchase Amount, Payment Mode, Category, Selling Price
          </p>
        </div>
      </div>
    </div>
  {% else %}

    <!-- Filters + Actions -->
    <div class="sticky-top-lite">
      <div class="card p-3">
        <div class="row g-3 align-items-end">
          <div class="col-md-2">
            <label class="form-label">Category</label>
            <select id="f_category" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Product</label>
            <select id="f_product" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Age Group</label>
            <select id="f_age" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Country</label>
            <select id="f_country" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Payment</label>
            <select id="f_pay" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Month</label>
            <select id="f_month" class="form-select" multiple></select>
          </div>
          <div class="col-12 d-flex gap-2 mt-2">
            <button class="btn btn-primary" onclick="applyFilters()">Apply Filters (Affects Forecast)</button>
            <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
            <button id="btn_pdf" class="btn btn-outline-info" onclick="downloadPDF()">Download PDF</button>
          </div>
          <div class="text-secondary small mt-1">PDF includes: KPI summary, key insights, and a 30-row preview (charts omitted for compatibility).</div>
        </div>
      </div>
    </div>

    <!-- KPIs -->
    <div class="row g-3 mt-3">
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_turnover">₹0</div><div class="kpi-sub">Total Turnover</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_cost">₹0</div><div class="kpi-sub">Total Cost</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_profit">₹0</div><div class="kpi-sub">Total Profit</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_profit_pct">0%</div><div class="kpi-sub">Profit %</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_customers">0</div><div class="kpi-sub">Total Customers</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_txn">0</div><div class="kpi-sub">Transactions</div></div></div>
    </div>

    <!-- Lists + Tops -->
    <div class="row g-3 mt-1">
      <div class="col-md-4">
        <div class="card p-3">
          <h5 class="mb-3">All Categories / Products / Age Groups</h5>
          <div class="mb-2"><span class="kpi-sub">Categories:</span><div id="list_categories" class="mt-2"></div></div>
          <div class="mb-2"><span class="kpi-sub">Products:</span><div id="list_products" class="mt-2"></div></div>
          <div class="mb-2"><span class="kpi-sub">Age Groups:</span><div id="list_ages" class="mt-2"></div></div>
        </div>
      </div>
      <div class="col-md-8">
        <div class="card p-3">
          <div class="row g-3">
            <div class="col-md-6"><h6>Top Selling Product</h6><div id="top_product" class="kpi"></div></div>
            <div class="col-md-6"><h6>Most Profitable Product</h6><div id="top_profit_product" class="kpi"></div></div>
            <div class="col-md-6"><h6>Most Active Country</h6><div id="top_country" class="kpi"></div></div>
            <div class="col-md-6"><h6>Best Category (Profit)</h6><div id="top_category" class="kpi"></div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Original Charts -->
    <div class="row g-3 mt-1">
      <div class="col-md-6"><div class="card p-3"><h5>Country vs Product Count</h5><div id="chart_country_product"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Category vs Profit</h5><div id="chart_category_profit"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Payment Mode vs Profit</h5><div id="chart_payment_profit"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Month vs Profit</h5><div id="chart_month_profit"></div></div></div>
    </div>

    <!-- New Charts (Requested) -->
    <div class="row g-3 mt-1">
      <div class="col-md-6"><div class="card p-3"><h5>Leading Category (Profit %) — Pie</h5><div id="chart_cat_profit_pct"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Country-wise Sales Share — Pie</h5><div id="chart_country_sales_share"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Category vs Total Sales — Bar</h5><div id="chart_category_sales"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Month vs Sales Trend — Line</h5><div id="chart_month_sales_trend"></div></div></div>
    </div>

    <!-- ===== Forecast (inside same page) ===== -->
    <div class="card p-3 mt-3">
      <div class="d-flex align-items-center gap-2">
        <h5 class="me-auto mb-0">🔮 Forecast</h5>
        <span class="badge badge-soft">Uses current filters</span>
      </div>
      <div class="row g-3 align-items-end mt-1">
        <div class="col-md-2">
          <label class="form-label">Forecast Horizon</label>
          <select id="fc_horizon" class="form-select">
            <option value="1">Next 1 month</option>
            <option value="3" selected>Next 3 months</option>
            <option value="6">Next 6 months</option>
          </select>
        </div>
        <div class="col-md-10 d-flex align-items-end">
          <button class="btn btn-primary ms-auto" onclick="runForecast()">Run Forecast</button>
        </div>
      </div>

      <div class="row g-3 mt-2">
        <div class="col-md-4">
          <div class="card p-3">
            <div class="kpi-sub">Next Month (Predicted Sales)</div>
            <div class="mini-kpi" id="pred_next_month">—</div>
            <div class="note mt-2" id="pred_note">Run forecast to see prediction.</div>
          </div>
        </div>
        <div class="col-md-8">
          <div id="chart_forecast"></div>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="card p-3 mt-3 mb-5">
      <div class="d-flex align-items-center">
        <h5 class="me-auto">All Records (Filtered)</h5>
        <input class="form-control w-auto" placeholder="Search..." oninput="searchTable(this.value)">
      </div>
      <div class="table-responsive mt-3">
        <table class="table table-sm" id="data_table">
          <thead></thead><tbody></tbody>
        </table>
      </div>
    </div>
  {% endif %}
</div>
<!-- Toast container (bottom-right) -->
<style>
  .cg-toast { min-width: 260px; max-width: 420px; background: #0f1624; color: #e6edf3; border:1px solid #1f2a3a; box-shadow: 0 6px 18px rgba(0,0,0,0.6); border-radius:8px; padding:12px; }
  .cg-toast .cg-title { font-weight:700; margin-bottom:6px; }
  .cg-toast .cg-body { font-size:0.95rem; color:#cbd6e4; }
  .cg-spinner { width:18px; height:18px; border:3px solid rgba(255,255,255,0.12); border-top-color: rgba(255,255,255,0.9); border-radius:50%; display:inline-block; vertical-align:middle; margin-right:8px; animation: cg-spin 0.9s linear infinite; }
  @keyframes cg-spin { to { transform: rotate(360deg); } }
</style>

<div id="cg-toast-container" class="position-fixed" style="right:16px; bottom:18px; z-index:10800;"></div>


<script>
{% if has_data %}
  // ===== Data from Flask =====
  const RAW = {{ data_json | safe }};
  const COLS = {
    customer: "Customer Name",
    age: "Age",
    country: "Country",
    product: "Product",
    date: "Purchase Date",
    cost: "{{ cost_col }}",
    pay: "Payment Mode",
    category: "Category",
    sell: "Selling Price",
    profit: "__Profit",
    age_group: "__Age Group",
    month: "__Month"
  };
  let CURRENT = [...RAW];

  // Utilities
  function uniqueSorted(arr){ return [...new Set(arr.filter(x=>x!==null && x!==undefined && x!=="" ))].sort((a,b)=> (a+'').localeCompare(b+'')); }
  function sum(arr, key){ return arr.reduce((s, r)=> s + (+r[key] || 0), 0); }
  function countBy(arr, key){ const m={}; arr.forEach(r=>{const k=r[key]; m[k]=(m[k]||0)+1;}); return m; }
  function sumBy(arr, keyGroup, keyVal){ const m={}; arr.forEach(r=>{const k=r[keyGroup]; const v=+r[keyVal]||0; m[k]=(m[k]||0)+v;}); return m; }
  function fmtINR(n){ if(!isFinite(n)) return "₹0"; return "₹"+Math.round(n).toLocaleString("en-IN"); }

  // Filters
// ✅ Smart Interlinked Filters (Category, Product, Age Group, Country, Payment, Month)

function fillSelect(id, values, preserveSelection=true){
  const el=document.getElementById(id);
  const prev = preserveSelection ? Array.from(el.selectedOptions).map(o=>o.value) : [];
  el.innerHTML="";
  values.forEach(v=>{
    const o=document.createElement("option");
    o.value=v; o.textContent=v;
    if(preserveSelection && prev.includes(v)) o.selected = true;
    el.appendChild(o);
  });
}

function selectedValues(id){
  return Array.from(document.getElementById(id).selectedOptions).map(o=>o.value);
}

function initFilters(){
  // Fill with initial full lists
  updateAllFilters(RAW);

  // Add event listeners to all filter boxes
  ["f_category","f_product","f_age","f_country","f_pay","f_month"].forEach(id=>{
    document.getElementById(id).addEventListener("change", onAnyFilterChange);
  });
}

function onAnyFilterChange(){
  // Filter RAW according to all currently selected filters
  const fc=selectedValues("f_category"), fp=selectedValues("f_product"), fa=selectedValues("f_age"),
        fco=selectedValues("f_country"), fpay=selectedValues("f_pay"), fm=selectedValues("f_month");

  const filtered = RAW.filter(r=>{
    const conds=[];
    if(fc.length)  conds.push(fc.includes(r[COLS.category]));
    if(fp.length)  conds.push(fp.includes(r[COLS.product]));
    if(fa.length)  conds.push(fa.includes(r[COLS.age_group]));
    if(fco.length) conds.push(fco.includes(r[COLS.country]));
    if(fpay.length)conds.push(fpay.includes(r[COLS.pay]));
    if(fm.length)  conds.push(fm.includes(r[COLS.month]));
    return conds.every(Boolean);
  });

  // Update all dropdowns based on filtered dataset
  updateAllFilters(filtered);
}

function updateAllFilters(dataset){
  const monthOrder=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  fillSelect("f_category", uniqueSorted(dataset.map(r=>r[COLS.category])));
  fillSelect("f_product",  uniqueSorted(dataset.map(r=>r[COLS.product])));
  fillSelect("f_age",      uniqueSorted(dataset.map(r=>r[COLS.age_group])));
  fillSelect("f_country",  uniqueSorted(dataset.map(r=>r[COLS.country])));
  fillSelect("f_pay",      uniqueSorted(dataset.map(r=>r[COLS.pay])));
  const um=uniqueSorted(dataset.map(r=>r[COLS.month]));
  fillSelect("f_month", monthOrder.filter(m=>um.includes(m)));
}

function applyFilters(){
  const fc=selectedValues("f_category"), fp=selectedValues("f_product"), fa=selectedValues("f_age"),
        fco=selectedValues("f_country"), fpay=selectedValues("f_pay"), fm=selectedValues("f_month");

  CURRENT = RAW.filter(r=>{
    const conds=[];
    if(fc.length)  conds.push(fc.includes(r[COLS.category]));
    if(fp.length)  conds.push(fp.includes(r[COLS.product]));
    if(fa.length)  conds.push(fa.includes(r[COLS.age_group]));
    if(fco.length) conds.push(fco.includes(r[COLS.country]));
    if(fpay.length)conds.push(fpay.includes(r[COLS.pay]));
    if(fm.length)  conds.push(fm.includes(r[COLS.month]));
    return conds.every(Boolean);
  });

  refreshAll();
}

function resetFilters(){
  ["f_category","f_product","f_age","f_country","f_pay","f_month"].forEach(id=>{
    Array.from(document.getElementById(id).options).forEach(o=>o.selected=false);
  });
  updateAllFilters(RAW);
  CURRENT=[...RAW];
  refreshAll();
}

  // KPIs & Tops
  function refreshKPIs(){
    const turnover=sum(CURRENT, COLS.sell), cost=sum(CURRENT, COLS.cost), profit=sum(CURRENT, COLS.profit);
    const pct = cost>0 ? profit/cost*100 : 0;
    document.getElementById("kpi_turnover").textContent=fmtINR(turnover);
    document.getElementById("kpi_cost").textContent=fmtINR(cost);
    document.getElementById("kpi_profit").textContent=fmtINR(profit);
    document.getElementById("kpi_profit_pct").textContent=pct.toFixed(1)+"%";
    document.getElementById("kpi_customers").textContent=uniqueSorted(CURRENT.map(r=>r[COLS.customer])).length;
    document.getElementById("kpi_txn").textContent=CURRENT.length;
  }
  function chips(id, arr){ const el=document.getElementById(id); el.innerHTML=""; uniqueSorted(arr).forEach(x=>{const s=document.createElement("span"); s.className="chip"; s.textContent=x; el.appendChild(s);}); }
  function refreshTops(){
    const cntProd=countBy(CURRENT, COLS.product); const topProd=Object.entries(cntProd).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_product").textContent = topProd ? `${topProd[0]} (${topProd[1]})` : "—";
    const sumProd=sumBy(CURRENT, COLS.product, COLS.profit); const topProfitProd=Object.entries(sumProd).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_profit_product").textContent = topProfitProd ? `${topProfitProd[0]} (${fmtINR(topProfitProd[1])})` : "—";
    const cntCountry=countBy(CURRENT, COLS.country); const topCountry=Object.entries(cntCountry).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_country").textContent = topCountry ? `${topCountry[0]} (${topCountry[1]})` : "—";
    const sumCat=sumBy(CURRENT, COLS.category, COLS.profit); const topCat=Object.entries(sumCat).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_category").textContent = topCat ? `${topCat[0]} (${fmtINR(topCat[1])})` : "—";
    chips("list_categories", CURRENT.map(r=>r[COLS.category]));
    chips("list_products",  CURRENT.map(r=>r[COLS.product]));
    chips("list_ages",      CURRENT.map(r=>r[COLS.age_group]));
  }

  // Chart helpers
  function drawBar(divId, labels, values){
    Plotly.newPlot(divId,[{x:labels,y:values,type:'bar'}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:20,r:10,b:60,l:50}}, {displayModeBar:false,responsive:true});
  }
  function drawLine(divId, labels, values){
    Plotly.newPlot(divId,[{x:labels,y:values,type:'scatter',mode:'lines+markers'}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:20,r:10,b:60,l:50}}, {displayModeBar:false,responsive:true});
  }
  function drawPie(divId, labels, values){
    Plotly.newPlot(divId,[{labels:labels, values:values, type:'pie', hole:0.3}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:10,b:10}}, {displayModeBar:false,responsive:true});
  }

  function refreshCharts(){
    // Originals
    drawBar("chart_country_product", Object.keys(countBy(CURRENT, COLS.country)), Object.values(countBy(CURRENT, COLS.country)));
    drawBar("chart_category_profit", Object.keys(sumBy(CURRENT, COLS.category, COLS.profit)), Object.values(sumBy(CURRENT, COLS.category, COLS.profit)));
    drawBar("chart_payment_profit",  Object.keys(sumBy(CURRENT, COLS.pay,      COLS.profit)), Object.values(sumBy(CURRENT, COLS.pay,      COLS.profit)));

    const moOrder=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const mProfit=sumBy(CURRENT, COLS.month, COLS.profit);
    const mpLabels=moOrder.filter(m=>m in mProfit);
    drawLine("chart_month_profit", mpLabels, mpLabels.map(m=>mProfit[m]||0));

    // New ones
    const catProfit=sumBy(CURRENT, COLS.category, COLS.profit);
    const cLabels=Object.keys(catProfit), cVals=Object.values(catProfit);
    const cTotal=cVals.reduce((a,b)=>a+b,0)||1;
    const cPctVals=cVals.map(v=> v/cTotal*100);
    drawPie("chart_cat_profit_pct", cLabels, cPctVals);

    const countrySales=sumBy(CURRENT, COLS.country, COLS.sell);
    drawPie("chart_country_sales_share", Object.keys(countrySales), Object.values(countrySales));

    const catSales=sumBy(CURRENT, COLS.category, COLS.sell);
    drawBar("chart_category_sales", Object.keys(catSales), Object.values(catSales));

    const mSales=sumBy(CURRENT, COLS.month, COLS.sell);
    const msLabels=moOrder.filter(m=>m in mSales);
    drawLine("chart_month_sales_trend", msLabels, msLabels.map(m=>mSales[m]||0));
  }

  // Table
  const TABLE_COLS=["Customer Name","Age","Country","Product","Purchase Date","{{ cost_col }}","Payment Mode","Category","Selling Price","__Profit","__Age Group","__Month"];
  function buildTableHead(){ document.querySelector("#data_table thead").innerHTML="<tr>"+TABLE_COLS.map(c=>`<th>${c}</th>`).join("")+"</tr>"; }
  function buildTableBody(rows){
    const tbody=document.querySelector("#data_table tbody");
    const fmt=(k,v)=> (["Selling Price","{{ cost_col }}","__Profit"].includes(k) ? ( "₹"+Math.round(+v||0).toLocaleString("en-IN") ) : v );
    tbody.innerHTML = rows.map(r=>"<tr>"+TABLE_COLS.map(c=>`<td>${fmt(c, r[c]??"")}</td>`).join("")+"</tr>").join("");
  }
  let TABLE_CURRENT=[];
  function refreshTable(){ TABLE_CURRENT=[...CURRENT]; buildTableBody(TABLE_CURRENT); }
  function searchTable(q){ q=(q||"").toLowerCase(); buildTableBody(TABLE_CURRENT.filter(r=> TABLE_COLS.some(c=>(r[c]+"").toLowerCase().includes(q)) )); }

  // CSV + PDF
  function downloadCSV(){
    const cols=TABLE_COLS, rows=CURRENT.map(r=> cols.map(c=> r[c]));
    let csv=cols.join(",")+"\n";
    rows.forEach(r=>{ csv+=r.map(v=>{const s=(v==null)?"":(""+v); return (s.includes(",")||s.includes('"')||s.includes("\n"))?('"'+s.replace(/"/g,'""')+'"'):s }).join(",")+"\n"; });
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8;"}); const url=URL.createObjectURL(blob); const a=document.createElement("a");
    a.href=url; a.download="filtered_data.csv"; a.click(); URL.revokeObjectURL(url);
  }
  // ---------- Toast helpers ----------
function makeToastElement(id, title, message, opts={spinner:false}) {
  const wrap = document.createElement("div");
  wrap.className = "cg-toast mb-2";
  wrap.id = id;
  const titleEl = document.createElement("div");
  titleEl.className = "cg-title";
  titleEl.textContent = title;
  const bodyEl = document.createElement("div");
  bodyEl.className = "cg-body";
  if(opts.spinner) {
    const sp = document.createElement("span");
    sp.className = "cg-spinner";
    bodyEl.appendChild(sp);
  }
  const msgSpan = document.createElement("span");
  msgSpan.className = "cg-msg";
  msgSpan.textContent = message;
  bodyEl.appendChild(msgSpan);
  const row = document.createElement("div");
  row.style.marginTop = "8px";
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.alignItems = "center";
  const status = document.createElement("small");
  status.style.color = "#9aa4b2";
  status.textContent = opts.statusText || "";
  row.appendChild(status);
  const closeBtn = document.createElement("button");
  closeBtn.className = "btn btn-sm";
  closeBtn.style.fontSize = "0.72rem";
  closeBtn.style.padding = "4px 8px";
  closeBtn.style.background = "transparent";
  closeBtn.style.color = "#9aa4b2";
  closeBtn.style.border = "1px solid rgba(255,255,255,0.04)";
  closeBtn.textContent = "Close";
  closeBtn.onclick = () => wrap.remove();
  row.appendChild(closeBtn);
  wrap.appendChild(titleEl);
  wrap.appendChild(bodyEl);
  wrap.appendChild(row);
  return wrap;
}

function showToast({ title="Info", message="", spinner=false, autoHideMs=6000, statusText="" } = {}) {
  const container = document.getElementById("cg-toast-container");
  const id = "cg-toast-" + Math.random().toString(36).slice(2,9);
  const el = makeToastElement(id, title, message, { spinner: spinner, statusText: statusText });
  container.appendChild(el);
  if(autoHideMs > 0) {
    setTimeout(()=> { if(el && el.remove) el.remove(); }, autoHideMs);
  }
  return el;
}

function updateToast(el, { title, message, spinner=false, statusText="", autoHideMs=5000 } = {}) {
  if(!el) return;
  if(title) el.querySelector(".cg-title").textContent = title;
  if(message) el.querySelector(".cg-msg").textContent = message;
  const body = el.querySelector(".cg-body");
  const existingSpinner = body.querySelector(".cg-spinner");
  if(existingSpinner && !spinner) existingSpinner.remove();
  if(!existingSpinner && spinner) {
    const sp = document.createElement("span");
    sp.className = "cg-spinner";
    body.insertBefore(sp, body.firstChild);
  }
  const small = el.querySelector("small");
  if(small) small.textContent = statusText;
  if(autoHideMs > 0) setTimeout(()=>{ try{ el.remove(); }catch(e){} }, autoHideMs);
}

// ---------- Improved downloadPDF ----------
async function downloadPDF(){
  const btn = document.getElementById("btn_pdf");
  try {
    const toastEl = showToast({ title: "Generating report…", message: "Preparing your PDF. This may take a few seconds.", spinner: true, autoHideMs: 0, statusText: "Working" });
    if(btn) { btn.disabled = true; btn.classList.add("disabled"); }

    const payload = { rows: CURRENT, cost_col: "{{ cost_col }}" };
    const resp = await fetch("/download_pdf", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });

    if(!resp.ok){
      updateToast(toastEl, { title: "Failed", message: `Server error (${resp.status}).`, spinner: false, statusText: "Error", autoHideMs: 6000 });
      alert("Failed to generate PDF. Server returned status: " + resp.status);
      return;
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Sales_Report.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    updateToast(toastEl, { title: "Done", message: "Report generated — download started.", spinner: false, statusText: "Completed", autoHideMs: 4000 });
  } catch(err) {
    console.error("PDF generation error:", err);
    showToast({ title: "Error", message: "Could not generate PDF. See console for details.", spinner: false, autoHideMs: 7000, statusText: "Failed" });
  } finally {
    if(btn) { btn.disabled = false; btn.classList.remove("disabled"); }
  }
}


  // ===== Forecast (server-side) =====
  async function runForecast(){
    const horizon = parseInt(document.getElementById("fc_horizon").value || "3");
    const resp = await fetch("/forecast", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ rows: CURRENT, horizon: horizon })
    });
    if(!resp.ok){
      document.getElementById("pred_note").textContent = "Forecast failed.";
      return;
    }
    const data = await resp.json();

    // Update mini card
    document.getElementById("pred_next_month").textContent = fmtINR(data.next_month || 0);
    document.getElementById("pred_note").textContent = data.note || "";

    // Draw chart
    const hist = data.history;   // [{period:'2025-01', sales:123}, ...]
    const fc   = data.forecast;  // same format
    const hx = hist.map(d=>d.period), hy = hist.map(d=>d.sales);
    const fx = fc.map(d=>d.period), fy = fc.map(d=>d.sales);

    Plotly.newPlot("chart_forecast",
      [
        { x:hx, y:hy, type:'scatter', mode:'lines+markers', name:'History' },
        { x:fx, y:fy, type:'scatter', mode:'lines+markers', name:'Forecast', line:{dash:'dash'} }
      ],
      { title:"Sales (Monthly) — History & Forecast",
        paper_bgcolor:'#0f1624', plot_bgcolor:'#0f1624', font:{color:'#e6edf3'},
        margin:{t:40,r:10,b:60,l:50}
      },
      { displayModeBar:false, responsive:true }
    );
  }

  // Init
  function refreshAll(){ refreshKPIs(); refreshTops(); refreshCharts(); refreshTable(); }
  initFilters(); buildTableHead(); refreshAll();

  // (Optional) auto-run forecast once on load
  runForecast();
{% endif %}
</script>
</body>
</html>
"""

# -------------------- Helpers --------------------
def ensure_users_csv():
    """Create a default users.csv if missing."""
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "password"])
            writer.writerow(["admin@example.com", "1234"])

def check_credentials(email: str, password: str) -> bool:
    if not os.path.exists(USERS_CSV):
        ensure_users_csv()
    try:
        df = pd.read_csv(USERS_CSV, dtype=str).fillna("")
    except Exception:
        return False
    row = df[(df["email"] == email) & (df["password"] == password)]
    return not row.empty

def _age_group(age):
    try:
        a = float(age)
    except Exception:
        return "Unknown"
    if a <= 18: return "Teen"
    if a <= 25: return "Youth"
    if a <= 40: return "Adult"
    if a <= 60: return "Middle"
    return "Senior"

def _month_short(val):
    try:
        return pd.to_datetime(val).strftime("%b")
    except Exception:
        return ""

def _prepare_dataframe(df):
    # Accept 'Purchase Amount' or common typo 'Purschase Amount'
    cost_col = "Purchase Amount" if "Purchase Amount" in df.columns else ("Purschase Amount" if "Purschase Amount" in df.columns else None)
    if cost_col is None:
        raise ValueError("Excel must include 'Purchase Amount' (or the common typo 'Purschase Amount').")

    df["Selling Price"] = pd.to_numeric(df.get("Selling Price", 0), errors="coerce").fillna(0)
    df[cost_col] = pd.to_numeric(df.get(cost_col, 0), errors="coerce").fillna(0)

    # Derived columns
    df["__Profit"] = df["Selling Price"] - df[cost_col]
    df["__Age Group"] = df["Age"].apply(_age_group)
    df["__Month"] = df["Purchase Date"].apply(_month_short)

    keep = ["Customer Name","Age","Country","Product","Purchase Date",cost_col,"Payment Mode","Category","Selling Price","__Profit","__Age Group","__Month"]
    for c in keep:
        if c not in df.columns:
            df[c] = None
    out = df[keep].copy()
    out["Purchase Date"] = pd.to_datetime(out["Purchase Date"], errors="coerce").dt.date.astype(str)
    return out, cost_col

# -------------------- Auth Routes --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_users_csv()
    if request.method == "GET":
        return render_template_string(LOGIN_HTML)
    # POST
    email = (request.form.get("email") or "").strip()
    password = (request.form.get("password") or "").strip()
    if check_credentials(email, password):
        session["user"] = email
        return redirect(url_for("home"))
    flash("Invalid email or password.")
    return render_template_string(LOGIN_HTML)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# -------------------- Template Download --------------------
@app.route("/download_template")
def download_template():
    # Generate Excel template in-memory
    cols = [
        "Customer Name","Age","Country","Product","Purchase Date",
        "Purchase Amount","Payment Mode","Category","Selling Price"
    ]
    example_row = {
        "Customer Name": "Rahul Sharma",
        "Age": 28,
        "Country": "India",
        "Product": "Smartphone",
        "Purchase Date": datetime.now().strftime("%Y-%m-%d"),
        "Purchase Amount": 18000,
        "Payment Mode": "UPI",
        "Category": "Electronics",
        "Selling Price": 22000
    }
    df = pd.DataFrame([example_row], columns=cols)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="sales_template.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# -------------------- Dashboard Routes --------------------
@app.route("/", methods=["GET"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template_string(HTML, has_data=False)

@app.route("/dashboard", methods=["POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    file = request.files.get("excel_file")
    if not file:
        return render_template_string(HTML, has_data=False)

    df = pd.read_excel(file)
    df_view, cost_col = _prepare_dataframe(df)
    data_json = df_view.to_dict(orient="records")

    return render_template_string(
        HTML,
        has_data=True,
        data_json=json.dumps(data_json, default=str),
        cost_col=cost_col
    )

# -------------------- Forecast API --------------------
@app.route("/forecast", methods=["POST"])
def forecast():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", [])
    horizon = int(payload.get("horizon", 3))

    if horizon < 1: horizon = 1
    if horizon > 12: horizon = 12

    if not rows:
        return jsonify({"history": [], "forecast": [], "next_month": 0, "note": "No data to forecast."}), 200

    df = pd.DataFrame(rows)
    # Parse dates, force to month start
    df["Purchase Date"] = pd.to_datetime(df["Purchase Date"], errors="coerce")
    df = df.dropna(subset=["Purchase Date"])
    df["Selling Price"] = pd.to_numeric(df["Selling Price"], errors="coerce").fillna(0)

    if df.empty:
        return jsonify({"history": [], "forecast": [], "next_month": 0, "note": "No valid dates/sales."}), 200

    df["month"] = df["Purchase Date"].values.astype("datetime64[M]")

    monthly = df.groupby("month")["Selling Price"].sum().sort_index()
    n = len(monthly)

    note = ""
    if n < 3:
        note = "Very little history. Forecast may be naive."

    history = [{"period": dt.strftime("%Y-%m"), "sales": float(v)} for dt, v in monthly.items()]

    if n == 0:
        fcast = []
        next_val = 0.0
    else:
        t = np.arange(n, dtype=float)
        y = monthly.values.astype(float)
        if n >= 3 and np.isfinite(y).all():
            # y = a + b*t  (np.polyfit returns [b, a])
            b, a = np.polyfit(t, y, 1)
            last_t = t[-1]
            fvals = []
            for h in range(1, horizon+1):
                val = a + b * (last_t + h)
                if not np.isfinite(val): val = y[-1]
                fvals.append(max(0.0, float(val)))
        else:
            fvals = [float(y[-1])] * horizon

        last_month = monthly.index[-1]
        f_dates = [(last_month + pd.offsets.MonthBegin(h)) for h in range(1, horizon+1)]
        fcast = [{"period": d.strftime("%Y-%m"), "sales": float(v)} for d, v in zip(f_dates, fvals)]
        next_val = fvals[0] if fvals else 0.0

    return jsonify({
        "history": history,
        "forecast": fcast,
        "next_month": round(next_val, 2),
        "note": note
    }), 200

# -------------------- PDF (No Matplotlib) --------------------
# app.py

from flask import Flask, request, render_template_string, send_file, jsonify, redirect, url_for, session, flash
import pandas as pd
import numpy as np
import io, json, tempfile, os, csv
from datetime import datetime

# For PDF export (no matplotlib)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

app = Flask(__name__)
app.secret_key = "replace-with-a-strong-secret-key"  # required for sessions

USERS_CSV = "users.csv"

# -------------------- Login HTML --------------------
LOGIN_HTML = r"""
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login | Sales Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background:#0b0e14; color:#e6edf3; }
    .card { background:#0f1624; border:1px solid #1f2a3a; }
    .form-control { background:#0f1624; color:#e6edf3; border-color:#1f2a3a; }
    .btn-primary { background:#2563eb; border-color:#2563eb; }
  </style>
</head>
<body>
  <div class="container py-5">
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card p-4">
          <h4 class="mb-3 text-center">🔐 Login</h4>
          {% with messages = get_flashed_messages() %}
            {% if messages %}
              <div class="alert alert-danger py-2">{{ messages[0] }}</div>
            {% endif %}
          {% endwith %}
          <form method="POST" action="{{ url_for('login') }}">
            <div class="mb-3">
              <label class="form-label">Email</label>
              <input name="email" type="email" class="form-control" placeholder="admin@example.com" required>
            </div>
            <div class="mb-3">
              <label class="form-label">Password</label>
              <input name="password" type="password" class="form-control" placeholder="••••" required>
            </div>
            <button class="btn btn-primary w-100">Login</button>
          </form>
          <p class="text-secondary small mt-3">
            Default user (auto-created if missing): <code>admin@example.com / 1234</code>
          </p>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

# -------------------- Dashboard HTML --------------------
HTML = r"""
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sales Dashboard (Dark)</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { background: #0b0e14; color:#e6edf3; }
    .navbar { background:#111826; }
    .card { background:#0f1624; border:1px solid #1f2a3a; }
    .form-select, .form-control { background:#0f1624; color:#e6edf3; border-color:#1f2a3a; }
    .btn-primary { background:#2563eb; border-color:#2563eb; }
    .btn-outline-info { border-color:#38bdf8; color:#38bdf8; }
    .btn-outline-info:hover { background:#38bdf8; color:#0b0e14; }
    .kpi { font-size:1.25rem; font-weight:600; }
    .kpi-sub { font-size:.9rem; color:#9aa4b2; }
    .chip { display:inline-block; padding:.3rem .6rem; margin:.15rem; border-radius:999px; border:1px solid #1f2a3a; background:#111826; }
    .sticky-top-lite { position: sticky; top: 0; z-index: 1020; background: #0b0e14; padding-top: .5rem; }
    .note { color:#9aa4b2; font-size:.9rem; }
    .mini-kpi { font-size:1.1rem; font-weight:700; }
    .badge-soft { background:#111826; border:1px solid #1f2a3a; color:#9cc0ff; }
    a { text-decoration:none; }
  </style>
</head>
<body>
<nav class="navbar navbar-dark px-3 mb-4">
  <span class="navbar-brand mb-0 h1">📊 Sales Dashboard</span>
  <div class="ms-auto d-flex gap-2">
    <a class="btn btn-outline-info btn-sm" href="{{ url_for('download_template') }}">Download Excel Template</a>
    <a class="btn btn-secondary btn-sm" href="{{ url_for('logout') }}">Logout</a>
  </div>
</nav>

<div class="container">
  {% if not has_data %}
    <div class="row justify-content-center">
      <div class="col-lg-7">
        <div class="card p-4">
          <div class="d-flex align-items-center mb-2">
            <h4 class="mb-0">Upload Excel (.xlsx)</h4>
            <a class="btn btn-outline-info btn-sm ms-auto" href="{{ url_for('download_template') }}">⬇ Download Template</a>
          </div>
          <form action="/dashboard" method="POST" enctype="multipart/form-data">
            <input class="form-control mb-3" type="file" name="excel_file" accept=".xlsx" required>
            <button class="btn btn-primary w-100">Generate Dashboard</button>
          </form>
          <p class="mt-3 text-secondary small">
            Expected columns (fixed): Customer Name, Age, Country, Product, Purchase Date,
            Purchase Amount, Payment Mode, Category, Selling Price
          </p>
        </div>
      </div>
    </div>
  {% else %}

    <!-- Filters + Actions -->
    <div class="sticky-top-lite">
      <div class="card p-3">
        <div class="row g-3 align-items-end">
          <div class="col-md-2">
            <label class="form-label">Category</label>
            <select id="f_category" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Product</label>
            <select id="f_product" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Age Group</label>
            <select id="f_age" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Country</label>
            <select id="f_country" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Payment</label>
            <select id="f_pay" class="form-select" multiple></select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Month</label>
            <select id="f_month" class="form-select" multiple></select>
          </div>
          <div class="col-12 d-flex gap-2 mt-2">
            <button class="btn btn-primary" onclick="applyFilters()">Apply Filters (Affects Forecast)</button>
            <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
            <button id="btn_pdf" class="btn btn-outline-info" onclick="downloadPDF()">Download PDF</button>
          </div>
          <div class="text-secondary small mt-1">PDF includes: KPI summary, key insights, and a 30-row preview (charts omitted for compatibility).</div>
        </div>
      </div>
    </div>

    <!-- KPIs -->
    <div class="row g-3 mt-3">
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_turnover">₹0</div><div class="kpi-sub">Total Turnover</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_cost">₹0</div><div class="kpi-sub">Total Cost</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_profit">₹0</div><div class="kpi-sub">Total Profit</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_profit_pct">0%</div><div class="kpi-sub">Profit %</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_customers">0</div><div class="kpi-sub">Total Customers</div></div></div>
      <div class="col-md-2"><div class="card p-3"><div class="kpi" id="kpi_txn">0</div><div class="kpi-sub">Transactions</div></div></div>
    </div>

    <!-- Lists + Tops -->
    <div class="row g-3 mt-1">
      <div class="col-md-4">
        <div class="card p-3">
          <h5 class="mb-3">All Categories / Products / Age Groups</h5>
          <div class="mb-2"><span class="kpi-sub">Categories:</span><div id="list_categories" class="mt-2"></div></div>
          <div class="mb-2"><span class="kpi-sub">Products:</span><div id="list_products" class="mt-2"></div></div>
          <div class="mb-2"><span class="kpi-sub">Age Groups:</span><div id="list_ages" class="mt-2"></div></div>
        </div>
      </div>
      <div class="col-md-8">
        <div class="card p-3">
          <div class="row g-3">
            <div class="col-md-6"><h6>Top Selling Product</h6><div id="top_product" class="kpi"></div></div>
            <div class="col-md-6"><h6>Most Profitable Product</h6><div id="top_profit_product" class="kpi"></div></div>
            <div class="col-md-6"><h6>Most Active Country</h6><div id="top_country" class="kpi"></div></div>
            <div class="col-md-6"><h6>Best Category (Profit)</h6><div id="top_category" class="kpi"></div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Original Charts -->
    <div class="row g-3 mt-1">
      <div class="col-md-6"><div class="card p-3"><h5>Country vs Product Count</h5><div id="chart_country_product"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Category vs Profit</h5><div id="chart_category_profit"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Payment Mode vs Profit</h5><div id="chart_payment_profit"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Month vs Profit</h5><div id="chart_month_profit"></div></div></div>
    </div>

    <!-- New Charts (Requested) -->
    <div class="row g-3 mt-1">
      <div class="col-md-6"><div class="card p-3"><h5>Leading Category (Profit %) — Pie</h5><div id="chart_cat_profit_pct"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Country-wise Sales Share — Pie</h5><div id="chart_country_sales_share"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Category vs Total Sales — Bar</h5><div id="chart_category_sales"></div></div></div>
      <div class="col-md-6"><div class="card p-3"><h5>Month vs Sales Trend — Line</h5><div id="chart_month_sales_trend"></div></div></div>
    </div>

    <!-- ===== Forecast (inside same page) ===== -->
    <div class="card p-3 mt-3">
      <div class="d-flex align-items-center gap-2">
        <h5 class="me-auto mb-0">🔮 Forecast</h5>
        <span class="badge badge-soft">Uses current filters</span>
      </div>
      <div class="row g-3 align-items-end mt-1">
        <div class="col-md-2">
          <label class="form-label">Forecast Horizon</label>
          <select id="fc_horizon" class="form-select">
            <option value="1">Next 1 month</option>
            <option value="3" selected>Next 3 months</option>
            <option value="6">Next 6 months</option>
          </select>
        </div>
        <div class="col-md-10 d-flex align-items-end">
          <button class="btn btn-primary ms-auto" onclick="runForecast()">Run Forecast</button>
        </div>
      </div>

      <div class="row g-3 mt-2">
        <div class="col-md-4">
          <div class="card p-3">
            <div class="kpi-sub">Next Month (Predicted Sales)</div>
            <div class="mini-kpi" id="pred_next_month">—</div>
            <div class="note mt-2" id="pred_note">Run forecast to see prediction.</div>
          </div>
        </div>
        <div class="col-md-8">
          <div id="chart_forecast"></div>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="card p-3 mt-3 mb-5">
      <div class="d-flex align-items-center">
        <h5 class="me-auto">All Records (Filtered)</h5>
        <input class="form-control w-auto" placeholder="Search..." oninput="searchTable(this.value)">
      </div>
      <div class="table-responsive mt-3">
        <table class="table table-sm" id="data_table">
          <thead></thead><tbody></tbody>
        </table>
      </div>
    </div>
  {% endif %}
</div>
<!-- Toast container (bottom-right) -->
<style>
  .cg-toast { min-width: 260px; max-width: 420px; background: #0f1624; color: #e6edf3; border:1px solid #1f2a3a; box-shadow: 0 6px 18px rgba(0,0,0,0.6); border-radius:8px; padding:12px; }
  .cg-toast .cg-title { font-weight:700; margin-bottom:6px; }
  .cg-toast .cg-body { font-size:0.95rem; color:#cbd6e4; }
  .cg-spinner { width:18px; height:18px; border:3px solid rgba(255,255,255,0.12); border-top-color: rgba(255,255,255,0.9); border-radius:50%; display:inline-block; vertical-align:middle; margin-right:8px; animation: cg-spin 0.9s linear infinite; }
  @keyframes cg-spin { to { transform: rotate(360deg); } }
</style>

<div id="cg-toast-container" class="position-fixed" style="right:16px; bottom:18px; z-index:10800;"></div>


<script>
{% if has_data %}
  // ===== Data from Flask =====
  const RAW = {{ data_json | safe }};
  const COLS = {
    customer: "Customer Name",
    age: "Age",
    country: "Country",
    product: "Product",
    date: "Purchase Date",
    cost: "{{ cost_col }}",
    pay: "Payment Mode",
    category: "Category",
    sell: "Selling Price",
    profit: "__Profit",
    age_group: "__Age Group",
    month: "__Month"
  };
  let CURRENT = [...RAW];

  // Utilities
  function uniqueSorted(arr){ return [...new Set(arr.filter(x=>x!==null && x!==undefined && x!=="" ))].sort((a,b)=> (a+'').localeCompare(b+'')); }
  function sum(arr, key){ return arr.reduce((s, r)=> s + (+r[key] || 0), 0); }
  function countBy(arr, key){ const m={}; arr.forEach(r=>{const k=r[key]; m[k]=(m[k]||0)+1;}); return m; }
  function sumBy(arr, keyGroup, keyVal){ const m={}; arr.forEach(r=>{const k=r[keyGroup]; const v=+r[keyVal]||0; m[k]=(m[k]||0)+v;}); return m; }
  function fmtINR(n){ if(!isFinite(n)) return "₹0"; return "₹"+Math.round(n).toLocaleString("en-IN"); }

  // Filters
// ✅ Smart Interlinked Filters (Category, Product, Age Group, Country, Payment, Month)

function fillSelect(id, values, preserveSelection=true){
  const el=document.getElementById(id);
  const prev = preserveSelection ? Array.from(el.selectedOptions).map(o=>o.value) : [];
  el.innerHTML="";
  values.forEach(v=>{
    const o=document.createElement("option");
    o.value=v; o.textContent=v;
    if(preserveSelection && prev.includes(v)) o.selected = true;
    el.appendChild(o);
  });
}

function selectedValues(id){
  return Array.from(document.getElementById(id).selectedOptions).map(o=>o.value);
}

function initFilters(){
  // Fill with initial full lists
  updateAllFilters(RAW);

  // Add event listeners to all filter boxes
  ["f_category","f_product","f_age","f_country","f_pay","f_month"].forEach(id=>{
    document.getElementById(id).addEventListener("change", onAnyFilterChange);
  });
}

function onAnyFilterChange(){
  // Filter RAW according to all currently selected filters
  const fc=selectedValues("f_category"), fp=selectedValues("f_product"), fa=selectedValues("f_age"),
        fco=selectedValues("f_country"), fpay=selectedValues("f_pay"), fm=selectedValues("f_month");

  const filtered = RAW.filter(r=>{
    const conds=[];
    if(fc.length)  conds.push(fc.includes(r[COLS.category]));
    if(fp.length)  conds.push(fp.includes(r[COLS.product]));
    if(fa.length)  conds.push(fa.includes(r[COLS.age_group]));
    if(fco.length) conds.push(fco.includes(r[COLS.country]));
    if(fpay.length)conds.push(fpay.includes(r[COLS.pay]));
    if(fm.length)  conds.push(fm.includes(r[COLS.month]));
    return conds.every(Boolean);
  });

  // Update all dropdowns based on filtered dataset
  updateAllFilters(filtered);
}

function updateAllFilters(dataset){
  const monthOrder=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  fillSelect("f_category", uniqueSorted(dataset.map(r=>r[COLS.category])));
  fillSelect("f_product",  uniqueSorted(dataset.map(r=>r[COLS.product])));
  fillSelect("f_age",      uniqueSorted(dataset.map(r=>r[COLS.age_group])));
  fillSelect("f_country",  uniqueSorted(dataset.map(r=>r[COLS.country])));
  fillSelect("f_pay",      uniqueSorted(dataset.map(r=>r[COLS.pay])));
  const um=uniqueSorted(dataset.map(r=>r[COLS.month]));
  fillSelect("f_month", monthOrder.filter(m=>um.includes(m)));
}

function applyFilters(){
  const fc=selectedValues("f_category"), fp=selectedValues("f_product"), fa=selectedValues("f_age"),
        fco=selectedValues("f_country"), fpay=selectedValues("f_pay"), fm=selectedValues("f_month");

  CURRENT = RAW.filter(r=>{
    const conds=[];
    if(fc.length)  conds.push(fc.includes(r[COLS.category]));
    if(fp.length)  conds.push(fp.includes(r[COLS.product]));
    if(fa.length)  conds.push(fa.includes(r[COLS.age_group]));
    if(fco.length) conds.push(fco.includes(r[COLS.country]));
    if(fpay.length)conds.push(fpay.includes(r[COLS.pay]));
    if(fm.length)  conds.push(fm.includes(r[COLS.month]));
    return conds.every(Boolean);
  });

  refreshAll();
}

function resetFilters(){
  ["f_category","f_product","f_age","f_country","f_pay","f_month"].forEach(id=>{
    Array.from(document.getElementById(id).options).forEach(o=>o.selected=false);
  });
  updateAllFilters(RAW);
  CURRENT=[...RAW];
  refreshAll();
}

  // KPIs & Tops
  function refreshKPIs(){
    const turnover=sum(CURRENT, COLS.sell), cost=sum(CURRENT, COLS.cost), profit=sum(CURRENT, COLS.profit);
    const pct = cost>0 ? profit/cost*100 : 0;
    document.getElementById("kpi_turnover").textContent=fmtINR(turnover);
    document.getElementById("kpi_cost").textContent=fmtINR(cost);
    document.getElementById("kpi_profit").textContent=fmtINR(profit);
    document.getElementById("kpi_profit_pct").textContent=pct.toFixed(1)+"%";
    document.getElementById("kpi_customers").textContent=uniqueSorted(CURRENT.map(r=>r[COLS.customer])).length;
    document.getElementById("kpi_txn").textContent=CURRENT.length;
  }
  function chips(id, arr){ const el=document.getElementById(id); el.innerHTML=""; uniqueSorted(arr).forEach(x=>{const s=document.createElement("span"); s.className="chip"; s.textContent=x; el.appendChild(s);}); }
  function refreshTops(){
    const cntProd=countBy(CURRENT, COLS.product); const topProd=Object.entries(cntProd).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_product").textContent = topProd ? `${topProd[0]} (${topProd[1]})` : "—";
    const sumProd=sumBy(CURRENT, COLS.product, COLS.profit); const topProfitProd=Object.entries(sumProd).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_profit_product").textContent = topProfitProd ? `${topProfitProd[0]} (${fmtINR(topProfitProd[1])})` : "—";
    const cntCountry=countBy(CURRENT, COLS.country); const topCountry=Object.entries(cntCountry).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_country").textContent = topCountry ? `${topCountry[0]} (${topCountry[1]})` : "—";
    const sumCat=sumBy(CURRENT, COLS.category, COLS.profit); const topCat=Object.entries(sumCat).sort((a,b)=>b[1]-a[1])[0];
    document.getElementById("top_category").textContent = topCat ? `${topCat[0]} (${fmtINR(topCat[1])})` : "—";
    chips("list_categories", CURRENT.map(r=>r[COLS.category]));
    chips("list_products",  CURRENT.map(r=>r[COLS.product]));
    chips("list_ages",      CURRENT.map(r=>r[COLS.age_group]));
  }

  // Chart helpers
  function drawBar(divId, labels, values){
    Plotly.newPlot(divId,[{x:labels,y:values,type:'bar'}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:20,r:10,b:60,l:50}}, {displayModeBar:false,responsive:true});
  }
  function drawLine(divId, labels, values){
    Plotly.newPlot(divId,[{x:labels,y:values,type:'scatter',mode:'lines+markers'}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:20,r:10,b:60,l:50}}, {displayModeBar:false,responsive:true});
  }
  function drawPie(divId, labels, values){
    Plotly.newPlot(divId,[{labels:labels, values:values, type:'pie', hole:0.3}],
      {paper_bgcolor:'#0f1624',plot_bgcolor:'#0f1624',font:{color:'#e6edf3'},margin:{t:10,b:10}}, {displayModeBar:false,responsive:true});
  }

  function refreshCharts(){
    // Originals
    drawBar("chart_country_product", Object.keys(countBy(CURRENT, COLS.country)), Object.values(countBy(CURRENT, COLS.country)));
    drawBar("chart_category_profit", Object.keys(sumBy(CURRENT, COLS.category, COLS.profit)), Object.values(sumBy(CURRENT, COLS.category, COLS.profit)));
    drawBar("chart_payment_profit",  Object.keys(sumBy(CURRENT, COLS.pay,      COLS.profit)), Object.values(sumBy(CURRENT, COLS.pay,      COLS.profit)));

    const moOrder=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const mProfit=sumBy(CURRENT, COLS.month, COLS.profit);
    const mpLabels=moOrder.filter(m=>m in mProfit);
    drawLine("chart_month_profit", mpLabels, mpLabels.map(m=>mProfit[m]||0));

    // New ones
    const catProfit=sumBy(CURRENT, COLS.category, COLS.profit);
    const cLabels=Object.keys(catProfit), cVals=Object.values(catProfit);
    const cTotal=cVals.reduce((a,b)=>a+b,0)||1;
    const cPctVals=cVals.map(v=> v/cTotal*100);
    drawPie("chart_cat_profit_pct", cLabels, cPctVals);

    const countrySales=sumBy(CURRENT, COLS.country, COLS.sell);
    drawPie("chart_country_sales_share", Object.keys(countrySales), Object.values(countrySales));

    const catSales=sumBy(CURRENT, COLS.category, COLS.sell);
    drawBar("chart_category_sales", Object.keys(catSales), Object.values(catSales));

    const mSales=sumBy(CURRENT, COLS.month, COLS.sell);
    const msLabels=moOrder.filter(m=>m in mSales);
    drawLine("chart_month_sales_trend", msLabels, msLabels.map(m=>mSales[m]||0));
  }

  // Table
  const TABLE_COLS=["Customer Name","Age","Country","Product","Purchase Date","{{ cost_col }}","Payment Mode","Category","Selling Price","__Profit","__Age Group","__Month"];
  function buildTableHead(){ document.querySelector("#data_table thead").innerHTML="<tr>"+TABLE_COLS.map(c=>`<th>${c}</th>`).join("")+"</tr>"; }
  function buildTableBody(rows){
    const tbody=document.querySelector("#data_table tbody");
    const fmt=(k,v)=> (["Selling Price","{{ cost_col }}","__Profit"].includes(k) ? ( "₹"+Math.round(+v||0).toLocaleString("en-IN") ) : v );
    tbody.innerHTML = rows.map(r=>"<tr>"+TABLE_COLS.map(c=>`<td>${fmt(c, r[c]??"")}</td>`).join("")+"</tr>").join("");
  }
  let TABLE_CURRENT=[];
  function refreshTable(){ TABLE_CURRENT=[...CURRENT]; buildTableBody(TABLE_CURRENT); }
  function searchTable(q){ q=(q||"").toLowerCase(); buildTableBody(TABLE_CURRENT.filter(r=> TABLE_COLS.some(c=>(r[c]+"").toLowerCase().includes(q)) )); }

  // CSV + PDF
  function downloadCSV(){
    const cols=TABLE_COLS, rows=CURRENT.map(r=> cols.map(c=> r[c]));
    let csv=cols.join(",")+"\n";
    rows.forEach(r=>{ csv+=r.map(v=>{const s=(v==null)?"":(""+v); return (s.includes(",")||s.includes('"')||s.includes("\n"))?('"'+s.replace(/"/g,'""')+'"'):s }).join(",")+"\n"; });
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8;"}); const url=URL.createObjectURL(blob); const a=document.createElement("a");
    a.href=url; a.download="filtered_data.csv"; a.click(); URL.revokeObjectURL(url);
  }
  // ---------- Toast helpers ----------
function makeToastElement(id, title, message, opts={spinner:false}) {
  const wrap = document.createElement("div");
  wrap.className = "cg-toast mb-2";
  wrap.id = id;
  const titleEl = document.createElement("div");
  titleEl.className = "cg-title";
  titleEl.textContent = title;
  const bodyEl = document.createElement("div");
  bodyEl.className = "cg-body";
  if(opts.spinner) {
    const sp = document.createElement("span");
    sp.className = "cg-spinner";
    bodyEl.appendChild(sp);
  }
  const msgSpan = document.createElement("span");
  msgSpan.className = "cg-msg";
  msgSpan.textContent = message;
  bodyEl.appendChild(msgSpan);
  const row = document.createElement("div");
  row.style.marginTop = "8px";
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.alignItems = "center";
  const status = document.createElement("small");
  status.style.color = "#9aa4b2";
  status.textContent = opts.statusText || "";
  row.appendChild(status);
  const closeBtn = document.createElement("button");
  closeBtn.className = "btn btn-sm";
  closeBtn.style.fontSize = "0.72rem";
  closeBtn.style.padding = "4px 8px";
  closeBtn.style.background = "transparent";
  closeBtn.style.color = "#9aa4b2";
  closeBtn.style.border = "1px solid rgba(255,255,255,0.04)";
  closeBtn.textContent = "Close";
  closeBtn.onclick = () => wrap.remove();
  row.appendChild(closeBtn);
  wrap.appendChild(titleEl);
  wrap.appendChild(bodyEl);
  wrap.appendChild(row);
  return wrap;
}

function showToast({ title="Info", message="", spinner=false, autoHideMs=6000, statusText="" } = {}) {
  const container = document.getElementById("cg-toast-container");
  const id = "cg-toast-" + Math.random().toString(36).slice(2,9);
  const el = makeToastElement(id, title, message, { spinner: spinner, statusText: statusText });
  container.appendChild(el);
  if(autoHideMs > 0) {
    setTimeout(()=> { if(el && el.remove) el.remove(); }, autoHideMs);
  }
  return el;
}

function updateToast(el, { title, message, spinner=false, statusText="", autoHideMs=5000 } = {}) {
  if(!el) return;
  if(title) el.querySelector(".cg-title").textContent = title;
  if(message) el.querySelector(".cg-msg").textContent = message;
  const body = el.querySelector(".cg-body");
  const existingSpinner = body.querySelector(".cg-spinner");
  if(existingSpinner && !spinner) existingSpinner.remove();
  if(!existingSpinner && spinner) {
    const sp = document.createElement("span");
    sp.className = "cg-spinner";
    body.insertBefore(sp, body.firstChild);
  }
  const small = el.querySelector("small");
  if(small) small.textContent = statusText;
  if(autoHideMs > 0) setTimeout(()=>{ try{ el.remove(); }catch(e){} }, autoHideMs);
}

// ---------- Improved downloadPDF ----------
async function downloadPDF(){
  const btn = document.getElementById("btn_pdf");
  try {
    const toastEl = showToast({ title: "Generating report…", message: "Preparing your PDF. This may take a few seconds.", spinner: true, autoHideMs: 0, statusText: "Working" });
    if(btn) { btn.disabled = true; btn.classList.add("disabled"); }

    const payload = { rows: CURRENT, cost_col: "{{ cost_col }}" };
    const resp = await fetch("/download_pdf", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });

    if(!resp.ok){
      updateToast(toastEl, { title: "Failed", message: `Server error (${resp.status}).`, spinner: false, statusText: "Error", autoHideMs: 6000 });
      alert("Failed to generate PDF. Server returned status: " + resp.status);
      return;
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Sales_Report.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    updateToast(toastEl, { title: "Done", message: "Report generated — download started.", spinner: false, statusText: "Completed", autoHideMs: 4000 });
  } catch(err) {
    console.error("PDF generation error:", err);
    showToast({ title: "Error", message: "Could not generate PDF. See console for details.", spinner: false, autoHideMs: 7000, statusText: "Failed" });
  } finally {
    if(btn) { btn.disabled = false; btn.classList.remove("disabled"); }
  }
}


  // ===== Forecast (server-side) =====
  async function runForecast(){
    const horizon = parseInt(document.getElementById("fc_horizon").value || "3");
    const resp = await fetch("/forecast", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ rows: CURRENT, horizon: horizon })
    });
    if(!resp.ok){
      document.getElementById("pred_note").textContent = "Forecast failed.";
      return;
    }
    const data = await resp.json();

    // Update mini card
    document.getElementById("pred_next_month").textContent = fmtINR(data.next_month || 0);
    document.getElementById("pred_note").textContent = data.note || "";

    // Draw chart
    const hist = data.history;   // [{period:'2025-01', sales:123}, ...]
    const fc   = data.forecast;  // same format
    const hx = hist.map(d=>d.period), hy = hist.map(d=>d.sales);
    const fx = fc.map(d=>d.period), fy = fc.map(d=>d.sales);

    Plotly.newPlot("chart_forecast",
      [
        { x:hx, y:hy, type:'scatter', mode:'lines+markers', name:'History' },
        { x:fx, y:fy, type:'scatter', mode:'lines+markers', name:'Forecast', line:{dash:'dash'} }
      ],
      { title:"Sales (Monthly) — History & Forecast",
        paper_bgcolor:'#0f1624', plot_bgcolor:'#0f1624', font:{color:'#e6edf3'},
        margin:{t:40,r:10,b:60,l:50}
      },
      { displayModeBar:false, responsive:true }
    );
  }

  // Init
  function refreshAll(){ refreshKPIs(); refreshTops(); refreshCharts(); refreshTable(); }
  initFilters(); buildTableHead(); refreshAll();

  // (Optional) auto-run forecast once on load
  runForecast();
{% endif %}
</script>
</body>
</html>
"""

# -------------------- Helpers --------------------
def ensure_users_csv():
    """Create a default users.csv if missing."""
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "password"])
            writer.writerow(["admin@example.com", "1234"])

def check_credentials(email: str, password: str) -> bool:
    if not os.path.exists(USERS_CSV):
        ensure_users_csv()
    try:
        df = pd.read_csv(USERS_CSV, dtype=str).fillna("")
    except Exception:
        return False
    row = df[(df["email"] == email) & (df["password"] == password)]
    return not row.empty

def _age_group(age):
    try:
        a = float(age)
    except Exception:
        return "Unknown"
    if a <= 18: return "Teen"
    if a <= 25: return "Youth"
    if a <= 40: return "Adult"
    if a <= 60: return "Middle"
    return "Senior"

def _month_short(val):
    try:
        return pd.to_datetime(val).strftime("%b")
    except Exception:
        return ""

def _prepare_dataframe(df):
    # Accept 'Purchase Amount' or common typo 'Purschase Amount'
    cost_col = "Purchase Amount" if "Purchase Amount" in df.columns else ("Purschase Amount" if "Purschase Amount" in df.columns else None)
    if cost_col is None:
        raise ValueError("Excel must include 'Purchase Amount' (or the common typo 'Purschase Amount').")

    df["Selling Price"] = pd.to_numeric(df.get("Selling Price", 0), errors="coerce").fillna(0)
    df[cost_col] = pd.to_numeric(df.get(cost_col, 0), errors="coerce").fillna(0)

    # Derived columns
    df["__Profit"] = df["Selling Price"] - df[cost_col]
    df["__Age Group"] = df["Age"].apply(_age_group)
    df["__Month"] = df["Purchase Date"].apply(_month_short)

    keep = ["Customer Name","Age","Country","Product","Purchase Date",cost_col,"Payment Mode","Category","Selling Price","__Profit","__Age Group","__Month"]
    for c in keep:
        if c not in df.columns:
            df[c] = None
    out = df[keep].copy()
    out["Purchase Date"] = pd.to_datetime(out["Purchase Date"], errors="coerce").dt.date.astype(str)
    return out, cost_col

# -------------------- Auth Routes --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_users_csv()
    if request.method == "GET":
        return render_template_string(LOGIN_HTML)
    # POST
    email = (request.form.get("email") or "").strip()
    password = (request.form.get("password") or "").strip()
    if check_credentials(email, password):
        session["user"] = email
        return redirect(url_for("home"))
    flash("Invalid email or password.")
    return render_template_string(LOGIN_HTML)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# -------------------- Template Download --------------------
@app.route("/download_template")
def download_template():
    # Generate Excel template in-memory
    cols = [
        "Customer Name","Age","Country","Product","Purchase Date",
        "Purchase Amount","Payment Mode","Category","Selling Price"
    ]
    example_row = {
        "Customer Name": "Rahul Sharma",
        "Age": 28,
        "Country": "India",
        "Product": "Smartphone",
        "Purchase Date": datetime.now().strftime("%Y-%m-%d"),
        "Purchase Amount": 18000,
        "Payment Mode": "UPI",
        "Category": "Electronics",
        "Selling Price": 22000
    }
    df = pd.DataFrame([example_row], columns=cols)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="sales_template.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# -------------------- Dashboard Routes --------------------
@app.route("/", methods=["GET"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template_string(HTML, has_data=False)

@app.route("/dashboard", methods=["POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    file = request.files.get("excel_file")
    if not file:
        return render_template_string(HTML, has_data=False)

    df = pd.read_excel(file)
    df_view, cost_col = _prepare_dataframe(df)
    data_json = df_view.to_dict(orient="records")

    return render_template_string(
        HTML,
        has_data=True,
        data_json=json.dumps(data_json, default=str),
        cost_col=cost_col
    )

# -------------------- Forecast API --------------------
@app.route("/forecast", methods=["POST"])
def forecast():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", [])
    horizon = int(payload.get("horizon", 3))

    if horizon < 1: horizon = 1
    if horizon > 12: horizon = 12

    if not rows:
        return jsonify({"history": [], "forecast": [], "next_month": 0, "note": "No data to forecast."}), 200

    df = pd.DataFrame(rows)
    # Parse dates, force to month start
    df["Purchase Date"] = pd.to_datetime(df["Purchase Date"], errors="coerce")
    df = df.dropna(subset=["Purchase Date"])
    df["Selling Price"] = pd.to_numeric(df["Selling Price"], errors="coerce").fillna(0)

    if df.empty:
        return jsonify({"history": [], "forecast": [], "next_month": 0, "note": "No valid dates/sales."}), 200

    df["month"] = df["Purchase Date"].values.astype("datetime64[M]")

    monthly = df.groupby("month")["Selling Price"].sum().sort_index()
    n = len(monthly)

    note = ""
    if n < 3:
        note = "Very little history. Forecast may be naive."

    history = [{"period": dt.strftime("%Y-%m"), "sales": float(v)} for dt, v in monthly.items()]

    if n == 0:
        fcast = []
        next_val = 0.0
    else:
        t = np.arange(n, dtype=float)
        y = monthly.values.astype(float)
        if n >= 3 and np.isfinite(y).all():
            # y = a + b*t  (np.polyfit returns [b, a])
            b, a = np.polyfit(t, y, 1)
            last_t = t[-1]
            fvals = []
            for h in range(1, horizon+1):
                val = a + b * (last_t + h)
                if not np.isfinite(val): val = y[-1]
                fvals.append(max(0.0, float(val)))
        else:
            fvals = [float(y[-1])] * horizon

        last_month = monthly.index[-1]
        f_dates = [(last_month + pd.offsets.MonthBegin(h)) for h in range(1, horizon+1)]
        fcast = [{"period": d.strftime("%Y-%m"), "sales": float(v)} for d, v in zip(f_dates, fvals)]
        next_val = fvals[0] if fvals else 0.0

    return jsonify({
        "history": history,
        "forecast": fcast,
        "next_month": round(next_val, 2),
        "note": note
    }), 200

# -------------------- PDF (No Matplotlib) --------------------
@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    from reportlab.lib.utils import ImageReader
    import plotly.express as px
    import plotly.io as pio
    import kaleido
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle
    import calendar, textwrap, io
    from datetime import datetime
    import pandas as pd

    if "user" not in session:
        return ("Unauthorized", 401)

    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", [])
    cost_col = payload.get("cost_col", "Purchase Amount")

    if not rows:
        return ("No data to generate PDF.", 400)

    df = pd.DataFrame(rows)
    df[cost_col] = pd.to_numeric(df.get(cost_col, 0), errors="coerce").fillna(0)
    df["Selling Price"] = pd.to_numeric(df.get("Selling Price", 0), errors="coerce").fillna(0)
    df["__Profit"] = pd.to_numeric(df.get("__Profit", df["Selling Price"] - df[cost_col]), errors="coerce").fillna(0)

    turnover = float(df["Selling Price"].sum())
    cost = float(df[cost_col].sum())
    profit = float(df["__Profit"].sum())
    pct = (profit / cost * 100) if cost > 0 else 0.0
    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

    def safe_mode(series):
        try:
            return series.mode().iloc[0]
        except Exception:
            return "—"

    top_selling = safe_mode(df["Product"]) if "Product" in df.columns else "—"
    top_country = safe_mode(df["Country"]) if "Country" in df.columns else "—"
    top_category = (
        df.groupby("Category")["__Profit"].sum().sort_values(ascending=False).index[0]
        if "Category" in df.columns and not df["Category"].dropna().empty else "—"
    )
    top_profit_prod = (
        df.groupby("Product")["__Profit"].sum().sort_values(ascending=False).index[0]
        if "Product" in df.columns and not df["Product"].dropna().empty else "—"
    )

    # ---------- Prepare Charts with Added Insights ----------
    charts, titles, notes, extra_info = [], [], [], []
    peak_month, low_month = "—", "—"
    top_country_name, top_country_sales = "—", 0
    try:
        # Category vs Profit
        cat_profit = df.groupby("Category")["__Profit"].sum().reset_index().sort_values("__Profit", ascending=False)
        if not cat_profit.empty:
            fig = px.bar(cat_profit, x="Category", y="__Profit", template="plotly_white",
                         title="Category vs Profit", color_discrete_sequence=["#1565C0"])
            fig.update_layout(margin=dict(l=30, r=30, t=60, b=40), title_x=0.5, height=500, width=1000)
            buf = io.BytesIO()
            pio.write_image(fig, buf, format="png", width=1000, height=500, scale=2)
            buf.seek(0)
            charts.append(buf)
            titles.append("Category vs Profit")
            notes.append("Shows which product categories generate the highest overall profit.")
            extra_info.append(
                f"The '{top_category}' category achieved the maximum profit. Consider increasing inventory, promotions, or similar SKUs."
            )

        # Monthly Sales Trend
        df["_parsed_date"] = pd.to_datetime(df.get("Purchase Date"), errors="coerce")
        if "_parsed_date" in df.columns and not df["_parsed_date"].dropna().empty:
            df["MonthNum"] = df["_parsed_date"].dt.month
            month_sales = df.groupby("MonthNum")["Selling Price"].sum().reset_index()
            if not month_sales.empty:
                month_sales["Month"] = month_sales["MonthNum"].apply(lambda m: calendar.month_abbr[m])
                month_sales = month_sales.sort_values("MonthNum")
                fig = px.line(month_sales, x="Month", y="Selling Price", markers=True,
                              template="plotly_white", title="Monthly Sales Trend",
                              color_discrete_sequence=["#43A047"])
                fig.update_layout(margin=dict(l=30, r=30, t=60, b=40), title_x=0.5, height=500, width=1000)
                buf = io.BytesIO()
                pio.write_image(fig, buf, format="png", width=1000, height=500, scale=2)
                buf.seek(0)
                charts.append(buf)
                titles.append("Monthly Sales Trend")
                notes.append("Visualizes monthly fluctuations in total sales.")
                try:
                    peak_month = month_sales.loc[month_sales["Selling Price"].idxmax(), "Month"]
                    low_month = month_sales.loc[month_sales["Selling Price"].idxmin(), "Month"]
                except Exception:
                    peak_month, low_month = "—", "—"
                extra_info.append(
                    f"Peak sales observed in {peak_month}. Lowest sales observed in {low_month}. Consider seasonal promotions and inventory planning."
                )

        # Country-wise Sales Share
        country_sales = df.groupby("Country")["Selling Price"].sum().reset_index().sort_values("Selling Price", ascending=False)
        if not country_sales.empty:
            fig = px.pie(country_sales, names="Country", values="Selling Price",
                         template="plotly_white", title="Country-wise Sales Share",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(margin=dict(l=20, r=20, t=60, b=40), title_x=0.5, height=500, width=1000)
            buf = io.BytesIO()
            pio.write_image(fig, buf, format="png", width=1000, height=500, scale=2)
            buf.seek(0)
            charts.append(buf)
            titles.append("Country-wise Sales Share")
            notes.append("Displays contribution of each country to total revenue.")
            try:
                top_country_name = country_sales.iloc[0]["Country"]
                top_country_sales = country_sales.iloc[0]["Selling Price"]
            except Exception:
                top_country_name, top_country_sales = "—", 0
            extra_info.append(
                f"{top_country_name} contributes the highest share (₹{int(top_country_sales):,}). Consider localised campaigns in other markets to diversify."
            )
    except Exception as e:
        print("Chart Error:", e)

    # ---------- PDF Creation ----------
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    PAGE_W, PAGE_H = A4
    MARGIN = 20 * mm
    usable_w = PAGE_W - 2 * MARGIN

    def draw_header(title=None):
        c.setFillColor(colors.HexColor("#1565C0"))
        c.rect(0, PAGE_H - 18 * mm, PAGE_W, 18 * mm, stroke=0, fill=1)
        if title:
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(colors.white)
            c.drawString(MARGIN, PAGE_H - 13 * mm, title)

    def draw_footer(page_num):
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        footer_text = f"Generated by Sales Dashboard — {now_str}"
        c.drawString(MARGIN, 10 * mm, footer_text)
        c.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {page_num}")

    # ---------- Cover Page ----------
    page_num = 1
    draw_header("Sales Performance Report")
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.HexColor("#0b2a66"))
    c.drawCentredString(PAGE_W / 2, PAGE_H - 55 * mm, "Sales Performance Report")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 62 * mm, f"Generated on {now_str}")

    # KPI Tiles
    kpis = [
        ("Turnover", f"₹{int(turnover):,}"),
        ("Cost", f"₹{int(cost):,}"),
        ("Profit", f"₹{int(profit):,}"),
        ("Profit %", f"{pct:.1f}%"),
        ("Top Product", top_selling),
        ("Top Country", top_country)
    ]
    cols = 3
    tile_w = (usable_w - (cols - 1) * 6 * mm) / cols
    tile_h = 16 * mm
    start_x = MARGIN
    start_y = PAGE_H - 85 * mm
    c.setFont("Helvetica", 9)
    for i, (k, v) in enumerate(kpis):
        col, row = i % cols, i // cols
        x = start_x + col * (tile_w + 6 * mm)
        y = start_y - row * (tile_h + 6 * mm)
        c.setFillColor(colors.whitesmoke)
        c.roundRect(x, y - tile_h, tile_w, tile_h, 3, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1565C0"))
        c.setFont("Helvetica", 8)
        c.drawString(x + 4 * mm, y - 6 * mm, k)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(x + tile_w - 4 * mm, y - 6 * mm, v)

    insight = f"Key Insight: The {top_category} category and {top_profit_prod} product are driving most profits."
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    y_text = PAGE_H - 130 * mm
    for line in textwrap.wrap(insight, 95):
        c.drawString(MARGIN, y_text, line)
        y_text -= 6 * mm

    draw_footer(page_num)
    c.showPage()
    page_num += 1

    # ---------- Chart Pages with Enhanced Insight Box ----------
    for i, img_buf in enumerate(charts):
        draw_header(titles[i])

        # Draw graph (centered and scaled to fit)
        img = ImageReader(img_buf)
        try:
            iw, ih = img.getSize()
            scale = min((usable_w) / iw, (PAGE_H - 90 * mm) / ih)
            draw_w, draw_h = iw * scale, ih * scale
        except Exception:
            # fallback fixed size
            draw_w, draw_h = usable_w, PAGE_H - 120 * mm

        x = (PAGE_W - draw_w) / 2
        y = (PAGE_H - draw_h) / 2 + 6 * mm  # slight nudge up for insight box
        c.drawImage(img, x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor='c', mask='auto')

        # Divider Line above Insight Box
        c.setStrokeColor(colors.HexColor("#B0BEC5"))
        c.setLineWidth(0.5)
        c.line(MARGIN, y - 10 * mm, PAGE_W - MARGIN, y - 10 * mm)

        # Light-blue rounded box for insight
        box_y = y - 40 * mm
        box_height = 34 * mm
        c.setFillColor(colors.HexColor("#E3F2FD"))
        c.roundRect(MARGIN, box_y, usable_w, box_height, 6, stroke=0, fill=1)

        # "Insight" heading
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor("#0D47A1"))
        c.drawString(MARGIN + 6 * mm, box_y + box_height - 9 * mm, "💡 Insight")

        # Short note
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)
        text_y = box_y + box_height - 15 * mm
        for line in textwrap.wrap(notes[i], 95):
            c.drawString(MARGIN + 10 * mm, text_y, line)
            text_y -= 5 * mm

        # Extended analysis
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        text_y -= 2 * mm
        for line in textwrap.wrap(extra_info[i], 110):
            c.drawString(MARGIN + 10 * mm, text_y, line)
            text_y -= 4.5 * mm
            if text_y < (10 * mm):  # safety: avoid overflow
                break

        draw_footer(page_num)
        c.showPage()
        page_num += 1

    # ---------- Executive Summary Page ----------
    draw_header("Executive Summary")
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.HexColor("#0b2a66"))
    c.drawCentredString(PAGE_W / 2, PAGE_H - 45 * mm, "Executive Summary of Key Insights")

    summary_points = [
        f"• Top profit category: {top_category}",
        f"• Most profitable product: {top_profit_prod}",
        f"• Top country: {top_country_name} (₹{int(top_country_sales):,})",
        f"• Peak sales month: {peak_month}  |  Lowest sales month: {low_month}",
        "• Recommendation: Promote top categories, review costs for low-margin categories, and run seasonal campaigns."
    ]

    c.setFont("Helvetica", 10)
    y_pos = PAGE_H - 70 * mm
    for line in summary_points:
        for wrapped_line in textwrap.wrap(line, 110):
            c.drawString(MARGIN, y_pos, wrapped_line)
            y_pos -= 8 * mm

    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(colors.grey)
    c.drawString(MARGIN, y_pos - 6 * mm,
                 "This executive summary aggregates chart-level insights for quick decision-making.")
    draw_footer(page_num)
    c.showPage()
    page_num += 1

    # ---------- Data Table (auto-split across pages) ----------
    preview_cols = ["Customer Name", "Product", "Category", "Country", "Selling Price", "__Profit"]
    for col in preview_cols:
        if col not in df.columns:
            df[col] = ""

    rows_to_show = df[preview_cols].astype(str).head(200).values.tolist()  # show up to 200 if present
    data = [preview_cols] + rows_to_show

    draw_header("Data Preview")
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#1565C0"))
    c.drawString(MARGIN, PAGE_H - 26 * mm, "Data Preview (First rows)")

    available_width = PAGE_W - 2 * MARGIN
    available_height = PAGE_H - 60 * mm
    num_cols = len(preview_cols)
    col_widths = [available_width / num_cols for _ in range(num_cols)]

    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565C0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    # Use Table.split to break the table into pages that fit available area
    parts = table.split(available_width, available_height)
    if not parts:
        # fallback: draw single table
        w, h = table.wrap(available_width, available_height)
        x_pos = MARGIN
        y_pos = PAGE_H - 60 * mm - h
        table.drawOn(c, x_pos, y_pos)
        draw_footer(page_num)
        c.showPage()
    else:
        for part in parts:
            # compute draw position for this part and render
            w, h = part.wrap(available_width, available_height)
            x_pos = MARGIN
            y_pos = PAGE_H - 60 * mm - h
            part.drawOn(c, x_pos, y_pos)
            draw_footer(page_num)
            c.showPage()
            page_num += 1

    c.save()
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name="Sales_Report.pdf")

# -------------------- Run --------------------
if __name__ == "__main__":
    ensure_users_csv()
    app.run(debug=True) 