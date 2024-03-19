from Ovadrive.llm import Assistant
import dill
from Ovadrive.bucket import S3
from Ovadrive.dynamodb import ID_Mapper

s3 = S3()
assistant_path = "assistants/X3TFg0SWtZOdGsDwa6Pk8RvDzfn2_object.joblib"
s3.download(assistant_path, stream='Live', save_as=assistant_path)

with open("assistants/X3TFg0SWtZOdGsDwa6Pk8RvDzfn2_object.joblib",'rb') as f:
    ai = dill.load(f)


print(ai.previous_date)

# ai.collection.modify(name = 'jatin.sharma')
# results = ai.collection.get(
#     where={"date":"2024-03-09"},
#     include=["documents","metadatas"]
# )
# print(results["documents"])
# print(ai.context_message)
# ai_new = Assistant(user_id="X3TFg0SWtZOdGsDwa6Pk8RvDzfn2",timezone="Asia/Kolkata")
# with open("assistants/X3TFg0SWtZOdGsDwa6Pk8RvDzfn2_object.joblib",'wb') as f:
#     dill.dump(ai_new,f)
# s3.upload(assistant_path, user_id="X3TFg0SWtZOdGsDwa6Pk8RvDzfn2", store_as=assistant_path)

# with open("assistants/jatin.object.joblib",'wb') as f:
#     dill.dump(ai,f)
# dynamo = ID_Mapper()
# stream = "Live"
# table_name = "USER_ID_COLLECTION"
# try:
#     dynamo.create_table(table_name, stream)
#     ids = dynamo.id_scan(table_name, stream)
#     print(ids)
# except Exception as e:
#     print("error")
    # logger.error(f"Error with DynamoDB operation: {e}", stream)
# x = [1,2]
# if len(ai.messages) >= 30:
#     ai.messages.pop(1)
# # print(ai.messages)
