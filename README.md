<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoSales Dashboard | AI-Powered Business Analytics</title>

<style>
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #0b1120;
    color: #e2e8f0;
    margin: 0;
    padding: 0;
  }

  header {
    background: linear-gradient(90deg, #1565C0, #1E88E5);
    padding: 40px 20px;
    text-align: center;
    color: white;
  }

  header h1 {
    font-size: 2.6em;
    margin: 0;
  }

  header p {
    font-size: 1.1em;
    opacity: 0.9;
  }

  .container {
    max-width: 1000px;
    margin: 40px auto;
    padding: 30px;
    background-color: #111827;
    border-radius: 12px;
    box-shadow: 0 6px 25px rgba(0,0,0,0.5);
  }

  h2 {
    color: #60a5fa;
    border-left: 4px solid #60a5fa;
    padding-left: 10px;
    margin-top: 40px;
  }

  p, ul {
    color: #cbd5e1;
    line-height: 1.7;
    font-size: 1.05em;
  }

  ul {
    list-style-type: "🔹 ";
    margin-left: 40px;
  }

  .download-button {
    display: inline-block;
    background-color: #1E88E5;
    color: white;
    padding: 12px 25px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: bold;
    margin: 20px 0;
    transition: 0.3s;
  }

  .download-button:hover {
    background-color: #1565C0;
    box-shadow: 0 0 10px #1E88E5;
  }

  .screenshots {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 25px;
    margin-top: 30px;
  }

  .screenshots img {
    width: 95%;
    max-width: 850px;
    border-radius: 10px;
    border: 2px solid #334155;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.4);
  }

  footer {
    text-align: center;
    padding: 25px;
    color: #9ca3af;
    font-size: 0.9em;
    border-top: 1px solid #1e293b;
    margin-top: 40px;
  }

  a {
    color: #60a5fa;
    text-decoration: none;
  }

  a:hover {
    text-decoration: underline;
  }
</style>
</head>

<body>

<header>
  <h1>📊 AutoSales Dashboard</h1>
  <p>AI-Powered Business Analytics, Visualization & Forecasting System</p>
</header>

<div class="container">
  <h2>📌 Project Overview</h2>
  <p>
    The <strong>AutoSales Dashboard</strong> is a full-stack business analytics project designed to automate 
    the process of analyzing and forecasting sales data. Using AI-driven models and interactive dashboards, 
    the system transforms raw Excel data into clear, actionable insights for businesses.
  </p>

  <p>
    It identifies top-performing product categories, tracks profit growth, forecasts sales, and assists in 
    optimizing pricing and marketing strategies — all through an intelligent and automated interface.
  </p>

  <h2>✅ Objectives of the Project</h2>
  <ul>
    <li>Analyze sales trends across products, categories, and countries</li>
    <li>Predict next-month sales using linear regression-based forecasting</li>
    <li>Display key performance metrics (Turnover, Profit, Cost, Transactions)</li>
    <li>Enable interactive visualizations for better business insights</li>
    <li>Provide PDF report generation with integrated charts</li>
  </ul>

  <h2>🛠 Tools & Technologies Used</h2>
  <ul>
    <li><strong>Python (Flask):</strong> Backend development & automation</li>
    <li><strong>Pandas, NumPy:</strong> Data cleaning and transformation</li>
    <li><strong>Plotly:</strong> Interactive visualizations</li>
    <li><strong>Scikit-learn:</strong> Forecasting with Linear Regression</li>
    <li><strong>ReportLab:</strong> PDF report generation</li>
    <li><strong>HTML, CSS, JavaScript:</strong> Dashboard frontend</li>
  </ul>

  <h2>📂 Dataset</h2>
  <p>
    The dataset contains transactional business data, including product sales, profit margins, 
    and payment details for multiple regions and categories.
  </p>

  <p><b>Dataset Features:</b></p>
  <ul>
    <li>Product Name & Category</li>
    <li>Sales, Cost, and Profit Values</li>
    <li>Country & Payment Type</li>
    <li>Date of Transaction</li>
  </ul>

  <a href="https://github.com/Dhruva912005/Dynamic-Sales-Dashboard-Generator/raw/main/BA_Template_fixed.xlsx" 
     class="download-button" download>⬇️ Download Dataset (Excel)</a>

  <h2>📸 Dashboard Preview</h2>
  <div class="screenshots">
    <img src="Screenshot 2025-11-12 212056.png" alt="Dashboard Overview">
    <img src="Screenshot 2025-11-12 212121.png" alt="Category vs Region Analysis">
    <img src="Screenshot 2025-11-12 212129.png" alt="Profit Distribution">
    <img src="Screenshot 2025-11-12 212138.png" alt="Forecasting Trends">
  </div>

  <h2>🔍 Key Insights</h2>
  <ul>
    <li>🏆 Home Appliances and Clothing are top profit-generating categories.</li>
    <li>🌍 Countries with stable product margins contribute 60% of total profits.</li>
    <li>📈 Moderate discounts (<20%) maximize both sales and profitability.</li>
    <li>🔮 Forecast predicts steady growth for upcoming months.</li>
  </ul>

  <h2>🚀 Future Scope & Improvements</h2>
  <ul>
    <li>Integrate real-time data through cloud-based APIs</li>
    <li>Implement predictive pricing optimization models</li>
    <li>Develop voice-based analytics chatbot</li>
    <li>Build mobile app dashboard version for executives</li>
  </ul>

  <h2>💼 Business Impact</h2>
  <ul>
    <li>⏱ 90% reduction in manual reporting time</li>
    <li>💰 15–20% increase in average profit margins</li>
    <li>📊 Data-driven marketing and pricing strategy creation</li>
    <li>🧠 Enables smart decision-making for non-technical users</li>
  </ul>

  <h2>👨‍💻 Developer</h2>
  <p>
    <strong>Dhruva Jain</strong><br>
    B.Tech – Mathematics & Computing, MITS-DU, Gwalior<br>
    Data Analytics | Business Intelligence | Automation Enthusiast<br>
    🔗 <a href="https://github.com/Dhruva912005" target="_blank">GitHub: Dhruva912005</a><br>
    ✉️ dhruvajain@example.com
  </p>
</div>

<footer>
  © 2025 AutoSales Dashboard | Designed & Developed by Dhruva Jain
</footer>

</body>
</html>
