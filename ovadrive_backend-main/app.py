import boto3

# Set up a Boto3 session with the specified region
boto3.setup_default_session(region_name="us-east-1")

cognito_client = boto3.client('cognito-idp', region_name='us-east-1')

from flask import Flask, request, jsonify
import json
import openai
from Ovadrive.llm import Assistant
from Ovadrive.dynamodb import ID_Mapper
from Ovadrive.bucket import S3
from Ovadrive import logger
import dill
import threading
import time as t
import os
import datetime




# Initialize Flask application
app = Flask(__name__)


# Setting default error stream: Test/Live
stream = "Live"


# Initialize DynamoDB mapper and create a table for user IDs
dynamo = ID_Mapper()
table_name = "USER_ID_COLLECTION"
ssm = boto3.client('ssm', region_name='us-east-1')
openai.api_key = ssm.get_parameter(Name='OVADRIVE_OPENAI_API_KEY', WithDecryption=True)['Parameter']['Value']
try:
    dynamo.create_table(table_name, stream)
    ids = dynamo.id_scan(table_name, stream)
except Exception as e:
    logger.error(f"Error with DynamoDB operation: {e}", stream)


# Initialize S3 bucket connection
s3 = S3()


# Downloading assistant objects for each user from S3 a nd store locally
for d in ids:
    assistant_path = f'assistants/{d}_object.joblib'
    try:
        s3.download(assistant_path, stream=stream, save_as=assistant_path)
    except Exception as e:
        logger.error(f"Error downloading from S3: {e}", stream)
    logger.info("Downloading Joblibs...: " + assistant_path, stream)
    
    
# Server coming live
logger.info("Server is Live!", stream)


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

emails_mapping = {email:user_id for user_id,email in user_data}
emails = [email for user_id,email in user_data]


# Flask route to handle AI requests
@app.route('/ai', methods=['POST'])
def handle_ai_request():    
    """
    Handles AI-related requests and manages conversation history for the user.

    This endpoint accepts a JSON payload containing user input and other
    contextual information necessary to process the AI response. It manages
    conversation states and interacts with an AI model to generate appropriate
    responses based on the conversation history.

    The endpoint expects the following data in the request:
    - text: The user's input text.
    - conversation_status: The status of the conversation indicating the type of processing required.
    - time: The timestamp of the user's message.
    - date: The date of the user's message.
    - user_id: A unique identifier for the user.

    Returns:
        - A JSON response containing the AI's response content and relevant HTTP status code.

    In case of missing data, a FileNotFoundError, or an unexpected exception,
    the endpoint will return an appropriate error message with the corresponding
    HTTP status code.
    
    Raises:
        - FileNotFoundError: If the assistant's state file is not found.
        - ValueError: If there is missing or invalid data in the request.
        - Exception: For any other unexpected errors during processing.
    """
    try:
        data = request.json
        
        # Extracting various data from the POST request
        user_input = data.get('text', '')
        status = data.get("conversation_status", '')
        time = data.get("time", '')
        date = data.get("date", '')
        user_id = data.get('user_id', '')
        timezone = data.get('timezone', '')

        # Ensure all necessary information is provided
        if not all([user_input, status, time, date, user_id]):
            raise ValueError("Missing data in request.")

        # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)

        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)
        
        response_data = {}

        # Handling different conversation statuses
        if status == "-1":
            # Status -1: Adding data to the conversation history
            transcriptions = []
            ids = []
            ai.context_message = ""
            for data in user_input:
                add_data = {
                    "conversation_key": {
                        "human": "",
                        "bot": ""
                    },
                    "statement": data["text"],
                    "date": data["date"],
                    "time": data["time"]
                }
                transcriptions.append(add_data)
                ids.append(data["id"])
                ai.messages.append({"role":"user", "content":data["text"]})
                
                ai.context_message += " " + data["text"]
    
            if transcriptions:
                ai.add_to_db(transcriptions, ids, user_id)
            ai.generate_summary(datetime.datetime.now(tz = ai.timezone),user_id)
            try:
                phone_messages = [{"role":"system","content":'''
                You will be provided with a text which might contain a phone number mentioned by user who spoke that text.You have to give an output in JSON format.  Analyze the ttext and follow these steps:\n
                1. If a phone number is mentioned in the text, provide the phone number in numerical digits format in the key "phone_number". The text is a speech transcription so it might contain numbers in the form of words. Convert them to digits and output in numerical format only in the key "phone_number". If no phone number is present, output the string "false" in the key "phone_number". \n
                2. If the name of the person who provided the contact number is present in the text, output the name in the key "name". Output the string "false" in the key "name" if no name is present in the text.
                3. Output a short description of the text in the key "notes". \n
                4. If you feel like the user is speaking wrong facts about something, or if you think the user needs some assistance, output the string "true" in the key "assistance", else output the string "false" in the key "assistance".
                Always give output in JSON format.
                '''}]
                phone_messages.append({"role":"user","content":f"{ai.context_message}"})
                response = openai.ChatCompletion.create(
                            messages=phone_messages,
                            model="gpt-3.5-turbo-1106",
                            response_format = {"type":"json_object"}
                        )
                try:
                    ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
                except:
                    ai.gpt3cost = 0
                arguments = json.loads(response["choices"][0]["message"]["content"])
                # print(arguments)
            except:
                arguments = {"phone_number":"false"}
                # print(arguments)
            
            
            logger.info(f"Message Added: {user_input}", user_id)
            # print(f"Message Added: {user_input}")
            with open(assistant_path, 'wb') as f:
                dill.dump(ai, f)
    
            s3.upload(assistant_path, user_id=user_id, store_as=assistant_path)
            if (arguments["phone_number"]):
                if (arguments["phone_number"] == 'false' and arguments["assistance"] == "false"):
                    # print("Arguments not present")
                    response_data["content"] = {"content":"Saved"}
                elif (arguments["phone_number"] != 'false'):
                    # print("Returned correct arguments")
                    response_data["content"] = {"content":"extract_phone_number","arguments":arguments}
                elif (arguments["assistance"] == "true" and arguments["phone_number"] == 'false'):
                    ai_response = ai.generate_prompt(ai.context_message,user_id)
                    response_data["content"] = {"content":"assistance","arguments": ai_response["content"]}
                else:
                    response_data["content"] = {"content":"Saved"}
            else:
                response_data["content"] = {"content":"Saved"}

        elif status == "1":
            # Status 1: Handling ongoing conversations
            ai.context_message += " " + user_input[0]["text"]
            answer = ai.generate_prompt(user_input[0]["text"], user_id)
    
            add_data = {
                "conversation_key": {
                    "human": user_input[0]["text"],
                    "bot": answer["content"]
                },
                "statement": "",
                "date": date,
                "time": time
            }
    
            # Adding new data to the database in a separate thread for efficiency
            add_to_database = threading.Thread(target=ai.add_to_db([add_data], [user_input[0]["id"]], user_id))
            add_to_database.start()
    
            with open(assistant_path, 'wb') as f:
                dill.dump(ai, f)
            s3.upload(assistant_path, user_id=user_id, store_as=assistant_path)
            add_to_database.join()
            response_data["content"] = answer
            logger.info(f"Response: {response_data}", user_id)
            # print(f"Response: {response_data}")
            
        # elif status == "2":
        #     ai.context_message += " " + user_input
        #     # Generate response and update conversation key
        #     answer = ai.execute_function(user_input)
        #     # if answer["status"]=="text":
        #     #     add_data = {
        #     #         "conversation_key": {
        #     #             "human": user_input,
        #     #             "bot": answer["content"]
        #     #         },
        #     #         "statement": "",
        #     #         "date": date,
        #     #         "time": time
        #     #     }
        #     #     ai.add_to_db(add_data)
        #         # convo = load_conversations() + ai.convos
        #         # save_conversations(convo)
        #     with open(assistant_path, 'wb') as f:
        #         dill.dump(ai, f)
        #     s3.upload(assistant_path, user_id=user_id, store_as=assistant_path)
        #     response_data["content"] = answer
        #     # else:
        #     #     response_data = answer
            
        else:
            # Handling any unaddressed statuses
            response_data['content'] = "Unhandled status"

        return jsonify(response_data)
    
    except FileNotFoundError:
        logger.error(f"Assistant file not found for user: {user_id}", user_id)
        # print(f"Assistant file not found for user: {user_id}")
        logger.info(f"Creating assistant file for user: {user_id}",user_id)
        assistant_path = f'assistants/{user_id}_object.joblib'
        # Append new user to DynamoDB if not already present
        if user_id not in ids:
            dynamo.append(id={"user_id": user_id, "path": assistant_path}, table_name=table_name)
            ids.append(user_id)
            ai = Assistant(user_id, timezone)
        with open(assistant_path, 'wb') as f:
            dill.dump(ai, f)
        s3.upload(assistant_path, user_id=user_id, store_as=assistant_path)

        return jsonify({'content': {'content': 'Error: Assistant file not found'}}), 404
    except ValueError as e:
        logger.error(f"Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500







@app.route('/initialize', methods=['POST'])
def initialize_assistant():
    """
    Initializes a new assistant instance for a user with a given user ID and timezone.

    This endpoint accepts a JSON payload with 'user_id' and 'timezone' which are used
    to create and configure a new Assistant instance. The initialized Assistant is
    then saved to a file and uploaded to an S3 bucket for persistence.

    It also ensures the new user is recorded in a DynamoDB table, which keeps track of
    all users and their corresponding assistant file paths.

    Returns:
        - A JSON response with the user ID to confirm successful initialization or
          an error message with an appropriate HTTP status code.

    Raises:
        - ValueError: If 'user_id' or 'timezone' is missing from the request data.
        - IOError: If there's an error in file operations, such as saving the assistant.
        - Exception: For any other unexpected errors during the process.
    """
    
    try:
        data = request.json
        user_id = data.get('user_id')
        timezone = data.get('timezone')
        email = data.get('email')
        if not user_id or not timezone:
            raise ValueError("Missing user_id or timezone in request data.")
        try: 
            if email:
                if email in emails:
                    
                    
                
                    old_id = emails_mapping[email]
                    logger.info(f"Found older id with email {email} and collection {emails_mapping[email]}",old_id)
                    
                    old_path = f'assistants/{old_id}_object.joblib'
                    new_path = f'assistants/{user_id}_object.joblib'
                    with open(old_path,'rb') as f:
                        ai = dill.load(f)
                    ai.collection.modify(name = user_id)
                    logger.info(f"Modified collection name for {email} from {old_id} to {user_id}", old_id)
                    logger.info(f"Modified collection name for {email} from {old_id} to {user_id}", user_id)
                    with open(new_path,'wb') as f:
                        dill.dump(ai,f)
                    

                    s3.upload(file_path=new_path,user_id=user_id,store_as=new_path)
                    s3.delete(old_path,old_id)



                    dynamo.delete_item(user_id=old_id,table_name=table_name)
                    dynamo.append(id={"user_id":user_id,"path":new_path},table_name=table_name)

                    ids.remove(old_id)
                    ids.append(user_id)
                    
                    emails.remove(email)
                    del emails_mapping[email]
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
                    except Exception as e:
                        username = None
                    # Example usage
                    if username is not None:
                        cognito_client.admin_delete_user(
                            UserPoolId=user_pool_id,
                            Username=username
                        )
                        logger.info(f"DELETED {username}",old_id)
                        logger.info(f"DELETED {username}",user_id)
                    else:
                        pass
                        # print(f"No username found for {email}")

        except Exception as e:
            logger.error(f"Failed to migrate to Firebase: {e}",old_id)
                
                






        # Create a new Assistant instance and save it
        
        # ai = Assistant(user_id, timezone)
        
        assistant_path = f'assistants/{user_id}_object.joblib'
        
        

        # Append new user to DynamoDB if not already present
        if user_id not in ids:
            dynamo.append(id={"user_id": user_id, "path": assistant_path}, table_name=table_name)
            ids.append(user_id)
            ai = Assistant(user_id, timezone)
        else:
            try:
                with open(assistant_path, 'rb') as f:
                    ai = dill.load(f)
            except:
                ai = Assistant(user_id, timezone)
            ai.messages = [ai.messages[0]]
            result = ai.collection.get(
                include=["documents"]
            )
            ids_data = result["ids"]
            if len(ids_data) >= 20:
                final_result = [json.loads(res) for res in result["documents"][-20:]]
            else:
                final_result = [json.loads(res) for res in result["documents"]]

            for res in final_result:
                if res["statement"] == "":
                    ai.messages.extend([{"role":"user","content":res["conversation_key"]["human"]},{"role":"assistant","content":res["conversation_key"]["bot"]}])
                else:
                    ai.messages.append({"role":"user","content":res["statement"]})
            ai.generate_summary(datetime.datetime.now(tz = ai.timezone),user_id)
                


        with open(assistant_path, 'wb') as f:
            dill.dump(ai, f)
        
        s3.upload(assistant_path, user_id=user_id, store_as=assistant_path)
        return jsonify({'content': user_id})

    except ValueError as e:
        logger.error(f"Line : 293 Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except IOError as e:
        logger.error(f"Line 296 File I/O error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: File operation failed'}}), 500
    except Exception as e:
        logger.error(f"Line 299 An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500







@app.route('/fetchchats', methods=['POST'])
def fetchchats():
    """
    Fetches the chat history for a user based on a specific date and status.

    This endpoint expects a JSON payload with 'date', 'user_id', and 'status'.
    It retrieves the chat history from the user's assistant object, differentiating
    between Ova's conversation history and the Drive's conversation history.

    Depending on the 'status' provided in the request, the endpoint will return
    the history relevant to either Ova's view or Drive's view.

    Args:
        date (str): The date for which to fetch the conversation history.
        user_id (str): The unique identifier for the user whose conversation history is being fetched.
        status (str): The requested view of the conversation history, 'ova' for Ova's view or
                      any other string for Drive's view.

    Returns:
        - A JSON response containing the requested conversation history or an error message
          with an appropriate HTTP status code.

    Raises:
        - FileNotFoundError: If the assistant file for the user is not found.
        - ValueError: If any of the required data is missing from the request.
        - Exception: For any other unexpected errors during the process.
    """
    response_data = {}
    try:
        data = request.json
        date = data.get("date")
        user_id = data.get('user_id')
        status = data.get("status")

        if not all([date, user_id, status]):
            raise ValueError("Missing required data in request.")

        # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)
        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)

        # Fetch chat history from the database
        results = ai.collection.get(    
                        where={"date":date},
                        include=["documents"]
                    )
        if results == []:
            return jsonify({"content":[]})
        # result_json = [json.loads(result) for result in results["documents"]]
        # result_ova = []  # Ova's conversation history
        # result_drive = []  # Drive's conversation history

        # # Segregating data based on whether it's a statement or a conversation
        # for result in result_json:
        #     if result["statement"] == "":
        #         # Handling conversation data
        #         user = {
        #             "type": "User",
        #             "message": result["conversation_key"]["human"],
        #             "time": result["date"] + " " + result["time"]
        #         }
        #         result_ova.append(json.dumps(user))
        #         ova = {
        #             "type": "Ova",
        #             "message": result["conversation_key"]["bot"],
        #             "time": result["date"] + " " + result["time"]
        #         }
        #         result_ova.append(json.dumps(ova))
        #         result_drive.append(json.dumps(user))
        #     else:
        #         # Handling statement data
        #         user = {
        #             "type": "User",
        #             "message": result["statement"],
        #             "time": result["date"] + " " + result["time"]
        #         }
        #         result_drive.append(json.dumps(user))
        result_json = []
        for i in range(len(results["ids"])):
            result_json.append([results["ids"][i],json.loads(results["documents"][i])])
        result_ova = []  # Ova's conversation history
        result_drive = []  # Drive's conversation history

        # Segregating data based on whether it's a statement or a conversation
        for result in result_json:
            if result[1]["statement"] == "":
                # Handling conversation data
                user = {
                    "type": "User",
                    "message": result[1]["conversation_key"]["human"],
                    "time": result[1]["date"] + " " + result[1]["time"],
                    "audio":result[0]
                }
                result_ova.append(json.dumps(user))
                ova = {
                    "type": "Ova",
                    "message": result[1]["conversation_key"]["bot"],
                    "time": result[1]["date"] + " " + result[1]["time"],
                    "audio":result[0]
                }
                result_ova.append(json.dumps(ova))
                result_drive.append(json.dumps(user))
            else:
                # Handling statement data
                user = {
                    "type": "User",
                    "message": result[1]["statement"],
                    "time": result[1]["date"] + " " + result[1]["time"],
                    "audio":result[0]
                }
                result_drive.append(json.dumps(user))
        # Returning the conversation history based on the requested status
        if status == "ova":
            response_data = {"content": result_ova}
        else:
            response_data = {"content": result_drive}

        return jsonify(response_data)

    except FileNotFoundError:
        logger.error(f"Assistant file not found for user: {user_id}", user_id)
        return jsonify({'content': {'content': 'Error: Assistant file not found'}}), 404
    except ValueError as e:
        logger.error(f"Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500

        
        
        
        
        
        
@app.route('/delete_data', methods=['POST'])
def delete_data():
    """
    Deletes specific data from the user's assistant collection based on the provided ID.

    This endpoint requires a JSON payload containing the 'user_id' of the assistant and
    the specific 'id' of the data to be deleted. It accesses the user's assistant object
    and performs a deletion operation on the collection.

    Args:
        user_id (str): The unique identifier for the user whose data is to be deleted.
        id (str): The unique identifier of the specific data to be deleted.

    Returns:
        - A JSON response confirming the deletion or an error message with an appropriate
          HTTP status code if the operation fails.

    Raises:
        - FileNotFoundError: If the assistant file for the user is not found.
        - ValueError: If 'user_id' or 'id' is missing from the request data.
        - Exception: For any other unexpected errors during the process.
    """

    try:
        data = request.json
        user_id = data.get("user_id")
        id = data.get("id")

        if not user_id or not id:
            raise ValueError("Missing user_id or id in request data.")

        # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)
        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)
        result = ai.collection.get(ids = [id],include = ["documents"])
        convo = json.loads(result["documents"][0])
        if convo["statement"] == "":
            messages = [x for x in ai.messages if x["content"] not in [convo["conversation_key"]["human"],convo["conversation_key"]["bot"]]]
            ai.messages = [ai.messages[0]]
            ai.messages.extend(messages)
        else:
            messages = [x for x in ai.messages if x["content"] != convo["statement"]]
            ai.messages = [ai.messages[0]]
            ai.messages.extend(messages)
        # Deleting specific data from the collection
        ai.collection.delete(ids=[id])
        with open(assistant_path, 'wb') as f:
            dill.dump(ai, f)

        return jsonify({"content": "deleted"})

    except FileNotFoundError:
        logger.error(f"Assistant file not found for user: {user_id}", user_id)
        return jsonify({'content': {'content': 'Error: Assistant file not found'}}), 404
    except ValueError as e:
        logger.error(f"Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500







@app.route('/delete_account', methods=['POST'])
def delete_account():
    """
    Deletes a user's account and all associated data from the system.

    This endpoint accepts a JSON payload with 'user_id' to identify the user account to delete.
    It performs several operations: deleting the user's data from the Vector database, removing
    the assistant object both locally and from an S3 bucket, and finally deleting the user record
    from a DynamoDB table.

    Args:
        user_id (str): The unique identifier for the user whose account is to be deleted.

    Returns:
        - A JSON response confirming the deletion of the account or an error message with an
          appropriate HTTP status code if the operation fails.

    Raises:
        - FileNotFoundError: If the assistant file for the user is not found.
        - ValueError: If 'user_id' is missing from the request data.
        - Exception: For any other unexpected errors during the process.
    """
    
    try:
        data = request.json
        user_id = data.get("user_id")

        if not user_id:
            raise ValueError("Missing user_id in request data.")

        # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)
        try:
            with open(assistant_path, 'rb') as f:
                ai = dill.load(f)
        except:
            pass
        
        # Deleting complete account
        ai.client.delete_collection(user_id)  # Deleting Vector database Collection

        # Deleting assistant object locally
        if os.path.exists(assistant_path):
            os.remove(assistant_path)

        # Deleting assistant object from S3 Bucket
        s3.delete(assistant_path, user_id)

        ids.remove(user_id)
        # Deleting user_id from DynamoDB
        dynamo.delete_item(user_id, table_name)

        return jsonify({"content": "deleted"})

    except FileNotFoundError:
        logger.error(f"Assistant file not found for user: {user_id}", user_id)
        return jsonify({'content': {'content': 'Error: Assistant file not found'}}), 404
    except ValueError as e:
        logger.error(f"Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500







@app.route('/delete_all', methods=['POST'])
def delete_all():
    """
    Deletes all data associated with a user's account within their assistant collection.

    This endpoint requires a JSON payload with 'user_id' to identify which user's data
    should be deleted. It retrieves all data associated with the user and removes it from
    the collection.

    Args:
        user_id (str): The unique identifier for the user whose data is to be deleted.

    Returns:
        - A JSON response indicating that all data has been deleted or an error message
          with an appropriate HTTP status code if the operation fails.

    Raises:
        - FileNotFoundError: If the assistant file for the user is not found.
        - ValueError: If 'user_id' is missing from the request data.
        - Exception: For any other unexpected errors during the process.
    """
    
    try:
        data = request.json
        user_id = data.get("user_id")

        if not user_id:
            raise ValueError("Missing user_id in request data.")

        # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)
        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)

        # Fetch and delete all user data
        user_data = ai.collection.get(include=["documents"])
        ids = user_data["ids"]
        ai.collection.delete(ids=ids)

        return jsonify({"content": "deleted"})

    except FileNotFoundError:
        logger.error(f"Assistant file not found for user: {user_id}", user_id)
        return jsonify({'content': {'content': 'Error: Assistant file not found'}}), 404
    except ValueError as e:
        logger.error(f"Value error: {e}", user_id)
        return jsonify({'content': {'content': 'Error: ' + str(e)}}), 400
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': {'content': 'Error: An unexpected error occurred'}}), 500



@app.route('/utilities', methods=['POST'])
def handle_utilities():
    """
    Handles all the utilities like providing user summary, deducing astrological sign and listing upcoming events.

    This endpoint requires a JSON payload with 'user_id' to identify which user's data
    shall be used and 'status' to know which utility to be used.

    Args:
        user_id (str): The unique identifier for the user .

    Returns:
        - A JSON response indicating the type of utility used and its content.
    Raises:
        
        - Exception: For any other unexpected errors during the process.
    """
    data = request.json
    response_data = {}
    try:
        status = data.get("status", '')
        user_id = data.get('user_id', '')
        if not all([status, user_id]):
            raise ValueError("Missing data in request.")

            # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)

        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)
        
    
        if status == "summary":
            res = str(ai.summary)
            messages = [
                {"role":"system","content":'''You are a personality summary provider. The user will provide a summary of his personality. 
                You have to reply to the user with a summary of the type of peronality the user has, using the list of his summary. Reply in not more than 100 words. 
                  The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 100 words. '''},
                {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}
        elif status == "events":
            res = str(ai.event_summary)
            messages = [
                {"role":"system","content":f'''You are an event schedule summary provider.Today's date and current time{datetime.datetime.now(tz = ai.timezone)}. is  The user will provide a list of all the events that have been scheduled.  
                Analyze the user query and list all the upcoming events that the user has scheduled.  '''},
                {"role":"user","content":res}
            ]

            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}

        elif status == "sign":
            res = str(ai.summary)
            messages = [
                {"role":"system","content":'''You are a astrological sign deducer. The user will provide a summary of his personality. 
                You have to reply to the user with what his astrological sign may be, using the list of his summary, and also give a brief description about it. Reply in not more than 100 words.
                  The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 100 words.  '''},
                {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}

        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': 'Error: An unexpected error occurred'}), 500



@app.route('/alarm_utilities', methods=['POST'])
def handle_alarm_utilities():
    """
    Handles all the periodic utilities like providing poem of the day, summary of the day and sentiment amalysis.

    This endpoint requires a JSON payload with 'user_id' to identify which user's data
    shall be used and 'status' to know which utility to be used.

    Args:
        user_id (str): The unique identifier for the user .

    Returns:
        - A JSON response indicating the type of utility used and its content.
    Raises:
        
        - Exception: For any other unexpected errors during the process.
    """
    data = request.json
    response_data = {}
    try:
        status = data.get("status", '')
        user_id = data.get('user_id', '')
        description = data.get('description', '')
        if not all([status, user_id]):
            raise ValueError("Missing data in request.")

            # Load the assistant object for the given user
        assistant_path = dynamo.assistant_path_loader(user_id, table_name)

        with open(assistant_path, 'rb') as f:
            ai = dill.load(f)
        result = ai.collection.get(
            where = {"date":datetime.datetime.now(tz = ai.timezone).strftime("%Y-%m-%d")}, 
            # where = {"date":"2024-01-25"},
            include = ["documents"]
        )
        
        res = str(result["documents"])
        if status == "summary_day":
            messages = [
            {"role":"system","content":'''The user will provide you a list of his conversations on a particular day which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record
             You have to reply to the user with a summary of how his day went and his activities and conversations on that day. Reply in not more than 50 words.
              The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words.  '''},
             {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}
        elif status == "poem_day":
            messages = [
            {"role":"system","content":'''The user will provide you a list of his conversations on a particular day which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record
             You have to reply to the user with a short poem of how his day went and his activities and conversations on that day. Reply in not more than 50 words.
              The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words.  '''},
             {"role":"user","content":res}
            ]

            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}

        elif status == "sentiment":
            messages = [
            {"role":"system","content":'''The user will provide you a list of his conversations on a particular day which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record
             You have to analyze his activities and conversations on that day and perform a sentiment analysis and give a summary of his sentiment score. Reply in not more than 50 words.
              The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words.  '''},
             {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}
        elif status == "motivation":
            messages = [
            {"role":"system","content":'''The user will provide you a list of his conversations on a particular day which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record
             You have to analyze his activities and conversations on that day and give improvement suggestions on a particular activity or conversation that the user might have done. Reply in not more than 50 words. 
              The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words. '''},
             {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}
        elif status == "happiness":
            messages = [
            {"role":"system","content":'''The user will provide you a list of his conversations on a particular day which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record
             You have to analyze his activities and conversations on that day and perform an analysis of his happiness throughout the day. Reply in not more than 50 words.
              The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words.  '''},
             {"role":"user","content":res}
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}
        elif status == "custom":
            messages = [
                {
                    "role":"system", "content":'''
                    The user will provide you a list of his conversations on a particular day which contain several keys as follows:-\n
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record\n
                 2. statement : background conversations of the user which you are constantly recording.\n
                 3. date : date of the record\n
                 4. time : time of the record\n
                 You have to answer the user's query related to the conversation data of that particular day provided to you.
                 The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words. 
                    '''
                },
                {"role":"user","content":f"Conversation data:{res},\n My Query:{description}"}
                
            ]
            response = openai.ChatCompletion.create(
                messages = messages,
                model = "gpt-3.5-turbo-1106",
                temperature=0.7
            )
            try:
                ai.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                ai.gpt3cost = 0
            response_data = {"content":response["choices"][0]["message"]["content"]}

        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", user_id)
        return jsonify({'content': 'Error: An unexpected error occurred'}), 500




if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.critical(f"Failed to start Flask application: {e}", stream)