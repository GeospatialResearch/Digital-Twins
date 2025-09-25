"""Runs to generate Routing Stack files"""
# Necessary packages
from pathlib import Path
import subprocess
import zipfile


# Develop a class to generate routing stack
class GenerateRouting:
    """A class to generate files that describe the routing"""

    def __init__(
            self,
            domain_path: str,
            regridding_routing_factor: int,
            minimum_basin_area_threshold: int
    ) -> None:
        """
        Definition:
            Init function to state common arguments
        References:
            https://github.com/NCAR/wrf_hydro_training/blob/main/lessons/training/Lesson-S2-GIS-pre-processing.ipynb
        Arguments:
            domain_path (str):
                A path that stores the domain files, especially the geo_em.d0x.nc
            regridding_routing_factor (int):
                Regridding factor for routing – defines how many smaller routing grid cells fit inside
                one land surface model (LSM) grid cell.
                It resizes the grid to connect the LSM to the routing model.
            minimum_basin_area_threshold (int):
                Minimum basin area threshold (in routing grid cells)
        """
        # A Window path where the Python script Build_Routing_Stack.py, wrfhydro_functions.py,
        # Create_Domain_Boundary_Shapefile.py, Create_SoilProperties_and_Hydro2D.py,
        # Examine_Outputs_of_GIS_Preprocessor.py, and Forecast_Point_Tools.py are located
        # [CHANGE INTO DIGITAL TWIN PATH - THIS SHOULD BE FIXED]
        self.window_routing_path = r"S:\FloodRiskResearch\Martin\WRF-Hydro\WRFHYDRO_preprocessing_tools"

        # Define variables
        self.domain_path = domain_path
        self.regridding_routing_factor = regridding_routing_factor
        self.minimum_basin_area_threshold = minimum_basin_area_threshold

    def generate_routing_commands(
            self,
            command_notes: int,
            log_name: int
    ) -> None:
        """
        Definition:
            A function to design common commands to generate and check routing stack files
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
        # Execute the command in Windows (could use Anaconda Prompt)
        #   * command: A string containing the command to generate or check the routing stack files
        #   * stdout=subprocess.PIPE: To capture the standard output (anything the command prints normally)
        #   * stderr=subprocess.PIPE: To capture the standard error (error messages from the command)
        #   * text=True: Tells python to return output as strings (not bytes)
        result = subprocess.run(
            command_notes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        # Print out log file after generating geo_em netcdf file
        with open(fr"{self.domain_path}\{log_name}.log", "w", encoding="utf-8") as f:
            f.write("*** RETURNCODE ***\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write("*** STDOUT ***\n")
            f.write(result.stdout)
            f.write("*** STDERR ***\n")
            f.write(result.stderr)

    def generate_routing_file(self) -> None:
        """
        Definition:
            A function to generate routing stack
        References:
            None.
        Arguments:
            Already defined above.
        """
        # Define command notes and log name
        command_notes = [
            "python", fr"{self.window_routing_path}\Build_Routing_Stack.py",
            "-i", fr"{self.domain_path}\geo_em.d01.nc",
            "--CSV", fr"{self.domain_path}\mataura_frxst_pts_csv.csv",
            "-r", "True",
            "-d", fr"{self.domain_path}\mataura_4326_merged.tif",
            "-R", f"{self.regridding_routing_factor}",
            "-t", f"{self.minimum_basin_area_threshold}",
            "-o", fr"{self.domain_path}\routing.zip"
        ]
        log_name = "routing_zip"

        # Run the Python script Build_Routing_Stack.py
        self.generate_routing_commands(command_notes, log_name)

    def unzip_routing_file(self) -> None:
        """
        Definition:
            A function to unzip the routing.zip
        References:
            https://stackoverflow.com/questions/3451111/unzipping-files-in-python
        Arguments:
            Already defined above.
        """
        # Create a path to extract the routing zip file to
        extract_to = str(Path(self.domain_path) / "DOMAIN")
        Path(extract_to).mkdir(parents=True, exist_ok=True)

        # Unzip routing zip file
        with zipfile.ZipFile(fr"{self.domain_path}\routing.zip", "r") as zip_ref:
            zip_ref.extractall(extract_to)

    def execute_routing_commands(self) -> None:
        """
        Definition:
            A function to execute the function to generate the routing.zip
        References:
            None.
        Arguments:
            Already defined above.
        """
        # Generate routing zipped file
        self.generate_routing_file()

        # Unzip the routing file
        self.unzip_routing_file()


# EXAMPLE
# routing_results = generateRouting(
#     r"C:\Users\mng42\wrf_wps\wrf_hydro_inputs\simulation_mataura_50m_002\run_003",
#     4,
#     2000
# )
#
# routing_results.execute_routing_commands()
