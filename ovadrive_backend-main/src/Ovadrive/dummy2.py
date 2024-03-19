import boto3

# Initialize a boto3 client
cognito_client = boto3.client('cognito-idp')

# Specify your user pool ID here
user_pool_id = 'us-east-1_LhhcoroCf'

# Specify the user's email or username
target_email = 'sharmajatin567@gmail.com'

def get_username_by_email(user_pool_id, email):
    try:
        # List users in the user pool by the specified email
        response = cognito_client.list_users(
            UserPoolId=user_pool_id,
            Filter=f'email = "{email}"',
            Limit=1
        )
        
        # Extract the username if a user is found
        if response and response['Users']:
            username = response['Users'][0]['Username']
            return username
        else:
            return None
    except Exception as e:
        print(f"Error fetching user by email: {e}")
        return None

# Example usage
username = get_username_by_email(user_pool_id, target_email)
if username:
    print(f"Username for email {target_email} is: {username}")
else:
    print(f"No user found for email {target_email}")