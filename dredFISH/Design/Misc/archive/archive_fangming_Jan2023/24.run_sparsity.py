import numpy as np
import torch
import os
from dredFISH.Design.model_v2p3_sparsity import train_model
from dredFISH.Design.data_loader_scrna import load_Allen_data
import sys
import glob

# device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu') # GPU if exists
# device = 'cpu'
device = None
disable_tqdm = True # False # True # False
print(f"disable tqdm (clean log): {disable_tqdm}")
print(f"GPU: {torch.cuda.is_available()}")
print(f"Use: {device}")

n_epochs = 6
n_iter = None #3 

lmd0 = 1 
lmd2 = 1
lmd3 = 1
n_bits = [12, 18, 24]
n_rcn = 0 # 1, 2, 3, 0 
lr = 1e-2
scales = [100, 200, 500, 1e3, 2e3, 5e3, 1e4, 2e4, 5e4, 1e5,]
noise = None #(1e1, 1)
# scale = 1.5e5
# noise = (1e5, 1e4)

studybatch = f"types_v24_Sep7"

# load data
trn_dataloader = load_Allen_data(
    datasetkey='smrt_trn', 
    keyX='counts', keyY='l3_code', keyYcat='l3_cat', 
    batch_size=64,
)
tst_dataloader = load_Allen_data(
    datasetkey='smrt_tst', 
    keyX='counts', keyY='l3_code', keyYcat='l3_cat', 
    batch_size=500,
)

# gsubidx = torch.tensor(np.arange(n_gns)).to(device) # selected genes for recon
f = os.path.join('/bigstore/GeneralStorage/fangming/projects/dredfish/data/', 'rna', 'gidx_sub140_smrt_v1.pt')
gsubidx = torch.load(f)

f = os.path.join('/bigstore/GeneralStorage/fangming/projects/dredfish/data/', 'rna', 'gidx_cnstrnts_pshop_mm10_isoflat.pt')
cnstrnts_idx = torch.load(f)
f = os.path.join('/bigstore/GeneralStorage/fangming/projects/dredfish/data/', 'rna',      'cnstrnts_pshop_mm10_isoflat.pt')
cnstrnts = torch.load(f)

# train
for n_bit in n_bits:
    for scale in scales:
        res_path = f'/bigstore/GeneralStorage/fangming/projects/dredfish/res_nn/{studybatch}_scale{scale:.1e}_lmd0{lmd0:.2e}_lmd2{lmd2:.2e}_nbit{n_bit}_nrcn{n_rcn}_lr{lr:.1g}'
        print(res_path)
        train_model(trn_dataloader, tst_dataloader, 
                    res_path, 
                    gsubidx, 
                    cnstrnts_idx,
                    cnstrnts,
                    lmd0, lmd2, lmd3,
                    n_bit=n_bit, n_rcn_layers=n_rcn, 
                    scale=scale, noise=noise,
                    lr=lr, n_epochs=n_epochs, n_iter=n_iter, 
                    # path_trained_model=path_trained_model,
                    disable_tqdm=disable_tqdm,
                    device=device,
                    )
