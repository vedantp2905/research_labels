import json
import pandas as pd

def analyze_evaluations(progress_file='clusters_data/500-clusters-output/comparison_progress.json'):
    # Load the evaluation data
    with open(progress_file, 'r') as f:
        data = json.load(f)
    
    evaluations = data['evaluations']
    
    # Initialize counters
    total = len(evaluations)
    if total == 0:
        # Return empty DataFrame with same structure when no evaluations exist
        return pd.DataFrame({
            'Evaluation Criteria': ['Acceptability', 'Precision', 'Quality vs. Human (Superior)'],
            'Before (%)': ['-', '-', '-'],
            'After (%)': ['-', '-', '-']
        })
    
    metrics = {
        'acceptability': {'Yes': 0, 'No': 0},
        'precision': {'More Precise': 0, 'Less Precise': 0, 'Same': 0},
        'quality': {'More Accurate': 0, 'Less Accurate': 0, 'Same': 0}
    }
    
    # Count the responses
    for eval_data in evaluations.values():
        metrics['acceptability'][eval_data['acceptability']] += 1
        metrics['precision'][eval_data['precision']] += 1
        metrics['quality'][eval_data['quality']] += 1
    
    # Calculate percentages
    results = {
        'Evaluation Criteria': ['Acceptability', 'Precision', 'Quality vs. Human (Superior)'],
        'Before (%)': ['-', '-', '-'],
        'After (%)': [
            round(metrics['acceptability']['Yes'] / total * 100, 1),
            round(metrics['precision']['More Precise'] / total * 100, 1),
            round(metrics['quality']['More Accurate'] / total * 100, 1)
        ]
    }
    
    # Create a DataFrame for nice display
    df = pd.DataFrame(results)
    
    # Save results to file
    df.to_csv('clusters_data/500-clusters-output/evaluation_results.csv', index=False)
    
    return df

if __name__ == "__main__":
    results = analyze_evaluations()
    print("\nEvaluation Results:")
    print(results.to_string(index=False)) 