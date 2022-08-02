from flask import Blueprint, Response, jsonify

# from .services import get_data_from_db, data_needs_update_from_external, update_data_from_external
from .services import fetch_updated_vector_data

vector_blueprint = Blueprint('vector', __name__, url_prefix='/datasources/vector-data')

engine = None

temp_region_of_interest = None


@vector_blueprint.route('', methods=['GET'])
def get_all_vector_data() -> Response:
    """Returns an up-to-date version of all Digital Twin vector data in list of GeoJSON feature collections"""
    return jsonify(fetch_updated_vector_data())
