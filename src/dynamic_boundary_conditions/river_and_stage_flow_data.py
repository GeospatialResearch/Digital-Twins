# -*- coding: utf-8 -*-
"""
Created on Tue Nov  9 16:16:49 2021

@author: pkh35
"""
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import geopandas as gpd
from urllib.parse import urlencode
import requests as rq
import pandas as pd
import datetime 
import dateutil.relativedelta
from src.digitaltwin import setup_environment


def filter_gauging_sites(url, engine):
    """Filter the gauging sites which have a past month data stored in it."""
    now = datetime.datetime.now()
    prev_month = now + dateutil.relativedelta.relativedelta(months=-1)
    df_river_gauge =  gpd.read_file(url)
    if engine.dialect.has_table(engine.connect(), "river_gauging_sites") == False:
        df_river_gauge.to_postgis("river_gauging_sites", engine, index=False, if_exists='replace')
    df_river_gauge['LAST_GAUGING'] = pd.to_datetime(df_river_gauge['LAST_GAUGING']).apply(lambda x: x.replace(tzinfo=None))
    df_river_gauge = df_river_gauge[(df_river_gauge['LAST_GAUGING'] > prev_month) & (df_river_gauge['LAST_GAUGING'] <= now)]
    return df_river_gauge

def river_stage_flow(url_river, SiteNo, StageFlow , Period = '1_Month'):
  """Extract last 1 month data from each site"""
  river_df = pd.DataFrame() 
  json_dict = {'SiteNo':SiteNo , 'Period': Period, 'StageFlow': StageFlow}
  base_url = url_river.split('?',1)[0]
  url = base_url +'?'+ urlencode(json_dict)
  url = str.replace(url, '+', '%20')
  response =  rq.get(url)
  try:
    df = pd.DataFrame(response.json()['data']['item'])
    river_df = river_df.append(df, ignore_index=True)
    return river_df
  except Exception as error:
      print(error, type(error))  


if __name__ == '__main__':
    
    engine = setup_environment.get_database()
    #Gauging sites url
    url_river_gauging_sites = 'https://opendata.arcgis.com/datasets/1591f4b1fc03410eb7b76cde0cf1ad85_4.geojson'
    # url_rainfall_gauging_sites = 'https://opendata.arcgis.com/datasets/482291bb562540888b1aec7b85919827_5.geojson'
    #river flow/stage url
    url_river = 'http://data.ecan.govt.nz/data/79/Water/River%20stage%20flow%20data%20for%20individual%20site/JSON?SiteNo=63101&Period=1_Month&StageFlow=River%20Flow'
    
    df_river_gauge = filter_gauging_sites(url_river_gauging_sites, engine) #pass url to the defined function
    print(df_river_gauge)
    #reading all the site numbers from Environment Canterbury's Gaugings Database
    final_df = pd.DataFrame()
    for i in df_river_gauge['SITENUMBER']:
            final_df = final_df.append(river_stage_flow(url_river, i, 'Stage Flow')) #change the values as per the requirements
    
    final_df.to_sql("stageflow", engine, index=False, if_exists='append')