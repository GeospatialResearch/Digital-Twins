# -*- coding: utf-8 -*-
"""
Created on Mon Jun 28 11:09:51 2021

@author: pkh35
"""

import geopandas as gpd
from urllib.parse import urlencode
import json
import requests as rq
import pandas as pd
import datetime 
import dateutil.relativedelta

def river_stage_flow(url_river, SiteNo, StageFlow , Period = '1_Month'):
  """Extract last 1 month data from each site"""
  df_n = pd.DataFrame() 
  
  #create dictionary of json query
  mydict = {'SiteNo':SiteNo , 'Period': Period, 'StageFlow': StageFlow} 
  base_url = url_river.split('?',1)[0]
  
  #add the requested query to url
  url = base_url +'?'+ urlencode(mydict)
  url = str.replace(url, '+', '%20')
  
  # store the response of URL
  response =  rq.get(url)
  
  try:
    #Extract data from nested json
    df = pd.DataFrame(response.json()['data']['item'])
    # add extracted data to an empty dataframe
    df_n = df_n.append(df, ignore_index=True)
  except:
    pass
  return df_n

def filter_gauging_sites(url):
    """Extract gauging sites data if updated last month"""
    df_river_gauge =  gpd.read_file(url)
    df_river_gauge['LAST_GAUGING'] = pd.to_datetime(df_river_gauge['LAST_GAUGING']).apply(lambda x: x.replace(tzinfo=None))
    #get today's date
    now = datetime.datetime.now()
    print(now)
    #get previous month date
    prev_month = now + dateutil.relativedelta.relativedelta(months=-1)
    print(prev_month)
    #select sites updated from the last month to today's date
    df_river_gauge[(df_river_gauge['LAST_GAUGING'] > prev_month) & (df_river_gauge['LAST_GAUGING'] <= now)]
    return df_river_gauge


if __name__ == '__main__':
    #Gauging sites url
    url_river_gauging_sites = 'https://opendata.arcgis.com/datasets/1591f4b1fc03410eb7b76cde0cf1ad85_4.geojson'
    
    #river flow/stage url
    url_river = 'http://data.ecan.govt.nz/data/79/Water/River%20stage%20flow%20data%20for%20individual%20site/JSON?SiteNo=63101&Period=1_Month&StageFlow=River%20Flow'
    
    df_river_gauge = filter_gauging_sites(url_river_gauging_sites) #pass url to the defined function
 
    #reading all the site numbers from Environment Canterbury's Gaugings Database
    final_df = pd.DataFrame()
    for i in df_river_gauge['SITENUMBER']:
            final_df = final_df.append(river_stage_flow(url_river, i, 'River Flow'))
            #final_df = final_df.append(river_stage_flow(url_river, i, 'River Stage'))

final_df.to_excel(r"C:\Users\pkh35\Dropbox\Digital_Twin_Pooja_Greg_Matt_Purvi\River_flow_stage_data\riverstage.xlsx")  
