
import numpy as np
import pandas as pd
import re
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset
from collections import Counter

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

df = pd.read_csv("IMDB Dataset.csv")

def text_cleanup(txt):
    return re.sub(r"[^a-zA-Z ]", "", txt.lower())

df["review"] = df["review"].apply(text_cleanup)

def split_into_words(txt):
    return txt.split()

words_in_reviews = [split_into_words(r) for r in df["review"]]

word_freqs = Counter(word for review in words_in_reviews for word in review)

vocab_size = 20000
word_to_num = {word: i + 2 for i, (word, _) in enumerate(word_freqs.most_common(vocab_size))}
word_to_num["<BLANK>"] = 0
word_to_num["<MISS>"] = 1

def convert_words_to_numbers(words, word_map, max_length=300):
    return [word_map.get(word, 1) for word in words][:max_length] + [0] * max(0, max_length - len(words))

X = torch.tensor([convert_words_to_numbers(r, word_to_num) for r in words_in_reviews], dtype=torch.long)
y = torch.tensor((df["sentiment"] == "positive").astype(int).values, dtype=torch.float32)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

batch_amt = 256
train_loader = DataLoader(TensorDataset(X_train.to(device), y_train.to(device)), batch_size=batch_amt, shuffle=True)
test_loader = DataLoader(TensorDataset(X_test.to(device), y_test.to(device)), batch_size=batch_amt, shuffle=False)

word_embed_dim = 50
random_matrix = torch.randn(len(word_to_num), word_embed_dim).to(device)

class RNN(nn.Module):
    def __init__(self, embed_mat, hidden_layer_size, final_output):
        super().__init__()
        num_words, embed_size = embed_mat.shape
        self.embeddings = nn.Embedding.from_pretrained(embed_mat, freeze=False)
        self.lstm_layer = nn.LSTM(embed_size, hidden_layer_size, batch_first=True, bidirectional=False)
        self.output_layer = nn.Linear(hidden_layer_size, final_output)

    def forward(self, x):
        embedded = self.embeddings(x)
        _, (hidden, _) = self.lstm_layer(embedded)
        return self.output_layer(hidden[-1])

hidden_layer_size = 256
final_output = 1
model = RNN(random_matrix, hidden_layer_size, final_output).to(device)

loss_function = nn.BCEWithLogitsLoss()
optimizer_tool = optim.AdamW(model.parameters(), lr=0.005)

epoch_count = 15
for e in range(epoch_count):
    model.train()
    total_loss = 0
    for x_values, y_values in train_loader:
        x_values, y_values = x_values.to(device), y_values.to(device)
        optimizer_tool.zero_grad()
        loss_value = loss_function(model(x_values).squeeze(), y_values)
        loss_value.backward()
        optimizer_tool.step()
        total_loss += loss_value.item()
    print(f"Epoch {e+1}, Loss: {total_loss / len(train_loader):.4f}")

model.eval()
correct, total = 0, 0
with torch.no_grad():
    for x_values, y_values in test_loader:
        x_values, y_values = x_values.to(device), y_values.to(device)
        predictions = torch.sigmoid(model(x_values).squeeze())
        predicted_labels = (predictions >= 0.5).float()
        correct += (predicted_labels == y_values).sum().item()
        total += y_values.size(0)

print("Final test accuracy:", round((correct / total) * 100, 2), "%")
