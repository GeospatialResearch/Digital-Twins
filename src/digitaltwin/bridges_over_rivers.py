import geopandas as gpd
from sqlalchemy.engine import Engine

from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area

def my_new_function(
    area_of_interest: gpd.GeoDataFrame,
    engine: Engine
) -> gpd.GeoDataFrame:

    # Get the area of interest polygon in well known text format for database querying
    aoi_wkt= area_of_interest["geometry"][0].wkt
    crs = area_of_interest.crs.to_epsg()

    # Create bridge dataframe
    query_bridge = f"""
    SELECT t50_fid, geometry from nz_bridge_centrelines
    WHERE ST_INTERSECTS(nz_bridge_centrelines.geometry, ST_GeomFromText('{aoi_wkt}', {crs}));
    """
    bridge_df = gpd.GeoDataFrame.from_postgis(
        query_bridge, engine, geom_col='geometry'
    )

    # Create river dataframe
    query_river = f"""
    SELECT river_section_id, geometry from nz_river_name
    WHERE ST_INTERSECTS(nz_river_name.geometry, ST_GeomFromText('{aoi_wkt}', {crs}));
    """
    river_df = gpd.GeoDataFrame.from_postgis(
        query_river, engine, geom_col='geometry'
    )

    # Geospatially join two dataframes
    bridge_river_join = bridge_df.sjoin(river_df, how='inner')

    # Rename columns
    bridge_river_join = bridge_river_join.rename(
        columns={
            't50_fid': 'bridge_id',
            'river_section_id': 'river_id'
        }
    )

    # Re-order columns
    bridge_river_join = bridge_river_join[['river_id', 'bridge_id', 'geometry']]

    return bridge_river_join


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Fetch tide data, read and store sea level rise data in the database, and generate the requested tide
    uniform boundary model input for BG-Flood.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)

    Returns
    -------
    None
        This function does not return any value.
    """

    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    my_new_function(catchment_area, engine)

if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.INFO
    )
