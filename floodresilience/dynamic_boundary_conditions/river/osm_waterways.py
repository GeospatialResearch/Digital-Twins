# -*- coding: utf-8 -*-
"""This script handles the fetching of OpenStreetMap (OSM) waterways data for the defined catchment area."""

import logging

import geopandas as gpd
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON
from OSMPythonTools.overpass import overpassQueryBuilder, Overpass

from src import config

log = logging.getLogger(__name__)


def configure_osm_cache() -> None:
    """Change the directory for storing the OSM cache files."""
    # Get the data directory from the environment variable
    data_dir = config.EnvVariable.DATA_DIR
    # Define the OSM cache directory
    osm_cache_dir = data_dir / "osm_cache"
    # Change the directory for storing the OSM cache files
    CachingStrategy.use(JSON, cacheDir=osm_cache_dir)


def fetch_osm_waterways(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetch OpenStreetMap (OSM) waterways data for the specified catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved OSM waterways data for the specified catchment area.
    """
    log.info("Fetching OpenStreetMap (OSM) waterways for the requested catchment area.")
    # Convert the catchment area to the desired coordinate reference system (CRS: 4326)
    osm_catchment_area = catchment_area.to_crs(4326)
    # Get the bounding box coordinates of the osm_catchment_area
    min_x, min_y, max_x, max_y = osm_catchment_area.bounds.values[0]
    # Construct an Overpass query to retrieve waterway elements within the specified bounding box
    query = overpassQueryBuilder(
        bbox=[min_y, min_x, max_y, max_x],
        elementType="way",
        selector="waterway",
        out="body",
        includeGeometry=True)
    # Execute the Overpass query to retrieve waterway elements
    waterways = Overpass().query(query, timeout=600)
    # Initialize an empty dictionary to store element information
    element_dict = {
        "id": [],
        "waterway": [],
        "geometry": []
    }
    # Iterate over the retrieved waterway elements
    for element in waterways.elements():
        # Extract and store the ID, waterway type, and geometry of each element
        element_dict["id"].append(element.id())
        element_dict["waterway"].append(element.tag("waterway"))
        element_dict["geometry"].append(element.geometry())
    # Create a GeoDataFrame from the extracted element information
    osm_waterways = gpd.GeoDataFrame(element_dict, crs=osm_catchment_area.crs)
    # Convert the osm_waterways GeoDataFrame to the CRS of the catchment_area
    osm_waterways = osm_waterways.to_crs(catchment_area.crs)
    return osm_waterways


def get_osm_waterways_data(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetch OpenStreetMap (OSM) waterways data for the specified catchment area.
    Only LineString geometries representing waterways of type "river" or "stream" are included.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing only LineString geometries representing waterways of type "river" or "stream".
    """
    # Change the directory for storing the OSM cache files
    configure_osm_cache()
    # Fetch OpenStreetMap (OSM) waterways data for the specified catchment area
    osm_waterways = fetch_osm_waterways(catchment_area)
    # Filter the OSM waterways data to include only LineString geometries
    osm_waterways = osm_waterways[osm_waterways["geometry"].type == "LineString"]
    # Keep only the waterways that have the waterway types "river" or "stream"
    osm_waterways_data = osm_waterways.loc[
        (osm_waterways["waterway"] == "river") | (osm_waterways["waterway"] == "stream")]
    # Reset the index of the resulting GeoDataFrame
    osm_waterways_data = osm_waterways_data.reset_index(drop=True)
    return osm_waterways_data
