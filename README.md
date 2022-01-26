# Digital-Twins

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

The digital twin stores API details and a local copy of data for the required Area of Interest provided by LINZ, ECAN, Stats NZ, KiwiRail, LRIS, opentopography, and NIWA in PostgreSQL. 

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
Enter the api data which you want to store in a database.
   ![image](https://user-images.githubusercontent.com/86580534/133012962-86d117f9-7ee7-4701-9497-c50484d5cdc7.png)

Run run.py file from your IDE:

![image](https://user-images.githubusercontent.com/86580534/135927747-0bff7da4-f30a-4858-add5-2e9bbb93d880.png)

This way data will be stored in the database which then will be used to make api requests for the desired Area of Interest.
geometry column's name, url and layer name are not required if the data provider is not LINZ, LRIS or StatsNZ:

To get the data from the database:

1. Make sure [db_configure.yml](https://github.com/GeospatialResearch/Digital-Twins/blob/get-apis-and-make-wfs-request/src/db_configure.yml) file has the correct information        stored in it. 
   
2. The geometry and source list needs to passed as an argument to get_data_from_db() function. Check [test1.json](https://github.com/GeospatialResearch/Digital-Twins/blob/get-apis-and-make-wfs-request/src/test1.json) for more details on the format and structure of the arguments.
3. Run get_data_from_db.py file from your IDE:
   
   ![image](https://user-images.githubusercontent.com/86580534/137419448-919a4372-0d69-4a79-98b0-0046f4b4edfc.png)


get_data_from_db module allows the user to get data from the multiple sources within the required Area of Interest from the database and if data is not available in the database for the desired area of Interest, wfs request is made from the stored APIs, data is stored in the database and spatial query is done within the database to get the data for the desired Area of Interest. 
Currently data is collected from LINZ, ECAN, Stats NZ, KiwiRail, LRIS, NIWa and opentopography but will be extended to other sources.

## Raster Database

Hydrologically conditioned DEMs are generated using [geofabrics] (https://github.com/rosepearson/GeoFabrics ) designed by NIWA which downloads the LiDAR data in the local directory from [opentopography] (https://portal.opentopography.org/dataCatalog ) and generates DEM. These DEMs are stored in the local directory set by the user. The objective of the **dem_metadata_in_db.py** script is to store the metadata of the generated DEM in the database for the requested catchment area. Storing these details in the database helps in getting the DEM already generated using geofabrics rather than generating DEM for the same catchment, again and again, saving time and resources. 
The stored DEM is used to run the Flood model (BG Flood model)[https://github.com/CyprienBosserelle/BG_Flood )] designed by NIWA. 
The [instruction file](https://github.com/GeospatialResearch/Digital-Twins/blob/lidar_to_db/src/lidar/file.json) used to create hydrologically conditioned DEM is passed to the **get_dem_path(instruction)** function which checks if the DEM information exists in the database, if it doesn’t exist, geofabrics is used to generate the hydrologically conditioned DEM which gets stored in the local directory and the metadata of the generated DEM is stored in the database and file path of the generated DEM is returned which is then used to run the flood model. 

## LiDAR Database

The data source for the LiDAR data is [opentopography]( https://portal.opentopography.org/dataCatalog). The data for the requested catchment area is downloaded using [geopais] (https://github.com/niwa/geoapis ) in the local directory set by the user. To store the LiDAR metadata in the database, lidar_metadata_in_db script is used. The [instruction file](https://github.com/GeospatialResearch/Digital-Twins/blob/lidar_to_db/src/lidar/file.json ) and path to the local directory where user wants to store the LiDAR data is passed as an argument to store_lidar_path(file_path_to_store, instruction_file) function as shown below:

![image](https://user-images.githubusercontent.com/86580534/145321190-9bf60d8b-95e0-4fee-9cda-5613e18d24e3.png)

## BoundaryConditions data

### Rain gauges location

The rain gauages location is accessed from [HIRDS](https://hirds.niwa.co.nz/) which is tool that provides a map-based interface to enable rainfall estimates to be provided at any location in New Zealand. The gauges information can be stored in the database using **hirds_gauges.py** script as shown below:

![image](https://user-images.githubusercontent.com/86580534/151071987-8efa0fe6-c1fa-418e-8562-37cb43a6ebce.png)

### To get the rainfall data of the gauging sites within the desired catchment area from HIRDS and store in the database, use **hirds_depth_data_to_db.py** script.

**hirds_depths_to_db(engine, catchment_area, path)** function requires three arguments,
1. engine: information about the database to interact with.
2. catchment_area: Polygon type 
3. path: hirds depth data is first downloaded as csv files in the local directory before getting stored in the database, so user needs to provide the path where the depth data will be stored as csv files.
The example is as shown below:

![image](https://user-images.githubusercontent.com/86580534/151073978-674f029e-9dca-4928-9c7a-3b86125ff664.png)

### To get the rainfall depth data from the database, **hirds_depth_data_from_db.py** script is used. 

**hirds_depths_from_db(engine, catchment_area, ari, duration, rcp, time_period)** function requires six arguments,
1. engine: information about the database to interact with.
2. catchment_area: Polygon type 
3. ari:  Average Recurrence Interval (ARI) i.e. the average or expected value of the periods between exceedances of a given rainfall total accumulated over a given duration.
4. duration: total rainfall depth for a particular duration i.e. 1,2,6,12,24,48,72,96 and 120 hr 
5. rcp: there are different Representative Concentration Pathway (RCP) which is a greenhouse gas concentration (not emissions) trajectory adopted by the IPCC. There values are 2.6, 4.5, 6, and 8.5 also called radiative forcing values. 
6. time_period: different rcp's are associated  with different time periods.

For more details on ari, duration, rcp and time_period go to [HIRDS](https://hirds.niwa.co.nz/)

![image](https://user-images.githubusercontent.com/86580534/151084770-582a75b6-bff0-414c-b035-b8f54f52f7d8.png)

### Theissen Polygons
Each gauge is associated for a particular area. To get the size of the area assoicated wih each gauge, **theissen_polygon_calculator.py** script is used. 

theissen_polygons(engine, catchment, gauges_in_polygon) function is used to calculate the area. It takes three arguments:
1. engine: information about the database to interact with.
2. catchment_area: Polygon type 
3. gauges_in_polygon: get the gauges information which are within the desired catchment area.
 to get the get the gauges within the catchment area, **get_guages_location(engine, catchment)** function is used from **hirds_gauges.py** script.
 
 ![image](https://user-images.githubusercontent.com/86580534/151086490-1f2f0bf4-53a7-4a0a-a595-803a0fecf61c.png)
 
 ### Hyetographs
 
 A hyetograph is a graphical representation of the distribution of rainfall intensity over time. For instance, in the 24-hour rainfall distributions, rainfall intensity progressively increases until it reaches a maximum and then gradually decreases. Where this maximum occurs and how fast the maximum is reached is what differentiates one distribution from another. One important aspect to understand is that the distributions are for design storms, not necessarily actual storms. In other words, a real storm may not behave in this same fashion
To generate a hyetograph, **hyetograph.py** script is used.
hyetograph(duration, site, total_rain_depth) function takes 3 arguments:
1. duration: how many hours rainfall distributions is required i.e. 1,2,6,12,24,48,72,96 and 120 hr 
2. site: site id of a site for which hyetograph is required
3. total_rain_depth: total rainfal depth at a given duration

![image](https://user-images.githubusercontent.com/86580534/151091023-fa680851-1f68-4f94-9490-6777f5a0918c.png)  ![image](https://user-images.githubusercontent.com/86580534/151091040-91050e83-79a4-4436-8b78-d61d516ff9dd.png)


### Run BG Flood model

To run the model, **bg_flood_model.py** script is used which takes DEM informationfrom the database, runs the model and stores the output back to the database.
run_model(bg_path, instructions, catchment_boundary, resolution, endtime, outputtimestep) function is used to run the model as shown below:

![image](https://user-images.githubusercontent.com/86580534/151091915-fc5b3829-0951-4cb0-986a-90ff87d8325b.png)

The function requires 9 arguments, of which 3 are set as default values and can be changed later:

![image](https://user-images.githubusercontent.com/86580534/151092395-ab6e62a9-96ea-4d55-be39-25aaeb5d3aa0.png)

The arguments are explained below:
1. bg_path: path where BG Flood exe file is saved.
2. instructions: json file used to generate DEM.
The script uses geofabrics to generate a hydrologically conditioned DEM if it doesn't exist in the database therefore instruction file is required as an argument. 
3. catchment_boundary: geopandas type
4. resolution: resolution value of the DEM. In the example above, resolution value is taken from the instruction file itself.
5. endtime: Saving the outputs till given time (in seconds)
6. outputtimestep: Saving the outputs after every given time (in seconds)
7. mask: take values above the given number from DEM.
8. gpudevice: if using GPU to run the model, set value as 0 else -1.
9. smallnc: Level of refinement to apply to resolution based on the adaptive resolution trigger


## Requirements

* [Python3](https://www.python.org/downloads/)
* [pip](https://pypi.org/project/pip/) (**P**ip **I**nstalls **P**ackages - Python package manager)
* [PostgreSQL](https://www.postgresql.org/download/)

## Required Credentials:

* [Stats NZ API KEY](https://datafinder.stats.govt.nz/my/api/)

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

## Create environment to run the packages

In order to run the code, run the following command in your Anaconda Powershell Prompt:

```bash
conda env create -f create_new_env_window.yml
conda activate digitaltwin
pip install git+https://github.com/Pooja3894/Digital-Twins.git
```

### Run codes locally

1. Open Anaconda Powershell Prompt
2. run the command

```bash 
conda activate digitaltwin
spyder
```

3. In Spyder IDE: Go to `Run`>`Configuration per file`>`Working directory settings` Select `The following directory:` option
   and specify the root of the directory

   ![image](https://user-images.githubusercontent.com/86580534/133013167-c7e4541a-5723-4a76-9344-25f9f835b986.png)
   
## Running docker on your machine

Install [docker](https://docs.docker.com/desktop/windows/install/)

When the installation finishes, Docker starts automatically. The whale   in the notification area indicates that Docker is running, and accessible from a terminal.

### Instructions to run docker
1. Create an .env file with variables in the following format, each on a new line:
   ```bash
      POSTGRES_USER=postgres
      POSTGRES_PASSWORD=postgres
      POSTGRES_DB=db
   ```
2. Save this file in the directory where docker-compose file is stored.
3. Open the command prompt, you can use `Windows Key + X` to open it.
4. In the commad prompt switch to the directory where docker-compose file is stored.
   For instance:  ![image](https://user-images.githubusercontent.com/86580534/135922576-25644dc3-ef32-4f59-8b5c-8c5778242cc8.png)
6. Run the command: 
   ```bash
      docker-compose build
      docker-compose up
   ```
Now your docker is up and running

### Explore the database that we just created
1. Get the container name by running the command: `docker ps`

![image](https://user-images.githubusercontent.com/86580534/135923023-c11a04bd-5bf0-4ad7-992b-783f0cbc2c50.png)

2. Run the container in the terminal using bash command, then using psql command to enter the database:
```bash
   docker exec -it [container id] bash
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
select * from apilinks;
```

![image](https://user-images.githubusercontent.com/86580534/135923860-d10a2323-100c-446e-bec3-6010cca2ba8b.png)

## Use a database server running as a container

Work in Progess. To deploy PostgreSQL database on a server.

