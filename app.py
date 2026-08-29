import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import sms_parser

st.set_page_config(
    page_title="Expense & Cash Flow Helper",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean, polished dashboard UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-size: 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Helper functions -----------------
@st.cache_data(show_spinner=False)
def get_parsed_data(csv_file_path, _rules):
    return sms_parser.parse_sms_file(csv_file_path, rules=_rules)

def format_inr(val):
    if abs(val) >= 10000000:
        return f"₹{val/10000000:.2f} Cr"
    elif abs(val) >= 100000:
        return f"₹{val/100000:.2f} L"
    elif abs(val) >= 1000:
        return f"₹{val/1000:.1f} K"
    else:
        return f"₹{val:,.2f}"

# ----------------- App State & Sidebar -----------------
st.sidebar.title("💰 Expense Helper")
st.sidebar.markdown("Smart SMS-driven expense tracking & categorization.")

# CSV Source
default_file = "file.csv" if os.path.exists("file.csv") else None
uploaded_file = st.sidebar.file_uploader("Upload SMS Backup CSV", type=["csv"])

if uploaded_file is not None:
    csv_source = uploaded_file
elif default_file:
    csv_source = default_file
else:
    st.info("Please upload an SMS CSV backup file to get started.")
    st.stop()

# Load rules
rules = sms_parser.load_rules()
df = get_parsed_data(csv_source, rules)

if df.empty:
    st.warning("No transactions could be parsed from the provided file.")
    st.stop()

# Sidebar Filters
st.sidebar.header("🔍 Filters")

# Date range
min_date = pd.to_datetime(df["Date"]).min().date()
max_date = pd.to_datetime(df["Date"]).max().date()
date_range = st.sidebar.date_input("Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)

# Account Filter
all_accounts = sorted(df["Account"].unique())
selected_accounts = st.sidebar.multiselect("Filter Accounts", all_accounts, default=all_accounts)

# Transaction Type Filter
all_types = sorted(df["Type"].unique())
selected_types = st.sidebar.multiselect("Filter Types", all_types, default=all_types)

# Apply Filters
start_d = date_range[0] if len(date_range) > 0 else min_date
end_d = date_range[1] if len(date_range) > 1 else start_d

mask = (
    (pd.to_datetime(df["Date"]).dt.date >= start_d) &
    (pd.to_datetime(df["Date"]).dt.date <= end_d) &
    (df["Account"].isin(selected_accounts)) &
    (df["Type"].isin(selected_types))
)
fdf = df[mask].copy()

# Header
st.markdown("<div class='main-header'>Expense & Cash Flow Analysis</div>", unsafe_allow_html=True)
st.markdown(f"<div class='sub-header'>Analyzing <b>{len(fdf)} transactions</b> from {start_d.strftime('%d %b %Y')} to {end_d.strftime('%d %b %Y')}</div>", unsafe_allow_html=True)

# ----------------- Top KPI Metric Cards -----------------
inflow = fdf[fdf["Type"].isin(["Income", "Salary / Income", "Dividend / Inflow", "Cashback / Reward", "Investment Inflow"])]["Amount"].sum()
expenses = fdf[fdf["Type"].isin(["Expense", "Debt / EMI", "Cash Withdrawal"])]["Amount"].sum()
investments = fdf[fdf["Type"].isin(["Investment", "Investment (SIP)"])]["Amount"].sum()
transfers = fdf[fdf["Type"].isin(["Transfer"])]["Amount"].sum()
net_cash = inflow - (expenses + investments + transfers)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("💵 Total Inflow", format_inr(inflow), f"{len(fdf[fdf['Type']=='Income'])} records")
kpi2.metric("💳 Direct Expenses", format_inr(expenses), f"{len(fdf[fdf['Type']=='Expense'])} records", delta_color="inverse")
kpi3.metric("📈 Investments", format_inr(investments), f"{len(fdf[fdf['Type']=='Investment'])} records")
kpi4.metric("👥 Transfers / P2P", format_inr(transfers), f"{len(fdf[fdf['Type']=='Transfer'])} records")
kpi5.metric("🏦 Net Cash Flow", format_inr(net_cash), "Inflow - Outflow")

st.divider()

# ----------------- Tabs / Views -----------------
tab1, tab2, tab3 = st.tabs([
    "📊 Insights & Analytics",
    "⚙️ Merchant & Hierarchy Admin",
    "📋 Raw Transactions Ledger"
])

# ==========================================
# VIEW 1: INSIGHTS & ANALYTICS
# ==========================================
with tab1:
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.subheader("📅 Month-on-Month Cash Flow")
        monthly = fdf.groupby(["Month", "Type"])["Amount"].sum().reset_index()
        fig_month = px.bar(
            monthly,
            x="Month",
            y="Amount",
            color="Type",
            barmode="group",
            title="Monthly Breakdown by Transaction Type",
            color_discrete_map={
                "Income": "#10B981",
                "Expense": "#EF4444",
                "Investment": "#3B82F6",
                "Transfer": "#8B5CF6",
                "Credit Card Bill Payment": "#F59E0B",
                "Cash Withdrawal": "#64748B"
            }
        )
        fig_month.update_layout(xaxis_title="", yaxis_title="Amount (₹)", legend_title="")
        st.plotly_chart(fig_month, use_container_width=True)
        
    with col_right:
        st.subheader("🍩 Expense Distribution by Bucket")
        exp_only = fdf[fdf["Type"] == "Expense"]
        if not exp_only.empty:
            bucket_agg = exp_only.groupby("Bucket")["Amount"].sum().reset_index()
            fig_pie = px.pie(
                bucket_agg,
                values="Amount",
                names="Bucket",
                hole=0.45,
                title="Direct Expenses by Bucket (L1)"
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense transactions in current filter selection.")

    st.divider()
    
    # 3-Level Sunburst Chart
    st.subheader("🌳 3-Tier Multi-Level Spending Hierarchy (Bucket ➔ Sub-Bucket ➔ Sub-Sub-Bucket)")
    st.caption("Click on any inner ring slice to drill down into sub-buckets and individual merchant sub-sub-categories.")
    
    if not exp_only.empty:
        fig_sunburst = px.sunburst(
            exp_only,
            path=["Bucket", "Sub_Bucket", "Sub_Sub_Bucket"],
            values="Amount",
            color="Bucket",
            title="Expense Hierarchy Sunburst Chart"
        )
        fig_sunburst.update_layout(margin=dict(t=30, l=0, r=0, b=0), height=550)
        st.plotly_chart(fig_sunburst, use_container_width=True)
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.subheader("🏆 Top 10 Merchants by Outflow")
        top_merchants = exp_only.groupby("Merchant")["Amount"].agg(["sum", "count"]).sort_values("sum", ascending=False).head(10).reset_index()
        fig_merchants = px.bar(
            top_merchants,
            x="sum",
            y="Merchant",
            orientation="h",
            text="sum",
            labels={"sum": "Total Spend (₹)", "Merchant": ""},
            title="Top 10 Merchants"
        )
        fig_merchants.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
        fig_merchants.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_merchants, use_container_width=True)
        
    with col_m2:
        st.subheader("💳 Spends by Account / Card")
        acc_spends = exp_only.groupby("Account")["Amount"].sum().reset_index().sort_values("Amount", ascending=False)
        fig_acc = px.bar(
            acc_spends,
            x="Account",
            y="Amount",
            color="Account",
            title="Spends by Payment Instrument"
        )
        fig_acc.update_layout(xaxis_title="", yaxis_title="Spend (₹)", showlegend=False)
        st.plotly_chart(fig_acc, use_container_width=True)


# ==========================================
# VIEW 2: MERCHANT & HIERARCHY ADMIN PANEL
# ==========================================
with tab2:
    st.subheader("⚙️ Merchant Rules & 3-Tier Hierarchy Management")
    st.markdown("Select any merchant to inspect all associated transactions and customize its **Bucket (L1)**, **Sub-Bucket (L2)**, and **Sub-Sub-Bucket (L3)**.")
    
    # List all unique merchants from dataset
    merchant_stats = df.groupby(["Merchant", "Raw_Merchant"])["Amount"].agg(["count", "sum"]).reset_index()
    merchant_stats = merchant_stats.sort_values("count", ascending=False)
    
    show_uncategorized_only = st.checkbox("Show only unmapped / 'Other / Uncategorized' merchants", value=False)
    
    if show_uncategorized_only:
        unmapped_merchants = df[df["Bucket"] == "Other / Uncategorized"]["Merchant"].unique()
        available_merchants = [m for m in merchant_stats["Merchant"].unique() if m in unmapped_merchants]
    else:
        available_merchants = merchant_stats["Merchant"].unique().tolist()
        
    if not available_merchants:
        st.success("All merchants are mapped!")
        available_merchants = merchant_stats["Merchant"].unique().tolist()

    selected_merchant = st.selectbox("Select Merchant / Payee to Configure", available_merchants)
    
    m_txns = df[df["Merchant"] == selected_merchant]
    m_count = len(m_txns)
    m_sum = m_txns["Amount"].sum()
    sample_raw = m_txns["Raw_Merchant"].iloc[0] if not m_txns.empty else selected_merchant
    curr_type = m_txns["Type"].iloc[0] if not m_txns.empty else "Expense"
    curr_b1 = m_txns["Bucket"].iloc[0] if not m_txns.empty else "Living & Daily Essentials"
    curr_b2 = m_txns["Sub_Bucket"].iloc[0] if not m_txns.empty else "Groceries & Quick Commerce"
    curr_b3 = m_txns["Sub_Sub_Bucket"].iloc[0] if not m_txns.empty else "Quick Delivery"

    stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
    stat_c1.metric("Selected Merchant", selected_merchant)
    stat_c2.metric("Total Transactions", m_count)
    stat_c3.metric("Total Volume", format_inr(m_sum))
    stat_c4.metric("Current Type", curr_type)
    
    st.markdown("#### Configure Classification & Tags")
    
    preset_buckets = [
        "Living & Daily Essentials",
        "Discretionary & Lifestyle",
        "Bills & Utilities",
        "Healthcare & Wellness",
        "Investments & Wealth",
        "Family & Personal Transfers",
        "Financial & Debt Obligations",
        "Income & Inflows",
        "Other / Uncategorized"
    ]
    
    type_options = ["Expense", "Income", "Investment", "Transfer", "Credit Card Bill Payment", "Cash Withdrawal", "Debt / EMI", "Refund / Reversal"]
    
    with st.form("edit_merchant_form"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            edit_name = st.text_input("Clean Merchant Display Name", value=selected_merchant)
            edit_type = st.selectbox("Transaction Type", type_options, index=type_options.index(curr_type) if curr_type in type_options else 0)
            
            bucket_idx = preset_buckets.index(curr_b1) if curr_b1 in preset_buckets else len(preset_buckets)-1
            edit_bucket = st.selectbox("Bucket (L1 - High Level)", preset_buckets, index=bucket_idx)
            
        with col_f2:
            edit_sub_bucket = st.text_input("Sub-Bucket (L2 - Domain Category)", value=curr_b2)
            edit_sub_sub_bucket = st.text_input("Sub-Sub-Bucket (L3 - Specific Item/Tag)", value=curr_b3)
            edit_patterns = st.text_input("Matching Keywords (comma-separated)", value=f"{sample_raw.lower()}, {selected_merchant.lower()}")

        submit_save = st.form_submit_button("💾 Save Rule & Re-tag All Transactions", type="primary")
        
        if submit_save:
            rule_key = edit_name.lower().replace(" ", "_").replace("'", "").replace(".", "")
            new_patterns = [p.strip() for p in edit_patterns.split(",") if p.strip()]
            
            if "merchants" not in rules:
                rules["merchants"] = {}
                
            rules["merchants"][rule_key] = {
                "name": edit_name,
                "type": edit_type,
                "bucket": edit_bucket,
                "sub_bucket": edit_sub_bucket,
                "sub_sub_bucket": edit_sub_sub_bucket,
                "match_patterns": new_patterns
            }
            
            sms_parser.save_rules(rules)
            st.cache_data.clear()
            st.success(f"Rule for '{edit_name}' saved successfully! Re-indexing data...")
            st.rerun()

    st.markdown("#### Associated Transactions for Selected Merchant")
    st.dataframe(
        m_txns[["Date", "Amount", "Account", "Type", "Bucket", "Sub_Bucket", "Sub_Sub_Bucket", "Ref_No", "Raw_SMS"]],
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# VIEW 3: RAW TRANSACTIONS TABLE
# ==========================================
with tab3:
    st.subheader("📋 Complete Tagged Transactions Ledger")
    
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        search_query = st.text_input("🔎 Search merchant, reference, account, or raw SMS content", "")
    with col_t2:
        export_df = fdf[["Date", "Month", "Amount", "Type", "Bucket", "Sub_Bucket", "Sub_Sub_Bucket", "Merchant", "Account", "Ref_No", "Sender", "Raw_SMS"]]
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Clean CSV",
            data=csv_data,
            file_name="expenses_clean_tagged.csv",
            mime="text/csv"
        )
        
    table_df = fdf.copy()
    if search_query:
        s = search_query.lower()
        table_df = table_df[
            table_df["Merchant"].str.lower().str.contains(s) |
            table_df["Bucket"].str.lower().str.contains(s) |
            table_df["Sub_Bucket"].str.lower().str.contains(s) |
            table_df["Account"].str.lower().str.contains(s) |
            table_df["Raw_SMS"].str.lower().str.contains(s) |
            table_df["Ref_No"].str.lower().str.contains(s)
        ]
        
    st.write(f"Showing **{len(table_df)}** transactions")
    
    st.dataframe(
        table_df[["Date", "Amount", "Type", "Bucket", "Sub_Bucket", "Sub_Sub_Bucket", "Merchant", "Account", "Ref_No", "Sender"]],
        use_container_width=True,
        hide_index=True
    )
    
    with st.expander("🔍 View Raw SMS Messages"):
        st.dataframe(
            table_df[["Date", "Merchant", "Amount", "Raw_SMS"]],
            use_container_width=True,
            hide_index=True
        )
