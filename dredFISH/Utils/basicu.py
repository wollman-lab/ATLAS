"""Misc functions that provide functionality to dredFISH module

"""

from typing import Union
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import jensenshannon, pdist, squareform
from sklearn.decomposition import LatentDirichletAllocation
from scipy import sparse
import logging
import itertools
from collections import Counter
from pyemd import emd


def normalize_data(X, in_place = False, norm_cell=True, norm_basis=True,onlypos = True):
    """Row and col normalization of data
    
    Parameters
    ----------
    Xorg : numpy 2D matrix
            The data to normalized in the forms of cells (rows) x basis (cols)
    in_place : bool (default = False)
        are calculatoins done in place or should we create a new copy of the data? 
    norm_cell : bool
        should row be normalized to sum to 1? 
    norm_basis : bool 
        should columns be normalized using z-score? 
    onlypos : bool
        should negative data (<0) be cliped to 0? 

    Returns
    -------
    Xnrm : numpy 2D matrix
        The normalized matrix. 
    

    """
    
    Xnrm = X.copy()
    
    # clip at 0
    if onlypos:
        X = np.clip(X, 0, None)

    # total counts per cell
    basissum = X.sum(axis=1)
    logging.info(f"{basissum.shape[0]} cells, minimum counts = {basissum.min()}")

    # normalize by cell 
    if norm_cell:
        X = X/basissum.reshape(-1,1)

    # normalize by bit
    if norm_basis:
        X = zscore(X, axis=0) # 0 - across rows (cells) for each col (bit) 

    return X # finalized



def reset_logging(**kwargs):
    """reset logging.
    """
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # logging.basicConfig(level=logging.WARNING)
    logging.basicConfig(**kwargs)
    return

def rank_array(array):
    """Return ranking of each element of an array
    """
    array = np.array(array)
    temp = array.argsort()
    ranks = np.empty_like(temp)
    ranks[temp] = np.arange(len(array))
    return ranks

def rank_rows(matrix):
    """Return rankings of each rwo in a 2d array
    """
    matrix = np.array(matrix)
    return np.apply_along_axis(rank_array, 1, matrix) # row = 1

def spearman_corrcoef(X, Y):
    """return spearman correlation matrix for each pair of rows of X and Y
    """
    return np.corrcoef(rank_rows(X), rank_rows(Y))

def spearmanr_paired_rows(X, Y):
    """with p-value, slow
    """
    X = np.array(X)
    Y = np.array(Y)
    corrs = []
    ps = []
    for x, y in zip(X, Y):
        r, p = stats.spearmanr(x, y)
        corrs.append(r)
    return np.array(corrs), np.array(ps)

def corr_paired_rows_fast(X, Y, offset=0, mode='pearsonr'):
    """low memory compared to fast2
    """
    if mode == 'pearsonr':
        X = np.array(X)
        Y = np.array(Y)
    elif mode == 'spearmanr':
        # rank
        X = rank_rows(X)
        Y = rank_rows(Y)
    # zscore
    X = (X - X.mean(axis=1).reshape(-1,1))/(X.std(axis=1).reshape(-1,1)+offset)
    Y = (Y - Y.mean(axis=1).reshape(-1,1))/(Y.std(axis=1).reshape(-1,1)+offset)
    # corrs
    corrs = (X*Y).mean(axis=1)
    return corrs

def corr_paired_rows_fast2(X, Y, offset=0, nan_to_num=False, mode='pearsonr'):
    """
    """
    if mode == 'pearsonr':
        X = np.array(X)
        Y = np.array(Y)
    elif mode == 'spearmanr':
        # rank
        X = rank_rows(X)
        Y = rank_rows(Y)
    # zscore
    xz = stats.zscore(X, axis=1, nan_policy='propagate', ddof=0)
    yz = stats.zscore(Y, axis=1, nan_policy='propagate', ddof=0)
    xy_cc = np.nanmean(xz*yz, axis=1)

    if nan_to_num:
        xy_cc = np.nan_to_num(xy_cc) # turn np.nan into zero
    return xy_cc

def get_index_from_array(arr, inqs, na_rep=-1):
    """Get index of array
    """
    arr = np.array(arr)
    arr = pd.Series(arr).reset_index().set_index(0)
    idxs = arr.reindex(inqs)['index'].fillna(na_rep).astype(int).values
    return idxs

def diag_matrix(X, rows=np.array([]), cols=np.array([]), threshold=None):
    """Diagonalize a matrix as much as possible
    threshold controls the level of diagnalization
    a smaller threshold enforces more number of strict diagnal values,
    while encourages less number of free columns (quasi-diagnal)
    """
    di, dj = X.shape
    transposed = 0
    
    # enforce nrows <= ncols
    if di > dj:
        di, dj = dj, di
        X = X.T.copy()
        rows, cols = cols.copy(), rows.copy()
        transposed = 1
        
    # start (di <= dj)
    new_X = X.copy()
    new_rows = rows.copy() 
    new_cols = cols.copy() 
    if new_rows.size == 0:
        new_rows = np.arange(di)
    if new_cols.size == 0:
        new_cols = np.arange(dj)
        
    # bring the greatest values in the lower right matrix to diagnal position 
    for idx in range(min(di, dj)):

        T = new_X[idx: , idx: ]
        i, j = np.unravel_index(T.argmax(), T.shape) # get the coords of the max element of T
        
        if threshold and T[i, j] < threshold:
            dm = idx # new_X[:dm, :dm] is done (0, 1, ..., dm-1) excluding dm
            break
        else:
            dm = idx+1 # new_X[:dm, :dm] will be done

        # swap row idx, idx+i
        tmp = new_X[idx, :].copy()
        new_X[idx, :] = new_X[idx+i, :].copy() 
        new_X[idx+i, :] = tmp 
        
        tmp = new_rows[idx]
        new_rows[idx] = new_rows[idx+i]
        new_rows[idx+i] = tmp

        # swap col idx, idx+j
        tmp = new_X[:, idx].copy()
        new_X[:, idx] = new_X[:, idx+j].copy() 
        new_X[:, idx+j] = tmp 
        
        tmp = new_cols[idx]
        new_cols[idx] = new_cols[idx+j]
        new_cols[idx+j] = tmp
        
    # 
    if dm == dj:
        pass
    elif dm < dj: # free columns

        col_dict = {}
        sorted_col_idx = np.arange(dm)
        free_col_idx = np.arange(dm, dj)
        linked_rowcol_idx = new_X[:, dm:].argmax(axis=0)
        
        for col in sorted_col_idx:
            col_dict[col] = [col]
        for col, key in zip(free_col_idx, linked_rowcol_idx): 
            if key in col_dict.keys():
                col_dict[key] = col_dict[key] + [col]
            else:
                col_dict[key] = [col]
                
            
        new_col_order = np.hstack([col_dict[key] for key in sorted(col_dict.keys())])
        
        # update new_X new_cols
        new_X = new_X[:, new_col_order].copy()
        new_cols = new_cols[new_col_order]
    else:
        raise ValueError("Unexpected situation: dm > dj")
    
    if transposed:
        new_X = new_X.T
        new_rows, new_cols = new_cols, new_rows
    return new_X, new_rows, new_cols 

def diag_matrix_rows(X):
    """Diagonalize a matrix as much as possible by only rearrange rows
    """
    di, dj = X.shape
    
    new_X = np.array(X.copy())
    new_rows = np.arange(di) 
    new_cols = np.arange(dj) 
    
    # free to move rows
    row_dict = {}
    free_row_idx = np.arange(di)
    linked_rowcol_idx = new_X.argmax(axis=1) # the column with max value for each row
    
    for row, key in zip(free_row_idx, linked_rowcol_idx): 
        if key in row_dict.keys():
            row_dict[key] = row_dict[key] + [row]
        else:
            row_dict[key] = [row]
            
    new_row_order = np.hstack([row_dict[key] for key in sorted(row_dict.keys())])
    # update new_X new_cols
    new_X = new_X[new_row_order, :].copy()
    new_rows = new_rows[new_row_order]
    
    return new_X, new_rows, new_cols 

def encode_mat(a, d, entrysize=1):
    """ Given a matrix and a dictionary; map elements of a according to d
    a - numpy array
    d - dictionary
    """
    u,inv = np.unique(a,return_inverse = True)
    if entrysize == 1:
        b = np.array([d[x] for x in u])[inv].reshape(a.shape)
        return b
    elif entrysize > 1:
        theshape = np.hstack([a.shape, entrysize])
        b = np.array([d[x] for x in u])[inv].reshape(theshape)
        return b

def group_sum(mat, groups, group_order=[]):
    """
    mat is a matrix (cell-by-feature) ; group are the labels (for each cell).
    
    this can be speed up!!! take advantage of the cluster label structure... check my metacell analysis script as well
    """
    m, n = mat.shape
    assert m == len(groups)
    if len(group_order) == 0:
        group_order = np.unique(groups)
    
    group_idx = get_index_from_array(group_order, groups)
    groupmat = sparse.csc_matrix(([1]*m, (group_idx, np.arange(m)))) # group by cell
    
    return groupmat.dot(mat), group_order

def group_mean(mat, groups, group_order=[], expand=False):
    """
    mat is a matrix (cell-by-feature) ; group are the labels (for each cell).
    """
    m, n = mat.shape
    assert m == len(groups)
    if len(group_order) == 0:
        group_order = np.unique(groups)
    
    group_idx = get_index_from_array(group_order, groups)
    groupmat = sparse.csc_matrix(([1]*m, (group_idx, np.arange(m)))) # group by cell
    groupmat_norm = groupmat/np.sum(groupmat, axis=1)  # row
    
    if not expand:
        return np.asarray(groupmat_norm.dot(mat)), group_order
    else:
        return np.asarray(groupmat.T.dot(groupmat_norm.dot(mat)))

def libsize_norm(mat):
    """cell by gene matrix, norm to median library size
    assume the matrix is in sparse format, the output will keep sparse
    """
    lib_size = mat.sum(axis=1)
    lib_size_median = np.median(lib_size)

    matnorm = (mat/lib_size.reshape(-1,1))*lib_size_median
    return matnorm

def sparse_libsize_norm(mat):
    """cell by gene matrix, norm to median library size
    assume the matrix is in sparse format, the output will keep sparse
    """
    lib_size = np.ravel(mat.sum(axis=1))
    lib_size_median = np.median(lib_size)

    lib_size_inv = sparse.diags(lib_size_median/lib_size)
    matnorm = lib_size_inv.dot(mat)
    return matnorm

def zscore(v, allow_nan=False, **kwargs):
    """
    v is an numpy array (any dimensional)

    **kwargs are arguments of np.mean and np.std, such as


    axis=0 # zscore across rows for each column (if v is 2-dimensional)
    axis=1 # zscore across cols for each row  (if v is 2-dimensional)
    """
    if allow_nan:
        return (v-np.nanmean(v, **kwargs))/(np.nanstd(v, **kwargs))
    else:
        return (v-np.mean(v, **kwargs))/(np.std(v, **kwargs))

def stratified_sample(df, col, n: Union[int, dict], return_idx=False, group_keys=False, sort=False, random_state=0, **kwargs):
    """
    n (int) represents the number for each group
    n (dict) can be used to sample different numbers for each group
    """
    if isinstance(n, int):
        dfsub = df.groupby(col, group_keys=group_keys, sort=sort, **kwargs).apply(
            lambda x: x.sample(n=min(len(x), n), random_state=random_state)
            )
    elif isinstance(n, dict):
        dfsub = df.groupby(col, group_keys=group_keys, sort=sort, **kwargs).apply(
            lambda x: x.sample(n=min(len(x), n[x[col].iloc[0]]), random_state=random_state)
            )

    if not return_idx:
        return dfsub
    else:
        idx = get_index_from_array(df.index.values, dfsub.index.values)
        return dfsub, idx


def clip_by_percentile(vector, low_p=5, high_p=95):
    """
    """
    low_val = np.percentile(vector, low_p)
    high_val = np.percentile(vector, high_p)
    vector_clip = np.clip(vector, low_val, high_val)
    return vector_clip

def rank(arr, **kwargs):
    """rank is equivalent to argsort twice
    """
    arr = np.array(arr)
    return np.argsort(np.argsort(arr, **kwargs), **kwargs)


def count_values(V,refvals,sz = None,norm_to_one = True):
    """
    count_values - simple tabulation with default values (refvals)
    """
    Cnt = Counter(V)
    if sz is not None: 
        for i in range(len(V)): 
            Cnt.update({V[i] : sz[i]-1}) # V[i] is already represented, so we need to subtract 1 from sz[i]  
            
    cntdict = dict(Cnt)
    missing = list(set(refvals) - set(V))
    cntdict.update(zip(missing, np.zeros(len(missing))))
    Pv = np.array([cntdict.get(k) for k in sorted(cntdict.keys())])
    if norm_to_one:
        Pv=Pv/np.sum(Pv)
    return(Pv)

def dist_emd(E1,E2,Dsim):
    
    if E2 is None: 
        cmb = np.array(list(itertools.combinations(np.arange(E1.shape[0]), r=2)))
        D = dist_emd(E1[cmb[:,0],:],E1[cmb[:,1],:],Dsim)
    else:
        sum_of_rows = E1.sum(axis=1)
        E1 = E1 / sum_of_rows[:, None]
        E1 = E1.astype('float64')
        sum_of_rows = E2.sum(axis=1)
        E2 = E2 / sum_of_rows[:, None]
        E2 = E2.astype('float64')
        D = np.zeros(E1.shape[0])
        Dsim = Dsim.astype('float64')
        for i in range(E1.shape[0]):
            e1=E1[i,:]
            e2=E2[i,:]
            D[i] = emd(e1,e2,Dsim)
    
    return D

def dist_jsd(M1,M2 = None):
    if M2 is None: 
        D = pdist(M1,metric = 'jensenshannon')
    else: 
        D = jensenshannon(M1,M2,base=2,axis=1)
    return D



