from http.client import BAD_REQUEST

from flask import Blueprint, Response, jsonify, request, abort
from geopandas import GeoDataFrame

from .services import fetch_updated_vector_data

vector_blueprint = Blueprint('vector', __name__, url_prefix='/static/vector-data')

engine = None

temp_region_of_interest = None


@vector_blueprint.route('', methods=['GET'])
def get_all_vector_data() -> Response:
    """Returns an up-to-date version of all Digital Twin vector data in list of GeoJSON feature collections
    Required query parameter - bbox - the two coordinates of the corners of the bounding box of the region to be fetched
    in wgs84 CRS.
    e.g. bbox=(-43.343736,172.633526),(-43.398719,172.720858)"""
    bbox = request.args.get('bbox')
    if not bbox:
        return Response("No bbox supplied", BAD_REQUEST)

    return jsonify(fetch_updated_vector_data())


def gdf_from_bbox(bbox: str) -> GeoDataFrame:
    pass