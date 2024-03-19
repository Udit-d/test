import boto3
from boto3.dynamodb.conditions import Key
from Ovadrive import logger  # Assuming logger is set up correctly





class ID_Mapper:
    """
    A class to handle interactions with a DynamoDB table for storing and retrieving user IDs.
    """

    def __init__(self) -> None:
        # Use AWS credentials from environment variables or IAM roles
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.ddb_exceptions = boto3.client('dynamodb', region_name='us-east-1').exceptions



    def create_table(self, table_name: str, stream : str) -> None:
        """
        Creates a DynamoDB table for storing user IDs.

        Args:
            table_name (str): The name of the table to be created.
        """
        try:
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
                ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10}
            )
            logger.info("Creating table", stream)
            # print("Creating table")
            waiter = self.dynamodb.meta.client.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            logger.info("Table created", stream)
            # print("Table created")

        except self.ddb_exceptions.ResourceInUseException:
            logger.info("Table already exists", stream)
            # print("Table already exists")



    def id_scan(self, table_name: str, stream : str) -> list:
        """
        Retrieves a list of user IDs from the DynamoDB table.

        Args:
            table_name (str): The name of the DynamoDB table.

        Returns:
            list: A list of user IDs.
        """
        try:
            table = self.dynamodb.Table(table_name)
            response = table.scan()
            return [item["user_id"] for item in response["Items"]]
        except Exception as e:
            logger.error(f"Error scanning table: {e}", stream)
            return []



    def append(self, id: dict, table_name: str) -> None:
        """
        Appends a new item to the DynamoDB table.

        Args:
            id (dict): The item to be added to the table.
            table_name (str): The name of the DynamoDB table.
        """
        try:
            table = self.dynamodb.Table(table_name)
            table.put_item(Item=id)
        except Exception as e:
            logger.error(f"Error appending item to table {table_name}: {e}", id)



    def assistant_path_loader(self, user_id: str, table_name: str) -> str:
        """
        Retrieves the assistant path for a given user ID from the DynamoDB table.

        Args:
            user_id (str): The user's unique identifier.
            table_name (str): The name of the DynamoDB table.

        Returns:
            str: The assistant path associated with the user ID.
        """
        try:
            table = self.dynamodb.Table(table_name)
            response = table.query(KeyConditionExpression=Key('user_id').eq(user_id))
            return response["Items"][0]['path']
        except Exception as e:
            logger.error(f"Error loading assistant path for user {user_id}: {e}", user_id)
            return ""



    def delete_item(self, user_id: str, table_name: str) -> None:
        """
        Deletes an item from the DynamoDB table.

        Args:
            user_id (str): The user's unique identifier to be deleted.
            table_name (str): The name of the DynamoDB table.
        """
        try:
            table = self.dynamodb.Table(table_name)
            table.delete_item(Key={'user_id': user_id})
        except Exception as e:
            logger.error(f"Error deleting item for user {user_id} from table {table_name}: {e}", user_id)