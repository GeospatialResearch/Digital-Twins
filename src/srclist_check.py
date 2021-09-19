# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 10:29:52 2021

@author: pkh35
"""

import pandas as pd
import json
import numpy as np
    
def srcListCheck(engine1,source_list,geometry):
    src = engine1.execute("Select source_name, api_modified_date from apilinks where source_name IN %(source_list)s",({'source_list':source_list}))
    srces= []
    for s in src:
        srces.append(s)  
    srcListUser_to_dict = pd.DataFrame(srces,columns = ['source_name', 'api_modified_date']).to_dict(orient="list") 
    stored_list = engine1.execute("select source_list from user_log_information") 
    stored_srces= []
    for src in stored_list:
        stored_srces.append(src)
 
    if stored_srces == []:
        return source_list, srcListUser_to_dict
    
    else: 
        srcList = stored_srces[0][0]
        table_user_values_of_key = json.loads(srcList)['source_name']
        data_not_avail_for_srces = np.setdiff1d(srcListUser_to_dict['source_name'],table_user_values_of_key)
        return tuple(data_not_avail_for_srces), srcListUser_to_dict
            