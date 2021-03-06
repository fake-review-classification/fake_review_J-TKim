import logging
from platform import python_version
import random
import argparse

import numpy as np
import torch
import sklearn
import torch.nn as nn
import pandas as pd
import matplotlib
import transformers
from torch.autograd import Variable
from sklearn.metrics import roc_auc_score

from preprocessing import preprocessing
from tokenize_and_pad_text import *
from train_model import KimCNN, train_test_model


random_seed = 42

torch.manual_seed(random_seed)
torch.cuda.manual_seed(random_seed)
# torch.cuda.manual_seed_all(random_seed) # if use multi-GPU
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
np.random.seed(random_seed)
random.seed(random_seed)

print('version')
print(f"python version=={python_version()}")
print(f"pandas=={pd.__version__}")
print(f"numpy=={np.__version__}")
print(f"torch=={torch.__version__}")
print(f"sklearn=={sklearn.__version__}")
print(f"transformers=={transformers.__version__}")
print(f"matplotlib=={matplotlib.__version__}",end='\n\n')

model_class = transformers.BertModel
tokenizer_class = transformers.BertTokenizer
pretrained_weights = 'bert-base-uncased'
target_columns = ['label']

max_seq = 128
bert_batch_size = 16

kernel_num = 3
kernel_sizes = [2, 3, 4]
dropout = 0.5
static = True

n_epochs = 50
patience = 10
batch_size = 64
lr = 0.001
k_fold = 5
optimizer = torch.optim.Adam
loss_fn = nn.BCELoss()

# If there's a GPU available...
if torch.cuda.is_available():    

    # Tell PyTorch to use the GPU.    
    device = torch.device("cuda")

    print(f'There are {torch.cuda.device_count()} GPU(s) available.')

    print(f'We will use the GPU: {torch.cuda.get_device_name(0)}', end='\n\n')

# If not...
else:
    print('No GPU available, using the CPU instead.')
    device = torch.device("cpu", end='\n\n')

logging.getLogger("transformers.tokenization_utils").setLevel(logging.ERROR)

data_path = '../reviews.csv'
data_name = data_path.split('/')[-1]
print(f'use {data_name} data', end='\n')
df = pd.read_csv(data_path)

def main(threshold):
    if threshold == 1:
        print('test with all word!!!')
    else:
        print(f'start threshold {threshold}!!!')
    preprocessing_class = preprocessing(df, threshold=threshold)

    df_train, df_val, df_test, (real_dict, fake_dict) = preprocessing_class.preprocessing_all()
    
    print('make train data ...')
    x_train, y_train = tokenize_and_pad_text_bert(df_train, device, model_class, tokenizer_class, pretrained_weights,
                                                max_seq=max_seq, batch_size=bert_batch_size, target_columns=target_columns)

    print('make valid data ...')
    x_val, y_val = tokenize_and_pad_text_bert(df_val, device, model_class, tokenizer_class, pretrained_weights,
                                                max_seq=max_seq, batch_size=bert_batch_size, target_columns=target_columns)

    print('make test data ...')
    x_test, y_test = tokenize_and_pad_text_bert(df_test, device, model_class, tokenizer_class, pretrained_weights,
                                                max_seq=max_seq, batch_size=bert_batch_size, target_columns=target_columns)

    embed_num = x_train.shape[1]
    embed_dim = x_train.shape[2]
    class_num = y_train.shape[1]

    auc_score_list = []
    
    for fold in range(k_fold):
        model = KimCNN(
            embed_num=embed_num,
            embed_dim=embed_dim,
            class_num=class_num,
            kernel_num=kernel_num,
            kernel_sizes=kernel_sizes,
            dropout=dropout,
            static=static,
        )

        model = model.to(device)

        # train and test
        review_classification_model = train_test_model(model)
        # auc_score_list = review_classification_model.kfold_train_test(x_train, y_train, x_test, y_test, kwargs, k_fold=5)

        review_classification_model.train(x_train, y_train, x_val, y_val, fold=0, patience=patience)
        y_test_np, y_preds_np = review_classification_model.test(x_test, y_test)

        auc_score = roc_auc_score(y_test_np, y_preds_np, average=None)
        print(f'k_fold: {fold+1}/{k_fold},\tauc score: {auc_score}')
        auc_score_list.append(auc_score)
        
    print(f'threshold: {threshold},\tauc score: {np.mean(auc_score_list)}, std: {np.std(auc_score_list)}')
    return auc_score_list

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(descroption='hyperparameter')
    parser.add_argument('--threshold', '-t', type=float, default=1, help='threshold t: 0 <= t <= 1')
    args = parser.parse_args()

    main(args.threshold)