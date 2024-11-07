import streamlit as st
import json
import os
from supabase import create_client
from analyze_results import analyze_evaluations
from datetime import datetime
import pandas as pd
import io

class ClusterComparator:
    def __init__(self):
        self.v1_labels = {}
        self.gpt4_labels = {}
        self.java_sentences = {}
        self.clusters_data = {}
        self.current_cluster_index = 0
        self.cluster_ids = []
        
        # Connect to Supabase
        self.supabase = create_client(
            "https://jfnrbqmcaqrydpqubqjr.supabase.co",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmbnJicW1jYXFyeWRwcXVicWpyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzA4Mjk2MjMsImV4cCI6MjA0NjQwNTYyM30.GOUJFOoCaPdkIPHrqtGg350ZsyYQA0PJrVGQqygG3cc"
        )
        self.create_table()
        self.evaluations = self.load_progress()
        self.base_path = os.getcwd()
        
    def create_table(self):
        # Supabase tables are created in the dashboard, not in code
        # You'll need to create a table named 'evaluations' with columns:
        # cluster_id (text, primary key)
        # last_cluster_index (int)
        # acceptability (text)
        # precision (text)
        # quality (text)
        # notes (text)
        pass
        
    def load_progress(self):
        try:
            response = self.supabase.table('evaluations').select("*").execute()
            evaluations = {}
            for row in response.data:
                evaluations[row['cluster_id']] = {
                    'last_cluster_index': row['last_cluster_index'],
                    'acceptability': row['acceptability'],
                    'precision': row['precision'],
                    'quality': row['quality'],
                    'notes': row['notes']
                }
            return evaluations
        except Exception as e:
            st.error(f"Error loading evaluations: {str(e)}")
            return {}

    def save_progress(self, cluster_id, evaluation):
        try:
            eval_data = {
                'cluster_id': cluster_id,
                'last_cluster_index': st.session_state.current_index,
                'prompt_engineering_helped': evaluation['prompt_engineering_helped'] == 'Yes',
                'syntactic_superior': evaluation['syntactic_superior'] == 'Yes',
                'semantic_superior': evaluation['semantic_superior'] == 'Yes',
                'error_description': evaluation.get('error_description', ''),
                'syntactic_error_notes': evaluation.get('syntactic_notes', ''),
                'semantic_error_notes': evaluation.get('semantic_notes', ''),
                'created_at': datetime.now().isoformat()
            }
            
            self.supabase.table('evaluations').upsert(eval_data).execute()
            return True
            
        except Exception as e:
            st.error(f"Error saving evaluation: {str(e)}")
            return False

    def load_data(self):
        v1_labels_path = os.path.join(self.base_path, 'Labels_and_tags_V1.json')
        with open(v1_labels_path, 'r') as f:
            self.v1_labels = json.load(f)
                
        gpt4_labels_path = os.path.join(self.base_path, 'GPT4o_Layer12_labels.json')
        with open(gpt4_labels_path, 'r') as f:
            self.gpt4_labels = json.load(f)
            
        java_path = os.path.join(self.base_path, 'java.in')
        with open(java_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                self.java_sentences[i] = line.strip()
                
        clusters_path = os.path.join(self.base_path, 'clusters-500.txt')
        with open(clusters_path, 'r') as f:
            for line in f:
                stripped_line = line.strip()
                pipe_count = stripped_line.count('|')

                # Handle special token cases
                if pipe_count == 13:
                    token = '|'
                elif pipe_count == 14:
                    token = '||'
                elif pipe_count == 12:
                    parts = stripped_line.split('|||')
                    token = parts[0]
                else:
                    continue  # Skip invalid lines

                parts = stripped_line.split('|||')
                line_number = int(parts[2])
                cluster_id = parts[4].split()[-1]
                
                if cluster_id not in self.clusters_data:
                    self.clusters_data[cluster_id] = []
                self.clusters_data[cluster_id].append(line_number)
        
        self.cluster_ids = sorted(list(set(self.clusters_data.keys())), 
                                key=lambda x: int(x) if x.isdigit() else float('inf'))
        
def find_next_unevaluated_cluster(comparator, start_index=0, batch_size=50):
    """Find the next unevaluated cluster within the user's assigned batch"""
    fresh_evaluations = comparator.load_progress()
    evaluated_cluster_ids = set(fresh_evaluations.keys())
    
    # Calculate batch boundaries
    batch_number = start_index // batch_size
    batch_start = batch_number * batch_size
    batch_end = (batch_number + 1) * batch_size
    
    # Only search within the current batch
    for i in range(start_index, min(batch_end, len(comparator.cluster_ids))):
        if comparator.cluster_ids[i] not in evaluated_cluster_ids:
            return i
            
    # If no unevaluated clusters found, find the last evaluated cluster in this batch
    for i in range(min(batch_end - 1, len(comparator.cluster_ids) - 1), batch_start - 1, -1):
        if comparator.cluster_ids[i] in evaluated_cluster_ids:
            return i
            
    # If no clusters found at all, return batch start
    return batch_start

def main():
    # Configure page with custom theme and wider layout
    st.set_page_config(
        layout="wide",
        page_title="Cluster Label Comparison Tool",
        page_icon="🔍",
        initial_sidebar_state="expanded"
    )
    
    # Enhanced CSS styling
    st.markdown("""
        <style>
        /* Global Styles */
        .stApp {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Header Styles */
        .main-header {
            text-align: center;
            color: #1e3d59;
            padding: 1.5rem 0;
            margin-bottom: 2rem;
            border-bottom: 3px solid #f5f5f5;
            font-family: 'Helvetica Neue', sans-serif;
        }
        
        /* Card Styles */
        .stat-card {
            background-color: white;
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #e0e0e0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            text-align: center;
            transition: transform 0.2s ease;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Section Headers */
        .section-header {
            color: #1e3d59;
            margin: 2rem 0 1rem 0;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid #f5f5f5;
            font-weight: 600;
        }
        
        /* Button Styles */
        .stButton>button {
            width: 100%;
            padding: 0.75rem 1.5rem;
            background-color: #1e3d59;
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            background-color: #2b4f76;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Radio Button Styling */
        .stRadio > div {
            background-color: #f8f9fa;
            padding: 1.25rem;
            border-radius: 10px;
            margin: 0.75rem 0;
            border: 1px solid #e0e0e0;
        }
        
        /* Text Area Styling */
        .stTextArea > div > div {
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            background-color: white;
        }
        
        /* Code Block Styling */
        .code-block {
            background-color: #f8f9fa;
            padding: 1.25rem;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            font-family: 'Monaco', monospace;
        }
        
        /* Sidebar Styling */
        .css-1d391kg {
            background-color: #f8f9fa;
            padding: 1rem;
            border-right: 1px solid #e0e0e0;
        }
        
        /* Progress Bar */
        .stProgress > div > div > div {
            background-color: #1e3d59;
        }
        
        /* Tables */
        .dataframe {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
        }
        .dataframe th {
            background-color: #f8f9fa;
            padding: 0.75rem !important;
        }
        .dataframe td {
            padding: 0.75rem !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background-color: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        </style>
    """, unsafe_allow_html=True)

    # Main title with enhanced styling
    st.markdown('<h1 class="main-header">🔍 Cluster Label Comparison Tool</h1>', unsafe_allow_html=True)

    # Download button with improved styling
    if 'comparator' in st.session_state:
        evaluations = st.session_state.comparator.load_progress()
        if evaluations:
            df = pd.DataFrame(evaluations).T
            json_str = df.to_json(orient='index', indent=2)
            
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                st.download_button(
                    label="📥 Download Evaluations",
                    data=json_str,
                    file_name="cluster_evaluations.json",
                    mime="application/json",
                    help="Download your evaluation results as a JSON file",
                )

    # Enhanced Instructions section
    with st.expander("📖 Instructions & Guidelines", expanded=not st.session_state.instructions_acknowledged):
        st.markdown("""
        <div style='background-color: white; padding: 2rem; border-radius: 12px; border: 1px solid #e0e0e0;'>
            <h3 style='color: #1e3d59; margin-bottom: 1.5rem;'>How to Use This Tool</h3>
            
            <div style='background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 1rem 0;'>
                <h4 style='color: #1e3d59;'>🎯 Evaluation Goals</h4>
                <ul>
                    <li>Analyze prompt engineering effectiveness</li>
                    <li>Identify and document unacceptable labels</li>
                    <li>Compare GPT-4o outputs with human labels</li>
                </ul>
            </div>

            <div style='background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin: 1rem 0;'>
                <h4 style='color: #1e3d59;'>📝 Evaluation Process</h4>
                <ul>
                    <li>Review cluster tokens and context</li>
                    <li>Compare V1 vs GPT-4o labels</li>
                    <li>Assess label quality and accuracy</li>
                </ul>
            </div>

            <div style='background-color: #fff3cd; padding: 1.5rem; border-radius: 10px; margin: 1rem 0;'>
                <h4 style='color: #856404;'>⚠️ Important Notes</h4>
                <ul>
                    <li>Focus on before/after prompt engineering comparison</li>
                    <li>V1 used basic prompting</li>
                    <li>Evaluate labeling coverage improvements</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Enhanced Stats display
    if st.session_state.instructions_acknowledged and 'comparator' in st.session_state:
        comparator = st.session_state.comparator
        fresh_evaluations = comparator.load_progress()
        evaluated_clusters = len(fresh_evaluations)
        
        progress_percentage = (evaluated_clusters / 500) * 100

        st.markdown('<h3 class="section-header">📊 Progress Overview</h3>', unsafe_allow_html=True)
        
        # Progress bar
        st.progress(progress_percentage / 100)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
                <div class="stat-card">
                    <h4 style="color: #666;">Total Clusters</h4>
                    <h2 style="color: #1e3d59; margin: 0;">{len(comparator.cluster_ids)}</h2>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div class="stat-card">
                    <h4 style="color: #666;">Evaluated</h4>
                    <h2 style="color: #1e3d59; margin: 0;">{evaluated_clusters}</h2>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div class="stat-card">
                    <h4 style="color: #666;">Remaining</h4>
                    <h2 style="color: #1e3d59; margin: 0;">{500 - evaluated_clusters}</h2>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
                <div class="stat-card">
                    <h4 style="color: #666;">Current Cluster</h4>
                    <h2 style="color: #1e3d59; margin: 0;">{st.session_state.current_index}</h2>
                </div>
            """, unsafe_allow_html=True)

        # Rest of your existing comparison code...
        st.markdown('<h3 class="section-header">🔄 Label Comparison</h3>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
