import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(layout="wide", page_title="Research Document Explorer")

# Constants and setup
VERSION = "1.03.01"
company_link = "company_sample.txt"
mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(mongodb_uri)
database = client["morgan_stanley_research"]
collection = database['research_reports']

# Configure logging
logging.basicConfig(level=logging.INFO)

# App title
st.title("Research Document Explorer")

# Function to load object IDs
def load_object_ids():
    processed_ids_file = Path(f"Results_{VERSION}/processed_ids_{VERSION}.txt")
    
    if not processed_ids_file.exists():
        logging.error(f"Can't find the file {processed_ids_file}")
        return []
    
    object_ids = []
    with open(processed_ids_file, 'r') as f:
        for line in f:
            doc_id = line.strip()
            if doc_id:
                try:
                    object_ids.append(ObjectId(doc_id))
                except Exception as e:
                    logging.warning(f"ID {doc_id} isn't valid: {e}")
    
    return object_ids

# Function to load companies
def load_companies():
    companies = set()
    with open(company_link, 'r') as file:
        for line in file:
            company = line.strip()
            if company:
                companies.add(company)
    return sorted(list(companies))

# Load data
object_ids = load_object_ids()
companies = load_companies()

# Header company selection (instead of sidebar)
selected_company = st.selectbox("Select Company", ["All Companies"] + companies)

# Query MongoDB for documents
query = {
    "_id": {"$in": object_ids},
    "Key_Metrics": {"$exists": True}
}

# If a specific company is selected (not "All Companies"), filter by that company
if selected_company != "All Companies":
    query["company_name"] = selected_company

# Fetch documents from MongoDB
documents = list(collection.find(query))

if not documents:
    st.warning(f"No documents found for the selected criteria.")
else:
    total_docs = len(documents)
    st.success(f"Found {total_docs} documents for {selected_company if selected_company != 'All Companies' else 'all companies'}.")
    
    # Initialize session state for document navigation
    if 'doc_index' not in st.session_state:
        st.session_state.doc_index = 0
    
    # Ensure doc_index is within bounds if documents change
    if st.session_state.doc_index >= total_docs:
        st.session_state.doc_index = 0
    
    # Navigation controls
    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    
    with col1:
        if st.button("← Previous"):
            st.session_state.doc_index = max(0, st.session_state.doc_index - 1)
    
    with col2:
        if st.button("Next →"):
            st.session_state.doc_index = min(total_docs - 1, st.session_state.doc_index + 1)
    
    with col3:
        st.metric("Document", f"{st.session_state.doc_index + 1} of {total_docs}")
    
    with col4:
        # Direct document selection
        new_index = st.number_input("Go to #", min_value=1, max_value=total_docs, 
                                    value=st.session_state.doc_index + 1) - 1
        if new_index != st.session_state.doc_index:
            st.session_state.doc_index = new_index
    
    # Get the current document
    current_doc = documents[st.session_state.doc_index]
    
    # Display document info
    doc_title = current_doc.get('title', 'No Title')
    st.subheader(f"{doc_title}")
    
    # Document metadata
    doc_info_col1, doc_info_col2, doc_info_col3 = st.columns(3)
    with doc_info_col1:
        st.info(f"**Company:** {current_doc.get('company_name', 'Unknown')}")
    with doc_info_col2:
        st.info(f"**Date:** {current_doc.get('timestamp', 'Unknown')}")
    with doc_info_col3:
        doc_id = current_doc.get('_id', 'Unknown')
        st.info(f"**ID:** {str(doc_id)[:10]}...")
    
    # Create split screen layout
    left_col, right_col = st.columns([1, 1])
    
    # Left column - PDF Viewer
    with left_col:
        st.subheader("Document PDF")
        pdf_url = current_doc.get("pdf_url", "")
        if pdf_url:
            # Add http:// prefix if not present
            full_url = f"http://{pdf_url}" if not pdf_url.startswith("http") else pdf_url
            
            # Embed PDF viewer
            pdf_display = f"""
            <div style="border: 1px solid #ddd; border-radius: 5px; padding: 5px;">
                <iframe
                    src="{full_url}"
                    width="100%"
                    height="700"
                    style="border: none;"
                ></iframe>
            </div>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Fallback link
            st.markdown(f"[Open PDF in new tab]({full_url})")
            
        else:
            st.error("No PDF URL available for this document.")
    
    # Right column - Metrics display
    with right_col:
        st.subheader("Key Metrics")
        
        if "Key_Metrics" in current_doc and current_doc["Key_Metrics"]:
            metrics = current_doc["Key_Metrics"]
            
            # Search functionality for metrics
            metric_search = st.text_input("Search metrics", "")
            
            # Filter metrics based on search
            if metric_search:
                filtered_metrics = {k: v for k, v in metrics.items() 
                                  if metric_search.lower() in k.lower()}
            else:
                filtered_metrics = metrics
            
            # Display metrics count
            st.write(f"Showing {len(filtered_metrics)} of {len(metrics)} metrics")
            
            # Display metrics in expandable sections
            if filtered_metrics:
                for metric_name in sorted(filtered_metrics.keys()):
                    metric_data = filtered_metrics[metric_name]
                    
                    with st.expander(f"{metric_name}", expanded=True):
                        # Value
                        if "Value" in metric_data and metric_data["Value"]:
                            st.info(f"**Value:** {metric_data['Value']}")
                        
                        # Explanation
                        if "Explanation" in metric_data and metric_data["Explanation"]:
                            st.success(f"**Explanation:** {metric_data['Explanation']}")
                        
                        # Description
                        if "Description" in metric_data and metric_data["Description"]:
                            st.markdown(f"**Description:** {metric_data['Description']}")
            else:
                st.warning("No metrics match your search term.")
        else:
            st.warning("No key metrics data available for this document.")
