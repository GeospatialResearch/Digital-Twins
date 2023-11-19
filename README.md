# Flood Resilience Digital Twin (FReDT)
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

Data is collected from an open data portal provided by multiple organisations or data providers such as LINZ, LRIS - MWLR, StatsNZ, ECAN, opentopography, NIWA, MFE, and more.
The collected data is stored in the application database using PostgreSQL

The reason for implementing a database are:
1.  Reusing data that has been processed by the digital twin that may have taken a long time to process 
1.	Avoid unnecessary network overhead on the data providers
1.	To avoid delays in fetching the same data from the API when required again and again to run the models.


## Basic running instructions
The following list defines the basic steps required to setup and run the digital twin.

## Requirements
* [Docker](https://www.docker.com/)
* [Anaconda](https://www.anaconda.com/download)
* [Node.js / NPM](https://nodejs.org/)

## Required Credentials:
Create API keys for each of these services. You may need to create an account and log in
* [Stats NZ API Key](https://datafinder.stats.govt.nz/my/api/)
* [LINZ API Key](https://data.linz.govt.nz/my/api/)
* [MFE API Key](https://data.mfe.govt.nz/my/api/)
* [NIWA Application API Key](https://developer.niwa.co.nz/) - Create an app that has the Tide API enabled  
* [Cesium access token](https://cesium.com/ion/tokens)

## Starting the Digital Twin application (localhost)
1. Set up Docker, Anaconda, and NPM to work on your system.

1. Clone this repository to your local machine (may be best to avoid network drives for software development since they are much slower)

1. In the project root, in an Anaconda prompt, run the following commands to initialise the environment:
   ```bash
   #!/usr/bin/env bash
   conda env create -f environment.yml
   conda activate digitaltwin
   ```
   _While the environment is being created, you can continue with the other steps until using the environment._
   
1. Create a file called `.env` in the project root, copy the contents of `.env.template` and fill in all blank fields unless a comment says you can leave it blank.
   
1. Set any file paths in `.env` if needed, for example `FLOOD_MODEL_DIR` references a Geospatial Research Institute
   network drive, so you may need to provide your own implementation of `BG_flood` here.  
   Multiple instances of the digital twin can point to the same directories and share the cached data to improve speed.
    
1. Create a file `visualisation/.env.local`. In this, fill in 
   `VUE_APP_CESIUM_ACCESS_TOKEN=[your_token_here]`, replace `[your_token_here]` with the Cesium Access Token
    
1. From project root, run the command `docker-compose up --build -d` to run the database, backend web servers, and helper services.  
**If this fails on a WindowsToastNotification error on windows, just run it again and it should work.**
   
1. Currently, the `visualisation` and `celery_worker` services are not set up to work with Docker, so these will be set up manually.
   1. In one terminal, with the conda environment activated, go to the project root directory and run `celery -A src.tasks worker --loglevel=INFO --pool=solo` to run the backend celery service.
   1. In another terminal open the `visualisation` directory and run `npm ci && npm run serve` to start the development visualisation server.

1. You may inspect the logs of the backend in the celery window.
   
1. You may inspect the PostgreSQL database by logging in using the credentials you stored in the `.env` file and a database client such as `psql` or pgAdmin or DBeaver or PyCharm Professional.

## Using the Digital Twin application
1. With the visualisation server running, visit the address shown in the visualisation server window, default [http://localhost:8080](http://localhost:8080)
1. To run a flood model, hold SHIFT and hold the left mouse button to drag a box around the area you wish to run the model for.
1. Once the model has completed running, you may need to click the button at the bottom of the screen requesting you to reload the flood model.
1. To see a graph for flood depths over time at a location, hold CTRL and click the left mouse button on the area you wish to query.
<br>

## Setup for developers

### Run single Docker service e.g. database
To run only one isolated service (services defined in `docker-compose.yml`) use the following command:
`docker-compose up --build [-d] [SERVICES]`

e.g. To run only the database in detached mode:
```bash
#!/usr/bin/env bash
docker-compose up --build -d db_postgres
```

### Run Celery locally (reccomended, since BG Flood does not yet work on Docker)
With the conda environment activated run:
```bash
#!/usr/bin/env bash
celery -A src.tasks worker --loglevel=INFO --pool=solo
```

### Running the backend without web interface.
It will likely be useful to run processing using the digital twin, without running the web interface.
To do so:
1. Run `db_postgres` and `geoserver` services in docker.
```bash
#!/usr/bin/env bash
docker-compose up --build -d db_postgres geoserver
```
2. 

For local testing, it may be useful to use the `src.run_all.py` script to run the processing.

<br>

## Tests
Tests exist in the `tests/` folder.

### Automated testing
[Github Actions](https://docs.github.com/en/actions) are used to run tests after each push to remote (i.e. github). [Miniconda](https://github.com/marketplace/actions/setup-miniconda) from the GitHub Actions marketplace is used to install the package dependencies. Linting with [Flake8](https://github.com/py-actions/flake8) and testing with [PyTest](https://docs.pytest.org/en/6.2.x/contents.html) is then performed. Several tests require an API key. This is stored as a GitHub secret and accessed by the workflow.



## Raster Database

Hydrologically-conditioned Digital Elevation Models (DEMs) are generated using [NewZeaLiDAR](https://github.com/xandercai/NewZeaLiDAR) desgined by Xander Cai at the GRI,
and [geofabrics](https://github.com/rosepearson/GeoFabrics ) designed by NIWA which downloads the LiDAR data from 
[opentopography](https://portal.opentopography.org/dataCatalog ) and generates . 

The objective of NewZeaLiDAR is to store the metadata of the generated DEM in the database for the requested catchment area.
Storing these details in the database helps in getting the DEM already generated using geofabrics rather than generating DEM for the same catchment, again and again, saving time and resources.

The hydrologically-conditioned DEM is used to run the Flood model (BG Flood model)[https://github.com/CyprienBosserelle/BG_Flood )] designed by NIWA.

