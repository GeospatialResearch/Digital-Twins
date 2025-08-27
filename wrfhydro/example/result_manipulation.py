"""Runs to adjust the results"""
# Necessary packages
from typing import List, Tuple

import glob
from pathlib import Path

import rioxarray as rxr
import xarray as xr


# Develop a class to manipulate the simulated result
class ResultManipulation:
    """A class to manipulate the simulation results"""

    def __init__(
            self,
            domain_path: str
    ) -> None:
        """
        Definition:
            Init function to state common arguments
        References:
            None.
        Arguments:
            domain_path (str):
                Define domain path that stores necessary inputs to run
                WRF-Hydro simulation, especially TBL files, DOMAIN, FORCING
        """
        self.domain_path = domain_path

    def generate_dem_and_paths(self) -> Tuple[List[str], rxr.open_rasterio]:
        """
        Definition:
            A function to generate DEM and streamflow paths
        References:
            None.
        Arguments:
            Already defined above
        Returns:
            streamflow_files (list):
                A list of paths
            dem (rxr.open_rasterio):
                A raster that contains multiple topographic features including DEM
        """
        # Load Topographic data (DEM)
        load_dem = rxr.open_rasterio(fr"{self.domain_path}\DOMAIN\Fulldom_hires.nc", mask_and_scale=True)
        dem = load_dem.squeeze()

        # Collect streamflow paths
        streamflow_files = sorted(glob.glob(fr"{self.domain_path}\simulations\*CHRTOUT_GRID1"))

        # Return streamflow_files and DEM
        return streamflow_files, dem

    def generate_flipped_reprojected_streamflow(
            self,
            each_file: str,
            dem: xr.Dataset
    ) -> xr.DataArray:
        """
        Definition:
            A function to generate flipped and reprojected streamflow files
        References:
            None.
        Arguments:
            each_file (str):
                Path of each streamflow file
            dem (xr.DataArray):
                DEM raster that stores coordinates and crs information
        Returns:
            streamflow_flipped_reprojected (xr.DataArray):
                Streamflow raster that were flipped upside down and reprojected
        """
        # Load CHRTOUT streamflow
        ds = xr.open_dataset(fr"{each_file}", mask_and_scale=True)
        streamflow = ds.streamflow.squeeze()

        # Flip streamflow vertically (Y is reversed in some CHRTOUT exports)
        streamflow_flipped = streamflow.isel(y=slice(None, None, -1))

        # Attach correct CRS and transform (from DEM) — even though CHRTOUT has it in attributes
        streamflow_flipped.rio.write_crs(dem.rio.crs, inplace=True)
        streamflow_flipped.rio.write_transform(dem.rio.transform(), inplace=True)

        # Reproject streamflow
        streamflow_flipped_reprojected = streamflow_flipped.rio.reproject("EPSG:4326")

        # Return flipped streamflow with new coordinates
        return streamflow_flipped_reprojected

    def write_out_nc_and_tiff(
            self,
            each_file: str,
            streamflow_flipped_reprojected: xr.DataArray
    ) -> None:
        """
        Definition:
            A function to generate flipped and reprojected streamflow files
        References:
            None.
        Arguments:
            each_file (str):
                Path of each streamflow file
            streamflow_flipped_reprojected (xr.DataArray):
                Streamflow raster that were flipped upside down and reprojected
        """
        # Create paths to save out
        simulations_tiff = fr"{self.domain_path}\simulations\streamflows\tiff"
        simulations_nc = fr"{self.domain_path}\simulations\streamflows\nc"
        Path(simulations_tiff).mkdir(parents=True, exist_ok=True)
        Path(simulations_nc).mkdir(parents=True, exist_ok=True)

        # Generate file name
        saveout_filename = Path(each_file).stem

        # Write out NetCDF and GeoTiff files
        streamflow_flipped_reprojected.rio.to_raster(fr"{simulations_tiff}\{saveout_filename}.tiff")
        streamflow_flipped_reprojected.to_netcdf(fr"{simulations_nc}\{saveout_filename}.nc")

    def execute_write_out_commands(self) -> None:
        """
        Definition:
            A function to write out flipped and reprojected streamflow files
            into GeoTiff and netCDF format.
        References:
            None.
        Arguments:
            Already defined above.
        """
        # Generate DEM and streamflow paths
        streamflow_files, dem = self.generate_dem_and_paths()

        # Flip, reproject, and write out streamflow files
        for each_file in streamflow_files:
            # Generate flipped and reprojected streamflow
            streamflow_flipped_reprojected = self.generate_flipped_reprojected_streamflow(each_file, dem)

            # Write out flipped and reprojected streamflow into GeoTiff and NetCDF files
            self.write_out_nc_and_tiff(each_file, streamflow_flipped_reprojected)


# EXAMPLES
# result_simulations = resultManipulation(
#     r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003"
# )
#
# result_simulations.execute_write_out_commands()
