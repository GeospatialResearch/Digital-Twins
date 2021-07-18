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
        
    def insert_row_db(self,source_name,source_apis,url,region_name,query_dictionary,url_update_date):
        """ insert a new source into the datalinks table """
        sql = """INSERT INTO datalinks (source_name,source_apis, url,region_name,query_dictionary,url_update_date) VALUES (%s,%s,%s,%s,%s,%s);\
        UPDATE datalinks SET geom =(SELECT geom FROM nz_polygons WHERE datalinks.geomid = nz_polygons.geomid)""" #adding nz polygon from another table where nz polygon is stored
        record_to_insert = (source_name,source_apis, url, region_name,query_dictionary,url_update_date)
        conn = None
        try:
            # create a cursor
            cur = self.conn.cursor()
            # execute the INSERT statement
            cur.execute(sql, record_to_insert)
            # commit the changes to the database
            self.conn.commit()
            count = self.cursor.rowcount
            print(count, "Record inserted successfully into datalinks table")
            # close communication with the database
            cur.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()


def api_query_dictionary(api):
    """to get the key value pair of api query"""
    try:
        parsed_api = urlparse(api)
        params = parse_qs(parsed_api.query)
        return json.dumps(params), api[:api.rfind(';')]+';'   
    except:
        print("Not a valid api")

def url_last_updated(URL):
    """to get the modified date of the data source"""
    try:
        content = requests.get(URL)
        print(content)
        soup = BeautifulSoup(content.text, 'html.parser')
        url_update_date = soup.find("th", text="Last updated").find_next_sibling("td").text
        print(url_update_date)
        def mdy_to_ymd(d):
            return datetime.strptime(d, '%d %b %Y').strftime('%Y-%m-%d')
        url_update_date = mdy_to_ymd(url_update_date)
        return url_update_date
    except:
        print('Not a valid url') 
        
        
URL = 'https://data.linz.govt.nz/layer/101292-nz-building-outlines-all-sources/'
url_update_date = url_last_updated(URL)       
api = "https://lris.scinfo.org.nz/services;key=YOUR_API_TOKEN/wfs?service=WFS&version=2.0.0&\
request=GetFeature&typeNames=layer-104400&outputFormat=json&\
SRSName=EPSG:2193&cql_filter=bbox(GEOMETRY,5169354.082, 1559525.958, 5167380.381, 1558247.433)"   
query_dictionary, source_apis = api_query_dictionary(api)
source_name = "testing"  
url = "testing"  
region_name = "New Zealand" 

# calling the class  
p1 = api_sources_db("datasourceapis", "postgres", "Pooja")
p1.insert_row_db(source_name,source_apis,url,region_name,query_dictionary,url_update_date) 
        
