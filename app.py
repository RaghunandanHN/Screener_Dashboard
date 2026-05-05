import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import requests

# ==========================================
# PAGE CONFIGURATION (Wide Mode)
# ==========================================
st.set_page_config(page_title="HNR Command Center", page_icon="🏛️", layout="wide")
st_autorefresh(interval=300000, key="datarefresh") # 5 Min Auto-Refresh

# ==========================================
# AGGRESSIVE CSS: HIDE HEADERS & KILL WHITESPACE
# ==========================================
st.markdown("""
    <style>
    header {visibility: hidden !important;}
    .block-container { 
        padding-top: 0rem !important; 
        padding-bottom: 0rem !important; 
        margin-top: 0rem !important;
        max-width: 100% !important;
    }
    div[data-testid="stVerticalBlock"] { gap: 0.2rem !important; }
    /* Hide the top margin of the markdown header */
    h4 { margin-top: 0rem !important; padding-top: 0rem !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INDIAN NUMBER FORMATTER (Lakhs / Crores)
# ==========================================
def format_indian(num, is_float=False):
    if pd.isna(num): return "0"
    try:
        num_val = float(num)
        is_neg = num_val < 0
        num_val = abs(num_val)
        int_part = int(num_val)
        
        s = str(int_part)
        if len(s) > 3:
            last_3 = s[-3:]
            rest = s[:-3]
            # Split remaining numbers into groups of 2
            chunks = [rest[max(0, i-2):i] for i in range(len(rest), 0, -2)]
            chunks.reverse()
            s = ",".join(chunks) + "," + last_3
            
        if is_float:
            dec = f"{num_val:.1f}".split(".")[1]
            s = f"{s}.{dec}"
            
        return f"-{s}" if is_neg else s
    except:
        return str(num)

# ==========================================
# DATA LOADING ENGINE
# ==========================================
@st.cache_data(ttl=300)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/12RfTgNRrePMfoIn9N2pQnQtoiVCftd7m3hJGHjOtxmc/export?format=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.astype(str).str.strip()
        
        if 'Ticker' in df.columns and 'Symbol' not in df.columns:
            df.rename(columns={'Ticker': 'Symbol'}, inplace=True)
        if 'Screen' in df.columns and 'Type' not in df.columns:
            df.rename(columns={'Screen': 'Type'}, inplace=True)
            
        # Dynamically find date column and preserve EXACT text from Google Sheet
        date_col = 'Date' if 'Date' in df.columns else df.columns[12]
        df['RawDate'] = df[date_col].fillna("N/A") 
        
        # Hidden parse for the sidebar date filter only
        df['DateTime'] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        
        numeric_cols = ['LTP', 'Gain', 'Volume', 'RSI', '52WH', 'PCR']
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = 0.0 
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Awaiting data from Google Sheets...")
    st.stop()

# ==========================================
# SIDEBAR FILTERS
# ==========================================
min_date = df['DateTime'].min().date() if not pd.isna(df['DateTime'].min()) else datetime.today().date()
max_date = df['DateTime'].max().date() if not pd.isna(df['DateTime'].max()) else datetime.today().date()
date_selection = st.sidebar.date_input("Date Range", [min_date, max_date])

if len(date_selection) == 2:
    start_date, end_date = date_selection
    mask = (df['DateTime'].dt.date >= start_date) & (df['DateTime'].dt.date <= end_date)
    filtered_df = df.loc[mask]
else:
    filtered_df = df.copy()

type_counts = filtered_df['Type'].value_counts()
type_options = type_counts.index.tolist()
format_func = lambda x: f"{x} ({type_counts[x]})"
selected_types = st.sidebar.multiselect("Select Categories:", type_options, default=type_options[:2] if len(type_options)>1 else type_options, format_func=format_func)
filtered_df = filtered_df[filtered_df['Type'].isin(selected_types)]

# ==========================================
# 1-PAGE UI: SINGLE INLINE HEADER
# ==========================================
kpi_string = f"**Total Records:** {format_indian(len(filtered_df))} &nbsp;&nbsp;|&nbsp;&nbsp; **Unique Symbols:** {format_indian(filtered_df['Symbol'].nunique())}"
st.markdown(f"#### 🏛️ HNR Command Center &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {kpi_string}")

# ==========================================
# HTML TABLE GENERATORS (Absolute Control)
# ==========================================
# Base CSS for tables ensuring perfect centering and sticky headers
BASE_TABLE_CSS = """
<style>
.custom-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; text-align: center; }
.custom-table th { background-color: #f8f9fa; position: sticky; top: 0; padding: 8px; border-bottom: 2px solid #ccc; text-align: center; z-index: 1;}
.custom-table td { padding: 6px 8px; border-bottom: 1px solid #eee; text-align: center; }
.custom-table tr:hover { background-color: #f1f3f5; }
.scroll-box { max-height: 650px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; }
</style>
"""
st.markdown(BASE_TABLE_CSS, unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 1.4, 1.6])

with col1:
    if not filtered_df.empty:
        pivot_df = filtered_df.groupby(['Symbol']).agg(Count=('Type', 'count'), Max_52W=('52WH', 'max')).reset_index().sort_values(by='Count', ascending=False)
        html = '<div class="scroll-box"><table class="custom-table"><tr><th>Symbol</th><th>Hits</th><th>52WH</th></tr>'
        for _, row in pivot_df.iterrows():
            html += f'<tr><td><b>{row["Symbol"]}</b></td><td>{format_indian(row["Count"])}</td><td>{format_indian(row["Max_52W"], True)}</td></tr>'
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

with col2:
    master_df = filtered_df.drop_duplicates(subset=['Symbol']).sort_values(by='Volume', ascending=False).copy()
    if not master_df.empty:
        html = '<div class="scroll-box"><table class="custom-table"><tr><th>Symbol</th><th>Action</th><th>LTP</th><th>RSI</th><th>Volume</th></tr>'
        for _, row in master_df.iterrows():
            link = f'https://in.tradingview.com/chart/?symbol=NSE:{row["Symbol"]}'
            html += f'''<tr>
                <td><b>{row["Symbol"]}</b></td>
                <td><a href="{link}" target="_blank" style="text-decoration:none; color: #1f77b4;">📈 View</a></td>
                <td>₹{format_indian(row["LTP"], True)}</td>
                <td>{row["RSI"]:.1f}</td>
                <td>{format_indian(row["Volume"])}</td>
            </tr>'''
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

with col3:
    if not filtered_df.empty:
        html = '<div class="scroll-box"><table class="custom-table"><tr><th>Symbol</th><th>Gain %</th><th>LTP</th><th>Time</th><th>PCR</th></tr>'
        for _, row in filtered_df.iterrows():
            try: gain_val = float(row["Gain"])
            except: gain_val = 0.0
            
            # CSS Progress Bar logic
            clamped_gain = min(max(gain_val, 0), 10) 
            width_pct = (clamped_gain / 10) * 100
            bar = f'''<div style="width:100%; background:#e0e0e0; border-radius:3px; text-align:left;">
                        <div style="width:{width_pct}%; background:#26a69a; height:16px; border-radius:3px; padding-left:4px; color:white; font-size:11px; font-weight:bold; line-height:16px; white-space:nowrap;">{gain_val:.2f}%</div>
                      </div>'''
                      
            html += f'''<tr>
                <td><b>{row["Symbol"]}</b></td>
                <td style="width: 25%;">{bar}</td>
                <td>₹{format_indian(row["LTP"], True)}</td>
                <td>{row["RawDate"]}</td>
                <td>{row["PCR"]:.2f}</td>
            </tr>'''
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)

# ==========================================
# GROQ AI ANALYTICS ENGINE
# ==========================================
if st.button("🧠 Generate AI Analysis (Groq Llama 3.3)"):
    with st.spinner("Analyzing..."):
        if not master_df.empty:
            prompt = f"""Act as a Senior Quant Analyst. Look at this screener data: {master_df[['Symbol', 'RSI', 'Gain', 'Volume']].head(10).to_string()}. 1. Sector pattern? 2. Top 2 asymmetric plays? 3. Risk warning? Keep it very brief."""
            try:
                groq_key = "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" 
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]}
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    st.info(res.json()['choices'][0]['message']['content'])
                else:
                    st.error("AI Error")
            except Exception as e:
                st.error(f"Error: {e}")
