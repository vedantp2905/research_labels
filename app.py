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
                    'prompt_engineering_helped': row['prompt_engineering_helped'],
                    'syntactic_superior': row['syntactic_superior'],
                    'semantic_superior': row['semantic_superior'],
                    'error_description': row['error_description'],
                    'syntactic_error_notes': row['syntactic_error_notes'],
                    'semantic_error_notes': row['semantic_error_notes']
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
                'prompt_engineering_helped': evaluation['prompt_engineering_helped'],
                'syntactic_superior': evaluation['syntactic_superior'],
                'semantic_superior': evaluation['semantic_superior'],
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

def calculate_evaluation_stats(evaluations):
    """Calculate statistics for evaluation criteria"""
    total = len(evaluations)
    if total == 0:
        return pd.DataFrame()
    
    # Count unacceptable cases from V1
    unacceptable_count = 0
    improved_count = 0
    
    # Initialize counters for superiority
    syntactic_v1_better = 0
    syntactic_gpt4_better = 0
    semantic_v1_better = 0
    semantic_gpt4_better = 0
    
    for cluster_id, eval_data in evaluations.items():
        # Get V1 acceptability for this cluster
        v1_data = st.session_state.comparator.v1_labels.get(cluster_id, {})
        is_unacceptable = v1_data.get('Q1_Answer', '').lower() == 'unacceptable'
        
        if is_unacceptable:
            unacceptable_count += 1
            if eval_data.get('prompt_engineering_helped') == 'Yes':
                improved_count += 1
        
        # Count syntactic superiority
        syn_value = eval_data.get('syntactic_superior', 'No')
        if syn_value == 'Yes':
            syntactic_gpt4_better += 1
        elif syn_value == 'No':
            syntactic_v1_better += 1
        
        # Count semantic superiority
        sem_value = eval_data.get('semantic_superior', 'No')
        if sem_value == 'Yes':
            semantic_gpt4_better += 1
        elif sem_value == 'No':
            semantic_v1_better += 1
    
    # Calculate percentages
    prompt_engineering_display = ('Haven\'t evaluated an unacceptable label yet' if unacceptable_count == 0 
                                else f"{(improved_count / unacceptable_count * 100):.1f}%")
    
    syntactic_v1_percentage = (syntactic_v1_better / total * 100) if total > 0 else 0
    syntactic_gpt4_percentage = (syntactic_gpt4_better / total * 100) if total > 0 else 0
    semantic_v1_percentage = (semantic_v1_better / total * 100) if total > 0 else 0
    semantic_gpt4_percentage = (semantic_gpt4_better / total * 100) if total > 0 else 0
    
    # Create DataFrame for the statistics
    data = {
        'Evaluation Criteria': [
            'Prompt Engineering Helped',
            'Syntactic Superiority',
            'Semantic Superiority'
        ],
        'V1 (%)': [
            'N/A',
            f"{syntactic_v1_percentage:.1f}%",
            f"{semantic_v1_percentage:.1f}%"
        ],
        'GPT-4o (%)': [
            prompt_engineering_display,  # More descriptive message when no unacceptable cases yet
            f"{syntactic_gpt4_percentage:.1f}%",
            f"{semantic_gpt4_percentage:.1f}%"
        ]
    }
    
    df = pd.DataFrame(data)
    return df

def main():
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")
    
    # Add statistics table and download options at the top
    if 'comparator' in st.session_state:
        evaluations = st.session_state.comparator.load_progress()
        if evaluations:  # Will be true even with just one evaluation
            df = calculate_evaluation_stats(evaluations)
            st.table(df)
            
            # Add CSV download button for the statistics table
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Statistics as CSV",
                data=csv,
                file_name="evaluation_statistics.csv",
                mime="text/csv",
            )
            
            # Add JSON download button for full evaluations
            json_str = pd.DataFrame(evaluations).T.to_json(orient='index', indent=2)
            st.download_button(
                label="Download Full Evaluations (JSON)",
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
           - Analyze if prompt engineering has helped improve LLM labels and made unacceptable labels acceptable
           - There are approximately 23 clusters that were marked as 'unacceptable' in V1
           - The prompt engineering questions will automatically appear when you encounter these specific clusters
           - Unacceptable labels are those that are:
              -a) Uninterpretable concepts: Where the LLM didnt understand what was the token and used a completely different concept
              -b) Precision: Where the LLM was able to understand but not give the exact concept 
              -c) Where the model didnt recognise the token so didnt give an labels ( Check mainly for this)
           - Compare quality of GPT-4o labels with human labels
           
        ⚠️ **Important Note About V1 Labels**:
           - Even though some V1 labels are marked as "acceptable", they might not actually be acceptable
           - You should independently evaluate the quality of each label regardless of its marked acceptability
           - Focus on whether prompt engineering has made the v1 unacceptable label acceptable wherever it applies
           
        2. **Prompts Used**
           - V1 Prompt: "Generate a concise label or theme for the following java code tokens: {token_summary}"
           
           - GPT-4o Prompt (partial):
             * "3. **Concise Syntactic Label**: Choose a descriptive label that accurately describes the syntactic function or syntactic role of the tokens in the code. Use specific terminology where applicable (e.g., Object, Dot operator, methods). Avoid generic terms."
             * "4. **Semantic Tags**: Provide 3-5 semantic tags that accurately describe the key functionality and purpose of the code. These tags should reflect the overall functionality and purpose of the code. Avoid using the same tag twice and avoid generic tags. Aim for detailed tags. Examples of good tags include 'Concurrency Control', 'Data Serialization', 'Error Handling'."
             * "5. **Description**: Provide a concise justification for the syntactic label and semantic tags you have chosen. Explain why these tokens and sentences are significant in the context of Java programming."
             * Additionally includes 2 examples from previous clusters as few-shot examples
           
        3. **For Each Cluster**
           - Review the tokens and their context
           - Compare V1 (before prompt engineering) vs GPT-4o (after prompt engineering) labels
           - Compare GPT-4o labels with human labels
           - For unacceptable cases (23 clusters), you'll see additional questions about prompt engineering improvement
           
        4. **Evaluation Criteria**
           - Prompt Engineering Impact: Has it helped convert previously unacceptable labels to acceptable ones?
           - Syntactic Superiority: Is GPT-4o's syntactic label better than the human label?
           - Semantic Superiority: Are GPT-4o's semantic tags better than human tags? (≥3/5 tags should be better)
                      
        ⚠️ **Important**: 
        - Focus on comparing before/after prompt engineering and against human labels
        - For V1 the model was just asked this question: 'Generate a concise label or theme for the following java code tokens: {token_summary}.' So there is no specific syntactic or semantic label it is just whatever LLM aligns to. 
        - We just want to see if prompt engineering helped getting all clusters labelled which the previous model failed to do.
        
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
            batch_size = 50
            total_batches = (len(st.session_state.comparator.cluster_ids) + batch_size - 1) // batch_size
            
            new_batch = st.selectbox(
                "Select your batch (50 clusters each)",
                range(total_batches),
                index=st.session_state.batch_number,
                format_func=lambda x: f"Batch {x} (clusters {x*50}-{min((x+1)*50-1, len(st.session_state.comparator.cluster_ids)-1)})"
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
                v1_label_data = comparator.v1_labels[current_cluster_key]
                st.write("LLM Label (not specific to syntactic or semantic):")
                st.write(v1_label_data.get("Labels", ["N/A"])[0])
                st.markdown(f"<span style='color: red'>**LLM label Acceptability:**</span> {v1_label_data.get('Q1_Answer', 'N/A')}", unsafe_allow_html=True)
            
                # Highlight semantic tags in red
                semantic_tags = v1_label_data.get("Semantic", "").split(", ")
                if semantic_tags:
                    st.markdown("<span style='color: red'>**Human Semantic Tags:**</span>", unsafe_allow_html=True)
                    for tag in semantic_tags:
                        st.write(f"- {tag}")
                else:
                    st.markdown("<span style='color: red'>**Semantic Tags: N/A**</span>", unsafe_allow_html=True)
                
                # Highlight syntactic label in red
                st.markdown(f"<span style='color: red'>**Human Syntactic Label:**</span> {v1_label_data.get('Syntactic', 'N/A')}", unsafe_allow_html=True)
                st.write("Human Description:", v1_label_data.get("Description", "N/A"))
        
        with col2:
            st.header("GPT-4o Labels")
            gpt4_cluster_key = f"c{current_cluster}"
            gpt4_cluster = next((item[gpt4_cluster_key] for item in comparator.gpt4_labels 
                               if gpt4_cluster_key in item), {})
            
            # Highlight syntactic label in red
            st.markdown(f"<span style='color: red'>**LLM Syntactic Label:**</span> {gpt4_cluster.get('Syntactic Label', 'N/A')}", unsafe_allow_html=True)
            
            # Highlight semantic tags in red
            semantic_tags = gpt4_cluster.get("Semantic Tags", [])
            if semantic_tags:
                st.markdown("<span style='color: red'>**LLM Semantic Tags:**</span>", unsafe_allow_html=True)
                for tag in semantic_tags:
                    st.write(f"- {tag}")
            else:
                st.markdown("<span style='color: red'>**Semantic Tags: N/A**</span>", unsafe_allow_html=True)
            
            st.markdown(f"<span style='color: red'>**LLM Description:**</span> {gpt4_cluster.get('Description', 'N/A')}", unsafe_allow_html=True)

        
        with col3:
            st.header("Error Analysis and Prompt Engineering Impact")
            
            # Always show prompt engineering question regardless of acceptability
            prompt_engineering_helped = st.radio(
                "Has prompt engineering made V1 unacceptable label acceptable?",
                ["Yes", "No"],
                key=f"prompt_engineering_{current_cluster}"
            )
            
            if prompt_engineering_helped == "No":
                error_description = st.text_area(
                    "Describe the issues:",
                    key=f"error_description_{current_cluster}"
                )
            
            st.header("Comparison with Human Labels")
            
            syntactic_superior = st.radio(
                "Is GPT-4o's syntactic label superior to the human label?",
                ["Yes", "No","Same"],
                key=f"syntactic_superior_{current_cluster}"
            )
            
            if syntactic_superior == "No":
                syntactic_notes = st.text_area(
                    "Why is it not superior?",
                    key=f"syntactic_notes_{current_cluster}"
                )
            
            semantic_superior = st.radio(
                "Are GPT-4o's semantic tags superior to human tags? (At least 3 tags should be really good and better tags)",
                ["Yes", "No","Same"],
                key=f"semantic_superior_{current_cluster}"
            )
            
            if semantic_superior == "No":
                semantic_notes = st.text_area(
                    "Why are they not superior?",
                    key=f"semantic_notes_{current_cluster}"
                )

            # Moved submit button here, inside col3
            if st.button("Submit Evaluation", key=f"submit_{current_cluster}"):
                evaluation = {
                    'prompt_engineering_helped': prompt_engineering_helped,
                    'syntactic_superior': syntactic_superior,
                    'semantic_superior': semantic_superior,
                    'error_description': error_description if prompt_engineering_helped == "No" else "",
                    'syntactic_notes': syntactic_notes if syntactic_superior == "No" else "",
                    'semantic_notes': semantic_notes if semantic_superior == "No" else ""
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
