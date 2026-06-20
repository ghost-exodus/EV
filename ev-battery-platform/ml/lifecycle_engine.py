import os
import pandas as pd
import numpy as np

# Define relative path routes
MASTER_DATA_PATH = 'ml/data/B0005_master_degradation.csv'
PASSPORT_OUTPUT_PATH = 'ml/data/B0005_battery_passport.csv'

def classify_battery_circular_path(soh, avg_temp, capacity_fade_rate):
    """
    Implements a strict automotive-to-sustainability grading matrix
    aligned directly with EV Circular Economy tracking protocols.
    """
    # 1. First Life Tier: Battery retains high structural and chemical health
    if soh >= 80.0:
        return {
            "lifecycle_stage": "First Life (EV Active)",
            "health_grade": "Grade A+",
            "recommended_destination": "Maintain in Active EV Fleet Operations",
            "circular_action": "None (Active Asset Lifecycle)"
        }
        
    # 2. Second Life Storage Tier: Past automotive use, but degradation is highly stable
    elif 70.0 <= soh < 80.0 and avg_temp <= 35.0 and capacity_fade_rate < 5.0:
        return {
            "lifecycle_stage": "Second Life Repurposing",
            "health_grade": "Grade B (Premium)",
            "recommended_destination": "Stationary Solar Energy Storage / Micro-Grid Backups",
            "circular_action": "Repurpose Pack (Divert from Landfill)"
        }
        
    # 3. Second Life Low Tier: Marginal health, suitable only for low-drain usage
    elif 65.0 <= soh < 70.0 and capacity_fade_rate < 8.0:
        return {
            "lifecycle_stage": "Second Life Repurposing",
            "health_grade": "Grade C (Standard)",
            "recommended_destination": "Low-Demand Telecom Tower Backup Power",
            "circular_action": "Refurbish Module Components"
        }
        
    # 4. Critical EOL Tier: Severe degradation or chemical volatility. Must recycle.
    else:
        return {
            "lifecycle_stage": "End of Life (EOL)",
            "health_grade": "Grade D (Recycle)",
            "recommended_destination": "Hydrometallurgical Material Extraction Plant",
            "circular_action": "Extract Raw Minerals (Lithium, Cobalt, Nickel)"
        }
    

def run_circular_economy_compiler():
    print("♻️ Commencing Circular Economy Lifecycle Pass...")
    
    if not os.path.exists(MASTER_DATA_PATH):
        print(f"Error: Missing dependency file at {MASTER_DATA_PATH}. Run data_cleaning.py first!")
        return

    # Ingest your master degradation logs
    df = pd.read_csv(MASTER_DATA_PATH)
    
    passport_records = []
    
    # Calculate historical capacity fade rate (slope) across a rolling 5-cycle block
    # This prevents noise spikes from throwing off the long-term trend calculations
    df['capacity_fade_velocity'] = df['capacity_mah'].diff(-5).abs() / 5
    df['capacity_fade_velocity'] = df['capacity_fade_velocity'].bfill().fillna(0)

    # Loop through every operational cycle recording to trace the full passport timeline
    for idx, row in df.iterrows():
        soh = row['soh_percent']
        temp = row['temp_mean']
        fade_rate = row['capacity_fade_velocity']
        
        # Ingest parameters into grading logic
        decision = classify_battery_circular_path(soh, temp, fade_rate)
        
        # Compile a master row snapshot
        record = {
            "battery_id": "EV_B0005_001", # Unique Asset Registry Tag
            "cycle_number": int(row['cycle_number']),
            "current_soh": round(soh, 2),
            "internal_temp_avg": round(temp, 2),
            "capacity_fade_rate": round(fade_rate, 4),
            "lifecycle_stage": decision['lifecycle_stage'],
            "health_grade": decision['health_grade'],
            "destination_target": decision['recommended_destination'],
            "circular_action": decision['circular_action']
        }
        passport_records.append(record)
        
    # Transform list into structured dataframe
    passport_df = pd.DataFrame(passport_records)
    
    # Export your final Battery Passport Ledger
    passport_df.to_csv(PASSPORT_OUTPUT_PATH, index=False)
    print(f"🎉 Success! Digital Battery Passport ledger compiled at: {PASSPORT_OUTPUT_PATH}")
    print("\n--- Passport Ledger Live View (Recent Degradation States) ---")
    print(passport_df.tail(10).to_string())

if __name__ == '__main__':
    run_circular_economy_compiler()