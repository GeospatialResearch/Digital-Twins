# Digital-Twins

## Introduction

The digitaltwin repository is designed to store APIs and local copy of data for the required Area of Interest provided
by LINZ, ECAN, Stats NZ, KiwiRail, and LRIS in PostgreSQL. User needs to pass values to the api_records function:

1. Name of the dataset e.g. 104400-lcdb-v50-land-cover, 101292-nz-building-outlines. **Note:** make sure the names are
   unique.
2. name of the region which is by default set to New Zealand but can be changed to regions e.g. Canterbury, Otago,
   etc. (regions can be further extended to other countries in future)
3. Geometry column name of the dateset, if required. for isntance, for all LDS property and ownership, street address
   and geodetic data the geometry column is ‘shape’. For most other layers including Hydrographic and Topographic data,
   the column name is 'GEOMETRY'. For more
   info: https://www.linz.govt.nz/data/linz-data-service/guides-and-documentation/wfs-spatial-filtering
4. If user is interested in a recent copy of the data, name of website must be specified to get the recent modified date
   of the dataset. See instructions.json
5. finally enter the api which you want to store in a database.
   ![image](https://user-images.githubusercontent.com/86580534/133012962-86d117f9-7ee7-4701-9497-c50484d5cdc7.png)

Currently the tables store vector data only but will be extended to LiDAR and raster data.It allows a user to download
the vector data from different data providers where data is publicly available and store data from an area of interest (
Polygon) into a database. Currently data is fetched from LINZ, ECAN, Stats NZ, KiwiRail, and LRIS but will be extended
to other sources.

## Requirements

* [Python3](https://www.python.org/downloads/)
* [pip](https://pypi.org/project/pip/) (**P**ip **I**nstalls **P**ackages - Python package manager)
* [PostgreSQL](https://www.postgresql.org/download/)

## Required Credentials:

* Stats NZ API KEY: https://datafinder.stats.govt.nz/my/api/

## Create extensions in PostgreSQL:

1. Install Postgresql and selet PostGIS application to install along with PostgreSQL
2. ![image](https://user-images.githubusercontent.com/86580534/133153382-3a5c1069-2e65-4938-933f-5c305515fc58.png)
3. Open pgAdmin 4 and set your password which will be used for connecting to PostgreSQL using Python
4. Create Database 'datasourceapis' as shown below:
5. ![image](https://user-images.githubusercontent.com/86580534/133153639-3b21aec0-1eb3-45de-8f73-b5caa5b102ee.png)          ![image](https://user-images.githubusercontent.com/86580534/133153696-fc992bbb-2de4-443a-beaa-a92a5c176bc1.png)
6. Within a created a database, create PostGIS extension as shown below:
7. ![image](https://user-images.githubusercontent.com/86580534/133153968-0d65230f-2b5d-4686-b115-2c354f66f04e.png)          ![image](https://user-images.githubusercontent.com/86580534/133154073-4e1702f8-866c-45a3-a8aa-4c1a505cf9b4.png)
8. Once the extension is created, spatial_ref_sys table will appear under tables as shown below:
9. ![image](https://user-images.githubusercontent.com/86580534/133154207-a8e5c181-7a8d-4a4a-81ce-aeae930e9593.png)

## Create environment to run the packages

In order to run the code, run the following command in your Anaconda Powershell Prompt:

```bash
conda env create -f create_new_env_window.yml
conda activate digitaltwin
pip install git+https://github.com/Pooja3894/Digital-Twins.git
```

### run codes locally

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
4. In the commad prompt switch to the directory where docker-compose file is stored
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
run the command: ```bash select * from apilinks;```
![image](https://user-images.githubusercontent.com/86580534/135923860-d10a2323-100c-446e-bec3-6010cca2ba8b.png)

## Use a database server running as a container

Work in Progess. To deploy PostgreSQL database on a server.

