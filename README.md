# Digital Twin for Flood Resilience in Aotearoa, New Zealand
## Introduction

According to the National Emergency Management Agency, flooding is the greatest hazard in New Zealand, in terms of frequency, losses and civil defence emergencies. With major flood events occurring on average every 8 months [(New Zealand – FloodList)](https://floodlist.com/tag/new-zealand), it is necessary to produce high precision flood models and in order to do better planning, risk assessment and response to flood events, making plans in advance can make all the difference, not just to property owners at risks, it will also help insurance companies who make underwriting decisions on properties, the banks supplying the property finance, the telecommunications and utilities companies providing vital services to homes and offices, and the government agencies tasked with protecting communities and their assets. Digital Twin can provide a better understanding of the degree of impact flood events can have on physical assets like buildings, roads, railways, transmission lines, etc.
Digital Twin is a real-time digital clone of a physical device.  Anyone looking at the digital twin can see crucial information about how the physical thing is doing out there in the real world. Digital Twin not only represents the current status of the visualised assets but also how they will perform/react to future situations. The build twin when used to run flood models combined with other sources of information can allow us to make predictions.
The first step of building a Digital Twin is data. Data is collected from an open data portal provided by multiple organisations or data providers such as LINZ, LRIS, stat NZ, ECAN, opentopography, NIWA, etc.
The collected data is stored in the local database using PostgreSQL which is an open-source relational database system and supports both SQL (relational) and JSON (non-relational) querying. PostgreSQL is a highly stable database backed by more than 20 years of development by the open-source community.
Spatial data is the primary data used for implementing the Digital Twin model. Therefore, PostgreSQL with the PostGIS extension which supports geospatial databases for geographic information systems (GIS) is the most preferable DBMS for this project. Also, it provides support for Python, C/C++ and JavaScript, the programming languages used for building Digital Twin. The spatial boundaries are currently limited to New Zealand with the potential of getting extended further.
The reason for creating a database are:
1.	Avoid unnecessary network overhead on the data providers
2.	To avoid delays in fetching the same data from the API when required again and again to run the models.
3.	To store the data only for the Area of Interest.

The Digital Twin stores API details and a local copy of data for the required Area of Interest provided by LINZ, ECAN, Stats NZ, KiwiRail, LRIS, opentopography, and NIWA in PostgreSQL.

## Basic running instructions
The following list defines the basic steps required to setup and run the digital twin.

## Requirements
* [Docker](https://www.docker.com/)
* [Anaconda](https://www.anaconda.com/download)
* [Node.js / NPM](https://nodejs.org/)

## Required Credentials:
* [Stats NZ API Key](https://datafinder.stats.govt.nz/my/api/)
* [LINZ API Key](linz.govt.nz/guidance/data-service/linz-data-service-guide/web-services/creating-api-key)
* [Cesium access token](https://cesium.com/ion/tokens)

## Starting the Digital Twin application (localhost)
1. Set up Docker, Anaconda, and NPM to work on your system.

1. In the project root, in an Anaconda prompt, run the following commands to initialise the environment:
   ```bash
   #!/usr/bin/env bash
   conda env create -f environment.yml
   conda activate digitaltwin
   ```
   _While this is running, you can continue with the other steps until using the environment._
   
1. Create a file called `.env` in the project root, copy the contents of `.env.template` and fill in all blank fields.
   
1. Set any file paths in `.env` if needed, for example `FLOOD_MODEL_DIR` references a Geospatial Research Institute
   network drive, so you may need to provide your own implementation of `BG_flood` here.
    
1. Create a file `visualisation/.env.local`. In this, fill in 
   `VUE_APP_CESIUM_ACCESS_TOKEN=[your_token_here]`, replace `[your_token_here]` with the Cesium Access Token
    
1. From project root, run the command `docker-compose up --build -d` to run the database, backend web servers, and helper services
   .
1. Currently, the `visualisation` and `celery_worker` services are not set up to work with Docker, so these will be set up manually.
   1. In one terminal, with the conda environment activated, go to the project root directory and run `celery -A src.tasks worker --loglevel=INFO --pool=solo` to run the backend celery service.
   1. In another terminal open the `visualisation` directory and run `npm ci && npm run serve` to start the development visualisation server.

1. You may inspect the logs of the backend in the celery window.
   
1. You may inspect the PostgreSQL database by logging in using the credentials you stored in the `.env` file and a database client such as `psql` or pgAdmin.

## Using the Digital Twin application
1. Visit the address shown in the visualisation server window, default [http://localhost:8080](http://localhost:8080)
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

### Create Conda environment
Setup a conda environment to allow intelligent code analysis and local development by using the following command run from the repository folder:



### Run Celery locally (reccomended, since BG Flood does not yet work on Docker)
With the conda environment activated run:
```bash
#!/usr/bin/env bash
celery -A src.tasks worker --loglevel=INFO --pool=solo
```

### Running the backend without web interface.
For local testing, it may be useful to use the `src.run_all.py` script to run the processing.

<br>

## Tests
Tests exist in the `tests/` folder.

### Automated testing
[Github Actions](https://docs.github.com/en/actions) are used to run tests after each push to remote (i.e. github). [Miniconda](https://github.com/marketplace/actions/setup-miniconda)from the GitHub Actions marketplace is used to install the package dependencies. Linting with [Flake8](https://github.com/py-actions/flake8) and testing with [PyTest](https://docs.pytest.org/en/6.2.x/contents.html) is then performed. Several tests require an API key. This is stored as a GitHub secret and accessed by the workflow.
### Running tests locally
See the [geoapis wiki testing page](https://github.com/niwa/geoapis/wiki/Testing) for instructions for setting up a .env file and running the geofabrics test.

<br>

## Vector Database
To store api details of vector data in the database,
The following inputs are required:

1. Name of the dataset e.g. 104400-lcdb-v50-land-cover, 101292-nz-building-outlines. **Note:** make sure the names are unique.
2. Name of the region which is by default set to New Zealand but can be changed to regions e.g. Canterbury, Otago, etc. (regions can be further extended to other countries in future)
3. Geometry column name of the dateset, if required. for instance, for all LDS property and ownership, street address and geodetic data the geometry column is ‘shape’. For most other layers including Hydrographic and Topographic data, the column name is 'GEOMETRY'. For more info: https://www.linz.govt.nz/data/linz-data-service/guides-and-documentation/wfs-spatial-filtering
4. Url i.e website from where the api is accessed.
5. Layer name of the dataset
6. Data provider name. For example: LINZ, LRIS, StatsNZ, etc.
For more details on the format and structure of the inputs check out [instructions_linz.json](https://github.com/GeospatialResearch/Digital-Twins/blob/get-apis-and-make-wfs-request/src/instructions_linz.json)


Run run.py file from your IDE:
1. Creating [json file](https://github.com/GeospatialResearch/Digital-Twins/blob/master/src/instructions_linz.json)
   
   ```python
   #!/usr/bin/env python
   if __name__ == "__main__":
       from src.digitaltwin import insert_api_to_table
       from src.digitaltwin import setup_environment
       engine = setup_environment.get_database()
       config.get_env_variable("StatsNZ_API_KEY")
       # create region_geometry table if it doesn't exist in the db.
       # no need to call region_geometry_table function if region_geometry table exist in the db
       insert_api_to_table.region_geometry_table(engine, Stats_NZ_KEY)

       record = input_data("src/instructions_linz.json")
       # call the function to insert record in apilinks table
       insert_api_to_table.insert_records(engine, record['data_provider'],
                                          record['source'],
                                          record['api'], record['region'],
                                          record['geometry_column'],
                                          record['url'],
                                          record['layer'])
   ```

StatsNZ Api key is only required if the region_geometry table doesn't exist in the database otherwise you can skip lines 5-9 of the above script.

This way data will be stored in the database which then will be used to make api requests for the desired Area of Interest.
geometry column's name, url and layer name are not required if the data provider is not LINZ, LRIS or StatsNZ:

To get the data from the database:

1. Make sure `.env` file has the correct information        stored in it.

2. The geometry (geopandas dataframe type) and source list (tuple data type) needs to passed as an argument to get_data_from_db() function. Check [test1.json](https://github.com/GeospatialResearch/Digital-Twins/blob/get-apis-and-make-wfs-request/src/test1.json) for more details on the format and structure of the arguments.
3. Run get_data_from_db.py file from your IDE:

   ```python
   #!/usr/bin/env python
   if __name__ == "__main__":
       from src.digitaltwin import get_data_from_apis
       from src.digitaltwin import setup_environment
       engine = setup_environment.get_database()
       # load in the instructions, get the source list and polygon from the user
       FILE_PATH = pathlib.Path().cwd() / pathlib.Path(r"P:\GRI_codes\DigitalTwin2\src\test3.json")
       with open(FILE_PATH, 'r') as file_pointer:
           instructions = json.load(file_pointer)
       source_list = tuple(instructions['source_name'])
       geometry = gpd.GeoDataFrame.from_features(instructions["features"])
       get_data_from_db(engine, geometry, source_list)
   ```

get_data_from_db module allows the user to get data from the multiple sources within the required Area of Interest from the database and if data is not available in the database for the desired area of Interest, wfs request is made from the stored APIs, data is stored in the database and spatial query is done within the database to get the data for the desired Area of Interest.
Currently data is collected from LINZ, ECAN, Stats NZ, KiwiRail, LRIS, NIWa and opentopography but will be extended to other sources.

<br>

## Raster Database

Hydrologically conditioned DEMs are generated using [geofabrics] (https://github.com/rosepearson/GeoFabrics ) designed by NIWA which downloads the LiDAR data in the local directory from [opentopography] (https://portal.opentopography.org/dataCatalog ) and generates DEM. These DEMs are stored in the local directory set by the user. The objective of the **dem_metadata_in_db.py** script is to store the metadata of the generated DEM in the database for the requested catchment area. Storing these details in the database helps in getting the DEM already generated using geofabrics rather than generating DEM for the same catchment, again and again, saving time and resources.
The stored DEM is used to run the Flood model (BG Flood model)[https://github.com/CyprienBosserelle/BG_Flood )] designed by NIWA.
The [instruction file](https://github.com/GeospatialResearch/Digital-Twins/blob/lidar_to_db/src/lidar/file.json) used to create hydrologically conditioned DEM is passed to the **get_dem_path(instruction)** function which checks if the DEM information exists in the database, if it doesn’t exist, geofabrics is used to generate the hydrologically conditioned DEM which gets stored in the local directory and the metadata of the generated DEM is stored in the database and file path of the generated DEM is returned which is then used to run the flood model.

<br>

## LiDAR Database

The data source for the LiDAR data is [opentopography]( https://portal.opentopography.org/dataCatalog). The data for the requested catchment area is downloaded using [geoapis](https://github.com/niwa/geoapis ) in the local directory set by the user. To store the LiDAR metadata in the database, **lidar_metadata_in_db.py** script is used. The [instruction file](/lidar_to_db/src/lidar/file.json ) and path to the local directory where user wants to store the LiDAR data is passed as an argument to **store_lidar_path(file_path_to_store, instruction_file) function 

## Create extensions in PostgreSQL:

1. Install Postgresql and selet PostGIS application to install along with PostgreSQL

   ![image](https://user-images.githubusercontent.com/86580534/133153382-3a5c1069-2e65-4938-933f-5c305515fc58.png)

2. Open pgAdmin 4 and set your password which will be used for connecting to PostgreSQL using Python
3. Create Database 'vector' as shown below:
4. ![image](https://user-images.githubusercontent.com/86580534/133153639-3b21aec0-1eb3-45de-8f73-b5caa5b102ee.png)          ![image](https://user-images.githubusercontent.com/86580534/137420617-705ff552-94f7-4b71-940d-1cb1a16d0719.png)
5. Within a created a database, create PostGIS extension as shown below:
   ![image](https://user-images.githubusercontent.com/86580534/133153968-0d65230f-2b5d-4686-b115-2c354f66f04e.png)          ![image](https://user-images.githubusercontent.com/86580534/133154073-4e1702f8-866c-45a3-a8aa-4c1a505cf9b4.png)
5. Once the extension is created, spatial_ref_sys table will appear under tables as shown below:
   ![image](https://user-images.githubusercontent.com/86580534/133154207-a8e5c181-7a8d-4a4a-81ce-aeae930e9593.png)

<br>


### Explore the database that we just created
2. Run the container in the terminal using bash command, then using psql command to enter the database:
```bash
#!/usr/bin/env bash
docker exec -it db_postgres_digital_twin bash
psql -U [username]
```
![image](https://user-images.githubusercontent.com/86580534/135923113-de2579eb-9993-48df-9481-58241f648390.png)

3. By default user will be connected to postgres database. You can change the database using the command:
`\c db `

4. We can also check the list of tables stored in our database using the command: `\dt`

![image](https://user-images.githubusercontent.com/86580534/135923541-9bd0b2a7-f6f6-4c32-b40e-c2130050f258.png)

5. To check the data stored in the table:
run the command:
```bash
#!/usr/bin/env bash
select * from region_geometry;
```

<br>
