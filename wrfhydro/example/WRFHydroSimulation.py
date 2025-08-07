# Necessary packages
import shutil
import cdsapi
from datetime import datetime, timedelta, date

import subprocess
from pathlib import Path

# Develop a class to generate WRF-Hydro simulation
class generateWRFHydroSimulation:
    def __init__(
            self,
            # Paths
            domain_path,

            # namelist.hrldas
            START_DATE,
            KHOUR,
            RESTART_FREQUENCY_HOURS,

            # hydro.namelist
            DXRT, AGGFACTRT,
            DTRT_CH, DTRT_TER,
            rst_dt=300,
            CHRTOUT_DOMAIN=1,
            CHANOBS_DOMAIN=1,
            CHRTOUT_GRID=1,
            LSMOUT_DOMAIN=1,
            RTOUT_DOMAIN=1,
            output_gw=1,
            outlake=0,
            frxst_pts_out=1
    ):
        """
        @Definition:
            A class to run WRF-Hydro simulation
        @References:
            None.
        @Arguments:
            domain_path (str):
                Define domain path that stores necessary inputs to run
                WRF-Hydro simulation, especially TBL files, DOMAIN, FORCING
            START_DATE (list):
                A list that stores information of a specific date.
                Format is [YYYY, M, D, H, MIN]
            KHOUR (int):
                A number of hours of simulations
            RESTART_REFREQUENCY_HOURS (int):
                Define how often the land surface model restart file is written out
            DXRT (float):
                Resolution og terrain routing grid (in meters)
            AGGFACTRT (int):
                Regridding factor stated when building routing stack
                or the integer multiply between the land model grid
                and the terrain routing grid
            DTRT_CH (int):
                Channel routing model timestep: How often water movement
                in the stream network is updated (in seconds)
            DTRT_TER (int):
                Terrain routing model timestep: How often overland or
                surface water routing (on hillslopes) is updated (in seconds)
            rst_dt (int):
                Control how often the restart file is written out (in seconds)
                Default is 5 minutes = 300 seconds
            CHRTOUT_DOMAIN, CHANOBS_DOMAIN, CHRTOUT_GRID, LSMOUT_DOMAIN,
            ROUT_DOMAIN, output_gw, outlake, frxst_pts_out (int):
                Parameters control output files:
                    - 1: Activate that output file
                    - 0: Deactivate that output file
                The explanation of each of them are detailed in functions to
                generate hydro.namelist and namelist.hrldas
        @Returns:
            None.
        """
        # Define domain path
        self.domain_path = domain_path
        # Define window simulation path where the TBL files and wrf_hydro_NoahMP.exe are stored
        self.window_simulation_path = r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\geogrid"

        # NAMELIST.HRLDAS
        self.START_DATE = START_DATE
        self.KHOUR = KHOUR
        self.RESTART_FREQUENCY_HOURS = RESTART_FREQUENCY_HOURS

        ## HYDRO.NAMELIST
        self.DXRT = DXRT
        self.AGGFACTRT = AGGFACTRT
        self.DTRT_CH = DTRT_CH
        self.DTRT_TER = DTRT_TER
        self.rst_dt = rst_dt
        self.CHRTOUT_DOMAIN = CHRTOUT_DOMAIN
        self.CHANOBS_DOMAIN = CHANOBS_DOMAIN
        self.CHRTOUT_GRID = CHRTOUT_GRID
        self.LSMOUT_DOMAIN = LSMOUT_DOMAIN
        self.RTOUT_DOMAIN = RTOUT_DOMAIN
        self.output_gw = output_gw
        self.outlake = outlake
        self.frxst_pts_out = frxst_pts_out

    def generate_simulation_date_info(self):
        """
        @Definition:
            A function to generate start date information to run WRF-Hydro simulation
        @References:
            None.
        @Arguments:
            Already defined above.
        @Returns:
            year, month, day, hour, minute (str):
                Information of a specific start date
        """
        # Define specific start date through datetime format
        specific_date = datetime(self.START_DATE[0], self.START_DATE[1],
                                 self.START_DATE[2], self.START_DATE[3],
                                 self.START_DATE[4])

        # Extract year, month, day, hour, and minute
        YEAR = specific_date.strftime("%Y")
        MONTH = specific_date.strftime("%m")
        DAY = specific_date.strftime("%d")
        HOUR = specific_date.strftime("%H")
        MINUTE = specific_date.strftime("%M")

        return YEAR, MONTH, DAY, HOUR, MINUTE

    def generate_namelist_hrldas(self):
        """
        @Definition:
            A function to generate namelist.hrldas to run WRF-Hydro simulation
        @References:
            https://ral.ucar.edu/sites/default/files/public/Noahhrldas.namelistfiledescriptionofoptionsWHV5.pdf
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """

        # Generate information of a specific start date
        YEAR, MONTH, DAY, HOUR, MINUTE = self.generate_simulation_date_info()

        # Content of namelist.hrldas to run simulation
        content = f"""&NOAHLSM_OFFLINE

HRLDAS_SETUP_FILE = "./DOMAIN/wrfinput_d01.nc"
INDIR = "./FORCING"
SPATIAL_FILENAME = "./DOMAIN/soil_properties.nc"
OUTDIR = "./"

START_YEAR  = {YEAR}
START_MONTH = {MONTH}
START_DAY   = {DAY}
START_HOUR  = {HOUR}
START_MIN   = {MINUTE}

! Specification of the land surface model restart file
! Comment out the option if not initializing from a restart file
! RESTART_FILENAME_REQUESTED = "RESTART/RESTART.2011082600_DOMAIN1"

! Specification of simulation length in hours OR days
! KDAY = 7 ! This option is deprecated and may be removed in a future version
KHOUR = {self.KHOUR}

! Physics options (see the documentation for details)
DYNAMIC_VEG_OPTION                = 4
CANOPY_STOMATAL_RESISTANCE_OPTION = 1
BTR_OPTION                        = 1
RUNOFF_OPTION                     = 3
SURFACE_DRAG_OPTION               = 1
FROZEN_SOIL_OPTION                = 1
SUPERCOOLED_WATER_OPTION          = 1
RADIATIVE_TRANSFER_OPTION         = 3
SNOW_ALBEDO_OPTION                = 2
PCP_PARTITION_OPTION              = 1
TBOT_OPTION                       = 2
TEMP_TIME_SCHEME_OPTION           = 3
GLACIER_OPTION                    = 2
SURFACE_RESISTANCE_OPTION         = 4
IMPERV_OPTION                     = 9  !(0->none; 1->total; 2->Alley&Veenhuis; 9->orig)

! Timesteps in units of seconds
FORCING_TIMESTEP = 3600
NOAH_TIMESTEP    = 3600
OUTPUT_TIMESTEP  = 3600

! Land surface model restart file write frequency
! A value of -99999 will output restarts on the first day of the month only
RESTART_FREQUENCY_HOURS = {self.RESTART_FREQUENCY_HOURS}

! Split output after split_output_count output times.
SPLIT_OUTPUT_COUNT = 1

! Soil layer specification
NSOIL=4
soil_thick_input(1) = 0.10
soil_thick_input(2) = 0.30
soil_thick_input(3) = 0.60
soil_thick_input(4) = 1.00

! Forcing data measurement height for winds, temp, humidity
ZLVL = 10.0

! Restart file format options
rst_bi_in = 0      !0: use netcdf input restart file
                   !1: use parallel io for reading multiple restart files (1 per core)
rst_bi_out = 0     !0: use netcdf output restart file
                   !1: use parallel io for outputting multiple restart files (1 per core)

! Forcing input variable names
forcing_name_T = "T2D"
forcing_name_Q = "Q2D"
forcing_name_U = "U10"
forcing_name_V = "V10"
forcing_name_P = "PSFC"
forcing_name_LW = "LWDOWN"
forcing_name_SW = "SWDOWN"
forcing_name_PR = "RAINRATE"

/

&WRF_HYDRO_OFFLINE

! Specification of forcing data:  1=HRLDAS-hr format, 2=HRLDAS-min format, 3=WRF,
!    4=Idealized, 5=Idealized w/ spec. precip.,
!    6=HRLDAS-hr format w/ spec. precip., 7=WRF w/ spec. precip.,
!    9=Channel-only forcing, see hydro.namelist output_channelBucket_influxes
!    10=Channel+Bucket only forcing, see hydro.namelist output_channelBucket_influxes
FORC_TYP = 1

/

&CROCUS_nlist
  crocus_opt = 0   ! 0 model is off, 1 model is on
  act_lev = 40     ! 20-40 normal range, 1-50 acceptable
/

"""
        # Generate the hydro.namelist file
        with open(f'{self.domain_path}/namelist.hrldas', "w") as namelist_hrldas_file:
            namelist_hrldas_file.write(content)

    def generate_hydro_namelist(self):
        """
        @Definition:
            A function to generate hydro.namelist
        @References:
            https://ral.ucar.edu/sites/default/files/public/WRF-Hydrohydro.namelistfiledescriptionofoptionsV5.pdf
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """

        # Content of hydro.namelist to run WRF-Hydro simulation
        content = f"""&HYDRO_nlist
!!!! ---------------------- SYSTEM COUPLING ----------------------- !!!!

! Specify what is being coupled:  1=HRLDAS (offline Noah-LSM), 2=WRF, 3=NASA/LIS, 4=CLM
sys_cpl = 1

!!!! ------------------- MODEL INPUT DATA FILES ------------------- !!!!

! Specify land surface model gridded input data file (e.g.: "geo_em.d01.nc")
GEO_STATIC_FLNM = "./DOMAIN/geo_em.d01.nc"

! Specify the high-resolution routing terrain input data file (e.g.: "Fulldom_hires.nc")
GEO_FINEGRID_FLNM = "./DOMAIN/Fulldom_hires.nc"

! Specify the spatial hydro parameters file (e.g.: "hydro2dtbl.nc")
! If you specify a filename and the file does not exist, it will be created for you.
HYDROTBL_F = "./DOMAIN/hydro2dtbl.nc"

! Specify spatial metadata file for land surface grid. (e.g.: "GEOGRID_LDASOUT_Spatial_Metadata.nc")
LAND_SPATIAL_META_FLNM = "./DOMAIN/GEOGRID_LDASOUT_Spatial_Metadata.nc"

! Specify the name of the restart file if starting from restart...comment out with '!' if not...
! RESTART_FILE  = 'RESTART/HYDRO_RST.2011-08-26_00:00_DOMAIN1'

!!!! --------------------- MODEL SETUP OPTIONS -------------------- !!!!

! Specify the domain or nest number identifier...(integer)
IGRID = 1

! Specify the restart file write frequency...(minutes)
! A value of -99999 will output restarts on the first day of the month only.
rst_dt = {self.rst_dt}

! Reset the LSM soil states from the high-res routing restart file (1=overwrite, 0=no overwrite)
! NOTE: Only turn this option on if overland or subsurface rotuing is active!
rst_typ = 1

! Restart file format control
rst_bi_in = 0       !0: use netcdf input restart file (default)
                    !1: use parallel io for reading multiple restart files, 1 per core
rst_bi_out = 0      !0: use netcdf output restart file (default)
                    !1: use parallel io for outputting multiple restart files, 1 per core

! Restart switch to set restart accumulation variables to 0 (0=no reset, 1=yes reset to 0.0)
RSTRT_SWC = 1

! Specify baseflow/bucket model initialization...(0=cold start from table, 1=restart file)
GW_RESTART = 1

!!!! -------------------- MODEL OUTPUT CONTROL -------------------- !!!!

! Specify the output file write frequency...(minutes)
out_dt = 60

! Specify the number of output times to be contained within each output history file...(integer)
!   SET = 1 WHEN RUNNING CHANNEL ROUTING ONLY/CALIBRATION SIMS!!!
!   SET = 1 WHEN RUNNING COUPLED TO WRF!!!
SPLIT_OUTPUT_COUNT = 1

! Specify the minimum stream order to output to netcdf point file...(integer)
! Note: lower value of stream order produces more output.
order_to_write = 1

! Flag to turn on/off new I/O routines: 0 = deprecated output routines (use when running with Noah LSM),
! 1 = with scale/offset/compression, ! 2 = with scale/offset/NO compression,
! 3 = compression only, 4 = no scale/offset/compression (default)
io_form_outputs = 4

! Realtime run configuration option:
! 0=all (default), 1=analysis, 2=short-range, 3=medium-range, 4=long-range, 5=retrospective,
! 6=diagnostic (includes all of 1-4 outputs combined)
io_config_outputs = 5

! Option to write output files at time 0 (restart cold start time): 0=no, 1=yes (default)
t0OutputFlag = 1

! Options to output channel & bucket influxes. Only active for UDMP_OPT=1.
! Nonzero choice requires that out_dt above matches NOAH_TIMESTEP in namelist.hrldas.
! 0=None (default), 1=channel influxes (qSfcLatRunoff, qBucket)
! 2=channel+bucket fluxes    (qSfcLatRunoff, qBucket, qBtmVertRunoff_toBucket)
! 3=channel accumulations    (accSfcLatRunoff, accBucket) *** NOT TESTED ***
output_channelBucket_influx = 0

! Output netcdf file control
CHRTOUT_DOMAIN = {self.CHRTOUT_DOMAIN}            ! Netcdf point timeseries output at all channel points (1d)
                                                 !      0 = no output, 1 = output
CHANOBS_DOMAIN = {self.CHANOBS_DOMAIN}           ! Netcdf point timeseries at forecast points or gage points (defined in Routelink)
                                                 !      0 = no output, 1 = output at forecast points or gage points.
CHRTOUT_GRID = {self.CHRTOUT_GRID}               ! Netcdf grid of channel streamflow values (2d)
                                                 !      0 = no output, 1 = output
                                                 !      NOTE: Not available with reach-based routing
LSMOUT_DOMAIN = {self.LSMOUT_DOMAIN}             ! Netcdf grid of variables passed between LSM and routing components (2d)
                                                 !      0 = no output, 1 = output
                                                 !      NOTE: No scale_factor/add_offset available
RTOUT_DOMAIN = {self.RTOUT_DOMAIN}               ! Netcdf grid of terrain routing variables on routing grid (2d)
                                                 !      0 = no output, 1 = output
output_gw = {self.output_gw}                     ! Netcdf GW output
                                                 !      0 = no output, 1 = output
outlake  = {self.outlake}                        ! Netcdf grid of lake values (1d)
                                                 !      0 = no output, 1 = output
frxst_pts_out = {self.frxst_pts_out}             ! ASCII text file of forecast points or gage points (defined in Routelink)
                                                 !      0 = no output, 1 = output

!!!! ------------ PHYSICS OPTIONS AND RELATED SETTINGS ------------ !!!!

! Specify the number of soil layers (integer) and the depth of the bottom of each layer... (meters)
! Notes: In Version 1 of WRF-Hydro these must be the same as in the namelist.input file.
!      Future versions will permit this to be different.
NSOIL=4
ZSOIL8(1) = -0.10
ZSOIL8(2) = -0.40
ZSOIL8(3) = -1.00
ZSOIL8(4) = -2.00

! Specify the grid spacing of the terrain routing grid...(meters)
DXRT = {self.DXRT}

! Specify the integer multiple between the land model grid and the terrain routing grid...(integer)
AGGFACTRT = {self.AGGFACTRT}

! Specify the channel routing model timestep...(seconds)
DTRT_CH = {self.DTRT_CH}

! Specify the terrain routing model timestep...(seconds)
DTRT_TER = {self.DTRT_TER}

! Switch to activate subsurface routing...(0=no, 1=yes)
SUBRTSWCRT = 1

! Switch to activate surface overland flow routing...(0=no, 1=yes)
OVRTSWCRT = 1

! Specify overland flow routing option: 1=Seepest Descent (D8) 2=CASC2D (not active)
! NOTE: Currently subsurface flow is only steepest descent
rt_option = 1

! Specify whether to adjust overland flow parameters based on imperviousness
imperv_adj = 0

! Switch to activate channel routing...(0=no, 1=yes)
CHANRTSWCRT = 1

! Specify channel routing option: 1=Muskingam-reach, 2=Musk.-Cunge-reach, 3=Diff.Wave-gridded,
! 5=Bypass channel routing (only active for UDMP=1 and reach configuration)
channel_option = 3

! Specify the reach file for reach-based routing options (e.g.: "Route_Link.nc")
route_link_f = "./DOMAIN/Route_Link.nc"

! If using channel_option=2, activate the compound channel formulation? (Default=.FALSE.)
! This option is currently only supported if using reach-based routing with UDMP=1.
compound_channel = .FALSE.

! Switch to activate channel-loss option (0=no, 1=yes) [Requires Kchan in RouteLink]
! channel_loss_option = 0

! Lake / Reservoir options (0=lakes off, 1=level pool (typical default),
!                           2=passthrough, 3=reservoir DA [see &reservoir_nlist below])
lake_option = 0

! Specify the lake parameter file (e.g.: "LAKEPARM.nc").
! Note REQUIRED if lakes are on.
! route_lake_f = "./DOMAIN/LAKEPARM.nc"

! Switch to activate baseflow bucket model...(0=none, 1=exp. bucket, 2=pass-through,
! 4=exp. bucket with area normalized parameters)
! Option 4 is currently only supported if using reach-based routing with UDMP=1.
GWBASESWCRT = 1

! Switch to activate bucket model loss (0=no, 1=yes)
! This option is currently only supported if using reach-based routing with UDMP=1.
bucket_loss = 0

! Groundwater/baseflow 2d mask specified on land surface model grid (e.g.: "GWBASINS.nc")
! Note: Only required if baseflow  model is active (1 or 2) and UDMP_OPT=0.
gwbasmskfil = "./DOMAIN/GWBASINS.nc"

! Groundwater bucket parameter file (e.g.: "GWBUCKPARM.nc")
GWBUCKPARM_file = "./DOMAIN/GWBUCKPARM.nc"

! User defined mapping, such as NHDPlus: 0=no (default), 1=yes
UDMP_OPT = 0

! If on, specify the user-defined mapping file (e.g.: "spatialweights.nc")
!udmap_file = "./DOMAIN/spatialweights.nc"

/
"""

        # Generate the hydro.namelist file
        with open(f'{self.domain_path}/hydro.namelist', "w") as hydro_namelist_file:
            hydro_namelist_file.write(content)

    def copy_TBL_files(self):
        """
        @Definition:
            A function to copy CHANPARM.TBL, GENPARM.TBL, HYDRO.TBL, SOILPARM.TBL
            to the directory that runs simulations
        @References:
            None.
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        all_files_paths = Path(self.window_simulation_path).glob('*')
        selected_all_files_paths = [each_file_path for each_file_path in all_files_paths \
                                    if each_file_path.is_file() and each_file_path.suffix in ['.TBL', '.exe']]

        # Create the destination folder
        Path(self.domain_path).mkdir(parents=True, exist_ok=True)

        # Copy selected files
        for each_file_path in selected_all_files_paths:
            shutil.copy2(
                str(Path(each_file_path)),
                str(Path(self.domain_path) / Path(each_file_path).name)
            )

    def convert_window_to_wsl_path(self):
        """
        @Definition:
            A function to convert window path to Window-Subsystem-for-Linux path
        @References:
            https://pypi.org/project/wsl-path-converter/ (NOT USE HERE)
        @Arguments:
            Already defined above.
        @Returns:
            A Window-Subsystem-for-Linux path
        """
        # Convert to Path object
        path_object = Path(self.domain_path)

        # Extract and lowercase the drive letter
        drive_letter = path_object.drive.rstrip(":").lower()

        # Replace backslashes in the rest of the path with forward slashes
        unix_part = str(path_object)[len(path_object.drive):].replace("\\", "/")

        # Join with /mnt/
        return f"/mnt/{drive_letter}{unix_part}"

    def generate_simulation_commands(self, command_notes, log_name):
        """
        @Definition:
            A function to design common commands to generate domain files
        @References:
            https://stackoverflow.com/questions/57693460/using-wsl-bash-from-within-python
            https://stackoverflow.com/questions/78219632/run-a-linux-application-on-wsl-from-a-windows-python-script
            https://forum.freecad.org/viewtopic.php?t=91659
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        # Full command notes that change the directory into the wsl_path
        # and are executed to obtain the results
        command_execution = f"cd {self.convert_window_to_wsl_path()} && {command_notes}"

        # Execute the full command in Window Subsystem for Linux (WSL)
        # Explanation:
        # - ["wsl", "bash", "-c", command]: The command list to run in the shell.
        #   * "wsl": Calls the WSL subsystem (to run Linux commands from Windows)
        #   * "bash": Runs the Bash shell inside WSL.
        #   * "-c": Tells Bash to execute the string following it as a command.
        #   * command: A string containing the actual Linux command you want to run
        #              (e.g., "ls -la" or "./geogrid.exe")
        # - stdout=subprocess.PIPE: To capture the standard output (anything the command prints normally)
        # - stderr=subprocess.PIPE: To capture the standard error (error messages from the command)
        # - text=True: Tells python to return output as strings (not bytes)
        result = subprocess.run(
            ["wsl", "bash", "-c", command_execution],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Print out log file after generating geo_em netcdf file
        with open(fr"{self.domain_path}\{log_name}.log", "w") as f:
            f.write("*** RETURNCODE ***\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write("*** STDOUT ***\n")
            f.write(result.stdout)
            f.write("*** STDERR ***\n")
            f.write(result.stderr)

    def generate_simulation_files(self):
        """
        @Definition:
            A function to run WRF-Hydro simulation
        @References:
            https://wrf-hydro.readthedocs.io/en/latest/appendices.html
            https://ral.ucar.edu/sites/default/files/public/HowToBuildandRunWRF-HydroV5inStandaloneMode_0.pdf
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        # Define command notes and log name
        command_notes = r"mpirun -np 2 ./wrf_hydro_NoahMP.exe >> run.log 2>&1"
        log_name = "simulation_result"

        # Run geogrid.exe
        self.generate_simulation_commands(command_notes, log_name)

    def move_files(self):
        """
        @Definition:
            A function to move all generated simulation files into the save path
        @References:
            https://stackoverflow.com/questions/39909655/listing-of-all-files-in-directory
            https://stackoverflow.com/questions/8858008/how-do-i-move-a-file-in-python
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """
        # List all necessary prefix and suffix
        prefix = [
            'diag_hydro', 'frxst_pts_out', 'HYDRO_RST',
            'RESTART', 'run', 'simulation_result'
        ]
        suffix = [
            '.CHANOBS_DOMAIN1', '.CHRTOUT_DOMAIN1', '.CHRTOUT_GRID1',
            '.GWOUT_DOMAIN1', '.LDASOUT_DOMAIN1', '.LSMOUT_DOMAIN1',
            '.RTOUT_DOMAIN1'
        ]

        # Select necessary simulated results to put into simulations folder
        all_files_paths = Path(self.domain_path).glob('*')
        selected_all_files_paths = [each_file_path for each_file_path in all_files_paths \
                                    if each_file_path.is_file() \
                                    and each_file_path.stem in prefix \
                                    or each_file_path.suffix in suffix]

        # Create the simulation folder
        simulations_path = f"{self.domain_path}\simulations"
        Path(simulations_path).mkdir(parents=True, exist_ok=True)

        # Move selected files
        for each_file_path in selected_all_files_paths:
            shutil.move(
                str(Path(each_file_path)),
                str(Path(simulations_path) / Path(each_file_path).name)
            )

    def execute_simulation_commands(self):
        """
        @Definition:
            A function to run WRF-Hydro simulation
        @References:
            None.
        @Arguments:
            Already defined above.
        @Returns:
            None.
        """

        # Generate namelist.hrldas
        self.generate_namelist_hrldas()

        # Generate hydro.namelist
        self.generate_hydro_namelist()

        # Copy all TBL to domain files
        self.copy_TBL_files()

        # Generate simulation files
        self.generate_simulation_files()

        # Copy all simulated results to
        self.move_files()

# EXAMPLES
# simulation = generateWRFHydroSimulation(
#     # Paths
#     r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003",
#
#     # namelist.hrldas
#     [2020, 2, 29, 1, 0],
#     2,
#     1,
#
#     # hydro.namelist
#     50, 4,
#     90, 120,
#     300,
#     1,
#     1,
#     1,
#     1,
#     1,
#     1,
#     0,
#     1
# )
#
# simulation.execute_simulation_commands()