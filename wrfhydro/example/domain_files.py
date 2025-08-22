"""Runs to generate domain files which are inputs for WRF-Hydro"""
# pylint: disable=too-many-instance-attributes

# Necessary packages
from pathlib import Path
import subprocess
import shutil


# Develop a class to generate domain files
class GenerateDomainFiles:
    """
    A class to generate domain files, which mainly includes:
        - geo_em.d01.nc:
                Static geographical data for a specific model domain
        - soil_properties.nc:
                Provides spatially distributed soil parameters for the land surface model (Noah-MP LSM)
        - hydro2dtbl.nc:
                Spatially distributed netCDF version of HYDRO.TBL (parameter table for lateral flow routing)
        - wrfinput_d01.nc:
                Describe initial conditions for the land surface,
                such as soil moisture, soil temperature, and snow states
    """

    def __init__(
            self,
            e_we: int,
            e_sn: int,
            ref_lat: float,
            ref_lon: float,
            dx: int,
            dy: int,
            geog_data_path: str,
            save_path: str,
            max_dom: int = 1,
            geog_data_res: str = 'default'
    ) -> None:
        """
        Definition:
            Init function to state common arguments
        References:
            https://wrf-hydro.readthedocs.io/en/readthedocs/model-inputs-preproc.html
        Arguments:
            e_we, e_sn (int):
                Extents in west-east (e_we) and south-north (e_sn) directions.
            ref_lat, ref_lon (float):
                The centroid - center of the domain. They should be in degree.
            dx, dy (int):
                The resolution of the domain or domain grid spacing (in meters).
            save_path (str):
                A directory to the folder that will store all the domain files.
            geog_data_res (str):
                A string that defines data resolution when interpolating static terrestrial data.
                Default is MODIS IGBP 21-category or "default".
            geog_data_path (str):
                A directory to the folder that stores static terrestrial data
            max_dom (int):
                Number of domains. Default is 1.
            geog_data_res (str):
                A string that defines data resolution when interpolating static terrestrial data.
                Default is MODIS IGBP 21-category or "default".
        """
        # A Window path where geogrid folder, create_soilproperties.R, create_wrfinput.R,
        # CHANPARM.TBL, GENPARM.TBL, HYDRO.TBL, MPTABLE.TBL, and SOILPARM.TBL are located
        # [CHANGE INTO DIGITAL TWIN PATH - THIS SHOULD BE FIXED]
        self.window_geogrid_path = r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\geogrid"

        # Define variables
        self.e_we = e_we
        self.e_sn = e_sn
        self.ref_lat = ref_lat
        self.ref_lon = ref_lon
        self.dx = dx
        self.dy = dy
        self.geog_data_path = geog_data_path
        self.save_path = save_path
        self.max_dom = max_dom
        self.geog_data_res = geog_data_res

    def convert_window_to_wsl_path(self) -> str:
        """
        Definition:
            A function to convert window path to Window-Subsystem-for-Linux path
        References:
            https://pypi.org/project/wsl-path-converter/ (NOT USE HERE)
        Arguments:
            Already defined above.
        Returns:
            A Window-Subsystem-for-Linux path
        """
        # Convert to Path object and resolve to absolute
        path_object = Path(self.window_geogrid_path).resolve()

        # Extract and lowercase the drive letter
        drive_letter = path_object.drive.rstrip(":").lower()

        # Replace backslashes in the rest of the path with forward slashes
        unix_part = str(path_object)[len(path_object.drive):].replace("\\", "/")

        # Join with /mnt/
        return f"/mnt/{drive_letter}{unix_part}"

    def generate_namelist_wps(self) -> str:
        """
        Definition:
            A function to generate namelist.wps to run geogrid.exe to generate static geographical data
        References:
            https://www2.mmm.ucar.edu/wrf/users/namelist_best_prac_wps.html
            http://140.112.69.65/research/coawst/COAWST_TUTORIAL/training_2019/monday/werner_wps.pdf
        Arguments:
            Already defined above.
        """
        # Calculate truelat1, truelat2, and stand_lon
        # The truelat1 and truelat2 defines where the cone slices the globe.
        # The stand_lon defines the central meridian of the projection,
        # where the longitude = 0 in the projected coordinate system.
        # It is not distorted by the projection.
        # For New Zealand catchments, we choose to set them as below
        truelat1 = self.ref_lat - 5
        truelat2 = self.ref_lat + 5
        stand_lon = self.ref_lon

        # Content of namelist.wps where the domain information is defined
        content = f"""&share

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!  Specify the number of domains
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

max_dom = {self.max_dom},

/

&geogrid

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! Define the extend in west-east (e_we) and south-north (e_sn) directions
!  Note: will create a domain of size (e_we-1) x (e_sn-1)
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

e_we              =  {self.e_we},
e_sn              =  {self.e_sn},

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! Define the center point of your domain
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

ref_lat   =  {self.ref_lat}
ref_lon   =  {self.ref_lon}

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! Define the domain grid spacing (in meters)
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

dx = {self.dx},
dy = {self.dy},

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! Define the map projection
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

map_proj  = 'lambert',
truelat1  = {truelat1},
truelat2  = {truelat2},
stand_lon = {stand_lon},

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
! Define the data sources and data path
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

geog_data_res  = '{self.geog_data_res}',
geog_data_path = '{self.geog_data_path}'

/
"""
        # Generate the namelist.wps file
        with open(f'{self.window_geogrid_path}/namelist.wps', "w", encoding="utf-8") as namelist_wps_file:
            namelist_wps_file.write(content)

    def generate_domain_commands(
            self,
            command_notes: str,
            log_name: str
    ) -> None:
        """
        Definition:
            A function to design common commands to generate domain files
        References:
            https://stackoverflow.com/questions/57693460/using-wsl-bash-from-within-python
            https://stackoverflow.com/questions/78219632/run-a-linux-application-on-wsl-from-a-windows-python-script
            https://forum.freecad.org/viewtopic.php?t=91659
        Arguments:
            command_notes (str):
                A command to be executed in WSL
            log_name (str):
                A name of the log file
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
            text=True,
            check=True
        )

        # Print out log file after generating geo_em netcdf file
        with open(fr"{self.window_geogrid_path}\{log_name}.log", "w", encoding="utf-8") as f:
            f.write("*** RETURNCODE ***\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write("*** STDOUT ***\n")
            f.write(result.stdout)
            f.write("*** STDERR ***\n")
            f.write(result.stderr)

    def generate_geogrid_files(self) -> None:
        """
        Definition:
            A function to run geogrid.exe and generate geo_em.d0x.nc file
        References:
            https://wrf-hydro.readthedocs.io/en/latest/appendices.html
            https://ral.ucar.edu/sites/default/files/public/HowToBuildandRunWRF-HydroV5inStandaloneMode_0.pdf
        Arguments:
            Already defined above.
        """
        # Define command notes and log name
        command_notes = r"./geogrid/geogrid.exe"
        log_name = "geogrid_result"

        # Run geogrid.exe
        self.generate_domain_commands(command_notes, log_name)

    def generate_soilproperties_hydro2dtbl_files(self) -> None:
        """
        Definition:
            A function to run Rscript create_soilproperties.R to generate soil parameters
        References:
            https://ral.ucar.edu/projects/wrf_hydro/pre-processing-tools
            https://wrf-hydro.readthedocs.io/en/readthedocs/model-inputs-preproc.html
        Arguments:
            Already defined above.
        """
        # Define command notes and log name
        command_notes = "Rscript create_soilproperties.R --geogrid=geo_em.d01.nc --outfile=soil_properties.nc"
        log_name = "soilproperties_hydro2dtbl_result"

        # Run Rscript create_soilproperties.R
        self.generate_domain_commands(command_notes, log_name)

    def generate_wrfinput_files(self) -> None:
        """
        Definition:
            A function to run Rscript create_wrfinput.R to generate initial conditions for land
        References:
            https://ral.ucar.edu/projects/wrf_hydro/pre-processing-tools
            https://wrf-hydro.readthedocs.io/en/readthedocs/model-inputs-preproc.html
        Arguments:
            Already defined above.
        """
        # Define command notes and log name
        command_notes = "Rscript create_wrfinput.R --geogrid=geo_em.d01.nc --outfile=wrfinput_d01.nc"
        log_name = "wrfinput_result"

        # Run Rscript create_wrfinput.R
        self.generate_domain_commands(command_notes, log_name)

    def copy_files(self) -> None:
        """
        Definition:
            A function to copy all generated domain files into the save path
        References:
            None.
        Arguments:
            Already defined above.
        """
        all_files_paths = Path(self.window_geogrid_path).glob('*')
        selected_all_files_paths = [each_file_path for each_file_path in all_files_paths
                                    if each_file_path.is_file() and each_file_path.suffix == '.nc']

        # Create the destination folder
        domain_path = fr"{self.save_path}\DOMAIN"
        Path(domain_path).mkdir(parents=True, exist_ok=True)

        # Move selected files
        for each_file_path in selected_all_files_paths:
            source_path = Path(each_file_path)
            shutil.copy2(
                str(source_path),
                str(Path(domain_path) / source_path.name)
            )

    def move_files(self) -> None:
        """
        Definition:
            A function to move all generated domain files into the save path
        References:
            https://stackoverflow.com/questions/39909655/listing-of-all-files-in-directory
            https://stackoverflow.com/questions/8858008/how-do-i-move-a-file-in-python
        Arguments:
            Already defined above.
        """
        all_files_paths = Path(self.window_geogrid_path).glob('*')
        selected_all_files_paths = [each_file_path for each_file_path in all_files_paths
                                    if each_file_path.is_file() and each_file_path.suffix in ['.wps', '.nc', '.log']]

        # Create the destination folder
        Path(self.save_path).mkdir(parents=True, exist_ok=True)

        # Move selected files
        for each_file_path in selected_all_files_paths:
            source_path = Path(each_file_path)
            shutil.move(
                str(source_path),
                str(Path(self.save_path) / source_path.name)
            )

    def execute_domain_commands(self) -> None:
        """
        Definition:
            A function to generate domain files
        References:
            None.
        Arguments:
            Already defined above.
        """
        # Generate namelist.wps
        self.generate_namelist_wps()

        # Generate geogrid files
        self.generate_geogrid_files()

        # Generate soilproperties and hydro2dtbl files
        self.generate_soilproperties_hydro2dtbl_files()

        # Generate wrfinput files
        self.generate_wrfinput_files()

        # Copy all generated domain files to the domain path
        self.copy_files()

        # Move all generated domain files to the save path
        self.move_files()

# EXAMPLES
# domain_files = generateDomainFiles(
#     400, 800,
#     -45.907, 168.8,
#     200, 200,
#     r'/mnt/s/FloodRiskResearch/Martin/WRF-Hydro/WRFdata/WPS_GEOG',
#     r'C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003'
# )
#
# domain_files.execute_domain_commands()
