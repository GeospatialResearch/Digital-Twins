# Digital-Twins

## Introduction

The digitaltwin repository is designed to create tables and store APIs provided by LINZ, ECAN, Stats NZ, KiwiRail, and LRIS in PostgreSQL.
User needs to pass values to the api_records function: 
1. Name of the dataset e.g. 104400-lcdb-v50-land-cover, 101292-nz-building-outlines. **Note:** make sure the names are unique.
2. name of the region which is by default set to New Zealand but can be changed to regions e.g. Canterbury, Otago, etc. (regions can be further extended to other countries in future)
3. Geometry column name of the dateset, if required. for isntance, for all LDS property and ownership, street address and geodetic data the geometry column is ‘shape’. For most other layers including Hydrographic and Topographic data, the column name is 'GEOMETRY'. For more info: https://www.linz.govt.nz/data/linz-data-service/guides-and-documentation/wfs-spatial-filtering 
4. If user is interested in a recent copy of the data, name of website must be specified to get the recent modified date of the dataset. See instructions.json
5. finally enter the api which you want to store in a database.
![image](https://user-images.githubusercontent.com/86580534/133012962-86d117f9-7ee7-4701-9497-c50484d5cdc7.png)

Currently the tables store vector data only but will be extended to LiDAR and raster data.It allows a user to download the vector data from different data providers where data is publicly available and store data from an area of interest (Polygon) into a database. Currently data is fetched from LINZ, ECAN, Stats NZ, KiwiRail, and LRIS but will be extended to other sources.

## Create environment to run the packages

In order to run the codes, run the following command in your Anaconda Powershell Prompt. 

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
3. In Spyder IDE: Go to 'Run>Configuration per file>Working directory settings
   Select 'The following directory:' option and speicify the root of the directory 
   
   ![image](https://user-images.githubusercontent.com/86580534/133013167-c7e4541a-5723-4a76-9344-25f9f835b986.png)

