import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
import io
from wordcloud import WordCloud
import matplotlib.pyplot as plt

class ClusterComparator:
    def __init__(self):
        self.v1_labels = {}
        self.gpt4_labels = {}
        self.java_sentences = {}
        self.clusters_data = {}
        self.current_cluster_index = 0
        self.cluster_ids = []
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.evaluations_file = os.path.join(self.base_path, 'evaluations.json')

    def load_progress(self):
        if os.path.exists(self.evaluations_file):
            try:
                with open(self.evaluations_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_progress(self, cluster_id, evaluation):
        evaluations = self.load_progress()
        evaluations[cluster_id] = evaluation
        try:
            with open(self.evaluations_file, 'w') as f:
                json.dump(evaluations, f, indent=2)
            return True
        except:
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


def generate_wordcloud(text_data, title):
    """Generate and display a wordcloud from the given text data"""
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text_data)
    
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title(title)
    st.pyplot(plt)

def main():
    st.set_page_config(layout="wide")
    st.title("Cluster Label Comparison Tool")
    
    # Add statistics table and download options at the top
    if 'comparator' in st.session_state:
        evaluations = st.session_state.comparator.load_progress()
        if evaluations:
            st.table(evaluations)
            
            # Generate wordclouds for semantic tags
            st.header("Visualization")
            col1, col2 = st.columns(2)
            
            with col1:
                # Collect all V1 semantic tags
                v1_tags = []
                for cluster_id in evaluations:
                    if cluster_id in st.session_state.comparator.v1_labels:
                        tags = st.session_state.comparator.v1_labels[cluster_id].get("Semantic", "").split(", ")
                        v1_tags.extend(tags)
                generate_wordcloud(" ".join(v1_tags), "V1 Semantic Tags WordCloud")
            
            with col2:
                # Collect all GPT-4o semantic tags
                gpt4_tags = []
                for cluster_id in evaluations:
                    cluster_key = f"c{cluster_id}"
                    for item in st.session_state.comparator.gpt4_labels:
                        if cluster_key in item:
                            tags = item[cluster_key].get("Semantic Tags", [])
                            gpt4_tags.extend(tags)
                generate_wordcloud(" ".join(gpt4_tags), "GPT-4o Semantic Tags WordCloud")
            

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
        
        # ... existing code until the columns section ...

        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.header("CodeConceptNet-V1 Labels")
            current_cluster_key = str(current_cluster)
            if current_cluster_key in comparator.v1_labels:
                v1_label_data = comparator.v1_labels[current_cluster_key]
                st.write("<span style='color: red'>**LLM Label (not specific to syntactic or semantic):**</span>", unsafe_allow_html=True)
                st.write(v1_label_data.get("Labels", ["N/A"])[0])
                st.markdown(f"<span style='color: red'>**LLM label Acceptability:**</span> {v1_label_data.get('Q1_Answer', 'N/A')}", unsafe_allow_html=True)
            
                semantic_tags = v1_label_data.get("Semantic", "").split(", ")
                if semantic_tags:
                    st.markdown("<span style='color: red'>**Human Semantic Tags:**</span>", unsafe_allow_html=True)
                    for tag in semantic_tags:
                        st.write(f"- {tag}")
                else:
                    st.markdown("<span style='color: red'>**Semantic Tags: N/A**</span>", unsafe_allow_html=True)
                
                st.markdown(f"<span style='color: red'>**Human Syntactic Label:**</span> {v1_label_data.get('Syntactic', 'N/A')}", unsafe_allow_html=True)
                st.write("<span style='color: red'>**Human Description:**</span>", v1_label_data.get("Description", "N/A"), unsafe_allow_html=True)
        
        with col2:
            st.header("GPT-4o Labels")
            gpt4_cluster_key = f"c{current_cluster}"
            gpt4_cluster = next((item[gpt4_cluster_key] for item in comparator.gpt4_labels 
                               if gpt4_cluster_key in item), {})
            
            st.markdown(f"<span style='color: red'>**LLM Syntactic Label:**</span> {gpt4_cluster.get('Syntactic Label', 'N/A')}", unsafe_allow_html=True)
            
            semantic_tags = gpt4_cluster.get("Semantic Tags", [])
            if semantic_tags:
                st.markdown("<span style='color: red'>**LLM Semantic Tags:**</span>", unsafe_allow_html=True)
                for tag in semantic_tags:
                    st.write(f"- {tag}")
            else:
                st.markdown("<span style='color: red'>**Semantic Tags: N/A**</span>", unsafe_allow_html=True)
            
            st.markdown(f"<span style='color: red'>**LLM Description:**</span> {gpt4_cluster.get('Description', 'N/A')}", unsafe_allow_html=True)

        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous Cluster") and st.session_state.current_index > 0:
                st.session_state.current_index -= 1
                st.rerun()
        with col2:
            if st.button("Next Cluster") and st.session_state.current_index < len(comparator.cluster_ids) - 1:
                st.session_state.current_index += 1
                st.rerun()

        # Display code examples section
        st.header("Sentences where the token appears")
        if current_cluster in comparator.clusters_data:
            for sentence_id in comparator.clusters_data[current_cluster]:
                if sentence_id in comparator.java_sentences:
                    sentence = comparator.java_sentences[sentence_id]
                    st.code(sentence, language="java")

if __name__ == "__main__":
    main()