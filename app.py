import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import requests
import os

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="HNR Advanced Command Center", page_icon="🏛️", layout="wide")
st_autorefresh(interval=300000, key="datarefresh") # 5 Min Auto-Refresh

# Custom CSS to mimic Looker's tight, compact layout
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
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
        # Clean column names to string and strip spaces
        df.columns = df.columns.astype(str).str.strip()
        
        # Mapping to match your Looker Dashboard columns (Adjust exact names if needed)
        # Assuming your sheet has columns somewhat similar to the image
        if 'Ticker' in df.columns and 'Symbol' not in df.columns:
            df.rename(columns={'Ticker': 'Symbol'}, inplace=True)
        if 'Screen' in df.columns and 'Type' not in df.columns:
            df.rename(columns={'Screen': 'Type'}, inplace=True)
            
        # Ensure Date is datetime
        date_col = 'Date' if 'Date' in df.columns else df.columns[12]
        df['DateTime'] = pd.to_datetime(df[date_col], errors='coerce')
        
        # Fill missing numeric columns for visual stability
        numeric_cols = ['LTP', 'Gain', 'Volume', 'RSI', '52WH', 'PCR']
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = 0.0 # Placeholder if column missing in CSV
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
st.sidebar.title("⚙️ Global Filters")

# 1. Date Range Picker
min_date = df['DateTime'].min().date() if not pd.isna(df['DateTime'].min()) else datetime.today().date()
max_date = df['DateTime'].max().date() if not pd.isna(df['DateTime'].max()) else datetime.today().date()
date_selection = st.sidebar.date_input("Date Range", [min_date, max_date])

# Apply Date Filter
if len(date_selection) == 2:
    start_date, end_date = date_selection
    mask = (df['DateTime'].dt.date >= start_date) & (df['DateTime'].dt.date <= end_date)
    filtered_df = df.loc[mask]
else:
    filtered_df = df.copy()

# 2. Type/Screen Multi-Select with Record Counts (Mimicking Looker Left Panel)
st.sidebar.markdown("### Filter by Type (Screen)")
type_counts = filtered_df['Type'].value_counts()
type_options = type_counts.index.tolist()

# Create a custom display string like "Nifty 50 Bullish (162)"
format_func = lambda x: f"{x} ({type_counts[x]})"
selected_types = st.sidebar.multiselect("Select Categories:", type_options, default=type_options[:2] if len(type_options)>1 else type_options, format_func=format_func)

filtered_df = filtered_df[filtered_df['Type'].isin(selected_types)]

# ==========================================
# MAIN DASHBOARD LAYOUT (5 SECTIONS)
# ==========================================
st.title("HNR Institutional Command Center")

# --- SECTION 1: TOP KPI BANNER ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Records", len(filtered_df))
col2.metric("Unique Symbols", filtered_df['Symbol'].nunique())
col3.metric("Avg RSI", f"{filtered_df['RSI'].mean():.1f}")
col4.metric("High Volume Movers", len(filtered_df[filtered_df['Volume'] > filtered_df['Volume'].mean()]))

st.divider()

# Split screen into Left (1/3) and Right (2/3) to mimic the image
left_col, right_col = st.columns([1, 2.5])

with left_col:
    # --- SECTION 2: LEFT PIVOT TABLE ---
    st.markdown("##### Type / Record Count Pivot")
    if not filtered_df.empty:
        # Replicating the bottom left pivot table from your image
        pivot_df = filtered_df.groupby(['Symbol']).agg(
            Count=('Type', 'count'),
            Max_52W=('52WH', 'max')
        ).reset_index().sort_values(by='Count', ascending=False)
        
        st.dataframe(
            pivot_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Count": st.column_config.NumberColumn("Hits", help="Times appeared in screen"),
                "Max_52W": st.column_config.NumberColumn("52WH", format="₹%.1f")
            }
        )
    
    # --- SECTION 3: MOMENTUM MATRIX (The "Beyond" Factor) ---
    st.markdown("##### Momentum Matrix")
    st.caption("RSI vs Gain (Bubble Size = Volume)")
    if not filtered_df.empty:
        fig = px.scatter(
            filtered_df.drop_duplicates(subset=['Symbol']), 
            x="RSI", y="Gain", size="Volume", color="Type", hover_name="Symbol",
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with right_col:
    # --- SECTION 4: MASTER VIEW WITH LIVE LINKS ---
    st.markdown("##### 📈 Institutional Master View")
    # Taking top unique stocks by volume
    master_df = filtered_df.drop_duplicates(subset=['Symbol']).sort_values(by='Volume', ascending=False).head(20)
    
    st.dataframe(
        master_df[['Symbol', 'LTP', 'Volume', 'RSI', '52WH', 'PCR']],
        hide_index=True,
        use_container_width=True,
        column_config={
            # This creates a clickable TradingView URL directly inside the table
            "Symbol": st.column_config.LinkColumn(
                "Symbol (Click for Chart)", 
                display_text="^([A-Z0-9]+)$", 
                url="https://in.tradingview.com/chart/?symbol=NSE:^([A-Z0-9]+)$"
            ),
            "LTP": st.column_config.NumberColumn("LTP", format="₹%.2f"),
            "Volume": st.column_config.NumberColumn("Volume"),
            "RSI": st.column_config.NumberColumn("RSI", format="%.2f"),
        }
    )

    st.markdown("##### 🚀 Intraday Action & Gains")
    # --- SECTION 5: INTRADAY VIEW WITH INLINE PROGRESS BARS ---
    # Replicating the bottom right table with the green inline bars
    st.dataframe(
        filtered_df[['Symbol', 'LTP', 'Gain', 'Volume', 'DateTime', 'RSI', 'PCR']],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol"),
            "DateTime": st.column_config.DatetimeColumn("Date/Time", format="DD-MMM HH:mm"),
            # Replicating the exact green progress bar from Looker
            "Gain": st.column_config.ProgressColumn(
                "Gain %", 
                help="Intraday Gain", 
                format="%.2f%%", 
                min_value=0, 
                max_value=10 # Assuming 10% is upper circuit for visual scaling
            ),
            "RSI": st.column_config.NumberColumn("RSI", format="%.2f"),
        }
    )

# ==========================================
# GROQ AI ANALYTICS ENGINE (Bottom Expandable)
# ==========================================
st.divider()
with st.expander("🧠 Deep-Dive AI Analytics (Groq Llama 3.3)"):
    if st.button("Analyze Current Matrix"):
        with st.spinner("Analyzing current dataframe..."):
            prompt = f"""
            Act as a Senior Quant Analyst for NSE India. 
            Here is the top data from my current screener dashboard:
            {master_df[['Symbol', 'RSI', 'Gain', 'Volume']].head(15).to_string()}
            
            1. What immediate sector or volume pattern stands out?
            2. Which 2 stocks show the most asymmetric risk/reward based on this RSI and Gain?
            3. Provide a strict risk management warning for this specific setup.
            """
            try:
                # Use your Groq API Key
                groq_key = "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" 
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]}
                response = requests.post(url, headers=headers, json=payload, timeout=20)
                
                if response.status_code == 200:
                    st.write(response.json()['choices'][0]['message']['content'])
                else:
                    st.error("AI Engine failed to respond.")
            except Exception as e:
                st.error(f"Error connecting to AI: {str(e)}")
