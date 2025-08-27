"""Runs to download ERA5 files and convert to FORCING data"""
# pylint: disable=differing-param-doc,differing-type-doc, wrong-import-position

# Necessary packages
from typing import Tuple

from pathlib import Path
import os
os.environ["ESMFMKFILE"] = r"C:\Users\mng42\AppData\Local\anaconda3\envs\wrfhydro_005\Library\lib\esmf.mk"
from datetime import datetime, timedelta  # noqa: E402

import xesmf as xe  # noqa: E402
import xarray as xr  # noqa: E402
import numpy as np  # noqa: E402
import cdsapi  # noqa: E402


# Develop a class to generate WRF-Hydro forcing data from ERA5
class DownloadERA5Forcing:
    """A class to download forcing data from ERA5"""

    def __init__(
            self,
            domain_path: str,
            download_path: str,
            start_date: str,
            end_date: str,
    ) -> None:
        """
        Definition:
            Init function to state common arguments
        References:
            https://cds.climate.copernicus.eu/how-to-api
            https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview
        Arguments:
            domain_path (str):
                A path that stores the domain files, especially the geo_em.d0x.nc
            download_path (str):
                A path to store downloaded forcing data from ERA5
            start_date, end_date (list):
                Specific information of start and end dates that the forcing data needs downloading
                The format of the list is [yyyy, m, d, h]
        """
        # Define variables
        self.download_path = download_path
        self.domain_path = domain_path

        # Set up start and end dates
        self.start_date = datetime(start_date[0], start_date[1], start_date[2], start_date[3])
        self.end_date = datetime(end_date[0], end_date[1], end_date[2], end_date[3])
        # Calculate total hours
        self.number_of_hours = (self.end_date - self.start_date).total_seconds() / 3600
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

    def generate_date_info(
            self,
            each_hour: int
    ) -> Tuple[str, str, str, str]:
        """
        Definition:
            A function to generate specific date information includes:
            year, month, day, hour, and hour_minute
        References:
            None.
        Arguments:
            each_hour (int):
                Number of hours accumulated towards the end date since the start date
        Returns:
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

    def generate_request(
            self,
            each_variable: int,
            year: str,
            month: str,
            day: str,
            hour_minute: str
    ) -> dict:
        """
        Definition:
            A function to generate specific date information includes:
            year, month, day, hour, and hour_minute
        References:
            None.
        Arguments:
            each_variable (int):
                The ordinal number of a variable in the list of variable names
            year (str):
                Year of the requested data.
            month (str):
                Month of the requested data.
            day (str):
                Day of the requested data.
            hour_minute (str):
                Hour and minute of the requested data.
        Returns:
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

    def download_era5_forcing_data(
            self,
            request: dict,
            each_file_name: str
    ) -> None:
        """
        Definition:
            A function to download forcing data from ERA5
        References:
            None.
        Arguments:
            request (dict):
                A dictionary that describe the information of the request to download the data
            each_file_name (str):
                A path that includes where the ERA5 files are downloaded to and their names
        """
        # Check if the files already exist
        if os.path.exists(each_file_name) and os.path.getsize(each_file_name) > 0:
            pass
        else:
            # If the files have not been downloaded then download
            client = cdsapi.Client()
            client.retrieve("reanalysis-era5-single-levels", request, each_file_name)

    def download_era5_each_variable(
            self,
            each_hour: int
    ) -> None:
        """
        Definition:
            A function to download all ERA5 variables necessary
            for WRF-Hydro forcing data given the time.
        References:
            None.
        Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time.
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
            self.download_era5_forcing_data(request, each_file_name)


class GenerateERA5Forcing:
    """A class to generate forcing data from ERA5"""

    def __init__(
            self,
            domain_path: str,
            download_path: str,
            start_date: str,
            end_date: str,
    ) -> None:
        """
        Definition:
            Init function to state common arguments
        References:
            https://cds.climate.copernicus.eu/how-to-api
            https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview
        Arguments:
            domain_path (str):
                A path that stores the domain files, especially the geo_em.d0x.nc
            download_path (str):
                A path to store downloaded forcing data from ERA5
            start_date, end_date (list):
                Specific information of start and end dates that the forcing data needs downloading
                The format of the list is [yyyy, m, d, h]
        """
        # Define variables
        self.era5_information = DownloadERA5Forcing(
            domain_path,
            download_path,
            start_date,
            end_date
        )

    def generate_wrf_grid(self) -> xr.Dataset:
        """
        Definition:
            A function to generate wrf file used to regrid
        References:
            None.
        Arguments:
            None.
        Returns:
            wrf_ds (xr.Dataset):
                A raster that includes domain features
            wrf_grid (xr.Dataset):
                A raster that includes latitude and longitude of domain
        """
        # Read geo_em.d0x.nc - domain file
        wrf_ds = xr.open_dataset(fr"{self.era5_information.domain_path}\geo_em.d01.nc")

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

    def adjust_longitude(
            self,
            ds: xr.Dataset
    ) -> xr.Dataset:
        """
        Definition:
            A function to adjust longitude from [0, 360] to [-180, 180]
        References:
            None.
        Arguments:
            ds (xr.Dataset):
                A raster of an ERA5 file
        Returns:
            sorted_ds (xr.Dataset):
                A raster that has longitude adjusted
        """
        # Adjust longitude of er4 variable from [0, 360] to [-180, 180]
        ds['longitude'] = ((ds['longitude'] + 180) % 360) - 180

        # Make sure the longitudes are sorted after shifting
        sorted_ds = ds.sortby('longitude')

        # Return sorted dataset
        return sorted_ds

    def generate_era5_grid(self) -> xr.Dataset:
        """
        Definition:
            A function to generate ERA5 grid
        References:
            None.
        Arguments:
            None.
        Returns:
            era5_grid (xr.Dataset):
                A raster of a variable (t2m chosen here) that includes latitude and longitude
        """
        # Get information of initial date
        s_year = self.era5_information.start_date.strftime("%Y")
        s_month = self.era5_information.start_date.strftime("%m")
        s_day = self.era5_information.start_date.strftime("%d")
        s_hour = self.era5_information.start_date.strftime("%H")

        # Adjust 2m temperature longitude from [0, 360] to [-180, 180]
        t2m_for_regridder = self.adjust_longitude(
            xr.open_dataset(fr"{self.era5_information.download_path}\t2m_{s_year}-{s_month}-{s_day}_{s_hour}_00_00.nc")
        )

        # Generate era5 grid
        lon_2d, lat_2d = np.meshgrid(t2m_for_regridder['longitude'], t2m_for_regridder['latitude'])
        era5_grid = xr.Dataset({
            'lat': (['y', 'x'], lat_2d),
            'lon': (['y', 'x'], lon_2d)
        })

        # Return era5 grid
        return era5_grid

    def generate_regridder(self) -> xe.Regridder:
        """
        Definition:
            A function to generate regridder function
        References:
            None.
        Arguments:
            None.
        Returns:
            regridder (xr.Dataset):
                A raster of a variable (t2m chosen here) that includes latitude and longitude
        """
        # Generate target wrf grid
        _, wrf_grid = self.generate_wrf_grid()

        # Generate era5 grid
        era5_grid = self.generate_era5_grid()

        # Generate regridder
        regridder = xe.Regridder(era5_grid, wrf_grid, 'bilinear',
                                 reuse_weights=False)

        # Return the regridder
        return regridder

    def load_an_era5_variable(
            self,
            file_name_order: int,
            each_hour: int
    ) -> xr.Dataset:
        """
        Definition:
            A function to load each ERA5 variable
        References:
            None.
        Arguments:
            file_name_order (int):
                The order of a variable in a list defined above
            each_hour (int):
                Each hour represents an increment added to the current time
        Returns:
            era_variable (xr.Dataset):
                An ERA5-variable raster
        """
        # Generate information of a specific date
        year, month, day, hour, _ = self.era5_information.generate_date_info(each_hour)

        # Generate ERA5 file name
        era5_file_name = f"{self.era5_information.file_names[file_name_order]}_{year}-{month}-{day}_{hour}_00_00.nc"

        # Load ERA5 variable
        era5_variable = self.adjust_longitude(
            xr.open_dataset(fr"{self.era5_information.download_path}\{era5_file_name}")
        )

        # Return the ERA5 variable
        return era5_variable

    def load_era5_variables(
            self,
            each_hour: int
    ) -> dict:
        """
        Definition:
            A function to load all ERA5 variables that are necessary
            for WRF-Hydro forcing data
        References:
            None.
        Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        Returns:
            era5_variables (dict):
                A dictionary that includes:
                    t2m - 2m temperature (K)
                    d2m - 2m dewpoint temperature (K)
                    sp - surface pressure (Pa)
                    u10m - 10m wind u-component (m/s)
                    v10m - 10m wind v-component (m/s)
                    msdlwrf - long-wave radiation (W/m2)
                    msdswrf - short-wave radiation (W/m2)
                    tp - total precipitation (m)
                    geo - geopotential (m2/s2)
        """
        # Load all ERA5 variables
        t2m = self.load_an_era5_variable(0, each_hour)  # 2m temperature from ERA5
        d2m = self.load_an_era5_variable(1, each_hour)  # 2m dewpoint temperature from ERA5
        sp = self.load_an_era5_variable(2, each_hour)  # surface pressure from ERA5
        u10m = self.load_an_era5_variable(3, each_hour)  # u 10m wind from ERA5
        v10m = self.load_an_era5_variable(4, each_hour)  # v 10m wind from ERA5
        msdlwrf = self.load_an_era5_variable(5, each_hour)  # long wave radiation from ERA5
        msdswrf = self.load_an_era5_variable(6, each_hour)  # short wave radiation from ERA5
        tp = self.load_an_era5_variable(7, each_hour)  # total precipitation from ERA5
        geo = self.load_an_era5_variable(8, each_hour)  # geopotential from ERA5

        # Store them into a dictionary
        era5_variables = {
            "t2m": t2m,
            "d2m": d2m,
            "sp": sp,
            "u10m": u10m,
            "v10m": v10m,
            "msdlwrf": msdlwrf,
            "msdswrf": msdswrf,
            "tp": tp,
            "geo": geo
        }

        # Return ERA5 variables
        return era5_variables

    def generate_ght_regridded(
            self,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate geopotential height or surface height
        References:
            None.
        Arguments:
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            ght_regridded (xr.Dataset):
                A raster of regridded geopotential height
        """
        # Define gravity (m/S^2)
        gravity = 9.80665

        # Convert geopotential to geopotential height
        ght = geo['z'] / gravity

        # Regrid to WRF-Hydro domain
        ght_regridded = regridder(ght)

        # Return regridded ght
        return ght_regridded

    def generate_terrain_difference(
            self,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate terrain difference
        References:
            None.
        Arguments:
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            terrain_diff (xr.Dataset):
                A raster of terrain difference
        """
        # Generate wrf dataset
        wrf_ds, _ = self.generate_wrf_grid()

        # Extract the WRF-Hydro terrain height
        wrf_terrain = wrf_ds['HGT_M'].isel(Time=0)

        # Generate regridded geopotential height
        ght_regridded = self.generate_ght_regridded(geo, regridder)

        # Compute the elevation difference
        terrain_diff = ght_regridded - wrf_terrain

        # Return terrain difference
        return terrain_diff

    def generate_adjusted_t2m(
            self,
            t2m: xr.Dataset,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate adjusted 2m temperature
        References:
            None.
        Arguments:
            t2m (xr.Dataset):
                A raster of ERA5 variable - 2m temperature
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            t2m_adj (xr.Dataset):
                A raster of adjusted 2m temperature
        """
        # Define lapse rate in K/m
        lapse_rate = 0.00649

        # Generate 2m temperature (in K)
        t2m_k_regridded = regridder(t2m)

        # Generate terrain difference
        terrain_diff = self.generate_terrain_difference(geo, regridder)

        # Generate adjusted 2m temperature (in K)
        t2m_adj = t2m_k_regridded - lapse_rate * terrain_diff

        # Return adjusted 2m temperature
        return t2m_adj

    def generate_adjusted_surface_pressure(
            self,
            t2m: xr.Dataset,
            sp: xr.Dataset,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate adjusted surface pressure
        References:
            None.
        Arguments:
            t2m (xr.Dataset):
                A raster of ERA5 variable - 2m temperature
            sp (xr.Dataset):
                A raster of ERA5 variable - surface pressure
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            sp_adj (xr.Dataset):
                A raster of adjusted surface pressure
        """
        # Define dry air constant (J/kg/K)
        dry_air_constant = 287

        # Define gravity (m/S^2)
        gravity = 9.80665

        # Generate regridded surface pressure
        sp_regridded = regridder(sp)

        # Generate adjusted 2m temperature
        t2m_adj = self.generate_adjusted_t2m(t2m, geo, regridder)

        # Generate terrain difference
        terrain_diff = self.generate_terrain_difference(geo, regridder)

        # Generate adjusted surface pressure
        sp_adj = sp_regridded * np.exp(-gravity * terrain_diff / (dry_air_constant * t2m_adj['t2m']))

        # Return adjusted surface pressure
        return sp_adj

    def generate_adjusted_d2m(
            self,
            d2m: xr.Dataset,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate adjusted 2m dewpoint temperature
        References:
            None.
        Arguments:
            d2m (xr.Dataset):
                A raster of ERA5 variable - 2m dewpoint temperature
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            d2m_c_adj (xr.Dataset):
                A raster of adjusted 2m dewpoint temperature
        """
        # Define lapse rate in K/m
        lapse_rate = 0.00649

        # Convert K to C
        d2m_c = d2m - 273.15

        # Generate regridded 2m dewpoint temperature
        d2m_c_regridded = regridder(d2m_c)

        # Generate terrain difference
        terrain_diff = self.generate_terrain_difference(geo, regridder)

        # Generate adjusted 2m dewpoint temperature
        d2m_c_adj = d2m_c_regridded - lapse_rate * terrain_diff

        # Return adjusted 2m dewpoint temperature
        return d2m_c_adj

    def generate_specific_humidity(
            self,
            t2m: xr.Dataset,
            d2m: xr.Dataset,
            sp: xr.Dataset,
            geo: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate adjusted surface pressure
        References:
            None.
        Arguments:
            t2m (xr.Dataset):
                A raster of ERA5 variable - 2m temperature
            d2m (xr.Dataset):
                A raster of ERA5 variable - 2m dewpoint temperature
            sp (xr.Dataset):
                A raster of ERA5 variable - surface pressure
            geo (xr.Dataset):
                A raster of ERA5 variable - geopotential
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            q2_positive (xr.Dataset):
                A raster of specific humidity
        """
        # Generate adjusted 2m dewpoint temperature
        d2m_c_adj = self.generate_adjusted_d2m(
            d2m,
            geo,
            regridder
        )

        # Generate saturation vapor pressure
        es_hpa = 6.112 * np.exp((17.67 * d2m_c_adj['d2m']) / (d2m_c_adj['d2m'] + 243.5))

        # Convert hPa to Pa
        es_pa = es_hpa * 100

        # Generate adjusted specific humidity
        sp_adj = self.generate_adjusted_surface_pressure(t2m, sp, geo, regridder)

        # Generate specific humidity
        q2 = (0.622 * es_pa) / (sp_adj - 0.378 * es_pa)

        # Make sure specific humidity is positive
        q2_positive = xr.where(q2 < 0, 0, q2)

        # Return positive specific humidity
        return q2_positive

    def generate_conversed_precipitation(
            self,
            tp: xr.Dataset,
            regridder: xe.Regridder
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate adjusted surface pressure
        References:
            None.
        Arguments:
            tp (xr.Dataset):
                A raster of ERA5 variable:
                    total precipitation
            regridder (xe.Regridder):
                A function to regrid ERA5 variable
        Returns:
            tp_regridded (xr.Dataset):
                A raster of conversed total precipitation
        """
        # Convert total precipitation in meter
        # and to rate (unit is mm/s)
        tp_conversion = tp * 1000 / 3600

        # Regrid conversed total precipitation
        tp_regridded = regridder(tp_conversion['tp'])

        # Return conversed total precipitation
        return tp_regridded

    def generate_forcing_dataset(
            self,
            each_hour: int
    ) -> xr.Dataset:
        """
        Definition:
            A function to generate all forcing dataset
        References:
            None.
        Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        Returns:
            forcing_dataset (dict):
                A dictionary that includes:
                    adjusted t2m - 2m temperature (K)
                    adjusted sp - surface pressure (Pa)
                    regridded u10m - 10m wind u-component (m/s)
                    regridded v10m - 10m wind v-component (m/s)
                    regridded msdlwrf - long-wave radiation (W/m2)
                    regridded msdswrf - short-wave radiation (W/m2)
                    regridded and conversed tp - total precipitation (m)
        """
        # Load all ERA5 variables
        era5_variables = self.load_era5_variables(each_hour)

        # Generate regridder
        regridder = self.generate_regridder()

        # Generate adjusted 2m temperature
        t2m_adj = self.generate_adjusted_t2m(
            era5_variables['t2m'], era5_variables['geo'], regridder)

        # Generate adjusted surface pressure
        sp_adj = self.generate_adjusted_surface_pressure(
            era5_variables['t2m'],
            era5_variables['sp'],
            era5_variables['geo'],
            regridder
        )

        # Generate specific humidity
        q2_positive = self.generate_specific_humidity(
            era5_variables['t2m'],
            era5_variables['d2m'],
            era5_variables['sp'],
            era5_variables['geo'],
            regridder
        )

        # Generate conversed precipitation
        tp_regridded = self.generate_conversed_precipitation(
            era5_variables['tp'],
            regridder)

        # Generate regridded short- and long-wave radiations
        lwr_regridded = regridder(era5_variables['msdlwrf']['avg_sdlwrf'])
        swr_regridded = regridder(era5_variables['msdswrf']['avg_sdswrf'])

        # Generate regridded wind with u- and v-components
        v10m_regridded = regridder(era5_variables['v10m']['v10'])
        u10m_regridded = regridder(era5_variables['u10m']['u10'])

        # Set up a dictionary to list all variables
        forcing_dataset = {
            "t2m_adj": t2m_adj,
            "sp_adj": sp_adj,
            "q2_positive": q2_positive,
            "u10m_regridded": u10m_regridded,
            "v10m_regridded": v10m_regridded,
            "lwr_regridded": lwr_regridded,
            "swr_regridded": swr_regridded,
            "tp_regridded": tp_regridded
        }

        # Return forcing dataset
        return forcing_dataset

    def generate_merged_forcing_dataset(
            self,
            each_hour: int
    ) -> xr.Dataset:
        """
        Definition:
            A function to merged all forcing dataset
        References:
            None.
        Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        Returns:
            combined_dataset (xr.Dataset):
                A raster that includes:
                    T2D: 2m temperature (K)
                    Q2D: 2m specific humidity (kg/kg)
                    PSFC: surface pressure (Pa)
                    U10, V10: 10m wind u- and v-components (m/s)
                    LWDOWN, SWDOWN: long- and short-wave radiation (W/m2)
                    RAINRATE: Total precipitation rate (mm/s)
        """
        # Generate forcing dataset
        forcing_dataset = self.generate_forcing_dataset(each_hour)

        # List WRF-Hydro forcing dataset
        datasets = [
            forcing_dataset['t2m_adj'].rename({"t2m": "T2D"}),
            forcing_dataset['sp_adj'].rename({"sp": "PSFC"}),
            forcing_dataset['q2_positive'].rename({"sp": "Q2D"}),
            forcing_dataset['u10m_regridded'].rename("U10"),
            forcing_dataset['v10m_regridded'].rename("V10"),
            forcing_dataset['lwr_regridded'].rename("LWDOWN"),
            forcing_dataset['swr_regridded'].rename("SWDOWN"),
            forcing_dataset['tp_regridded'].rename("RAINRATE")
        ]

        # Merge WRF-Hydro forcing dataset
        combined_dataset = xr.merge(datasets)

        # Return WRF-Hydro forcing dataset
        return combined_dataset

    def generate_ldasin(
            self,
            each_hour: int
    ) -> None:
        """
        Definition:
            A function to convert them into LDASIN data that can be used by WRF-Hydro
        References:
            None.
        Arguments:
            each_hour (int):
                Each hour represents an increment added to the current time
        """
        # Generate merged dataset
        combined_dataset = self.generate_merged_forcing_dataset(each_hour)

        # Create forcing folder to store all forcing data
        forcing_path = fr"{self.era5_information.domain_path}\FORCING"
        Path(forcing_path).mkdir(parents=True, exist_ok=True)

        # Generate information of a specific date
        year, month, day, hour, _ = self.era5_information.generate_date_info(each_hour)

        # Write out the merged dataset
        combined_dataset.to_netcdf(
            fr"{self.era5_information.domain_path}\\FORCING\\{year}{month}{day}{hour}.LDASIN_DOMAIN1"
        )

    ####################################

    def execute_download_and_convert_commands(self) -> None:
        """
        Definition:
            A function to download forcing data from ERA5
            and convert them into LDASIN data that can be
            used by WRF-Hydro
        References:
            None.
        Arguments:
            Already defined above.
        """
        # Loop each hour from total number of hours
        for each_hour in range(int(self.era5_information.number_of_hours)):
            # Download ERA5 data
            self.era5_information.download_era5_each_variable(each_hour)

            # Convert ERA5 dataset into WRF-Hydro forcing variable
            # and write out as YYYYMMDDHH.LDASIN_DOMAIN1
            self.generate_ldasin(each_hour)


# EXAMPLES
# download_result = generateERA5Forcing(
#     r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003",
#     r"Y:\Temporary\ERA_003",
#     [2020, 2, 29, 1],
#     [2020, 2, 29, 3]
# )
#
# download_result.execute_download_and_convert_commands()
