import boto3
from collections import defaultdict
import chromadb
from chromadb.utils import embedding_functions
import openai
import time
import json
from Ovadrive.dynamodb import ID_Mapper
i=0
dynamo = ID_Mapper()
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key="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",
                model_name="text-embedding-ada-002"
            )
client = chromadb.HttpClient(host="18.209.34.195", port=8000, headers={"X-Chroma-Token":"sk-mytoken"})

# dynamo.id_scan("USER_ID_COLLECTION","Test")
# print(dynamo.id_scan("USER_ID_COLLECTION","Test"))
def delete_collection(name):
    # collection = client.get_or_create_collection("jatin",embedding_function=openai_ef)
    try:
        print("COLLECTION DELETED:",name)
        client.delete_collection(name)
    except Exception as e:
        print(e)
# Configuration variables
AWS_REGION = 'us-east-1'
COGNITO_USER_POOL_ID = 'us-east-1_LhhcoroCf'
S3_BUCKET_NAME = 'ovadrive'

# Initialize AWS clients
cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

def list_cognito_users(user_pool_id):
    users = []
    pagination_token = None
    while True:
        kwargs = {'UserPoolId': user_pool_id}
        if pagination_token:
            kwargs['PaginationToken'] = pagination_token
        response = cognito_client.list_users(**kwargs)
        users.extend(response['Users'])
        pagination_token = response.get('PaginationToken')
        if not pagination_token:
            break
    return users

def get_s3_file_last_modified(bucket_name, user_sub):
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=user_sub)
    for obj in response.get('Contents', []):
        if obj['Key'] == user_sub:
            return obj['LastModified']
    return None

def delete_cognito_user(user_pool_id, username):
    
    try:
        cognito_client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=username
        )
        print(f"DELETED {username}")
    except Exception as e:
        print(e)

    

def delete_s3_file(bucket_name, key):
    
    try:
        
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        print(f"DELETED S3 bucket:",key)
    except Exception as e:
        print(e)

def deduplicate_users(users, bucket_name, user_pool_id):
    email_to_users = defaultdict(list)
    for user in users:
        for attr in user['Attributes']:
            if attr['Name'] == 'email':
                email = attr['Value']
                sub = next((a['Value'] for a in user['Attributes'] if a['Name'] == 'sub'), None)
                if sub:
                    last_modified = get_s3_file_last_modified(bucket_name, sub)
                    email_to_users[email].append((user, sub, last_modified))
                break

    for email, user_infos in email_to_users.items():
        if len(user_infos) > 1:
            # Sort by last modified to retain the latest
            user_infos.sort(key=lambda x: x[2] or 0, reverse=True)
            to_keep = user_infos[0]
            to_delete = user_infos[1:]
            for user, sub, _ in to_delete:
                # print("RECORD ",i)
                delete_cognito_user(user_pool_id, user['Username'])
                delete_s3_file(bucket_name, f'assistants/{sub}_object.joblib')
                delete_collection(sub)
            print(f"Retained {to_keep[1]} for {email}, deleted {[u[1] for u in to_delete]}")

# Example usage
users = list_cognito_users(COGNITO_USER_POOL_ID)
deduplicate_users(users, S3_BUCKET_NAME, COGNITO_USER_POOL_ID)
