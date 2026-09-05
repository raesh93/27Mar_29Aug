# SMS Expense & Cash Flow Helper

An intelligent, lightweight application to analyze and categorize personal expenses, income, investments, and cash flows directly from Indian bank and payment SMS backups.

## Features

- **Automated SMS Parser (`sms_parser.py`)**:
  - Regex-based transaction extraction for Kotak, AU Bank, ICICI Bank, Axis Bank, HDFC Bank, Bank of Baroda, CRED, Amazon Pay, Zepto Cash, etc.
  - Extracts Date, Amount, Transaction Type, Accounts, Ref/UTR Numbers, and Clean Merchant Names.
  - Automatically filters noise (OTPs with amounts, promotional/loan alerts, portfolio updates) to prevent duplicate transactions.
  - Distinguishes direct card/merchant spends from credit card bill settlements (CRED/NEFT) to avoid double-counting.

- **3-Tier Categorization Hierarchy**:
  - **Bucket (L1)**: High-level financial categories (e.g. *Living & Daily Essentials*, *Discretionary & Lifestyle*, *Bills & Utilities*, *Healthcare*, *Investments*, *Financial Obligations*, *Income*).
  - **Sub-Bucket (L2)**: Domain categories (e.g. *Groceries & Quick Commerce*, *Food Delivery & Dining*, *Mutual Funds & SIP*).
  - **Sub-Sub-Bucket (L3)**: Granular tags (e.g. *Zepto 10-min*, *Swiggy Delivery*, *Groww Equity SIP*).

- **Streamlit Interactive Web App (`app.py`)**:
  - **View 1 (Insights & Analytics)**: High-level KPIs, Month-on-Month cash flow comparison, 3-level interactive Sunburst chart, Top 10 merchants, and account-wise spend distribution.
  - **View 2 (Merchant & Hierarchy Admin Panel)**: Inspect any merchant's transaction history and customize their 3-tier categorization rules with real-time saving and hot reloading.
  - **View 3 (Raw Transactions Ledger)**: Searchable, filterable ledger with raw SMS inspector and CSV export.
  - **View 4 (Merchant & Category Filter)**: Multi-dimensional drilldown by any combination of Merchant, Bucket (L1), and Sub-Bucket (L2), complete with dedicated KPIs, monthly charts, breakdown visualizations, and filtered CSV export.

## Setup & Running

1. **Clone the repository**:
   ```bash
   git clone https://github.com/raesh93/27Mar_29Aug.git
   cd 27Mar_29Aug
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the Dashboard**:
   ```bash
   streamlit run app.py
   ```
