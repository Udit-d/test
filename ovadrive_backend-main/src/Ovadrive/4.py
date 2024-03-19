import chromadb
from chromadb.utils import embedding_functions
import openai
import time
import json
from Ovadrive.dynamodb import ID_Mapper
dynamo = ID_Mapper()
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key="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",
                model_name="text-embedding-ada-002"
            )
client = chromadb.HttpClient(host="18.209.34.195", port=8000, headers={"X-Chroma-Token":"sk-mytoken"})

# dynamo.id_scan("USER_ID_COLLECTION","Test")
# print(dynamo.id_scan("USER_ID_COLLECTION","Test"))
collection = client.get_or_create_collection("X3TFg0SWtZOdGsDwa6Pk8RvDzfn2",embedding_function=openai_ef)


results = collection.get(
    where={"date":"2024-03-09"},
    include=["documents","metadatas"]
)
# ids = results["ids"]
print(results["ids"],results["documents"])
# result_json = []
# for i in range(len(results["ids"])):
#     result_json.append([results["ids"][i],json.loads(results["documents"][i])])
# result_ova = []  # Ova's conversation history
# result_drive = []  # Drive's conversation history

# # Segregating data based on whether it's a statement or a conversation
# for result in result_json:
#     if result[1]["statement"] == "":
#         # Handling conversation data
#         user = {
#             "type": "User",
#             "message": result[1]["conversation_key"]["human"],
#             "time": result[1]["date"] + " " + result[1]["time"],
#             "audio":result[0]
#         }
#         result_ova.append(json.dumps(user))
#         ova = {
#             "type": "Ova",
#             "message": result[1]["conversation_key"]["bot"],
#             "time": result[1]["date"] + " " + result[1]["time"],
#             "audio":result[0]
#         }
#         result_ova.append(json.dumps(ova))
#         result_drive.append(json.dumps(user))
#     else:
#         # Handling statement data
#         user = {
#             "type": "User",
#             "message": result[1]["statement"],
#             "time": result[1]["date"] + " " + result[1]["time"],
#             "audio":result[0]
#         }
#         result_drive.append(json.dumps(user))
# print(result_ova)
# ids = data["ids"]
# print(ids)
# print(data["metadatas"])
# id_record = [str("id" + str(len(ids)+ i)) for i in range(9)]
# print(id_record)
# results=collection.get(    
#                     # where = {"time":{"$in":["01:33","01:32"]}},
#                     include=["documents","metadatas"],
#                 )
# print(results["metadatas"]["date"])
# results_date = [results["documents"][i] for i in range(len(results["documents"])) if results["metadatas"][i]["date"] == "2023-12-31"]
# result_json = [json.loads(result) for result in results["documents"]]
# result_ova = []
# result_drive = []
# x = time.time()

# for result in result_json:
#     if result["statement"] == "":
#         user = {
#             "type":"User",
#             "message":result["conversation_key"]["human"],
#             "time": result["date"] + " " + result["time"]
#         }
#         result_ova.append(json.dumps(user))
#         ova = {
#             "type":"Ova",
#             "message":result["conversation_key"]["bot"],
#             "time": result["date"] + " " + result["time"]
#         }
#         result_ova.append(json.dumps(ova))
#     else:
#         user = {
#             "type":"User",
#             "message":result["statement"],
#             "time": result["date"] + " " + result["time"]
#         }
#         result_drive.append(json.dumps(user))
# y = time.time()
# print("Time:",y-x)
# print(result_ova)
# ova_tab = []
# drive_tab = []
# for doc in x:
#     if (!(doc["statement"] == ))
# print(type(x))


# collection.delete(ids = ids)