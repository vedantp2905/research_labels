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
    
    # Initialize acknowledgment state if not exists
    if 'instructions_acknowledged' not in st.session_state:
        st.session_state.instructions_acknowledged = False
    
    # Add instructions with checkbox
    with st.expander("📖 Instructions", expanded=not st.session_state.instructions_acknowledged):
        st.markdown("""
        ### How to Use This Tool

        1. **Getting Started**
           - Choose a batch of clusters to evaluate on the sidebar
          
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
           - So First evaluate the GPT40 abel ad semantic tags and then compare it. 
           

        ⚠️ **Important**: Avoid evaluating clusters outside your assigned batch
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
            
            tokens = gpt4_cluster.get("Unique Tokens", [])
            
            st.header("Unique Tokens")
            st.write(", ".join(sorted(tokens)) if tokens else "No tokens found")
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
            st.write("Description:", gpt4_cluster.get("Description", "N/A"))

        
        with col3:
            st.header("Evaluation")
            
            # Radio buttons and their error fields
            acceptability = st.radio(
                "Is the GPT-4o label acceptable? (If the label and description fits some aspect of the cluster correctly)",
                ["Yes", "No"],
                key=f"acceptability_{current_cluster}"
            )
            
            precision = st.radio(
                "How precise is the GPT-4o label compared to V1? (If it’s to  the point and not overly vague, no extra information)",
                ["More Precise", "Less Precise", "Same"],
                key=f"precision_{current_cluster}"
            )
            
            # Show precision error field if needed
            precision_error = ""
            if precision == "Less Precise":
                precision_error = st.text_area(
                    "* Please describe why GPT-4o's label is less precise",
                    key=f"precision_error_{current_cluster}"
                )
            
            quality = st.radio(
                "Is the GPT-4o label superior? (Based on precision and accuracy take your judgement)",
                ["Superior", "Inferior", "Same"],
                key=f"quality_{current_cluster}"
            )
            
            # Show quality error field if needed
            quality_error = ""
            if quality == "Inferior":
                quality_error = st.text_area(
                    "* Please describe why GPT-4o's label is inferior",
                    key=f"quality_error_{current_cluster}"
                )
            
            semantic_tags = st.radio(
                "Does the GPT-4o have the precise and accurate semantic tags? (Atleast 3 out of 5)",
                ["Yes", "No"],
                key=f"semantic_tags_{current_cluster}"
            )
            
            # Show semantic error field if needed
            semantic_error = ""
            if semantic_tags == "No":
                semantic_error = st.text_area(
                    "* Please describe the error in GPT-4o's semantic tags",
                    key=f"semantic_error_{current_cluster}"
                )
            
            notes = st.text_area(
                "Additional Notes (optional)",
                key=f"notes_{current_cluster}"
            )
            
            # Submit button in a form
            with st.form(key=f"submit_form_{current_cluster}"):
                submitted = st.form_submit_button("Submit Evaluation")
                
            if submitted:
                # Validation
                validation_failed = False
                
                if precision == "Less Precise" and not precision_error.strip():
                    st.error("Please provide a description for why the GPT-4o label is less precise.")
                    validation_failed = True
                    
                if quality == "Inferior" and not quality_error.strip():
                    st.error("Please provide a description for why the GPT-4o label is inferior.")
                    validation_failed = True
                    
                if semantic_tags == "No" and not semantic_error.strip():
                    st.error("Please provide a description for the semantic tags error.")
                    validation_failed = True
                
                if not validation_failed:
                    evaluation_data = {
                        "acceptability": acceptability,
                        "precision": precision,
                        "quality": quality,
                        "semantic_tags": semantic_tags,
                        "notes": notes,
                        "precision_error": precision_error,
                        "quality_error": quality_error,
                        "semantic_error": semantic_error
                    }
                    
                    if comparator.save_progress(current_cluster, evaluation_data):
                        # Find next unevaluated cluster within the same batch
                        next_index = find_next_unevaluated_cluster(
                            comparator, 
                            st.session_state.current_index + 1,
                            batch_size=100
                        )
                        
                        if next_index is not None:
                            # Check if next index is still within current batch
                            current_batch = st.session_state.batch_number
                            if next_index // 100 == current_batch:
                                st.session_state.current_index = next_index
                                st.rerun()
                            else:
                                st.success(f"Batch {current_batch} completed!")
                        else:
                            st.success(f"Batch {st.session_state.batch_number} completed!")

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
    else:
        st.warning("Please read the instructions and check the acknowledgment box to continue.")
        st.stop()

if __name__ == "__main__":
    main()
