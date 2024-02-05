# Flood Resilience Digital Twin (FReDT)
![image](https://github.com/GeospatialResearch/Digital-Twins/assets/41398636/b7b9da6c-3895-46f5-99dc-4094003b2946)


## Introduction

According to the National Emergency Management Agency, flooding is the greatest hazard in New Zealand, in terms of frequency, losses and civil defence emergencies. 
With major flood events occurring on average every 8 months [(New Zealand – FloodList)](https://floodlist.com/tag/new-zealand),
it is necessary to produce high precision flood models and in order to do better planning, risk assessment and response to flood events,
making plans in advance can make all the difference, not just to property owners at risks,
it will also help insurance companies who make underwriting decisions on properties,
the banks supplying the property finance, the telecommunications and utilities companies providing vital services to homes and offices,
and the government agencies tasked with protecting communities and their assets.

The Flood Resilience Digital Twin can provide a better understanding of the degree of impact flood events can have on physical assets like buildings, roads, railways, transmission lines, etc.
Digital Twin not only represents the current status of the visualised assets but also how they will perform/react to future situations. 
The build twin when used to run flood models combined with other sources of information can allow us to make predictions.

Data is collected from open data portals provided by multiple organisations or data providers such as LINZ, StatsNZ, opentopography, NIWA, MFE, and more.
The collected data is stored in the application database using PostgreSQL

The reason for implementing a database are:
1.  Reusing data that has been processed by the digital twin that may have taken a long time to process 
1.	Avoid unnecessary network overhead on the data providers
1.	To avoid delays in fetching the same data from the API when required again and again to run the models.


## Basic running instructions
The following list defines the basic steps required to setup and run the digital twin.


## Requirements
* [Docker](https://www.docker.com/)


## Required Credentials:
Create API keys for each of these services. You may need to create an account and log in
* [Stats NZ API Key](https://datafinder.stats.govt.nz/my/api/)
* [LINZ API Key](https://data.linz.govt.nz/my/api/)
* [MFE API Key](https://data.mfe.govt.nz/my/api/)
* [NIWA Application API Key](https://developer.niwa.co.nz/) - Create an app that has the Tide API enabled


## Starting the Digital Twin application (localhost)
1. Clone this repository to your local machine.
   
1. Create a file called `.env` in the project root, copy the contents of `.env.template` and fill in all blank fields unless a comment says you can leave it blank.
Blank fields to fill in include things like the `POSTGRES_PASSWORD` variable and `CESIUM_ACCESS_TOKEN`. You may configure other variables as needed.
   
1. Configure `DATA_DIRx` variables in `.env` such that they point to real directories accessible to your file system.
   We have these mounted on UC network drives, so we can share lidar data between FReDT instances.

1. Create a file called `api_keys.env`, copy the contents of `api_keys.env.template` and fill in the blank values with API credentials.
   
1. Set any file paths in `.env` if needed. Multiple instances of the digital twin can point to the same directories and share the cached data to improve speed.
    
1. From project root, run the command `docker-compose up -d` to run the database, backend web servers, and helper services.  
**If this fails on a WindowsToastNotification error on windows, just run it again and it should work.**
   
1. You may inspect the logs of the backend using `docker-compose logs -f backend celery_worker`
   
1. You may inspect the PostgreSQL database by logging in using the credentials you stored in the `.env` file and a database client such as `psql` or pgAdmin or DBeaver or PyCharm Professional.


## Using the Digital Twin application
The current application is running only in headless mode.  Meaning, the front-end website is not active. 
To interact with the application you send calls to the REST API. Example calls are shown in api_calls.py, and they can be replicated in other http clients such as Postman.


## Setup for developers
Set up environment variables as above.

### Run single Docker service e.g. database
To run only one isolated service (services defined in `docker-compose.yml`) use the following command:
`docker-compose up --build [-d] [SERVICES]`

e.g. To run only the database in detached mode:
```bash
#!/usr/bin/env bash
docker-compose up --build -d db_postgres
```

### Run Celery locally (without docker)
With the conda environment activated run:
```bash
#!/usr/bin/env bash
celery -A src.tasks worker -P threads --loglevel=INFO
```

### Running the backend as a processing script instead of web interface
It will likely be useful to run processing using the digital twin, without running the web interface.
To do so:
1. Run `db_postgres` and `geoserver` services in docker.
```bash
#!/usr/bin/env bash
docker-compose up --build -d db_postgres geoserver
```
2. For local testing, it may be useful to use the `src.run_all.py` script to run the processing. From the project root run
`python -m src.run_all`


## Tests
Tests exist in the `tests/` folder.

### Automated testing
[Github Actions](https://docs.github.com/en/actions) are used to run tests after each push to remote (i.e. github). [Miniconda](https://github.com/marketplace/actions/setup-miniconda) from the GitHub Actions marketplace is used to install the package dependencies. Linting with [Flake8](https://github.com/py-actions/flake8) and testing with [PyTest](https://docs.pytest.org/en/6.2.x/contents.html) is then performed. Several tests require an API key. This is stored as a GitHub secret and accessed by the workflow.


## Raster Database

Hydrologically-conditioned Digital Elevation Models (DEMs) are generated using [NewZeaLiDAR](https://github.com/xandercai/NewZeaLiDAR) designed by Xander Cai at the GRI,
and [geofabrics](https://github.com/rosepearson/GeoFabrics) designed by NIWA which downloads the LiDAR data from 
[opentopography](https://portal.opentopography.org/dataCatalog).

The objective of NewZeaLiDAR is to store the metadata of the generated DEM in the database for the requested catchment area.
Storing these details in the database helps in getting the DEM already generated using geofabrics rather than generating DEM for the same catchment, again and again, saving time and resources.

The hydrologically-conditioned DEM is used to run the Flood model (BG Flood model)[https://github.com/CyprienBosserelle/BG_Flood )] designed by NIWA.

