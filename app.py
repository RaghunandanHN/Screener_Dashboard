import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# ==========================================
# PAGE CONFIGURATION & AUTO-REFRESH
# ==========================================
st.set_page_config(page_title="HNR Momentum Dashboard", page_icon="📈", layout="wide")

# Auto-refresh the app every 5 minutes (300,000 milliseconds)
st_autorefresh(interval=300000, key="datarefresh")

# ==========================================
# DATA LOADING ENGINE
# ==========================================
@st.cache_data(ttl=300) # Cache clears every 5 mins
def load_data():
    url = "https://docs.google.com/spreadsheets/d/12RfTgNRrePMfoIn9N2pQnQtoiVCftd7m3hJGHjOtxmc/export?format=csv"
    try:
        df = pd.read_csv(url)
        # Assuming standard naming, adjust these based on your exact sheet headers if needed.
        # From your previous script, Col 0 is Ticker, Col 5 is Screen, Col 12 is Date.
        # Let's standardize column names for the dashboard.
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Failed to load data from Google Sheets: {e}")
        return pd.DataFrame()

df = load_data()

# ==========================================
# SIDEBAR FILTERS
# ==========================================
st.sidebar.title("⚙️ Control Panel")
st.sidebar.write(f"**Last Updated:** {datetime.now().strftime('%H:%M:%S IST')}")

if not df.empty:
    # Identify the 'Category/Screen' column (assuming it contains 'bullish' keywords)
    # Fallback to column index 5 if standard naming isn't found
    screen_col = 'screen' if 'screen' in df.columns else df.columns[5]
    date_col = 'date' if 'date' in df.columns else df.columns[12]
    ticker_col = 'ticker' if 'ticker' in df.columns else df.columns[0]

    # Filter: Categories (Bullish50, Bullish500, etc.)
    categories = df[screen_col].dropna().unique().tolist()
    selected_categories = st.sidebar.multiselect("Filter by Category", categories, default=categories[:2] if len(categories)>1 else categories)

    # Apply Filter
    filtered_df = df[df[screen_col].isin(selected_categories)]

    # ==========================================
# MAIN DASHBOARD UI
# ==========================================
st.title("🚀 HNR Real-Time Momentum Dashboard")

if not df.empty:
    # --- Metrics Section ---
    st.markdown("### 📊 Market Overview")
    col1, col2, col3 = st.columns(3)
    
    total_scanned = len(df)
    total_filtered = len(filtered_df)
    
    # 2-Day Lookback Logic
    df[date_col] = pd.to_datetime(df[date_col], format="%d-%m-%Y", errors='coerce') # Adjust format if needed
    two_days_ago = pd.Timestamp.now().normalize() - timedelta(days=2)
    recent_trenders = df[df[date_col] >= two_days_ago]
    
    col1.metric("Total Stocks Scanned", total_scanned)
    col2.metric("Stocks in Selected Categories", total_filtered)
    col3.metric("Trending Last 48 Hrs", len(recent_trenders))

    # --- Data Visuals ---
    st.markdown("### 📋 Filtered Screen Results")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # --- 2-Day Trend Analysis ---
    st.markdown("### 🔥 High-Conviction (Last 2 Days)")
    st.write("Stocks that have appeared in the screener multiple times over the last 48 hours, indicating sustained momentum.")
    
    if not recent_trenders.empty:
        # Count occurrences of each ticker in the last 2 days
        trend_counts = recent_trenders[ticker_col].value_counts().reset_index()
        trend_counts.columns = ['Ticker', 'Occurrences']
        trend_counts = trend_counts[trend_counts['Occurrences'] > 1] # Show only those appearing more than once
        
        if not trend_counts.empty:
            st.bar_chart(data=trend_counts.set_index('Ticker'))
        else:
            st.info("No stocks have repeated in the screener over the last 48 hours.")
    
    # ==========================================
    # GROQ AI ANALYTICS ENGINE
    # ==========================================
    st.markdown("---")
    st.markdown("### 🧠 AI Intuitive Suggestions")
    st.write("Generate unique trading patterns and suggestions based on today's current spreadsheet data.")
    
    if st.button("Generate AI Market Intelligence"):
        with st.spinner("Groq Llama-3.3 is analyzing the sheet..."):
            # Prepare a summary of the data to send to the AI
            data_summary = filtered_df[[ticker_col, screen_col]].head(20).to_string()
            
            prompt = f"""
            Act as a Senior Quant Analyst. Look at this snapshot of currently trending Indian stocks from my momentum screener:
            
            {data_summary}
            
            Based strictly on these groupings (e.g., bullish50, bullish500), provide:
            1. An intuitive pattern you notice in the sectors or types of stocks moving right now.
            2. Does it make sense to take long positions in the broader market today based on this list?
            3. 2 unique trading suggestions or risk-management warnings.
            
            Keep it concise, plain text, and highly actionable.
            """
            
            try:
                # Using your Groq Key from the previous setup
                groq_key = "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" 
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }
                response = requests.post(url, headers=headers, json=payload, timeout=20)
                
                if response.status_code == 200:
                    ai_response = response.json()['choices'][0]['message']['content']
                    st.success("Analysis Complete")
                    st.write(ai_response)
                else:
                    st.error("AI Engine failed to respond.")
            except Exception as e:
                st.error(f"Error connecting to AI: {str(e)}")

else:
    st.warning("Awaiting data from Google Sheets...")