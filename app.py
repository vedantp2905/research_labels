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

    # If the current index is 0 and there are evaluations, move to the next cluster
    if st.session_state.current_index == 0 and evaluations:
        st.session_state.current_index = 1

    comparator = st.session_state.comparator  # Access the comparator from session state

    # Display the current cluster
    current_cluster = comparator.cluster_ids[st.session_state.current_index]

    # Inside your evaluation form
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
            # Move to next cluster
            if st.session_state.current_index < len(comparator.cluster_ids) - 1:
                st.session_state.current_index += 1
                st.rerun()  # Rerun to refresh the state
            else:
                st.success("You've completed all clusters!")

    # Optionally, you can add a download button for evaluations
    if st.button("Download All Evaluations"):
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

    
if __name__ == "__main__":
    main()
