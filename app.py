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
    /* Hide the default Streamlit top header and menu */
    header {visibility: hidden !important;}
    
    /* Erase all top/bottom padding to push content to the absolute edges */
    .block-container { 
        padding-top: 0rem !important; 
        padding-bottom: 0rem !important; 
        margin-top: 0rem !important;
        max-width: 100% !important;
    }
    
    /* Make markdown headings tighter */
    h4, h5 { margin-bottom: 0rem !important; padding-bottom: 0.2rem !important; padding-top: 0rem !important; }
    
    /* Shrink the gap between elements */
    div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    </style>
""", unsafe_allow_html=True)

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
            
        date_col = 'Date' if 'Date' in df.columns else df.columns[12]
        df['DateTime'] = pd.to_datetime(df[date_col], errors='coerce')
        
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
# SIDEBAR: ADVANCED FILTERING
# ==========================================
# 1. Date Range Picker
min_date = df['DateTime'].min().date() if not pd.isna(df['DateTime'].min()) else datetime.today().date()
max_date = df['DateTime'].max().date() if not pd.isna(df['DateTime'].max()) else datetime.today().date()
date_selection = st.sidebar.date_input("Date Range", [min_date, max_date])

if len(date_selection) == 2:
    start_date, end_date = date_selection
    mask = (df['DateTime'].dt.date >= start_date) & (df['DateTime'].dt.date <= end_date)
    filtered_df = df.loc[mask]
else:
    filtered_df = df.copy()

# 2. Type/Screen Multi-Select
type_counts = filtered_df['Type'].value_counts()
type_options = type_counts.index.tolist()
format_func = lambda x: f"{x} ({type_counts[x]})"
selected_types = st.sidebar.multiselect("Select Categories:", type_options, default=type_options[:2] if len(type_options)>1 else type_options, format_func=format_func)
filtered_df = filtered_df[filtered_df['Type'].isin(selected_types)]

# ==========================================
# 1-PAGE UI: INLINE KPI HEADER
# ==========================================
# We pack all metrics into a single text string to save massive vertical space
kpi_string = f"**Total Records:** {len(filtered_df)} &nbsp;&nbsp;|&nbsp;&nbsp; **Unique Symbols:** {filtered_df['Symbol'].nunique()} &nbsp;&nbsp;|&nbsp;&nbsp; **Avg RSI:** {filtered_df['RSI'].mean():.1f}"
st.markdown(f"#### 🏛️ HNR Command Center &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {kpi_string}")

# ==========================================
# 1-PAGE UI: 3-COLUMN HORIZONTAL LAYOUT
# ==========================================
# By placing tables side-by-side, we eliminate page scrolling
col1, col2, col3 = st.columns([1, 1.4, 1.6])

# Set a strict height for tables so the tables scroll internally, but the web page NEVER scrolls
TABLE_HEIGHT = 650 

with col1:
    st.markdown("##### Pivot View")
    if not filtered_df.empty:
        pivot_df = filtered_df.groupby(['Symbol']).agg(
            Count=('Type', 'count'),
            Max_52W=('52WH', 'max')
        ).reset_index().sort_values(by='Count', ascending=False)
        
        st.dataframe(
            pivot_df,
            height=TABLE_HEIGHT,
            hide_index=True,
            use_container_width=True,
            column_config={"Count": st.column_config.NumberColumn("Hits")}
        )

with col2:
    st.markdown("##### 📈 Master View")
    master_df = filtered_df.drop_duplicates(subset=['Symbol']).sort_values(by='Volume', ascending=False).copy()
    
    if not master_df.empty:
        master_df['Chart'] = "https://in.tradingview.com/chart/?symbol=NSE:" + master_df['Symbol']
        st.dataframe(
            master_df[['Symbol', 'Chart', 'LTP', 'RSI', 'Volume']],
            height=TABLE_HEIGHT,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Chart": st.column_config.LinkColumn("Action", display_text="View"),
                "LTP": st.column_config.NumberColumn("LTP", format="₹%.1f"),
                "RSI": st.column_config.NumberColumn("RSI", format="%.1f")
            }
        )

with col3:
    st.markdown("##### 🚀 Intraday Action")
    if not filtered_df.empty:
        st.dataframe(
            filtered_df[['Symbol', 'Gain', 'LTP', 'DateTime', 'PCR']],
            height=TABLE_HEIGHT,
            hide_index=True,
            use_container_width=True,
            column_config={
                "DateTime": st.column_config.DatetimeColumn("Time", format="HH:mm"),
                "Gain": st.column_config.ProgressColumn("Gain %", format="%.2f%%", min_value=0, max_value=10),
                "LTP": st.column_config.NumberColumn("LTP", format="₹%.1f")
            }
        )

# ==========================================
# GROQ AI ANALYTICS ENGINE (Ultra Compact)
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
