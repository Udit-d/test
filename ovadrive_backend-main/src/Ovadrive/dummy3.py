import boto3
from collections import defaultdict

# Initialize AWS clients
cognito_client = boto3.client('cognito-idp', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')
amplify_client = boto3.client('amplify', region_name='us-east-1')

def list_cognito_users():
    # Retrieve all users from Cognito
    users = []
    pagination_token = None
    while True:
        if pagination_token:
            response = cognito_client.list_users(
                UserPoolId='us-east-1_LhhcoroCf',
                PaginationToken=pagination_token
            )
        else:
            response = cognito_client.list_users(UserPoolId='us-east-1_LhhcoroCf')
        
        users.extend(response['Users'])
        
        if 'PaginationToken' in response:
            pagination_token = response['PaginationToken']
        else:
            break
    
    # print('users')
    return users

def list_s3_files(bucket_name):
    # List objects in the bucket
    response = s3_client.list_objects_v2(Bucket=bucket_name)

    # Check if the bucket contains any objects
    if 'Contents' in response:
        # Extract file names and last modified timestamps
        files = [{'Key': ((obj['Key'].split('/'))[1]).split('_')[0], 'LastModified': obj['LastModified']} for obj in response['Contents']]
        # files = [response['Contents']]
        # print("Files:",files)
        return files
    else:
        return []

def delete_s3_files(bucket_name, keys_to_delete):
    print("DELETING S3 FILES:", keys_to_delete)
    # Delete objects from the bucket
    # for key in keys_to_delete:
    #     s3_client.delete_object(Bucket=bucket_name, Key=key)

def update_cognito_user(user_pool_id, username_to_keep):
    # Update user attributes in Cognito
    # cognito_client.admin_update_user_attributes(
    #     UserPoolId=user_pool_id,
    #     Username=username_to_keep,
    #     UserAttributes=[
    #         {
    #             'Name': 'preferred_username',
    #             'Value': username_to_keep
    #         }
    #     ]
    # )
    print(f"UPDATING {username_to_keep}")

def remove_redundant_users_amplify(email, usernames_to_delete):
    # Get the latest modified username associated with the email
    latest_username = None
    for user, user2 in list_cognito_users(),list_s3_files('ovadrive'):
        if next((attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'email'), None) == email:
            if latest_username is None or user2['LastModified'] > latest_username['LastModified']:
                latest_username = user
    
    # Retain only the latest username in the list of usernames to delete
    usernames_to_delete = [username for username in usernames_to_delete if username != latest_username['Username']]
    
    # Remove redundant users from Amplify
    for username in usernames_to_delete:
        try:
            # amplify_client.delete_user(username=username)
            print(f"Removed user {username} from Amplify for email {email}")
        except Exception as e:
            print(f"Failed to remove user {username} from Amplify: {str(e)}")

def process_users_with_duplicates(users):
    # Group users by email
    email_to_users = defaultdict(list)
    for user in users:
        email = next(attr['Value'] for attr in user['Attributes'] if attr['Name'] == 'email')
        email_to_users[email].append(user)
    
    # Process users with duplicate emails
    for email, users in email_to_users.items():
        if len(users) > 1:
            # Sort users by last modified timestamp of associated S3 file
            users.sort(key=lambda user: user['LastModified'], reverse=True)
            user_to_keep = users[0]  # Keep the user with the latest S3 file modification
            usernames_to_delete = [user['Username'] for user in users[1:]]  # Delete other users
            keys_to_delete = [user['Username'] for user in users[1:]]  # Keys to delete in S3

            # Delete extra files from S3
            delete_s3_files('ovadrive', keys_to_delete)

            # Update user in Cognito
            update_cognito_user('us-east-1_LhhcoroCf', user_to_keep['Username'])

            # Remove redundant users from Amplify
            remove_redundant_users_amplify(email, usernames_to_delete)

            # Print info
            print(f"For email {email}, kept user {user_to_keep['Username']} and deleted users {usernames_to_delete}")

# Retrieve users from Cognito
users = list_cognito_users()
print(users)

# Process users with duplicate emails
# process_users_with_duplicates(users)
