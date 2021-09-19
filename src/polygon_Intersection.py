# -*- coding: utf-8 -*-
"""
Created on Thu Aug 12 15:30:00 2021

@author: pkh35
"""
import shapely.wkt

def get_intersection(engine,geometry):
    engine.execute("create temp table if not exists temp_user_log_information (geometry geometry not null)")
    engine.execute("insert into temp_user_log_information(geometry) values(%s)",(geometry,))

    intersections = engine.execute("SELECT ST_AsText(ST_Intersection(st_astext(temp_user_log_information.geometry), \
                                  st_astext(user_log_information.geometry))) from user_log_information,temp_user_log_information")
    poly_available =[]
    for poly in intersections:
        poly_available.append(poly)
    all_empty = all(element[0] == 'POLYGON EMPTY' for element in poly_available)

    if all_empty:
        return shapely.wkt.loads(geometry)
    else:
        differences =  engine.execute("SELECT ST_AsText(ST_Difference(st_astext(temp_user_log_information.geometry), \
                                    st_astext(user_log_information.geometry))) from user_log_information,temp_user_log_information")
    
        poly_not_available =[]    
        for poly in differences:   
            poly_not_available.append(poly)
        
        a = [item for item in poly_not_available if 'POLYGON EMPTY' in item[0]]
        if a == [] :
            return shapely.wkt.loads(poly_not_available[0][0])
        else:
            return None
        


