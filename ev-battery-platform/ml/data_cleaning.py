import os
import pandas as pd
import numpy as np

# Define paths relative to the root project workspace directory
METADATA_PATH = 'ml/data/metadata.csv'
DATA_DIR = 'ml/data'
OUTPUT_PATH = 'ml/data/B0005_master_degradation.csv'

def profile_single_cycle(file_name):
    """
    Optimized reader: Loads only required columns and vectorizes the mean 
    calculations to keep memory overhead near zero.
    """
    full_path = os.path.join(DATA_DIR, file_name)
    
    if not os.path.exists(full_path):
        return None
    
    # Optimization: Only load the columns we actually need for analytics
    needed_cols = ['Time', 'Voltage_measured', 'Current_measured', 'Temperature_measured']
    
    try:
        cycle_df = pd.read_csv(full_path, usecols=needed_cols)
        
        # Calculate vectorized summaries for this specific operational cycle
        return {
            "voltage_mean": cycle_df['Voltage_measured'].mean(),
            "current_mean": cycle_df['Current_measured'].mean(),
            "temp_mean": cycle_df['Temperature_measured'].mean(),
            "duration_seconds": cycle_df['Time'].max()
        }
    except Exception as e:
        print(f"Warning: Failed to parse file {file_name} due to: {e}")
        return None
    
def generate_master_dataset():
    print("🚀 Initializing Optimized Data Cleaning Pipeline...")
    
    # Check if the master index exists
    if not os.path.exists(METADATA_PATH):
        print(f"Error: Could not find master metadata at {METADATA_PATH}")
        return

    # Load master metadata and force numeric types to fix string errors
    metadata_df = pd.read_csv(METADATA_PATH)
    metadata_df['Capacity'] = pd.to_numeric(metadata_df['Capacity'], errors='coerce')
    
    # Filter for B0005 discharge cycles early to minimize loop iterations
    b0005_meta = metadata_df[
        (metadata_df['battery_id'] == 'B0005') & 
        (metadata_df['type'] == 'discharge')
    ].copy()
    
    print(f"Found {len(b0005_meta)} discharge profiles for Battery B0005. Starting extraction...")

    aggregated_data = []
    cycle_counter = 1

    # Loop through the pre-filtered rows
    for idx, row in b0005_meta.iterrows():
        csv_filename = row['filename']
        capacity_ah = row['Capacity']
        
        # Call our optimized profile function
        metrics = profile_single_cycle(csv_filename)
        
        if metrics is not None:
            # Combine macro metadata values with granular file summaries
            metrics['cycle_number'] = cycle_counter
            metrics['capacity_mah'] = capacity_ah * 1000  # Convert Ah to mAh [cite: 42]
            metrics['ambient_temp'] = row['ambient_temperature']
            
            aggregated_data.append(metrics)
            cycle_counter += 1

    # Convert the list of dictionaries directly into a master DataFrame
    master_df = pd.DataFrame(aggregated_data)
    
    # VECTORIZED SOH CALCULATION: Fast, clean, and avoids row-by-row iteration loops
    # Formula: (Current Capacity / Initial New Capacity) * 100 [cite: 42]
    nominal_capacity = master_df['capacity_mah'].iloc[0]
    master_df['soh_percent'] = (master_df['capacity_mah'] / nominal_capacity) * 100
    
    # Save the polished, consolidated dataset to your data folder
    master_df.to_csv(OUTPUT_PATH, index=False)
    print(f"🎉 Success! Consolidated master data saved to: {OUTPUT_PATH}")
    print(master_df.head())

if __name__ == '__main__':
    generate_master_dataset()