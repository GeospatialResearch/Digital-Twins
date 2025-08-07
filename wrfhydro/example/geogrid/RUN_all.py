# THIS IS JUST A SAMPLE OF RUN_ALL

# Reference: https://stackoverflow.com/questions/15514593/importerror-no-module-named-when-trying-to-run-python-script/15622021#15622021
# Here choosing the folder that stores all the modules
import sys
sys.path.append(r'C:\Users\mng42\wrf_wps\wrf_hydro_simulation')

# Necessary packages
from domainFiles import generateDomainFiles
from routingStack import generateRouting
from forcingDataset import generateERA5Forcing
from WRFHydroSimulation import generateWRFHydroSimulation
from simulatedResultManipulation import resultManipulation

# State variables
# Generate domain files
domain_files = generateDomainFiles(
    400, 800,
    -45.907, 168.8,
    200, 200,
    r'/mnt/s/FloodRiskResearch/Martin/WRF-Hydro/WRFdata/WPS_GEOG',
    r'S:\FloodRiskResearch\Martin\WRF-Hydro\wrfhydro_mataura_002'
)

# Generate routing stack
routing_files = generateRouting(
    r"S:\FloodRiskResearch\Martin\WRF-Hydro\wrfhydro_mataura_002",
    4,
    2000
)

# Download and convert ERA5 variables into WRF-Hydro forcing data
forcing_files = generateERA5Forcing(
    r"S:\FloodRiskResearch\Martin\WRF-Hydro\wrfhydro_mataura_002",
    r"Y:\Temporary\ERA_003",
    [2020, 2, 29, 1],
    [2020, 2, 29, 3]
)

# Generate WRF-Hydro simulations
simulation_files = generateWRFHydroSimulation(
    # Paths
    r"S:\FloodRiskResearch\Martin\WRF-Hydro\wrfhydro_mataura_002",

    # namelist.hrldas
    [2020, 2, 29, 1, 0],
    2,
    1,

    # hydro.namelist
    50, 4,
    90, 120,
    300,
    1,
    1,
    1,
    1,
    1,
    1,
    0,
    1
)

# Manipulate simulated results
result_simulation_files = resultManipulation(
    r"S:\FloodRiskResearch\Martin\WRF-Hydro\wrfhydro_mataura_002"
)

# Execute commands
domain_files.execute_domain_commands()
print("DONE domain files")
routing_files.execute_routing_commands()
print("DONE routing files")
forcing_files.execute_download_and_convert_commands()
print("DONE forcing files")
simulation_files.execute_simulation_commands()
print("DONE simulation files")
result_simulation_files.execute_write_out_commands()
print("DONE result simulation files")