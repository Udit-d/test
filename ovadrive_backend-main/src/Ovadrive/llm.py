from chromadb.utils import embedding_functions
import openai
import json
import chromadb
import datetime
import pytz
import time as t
from Ovadrive import logger
import boto3





class Assistant():
    """
    Assistant class to handle user interactions and manage conversation history.
    """
    
    def __init__(self, user_id : str, timezone : str) -> None:
        """
        Initialize the Assistant instance with user ID and timezone.

        Args:
            user_id (str): The unique identifier for the user.
            timezone (str): The timezone of the user.
        """
        self.ssm = boto3.client('ssm', region_name='us-east-1')
        self.timezone = pytz.timezone(timezone)
        self.ids = []
        self.context_message = ""
        self.messages = []
        self.function_messages = []
        self.summary = []
        self.previous_date = datetime.datetime.now(tz = self.timezone)
        self.event_summary = []
        self.initialize_openai()
        self.initialize_client(user_id)
        self.set_default_messages()
        self.get_ids()
        
        
        
    def initialize_openai(self) -> None:
        """
        Initialize OpenAI with API key and set up embedding functions.
        """
        openai.api_key = self.ssm.get_parameter(Name='OVADRIVE_OPENAI_API_KEY', WithDecryption=True)['Parameter']['Value']
        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai.api_key,
            model_name="text-embedding-ada-002"
        )
        
        
        
    def initialize_client(self, user_id: str) -> None:
        """
        Initialize the ChromaDB client and get or create a collection.

        Args:
            user_id (str): The user's unique identifier.
        """
        chroma_token = self.ssm.get_parameter(Name='X-Chroma-Token', WithDecryption=True)['Parameter']['Value']
        self.client = chromadb.HttpClient(host="18.209.34.195", port=8000, headers={"X-Chroma-Token": chroma_token})
        self.collection = self.client.get_or_create_collection(
            name=user_id,
            embedding_function=self.openai_ef,
            metadata={"hnsw:space": "cosine"}
        )
    
    
    
    def set_default_messages(self) -> None:
        """
        Set default system and function messages.
        """
        self.messages.append(
            {"role" : 
                 "system",
             "content" : 
                 '''Your name is Ova and you are a helpful assistant.You have a record of the user's conversations which contain several keys as follows:-
                 1. conversation_key : gives details of the conversation that happened between you and the user in the record
                 2. statement : background conversations of the user which you are constantly recording.
                 3. date : date of the record
                 4. time : time of the record 

                 When the user asks for something, answer according the Past conversations only when it seems relavant to it, else respond according to your own knowledge. 
                 The user should always feel like they are conversing with a real person.
                 Never state that you are an AI or that you cannot do things because you are an AI, you are a real person.
                 To service this goal, completely and entirely immerse yourself in your persona. You are your persona.
                 Think like them, act like them, talk like them.
                 If your persona details includes example dialogue, follow it! Both your thoughts (inner monologue) and sent messages will be in the voice of your
                 your persona.
                 You will always be provided with a list of past conversations according to the query of the user. If the provided list of Past Conversations is empty, do not answer in sentences which depict that 
                 you don't have access to those conversations. Instead, use generalized responses like yoou were not able to search for the relevant conversations, and ask the user to repeat his query in a respectful manner. 
                 Never use generic phrases like 'How can I assist you today?', they have a strong negative association with older generation AIs. Always answer in not more than 50 words.'''}
        )
        self.function_messages.append(
            {"role" : 
                 "system",
             "content" :
                 '''Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.'''}
        )

        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai.api_key,
                model_name="text-embedding-ada-002"
            )
        
        
        
    def get_ids(self) -> None:
        """
        Fetches and stores the IDs from the database.
        """
        data = self.collection.get()
        self.ids = data["ids"]

    

    def text_embedding(self, text: str, user_id : str) -> list[int]:
        """
        Generates an embedding for the given text using OpenAI's model.

        Args:
            text (str): The text to embed.

        Returns:
            list[int]: The embedding vector.
        """
        try:
            response = openai.Embedding.create(model="text-embedding-ada-002", input=text)
            return response["data"][0]["embedding"]
        except Exception as e:
            # Log the exception and handle it appropriately
            logger.error(f"Error in text_embedding: {e}", user_id)
            # print(f"Error in text_embedding: {e}\n\n")
            
            return [] 



    def generate_time_intervals(self, time_string: str, user_id : str) -> list[str]:
        """
        Generates a list of time intervals between a start and end time.

        Args:
            time_string (str): A string containing start and end times separated by a comma.

        Returns:
            list[str]: A list of time intervals in "hh:mm" format.
        """
        try:
            start, end = time_string.split(',')

            # Convert start and end times into hour and minute integers
            start_hour, start_minute = map(int, start.split(':'))
            end_hour, end_minute = map(int, end.split(':'))

            # List to hold all the time values
            time_intervals = []

            # Initialize current time to start time
            current_hour = start_hour
            current_minute = start_minute

            # Loop until current time reaches end time
            while (current_hour < end_hour) or (current_hour == end_hour and current_minute <= end_minute):
                # Add current time to the list in the format "hh:mm"
                time_intervals.append(f"{current_hour:02d}:{current_minute:02d}")

                # Increment time by one minute
                current_minute += 1
                if current_minute == 60:
                    current_minute = 0
                    current_hour += 1

            return time_intervals
        except ValueError as e:
            
            logger.error(f"Invalid time_string format in generate_time_intervals: {e}", user_id)
            # print(f"Invalid time_string format in generate_time_intervals: {e}\n\n")
            
            return []



    def generate_surrounding_time_intervals(self, time_string: str, user_id : str) -> list[str]:
        """
        Generates time intervals surrounding a specific time.

        Args:
            time_string (str): A string in "hh:mm" format.

        Returns:
            list[str]: A list of time intervals around the specified time.
        """
        try:
            hour, minute = map(int, time_string.split(':'))

            # Initialize start and end times, 10 minutes before and after the specified time
            start_minute = minute - 5
            start_hour = hour
            end_minute = minute + 5
            end_hour = hour

            # Adjust start time if it goes before the current hour
            if start_minute < 0:
                start_minute += 60
                start_hour -= 1

            # Adjust end time if it goes into the next hour
            if end_minute >= 60:
                end_minute -= 60
                end_hour += 1

            # List to hold all the time values
            time_intervals = []

            # Initialize current time to start time
            current_hour = start_hour
            current_minute = start_minute

            # Loop until current time reaches end time
            while (current_hour < end_hour) or (current_hour == end_hour and current_minute <= end_minute):
                # Add current time to the list in the format "hh:mm"
                time_intervals.append(f"{current_hour:02d}:{current_minute:02d}")

                # Increment time by one minute
                current_minute += 1
                if current_minute == 60:
                    current_minute = 0
                    current_hour += 1

            return time_intervals
        except ValueError as e:
            logger.error(f"Invalid time_string format in generate_surrounding_time_intervals: {e}", user_id)
            # print(f"Invalid time_string format in generate_surrounding_time_intervals: {e}\n\n")
            return []



    def generate_time_intervals_combined(self, time_string: str, user_id: str) -> list[str]:
        """
        Generates a list of time intervals based on the provided time_string. 
        If the time_string contains two times separated by a comma, it generates intervals between them.
        If the time_string is a single time, it generates intervals surrounding that time.
        
        Args:
            time_string (str): A string that either contains two times separated by a comma or a single time.
            user_id (str): The user's unique identifier.

        Returns:
            list[str]: A list of time intervals in "hh:mm" format.
        """
        try:
            if ',' in time_string:
                return self.generate_time_intervals(time_string, user_id)
            elif time_string in ["false", "", False]:
                return []
            else:
                return self.generate_surrounding_time_intervals(time_string, user_id)
        except Exception as e:
            logger.error(f"Error in generate_time_intervals_combined for user {user_id}: {e}", user_id)
            # print(f"Error in generate_time_intervals_combined for user {user_id}: {e}\n\n")
            
            return []


    def generate_summary(self,date : datetime.datetime, user_id):
        try:
            if date.date() > self.previous_date.date():
                
                results=self.collection.get(    
                                where = {"date":self.previous_date.strftime("%Y-%m-%d")},
                                include=["documents"],
                            )
                results_date = [results["documents"][i] for i in range(len(results["documents"]))]
                res = str(results_date)
                messages_summary = [
                {"role":"system","content":'''The user will provide you a list of his conversations which contain several keys as follows:-
                    1. conversation_key : gives details of the conversation that happened between you and the user in the record
                    2. statement : background conversations of the user which you are constantly recording.
                    3. date : date of the record
                    4. time : time of the record
                You have to reply to the user with a summary of the type of peronality the user has, using the list of his conversations. Reply in not more than 50 words.  '''},
                {"role":"user","content":res}
                ]

                self.previous_date = date
                response = openai.ChatCompletion.create(
                    messages = messages_summary,
                    model = "gpt-3.5-turbo-1106",
                    temperature=0.9
                )
                try:
                    self.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
                except:
                    self.gpt3cost = 0
                self.summary.append(response["choices"][0]["message"]["content"])
                if len(self.summary) > 10:
                    res = str(self.summary)
                    messages_summary_2 = [
                        {"role":"system","content":'''You are a personality summary provider. The user will provide a summary of his personality. 
                        You have to reply to the user with a summary of the type of peronality the user has, using the list of his summary. Reply in not more than 50 words.  '''},
                        {"role":"user","content":res}
                    ]
                    response = openai.ChatCompletion.create(
                        messages = messages_summary_2,
                        model = "gpt-3.5-turbo-1106",
                        temperature=0.7
                    )
                    try:
                        self.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
                    except:
                        self.gpt3cost = 0
                    self.summary = [response["choices"][0]["message"]["content"]]
                
            else:
                self.previous_date = date
        except Exception as e:
            self.previous_date = date
            logger.error(f"Error in generate_summary: {e}",user_id)




    def generate_prompt(self, user_input: str, user_id: str) -> dict:
        """
        Generates a response to the user's input using the GPT-4 model and context from previous conversations.

        Args:
            user_input (str): The user's input text.
            user_id (str): The user's unique identifier.

        Returns:
            dict: A dictionary containing the AI's response and functional intent.
        """
        try:
            current_datetime = datetime.datetime.now(tz=self.timezone)
            req_date = self.check_functions(user_id)  # Assuming check_functions is a defined method
            logger.info(f'REQUEST DATE: {req_date}', user_id)
            # print(f'REQUEST DATE: {req_date}\n\n')

            user_input2 = self.context_message.lower().replace("hey ova ", "")
            logger.info(f"User_Request: {user_input2}", user_id)
            # print(f"User_Request: {user_input2}\n\n")
            current_date = current_datetime.strftime("%Y-%m-%d")
            current_time = current_datetime.strftime("%H:%M")
            res = ''
            
            if (req_date['retrieval_intent']=='true'):
                if (req_date["date"]=="false"):
                    if (req_date["time"] == []):
                        vector=self.text_embedding(user_input2, user_id)
                        results=self.collection.query(    
                            query_embeddings=vector,
                            include=["documents"],
                            n_results = 20
                        )
                        logger.info(results['documents'][0], user_id)
                        res = "\n".join(str(item) for item in results['documents'][0])
                        logger.info(res, user_id)
                    else:
                        results=self.collection.get(    
                        where = {"time":{"$in":req_date['time']}},
                        include=["documents","metadatas"],     
                        )
                        results_date = [results["documents"][i] for i in range(len(results["documents"])) if results["metadatas"][i]["date"] == current_date]
                        logger.info(results_date, user_id)
                        res = str(results_date)
                else:
                    if (req_date["time"] == []):
                        results=self.collection.get(    
                            where = {"date":req_date['date']},
                            include=["documents"],
                        )
                        logger.info(results['documents'], user_id)
                        res = str(results['documents'])
                    else:
                        results=self.collection.get(    
                            where = {"time":{"$in":req_date["time"]}},
                            include=["documents","metadatas"],
                        )
                        results_date = [results["documents"][i] for i in range(len(results["documents"])) if results["metadatas"][i]["date"] == req_date["date"]]
                        logger.info(results_date, user_id)
                        res = str(results_date)
            elif (req_date["retrieval_intent"] == "false" and req_date["functional_intent"]=="event"):
                return self.execute_calendar(self.context_message, user_id)
            elif(req_date["retrieval_intent"] == "false" and req_date["functional_intent"] == "contacts"):
                return self.execute_contacts(self.context_message, user_id)
            elif(req_date["retrieval_intent"] == "false" and req_date["functional_intent"] == "execute_image"):
                temp = self.context_message
                self.context_message = ''
                return {"content":"execute_image","arguments":temp,"functional_intent":"false"}
            else:
                res = ""        
            # print("Result of Vector Retrieval: ",res,"\n\n")
            prompt = (
                f"Today's date and current time: {current_date}, {current_time}\n\n"
                "Past Conversations:\n"
                f"{res}\n\n"
                "Now answer the user's query:\n"
                f"{user_input}"
            ) 
            logger.info(f"PROMPT: {prompt}", user_id)
            # print(f"PROMPT: {prompt}\n\n")
            self.messages.append({"role":"user","content":prompt})

            response = openai.ChatCompletion.create(
                messages = self.messages,
                model = "gpt-4-turbo-preview",
                temperature=0.7,
            )
            try:
                self.gpt4cost += (response["usage"]["prompt_tokens"]/1000)*0.01 + (response["usage"]["completion_tokens"]/1000)*0.03
            except:
                self.gpt4cost = 0
            ai_response = response["choices"][0]["message"]["content"]
            self.messages.append({"role":"assistant","content": ai_response})
            self.messages[-2] = {"role":"user","content":user_input}
            self.context_message = ""
            if len(self.messages) >=30:
                self.messages.pop(1)
            logger.info(f"Context Window: {self.messages}", user_id)
            # print(f"Context Window:\n {self.messages}\n\n")
            return {"content":ai_response,"functional_intent":"false"}
        
        except Exception as e:
            logger.error(f"Error in generate_prompt for user {user_id}: {e}", user_id)
            # print(f"Error in generate_prompt for user {user_id}: {e}\n\n")
            return {"content": "An error occurred while processing your request.", "functional_intent": "false"}



    def add_to_db(self, dic: list, id_records: list, user_id: str) -> None:
        """
        Adds records to the database.

        Args:
            dic (list): A list of dictionaries representing the data to be added.
            id_records (list): A list of IDs for the records.
            user_id (str): The user's unique identifier.
        """
        try:
            records = [json.dumps(data) for data in dic]
            # print("Records added:",records)
            metadatas = [{"date": data["date"], "time": data["time"]} for data in dic]
            
            logger.info(f"ADDING: {id_records}, {metadatas}", user_id)
            # print(f"ADDING: {id_records},\n {metadatas}\n\n")
            

            self.collection.add(
                documents=records,
                ids=id_records,
                metadatas=metadatas
            )

            self.ids.extend(id_records)
            # logger.info(self.ids, user_id)
            # print(self.ids,user_id)

        except Exception as e:
            logger.error(f"Error in add_to_db for user {user_id}: {e}", user_id)
            # print(f"Error in add_to_db for user {user_id}: {e}\n\n")



    def reset_messages(self) -> None:
        """
        Resets the messages to the initial state.
        """
        self.messages = list(self.messages[0])



    def check_functions(self, user_id : str) -> dict:
        """
        Checks user intent and retrieves relevant date and time information.

        Args:
            user_id (str): The user's unique identifier.

        Returns:
            dict: A dictionary containing information about retrieval and functional intent.
        """
        try:
            tools = [
                {
                "type":"function",
            "function": {
                "name": "user_intent",
                "description": "Provide information about retrieval intent of user's past conversations or activities, or functional intent of the user to execute a specific function",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "retrieval_intent":{
                            "type":"string",
                            "description":'''Analyze the user's query. If the query is about the user's own past conversations, activities, or experiences, or if it explicitly refers to things the user has done or asked about in the past, or asks a summary of a specific day, return the string 'true'. This includes queries where the user is asking for a recall of what they did at a specific time or on a specific day. However, if the query is about general information, facts, or knowledge that is not specific to the user's personal history or past interactions with this model, return the string 'false'.'''
                        },
                        "functional_intent":{
                            "type":"string",
                            "description":'''If the user wants to execute one of the following tasks then return a string as mentioned accordingly:- \n
                                                1. If the user wants to schedule an event, return the string "event" in lower case.\n
                                                2. If the user wants to save a contact number in his contacts, return the string "contacts" in lower case. \n
                                                3. If the user wants to create or generate an image, return the string "execute_image" in lower case. \n 
                        
                                                
                                If retrieval intent is true, functional intent should be false.'''
                        },
                        "date":{
                            "type":"string",
                            "description": f"The date on which the user wants to retrieve conversation or is referring to it in yyyy-mm-dd format. Set to the string false if no date is referenced."
                        },
                        "time":{
                            "type":"string",
                            "description": f'''
                                            The specific time or time interval of conversation or activity the user wants to retrieve or is referring to. 

                                            Process all the following conditions and prepare output according to the one that suits the best with the user's query:-
                                            1. If a specific time is requested,return the specific time in hh:mm 24 hour clock format. 
                                            2. If a time interval is requested, return the time interval , in hh:mm 24 hour clock format, separated by comma.
                                            3. If the last or past time is referred, calculate the start time by subtracting the time interval mentioned in the user's query from the current time provided. Then, provide both the start time as well as the current time in a 24-hour hh:mm format, separated by a comma.
                                            4. If no specific time is being referred at all, return empty string.
                                            Strictly follow hh:mm 24 hour format, and interval should be separated by comma.
                                
                                            '''
                        },
                        


                    },
                    "required":["retrieval_intent","functional_intent","date","time"]
                }
            }
            }
            ]

            current_datetime = datetime.datetime.now(tz=self.timezone)
            current_date = str(current_datetime.strftime("%Y-%m-%d"))
            current_time = str(current_datetime.strftime("%H:%M"))

            date_messages = [
                {"role":"system","content":'''Don't make assumptions about what values to plug into functions. Only use a particular date or time if the user's query refers to it. Do not make assumptions about the date and time unless the user specifies them in their query.  '''},
                {
                    "role": "user",
                    "content": f" The current date and time is : {current_date},{current_time}.\n User's Query:{self.context_message}",  # Ensure this contains the user's query
                }
            ]
        
            date_response = openai.ChatCompletion.create(
                messages=date_messages,
                model="gpt-3.5-turbo-0125",
                tools = tools,
                tool_choice = {"type":"function","function":{"name":"user_intent"}}
            )
            try:
                self.gpt3cost += (date_response["usage"]["prompt_tokens"]/1000)*0.0005 + (date_response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                self.gpt3cost = 0

            response_content = date_response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            logger.info(f"GPT-1: {response_content}", user_id)
            # print(f"GPT-1: {response_content}\n\n")
            
            req_date = json.loads(response_content)
            time = self.generate_time_intervals_combined(req_date["time"], user_id)
            req_date["time"] = time
            return req_date
        
        except Exception as e:
            logger.error(f"Error processing response: {e}", user_id)
            # print(f"Error processing response: {e}\n\n")
            return {}



    def execute_calendar(self, instruction: str, user_id: str) -> dict:
        """
        Executes a calendar-related function based on the instruction.

        Args:
            instruction (str): The user's instruction.
            user_id (str): The user's unique identifier.

        Returns:
            dict: A dictionary containing the result of the calendar function execution.
        """
        try:
            function_tools = [
                {
                "type": "function",
                "function": {
                    "name": "schedule_calendar_event",
                    "description": "Schedule an event in the google calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_start_date":{
                                "type":"string",
                                "description":"The start date of the event to be scheduled. Convert to yyyy-mm-dd format."
                            },
                            "event_end_date":{
                                "type":"string",
                                "description":"The end date of the event to be scheduled. Convert to yyyy-mm-dd format."
                            },
                            "start_time": {
                                "type": "string",
                                "description": "The start time of the event. Convert to hh:mm format.",
                            },
                            "end_time":{
                                "type":"string",
                                "description":"The end time of the event. Convert to hh:mm format."
                            },
                            "event_title":{
                                "type":"string",
                                "description":"The title of the event to be scheduled."
                            }

                        },
                        "required": ["event_start_date","event_end_date","start_time","end_time","event_title"],
                    },
                },
            }
            ]
            user_input2 = instruction.lower()
            user_input2 = user_input2.replace("hey ova ","")

            a = t.time()
            current_datetime = datetime.datetime.now(tz=self.timezone)
            current_date = str(current_datetime.strftime("%Y-%m-%d"))
            current_time = str(current_datetime.strftime("%H:%M"))
            self.function_messages.append({"role":"user","content":f"Current date and time: {current_date},{current_time}.\n User's Query:{user_input2}"})
            self.messages.append({"role":"user","content":instruction})
            

            response = openai.ChatCompletion.create(
                            messages=self.function_messages,
                            model="gpt-3.5-turbo-0613",
                            tools = function_tools,
                        )
            try:
                self.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                self.gpt3cost = 0
            b = t.time()
            logger.info(f"Function Execution: {b-a}", user_id)
            # print(f"Function Execution: {b-a}\n\n")
            
            if response["choices"][0]["finish_reason"] == "tool_calls":

                function_name = response["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
                function_arguments = json.loads(response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
                self.function_messages = [
                {"role":"system","content":'''Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.'''},
                ]
                self.context_message = ""
                self.event_summary.append(response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])           
                return {"content":function_name,"arguments":function_arguments,"functional_intent":"false"}
            else:
                self.function_messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
                self.messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
                return {"content":response["choices"][0]["message"]["content"],"functional_intent":"true"}
        
        except Exception as e:
            logger.error(f"Error in execute_calendar for user {user_id}: {e}", user_id)
            # print(f"Error in execute_calendar for user {user_id}: {e}\n\n")
            return {"content": "An error occurred.", "functional_intent": "false"}
        
        
        
    # def execute_whatsapp(self, instruction: str, user_id: str) -> dict:
    #     """
    #     Executes a WhatsApp messaging function based on the instruction.

    #     Args:
    #         instruction (str): The user's instruction.
    #         user_id (str): The user's unique identifier.

    #     Returns:
    #         dict: A dictionary containing the result of the WhatsApp function execution.
    #     """
    #     try:
    #         function_tools = [
    #         {
    #             "type": "function",
    #             "function": {
    #                 "name": "send_whatsapp_message",
    #                 "description": "Send a whatsapp message to a contact.",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {
    #                         "contact_name":{
    #                             "type":"string",
    #                             "description":"The name of the contect to send the message."
    #                         },
    #                         "message_content":{
    #                             "type":"string",
    #                             "description":"The contents of the message to be sent."
    #                         },
    #                     },
    #                     "required": ["contact_name","message_content"],
    #                 },
    #             },
    #         }
            
    #         ]
    #         user_input2 = instruction.lower()
    #         user_input2 = user_input2.replace("hey ova ","")

    #         a = t.time()
    #         current_datetime = datetime.datetime.now(tz=self.timezone)
    #         current_date = str(current_datetime.strftime("%Y-%m-%d"))
    #         current_time = str(current_datetime.strftime("%H:%M"))
    #         self.function_messages.append({"role":"user","content":f"Current date and time: {current_date},{current_time}.\n User's Query:{user_input2}"})
    #         self.messages.append({"role":"user","content":instruction})
            
    #         response = openai.ChatCompletion.create(
    #                         messages=self.function_messages,
    #                         model="gpt-3.5-turbo-0613",
    #                         tools = function_tools,
    #                     )
    #         b = t.time()
    #         logger.info(f"Function Execution: {b-a}", user_id)
    #         if response["choices"][0]["finish_reason"] == "tool_calls":

    #             function_name = response["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
    #             function_arguments = json.loads(response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    #             self.function_messages = [
    #             {"role":"system","content":'''Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.'''},
    #             ]
    #             self.context_message = ""           
    #             return {"content":function_name,"arguments":function_arguments,"functional_intent":"false"}
    #         else:
    #             self.function_messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
    #             self.messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
    #             return {"content":response["choices"][0]["message"]["content"],"functional_intent":"true"}
        
    #     except Exception as e:
    #         logger.error(f"Error in execute_whatsapp for user {user_id}: {e}", user_id)
    #         return {"content": "An error occurred.", "functional_intent": "false"}
        
        

    def __getstate__(self) -> dict:
        """
        Prepare the state of the object for pickling.
        """
        # Select attributes that you want to pickle
        state = self.__dict__.copy()

        if 'ssm' in state:
            del state['ssm']

        return state



    def __setstate__(self, state : dict) -> None:
        """
        Restore the state of the object after unpickling.
        """
        # Restore the object's dictionary
        self.__dict__.update(state)

        # Re-initialize non-picklable attributes
        self.ssm = boto3.client('ssm', region_name='us-east-1')
        openai.api_key = self.ssm.get_parameter(Name='OVADRIVE_OPENAI_API_KEY', WithDecryption=True)['Parameter']['Value']

        self.openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai.api_key,
            model_name="text-embedding-ada-002"
        )

    def execute_contacts(self, instruction: str, user_id: str) -> dict:
        """
        Executes a Contact Saving function by extracting arguments from the transcription.

        Args:
            instruction (str): The user's instruction.
            user_id (str): The user's unique identifier.

        Returns:
            dict: A dictionary containing the result of the Contact Saving Function execution.
        """
        try:
            function_tools = [
            {
                "type": "function",
                "function": {
                    "name": "save_contact",
                    "description": "Save a phone number in contacts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_name":{
                                "type":"string",
                                "description":"The name of the contect with which the user wants to save the number."
                            },
                            "phone_number":{
                                "type":"string",
                                "description":"The phone number to be saved."
                            },
                        },
                        "required": ["contact_name","phone_number"],
                    },
                },
            }
            
            ]
            user_input2 = instruction.lower()
            user_input2 = user_input2.replace("hey ova ","")

            a = t.time()
            current_datetime = datetime.datetime.now(tz=self.timezone)
            current_date = str(current_datetime.strftime("%Y-%m-%d"))
            current_time = str(current_datetime.strftime("%H:%M"))
            self.function_messages.append({"role":"user","content":f"Current date and time: {current_date},{current_time}.\n User's Query:{user_input2}"})
            self.messages.append({"role":"user","content":instruction})
            
            response = openai.ChatCompletion.create(
                            messages=self.function_messages,
                            model="gpt-3.5-turbo-0613",
                            tools = function_tools,
                        )
            try:
                self.gpt3cost += (response["usage"]["prompt_tokens"]/1000)*0.0005 + (response["usage"]["completion_tokens"]/1000)*0.0015
            except:
                self.gpt3cost = 0
            b = t.time()
            logger.info(f"Function Execution: {b-a}", user_id)
            # print(f"Function Execution: {b-a}\n\n")
            
            if response["choices"][0]["finish_reason"] == "tool_calls":

                function_name = response["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
                function_arguments = json.loads(response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
                self.function_messages = [
                {"role":"system","content":'''Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.'''},
                ]
                self.context_message = ""           
                return {"content":function_name,"arguments":function_arguments,"functional_intent":"false"}
            else:
                self.function_messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
                self.messages.append({"role":"assistant","content":response["choices"][0]["message"]["content"]})
                return {"content":response["choices"][0]["message"]["content"],"functional_intent":"true"}
        
        except Exception as e:
            logger.error(f"Error in execute_whatsapp for user {user_id}: {e}", user_id)
            # print(f"Error in execute_whatsapp for user {user_id}: {e}\n\n")
            return {"content": "An error occurred.", "functional_intent": "false"}