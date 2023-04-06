import pandas as pd
import numpy as np
import sys
import getopt
import pickle
from utils.near_stations import prox
from globals import *
from util import find_contiguous_observation_blocks
from utils.windowing import apply_windowing
import util as util

def apply_subsampling(X, y, keep_percentage=0.1):
    y_eq_zero_idxs = np.where(y == 0)[0]
    y_gt_zero_idxs = np.where(y > 0)[0]
    print(f' - Original sizes (target=0)/(target>0): ({y_eq_zero_idxs.shape[0]})/({y_gt_zero_idxs.shape[0]})')

    mask = np.random.choice([True, False], size=y.shape[0], p=[
                            keep_percentage, 1.0-keep_percentage])
    y_train_subsample_idxs = np.where(mask == True)[0]

    print(f" - Subsample (total) size: {y_train_subsample_idxs.shape[0]}")
    idxs = np.intersect1d(y_eq_zero_idxs, y_train_subsample_idxs)
    print(f" - Subsample (target=0) size: {idxs.shape[0]}")

    idxs = np.union1d(idxs, y_gt_zero_idxs)
    X, y = X[idxs], y[idxs]
    y_eq_zero_idxs = np.where(y == 0)[0]
    y_gt_zero_idxs = np.where(y > 0)[0]
    print(f' - Resulting sizes (target=0)/(target>0): ({y_eq_zero_idxs.shape[0]})/({y_gt_zero_idxs.shape[0]})')

    return X, y


def generate_windowed(df: pd.DataFrame, target_idx: int):
    """
    This function applies the sliding window preprocessing technique to generate data an response matrices 
    from an input time series represented as a pandas DataFrame. This DataFrame is supposed to have
    a datetime index that corresponds to the timestamps in the time series.

    @see: https://stackoverflow.com/questions/8269916/what-is-sliding-window-algorithm-examples

    Note that this function takes the eventual existence of gaps in the input time series 
    into account. In particular, the windowing operation is performed in each separate 
    contiguous block of observations.
    """
    contiguous_observation_blocks = list(
        find_contiguous_observation_blocks(df))

    is_first_block = True

    for block in contiguous_observation_blocks:
        start = block[0]
        end = block[1]

        # print(df[start:end].shape)
        if df[start:end].shape[0] < TIME_WINDOW_SIZE + 1:
            continue

        arr = np.array(df[start:end])
        X_block, y_block = apply_windowing(arr,
                                           initial_time_step=0,
                                           max_time_step=len(
                                               arr)-TIME_WINDOW_SIZE-1,
                                           window_size=TIME_WINDOW_SIZE,
                                           target_idx=target_idx)
        y_block = y_block.reshape(-1, 1)
        if is_first_block:
            X = X_block
            y = y_block
            is_first_block = False
        else:
            X = np.concatenate((X, X_block), axis=0)
            y = np.concatenate((y, y_block), axis=0)

    return X, y


def generate_windowed_split(train_df, val_df, test_df, target_name):
    target_idx = train_df.columns.get_loc(target_name)
    print(f"Position (index) of target variable {target_name}: {target_idx}")
    X_train, y_train = generate_windowed(train_df, target_idx)
    X_val, y_val = generate_windowed(val_df, target_idx)
    X_test, y_test = generate_windowed(test_df, target_idx)
    return X_train, y_train, X_val, y_val, X_test, y_test


def prepare_datasets(station_id, use_sounding_as_data_source, use_numerical_model_as_data_source, num_neighbors=0):

    pipeline_id = station_id + '_E'
    if use_numerical_model_as_data_source:
        pipeline_id = pipeline_id + '-N'
    if use_sounding_as_data_source:
        pipeline_id = pipeline_id + '-R'
    if num_neighbors > 0:
        pipeline_id = pipeline_id + '_EI+' + str(num_neighbors) + 'NN'
    else:
        pipeline_id = pipeline_id + '_EI'

    df_ws = pd.read_parquet(
        '../data/weather_stations/A652_2007_2023_preprocessed.parquet.gzip')
    print(f"Observations for weather station {station_id} loaded. Shape = {df_ws.shape}.")

    #
    # Merge datasources
    #
    merged_df = df_ws

    if use_numerical_model_as_data_source:
        df_nwp_era5 = pd.read_parquet(
            '../data/numerical_models/ERA5_A652_1997-01-01_2021-12-31_preprocessed.parquet.gzip')
        assert (not df_nwp_era5.isnull().values.any().any())
        print(f"NWP data loaded. Shape = {df_nwp_era5.shape}.")
        merged_df = pd.merge(df_ws, df_nwp_era5, how='left', left_index=True, right_index=True)
        # merged_df = merged_df.join(df_nwp_era5)

        print(f"NWP successfully joined; resulting shape = {merged_df.shape}.")
        print(df_ws.index.difference(merged_df.index).shape)
        print(merged_df.index.difference(df_ws.index).shape)

        print(df_nwp_era5.index.intersection(df_ws.index).shape)
        print(df_nwp_era5.index.difference(df_ws.index).shape)
        print(df_ws.index.difference(df_nwp_era5.index).shape)
        print(df_ws.index.difference(df_nwp_era5.index))

        assert(merged_df.shape[0] == df_ws.shape[0])

    if use_sounding_as_data_source:
        df_sounding = pd.read_parquet(
            '../data/sounding_stations/SBGL_indices_1997-01-01_2022-12-31_preprocessed.parquet.gzip')
        merged_df = pd.merge(merged_df, df_sounding, on='Datetime', how='left')
        # TODO: data normalization 
        # TODO: implement interpolation
        # TODO: deal with missing values (see https://youtu.be/DKmDJJzayZw)

    if num_neighbors != 0:
        pass

    ####
    # TODO: add a data filtering step (e.g., to disregard all observations made between May and September.).
    ####

    #
    # Data splitting (train/val/test)
    # TODO: parameterize with user-defined splitting proportions.
    dict_splitting_proportions = {"train": 0.7, "val": 0.2, "test": 0.1}
    print(f"Splitting train/val/test examples according to proportion {dict_splitting_proportions}.")
    p_train = dict_splitting_proportions["train"]
    p_val = dict_splitting_proportions["val"]
    n = len(merged_df)
    df_train = merged_df[0:int(n*p_train)]
    df_val = merged_df[int(n*p_train):int(n*(p_train+p_val))]
    df_test = merged_df[int(n*(p_train+p_val)):]
    print(f'Done! Number of examples in each part (train/val/test): {len(df_train)}/{len(df_val)}/{len(df_test)}.')

    #
    # Save train/val/test DataFrames for future error analisys.
    print(f'Saving train/val/test datasets ({pipeline_id}).')
    df_train.to_parquet('../data/datasets/' + pipeline_id +
                        '_train.parquet.gzip', compression='gzip')
    df_val.to_parquet('../data/datasets/' + pipeline_id +
                      '_val.parquet.gzip', compression='gzip')
    df_test.to_parquet('../data/datasets/' + pipeline_id +
                       '_test.parquet.gzip', compression='gzip')

    #
    # Apply sliding windowing method to build train/val/test datasets 
    print('Applying sliding window to build train/val/test datasets.')
    _, target_name = util.get_relevant_variables(station_id)
    # target_column_train = df_train[target_name]
    # target_column_val = df_val[target_name]
    # target_column_test = df_test[target_name]

    min_y_train, max_y_train = min(df_train[target_name]), max(df_train[target_name])
    df_train = util.min_max_normalize(df_train)

    min_y_val, max_y_val = min(df_val[target_name]), max(df_val[target_name])
    df_val = util.min_max_normalize(df_val)

    min_y_test, max_y_test = min(df_test[target_name]), max(df_test[target_name])
    df_test = util.min_max_normalize(df_test)

    X_train, y_train, X_val, y_val, X_test, y_test = generate_windowed_split(
        df_train, df_val, df_test, target_name=target_name)
    print("Done! Resulting shapes:")
    print(f' - (X_train/X_val/X_test): ({X_train.shape}/{X_val.shape}/{X_test.shape})')
    print(f' - (y_train/y_val/y_test): ({y_train.shape}/{y_val.shape}/{y_test.shape})')

    y_train = (y_train + min_y_train) * (max_y_train - min_y_train)
    y_val = (y_val + min_y_val) * (max_y_val - min_y_val)
    y_test = (y_test + min_y_test) * (max_y_test - min_y_test)

    print('Min precipitation values (train/val/test): %.5f, %.5f, %.5f' %
          (np.min(y_train), np.min(y_val), np.min(y_test)))
    print('Max precipitation values (train/val/test): %.5f, %.5f, %.5f' %
          (np.max(y_train), np.max(y_val), np.max(y_test)))

    #
    # Subsampling
    #
    print('**********Subsampling************')
    print('***Before')
    print(f'Shapes (Y_train/y_val/y_test): {y_train.shape}, {y_val.shape}, {y_test.shape}')

    print("Subsampling train data.")
    X_train, y_train = apply_subsampling(X_train, y_train)
    print("Subsampling val data.")
    X_val, y_val = apply_subsampling(X_val, y_val)
    print("Subsampling test data.")
    X_test, y_test = apply_subsampling(X_test, y_test)

    print('***After')
    print('Min precipitation values (train/val/test): %.5f, %.5f, %.5f' %
          (np.min(y_train), np.min(y_val), np.min(y_test)))
    print('Max precipitation values (train/val/test): %.5f, %.5f, %.5f' %
          (np.max(y_train), np.max(y_val), np.max(y_test)))
    print(f'Shapes (y_train/val/test): {y_train.shape}, {y_val.shape}, {y_test.shape}')

    #
    # Write numpy arrays to a parquet file
    print(f'Saving train/val/test np arrays ({pipeline_id}).')
    print(
        f'Number of examples (train/val/test): {len(X_train)}/{len(X_val)}/{len(X_test)}.')
    file = open('../data/datasets/' + pipeline_id + ".pickle", 'wb')
    ndarrays = (X_train, y_train, #min_y_train, max_y_train,
                X_val, y_val, #min_y_val, max_y_val,
                X_test, y_test)#, min_y_test, max_y_test)
    pickle.dump(ndarrays, file)

    print('Done!')


def main(argv):
    station_id = ""
    use_sounding_as_data_source = 0
    use_numerical_model_as_data_source = 0
    num_neighbors = 0
    help_message = "Usage: {0} -s <station_id> -d <data_source_spec> -n <num_neighbors>".format(
        argv[0])

    try:
        opts, args = getopt.getopt(argv[1:], "hs:d:n:", [
                                   "help", "station_id=", "datasources=", "neighbors="])
    except:
        print(help_message)
        sys.exit(2)

    num_neighbors = 0
    use_sounding_as_data_source = False
    use_numerical_model_as_data_source = False

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(help_message)  # print the help message
            sys.exit(2)
        elif opt in ("-s", "--station_id"):
            station_id = arg
            if not ((station_id in INMET_STATION_CODES_RJ) or (station_id in COR_STATION_NAMES_RJ)):
                print(f"Invalid station identifier: {station_id}")
                print(help_message)
                sys.exit(2)
        elif opt in ("-d", "--datasources"):
            if arg.find('R') != -1:
                use_sounding_as_data_source = True
            if arg.find('N') != -1:
                use_numerical_model_as_data_source = True
        elif opt in ("-n", "--neighbors"):
            num_neighbors = arg

    assert(station_id is not None) and (station_id != "")
    prepare_datasets(station_id, use_sounding_as_data_source,
             use_numerical_model_as_data_source, num_neighbors=num_neighbors)


# python prepare_datasets.py -s A652 -d N
if __name__ == "__main__":
    main(sys.argv)
