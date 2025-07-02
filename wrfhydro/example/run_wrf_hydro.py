import subprocess

def run_wrf_hydro(executable_path="./wrf_hydro_NoahMP.exe", num_procs=2, log_file="run.log"):
    """
        Generate WRF-Hydro simulation
    """
    command = ["mpirun", "-np", str(num_procs), executable_path]

    with open(log_file, "w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)