import logging
import pathlib
from typing import Tuple, Union

import geopandas as gpd
import pandas as pd
import pyarrow.csv as csv

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


class InvalidDirectoryError(Exception):
    pass


def get_catchment_area_coords(catchment_file: pathlib.Path) -> Tuple[float, float]:
    """
    Extract the catchment polygon centroid coordinates.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    """
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    long, lat = catchment_polygon.centroid.coords[0]
    return lat, long


def get_slr_data_directory(folder_name: str = "data") -> pathlib.Path:
    """
    Returns a Path object pointing to the directory containing the sea level rise data files.

    Parameters
    ----------
    folder_name : str = "data"
        A string representing the name of the folder containing the sea level rise data files. Default is 'data'.
    """
    # Construct the path to the sea level rise data directory
    slr_data_dir = pathlib.Path(__file__).parent / folder_name
    # Check if the sea level rise data directory exists, if not, raise an error
    if not slr_data_dir.exists():
        raise InvalidDirectoryError(f"Sea level rise data directory '{slr_data_dir}' does not exist.")
    return slr_data_dir


def get_all_slr_data(folder_name: str = "data") -> pd.DataFrame:
    """
    Returns a Pandas DataFrame that is a concatenation of all the sea level rise data located in the
    sea level rise data directory.

    Parameters
    ----------
    folder_name : str = "data"
        A string representing the name of the folder containing the sea level rise CSV files. Default is 'data'.
    """
    # Get the sea level rise data directory
    slr_data_dir = get_slr_data_directory(folder_name)
    # Check if there are any CSV files in the specified directory
    if not any(slr_data_dir.glob("*.csv")):
        raise FileNotFoundError(f"No sea level rise data files found in {slr_data_dir}")
    # Loop through each CSV file in the specified directory
    slr_nz_list = []
    for file_path in slr_data_dir.glob("*.csv"):
        # Read the CSV file into a pandas DataFrame using pyarrow
        slr_region = csv.read_csv(file_path).to_pandas()
        # Extract the region name from the file name and add it as a new column in the DataFrame
        file_name = file_path.stem
        start_index = file_name.find('projections_') + len('projections_')
        end_index = file_name.find('_region')
        region_name = file_name[start_index:end_index]
        slr_region['region'] = region_name
        # Append the DataFrame to the list
        slr_nz_list.append(slr_region)
        # Log that the file has been successfully loaded
        log.info(f"{file_path.name} data file has been successfully loaded.")
    # Concatenate all the dataframes in the list
    slr_nz = pd.concat(slr_nz_list, axis=0)
    # Convert all column names to lowercase
    slr_nz.columns = slr_nz.columns.str.lower()
    return slr_nz


def get_closest_slr_site_to_tide(
        slr_nz: pd.DataFrame,
        tide_lat: Union[int, float],
        tide_long: Union[int, float]) -> Tuple[float, float]:
    """
    Find the closest sea level rise site to the target tide position.
    Returns the latitude and longitude coordinates of the closest sea level rise site.

    Parameters
    ----------
    slr_nz : pd.DataFrame
        Sea level rise data for the entire country.
    tide_lat : int or float
        Latitude coordinate of the target tide position.
    tide_long : int or float
        Longitude coordinate of the target tide position.
    """
    # Convert the target tide position into a GeoDataFrame
    target_coord = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy([tide_long], [tide_lat]), crs='EPSG:4326')
    # Get unique latitude and longitude coordinates from the sea level rise data
    slr_nz_coords = slr_nz[['lat', 'lon']].drop_duplicates()
    # Create a GeoDataFrame with the latitude and longitude coordinates
    geometry = gpd.points_from_xy(slr_nz_coords['lon'], slr_nz_coords['lat'], crs="EPSG:4326")
    slr_nz_coords = gpd.GeoDataFrame(slr_nz_coords, geometry=geometry)
    # Reproject the GeoDataFrames to a projected coordinate system
    target_coord = target_coord.to_crs('EPSG:2193')
    slr_nz_coords = slr_nz_coords.to_crs('EPSG:2193')
    # Calculate the distance between each sea level rise site and the target tide position
    slr_nz_coords['distance_metres'] = slr_nz_coords.distance(target_coord.iloc[0]['geometry'])
    slr_nz_coords = slr_nz_coords.to_crs('EPSG:4326')
    # Find the closest sea level rise site to the target tide position
    closest_site = slr_nz_coords.nsmallest(1, 'distance_metres').iloc[0]
    closest_site_lat, closest_site_long = closest_site['lat'], closest_site['lon']
    closest_site_dist = closest_site['distance_metres']
    # Log the result
    log.info(f"The closest sea level rise site is located at latitude {closest_site_lat:.4f} and "
             f"longitude {closest_site_long:.4f}, with a distance of {closest_site_dist:.2f} meters")
    return closest_site_lat, closest_site_long


def get_closest_slr_data(
        slr_nz: pd.DataFrame,
        closest_site_lat: Union[int, float],
        closest_site_long: Union[int, float]) -> gpd.GeoDataFrame:
    """
    Returns the closest sea level rise data as a GeoDataFrame.

    Parameters
    ----------
    slr_nz : pd.DataFrame
        A DataFrame containing sea level rise data for New Zealand.
    closest_site_lat : float
        The latitude of the closest sea level rise site.
    closest_site_long : float
        The longitude of the closest sea level rise site.
    """
    # Filter the data to find the closest site based on latitude and longitude
    lat_filter = (slr_nz['lat'] == closest_site_lat)
    long_filter = (slr_nz['lon'] == closest_site_long)
    closest_slr_data = slr_nz[lat_filter & long_filter]
    # Convert the coordinates to a geometry object and create a new GeoDataFrame
    geometry = gpd.points_from_xy(closest_slr_data['lon'], closest_slr_data['lat'], crs='EPSG:4326')
    closest_slr_data = gpd.GeoDataFrame(closest_slr_data, geometry=geometry).reset_index(drop=True)
    return closest_slr_data


def main():
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    # Get the catchment polygon centroid coordinates.
    lat, long = get_catchment_area_coords(catchment_file)
    # Get the sea level rise data for the entire country
    slr_nz = get_all_slr_data()
    # Find the closest sea level rise site to the target tide position.
    closest_site_lat, closest_site_long = get_closest_slr_site_to_tide(slr_nz, lat, long)  # -43.3803 172.7114
    closest_slr_data = get_closest_slr_data(slr_nz, closest_site_lat, closest_site_long)
    print(closest_slr_data)


if __name__ == "__main__":
    main()
