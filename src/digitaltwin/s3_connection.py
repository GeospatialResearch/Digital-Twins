# -*- coding: utf-8 -*-
"""This script defines a python class to facilitate interactions with an Amazon S3 bucket."""

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

from src.config import EnvVariable

log = logging.getLogger(__name__)


class S3Manager:
    """
    A class for managing interactions with an Amazon Simple Storage Service (Amazon S3) bucket.
    Provides methods to interact with an AWS S3 bucket, including storing and retrieving objects,
    listing objects, removing objects, uploading files, retrieving files, and clearing the entire bucket.
    """

    def __init__(self) -> None:
        """
        Initialize an S3Manager instance.
        Sets up the S3Manager with the necessary AWS credentials obtained from environment variables and creates a boto3
        session, S3 client, and S3 resource for interacting with an Amazon Simple Storage Service (Amazon S3) bucket.
        """
        # Validate that necessary AWS environment variables are set when S3 usage is enabled
        self.validate_aws_env_vars()

        self.access_key_id = EnvVariable.AWS_ACCESS_KEY_ID
        self.secret_access_key = EnvVariable.AWS_SECRET_ACCESS_KEY
        self.bucket_name = EnvVariable.AWS_BUCKET_NAME
        self.session = self._create_session()
        self.s3_client = self.session.client("s3")
        self.s3_resource = self.session.resource("s3")

    @staticmethod
    def validate_aws_env_vars() -> None:
        """
        Validate that necessary AWS environment variables are set when S3 usage is enabled.

        Raises
        ------
        ValueError
            If any required AWS environment variable is missing when S3 usage is enabled.
        """
        # Check if S3 usage is enabled from the USE_AWS_S3_BUCKET environment variable
        use_aws_s3_bucket = EnvVariable.USE_AWS_S3_BUCKET
        # If S3 usage is enabled, check that required AWS variables are set
        if use_aws_s3_bucket:
            # Raise an error if AWS_ACCESS_KEY_ID is not set
            if not EnvVariable.AWS_ACCESS_KEY_ID:
                raise ValueError("Environment variable `AWS_ACCESS_KEY_ID` must be set when S3 usage is enabled.")
            # Raise an error if AWS_SECRET_ACCESS_KEY is not set
            if not EnvVariable.AWS_SECRET_ACCESS_KEY:
                raise ValueError("Environment variable `AWS_SECRET_ACCESS_KEY` must be set when S3 usage is enabled.")
            # Raise an error if AWS_BUCKET_NAME is not set
            if not EnvVariable.AWS_BUCKET_NAME:
                raise ValueError("Environment variable `AWS_BUCKET_NAME` must be set when S3 usage is enabled.")

    def _create_session(self) -> boto3.session.Session:
        """
        Create a boto3 session using the provided AWS credentials.

        Returns
        -------
        boto3.session.Session
            A boto3 session that allows interaction with AWS services.
        """
        # Create a boto3 session for interacting with AWS services
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key)
        return session

    def list_objects(self) -> List[str]:
        """
        Retrieve a list of keys for objects stored in the S3 bucket.

        Returns
        -------
        List[str]
            A list containing the keys of objects stored in the S3 bucket.
        """
        # Create a reusable Paginator
        paginator = self.s3_client.get_paginator('list_objects_v2')
        # Create a PageIterator from the Paginator
        page_iterator = paginator.paginate(Bucket=self.bucket_name)
        # Initialize an empty list to store the object keys
        object_keys = []
        # Retrieve a list of objects from the S3 bucket
        for page in page_iterator:
            # Check if the response contains any objects
            if "Contents" in page:
                # Iterate over each object in the response
                for obj in page["Contents"]:
                    # Extract the object key and append it to the list
                    object_keys.append(obj["Key"])
        return object_keys

    def store_object(
            self,
            s3_object_key: Union[str, pathlib.Path],
            data: Union[nx.DiGraph, gpd.GeoDataFrame]) -> None:
        """
        Store an object in the S3 bucket.

        Parameters
        ----------
        s3_object_key : Union[str, pathlib.Path]
            The key under which to store the object in the S3 bucket. If a pathlib.Path object is provided,
            it will be converted to a string representation.
        data : Union[nx.DiGraph, gpd.GeoDataFrame]
            The object or data to be stored.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Check if the provided data is a NetworkX DiGraph object
        if isinstance(data, nx.DiGraph):
            # Serialize the DiGraph object into a byte string using the pickle module
            body = pickle.dumps(data)
        else:
            # Convert the data to a JSON string
            body = data.to_json(drop_id=True)
        # Upload the data to the S3 bucket using the provided object key
        self.s3_client.put_object(Bucket=self.bucket_name, Key=s3_object_key, Body=body)
        # Log a message confirming successful storage in the S3 bucket
        log.info(f"Successfully stored `{s3_object_key}` in the S3 bucket.")

    def retrieve_object(
            self, s3_object_key: Union[str, pathlib.Path]) -> Union[nx.DiGraph, xr.Dataset, gpd.GeoDataFrame]:
        """
        Retrieve an object from the S3 bucket.

        Parameters
        ----------
        s3_object_key : Union[str, pathlib.Path]
            The key of the object to be retrieved from the S3 bucket. If a pathlib.Path object is provided,
            it will be converted to a string representation.

        Returns
        -------
        Union[nx.DiGraph, xr.Dataset, gpd.GeoDataFrame]
            The retrieved object or data.
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
                    try:
                        # Extract and convert dataset's CRS spatial reference to EPSG code
                        epsg_code = CRS.from_string(data.crs.spatial_ref).to_epsg()
                    except AttributeError:
                        # Extract and convert dataset's CRS spatial reference to EPSG code
                        epsg_code = CRS.from_string(data.spatial_ref.crs_wkt).to_epsg()
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

        Parameters
        ----------
        s3_object_key : Union[str, pathlib.Path]
            The key of the object to be removed from the S3 bucket. If a pathlib.Path object is provided,
            it will be converted to a string representation.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Delete the object with the provided object key from the S3 bucket
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_object_key)
        # Log a message confirming successful deletion from the S3 bucket
        log.info(f"Successfully deleted '{s3_object_key}' from the S3 bucket.")

    def store_file(
            self,
            s3_object_key: Union[str, pathlib.Path],
            file_path: Union[str, pathlib.Path]) -> None:
        """
        Upload a file to the S3 bucket.

        Parameters
        ----------
        s3_object_key : Union[str, pathlib.Path]
            The key under which to store the file in the S3 bucket. If a pathlib.Path object is provided,
            it will be converted to a string representation.
        file_path : Union[str, pathlib.Path]
            The local file path of the file to be uploaded.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Upload the file at 'file_path' to the S3 bucket with the provided object key
        self.s3_client.upload_file(Bucket=self.bucket_name, Key=s3_object_key, Filename=file_path)
        # Log a message confirming successful storage in the S3 bucket
        log.info(f"Successfully stored `{s3_object_key}` in the S3 bucket.")

    def retrieve_file(
            self,
            s3_object_key: Union[str, pathlib.Path],
            file_path: Union[str, pathlib.Path]) -> None:
        """
        Download a S3 object to a local file.

        Parameters
        ----------
        s3_object_key : Union[str, pathlib.Path]
            They key of the object to download from the S3 bucket. If a pathlib.Path object is provided,
            it will be converted to a string representation.
        file_path : Union[str, pathlib.Path]
            The local file path where the downloaded S3 object will be saved.
        """
        # Check if the provided s3_object_key is a pathlib.Path object
        if isinstance(s3_object_key, pathlib.Path):
            # Convert the pathlib.Path object to a string representation
            s3_object_key = s3_object_key.as_posix()
        # Get the parent directory of the specified file path
        file_directory = pathlib.Path(file_path).parent
        # Create the directory if it doesn't exist
        file_directory.mkdir(parents=True, exist_ok=True)
        # Download the object/file from the S3 bucket to the specified local path
        self.s3_client.download_file(Bucket=self.bucket_name, Key=s3_object_key, Filename=file_path)
        # Log a message confirming successful download from the S3 bucket
        log.info(f"Successfully downloaded `{s3_object_key}` from the S3 bucket.")

    def clear_bucket(self) -> None:
        """Clear the entire S3 bucket by removing all objects."""
        # Access the S3 bucket
        bucket = self.s3_resource.Bucket(self.bucket_name)
        # Delete all objects within the bucket
        for obj in bucket.objects.all():
            obj.delete()
        # Log a message confirming successful removal of all objects from the S3 bucket
        log.info("Successfully removed all objects from the S3 bucket.")
