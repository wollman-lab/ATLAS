"""Classification of biospatial units in TMG analysis

This module contains the main classes related to the task of classification of biospatial units (i.e. cells, isozones, regions) into type. 
The module is composed of a class hierarchy of classifiers. The "root" of this heirarchy is an abstract base class "Classifier" that has two 
abstract methods (train and classify) that any subclass will have to implement. 

"""

from scipy.stats import mode
from scipy.spatial.distance import squareform
from scipy.optimize import minimize_scalar
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score 
import pynndescent 


import os.path 
import abc
import numpy as np
import pandas as pd
import itertools

from dredFISH.Analysis.TissueGraph import *
from dredFISH.Utils.basicu import *





    
    
class Classifier(metaclass=abc.ABCMeta): 
    """Interface for classifiers 

    This is an abstract class that defines the interface (i.e. methods and attributes) that all different classifiers must have. 
        
    Attributes
    ----------
    tax : Taxonomy
        A taxonomy system that the classifier classifies into. 
    """
    
    def __init__(self,tax = None): 
        """Create a classifier
        
        Parameters
        ----------
        tax : Taxnonomy system
            The taxonomical system that is used for classification. 
        """
        if tax is None: 
            tax = Taxonomy(name = 'clusters')
        self.tax = tax
        
        pass
        
    
    @abc.abstractmethod
    def train(self):
        """Trains a classifier
        """
        pass
    
    @abc.abstractmethod
    def classify(self,data):
        """Classifies input into types
        """
        pass
    
    
class KNNClassifier(Classifier): 
    """k-nearest-neighbor classifier
    
    Attributes
    ----------
    k : int (default = 1)
        The number of local neighbors to consider
    approx_nn : int (default = 30)
        Number of NN used by pynndescent to construct the approximate knn graph
    metric : str (default = 'correlation')
        What metric to use to determine similarity
        
    """
    def __init__(self,k=1,approx_nn= 30,metric = 'correlation'):
        """Define a KNN classifier
        
        Parameters
        ----------
        k : int
            the K in KNN
        approx_nn : int
            number of nearest neighbors used in pynndescent calculation of the knn graph
        metric : str
            what distance metric to use? 
        """
        super().__init__(tax = None)
        self.k = k
        self.approx_nn = approx_nn
        self.metric = metric
        pass

    def train(self,ref_data,ref_label_id):
        """ Builds approx. KNN graph for queries
        """
        self._knn = pynndescent.NNDescent(ref_data,n_neighbors = self.approx_nn, metric = self.metric)
        self._knn.prepare()
        self._ref_label_id = np.array(ref_label_id)
        
        # update the taxonomy
        self.tax.add_types(ref_label_id,ref_data)
        pass

    def classify(self,data): 
        """Find class of rows in data based on approx. KNN
        """
        # get indices and remove self. 
        indices,distances = self._knn.query(data,k=self.k)
        if self.k==1:
            ids = self._ref_label_id[indices]
        else:
            kids = self._ref_label_id[indices]
            ids = mode(kids,axis=1)
        return ids.flatten()
    

class OptimalLeidenKNNClassifier(KNNClassifier):
    """Classifiy cells based on unsupervized Leiden 
    
    This classifiers is trained using unsupervized learning with later classification done by knn (k=1)
    the implementations uses the same classify method is KNNClassifier.  
    The overladed train method does the unsupervized learning before calling super().train to create the KNN index.
    """
    def __init__(self,TG):
        """
        Parameters
        ----------
        TG : TissueGraph
            Required parameter - the TissueGraph object we're going to use for unsupervised clustering. 
        """
        if not isinstance(TG,TissueGraph): 
            raise ValueError("OptimalLeidenKNNClassifier requires a TissueGraph object as input")
            
        #set up the KNN portion
        super().__init__(k=1,approx_nn = 10,metric = 'correlation')
        self._TG = TG
        pass
    
    def train(self,opt_res = None, opt_params = {'iters' : 10, 'n_consensus' : 50}):
        """training for this class is performing optimal leiden clustering 
        
        Optimization is done over resolution parameter trying to maximize the TG conditional entropy. 
        The analysis uses the two graphs (spatial and features) and finds a resolution parameters that will maximize 
        the conditional entropy, H(Zone|Type). 
        
            
        Parameters
        ----------
        opt_params : dict
            Few parameters that control optimizaiton. 
            'iter' is the number of repeats in each optimization round. 
            'n_consensus' is the number of times to do the final clustering with optimal resolution.   
            
        """
            

        def ObjFunLeidenRes(res,return_types = False):
            """
            Basic optimization routine for Leiden resolution parameter. 
            Implemented using igraph leiden community detection
            """
            EntropyVec = np.zeros(opt_params['iters'])
            for i in range(opt_params['iters']):
                TypeVec = self._TG.FG.community_leiden(resolution_parameter=res,
                                                   objective_function='modularity').membership
                TypeVec = np.array(TypeVec).astype(np.int64)
                EntropyVec[i] = self._TG.contract_graph(TypeVec).cond_entropy()
            Entropy = EntropyVec.mean()
            if return_types: 
                return -Entropy,TypeVec
            else:
                return(-Entropy)

        if opt_res is None: 
            print(f"Calling initial optimization")
            sol = minimize_scalar(ObjFunLeidenRes, bounds = (0.1,30), 
                                                method='bounded',
                                                options={'xatol': 1e-2, 'disp': 3})
            self._opt_res = sol['x']
            ent = sol['fun']
            evls = sol['nfev']
        else: 
            self._opt_res = opt_res
            ent = -1
            evls = 0
        
        # consensus clustering
        TypeVec = np.zeros((self._TG.N,opt_params['n_consensus']))
        for i in range(opt_params['n_consensus']):
            ent,TypeVec[:,i] = ObjFunLeidenRes(self._opt_res,return_types = True)
            
        if opt_params['n_consensus']>1:
            cmb = np.array(list(itertools.combinations(np.arange(opt_params['n_consensus']), r=2)))
            rand_scr = np.zeros(cmb.shape[0])
            for i in range(cmb.shape[0]):
                rand_scr[i] = adjusted_rand_score(TypeVec[:,cmb[i,0]],TypeVec[:,cmb[i,1]])
            rand_scr = squareform(rand_scr)
            total_rand_scr = rand_scr.sum(axis=0)
            TypeVec = TypeVec[:,np.argmax(total_rand_scr)]
                                                  

        print(f"Number of types: {len(np.unique(TypeVec))} initial entropy: {ent} number of evals: {evls}")
        
        # train the KNN classifier using the types we found
        super().train(self._TG.feature_mat,TypeVec)
        
        # train doesn't return anything. 
        pass



class TopicClassifier(Classifier): 
    """Uses Latent Dirichlet Allocation to classify cells into regions types. 

    Decision on number of topics comes from maximizing overall entropy. 
    """


    def __init__(self,TG, ordr = 4):
        """
        Parameters
        ----------
        TG : TissueGraph
            Required parameter - the TissueGraph object we're going to use for unsupervised clustering. 
        """
        if not isinstance(TG,TissueGraph): 
            raise ValueError("TopicClassifier requires a (cell level) TissueGraph object as input")

        super().__init__(tax = None)
        self.tax.name = 'topics'
        self._TG = TG
        Env = self._TG.extract_environments(ordr=ordr)
        row_sums = Env.sum(axis=1)
        row_sums = row_sums[:,None]
        Env = Env/row_sums
        self.Env = Env


    def train(self,use_parallel = False,max_num_of_topics = 100):
        """fit multiple LDA models and chose the one with highest type entropy
        """
        
        Ntopics = np.arange(2,max_num_of_topics)  
        
        if use_parallel: 
            logging.info("Running LDA in parallel")
            # define function handle
            def lda_fit(n_topics,Env = None):
                lda = LatentDirichletAllocation(n_components=n_topics)
                B = lda.fit(Env)
                T = lda.transform(Env)
                return (B,T)

            # start parallel engine
            rc = ipp.Client()
            dview = rc[:]
            dview.push({'Env': self.Env})
            with dview.sync_imports():
                import sklearn.decomposition
            # add env to lda_fit to create new function handle we can use in parallel
            g = functools.partial(lda_fit, Env=self.Env)
            result = dview.map_sync(g,Ntopics)
        else:
            logging.info("Running LDA n serial") 
            result = list()
            for i in range(len(Ntopics)):
                lda = LatentDirichletAllocation(n_components=Ntopics[i])
                B = lda.fit(self.Env)
                T = lda.transform(self.Env)
                result.append((B,T))
                
        IDs = np.zeros((self._TG.N,len(result)))
        for i in range(len(result)):
            IDs[:,i] = np.argmax(result[i][1],axis=1)
        Type_entropy = np.zeros(IDs.shape[1])
        for i in range(IDs.shape[1]):
            _,cnt = np.unique(IDs[:,i],return_counts=True)
            cnt=cnt/cnt.sum()
            Type_entropy[i] = entropy(cnt,base=2) 

        self._lda = result[np.argmax(Type_entropy)][0]

        return self


    def classify(self,data):
        """classify based on fitted LDA"""
        topics_prob = self._lda.transform(data)
        topics = np.argmax(topics_prob,axis=1)

        # renumber topics 
        unq,ix = np.unique(topics,return_inverse=True)
        id = np.arange(len(unq))
        topics = id[ix]

        return topics