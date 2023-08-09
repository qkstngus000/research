import numpy as np
import numpy.linalg as la
import sys
sys.path.append("../")
import matplotlib.pyplot as plt

# Package for importing image representation
from PIL import Image, ImageOps

from src.compress_sensing_library import *
from src.utility_library import *
import pandas as pd
import itertools
import dask
from dask.distributed import Client, progress
import time
import os.path

import argparse
import pywt



def run_sweep(method, img, observation, mode, dwt_type, lv, alpha_list, num_cell, cell_size, sparse_freq):
    ''' Generate a sweep over desired hyperparameters and saves results to a file.
    
    Parameters
    ----------
    method : String
        Method of reconstruction ('dwt' or 'dct')
    
    img : String
        Name of image to reconstruct (e.g. 'tree_part1.jpg')

    observation : String
        Method of observation (e.g. pixel, gaussian, v1)
    
    mode : String
        Desired mode to reconstruct image (e.g. 'Color' for RGB, 'Black' for greyscaled images).

    dwt_type : String
        Type of dwt method to be used -- see pywt.wavelist() for all possible dwt types.
        
    lv : List of int
        List of one or more integers in [1, 4].
        
    alpha_list : List of float
        Penalty for fitting data onto LASSO function to search for significant coefficents

    num_cell : List of int
        Number of blobs that will be used to be determining which pixels to grab and use
    
    cell_size : List of int
        Determines field size of opened and closed blob of data. Affect the data training

    sparse_freq : List of int
        Determines filed frequency on how frequently opened and closed area would appear. Affect the data training
        
    '''


    delay_list = []
    rep = np.arange(20)
    image_nm = img.split('.')[0]
    img_arr = process_image(img, mode)

    # call dask
    client = Client()
    # give non-V1 param search space
    if observation.upper() != 'V1':
        # specify search space for dct and dwt params
        if method.lower() == 'dct':
            search_list = [rep, alpha_list, num_cell]
            search = list(itertools.product(*search_list))
            search_df = pd.DataFrame(search, columns= [ 'rep', 'alp', 'num_cell'])
            sim_wrapper = lambda rep, alp, num_cell: run_sim_dct(method, observation, mode, rep, alp, num_cell, img_arr)
        elif method.lower() == 'dwt':
            search_list = [rep, lv, alpha_list, num_cell]
            search = list(itertools.product(*search_list))             
            search_df = pd.DataFrame(search, columns= [ 'rep', 'lv', 'alp', 'num_cell'])
            sim_wrapper = lambda rep, lv, alp, num_cell: run_sim_dwt(method, observation, mode, dwt_type, rep, lv, alp, num_cell, img_arr)
    # give v1 param search space
    elif observation.upper() == 'V1':
        # specify search space for dct and dwt params
        if method.lower() == 'dct': 
            search_list = [rep, alpha_list, num_cell, cell_size, sparse_freq]
            search = list(itertools.product(*search_list))
            search_df = pd.DataFrame(search, columns= ['rep', 'alp', 'num_cell', 'cell_size', 'sparse_freq'])
            sim_wrapper = lambda rep, alp, num_cell, cell_size, sparse_freq: run_sim_V1_dct(method, observation, mode, rep, alp, num_cell, cell_size, sparse_freq, img_arr)
        elif method.lower() == 'dwt':
            search_list = [rep, lv, alpha_list, num_cell, cell_size, sparse_freq]
            search = list(itertools.product(*search_list))             
            search_df = pd.DataFrame(search, columns= [ 'rep', 'lv', 'alp', 'num_cell', 'cell_size', 'sparse_freq'])
            sim_wrapper = lambda rep, lv, alp, num_cell, cell_size, sparse_freq: run_sim_V1_dwt(method, observation, mode, dwt_type, rep, lv, alp, num_cell, cell_size, sparse_freq, img_arr)
    else: 
         print("The observation {observation} is currently not supported. Please try valid observation type.".format(observation = observation))

    for p in search_df.values:
        delay = dask.delayed(sim_wrapper)(*p)
        delay_list.append(delay)
    futures = dask.persist(*delay_list)
    progress(futures)
    # Compute the result
    results = dask.compute(*futures)
    results_df = pd.DataFrame(results, columns=['error'])#, 'theta', 'reform', 's'])
    param_csv_nm = "param_"
    param_path = data_save_path(image_nm, method, observation, '{mode}_{param_csv_nm}'.format(mode = mode, param_csv_nm = param_csv_nm))
    # Add error onto parameter
    params_result_df = search_df.join(results_df['error'])
    # save parameter_error data with error_results data
    params_result_df.to_csv(param_path)
    hyperparam_track = data_save_path(image_nm, method, observation, '{mode}_hyperparam'.format(mode = mode))
    f = open(hyperparam_track, 'a+')
    hyperparam_list = list(zip(search_df.columns, search_list))
    f.write(f"{param_csv_nm}\n")
    for hyperparam in hyperparam_list :
        f.write(f"   {hyperparam[0]}: {hyperparam[1]}\n")
    f.write("\n\n")
    f.close()


# run sim for non-v1 dwt
def run_sim_dwt(method, observation, mode, dwt_type, rep, lv, alpha, num_cell, img_arr):
    ''' Run a sim for non-v1 dwt
    
    Parameters
    ----------
    method : String
        Method of reconstruction ('dwt' or 'dct')
    
    observation : String
        Method of observation (e.g. pixel, gaussian, v1)
    
    mode : String
        Desired mode to reconstruct image (e.g. 'Color' or 'Black').

    dwt_type : String
        Type of dwt method to use -- see pywt.wavelist() for all possible dwt types.
        
    rep : int
        The current repetition with the given parameters.

    lv : int
        Generate level of signal frequencies when dwt is used. Should be in [1, 4].

    alpha : float
        Penalty for fitting data onto LASSO function to search for significant coefficents

    num_cell : int
        Number of blobs that will be used to be determining which pixles to grab and use

    img_arr : numpy_array
        (n, m) shape image containing array of pixels
    
    Returns
    ----------
    error : float
        Computed normalized error value per each pixel
        
    '''
    dim = img_arr.shape
    if (len(dim) == 3) :
    	n, m, rgb = dim
    else :
    	n, m = dim
    # Deal with fraction num_cell amount
    if (num_cell < 1):
        num_cell = round(n * m * num_cell)
    num_cell = int(num_cell)
    rep = int(rep)
    lv = int(lv)
    alpha = float(alpha)
    img_arr = np.array([img_arr]).squeeze()
    reconst = filter_reconstruct(img_arr, num_cell = num_cell, alpha = alpha, method = method, observation = observation, mode = mode, lv = lv, dwt_type = dwt_type)

    # Call function and calculate error
    error = error_calculation(img_arr, reconst)
    
    return error


# run sim for v1 dwt
def run_sim_V1_dwt(method, observation, mode, dwt_type, rep, lv, alpha, num_cell, cell_size, sparse_freq, img_arr):
    ''' Run a sim for v1 dwt
    
    Parameters
    ----------
    method : String
        Method of reconstruction ('dwt' or 'dct')

    observation : String
        Method of observation (e.g. pixel, gaussian, v1)
    
    mode : String
        Desired mode to reconstruct image (e.g. 'Color' or 'Black').

    dwt_type : String
        Type of dwt method to use -- see pywt.wavelist() for all possible dwt types.

    rep: int
        The current repetition with the given parameters.

    lv : int
        Generate level of signal frequencies when dwt is used. Should be in [1, 4].

    alpha : float
        Penalty for fitting data onto LASSO function to search for significant coefficents

    num_cell : int
        Number of blobs that will be used to be determining which pixles to grab and use
    
    cell_size : int
        Determines field size of opened and closed blob of data. Affect the data training

    sparse_freq : int
        Determines filed frequency on how frequently opened and closed area would appear. Affect the data training

    img_arr : numpy_array
        (n, m) shape image containing array of pixels
        
    Returns
    ----------
    error : float
        Computed normalized error value per each pixel

    '''
    dim = img_arr.shape
    if (len(dim) == 3) :
    	n, m, rgb = dim
    else :
    	n, m = dim
    # Deal with fraction num_cell amount
    if (num_cell < 1):
        num_cell = round(n * m * num_cell)
    num_cell = int(num_cell)
    lv = int(lv)
    rep = int(rep)
    alpha = float(alpha)
    
    img_arr = np.array([img_arr]).squeeze()
    #Filter reconst to make sure it can reconstruct any size 
    reconst = filter_reconstruct(img_arr, num_cell = num_cell, cell_size=cell_size, sparse_freq=sparse_freq, alpha = alpha, method = method, observation = observation, mode = mode, lv = lv, dwt_type = dwt_type)
    
    # Calculates for the error per pixel
    error = error_calculation(img_arr, reconst)
    
    return error

    
# run sim for non-v1 dct 
def run_sim_dct(method, observation, mode, rep, alpha, num_cell, img_arr):
    ''' Run a sim for non-v1 dct
    
    Parameters
    ----------

    method : String
        Method of reconstruction ('dwt' or 'dct')

    observation : String
        Method of observation (e.g. pixel, gaussian, v1)
    
    mode : String
        Desired mode to reconstruct image (e.g. 'Color' or 'Black').

    rep: int
        The current repetition with the given parameters.

    alpha : float
        Penalty for fitting data onto LASSO function to search for significant coefficents

    num_cell : List of int
        Number of blobs that will be used to be determining which pixles to grab and use
    
    img_arr : numpy_array
        (n, m) shape image containing array of pixels

    Returns
    ----------
    error : float
        Computed normalized error value per each pixel

    '''
    dim = img_arr.shape
    if (len(dim) == 3) :
    	n, m, rgb = dim
    else :
    	n, m = dim
    # Deal with fraction num_cell amount
    if (num_cell < 1):
        num_cell = round(n * m * num_cell)
    num_cell = int(num_cell)
    img_arr = np.array([img_arr]).squeeze()
    reconst = filter_reconstruct(img_arr, num_cell = num_cell, alpha = alpha, method = method, observation = observation, mode = mode)
    
    # Call function and calculate error
    error = error_calculation(img_arr, reconst)
    return error

# run sim for v1 dct
def run_sim_V1_dct(method, observation, mode, rep, alpha, num_cell, cell_size, sparse_freq, img_arr):
    ''' Run a sim for V1 dct
    
    Parameters
    ----------
    method : String
        Method of reconstruction ('dwt' or 'dct')
    
    observation : String
        Method of observation (e.g. pixel, gaussian, v1)
    
    mode : String
        Desired mode to reconstruct image (e.g. 'Color' or 'Black').

    rep: int
        The current repetition with the given parameters.

    alpha : float
        Penalty for fitting data onto LASSO function to search for significant coefficents

    num_cell : int
        Number of blobs that will be used to be determining which pixles to grab and use
    
    cell_size : int
        Determines field size of opened and closed blob of data. Affect the data training

    sparse_freq : int
        Determines filed frequency on how frequently opened and closed area would appear. Affect the data training
        
    img_arr : numpy_array
        (n, m) shape image containing array of pixels

    Returns
    ----------
    error : float
        Computed normalized error value per each pixel

    '''
    dim = img_arr.shape
    if (len(dim) == 3) :
    	n, m, rgb = dim
    else :
    	n, m = dim
    # Deal with fraction num_cell amount
    if (num_cell < 1):
        num_cell = round(n * m * num_cell)
    num_cell = int(num_cell)
    img_arr = np.array([img_arr]).squeeze()
    reconst = filter_reconstruct(img_arr, num_cell = num_cell, cell_size=cell_size, sparse_freq=sparse_freq, alpha = alpha, method = method, observation = observation, mode = mode)
    error = error_calculation(img_arr, reconst)
    
    return error


def parse_args():
    parser = argparse.ArgumentParser(description='Create a hyperparameter sweep')
    # theres a lot of these -- use this function instead of manually typing all
    wavelist = pywt.wavelist()
    
    # get image infile
    parser.add_argument('-img_name', action='store', metavar='IMG_NAME', help='filename of image to be reconstructed', required=True, nargs=1)
    # add standard params
    parser.add_argument('-method', choices=['dct', 'dwt'], action='store', metavar='METHOD', help='Method you would like to use for reconstruction', required=True, nargs=1)
    parser.add_argument('-observation', choices=['pixel', 'V1', 'gaussian'], action='store', metavar='OBSERVATION', help='observation type to use when sampling', required=True, nargs=1)
    parser.add_argument('-mode', choices=['color', 'black'], action='store', metavar='COLOR_MODE', help='color mode of reconstruction', required=True, nargs=1)
    # add hyperparams REQUIRED for dwt ONLY
    parser.add_argument('-dwt_type', choices=wavelist, action='store', metavar='DWT_TYPE', help='dwt type', required=False, nargs=1)
    parser.add_argument('-level', choices=['1', '2', '3', '4'], action='store', metavar='LEVEL', help='level', required=False, nargs="+")
    # add hyperparams REQUIRED for v1 only
    parser.add_argument('-cell_size', action='store', metavar='CELL_SIZE', help='cell size', required=False, nargs="+")
    parser.add_argument('-sparse_freq', action='store', metavar='SPARSE_FREQUENCY', help='sparse frequency', required=False, nargs="+")
    # add hyperparams that are used for both dct and dwt
    parser.add_argument('-alpha_list', action='store', metavar="ALPHAS", help='alpha values to use', required=True, nargs="+")
    parser.add_argument('-num_cells', action='store', metavar='NUM_CELLS', help='Method you would like to use for reconstruction', required=True, nargs="+")
    
    args = parser.parse_args()
    method = args.method[0]
    img_name = args.img_name[0]
    observation = args.observation[0]
    mode = args.mode[0]
    # deal with missing or unneccessary command line args
    if method == "dwt" and (args.dwt_type is None or args.level is None):
        parser.error('dwt method requires -dwt_type and -level.')
    elif method == "dct" and (args.dwt_type is not None or args.level is not None):
        parser.error('dct method does not use -dwt_type and -level.')
    if observation.lower() == "v1": and (args.cell_size is None or args.sparse_freq is None):
        parser.error('v1 observation requires cell size and sparse freq.')
    elif observation.lower() != "v1" and (args.cell_size is not None or args.sparse_freq is not None):
        parser.error('Cell size and sparse freq params are only required for V1 observation.')
    dwt_type = args.dwt_type
    level = [eval(i) for i in args.level] if args.level is not None else None
    alpha_list = [eval(i) for i in args.alpha_list]
    num_cells = [eval(i) for i in args.num_cells]
    cell_size = [eval(i) for i in args.cell_size] if args.cell_size is not None else None
    sparse_freq = [eval(i) for i in args.sparse_freq] if args.sparse_freq is not None else None

    return method, img_name, observation, mode, dwt_type, level, alpha_list, num_cells, cell_size, sparse_freq
    

def main():
    method, img, observation, mode, dwt_type, level, alpha_list, num_cell, cell_size, sparse_freq = parse_args()
    run_sweep(method, img, observation, mode, dwt_type, level, alpha_list, num_cell, cell_size, sparse_freq)

if __name__ == '__main__':
    main()