def run_create_domain_boundary_shapefile(
        file_path,
        geogrid_file,
        output_file
):

    executable_command = [
        "python", file_path,
        "-i", geogrid_file,
        "-o", output_file
    ]

    with open(log_file, "w") as log:
        subprocess.run(executable_command, stdout=log, stderr=subprocess.STDOUT, check=True)


def run_Forecast_Point_Tools(
        file_path,
        geogrid_file,
        gauge_file,
        output_file
):

    executable_command = [
        "python", file_path,
        "-i", geogrid_file,
        "-s", gauge_file,
        "-o", output_file
    ]

    with open(log_file, "w") as log:
        subprocess.run(executable_command, stdout=log, stderr=subprocess.STDOUT, check=True)


def run_build_routing_stack(
        file_path,
        geogrid_file,
        burn_channel_grids,
        reach,
        dem_file,
        regridding_factor,
        minimum_threshold,
        output_file
):

    executable_command = [
        "python", file_path,
        "-i", geogrid_file,
        "-b", burn_channel_grids,
        "-r", reach,
        "-d", dem_file,
        "-R", regridding_factor,
        "-t", minimum_threshold,
        "-o", output_file
    ]

    with open(log_file, "w") as log:
        subprocess.run(executable_command, stdout=log, stderr=subprocess.STDOUT, check=True)


def run_examine_outputs_of_GIS_preprocessor(
        file_path,
        geogrid_file,
        output_file

    ):

    executable_command = [
    "python", file_path,
    "-i", geogrid_file,
    "-o", output_file
    ]

    with open(log_file, "w") as log:
        subprocess.run(executable_command, stdout=log, stderr=subprocess.STDOUT, check=True)