import streamlit as st
import json
import csv
import os
from analyze_results import analyze_evaluations

class ClusterComparator:
    def __init__(self):
        self.v1_labels = {}
        self.gpt4_labels = {}
        self.java_sentences = {}
        self.clusters_data = {}
        self.current_cluster_index = 0
        self.cluster_ids = []
        self.progress_file = os.path.join(os.getcwd(), 'comparison_progress.json')
        self.evaluations = self.load_progress()
        self.base_path = os.getcwd()
        
    def load_progress(self):
        # Ensure the progress file is in the current working directory
        if not os.path.exists(self.progress_file):
            initial_progress = {
                "last_cluster_index": 0,
                "evaluations": {}
            }
            with open(self.progress_file, 'w') as f:
                json.dump(initial_progress, f, indent=2)
            return initial_progress
        
        with open(self.progress_file, 'r') as f:
            return json.load(f)
        
    def save_progress(self, cluster_id, evaluation):
        self.evaluations["evaluations"][cluster_id] = evaluation
        self.evaluations["last_cluster_index"] = st.session_state.current_index
        
        with open(self.progress_file, 'w') as f:
            json.dump(self.evaluations, f, indent=2)
        
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
                parts = line.strip().split('|||')
                if len(parts) >= 5:
                    token = parts[0]
                    line_number = int(parts[2])
                    cluster_id = parts[4]
                    
                    if cluster_id not in self.clusters_data:
                        self.clusters_data[cluster_id] = []
                    self.clusters_data[cluster_id].append(line_number)
        
        self.cluster_ids = sorted(list(set(self.clusters_data.keys())), 
                                key=lambda x: int(x) if x.isdigit() else float('inf'))
        

def main():
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")

    # Add a download button for evaluations at the top
    evaluations_json = json.dumps(st.session_state.comparator.evaluations, indent=2)
    st.download_button(
        label="Download Current Evaluations",
        data=evaluations_json,
        file_name='evaluations.json',
        mime='application/json'
    )

    if 'comparator' not in st.session_state:
        st.session_state.comparator = ClusterComparator()
        st.session_state.comparator.load_data()
        
        # Load the last cluster index from progress file
        last_index = st.session_state.comparator.evaluations.get("last_cluster_index", 0)
        
        # Check if the last index is already evaluated
        if last_index in st.session_state.comparator.evaluations["evaluations"]:
            # Start from the next index if the last one is done
            st.session_state.current_index = last_index + 1
        else:
            st.session_state.current_index = last_index  # Start from the last index if not done

    comparator = st.session_state.comparator
    
    st.write(f"Total clusters: {len(comparator.cluster_ids)}")
    
    # Calculate clusters remaining based on evaluations
    evaluated_clusters = len(comparator.evaluations["evaluations"])
    st.write(f"Clusters remaining: {len(comparator.cluster_ids) - evaluated_clusters}")
    
    # Entry field for cluster ID
    cluster_id_input = st.text_input("Enter Cluster ID:", "")
    
    if cluster_id_input:
        if cluster_id_input in comparator.cluster_ids:
            st.session_state.current_index = comparator.cluster_ids.index(cluster_id_input)
        else:
            st.warning("Invalid Cluster ID. Please enter a valid ID.")

    st.write(f"Current cluster: {comparator.cluster_ids[st.session_state.current_index]}")
    
    if st.session_state.current_index < len(comparator.cluster_ids):
        current_cluster = comparator.cluster_ids[st.session_state.current_index]
        
        if current_cluster in comparator.clusters_data:
            tokens = set()
            with open(os.path.join(comparator.base_path, 'clusters-500.txt'), 'r') as f:
                for line in f:
                    parts = line.strip().split('|||')
                    if len(parts) >= 5 and parts[4] == current_cluster:
                        tokens.add(parts[0])
            
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
                    "Is the GPT-4 label acceptable?",
                    ["Yes", "No"],
                    key=f"acceptability_{current_cluster}"
                )
                
                precision = st.radio(
                    "How precise is the GPT-4 label compared to V1?",
                    ["More Precise", "Less Precise", "Same"],
                    key=f"precision_{current_cluster}"
                )
                
                quality = st.radio(
                    "Is the GPT-4 label better than V1?",
                    ["More Accurate", "Less Accurate", "Same"],
                    key=f"quality_{current_cluster}"
                )
                
                notes = st.text_area(
                    "Additional Notes (optional)",
                    key=f"notes_{current_cluster}"
                )
                
                submitted = st.form_submit_button("Submit Evaluation")
                
                if submitted:
                    comparator.save_progress(current_cluster, {
                        "acceptability": acceptability,
                        "precision": precision,
                        "quality": quality,
                        "notes": notes
                    })
        
        # Check if the current cluster has already been evaluated
        if current_cluster in comparator.evaluations["evaluations"]:
            st.success("Cluster done")
        
        # Add "Back" and "Next" buttons outside the form
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Back"):
                st.session_state.current_index = max(0, st.session_state.current_index - 1)
                st.rerun()
        
        with col2:
            if st.button("Next"):
                st.session_state.current_index += 1
                st.rerun()
        
        st.header("Code Examples")
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
