import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys
sys.path.append("../")

from mpl_toolkits.axes_grid1 import make_axes_locatable
import seaborn as sns
import time
import os.path
from src.compress_sensing_library import *
from src.utility_library import *

# Package for importing image representation
from PIL import Image, ImageOps

# argparse stuff
import pywt
import argparse


def error_colorbar(img_arr, reconst, method, observation, num_cell, img_name, save_img = False): 
    ''' Display the reconstructed image along with pixel error and a colorbar.
    
    Parameters
    ----------
        img_arr : numpy array 
            Contains the pixel values for the original image
        
        reconst : numpy array 
            Containing the pixel values for the reconstructed image
        
        method : String
            Method used for the reconstruction.
            Possible methods are ['dct', 'dwt']
        
        observation : String
            Observation used to collect data for reconstruction
            Possible observations are ['pixel', 'gaussian', 'V1']
        
        num_cell : Integer
            Number of blobs that will be used to be determining which pixles to grab and use
    
        img_name : String
            Name of the original image file (e.g. "Peppers")
        
        save_img : boolean
            Determines if the image will be saved.
    '''

    # setup figures and axes
    # NOTE: changing figsize here requires you to rescale the colorbar as well --adjust the shrink parameter to fit.
    fig, axis = plt.subplots(1, 2, figsize = (8, 8))
    plt.tight_layout()

    # prepare the reconstruction axis
    axis[0].set_title("{observation} Reconst: {num_cell} cell".format(observation=observation, num_cell = num_cell))
    axis[0].axis('off')

    # prepare the observation error axis
    axis[1].set_title("{observation} Error: {num_cell} cells".format(observation = observation, num_cell = num_cell))
    axis[1].axis('off')
    
    # calculate error for RGB images
    if (len(img_arr.shape) == 3):
        axis[0].imshow(reconst, vmin = 0, vmax = 255)
        vmax = ((img_arr - reconst)**2).mean(axis = 2)
        vmax = vmax.max() if vmax.max() < 255 else 255
        err = axis[1].imshow(((img_arr - reconst)**2).mean(axis = 2), 'Reds', vmin = 0, vmax = vmax)

    # calculate error for Grayscaled images
    else :
        axis[0].imshow(reconst, cmap='gray', vmin = 0, vmax = 255)
        vmax = img_arr - reconst
        vmax = vmax.max() if vmax.max() < 255 else 255
        err = axis[1].imshow((img_arr - reconst), 'Reds', vmin = 0, vmax = vmax)


    # apply colorbar -- NOTE : if figsize is not (8, 8) then shrink value must be changeed as well
    cbar = fig.colorbar(err, ax=axis, shrink = 0.363, aspect=10)
    cbar.set_label("Error")
    # save image to outfile if desired, else display to the user
    if save_img == True:
        outfile = fig_save_path(img_name, "dct", observation, "colorbar")
        plt.savefig(outfile, dpi = 300, bbox_inches = "tight")
    else:
        plt.show()



def num_cell_error_figure(img, method, pixel_file=None, gaussian_file=None, V1_file=None, data_grab = 'auto', save = False) :
    ''' Generate figure that compares which method gives the best minimum error
    
    Parameters
    ----------
    img : String
        the name of image file
       
    method : String
        Basis the data file was worked on. Currently supporting dct (descrete cosine transform) and dwt (descrete wavelet transform)
    
    pixel_file : String
        pixel observation data file from hyperparameter sweep that is needed to plot
    
    gaussian_file : String
        gaussian observation data file from hyperparameter sweep that is needed to plot
    
    V1_file : String
        V1 observation data file from hyperparameter sweep that is needed to plot
    
    data_grab : String
        With structured path, decides to grab all three data file automatically or manually. Currently not implemented
        ['auto', 'manual']
    
    save : bool
        Save data into specified path
        [True, False]
            
    Returns
    ----------
    '''
    img_nm = img.split('.')[0]
    
    if None in [pixel_file, gaussian_file, V1_file] and data_grab == 'manual': 
        print("All observation data file must be given")    
        sys.exit(0)
    
    #Pre-processing data to receive
    data = process_result_data(img, method, pixel_file, gaussian_file, V1_file)
    plt.xticks(data['V1'][0]['num_cell'])
    plt.xlabel('num_cell')
    title = "Num_Cell_Vs_Error_{img}_".format(img = img_nm)
    plt.title(title.replace('_', ' '))
    plt.legend(['V1', 'Pixel', 'Gaussian'], loc = 'best')
    
    for obs, plot in data.items():
        sns.lineplot(data = plot[0], x = 'num_cell', y = 'error', palette='Accent', label = obs)
        plt.plot(plot[1]['num_cell'], plot[1]['min_error'], 'r.')
    plt.legend(loc = 'best')
    if save :
        # for its save name, the name of file order is pixel -> gaussian -> V1 
        save_nm = pixel_file.split('.')[0] + '_' + gaussian_file.split('.')[0] + '_' + V1_file.split('.')[0]
        save_path = fig_save_path(img_nm, method, 'num_cell_error', save_nm)
        plt.savefig(save_path, dpi = 200)
        
    plt.show()


def colorbar_live_reconst(method, img_name, observation, mode, dwt_type, level, alpha, num_cells, cell_size, sparse_freq):
    rand_weight = False
    filter_dim = (30, 30)
    img_arr = process_image(img_name, mode, False)
    print(f"Image \"{img_name}\" loaded.") 
    reconst = filter_reconstruct(img_arr, num_cells, cell_size, sparse_freq, filter_dim, alpha, method, observation, level, dwt_type, rand_weight, mode) 
    print(f"Image {img_name} reconstructed. Displaying reconstruction and error.") 
    error_colorbar(img_arr, reconst, method, observation, num_cells, img_name.split('.')[0], False)

    
def add_colorbar_args(parser):
    # theres a lot of these -- use this function instead of manually typing all
    wavelist = pywt.wavelist()
    # get image infile
    
    parser.add_argument('-img_name', action='store', metavar='IMG_NAME', help='[Colorbar and Num Cell Figure] : filename of image to be reconstructed', required=False, nargs=1)
    # add standard params
    parser.add_argument('-method', choices=['dct', 'dwt'], action='store', metavar='METHOD', help='[Colorbar and Num Cell Figure] : Method you would like to use for reconstruction', required=False, nargs=1)
    parser.add_argument('-observation', choices=['pixel', 'V1', 'gaussian'], action='store', metavar='OBSERVATION', help='[Colorbar Figure] : observation type to use when sampling', required=False, nargs=1)
    parser.add_argument('-mode', choices=['color', 'black'], action='store', metavar='COLOR_MODE', help='[Colorbar Figure] : color mode of reconstruction', required=False, nargs=1)
    # add hyperparams REQUIRED for dwt ONLY
    parser.add_argument('-dwt_type', choices=wavelist, action='store', metavar='DWT_TYPE', help='[Colorbar Figure] : dwt type', required=False, nargs=1)
    parser.add_argument('-level', choices=['1', '2', '3', '4'], action='store', metavar='LEVEL', help='[Colorbar Figure] : level', required=False, nargs=1)
    # add hyperparams REQUIRED for V1 ONLY
    parser.add_argument('-cell_size', action='store', metavar='CELL_SIZE', help='[Colorbar Figure] : cell size', required=False, nargs=1)
    parser.add_argument('-sparse_freq', action='store', metavar='SPARSE_FREQUENCY', help='[Colorbar Figure] : sparse frequency', required=False, nargs=1)
    # add hyperparams that are used for both dct and dwt
    parser.add_argument('-alpha', action='store', metavar="ALPHA", help='[Colorbar Figure] : alpha values to use', required=False, nargs=1)
    parser.add_argument('-num_cells', action='store', metavar='NUM_CELLS', help='[Colorbar Figure] : Method you would like to use for reconstruction', required=False, nargs=1)
    

def eval_colorbar_args(args, parser):
    method = args.method[0] if args.method is not None else None
    img_name = args.img_name[0] if args.img_name is not None else None
    observation = args.observation[0] if args.observation is not None else None
    mode = args.mode[0] if args.mode is not None else None
    num_cells = eval(args.num_cells[0]) if args.num_cells is not None else None
    if None in [method, img_name, observation, mode, num_cells]:
        parser.error('[Colorbar Figure] : at least method, img_name, observation, mode, num_cells required for colorbar figure')
    # deal with missing or unneccessary command line args
    if method == "dwt" and (args.dwt_type is None or args.level is None):
        parser.error('[Colorbar Figure] : dwt method requires -dwt_type and -level.')
    elif method == "dct" and (args.dwt_type is not None or args.level is not None):
        parser.error('[Colorbar Figure] : dct method does not use -dwt_type and -level.')
    if observation.lower() == "v1" and (args.cell_size is None or args.sparse_freq is None):
        parser.error('[Colorbar Figure] : V1 observation requires cell size and sparse freq.')
    elif observation.lower() != "v1" and (args.cell_size is not None or args.sparse_freq is not None):
        parser.error('[Colorbar Figure] : Cell size and sparse freq params are only required for V1 observation.')
    dwt_type = eval(args.dwt_type[0]) if args.dwt_type is not None else None
    level = eval(args.level[0]) if args.level is not None else None
    alpha = eval(args.alpha[0]) if args.alpha is not None else None
    cell_size = eval(args.cell_size[0]) if args.cell_size is not None else None
    sparse_freq = eval(args.sparse_freq[0]) if args.sparse_freq is not None else None
    return method, img_name, observation, mode, dwt_type, level, alpha, num_cells, cell_size, sparse_freq


def add_num_cell_args(parser):
    parser.add_argument('-pixel_file', action='store', metavar='PIXEL', help='[Num Cell Figure] : file to read pixel data from', required=False, nargs=1)
    parser.add_argument('-gaussian_file', action='store', metavar='GAUSSIAN', help='[Num Cell Figure] : file to read gaussian data from', required=False, nargs=1)
    parser.add_argument('-v1_file', action='store', metavar='V1', help='[Num Cell Figure] : file to read V1 data from', required=False, nargs=1)
    parser.add_argument('-data_grab', action='store_true', help='[Num Cell Figure] : auto grab data when argument is present', required=False)
    parser.add_argument('-save', action='store_true', help='[Num Cell Figure] : save into specified path when argument is present', required=False)

def eval_num_cell_args(args, parser):
    img_name = args.img_name[0] if args.img_name is not None else None
    method = args.method[0] if args.method is not None else None
    pixel = args.pixel_file[0] if args.pixel_file is not None else None
    gaussian = args.gaussian_file[0] if args.gaussian_file is not None else None
    v1 = args.v1_file[0] if args.v1_file is not None else None
    data_grab = args.data_grab# if args.data_grab is not None else None
    save = args.save# if args.save is not None else None
    return img_name, method, pixel, gaussian, v1, data_grab, save

def parse_args():
    parser = argparse.ArgumentParser(description='Generate a figure of your choosing.')
    
    # add figtype -- this is the only required argparse arg, determine which others should be there based on figtype
    parser.add_argument('-fig_type', choices=['colorbar', 'num_cell'], action='store', metavar='FIGTYPE', help='type of figure to generate', required=True, nargs=1)

    add_colorbar_args(parser)
    add_num_cell_args(parser)
    args = parser.parse_args()
    fig_type = args.fig_type[0]
    if fig_type == 'colorbar':
        params = eval_colorbar_args(args, parser)
    elif fig_type == 'num_cell':
        params = eval_num_cell_args(args, parser)

    return fig_type, params

def main():
    fig_type, args = parse_args()
    if fig_type == 'colorbar' :
      method, img_name, observation, mode, dwt_type, level, alpha, num_cells, cell_size, sparse_freq = args
      colorbar_live_reconst(method, img_name, observation, mode, dwt_type, level, alpha, num_cells, cell_size, sparse_freq)      
    elif fig_type == 'num_cell':
        img_name, method, pixel, gaussian, v1, data_grab, save = args
        num_cell_error_figure(img_name, method, pixel, gaussian, v1, data_grab, save)


if __name__ == "__main__":
    main()