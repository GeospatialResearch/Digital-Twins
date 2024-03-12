import pathlib
import pickle
from io import BytesIO

import boto3
import geopandas as gpd
import networkx as nx
import xarray as xr
from pyproj import CRS

from src import config


class S3Manager:
    """
    A class for managing interactions with an Amazon Simple Storage Service (Amazon S3) bucket.
    Provides methods to interact with an AWS S3 bucket, including storing and retrieving objects,
    listing objects, removing objects, uploading files, and clearing the entire bucket.
    """

    def __init__(self):
        """
        Initialize an S3Manager instance.
        Sets up the S3Manager with the necessary AWS credentials obtained from environment variables and creates
        a boto3 session and S3 client for interacting with an Amazon Simple Storage Service (Amazon S3) bucket.
        """
        self.access_key_id = config.get_env_variable("AWS_ACCESS_KEY_ID")
        self.secret_access_key = config.get_env_variable("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = config.get_env_variable("AWS_BUCKET_NAME")
        self.session = self._create_session()
        self.s3 = self.session.client("s3")

    def _create_session(self):
        """
        Create a boto3 session using the provided AWS credentials.
        """
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key)
        return session

    def list_objects(self):
        """
        List objects in the S3 bucket.
        """
        resp = self.s3.list_objects_v2(Bucket=self.bucket_name)
        object_keys = []
        if "Contents" in resp:
            for obj in resp["Contents"]:
                object_keys.append(obj["Key"])
        return object_keys

    def store_object(self, s3_object_key, data):
        """
        Store an object in the S3 bucket.
        """
        if isinstance(s3_object_key, pathlib.Path):
            s3_object_key = s3_object_key.as_posix()
        if isinstance(data, nx.DiGraph):
            body = pickle.dumps(data)
        else:
            body = data.to_json(drop_id=True)
        self.s3.put_object(Bucket=self.bucket_name, Key=s3_object_key, Body=body)

    def retrieve_object(self, s3_object_key):
        """
        Retrieve an object from the S3 bucket.
        """
        if isinstance(s3_object_key, pathlib.Path):
            s3_object_key = s3_object_key.as_posix()
        resp = self.s3.get_object(Bucket=self.bucket_name, Key=s3_object_key)
        body = resp["Body"].read()
        if s3_object_key.endswith(".pickle"):
            data = pickle.loads(body)
        elif s3_object_key.endswith(".nc"):
            with BytesIO(body) as body_object:
                data = xr.load_dataset(body_object, engine="h5netcdf")
                if data.rio.crs is None:
                    epsg_code = CRS.from_string(data.crs.spatial_ref).to_epsg()
                    data.rio.write_crs(epsg_code, inplace=True)
        else:
            data = gpd.read_file(BytesIO(body))
        return data

    def remove_object(self, s3_object_key):
        """
        Remove an object from the S3 bucket.
        """
        self.s3.delete_object(Bucket=self.bucket_name, Key=s3_object_key)

    def store_file(self, s3_object_key, file_path):
        """
        Upload a file to the S3 bucket.
        """
        if isinstance(s3_object_key, pathlib.Path):
            s3_object_key = s3_object_key.as_posix()
        self.s3.upload_file(Bucket=self.bucket_name, Key=s3_object_key, Filename=file_path)

    def clear_bucket(self):
        """
        Clear the entire S3 bucket by removing all objects.
        """
        bucket = self.s3.Bucket(self.bucket_name)
        bucket.objects.all().delete()



