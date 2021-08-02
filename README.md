# Digital-Twins

## Introduction

The digitaltwin package allows the creation of tables in PostgreSQL. Currently the package supports vector data only but will be extended to LiDAR and raster data.

The digitaltwin package allows user to download the vector data from different data providers where data is publicly available and store data from an area of interest into a database. Currently data is fetched from LINZ and LRIS but will be extended to other sources.

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
