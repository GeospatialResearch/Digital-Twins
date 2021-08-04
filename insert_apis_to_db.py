# -*- coding: utf-8 -*-
"""
Created on Fri Jul 16 09:51:31 2021

@author: pkh35
"""

from urllib.parse import urlparse, parse_qs
import json
import pathlib
import urllib
from datetime import datetime
import psycopg2
from bs4 import BeautifulSoup
import requests
import validators

class apiSourcesDb:
    """class to insert and update values in database where all APIs are stored in a table"""

    def __init__(self, dbname, user, password):
        """connect to PostgreSQL DBMS"""
        self.dbname = dbname
        self.user = user
        self.password = password
        self.connect_text = f"dbname ='{dbname}' user= '{user}' password='{password}'"
        self.conn = psycopg2.connect(self.connect_text)
        self.cursor = self.conn.cursor()

    def insertNewApiToTbl(self, records, create_table,insert_query):
        """ insert a new source information into the apilinks table """
        #adding nz polygon from another table where nz polygon is stored
        try:
            self.cursor.execute(create_table)
            self.cursor.execute(insert_query, records[0])
            self.conn.commit()
            count = self.cursor.rowcount
            print(count, "Record inserted successfully into datalinks table")
            self.cursor.close()
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def extractApiQueryParams(self, api):
        """to parse the api, to get the base url and params"""
        parsed_api = urlparse(api)
        params = parse_qs(parsed_api.query)
        base_url = urllib.parse.urlunparse(
            (parsed_api.scheme, parsed_api.netloc, parsed_api.path, "", "", ""))
        return json.dumps(params), base_url

    def url_validator(self, url):
        """check if the url entered by the user is valid"""
        valid = validators.url(url)
        return url if valid is True else print("Invalid url")

    def urlModifiedDate(self, url):
        """to get the modified date of the data source"""
        content = requests.get(url)
        soup = BeautifulSoup(content.text, 'html.parser')
        url_update_date = soup.find(
            "th", text="Last updated").find_next_sibling("td").text

        def mdy_to_ymd(url_date):
            """to change the format of the date type variable"""
            return datetime.strptime(url_date, '%d %b %Y').strftime('%Y-%m-%d')
        url_update_date = mdy_to_ymd(url_update_date)
        return url_update_date


# load in the instructions
file_path = pathlib.Path().cwd() / pathlib.Path("instructions.json")
with open(file_path, 'r') as file_pointer:
    instructions = json.load(file_pointer)

source_name = instructions['instructions']['apis']['linz']['source_name']
region_name = instructions['instructions']['region_name']
db_name = instructions['instructions']['db_name']
user_name = instructions['instructions']['user_name']
password = instructions['instructions']['password']
geometry_col_name = instructions['instructions']['apis']['linz']['geometry_col_name']
create_table = instructions['instructions']['sql_query']
insert_query = instructions['instructions']['insert_query']
# calling the class and its functions
callSrcDbClass = apiSourcesDb(db_name, user_name, password)
valid_url = callSrcDbClass.url_validator(instructions['instructions']['url'])
api_modified_date = callSrcDbClass.urlModifiedDate(valid_url)
query_dictionary, source_apis = callSrcDbClass.extractApiQueryParams(
    instructions['instructions']['api'])
valuesToEnterToDb = [(source_name, source_apis, valid_url, region_name,
                      query_dictionary, api_modified_date, geometry_col_name)]
callSrcDbClass.insertNewApiToTbl(
    valuesToEnterToDb, create_table,insert_query)
