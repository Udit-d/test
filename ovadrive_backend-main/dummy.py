import boto3
boto3.setup_default_session(region_name="us-east-1")
from Ovadrive.dynamodb import ID_Mapper
from Ovadrive.bucket import S3
from collections import Counter
import chromadb
from chromadb.utils import embedding_functions
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key="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",
                model_name="text-embedding-ada-002"
            )
client = chromadb.HttpClient(host="18.209.34.195", port=8000, headers={"X-Chroma-Token":"sk-mytoken"})
s3 = S3()
# Initialize the Cognito client
cognito_client = boto3.client('cognito-idp', region_name='us-east-1')
dynamo = ID_Mapper()
table_name = "USER_ID_COLLECTION_FIREBASE"
ssm = boto3.client('ssm', region_name='us-east-1')
stream = 'Live'
# openai.api_key = ssm.get_parameter(Name='OVADRIVE_OPENAI_API_KEY', WithDecryption=True)['Parameter']['Value']
# try:
#     dynamo.create_table(table_name, stream)
#     # ids = dynamo.id_scan(table_name, stream)
# except Exception as e:
#     print(f"Error with DynamoDB operation: {e}")

# Define the user pool ID
user_pool_id = 'us-east-1_LhhcoroCf'

# Define the pagination parameters
pagination_token = None
users = []

# Paginate through the list of users
while True:
    if pagination_token:
        response = cognito_client.list_users(
            UserPoolId=user_pool_id,
            PaginationToken=pagination_token
        )
    else:
        response = cognito_client.list_users(UserPoolId=user_pool_id)
    
    users.extend(response['Users'])
    
    if 'PaginationToken' in response:
        pagination_token = response['PaginationToken']
    else:
        break

# Extract sub (user IDs) and emails
user_data = [(next(attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'sub'), 
              next(attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'email')) for user in users]

# emails = [email for user_id,email in user_data]
# email_count = Counter(emails)
# for email,count in email_count.items():
#     if count>1:
#         print(email)
# Print sub (user IDs) and emails
for user_id, email in user_data:
    print(f"User ID (sub): {user_id}, Email: {email}")
    username = [email]
    user = email.split('@')[0]
    try:
        my_collection = client.get_collection(
                name=user,
                embedding_function=openai_ef,
            )
        print(f"Got Collection {user}")
        # results = my_collection.get(
        #     include = ["documents","metadatas"]
        # )
        my_collection.modify(name=username[0])
        print(f"Modified collection name of {user} ot {username[0]}")
        # print("Got data")
        # collection_to_create = client.create_collection(
        #         name=username[0],
        #         embedding_function=openai_ef,
        #         metadata={"hnsw:space": "cosine"}
        #     )
        # print(f"Created new collection {username}")
        # collection_to_create.add(
        #     ids=results["ids"],
        #     documents=results["documents"],
        #     metadatas=results["metadatas"]
        # )
        # print("Added to new collection")
    except Exception as e:
        print(e)

    # assistant_path = f'assistants/{user_id}_object.joblib'
    # assistant_firebase_path = f'assistants_firebase/{username[0]}_object.joblib'
    # try:
    #     s3.download(assistant_path, stream='Live', save_as=assistant_path)
    #     print(assistant_path, " downloaded")
    # except Exception as e:
    #     print(f"Error downloading from S3: {e}")
    
    
    # try:
    #     s3.upload(assistant_path, user_id=user_id, store_as=assistant_firebase_path)
    #     print(assistant_firebase_path, " uploaded")
    # except Exception as e:
    #     print(f"Error downloading from S3: {e}")
    # dynamo.append(id={"user_id":username[0],"path":assistant_firebase_path},table_name=table_name)
    # print("Id appended to dynamo",{"user_id":username[0],"path":assistant_firebase_path})



