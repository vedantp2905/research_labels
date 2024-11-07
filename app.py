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
        
def find_next_unevaluated_cluster(comparator, start_index=0, batch_size=100):
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
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")
    
    # Add download button at the top
    if 'comparator' in st.session_state:
        evaluations = st.session_state.comparator.load_progress()
        if evaluations:
            df = pd.DataFrame(evaluations).T
            json_str = df.to_json(orient='index', indent=2)
            
            st.download_button(
                label="Download Evaluated Clusters (JSON)",
                data=json_str,
                file_name="cluster_evaluations.json",
                mime="application/json",
            )
    
    # Initialize acknowledgment state if not exists
    if 'instructions_acknowledged' not in st.session_state:
        st.session_state.instructions_acknowledged = False
    
    # Add instructions with checkbox
    with st.expander("📖 Instructions", expanded=not st.session_state.instructions_acknowledged):
        st.markdown("""
        ### How to Use This Tool

        1. **Evaluation Goals**
           - Analyze if prompt engineering has helped improve LLM labels
           - Compare quality of GPT-4o labels with human labels
           
        2. **For Each Cluster**
           - Review the tokens and their context
           - Compare V1 (before prompt engineering) vs GPT-4o (after) labels
           - Compare GPT-4o labels with human labels
           
        3. **Evaluation Criteria**
           - Prompt Engineering Impact: Has it helped convert previously unacceptable labels to acceptable ones?
           - Syntactic Superiority: Is GPT-4o's syntactic label better than the human label?
           - Semantic Superiority: Are GPT-4o's semantic tags better than human tags? (≥3/5 tags should be better)
           
        4. **Error Analysis**
           - Document specific improvements in error cases
           - Note any remaining issues
           

        ⚠️ **Important**: Focus on comparing before/after prompt engineering and against human labels
        """)
        
        # Add checkbox at the bottom of instructions
        acknowledged = st.checkbox(
            "I have read and understood the instructions",
            value=st.session_state.instructions_acknowledged,
            key="acknowledge_checkbox"
        )
        
        if acknowledged != st.session_state.instructions_acknowledged:
            st.session_state.instructions_acknowledged = acknowledged
            st.rerun()
    
    # Only show the main content if instructions are acknowledged
    if st.session_state.instructions_acknowledged:
        # Initialize the comparator and rest of the main content
        if 'comparator' not in st.session_state:
            st.session_state.comparator = ClusterComparator()
            st.session_state.comparator.load_data()
            
            # Get all evaluations
            evaluations = st.session_state.comparator.load_progress()
            
            # Find the highest cluster index that has been evaluated
            if evaluations:
                last_evaluated_index = max(
                    st.session_state.comparator.cluster_ids.index(cluster_id)
                    for cluster_id in evaluations.keys()
                )
                # Start from the next unevaluated cluster
                st.session_state.current_index = last_evaluated_index + 1
            else:
                # If no evaluations exist, start from 0
                st.session_state.current_index = 0
                
        if 'batch_number' not in st.session_state:
            st.session_state.batch_number = 0
            
        # Add batch selector in the sidebar
        with st.sidebar:
            st.header("Batch Selection")
            batch_size = 100
            total_batches = (len(st.session_state.comparator.cluster_ids) + batch_size - 1) // batch_size
            
            new_batch = st.selectbox(
                "Select your batch (100 clusters each)",
                range(total_batches),
                index=st.session_state.batch_number,
                format_func=lambda x: f"Batch {x} (clusters {x*100}-{min((x+1)*100-1, len(st.session_state.comparator.cluster_ids)-1)})"
            )
            
            if new_batch != st.session_state.batch_number:
                st.session_state.batch_number = new_batch
                # Find the last evaluated cluster in the new batch or start at beginning of batch
                batch_start = new_batch * batch_size
                next_index = find_next_unevaluated_cluster(st.session_state.comparator, batch_start)
                st.session_state.current_index = next_index
                st.rerun()

        comparator = st.session_state.comparator

        # Fetch fresh evaluations data for the count
        fresh_evaluations = comparator.load_progress()
        evaluated_clusters = len(fresh_evaluations)

        col1, col2, col3 = st.columns([1,1,1])
        
        with col1:
            st.write(f"Total clusters: {len(comparator.cluster_ids)}")
        with col2:
            st.write(f"Clusters remaining: {500 - evaluated_clusters}")
        with col3:
            st.write(f"Current cluster Number: {st.session_state.current_index}")

        # Check if current cluster is already evaluated
        current_cluster = comparator.cluster_ids[st.session_state.current_index]
        fresh_evaluations = comparator.load_progress()
        
        if current_cluster in fresh_evaluations:
            # Find next unevaluated cluster
            next_index = find_next_unevaluated_cluster(comparator, st.session_state.current_index)
            if next_index is not None:
                st.session_state.current_index = next_index
                st.rerun()
            else:
                st.success("All clusters have been evaluated!")
                st.stop()

        # Store the time when we start viewing this cluster
        if 'evaluation_start_time' not in st.session_state:
            st.session_state.evaluation_start_time = datetime.now().isoformat()
        
        # Reset the start time when moving to a new cluster
        if 'last_viewed_cluster' not in st.session_state or st.session_state.last_viewed_cluster != current_cluster:
            st.session_state.evaluation_start_time = datetime.now().isoformat()
            st.session_state.last_viewed_cluster = current_cluster

        if current_cluster in comparator.clusters_data:
            # Replace the token extraction logic with direct access from GPT4o labels
            current_cluster_key = f"c{current_cluster}"
            gpt4_cluster = next((item[current_cluster_key] for item in comparator.gpt4_labels 
                               if current_cluster_key in item), {})
            
            tokens = gpt4_cluster.get("Unique tokens", [])
            
            st.header("Unique Tokens")
            st.write(", ".join(sorted(tokens)) if tokens else "No tokens found")
            st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.header("CodeConceptNet-V1 Labels")
            current_cluster_key = str(current_cluster)
            if current_cluster_key in comparator.v1_labels:
                # Display additional fields from V1 labels
                v1_label_data = comparator.v1_labels[current_cluster_key]
                st.write("LLM Label:", v1_label_data.get("Labels", ["N/A"])[0])
                
                # Display Semantic one below the other
                semantic_tags = v1_label_data.get("Semantic", "").split(", ")  # Split by comma for individual tags
                if semantic_tags:
                    st.write("Human Semantic Tags:")
                    for tag in semantic_tags:
                        st.write(f"- {tag}")  # Display each tag on a new line
                else:
                    st.write("Semantic Tags: N/A")  # If no tags are present
                
                st.write("Human Syntactic Label:", v1_label_data.get("Syntactic", "N/A"))
                st.write("Human Description:", v1_label_data.get("Description", "N/A"))
        
        with col2:
            st.header("GPT-4o Labels")
            gpt4_cluster_key = f"c{current_cluster}"
            gpt4_cluster = next((item[gpt4_cluster_key] for item in comparator.gpt4_labels 
                               if gpt4_cluster_key in item), {})
            st.write("LLM Syntactic Label:", gpt4_cluster.get("Syntactic Label", "N/A"))
            
            # Display Semantic Tags one below the other
            semantic_tags = gpt4_cluster.get("Semantic Tags", [])
            if semantic_tags:
                st.write("LLM Semantic Tags:")
                for tag in semantic_tags:
                    st.write(f"- {tag}")  # Display each tag on a new line
            else:
                st.write("Semantic Tags: N/A")  # If no tags are present
            
            st.write("LLM Description:", gpt4_cluster.get("Description", "N/A"))

        
        with col3:
            st.header("Evaluation")
            
            prompt_engineering_helped = st.radio(
                "Has prompt engineering helped improve previously unacceptable labels?",
                ["N/A", "Yes", "No"],
                key=f"prompt_engineering_{current_cluster}"
            )
            
            if prompt_engineering_helped == "No":
                error_description = st.text_area(
                    "Describe the remaining issues:",
                    key=f"error_description_{current_cluster}"
                )
            
            st.header("Comparison with Human Labels")
            
            syntactic_superior = st.radio(
                "Is GPT-4o's syntactic label superior to the human label?",
                ["Yes", "No"],
                key=f"syntactic_superior_{current_cluster}"
            )
            
            if syntactic_superior == "Yes":
                syntactic_notes = st.text_area(
                    "Provide examples of superiority:",
                    key=f"syntactic_notes_{current_cluster}"
                )
            
            semantic_superior = st.radio(
                "Are GPT-4o's semantic tags superior to human tags? (≥3/5 tags)",
                ["Yes", "No"],
                key=f"semantic_superior_{current_cluster}"
            )
            
            if semantic_superior == "Yes":
                semantic_notes = st.text_area(
                    "Provide examples of superiority:",
                    key=f"semantic_notes_{current_cluster}"
                )

        # Move submit button here, after the columns but before the sentences section
        if st.button("Submit Evaluation", key=f"submit_{current_cluster}"):
            evaluation = {
                'prompt_engineering_helped': prompt_engineering_helped,
                'syntactic_superior': syntactic_superior,
                'semantic_superior': semantic_superior,
                'error_description': error_description if prompt_engineering_helped == "No" else "",
                'syntactic_notes': syntactic_notes if syntactic_superior == "Yes" else "",
                'semantic_notes': semantic_notes if semantic_superior == "Yes" else ""
            }
            
            if comparator.save_progress(current_cluster, evaluation):
                st.success("Evaluation saved successfully!")
                # Find next unevaluated cluster
                next_index = find_next_unevaluated_cluster(comparator, st.session_state.current_index)
                if next_index is not None:
                    st.session_state.current_index = next_index
                    st.rerun()
                else:
                    st.success("All clusters in this batch have been evaluated!")
            else:
                st.error("Failed to save evaluation")

        # Display code examples section
        st.header("Sentences where the token appears")
        if current_cluster in comparator.clusters_data:
            token_positions = {}
            with open(os.path.join(comparator.base_path, 'clusters-500.txt'), 'r') as f:
                for line in f:
                    parts = line.strip().split('|||')
                    if len(parts) >= 5 and parts[4] == str(current_cluster):
                        line_num = int(parts[2])
                        if line_num not in token_positions:
                            token_positions[line_num] = []
                        token_positions[line_num].append({
                            'token': parts[0],
                            'column': int(parts[3])
                        })
                
            for sentence_id in comparator.clusters_data[current_cluster]:
                if sentence_id in comparator.java_sentences:
                    sentence = comparator.java_sentences[sentence_id]
                    st.code(sentence, language="java")
    else:
        st.warning("Please read the instructions and check the acknowledgment box to continue.")
        st.stop()

if __name__ == "__main__":
    main()
