import pathlib
import pickle
from io import BytesIO

import boto3
import geopandas as gpd
import networkx as nx

from src import config


class S3Manager:
    """
    A class to manage connections to AWS S3 bucket.
    """

    def __init__(self):
        """
        Initializes the S3Manager with AWS credentials and bucket name.
        """
        self.access_key_id = config.get_env_variable("AWS_ACCESS_KEY_ID")
        self.secret_access_key = config.get_env_variable("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = config.get_env_variable("AWS_BUCKET_NAME")
        self.session = self._create_session()
        self.s3 = self.session.client("s3")

    def _create_session(self):
        """
        Creates and returns a boto3 session with the provided AWS credentials.
        """
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key)
        return session

    def list_object_keys(self):
        """
        Lists objects in the AWS S3 bucket.
        """
        resp = self.s3.list_objects_v2(Bucket=self.bucket_name)
        object_keys = []
        if "Contents" in resp:
            for obj in resp["Contents"]:
                object_keys.append(obj["Key"])
        return object_keys

    def store_object(self, s3_object_key, data):
        if isinstance(s3_object_key, pathlib.Path):
            s3_object_key = s3_object_key.as_posix()
        if isinstance(data, nx.DiGraph):
            body = pickle.dumps(data)
        else:
            body = data.to_json(drop_id=True)
        self.s3.put_object(Bucket=self.bucket_name, Key=s3_object_key, Body=body)

    def retrieve_object(self, s3_object_key):
        resp = self.s3.get_object(Bucket=self.bucket_name, Key=s3_object_key)
        body = resp["Body"].read()
        if s3_object_key.endswith(".pickle"):
            data = pickle.loads(body)
        else:
            data = gpd.read_file(BytesIO(body))
        return data

    def remove_object(self, s3_object_key):
        self.s3.delete_object(Bucket=self.bucket_name, Key=s3_object_key)

    def clear_bucket(self):
        """
        Clear objects in the AWS S3 bucket.
        """
        bucket = self.s3.Bucket(self.bucket_name)
        bucket.objects.all().delete()



