"""Tests for data_to_db.py"""
import unittest
from unittest import mock

import geopandas as gpd
import pandas as pd
import shapely

from eddie.digitaltwin import data_to_db


class AppendToExistingLayerTest(unittest.TestCase):
    """Tests that data fetched in one working CRS is appended in the CRS the layer table was created in."""

    @mock.patch.object(data_to_db, "get_vector_data_id_not_in_db", return_value={1})
    @mock.patch.object(data_to_db, "fetch_vector_data_using_geoapis")
    def test_reprojects_to_table_crs(self, fetch, _):
        # Fetched in UTM zone 60 (an Auckland request) for a table created in UTM zone 59 (a Christchurch request)
        fetched = gpd.GeoDataFrame({"id": [1]}, crs=4326, geometry=[shapely.Point(174.76, -36.85)]).to_crs(32760)
        fetch.return_value = fetched
        conn = mock.MagicMock()
        conn.execute.return_value.scalar.return_value = 32759
        aoi = gpd.GeoDataFrame(index=[0], crs=32760, geometry=[fetched.buffer(100).geometry[0]])
        with mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            data_to_db.process_existing_non_nz_geospatial_layers(conn, "LINZ", 1, "layer", "id", aoi, 32760)
        appended = to_postgis.call_args.args[0]
        self.assertEqual(appended.crs.to_epsg(), 32759)
        self.assertTrue(appended.geometry[0].equals_exact(fetched.to_crs(32759).geometry[0], 1e-6))


class AoiSridTest(unittest.TestCase):
    """Tests that the AOI is bound in the CRS it came with, else EPSG:4326."""

    def bound_srid(self, aoi: gpd.GeoDataFrame) -> int:
        with mock.patch.object(data_to_db.pd, "read_sql", return_value=pd.DataFrame({"id": []})) as read_sql:
            data_to_db.get_vector_data_id_not_in_db(mock.MagicMock(), pd.DataFrame({"id": [1]}), "layer", "id", aoi)
        return read_sql.call_args.args[0].compile().params["aoi_srid"]

    def test_crs_from_the_aoi(self):
        self.assertEqual(self.bound_srid(gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=32759)), 32759)

    def test_4326_without_crs(self):
        self.assertEqual(self.bound_srid(gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)])), 4326)


if __name__ == "__main__":
    unittest.main()