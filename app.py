import streamlit as st
import pandas as pd
import os
import io
from pathlib import Path
from apify_client import ApifyClient

def run_apify_scraper(urls, apify_token, actor_id, campaign_keywords=""):
    client = ApifyClient(apify_token)
    run_input = {
        "start_urls": [{"url": u} for u in urls],
        "max_depth": 1,
        "campaign_keywords": campaign_keywords
    }
    status_text = st.empty()
    status_text.text("Starting Apify Scraper in the cloud...")
    run = client.actor(actor_id).call(run_input=run_input)
    status_text.text("Scraping completed! Downloading dataset...")
    dataset_items = client.dataset(run.default_dataset_id).list_items().items
    status_text.text("Dataset downloaded successfully.")
    return dataset_items

st.set_page_config(page_title="Campaign Intelligence", layout="wide", initial_sidebar_state="expanded")

# Hardcoded Apify Credentials
APIFY_TOKEN = "apify_api_C04MRNhmC8j95ZE4C56f9hUeXRSx1s22t6uu"
APIFY_ACTOR = "unstoppablepm/campaign"

st.title("Campaign Intelligence")

with st.sidebar:
    st.header("1. Campaign Configuration")
    campaign_name = st.text_input("Campaign Name", value="My Campaign")
    campaign_keywords = st.text_input("Campaign Keywords/Hashtags (Comma Separated)", value="coke, coca-cola, cocacola, mantra, cokeambassador", help="Posts must contain at least one of these words to be marked Valid.")
    
    st.header("2. Data Upload")
    uploaded_file = st.file_uploader("Upload Registration Excel (IDs & Links)", type=['xlsx', 'csv'])
    
    # Show column selection immediately if file is uploaded
    reg_id_column = None
    link_column = None
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        uploaded_columns = list(df.columns)
        
        # Auto-detect defaults
        default_link_col = 0
        default_reg_col = 0
        for i, col in enumerate(df.columns):
            if df[col].dropna().astype(str).str.startswith('http').any():
                default_link_col = i
                break
                
        for i, col in enumerate(df.columns):
            if 'regn' in col.lower() or 'id' in col.lower():
                default_reg_col = i
                break
                
        st.markdown("### Select Data Columns")
        reg_id_column = st.selectbox("Registration ID Column", options=uploaded_columns, index=default_reg_col)
        link_column = st.selectbox("LinkedIn Link Column", options=uploaded_columns, index=default_link_col)
    
    st.markdown("---")
    start_run = st.button("Run Pipeline", type="primary")

if start_run:
    if not uploaded_file:
        st.error("Please upload the Excel file.")
        st.stop()
        
    if not APIFY_TOKEN:
        st.error("Please provide the Apify API token in app.py (APIFY_TOKEN variable).")
        st.stop()
        
    # df is already loaded from the sidebar logic above
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Clean and filter to only valid HTTP URLs
    raw_urls = df[link_column].dropna().astype(str).tolist()
    urls = [u for u in raw_urls if u.strip().startswith('http')]
    st.success(f"Found {len(urls)} valid links to process (filtered out {len(raw_urls) - len(urls)} invalid entries).")
    
    st.markdown("### Data Extraction")
    with st.spinner("Scraping data..."):
        try:
            dataset_items = run_apify_scraper(urls, APIFY_TOKEN, APIFY_ACTOR, campaign_keywords)
            st.success(f"Extracted {len(dataset_items)} posts.")
            scraped_df = pd.DataFrame(dataset_items)
        except Exception as e:
            st.error(f"Apify Scraper failed: {str(e)}")
            st.stop()
            
    # Merge the scraped data back onto the original dataframe
    st.info("Merging data...")
    if 'url' in scraped_df.columns:
        # Merge keeping all original rows exactly intact
        df = pd.merge(df, scraped_df, left_on=link_column, right_on='url', how='left')
        
        # Cleanup extra 'url' column from merge if it exists
        if 'url' in df.columns:
            df.drop('url', axis=1, inplace=True)
            
    st.success("Scraping and merging completed!")
    
    # Generate the final Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Final_Results')
    
    st.download_button(
        label="Download Final Results",
        data=buffer.getvalue(),
        file_name=f"{campaign_name.replace(' ', '_')}_Final_Results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
