import os
import numpy as np
import pandas as pd
import nrrd
from scipy.ndimage import label,grey_dilation
import sys

# the gloval path where CCF reference is saved. 
ccf_path = "/scratchdata1/MouseBrainAtlases/Taxonomies/CCF_Ref"


def get_annotation_matrix():
    " the CCF volume annotation, after a little bit of cleanup "
    ccf_annotation_volume_2017_25, header = nrrd.read(os.path.join(ccf_path,'ccf_2017','annotation_25.nrrd'))
    
    onto = get_ccf_term_onthology()

    missing_ids = np.setdiff1d(ccf_annotation_volume_2017_25,onto.index)
    missing_ids = np.setdiff1d(missing_ids,[0])
    ccf_annotation_volume_2017_25[np.isin(ccf_annotation_volume_2017_25,missing_ids)]=0

    return ccf_annotation_volume_2017_25

def get_ccf_term_onthology():
    """ 
    get the CCF term onthology with added pacellation levels
    
    pacelation levels taken from Allen/Zhaung MERFISH atlas
    """
    map_df = pd.read_csv(os.path.join(ccf_path,"parcellation_to_parcellation_term_membership.csv"))
    map_df_2017 = map_df[map_df["parcellation_term_label"].str.startswith("AllenCCF-Ontology-2017-")].copy()
    labels_str = map_df_2017["parcellation_term_label"]
    labels_int_2017 = labels_str.str.replace("AllenCCF-Ontology-2017-", "").astype(int)
    map_df_2017["id_2017"]=labels_int_2017

    onto = pd.read_csv(os.path.join(ccf_path,"allen_ontology.csv"))
    onto.set_index('id', inplace=True)
    # Drop rows from 'onto' DataFrame where the index is not in 'map_df_2017["id_2017"]'
    onto = onto[onto.index.isin(map_df_2017["id_2017"])]
    onto["id_paths"] = onto["structure_id_path"].apply(lambda x: [int(i) for i in x.strip('/').split('/') if i])
    # Filter each list in the 'id_paths' column to only include ids that are present in the index of 'onto'
    onto["id_paths"] = onto["id_paths"].apply(lambda path: [id for id in path if id in onto.index])
    # Ensure all id_paths have a length of 5 by duplicating the last item as needed
    onto["id_paths"] = onto["id_paths"].apply(lambda path: path + [path[-1]] * (5 - len(path)) if len(path) < 5 else path)

    # Extract the 5 columns from the stacked id_paths
    id_paths_stacked = np.vstack(onto["id_paths"])
    onto["parcellation_organ"] = id_paths_stacked[:, 0]
    onto["parcellation_category"] = id_paths_stacked[:, 1]
    onto["parcellation_division"] = id_paths_stacked[:, 2]
    onto["parcellation_structure"] = id_paths_stacked[:, 3]
    onto["parcellation_substructure"] = id_paths_stacked[:, 4]

    return onto

# def get_pivot_df():
#     "reads pivot table for parcellation including colors"
#     merged_df = pd.read_csv(os.path.join(ccf_path,"parcellation_to_parcellation_term_membership_acronym.csv"))
#     for clr in ['red','blue','green']:
#         clr_df = pd.read_csv(os.path.join(ccf_path,f"parcellation_to_parcellation_term_membership_{clr}.csv"))
#         # Merge the 'pivot_ccf_df' and 'red_df' on the 'parcellation_index' column
#         merged_df = pd.merge(merged_df, clr_df, on='parcellation_index', how='inner')
#         # Rename all columns that end with 'color' to end with 'red'
#         merged_df.columns = [col if not col.endswith('color') else col.replace('color', clr) for col in merged_df.columns]

#     levels = ["organ","category","division","structure","substructure"]
#     for lvl in levels: 
#         # Read the three columns that start with the current level and end with _red, _green, _blue
#         red_col = merged_df[f'{lvl}_red']
#         green_col = merged_df[f'{lvl}_green']
#         blue_col = merged_df[f'{lvl}_blue']
        
#         # Convert the RGB values to hex codes
#         hex_colors = ['#%02x%02x%02x' % (r, g, b) for r, g, b in zip(red_col, green_col, blue_col)]
        
#         # Assign the hex colors as a new column to the dataframe
#         merged_df[f'{lvl}_color'] = hex_colors

#     # Drop all columns that end with 'red', 'green', or 'blue'
#     columns_to_drop = [col for col in merged_df.columns if col.endswith(('red', 'green', 'blue'))]
#     merged_df.drop(columns=columns_to_drop, inplace=True)

#     # Add 'parcellation_' prefix to columns that don't already start with it
#     merged_df.columns = [f'parcellation_{col}' if not col.startswith('parcellation_') else col for col in merged_df.columns]
#     return merged_df

def discretize_XYZ(XYZ,res=25):
    Xref = XYZ[:,0]
    Yref = XYZ[:,1]
    Zref = XYZ[:,2]

    Xref_int = (Xref*1000/res).astype(int)
    Yref_int = (Yref*1000/res).astype(int)
    Zref_int = (Zref*1000/res).astype(int)

    ccf_parcel_index = get_annotation_matrix()

    # Ensure indices are within the bounds of the annotation array
    Xref_int = np.clip(Xref_int, 0, ccf_parcel_index.shape[2] - 1)
    Yref_int = np.clip(Yref_int, 0, ccf_parcel_index.shape[1] - 1)
    Zref_int = np.clip(Zref_int, 0, ccf_parcel_index.shape[0] - 1) 

    return (Xref_int,Yref_int,Zref_int)

def get_ccf_labeled_volume(structure = None):
    label_file_path = os.path.join(ccf_path, 'ccf_labels.npy')
    if os.path.exists(label_file_path):
        labeled_volume = np.load(label_file_path)
    else: 
        annotation = get_annotation_matrix()
        annotation_borders = create_neighbor_binary_image(annotation)
        annotation_without_borders = annotation.copy()
        annotation_without_borders[annotation_borders]=0

        if structure is None:
            # structure = np.array([[[0, 0, 0], [0, 1, 0], [0, 0, 0]],
            #                       [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
            #                       [[0, 0, 0], [0, 1, 0], [0, 0, 0]]], dtype=int)
            structure = np.ones([3,3,3])
        (labeled_volume,n_lbls) = label(annotation_without_borders,structure=structure)

        labeled_volume = fill_borders_vectorized(labeled_volume,annotation_borders)
        np.save(os.path.join(ccf_path,'ccf_labels.npy'),labeled_volume)

    return labeled_volume
    

def create_neighbor_binary_image(image, shifts = None):
    z, y, x = image.shape
    binary_image = np.zeros_like(image, dtype=bool)
    
    # Define shifts for 6-connectivity in 3D (only along the cardinal directions)
    if shifts is None:
        shifts = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if not (dx == 0 and dy == 0 and dz == 0)]
        #shifts = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

    for dz, dy, dx in shifts:
        shifted_image = np.roll(image, shift=(dz, dy, dx), axis=(0, 1, 2))
        mask = (image > 0) & (shifted_image > 0)
        different_label_mask = mask & (image != shifted_image)
        binary_image |= different_label_mask

    return binary_image

def fill_borders_vectorized(labeled_components, border_mask):
    # Use grey_dilation to propagate the maximum label value into the zero-valued border areas
    # Only apply dilation where the border_mask is True
    dilation_structure = np.ones((3, 3, 3))  # 3D dilation structure for 26-connectivity
    filled_borders = grey_dilation(labeled_components, footprint=dilation_structure, mode='nearest')

    # Now, combine the original labeled components with the filled borders
    # Only update the border areas
    filled_image = labeled_components.copy()
    filled_image[border_mask] = filled_borders[border_mask]

    return filled_image


    


def retrieve_CCF_info(XYZ, Section = None):
    """
    Data driven assignment of CCF types (division, structure, substructure)
    additionaly output includes lowest level index + unique label per connected component region

    function loads data from drive for index, labels, and pivot table converted
    data was created with resolytion of 25um (one of Allen SDK options)

    Labeling is done in 2D (XY) taking into account section information
    """

    out_df = pd.DataFrame()

    # get volume and onthology
    annotation_volume = get_annotation_matrix()
    labeled_volume = get_ccf_labeled_volume()
    onto = get_ccf_term_onthology()

    (Xref_int,Yref_int,Zref_int) = discretize_XYZ(XYZ)

    infered_parecl_id = annotation_volume[Zref_int,Yref_int,Xref_int]
    # anything we can't find, just assign "brain"
    infered_parecl_id[infered_parecl_id==0]=997

    parcilation_levels = ["parcellation_division",
                        "parcellation_structure",
                        "parcellation_substructure"]

    unq,inv = np.unique(infered_parecl_id,return_inverse=True)
    for lvl in parcilation_levels:
        ix = onto[lvl].loc[unq].values[inv]
        selected_columns = onto.loc[ix, ["acronym", "name", "color_hex_triplet"]]
        # acronym, name, and color
        out_df[lvl] = selected_columns["acronym"].values
        out_df[f"{lvl}_color"] = selected_columns["color_hex_triplet"].values
        out_df[f"{lvl}_name"] = selected_columns["name"].values

    out_df["parcellation_label"] = labeled_volume[Zref_int,Yref_int,Xref_int]

    # create the pivot table
    if Section is None:
        unq,lbl_ix = np.unique(out_df['parcellation_label'],return_index=True)
    else:
        unq, lbl_ix, inv_ix = np.unique(np.array(list(zip(out_df['parcellation_label'], Section))), axis=0, return_index=True, return_inverse=True)
        unq = np.arange(len(unq))
        out_df['parcellation_label'] = unq[inv_ix]

    parcellation_label_type_df = pd.DataFrame()
    parcellation_label_type_df['parcellation_label']=unq

    for tx in parcilation_levels:
        parcellation_label_type_df[tx] = out_df[tx][lbl_ix].reset_index(drop=True)

    return (out_df,parcellation_label_type_df)




