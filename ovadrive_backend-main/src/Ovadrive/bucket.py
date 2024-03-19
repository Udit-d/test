import boto3
from Ovadrive import logger
from botocore.exceptions import NoCredentialsError, ClientError





class S3:
    """
    A class to handle basic S3 operations such as uploading, downloading, and deleting objects.
    """

    def __init__(self, bucket_name : str ='ovadrive') -> None:
        """
        Initializes the S3 client and sets the bucket name.

        Args:
            bucket_name (str): The name of the S3 bucket to be used.
        """
        # AWS credentials should be set in environment variables or IAM roles
        self.client = boto3.client('s3', region_name='us-east-1')
        self.bucket_name = "ovadrive"
        
        
        
    def upload(self, file_path: str, user_id : str, store_as: str = None) -> None:
        """
        Uploads a file to the specified S3 bucket.

        Args:
            file_path (str): The local path to the file.
            store_as (str, optional): The key under which to store the file in the bucket.
        """
        try:
            if store_as is None:
                store_as = file_path
            self.client.upload_file(file_path, self.bucket_name, store_as)
            logger.info(f"File {file_path} uploaded to {self.bucket_name} as {store_as}", user_id)
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Upload failed: {e}", user_id)
        
        
        
    def download(self, object_name: str, stream : str, save_as: str = None) -> None:
        """
        Downloads an object from S3.

        Args:
            object_name (str): The key of the object to download.
            save_as (str, optional): The local path to save the file to.
        """
        try:
            if save_as is None:
                save_as = object_name
            self.client.download_file(self.bucket_name, object_name, save_as)
            logger.info(f"Object {object_name} downloaded from {self.bucket_name} as {save_as}", stream)
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Download failed: {e}", stream)
    
    
    
    def delete(self, object_name: str, user_id : str) -> None:
        """
        Deletes an object from S3.

        Args:
            object_name (str): The key of the object to delete.
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Object {object_name} deleted from {self.bucket_name}", user_id)
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Delete failed: {e}", user_id)

    
            
            
            
# if __name__ == "__main__":
#     s3 = S3()
#     s3.upload("src\Ovadrive\\bucket.py", store_as='assistants/bucket.py')
#     s3.delete('assistants/bucket.py')