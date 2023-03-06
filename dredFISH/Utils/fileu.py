import numpy as np
import cv2 
import pandas as pd
import os
import anndata
import logging
import shapely
from datetime import datetime
import torch

def check_existance(path='',hybe='',channel='',type='',model_type='',dataset='',section='',logger='FileU'):
    """
    check_existance Check if File Existsin accordance with established file structure

    :param path: Path to Section /Storage/Images20**/User/Project/Dataset/fishdata/Dataset/Section/
    :type path: str, optional
    :param hybe: name of hybe ('hybe1','Hybe1','1')
    :type hybe: str, optional
    :param channel: Name of Channel ('DeepBlue', 'FarRed',...)
    :type channel: str, optional
    :param type: Data Type to save ('stitched','mask','anndata',...)
    :type type: str, optional
    :param model_type: segmentation Type ('total','nuclei','cytoplasm')
    :type model_type: str, optional
    :param logger: Logger to send logs can be a name of logger, defaults to 'FileU'
    :type logger: str, logging.Logger, optional
    :return : True of file exists, False otherwise
    :rtype : bool
    """
    filename = generate_filename(path,hybe,channel,type,model_type,dataset,section,logger=logger)
    return os.path.exists(filename)

def generate_filename(path,hybe,channel,type,model_type,dataset,section,logger='FileU'):
    """
    fname Generate File Name 

    :param path: Path to Section /Storage/Images20**/User/Project/Dataset/fishdata/Dataset/Section/
    :type path: str
    :param hybe: name of hybe ('hybe1','Hybe1','1')
    :type hybe: str
    :param channel: Name of Channel ('DeepBlue', 'FarRed',...)
    :type channel: str
    :param type: Data Type to save ('stitched','mask','anndata',...)
    :type type: str
    :param model_type: context dependents. For segmentation is Type ('total','nuclei','cytoplasm') for Layer it's layer type
    :type model_type: str
    :param logger: Logger to send logs can be a name of logger, defaults to 'FileU'
    :type logger: str, logging.Logger, optional
    :return: File Path
    :rtype: str
    """
    # normalize path (removes trailing / and makes two consecutive // into /)
    path = os.path.normpath(path)
    # infer section and dataset from path if both are missing. 
    if section == '' and dataset == '':
        (prefix,section) = os.path.split(path)
        (prefix,dataset) = os.path.split(prefix)
    
    out_path = os.path.join(path,type)
    if not os.path.exists(out_path):
        update_user('Making Type Path',logger=logger)
        os.mkdir(out_path)

    if 'hybe' in hybe:
        hybe = hybe.split('hybe')[-1]
    if not 'Hybe' in hybe:
        hybe = 'Hybe'+hybe
    if type == 'anndata':
        fname = dataset+'_'+section+'_'+model_type+'_'+type+'.h5ad'
    elif type =='matrix':
        fname = dataset+'_'+section+'_'+model_type+'_'+type+'.csv'
    elif type == 'metadata':
        fname = dataset+'_'+section+'_'+model_type+'_'+type+'.csv'
    elif type == 'mask':
        fname = dataset+'_'+section+'_'+model_type+'_'+'mask_stitched'+'.pt'
    elif type == 'image':
        fname = dataset+'_'+section+'_'+hybe+'_'+channel+'_'+'stitched'+'.tif'
    elif type == 'stitched':
        fname = dataset+'_'+section+'_'+hybe+'_'+channel+'_'+type+'.pt'
    elif type == 'FF':
        fname = dataset+'_'+section+'_'+channel+'_'+type+'.pt'
    elif type == 'Layer':
        fname = dataset+'_'+model_type+'_'+type+'.h5ad'
    elif type == 'Taxonomy': 
        fname = dataset+'_'+model_type+'_'+type+'.csv'
    elif type == 'Geom':
        fname = dataset+'_'+section+'_'+model_type+'_'+type+'.wkt'
    else:
        update_user('Unsupported File Type '+type,level=40,logger=logger)
        fname = dataset+'_'+section+'_'+hybe+'_'+channel+'_'+type
    fname = os.path.join(out_path,fname)
    return fname

def save(data,path='',hybe='',channel='',type='',model_type='',dataset='',section='',logger='FileU'):
    """
    save save File in accordance with established file structure

    :param data: data object to be saved
    :type path: object
    :param path: Path to Section /Storage/Images20**/User/Project/Dataset/fishdata/Dataset/Section/
    :type path: str
    :param hybe: name of hybe ('hybe1','Hybe1','1')
    :type hybe: str, optional
    :param channel: Name of Channel ('DeepBlue', 'FarRed',...)
    :type channel: str, optional
    :param type: Data Type to save ('stitched','mask','anndata',...)
    :type type: str, optional
    :param model_type: segmentation Type ('total','nuclei','cytoplasm')
    :type model_type: str, optional
    :param logger: Logger to send logs can be a name of logger, defaults to 'FileU'
    :type logger: str, logging.Logger, optional
    """
    fname = generate_filename(path,hybe,channel,type,model_type,dataset,section,logger=logger)
    update_user('Saving '+type,level=10,logger=logger)
    if type == 'anndata':
        data.write(fname)
    elif type =='matrix':
        data.to_csv(fname)
    elif type == 'metadata':
        data.to_csv(fname)
    elif type == 'mask':
        torch.save(data,fname)
    elif type == 'image':
        if not isinstance(data,np.ndarray):
            data = data.numpy()
        data = data.copy()
        data[data<np.iinfo('uint16').min] = np.iinfo('uint16').min
        data[data>np.iinfo('uint16').max] = np.iinfo('uint16').max
        cv2.imwrite(fname, data.astype('uint16'))
    elif type == 'stitched':
        torch.save(data,fname)
    elif type == 'FF':
        torch.save(data,fname)
    elif type == 'Layer':
        data.write(fname)
    elif type == 'Taxonomy':
        data.to_csv(fname)
    elif type == 'Geom':
        save_polygon_list(data,fname)
    else:
        update_user('Unsupported File Type '+type,level=30,logger=logger)

def load(path='',hybe='',channel='',type='anndata',model_type='',dataset='',section='',logger='FileU'):
    """
    load load File in accordance with established file structure

    :param path: Path to Section /Storage/Images20**/User/Project/Dataset/fishdata/Dataset/Section/
    :type path: str
    :param hybe: name of hybe ('hybe1','Hybe1','1')
    :type hybe: str, optional
    :param channel: Name of Channel ('DeepBlue', 'FarRed',...)
    :type channel: str, optional
    :param type: Data Type to save ('stitched','mask','anndata',...)
    :type type: str, optional
    :param model_type: segmentation Type ('total','nuclei','cytoplasm')
    :type model_type: str, optional
    :param logger: Logger to send logs can be a name of logger, defaults to 'FileU'
    :type logger: str, logging.Logger, optional
    :return : Desired Data Object or None if not found
    :rtype : object
    """
    fname = generate_filename(path,hybe,channel,type,model_type,dataset,section,logger=logger)
    if os.path.exists(fname):
        update_user('Loading '+type,level=10,logger=logger)
        if type == 'anndata':
            data = anndata.read_h5ad(fname)
        elif type =='matrix':
            data = pd.read_csv(fname)
        elif type == 'metadata':
            data = pd.read_csv(fname)
        elif type == 'mask':
            data = torch.load(fname)
        elif type == 'image':
            data = cv2.imread(fname,cv2.IMREAD_UNCHANGED)
            data = data.astype('uint16')
        elif type == 'stitched':
            data = torch.load(fname)
        elif type == 'FF':
            data = torch.load(fname)
        elif type == 'Layer':
            data = anndata.read_h5ad(fname)
        elif type == 'Taxonomy':
            data = pd.read_csv(fname)
        elif type == 'Geom':
            data = load_polygon_list(fname)        
        else:
            update_user('Unsupported File Type '+type,level=30,logger=logger) 
            data = None
        return data
    else:
        update_user('File Does Not Exist '+fname,level=30,logger=logger)
        return None

def update_user(message,level=20,logger=None):
    """
    update_user Send string messages to logger with various levels OF IMPORTANCE

    :param message: _description_
    :type message: str
    :param level: _description_, defaults to 20
    :type level: int, optional
    :param logger: Logger to send logs can be a name of logger, defaults to 'FileU'
    :type logger: str, logging.Logger, optional
    """
    if isinstance(logger,logging.Logger):
        log = logger
    elif isinstance(logger,str):
        log = logging.getLogger(logger)
    elif isinstance(log,type(None)):
        log = logging.getLogger('Update_User')
    else:
        log = logging.getLogger('Unknown Logger')
    if level<=10:
        log.debug(♦+' '+str(message))
    elif level==20:
        log.info(str(datetime.now().strftime("%H:%M:%S"))+' '+str(message))
    elif level==30:
        log.warning(str(datetime.now().strftime("%H:%M:%S"))+' '+str(message))
    elif level==40:
        log.error(str(datetime.now().strftime("%H:%M:%S"))+' '+str(message))
    elif level>=50:
        log.critical(str(datetime.now().strftime("%H:%M:%S"))+' '+str(message))

def save_polygon_list(polys,fname):
    """
    Simple polygon saving utility 
    """
    with open(fname, "w") as f:
        for p in polys:
            wkt = shapely.wkt.dumps(p)
            f.write(wkt + "\n")

def load_polygon_list(fname):
    polys = list()
    with open(fname) as file:
        for line in file:
            wktstr = line.rstrip()
            p = shapely.wkt.loads(wktstr)
            polys.append(p)
    return polys