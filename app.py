import streamlit as st
import json
import csv
import os
import mysql.connector
from analyze_results import analyze_evaluations

class ClusterComparator:
    def __init__(self):
        self.v1_labels = {}
        self.gpt4_labels = {}
        self.java_sentences = {}
        self.clusters_data = {}
        self.current_cluster_index = 0
        self.cluster_ids = []
        
        # Connect to MySQL database with new credentials
        self.db_connection = mysql.connector.connect(
            host='sql5.freesqldatabase.com',
            database='sql5742739',
            user='sql5742739',
            password='AhvzmKbr2A',
            port=3306
        )
        self.create_table()
        self.evaluations = self.load_progress()
        self.base_path = os.getcwd()
        
    def create_table(self):
        with self.db_connection.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluations (
                    cluster_id VARCHAR(255) PRIMARY KEY,
                    last_cluster_index INT,
                    acceptability VARCHAR(50),
                    `precision` VARCHAR(50),
                    quality VARCHAR(50),
                    notes TEXT
                )
            ''')
            self.db_connection.commit()
        
    def load_progress(self):
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM evaluations")
            rows = cursor.fetchall()
            evaluations = {}
            for row in rows:
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
        finally:
            cursor.close()

    def save_progress(self, cluster_id, evaluation):
        self.ensure_connection()
        with self.db_connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO evaluations (cluster_id, last_cluster_index, acceptability, `precision`, quality, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    last_cluster_index = VALUES(last_cluster_index),
                    acceptability = VALUES(acceptability),
                    `precision` = VALUES(`precision`),
                    quality = VALUES(quality),
                    notes = VALUES(notes)
            ''', (
                cluster_id, 
                st.session_state.current_index,  # Save current index instead of from evaluation
                evaluation['acceptability'],
                evaluation['precision'],
                evaluation['quality'],
                evaluation['notes']
            ))
            self.db_connection.commit()
        
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
        
    def ensure_connection(self):
        try:
            self.db_connection.ping(reconnect=True, attempts=3, delay=5)
        except mysql.connector.Error as err:
            # Reconnect if connection is lost
            self.db_connection = mysql.connector.connect(
                host='sql5.freesqldatabase.com',
                database='sql5742739',
                user='sql5742739',
                password='AhvzmKbr2A',
                port=3306
            )

def main():
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")

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

    # Add a download button for evaluations at the top
    if st.button("Download All Evaluations"):
        # Fetch fresh data from database
        evaluations = st.session_state.comparator.load_progress()
        evaluations_json = json.dumps(evaluations, indent=2)
        if evaluations:
            st.download_button(
                label="Click to Download Evaluations",
                data=evaluations_json,
                file_name='evaluations.json',
                mime='application/json'
            )
        else:
            st.warning("No evaluations available to download.")

    st.write(f"Total clusters: {len(comparator.cluster_ids)}")
    
    # Calculate clusters remaining based on evaluations
    evaluated_clusters = len(comparator.evaluations)
    st.write(f"Clusters remaining: {len(comparator.cluster_ids) - evaluated_clusters}")

    st.write(f"Current cluster: {comparator.cluster_ids[st.session_state.current_index]}")

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
                # Save to database
                comparator.save_progress(current_cluster, {
                    "acceptability": acceptability,
                    "precision": precision,
                    "quality": quality,
                    "notes": notes
                })
                # Increment the index and rerun
                if st.session_state.current_index < len(comparator.cluster_ids) - 1:
                    st.session_state.current_index += 1
                    st.rerun()
        
        # Show previous evaluation if it exists
        if current_cluster in comparator.evaluations:
            existing_eval = comparator.evaluations[current_cluster]
            st.info("Previous evaluation exists:")
            st.write(f"Acceptability: {existing_eval['acceptability']}")
            st.write(f"Precision: {existing_eval['precision']}")
            st.write(f"Quality: {existing_eval['quality']}")
            st.write(f"Notes: {existing_eval['notes']}")

    # Display code examples section
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
