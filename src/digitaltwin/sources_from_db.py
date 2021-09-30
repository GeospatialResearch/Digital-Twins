# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 10:29:52 2021

@author: pkh35
"""

import pandas as pd


def get_source_from_db(engine1, source_list):
    """check table present for requested sources"""
    query = engine1.execute("Select source_name, api_modified_date from\
                          apilinks where source_name IN %(source_list)s", (
        {'source_list': source_list}))
    sources = []
    for source in query:
        sources.append(source)
    srcListUser_to_dict = pd.DataFrame(sources, columns=['source_name',
                                                         'api_modified_date']
                                       ).to_dict(orient="list")
    return srcListUser_to_dict
