# -*- coding: utf-8 -*-
"""
Created on Mon Jul 19 09:32:01 2021

@author: pkh35
"""

import psycopg2
import geopandas as gpd
import requests as rq
from sqlalchemy import create_engine

class api_sources_db:
    """class to insert and update values in database where all APIs are stored in a table"""
    def __init__(self, dbname, user, password):
        """connect to PostgreSQL DBMS"""
        self.dbname = dbname
        self.user = user
        self.password = password
        self.connect_text = "dbname ='%s' user= '%s' password='%s'" % (self.dbname, self.user, self.password)
        self.conn = psycopg2.connect(self.connect_text)
        self.cursor = self.conn.cursor()
    def access_api_from_sourcedb(self,source_name):
        """ select desired API from the table """
        try:
            # create a new cursor
            cur = self.conn.cursor()
            # execute the UPDATE  statement
            cur.execute("SELECT source_apis,query_dictionary, geometry_col_name FROM datalinks WHERE source_name = %s", (source_name,))
            #get the api
            api = cur.fetchall()
            #everytime api is accessed, update access datetime of the api from the database
            cur.execute("UPDATE datalinks SET date = CURRENT_TIMESTAMP WHERE source_name = %s", (source_name,))
            # Commit the changes to the database
            self.conn.commit()
            # Close communication with the PostgreSQL database
            cur.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if self.conn is not None:
                self.conn.close()
        return api
    
def data_from_apis(url, key, params, geometry_col_name,geometry):
    """Construct the api query for the requested area and save it as a cache table"""
    params['cql_filter']= "Within(" + geometry_col_name +"," + geometry
    base_url = url.split(';',1)[0]
    base_url = base_url +';key='+ key+'/wfs'
    try:
        #add the requested query to url
        response = rq.get(base_url, params = params)
        gdf = gpd.read_file(response.text)
        engine = create_engine(r'postgresql://postgres:username@localhost:port/db_name?gssencmode=disable')
        gdf.to_postgis("road_centerlines_data", engine, index = False, if_exists = 'replace')
        print("Pull request successful")
    except:
        print("Pull request failed, Please enter a valid polygon")

              
#Get the source name whose api user wants to access                
source_name = "Building_Outlines" 
#get the api key from the user
api_key = " "

#get the polygon from the user
try:
    polygon=(input("Coordinate format and order for nzta coordinates is 5939800 1722599, 5916017 1760652 (y/x) \nEnter the polygon: "))
    list_poly = polygon.split (",")
except:
    print ('You have entered an invalid value.')
else:
    if len(list_poly) <= 7:
            geometry = "POLYGON((" + polygon + ")))"
    else:    
        print("points exceeding the limit, maximum limit is 6")

              
p1 = api_sources_db("datasourceapis", "postgres", "Pooja")
selected_api = p1.access_api_from_sourcedb(source_name) 
base_url = selected_api[0][0]   #access base url
query_param = selected_api[0][1] # access query part of api
geometry_col_name = selected_api[0][2] # access column name where geometry is stored in the source database

data_from_apis(base_url,api_key,query_param,geometry_col_name,geometry)











