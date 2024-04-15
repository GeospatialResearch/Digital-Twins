import logging
import pathlib
import pickle
from io import BytesIO
from typing import List, Union

import boto3
import geopandas as gpd
import networkx as nx
import xarray as xr
from pyproj import CRS

from src import config

log = logging.getLogger(__name__)


class S3Manager:
    """
    A class for managing interactions with an Amazon Simple Storage Service (Amazon S3) bucket.
    Provides methods to interact with an AWS S3 bucket, including storing and retrieving objects,
    listing objects, removing objects, uploading files, and clearing the entire bucket.
    """

    def __init__(self) -> None:
        """
        Initialize an S3Manager instance.
        Sets up the S3Manager with the necessary AWS credentials obtained from environment variables and creates
        a boto3 session and S3 client for interacting with an Amazon Simple Storage Service (Amazon S3) bucket.
        """
        self.access_key_id = config.get_env_variable("AWS_ACCESS_KEY_ID")
        self.secret_access_key = config.get_env_variable("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = config.get_env_variable("AWS_BUCKET_NAME")
        self.session = self._create_session()
        self.s3_client = self.session.client("s3")
        self.s3_resource = self.session.resource("s3")

    def _create_session(self) -> boto3.session.Session:
        """
        Create a boto3 session using the provided AWS credentials.
        """
        # Create a boto3 session object for interacting with AWS services
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key)
        return session

    def list_objects(self) -> List[str]:
        """
        List objects in the S3 bucket.
        """
        # Retrieve a list of objects from the S3 bucket
        resp = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
        # Initialize an empty list to store the object keys
        object_keys = []
        # Check if the response contains any objects
        if "Contents" in resp:
            # Iterate over each object in the response
            for obj in resp["Contents"]:
                # Extract the object key and append it to the list
                object_keys.append(obj["Key"])
        return object_keys

    def store_object(self, s3_object_key: Union[str, pathlib.Path], data: Union[nx.Graph, gpd.GeoDataFrame]) -> None:
        """
        Store an object in the S3 bucket.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Check if the provided data is a NetworkX DiGraph object
        if isinstance(data, nx.Graph):
            # Serialize the DiGraph object into a byte string using the pickle module
            body = pickle.dumps(data)
        else:
            # Convert the data to a JSON string
            body = data.to_json(drop_id=True)
        # Upload the data to the S3 bucket using the provided object key
        self.s3_client.put_object(Bucket=self.bucket_name, Key=s3_object_key, Body=body)
        # Log a message confirming successful storage in the S3 bucket
        log.info(f"Successfully stored `{s3_object_key}` in the S3 bucket.")

    def retrieve_object(self, s3_object_key: Union[str, pathlib.Path]):
        """
        Retrieve an object from the S3 bucket.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Retrieve the object from the S3 bucket using the provided object key
        resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_object_key)
        # Read the content of the retrieved object
        body = resp["Body"].read()
        # Determine the appropriate action based on the file extension of the object
        # Check if the s3_object_key ends with ".pickle" extension
        if s3_object_key.endswith(".pickle"):
            # Deserialize (load) the binary data
            data = pickle.loads(body)
        # Check if the s3_object_key ends with ".nc" extension
        elif s3_object_key.endswith(".nc"):
            # Open the body as a BytesIO object for efficient in-memory handling
            with BytesIO(body) as body_object:
                # Load the dataset from the BytesIO object using the h5netcdf engine
                data = xr.load_dataset(body_object, engine="h5netcdf")
                # Check if the dataset does not have a Coordinate Reference System (CRS) defined
                if data.rio.crs is None:
                    # Extract and convert dataset's CRS spatial reference to EPSG code
                    epsg_code = CRS.from_string(data.crs.spatial_ref).to_epsg()
                    # Write the EPSG code as the Coordinate Reference System (CRS) for the dataset
                    data.rio.write_crs(epsg_code, inplace=True)
        # If the file extension is neither ".pickle" nor ".nc"
        else:
            # Read the content of the retrieved object using geopandas
            data = gpd.read_file(BytesIO(body))
        # Log a message confirming successful retrieval from the S3 bucket
        log.info(f"Successfully retrieved '{s3_object_key}' from the S3 bucket.")
        return data

    def remove_object(self, s3_object_key: Union[str, pathlib.Path]) -> None:
        """
        Remove an object from the S3 bucket.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Delete the object with the provided object key from the S3 bucket
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_object_key)
        # Log a message confirming successful deletion from the S3 bucket
        log.info(f"Successfully deleted '{s3_object_key}' from the S3 bucket.")

    def store_file(self, s3_object_key: Union[str, pathlib.Path], file_path: Union[str, pathlib.Path]) -> None:
        """
        Upload a file to the S3 bucket.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Upload the file at 'file_path' to the S3 bucket with the provided object key
        self.s3_client.upload_file(Bucket=self.bucket_name, Key=s3_object_key, Filename=file_path)
        # Log a message confirming successful storage in the S3 bucket
        log.info(f"Successfully stored `{s3_object_key}` in the S3 bucket.")

    def clear_bucket(self) -> None:
        """
        Clear the entire S3 bucket by removing all objects.
        """
        # Access the S3 bucket
        bucket = self.s3_resource.Bucket(self.bucket_name)
        # Delete all objects within the bucket
        for obj in bucket.objects.all():
            obj.delete()
        # Log a message confirming successful removal of all objects from the S3 bucket
        log.info("Successfully removed all objects from the S3 bucket.")
