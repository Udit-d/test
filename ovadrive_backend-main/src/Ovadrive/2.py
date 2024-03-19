import requests
import json
import datetime
import time

i=9
url = "http://192.168.1.5:8080/ai"
url2 = "http://192.168.1.5:8080/initialize"
url3 = "http://192.168.1.5:8080/fetchchats"
url4 = "http://192.168.1.5:8080/delete_data"
url5 = "http://192.168.1.5:8080/delete_account"
url6 = "http://192.168.1.5:8080/alarm_utilities"

# url = "http://52.91.196.39:8080/ai"
# url2 = "http://52.91.196.39:8080/initialize"
# url3 = "http://52.91.196.39:8080/fetchchats"
# url4 = "http://52.91.196.39:8080/delete_data"
# url5 = "http://52.91.196.39:8080/delete_account"

# url = "http://192.168.29.100:8080/ai"
# url2 = "http://192.168.29.100:8080/initialize"
# url3 = "http://192.168.29.100:8080/fetchchats"
# url4 = "http://192.168.29.100:8080/delete_data"
# url5 = "http://192.168.29.100:8080/delete_account"


header = {
    "Content-Type": "application/json"
}
def initi(user_id : str):
    global header
    user = {"user_id":user_id,"timezone":"Asia/Kolkata","email":"sharmajatin567@gmail.com"}
    payload = json.dumps(user)
        # Send an HTTP POST request to the server
    response = requests.post(url2,headers=header,data=payload)
    if response.status_code == 200:
            print('Data sent successfully to the server.')
    else:
        print(f'Failed to send data. Status code: {response.status_code}')
    
def talk_to_agent(name):
    global i
    while True:
        try:
            i+=1
            text_data = str(input("Human: "))
            convo_status = str(input("Status:"))
            x = time.time()
            current_datetime = datetime.datetime.now()

    # Extract date and time components
            current_date = str(current_datetime.strftime("%Y-%m-%d"))
            current_time = str(current_datetime.strftime("%H:%M"))
            user = {"text":[
                            {'text': text_data,
                            "date":current_date,
                            "time":current_time,
                            "id":"id"+str(i)}],
                    "user_id":f"{name}",
                    "conversation_status":convo_status,
                    "date":current_date,
                    "time":current_time}
            # Create a dictionary or payload with the data you want to send
            payload = json.dumps(user)
            # Send an HTTP POST request to the server
            response = requests.post(url,headers=header,data=payload)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                print('Data sent successfully to the server.')
            else:
                print(f'Failed to send data. Status code: {response.status_code}')
            try:
                print("Ova: ",response.json()['content']['content'])
            except:
                print(response.json())
            # if (response.json()['content']['content'] == "schedule_calendar_event"):
            #     print(response.json()['content']['arguments'])
            #     print("Function Executed Successfuly !!")
            y = time.time()
            print("Response in :",y-x," seconds")
        except requests.exceptions.RequestException as e:
            print(f'An error occurred: {e}')

def delele_account(user_id : str):
    user = {"user_id":user_id}
    payload = json.dumps(user)
    response = requests.post(url5,headers=header,data=payload)
    if response.status_code == 200:
            print('Data sent successfully to the server.')
    else:
        print(f'Failed to send data. Status code: {response.status_code}')


def fetch_the_chats(user_id: str):
    user = {"user_id":user_id,"status":"drive","date":"2024-02-29"}
    payload = json.dumps(user)
    response = requests.post(url3,headers=header,data=payload)
    if response.status_code == 200:
            print('Data sent successfully to the server.')
    else:
        print(f'Failed to send data. Status code: {response.status_code}')
    print("Ova: ",response.json())


# def fetch_alarm(user_id: str):
#     description = str(input("Enter description:"))
#     user = {"user_id":user_id,"status":"custom","description":description}
#     payload = json.dumps(user)
#     response = requests.post(url6,headers=header,data=payload)
#     if response.status_code == 200:
#             print('Data sent successfully to the server.')
#     else:
#         print(f'Failed to send data. Status code: {response.status_code}')
#     print("Ova: ",response.json())
     

if __name__ == "__main__":
    user = input("Enter User: ")
    # fetch_alarm(user)
    # initi(user)
    talk_to_agent(user)
    # delele_account(user)
    # fetch_the_chats(user)