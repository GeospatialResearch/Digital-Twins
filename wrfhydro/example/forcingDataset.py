# Necessary packages
import os
os.environ["ESMFMKFILE"] = r"C:\Users\mng42\AppData\Local\anaconda3\envs\wrfhydro_005\Library\lib\esmf.mk"

import xesmf as xe
import xarray as xr
import rioxarray as rxr
import numpy as np

import cdsapi
from datetime import datetime, timedelta, date
import calendar
from dateutil.relativedelta import relativedelta
import glob

from pathlib import Path
import os

# Develop a class to generate WRF-Hydro forcing data from ERA5
class generateERA5Forcing:
    def __init__(
            self,
            domain_path,
            download_path,
            start_date,
            end_date,
    ):
        """
        @Definition:
            A class to download forcing data from ERA5
        @References:
            https://cds.climate.copernicus.eu/how-to-api
            https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview
        @Arguments:
            domain_path (str):
                A path that stores the domain files, especially the geo_em.d0x.nc
            download_path (str):
                A path to store downloaded forcing data from ERA5
            start_date, end_date (list):
                Specific information of start and end dates that the forcing data needs downloading
                The format of the list is [yyyy, m, d, h]
        @Returns:
            None.
        """
        # Define variables
        self.download_path = download_path
        self.domain_path = domain_path

        self.start_date = datetime(start_date[0], start_date[1], start_date[2], start_date[3])
        self.end_date = datetime(end_date[0], end_date[1], end_date[2], end_date[3])
        # Total number of days
        self.number_of_days = (self.end_date - self.start_date)
        # Total hours
        self.number_of_hours = self.number_of_days.total_seconds() / 3600
        # Forcing variables
        self.variable_names = [
            "2m_temperature", "2m_dewpoint_temperature", "surface_pressure", "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "mean_surface_downward_long_wave_radiation_flux", "mean_surface_downward_short_wave_radiation_flux",
            "total_precipitation", "geopotential"
        ]
        # File names of variables
        self.file_names = [
            "t2m", "d2m", "sp", "u10m", "v10m", "msdlwrf", "msdswrf", "tp", "geo"
        ]

    def generate_date_info(self, each_hour):
        """
        @Definition:
            A function to generate specific date information includes:
            year, month, day, hour, and hour_minute
        @References:
            None.
        @Arguments:
            each_hour (int):
                Number of hours accumulated towards the end date since the start date
        @Returns:
            year, month, day, hour, hour_minute (str):
                Information of a specific date
        """
        # Generate specific date since the start date by increasing the hours
        specific_date = self.start_date + timedelta(hours=each_hour)

        # Generate year, month, day, hour, and hour_minute from the specific date
        year = specific_date.strftime("%Y")
        month = specific_date.strftime("%m")
        day = specific_date.strftime("%d")
        hour = specific_date.strftime("%H")
        hour_minute = specific_date.strftime("%H:%M")

        # Return the information of the specific date
        return year, month, day, hour, hour_minute

    def generate_request(self, each_variable, year, month, day, hour_minute):
        """
        @Definition:
            A function to generate specific date information includes:
            year, month, day, hour, and hour_minute
        @References:
            None.
        @Arguments:
            each_variable (int):
                The ordinal number of a variable in the list of variable names
            year, month, day, hour_minute (str):
                The information of the specific date
        @Returns:
            request (dict):
                A dictionary that describe the information of the request to download the data
        """
        # Design the request to download forcing data from ERA5
        request = {
            "product_type": ["reanalysis"],
            "variable": self.variable_names[each_variable],
            "year": [year],
            "month": [month],
            "day": [day],
            "time": [
                hour_minute
            ],
            "data_format": "netcdf",
            "download_format": "unarchived"
        }

        # Return the request
        return request

    def download_ERA5_forcing_data(self, request, each_file_name):
        """
        @Definition:
            A function to download forcing data from ERA5
        @References:
            None.
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        # Check if the files already exist
        if os.path.exists(each_file_name) and os.path.getsize(each_file_name) > 0:
            pass
        else:
            # If the files have not been downloaded then download
            client = cdsapi.Client()
            client.retrieve("reanalysis-era5-single-levels", request, each_file_name)

    def download_ERA5_each_variable(self, each_hour):
        """
        @Definition:
            A function to download all ERA5 variables necessary
            for WRF-Hydro forcing data given the time
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Loop each variable from total number of variables
        for each_variable in range(len(self.variable_names)):
            # Generate information for a specific date
            year, month, day, hour, hour_minute = self.generate_date_info(each_hour)
            # Generate request to download data
            request = self.generate_request(each_variable, year, month, day, hour_minute)
            # Generate path to download data
            each_file_name = str(
                Path(self.download_path) / f"{self.file_names[each_variable]}_{year}-{month}-{day}_{hour}_00_00.nc")
            # Download ERA5 forcing data
            self.download_ERA5_forcing_data(request, each_file_name)

    ####################################

    def generate_target_grid_dataset(self):
        """
        @Definition:
            A function to generate wrf file used to regrid
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Read geo_em.d0x.nc - domain file
        wrf_ds = xr.open_dataset(fr"{self.domain_path}\geo_em.d01.nc")

        # Extract 2D lat and lon
        wrf_lat = wrf_ds['XLAT_M'].isel(Time=0)
        wrf_lon = wrf_ds['XLONG_M'].isel(Time=0)

        # Generate the target grid dataset
        wrf_grid = xr.Dataset({
            'lat': wrf_lat,
            'lon': wrf_lon
        })

        # Return the target grid dataset
        return wrf_ds, wrf_grid

    def generate_sample_ERA5_to_regrid(self, each_hour):
        """
        @Definition:
            A function to generate sample ERA5 variable used to
            mearure the regridder
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Generate information of a specific date
        year, month, day, hour, _ = self.generate_date_info(each_hour)

        # Choose t2m as the sample variable to regrid
        t2m = xr.open_dataset(fr"{self.download_path}\t2m_{year}-{month}-{day}_{hour}_00_00.nc")
        t2m_copy = t2m.copy(deep=True)

        # Adjust t2m longitude from [0, 360] to [-180, 180]
        # and then extract 2D lat and lon
        t2m_copy['longitude'] = (((t2m_copy['longitude'] + 180) % 360) - 180)
        t2m_copy = t2m_copy.sortby('longitude')  # make sure the longitudes are sorted after shifting
        lon_2d, lat_2d = np.meshgrid(t2m_copy['longitude'], t2m_copy['latitude'])

        # Generate sample ERA5 file to regrid
        era5_grid = xr.Dataset({
            'lat': (['y', 'x'], lat_2d),
            'lon': (['y', 'x'], lon_2d)
        })

        # Return sample ERA5
        return era5_grid

    def regrid_ERA5(self, each_hour):
        """
        @Definition:
            A function to generate regridder to regrid ERA5 variables
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Generate target grid dataset
        _, wrf_grid = self.generate_target_grid_dataset()

        # Generate sample ERA5 file to regrid
        era5_grid = self.generate_sample_ERA5_to_regrid(each_hour)

        # Regrid to WRF-Hydro domain
        regridder = xe.Regridder(era5_grid, wrf_grid, 'bilinear',
                                 reuse_weights=False)

        # Return regridder
        return regridder

    def load_a_ERA5_variable(self, file_name_order, each_hour):
        """
        @Definition:
            A function to load each ERA5 variable
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Generate information of a specific date
        year, month, day, hour, _ = self.generate_date_info(each_hour)

        # Generate ERA5 file name
        era5_file_name = f"{self.file_names[file_name_order]}_{year}-{month}-{day}_{hour}_00_00.nc"

        # Load ERA5 variable
        era5_variable = xr.open_dataset(fr"{self.download_path}\{era5_file_name}")

        return era5_variable

    def load_ERA5_variables(self, each_hour):
        """
        @Definition:
            A function to load all ERA5 variables that are necessary
            for WRF-Hydro forcing data
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """
        # Load all ERA5 variables
        t2m = self.load_a_ERA5_variable(0, each_hour)  # 2m temperature from ERA5
        d2m = self.load_a_ERA5_variable(1, each_hour)  # 2m dewpoint temperature from ERA5
        sp = self.load_a_ERA5_variable(2, each_hour)  # surface pressure from ERA5
        u10m = self.load_a_ERA5_variable(3, each_hour)  # u 10m wind from ERA5
        v10m = self.load_a_ERA5_variable(4, each_hour)  # v 10m wind from ERA5
        msdlwrf = self.load_a_ERA5_variable(5, each_hour)  # long wave radiation from ERA5
        msdswrf = self.load_a_ERA5_variable(6, each_hour)  # short wave radiation from ERA5
        tp = self.load_a_ERA5_variable(7, each_hour)  # total precipitation from ERA5
        geo = self.load_a_ERA5_variable(8, each_hour)  # geopotential from ERA5

        # Return ERA5 variables
        return t2m, d2m, sp, u10m, v10m, msdlwrf, msdswrf, tp, geo

    def generate_merged_forcing_dataset(self, each_hour):
        """
        @Definition:
            A function to compute and convert ERA5 variables into
            WRF-Hydro forcing data and merge them together.
            At the moment, this function cannot be splitted into
            smaller functions because the regridder is called only once.
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """

        # Load all ERA5 variables
        t2m, d2m, sp, u10m, v10m, lwr, swr, tp, geo = self.load_ERA5_variables(each_hour)

        # Generate regridder
        # Generate regridder
        regridder = self.regrid_ERA5(each_hour)

        ## Generate geopotential height or surface height ----
        # Convert geopotential to geopotential height
        ght = geo['z'] / 9.80665
        # Regrid to WRF-Hydro domain
        ght_regridded = regridder(ght)

        ## Generate terrain difference ----
        # Generate target grid dataset and geopotential height
        wrf_ds, _ = self.generate_target_grid_dataset()
        # Extract the WRF-Hydro terrian height
        wrf_terrain = wrf_ds['HGT_M'].isel(Time=0)
        # Compute the elevation difference
        terrain_diff = ght_regridded - wrf_terrain

        ## Generate adjusted 2m temperature ----
        # Define lapse rate in K/m
        lapse_rate = 0.00649
        # Generate 2m temperature (in K)
        t2m_k_regridded = regridder(t2m)
        # Generate adjusted 2m temperature (in K)
        t2m_adj = t2m_k_regridded + lapse_rate * terrain_diff

        ## Generate surface pressure
        Rd = 287  # dry air constant (J/kg/K)
        g = 9.80665  # gravity (m/S^2)
        # Generate regridded surface pressure
        sp_regridded = regridder(sp)
        # Generate adjusted surface pressure
        sp_adj = sp_regridded * np.exp(-g * terrain_diff / (Rd * t2m_adj['t2m']))

        ## Generate specific humidity
        # Convert K to C
        d2m_c = d2m - 273.15  # K to C
        # Generate regridded dewpoint temperature
        d2m_c_regridded = regridder(d2m_c)
        # Generate adjusted dewpoint temperature
        d2m_c_adj = d2m_c_regridded + lapse_rate * terrain_diff
        # Generate saturation vapor pressure
        es_hPa = 6.112 * np.exp((17.67 * d2m_c_adj['d2m']) / (d2m_c_adj['d2m'] + 243.5))
        es_Pa = es_hPa * 100  # convert hPa to Pa
        # Generate specific humidity
        q2 = (0.622 * es_Pa) / (sp_adj - 0.378 * es_Pa)
        q2_positive = xr.where(q2 < 0, 0, q2)  # Make sure specific humidity is positive

        ## Generate regridded radiation, precipitation, and wind
        lwr_regridded = regridder(lwr['avg_sdlwrf'])  # regridded long wave radiation
        swr_regridded = regridder(swr['avg_sdswrf'])  # regridded short wave radiation
        tp_regridded = regridder(tp['tp'])  # regridded total precipitation
        v10m_regridded = regridder(v10m['v10'])  # regridded v 10m wind
        u10m_regridded = regridder(u10m['u10'])  # regridded u 10m wind

        # List WRF-Hydro forcing data
        datasets = [
            t2m_adj.rename({"t2m": "T2D"}),
            sp_adj.rename({"sp": "PSFC"}),
            q2_positive.rename({"sp": "Q2D"}),
            u10m_regridded.rename("U10"),
            v10m_regridded.rename("V10"),
            lwr_regridded.rename("LWDOWN"),
            swr_regridded.rename("SWDOWN"),
            tp_regridded.rename("RAINRATE")
        ]

        # Merge WRF-Hydro forcing data
        combined_dataset = xr.merge(datasets)

        # Return WRF-Hydro forcing data
        return combined_dataset

    def generate_LDASIN(self, each_hour):
        """
        @Definition:
            A function to convert them into LDASIN data that can be
            used by WRF-Hydro
        @References:
            None.
        @Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        @Returns:
            None.
        """

        # Generate merged dataset
        combined_dataset = self.generate_merged_forcing_dataset(each_hour)

        # Create forcing folder to store all forcing data
        forcing_path = fr"{self.domain_path}\FORCING"
        Path(forcing_path).mkdir(parents=True, exist_ok=True)

        # Generate information of a specific date
        year, month, day, hour, _ = self.generate_date_info(each_hour)

        # Write out the merged dataset
        combined_dataset.to_netcdf(fr"{self.domain_path}\\FORCING\\{year}{month}{day}{hour}.LDASIN_DOMAIN1")

    ####################################

    def execute_download_and_convert_commands(self):
        """
        @Definition:
            A function to download forcing data from ERA5
            and convert them into LDASIN data that can be
            used by WRF-Hydro
        @References:
            None.
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        # Loop each hour from total number of hours
        for each_hour in range(int(self.number_of_hours)):
            # Download ERA5 data
            self.download_ERA5_each_variable(each_hour)

            # Convert ERA5 dataset into WRF-Hydro forcing variable
            # and write out as YYYYMMDDHH.LDASIN_DOMAIN1
            self.generate_LDASIN(each_hour)

# EXAMPLES
# download_result = generateERA5Forcing(
#     r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003",
#     r"Y:\Temporary\ERA_003",
#     [2020, 2, 29, 1],
#     [2020, 2, 29, 3]
# )
#
# download_result.execute_download_and_convert_commands()