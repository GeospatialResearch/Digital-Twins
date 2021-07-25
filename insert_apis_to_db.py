# -*- coding: utf-8 -*-
"""
Created on Fri Jul 16 09:51:31 2021

@author: pkh35
"""

import psycopg2
from urllib.parse import urlparse, parse_qs
import json
from bs4 import BeautifulSoup 
from datetime import datetime
import requests
import validators

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
        
    def insertNewApiToTbl(self,records):
        """ insert a new source information into the apilinks table """
        createTable = """CREATE TABLE IF NOT EXISTS public.apilinks(\
                                unique_id uuid NOT NULL DEFAULT uuid_generate_v4(),\
                                source_name character varying(255) COLLATE pg_catalog."default",\
                                source_apis character varying(65535) COLLATE pg_catalog."default",\
                                access_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,\
                                url character varying(67777) COLLATE pg_catalog."default",\
                                api_modified_date date,\
                                region_name character varying(255) COLLATE pg_catalog."default",\
                                geometry geometry,\
                                geomid character varying COLLATE pg_catalog."default" DEFAULT 'nz_1'::character varying,\
                                api_key character varying(255) COLLATE pg_catalog."default",\
                                query_dictionary jsonb,\
                                geometry_col_name character varying(255) COLLATE pg_catalog."default",\
                                UNIQUE (source_name))"""
        insertQuery = """INSERT INTO apilinks (source_name,source_apis, url,region_name,query_dictionary,api_modified_date,geometry_col_name) VALUES (%s,%s,%s,%s,%s,%s,%s);\
        UPDATE apilinks SET geometry =(SELECT geom FROM nz_polygons WHERE apilinks.geomid = nz_polygons.geomid)""" #adding nz polygon from another table where nz polygon is stored
        record_to_insert = (source_name,source_apis, url, region_name,query_dictionary,api_modified_date,geometry_col_name)
        try:
            self.cursor.execute(createTable)
            self.cursor.execute(insertQuery, record_to_insert)
            self.conn.commit()
            count = self.cursor.rowcount
            print(count, "Record inserted successfully into datalinks table")
            self.cursor.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def extractApiQueryParams(self,api):
        """to get the key value pair of api query"""
        parsed_api = urlparse(api)
        params = parse_qs(parsed_api.query)
        return json.dumps(params), api[:api.rfind(';')]+';'   
            
    def url_validator(self, url):
        """check if the url entered by the user is valid"""
        valid=validators.url(url)
        return url if valid==True else print("Invalid url")
    
    def urlModifiedDate(self,URL):
        """to get the modified date of the data source"""
        content = requests.get(URL)
        soup = BeautifulSoup(content.text, 'html.parser')
        url_update_date = soup.find("th", text="Last updated").find_next_sibling("td").text
        def mdy_to_ymd(d):
            """to change the format of the date type variable"""
            return datetime.strptime(d, '%d %b %Y').strftime('%Y-%m-%d')
        url_update_date = mdy_to_ymd(url_update_date)
        return url_update_date

            
    def api_validator(self,api):
        """check if the API is responsive"""
        page = requests.get(api)
        return api if page.status_code == 200 else print("Invalid URL")
        
#values from the user to insert in the datalinks table in sourceapisdb Database        
url = "https://data.linz.govt.nz/layer/101292-nz-building-outlines-all-sources/"
api ="https://data.linz.govt.nz/services;key=API_KEY/wfs?\
service=WFS&version=2.0.0&request=GetFeature&typeNames=layer-101292&outputFormat=json&\
SRSName=EPSG:2193&cql_filter=bbox(shape,5169354.082, 1559525.958, 5167380.381, 1558247.433 )"
source_name = "testing"  
region_name = "New Zealand" 
db_name = "datasourceapis"
user_name = "postgres"
password = "password"
geometry_col_name = "shape"
# calling the class and its functions 
callSrcDbClass = api_sources_db(db_name, user_name, password)
valid_url = callSrcDbClass.url_validator(url)
valid_api = callSrcDbClass.api_validator(api)
api_modified_date = callSrcDbClass.urlModifiedDate(valid_url) 
query_dictionary, source_apis = callSrcDbClass.extractApiQueryParams(valid_api)
valuesToEnterToDb = [(source_name,source_apis,valid_url,region_name,query_dictionary,api_modified_date,geometry_col_name)]
callSrcDbClass.insertNewApiToTbl(valuesToEnterToDb)
        
