import streamlit as st
import json
import os
from supabase import create_client
from analyze_results import analyze_evaluations
from datetime import datetime

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
            # Check if evaluation already exists
            existing = self.supabase.table('evaluations').select("*").eq('cluster_id', cluster_id).execute()
            
            if existing.data and st.session_state.get('evaluation_start_time', 0) < existing.data[0].get('created_at', 0):
                # Someone else evaluated this cluster after we loaded it
                if not st.confirm("This cluster has been evaluated by someone else since you started. Do you want to overwrite their evaluation?"):
                    return False
            
            # Prepare evaluation data
            eval_data = {
                'cluster_id': cluster_id,
                'last_cluster_index': st.session_state.current_index,
                'acceptability': evaluation['acceptability'],
                'precision': evaluation['precision'],
                'quality': evaluation['quality'],
                'notes': evaluation.get('notes', ''),
                'created_at': datetime.now().isoformat()
            }

            # Add error descriptions if they exist
            if evaluation['precision'] == 'Less Precise':
                eval_data['precision_error'] = evaluation.get('precision_error', '')
                
            if evaluation['quality'] == 'Inferior':
                eval_data['quality_error'] = evaluation.get('quality_error', '')
                
            if evaluation.get('semantic_tags'):
                eval_data['semantic_tags'] = evaluation['semantic_tags']
                if evaluation['semantic_tags'] == 'No':
                    eval_data['semantic_error'] = evaluation.get('semantic_error', '')

            # Save the evaluation
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
        
def find_next_unevaluated_cluster(comparator, start_index=0):
    """Find the next unevaluated cluster starting from given index"""
    fresh_evaluations = comparator.load_progress()
    evaluated_cluster_ids = set(fresh_evaluations.keys())
    
    for i in range(start_index, len(comparator.cluster_ids)):
        if comparator.cluster_ids[i] not in evaluated_cluster_ids:
            return i
    return None

def main():
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")
    
    # Add an expander for instructions at the top - now expanded by default
    with st.expander("📖 Instructions", expanded=True):
        st.markdown("""
        ### How to Use This Tool

        1. **Getting Started**
           - Choose a batch of clusters to evaluate
           - Use "Jump to cluster" to go to your assigned batch

        2. **For Each Cluster**
           - Review the tokens shown
           - Compare V1 and GPT-4o labels side by side
           - Look at example sentences for context
           
        3. **Evaluation Criteria**
           - Acceptable : if label and description fits some aspect of the cluster correctly
           - Precise: if it’s to  the point and not overly vague, no extra information
           - Superior: based on precision and accuracy take your judgement
           - Error description: if the label and semantic tags are not correct give a one-two sentence description of the error

        4. **Tips**
           - Add notes to justify your choices
           - Check example sentences for context
           - Look for both syntactic and semantic accuracy

        ⚠️ **Important**: Avoid evaluating clusters outside your assigned batch
        """)

    # Initialize the comparator in session state if it doesn't exist
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

    comparator = st.session_state.comparator

    # Fetch fresh evaluations data for the count
    fresh_evaluations = comparator.load_progress()
    evaluated_clusters = len(fresh_evaluations)

    col1, col2, col3, col4, col5 = st.columns([1,1,1,1,1])
    
    with col1:
        st.write(f"Total clusters: {len(comparator.cluster_ids)}")
    with col2:
        st.write(f"Clusters remaining: {500 - evaluated_clusters}")
    with col3:
        st.write(f"Current cluster Number: {st.session_state.current_index}")
    with col4:
        # Add jump to cluster functionality
        jump_to = st.number_input(
            "Jump to cluster",
            min_value=0,
            max_value=len(comparator.cluster_ids) - 1,
            value=st.session_state.current_index,
            key="jump_to_cluster"
        )
        if st.button("Go"):
            # Find next unevaluated cluster from the jumped position
            next_index = find_next_unevaluated_cluster(comparator, int(jump_to))
            if next_index is not None:
                st.session_state.current_index = next_index
                st.session_state.evaluation_start_time = datetime.now().isoformat()
                st.rerun()
            else:
                st.error("No unevaluated clusters found after this position!")

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
        tokens = set()
        with open(os.path.join(comparator.base_path, 'clusters-500.txt'), 'r') as f:
            for line in f:
                stripped_line = line.strip()
                pipe_count = stripped_line.count('|')
                parts = stripped_line.split('|||')

                # Get the token based on pipe count
                if pipe_count == 13:
                    token = '|'
                elif pipe_count == 14:
                    token = '||'
                elif pipe_count == 12:
                    token = parts[0]
                else:
                    continue

                if len(parts) >= 5 and parts[4].split()[-1] == current_cluster:
                    tokens.add(token)
        
        st.header("Unique Tokens")
        st.write(", ".join(sorted(tokens)))
        st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.header("CodeConceptNet-V1 Labels")
        current_cluster_key = f"c{current_cluster}"
        if current_cluster_key in comparator.v1_labels:
            st.write("Label:", comparator.v1_labels[current_cluster_key].get("Label", "N/A"))
            st.write("Semantic Tags:", comparator.v1_labels[current_cluster_key].get("Semantic_Tags", []))
    
    with col2:
        st.header("GPT-4o Labels")
        gpt4_cluster = next((item[current_cluster_key] for item in comparator.gpt4_labels 
                           if current_cluster_key in item), {})
        st.write("Label:", gpt4_cluster.get("Label", "N/A"))
        st.write("Semantic Tags:", gpt4_cluster.get("Semantic Tags", []))
    
    with col3:
        st.header("Evaluation")
        with st.form(key=f"evaluation_form_{current_cluster}"):
            acceptability = st.radio(
                "Is the GPT-4o label acceptable?",
                ["Yes", "No"],
                key=f"acceptability_{current_cluster}"
            )
            
            precision = st.radio(
                "How precise is the GPT-4o label compared to V1?",
                ["More Precise", "Less Precise", "Same"],
                key=f"precision_{current_cluster}"
            )
            
            if precision == "Less Precise":
                error_description = st.text_area(
                    "Please describe why GPT-4o's label is less precise",
                    key=f"error_description_text_{current_cluster}"
                )
            
            quality = st.radio(
                "Is the GPT-4o label superior?",
                ["Superior", "Inferior", "Same"],
                key=f"quality_{current_cluster}"
            )
            
            if quality == "Inferior":
                quality_error = st.text_area(
                    "Please describe why GPT-4o's label is inferior",
                    key=f"quality_error_text_{current_cluster}"
                )
            
            semantic_tags = st.radio(
                "Does the GPT-4o have the precise and accurate semantic tags? (Atleast 3 out of 5)",
                ["Yes", "No"],
                key=f"semantic_tags_{current_cluster}"
            )
            
            if semantic_tags == "No":
                semantic_error = st.text_area(
                    "Please describe the error in GPT-4o's semantic tags",
                    key=f"semantic_error_text_{current_cluster}"
                )
            
            notes = st.text_area(
                "Additional Notes (optional)",
                key=f"notes_{current_cluster}"
            )
            
            submitted = st.form_submit_button("Submit Evaluation")
            
            if submitted:
                # Save to database
                if comparator.save_progress(current_cluster, {
                    "acceptability": acceptability,
                    "precision": precision,
                    "quality": quality,
                    "notes": notes
                }):
                    # Find next unevaluated cluster
                    next_index = find_next_unevaluated_cluster(comparator, st.session_state.current_index + 1)
                    if next_index is not None:
                        st.session_state.current_index = next_index
                        st.rerun()
                    else:
                        st.success("All clusters have been evaluated!")
            
        # Show previous evaluation if it exists
        if current_cluster in comparator.evaluations:
            existing_eval = comparator.evaluations[current_cluster]
            st.info("Previous evaluation exists:")
            st.write(f"Acceptability: {existing_eval['acceptability']}")
            st.write(f"Precision: {existing_eval['precision']}")
            st.write(f"Quality: {existing_eval['quality']}")
            st.write(f"Notes: {existing_eval['notes']}")

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

    
if __name__ == "__main__":
    main()
