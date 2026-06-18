import os
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

# Define training configuration
DATA_PATH = 'ml/data/B0005_master_degradation.csv'
MODEL_SAVE_PATH = 'ml/models/rul_lstm_v1.pt'
SCALER_SAVE_PATH = 'ml/models/scaler.pkl'

# Ensure the directory to store our trained model artifacts exists
os.makedirs('ml/models', exist_ok=True)

# 1. Load your master processed data
df = pd.read_csv(DATA_PATH)

# Define our 5 features for the time-series window (Match the roadmap specs!)
feature_cols = ['voltage_mean', 'current_mean', 'temp_mean', 'capacity_mah', 'soh_percent']

# Target variable: Remaining Useful Life (RUL) in cycles
# In the NASA dataset, we can calculate RUL per row as: (Total Cycles - Current Cycle)
total_cycles = df['cycle_number'].max()
df['RUL'] = total_cycles - df['cycle_number']

# Fit our scalers
scaler_x = MinMaxScaler()
scaled_features = scaler_x.fit_transform(df[feature_cols])

scaler_y = MinMaxScaler()
scaled_rul = scaler_y.fit_transform(df[['RUL']])

def create_sliding_windows(features, targets, sequence_length=50):
    X, y = [], []
    for i in range(len(features) - sequence_length):
        X.append(features[i : i + sequence_length])
        y.append(targets[i + sequence_length])
    return np.array(X), np.array(y)

# Generate sequences (Sequence Length = 50 cycles)
X_data, y_data = create_sliding_windows(scaled_features, scaled_rul, sequence_length=50)

# Convert Numpy arrays into PyTorch Tensors for the Neural Network
X_tensor = torch.tensor(X_data, dtype=torch.float32)
y_tensor = torch.tensor(y_data, dtype=torch.float32)

print(f"Features Sequence Shape: {X_tensor.shape}")  # Expected: [Cycles, 50, 5]
print(f"Target RUL Shape: {y_tensor.shape}")

class BatteryRULPredictorLSTM(nn.Module):
    def __init__(self, input_size=5, hidden_size=128, num_layers=2, output_size=1):
        super(BatteryRULPredictorLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # Core LSTM Recurrent layer
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        
        # Fully Connected Linear layer to output the final single prediction score
        self.fc = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        # Initialize hidden and cell states with zeros
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # Forward pass through LSTM
        out, _ = self.lstm(x, (h0, c0))
        
        # Decode the hidden state of the absolute last time step in the sequence
        out = self.fc(out[:, -1, :])
        return out

# Instantiate the model instance
model = BatteryRULPredictorLSTM()
print(model)

# Define loss function and optimizer engine
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# Training loop
epochs = 100
print("\n🏋️ Training Neural Network...")

for epoch in range(epochs):
    model.train()
    
    # 1. Clear previous gradients from optimizer memory
    optimizer.zero_grad()
    
    # 2. Compute forward pass predictions
    predictions = model(X_tensor)
    
    # 3. Evaluate prediction loss against true RUL metrics
    loss = criterion(predictions, y_tensor)
    
    # 4. Execute backpropagation gradients calculation
    loss.backward()
    
    # 5. Optimize and tweak model weights
    optimizer.step()
    
    if (epoch + 1) % 10 == 0:
        print(f"Epoch [{epoch+1}/{epochs}] ---> Training Loss (MSE): {loss.item():.6f}")

# Save the final trained model file weights
torch.save(model.state_dict(), MODEL_SAVE_PATH)

# Save our scaler as well using standard Python pickle tool so inference script can use it later
import pickle
with open(SCALER_SAVE_PATH, 'wb') as f:
    pickle.dump({'scaler_x': scaler_x, 'scaler_y': scaler_y}, f)

print(f"\n🎉 Model training complete! Artifact saved cleanly to: {MODEL_SAVE_PATH}")