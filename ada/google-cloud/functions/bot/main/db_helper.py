import logging
from pymongo import MongoClient


def connect_db(collection_name):
    collection = None
    try:
        client = MongoClient(
            "mongodb+srv://-------") #Please add your own DB connection string
        db = client["thesis"]
        collection = db[collection_name]
    except Exception as error:
        logging.error("connect_db/ERROR: %s", str(error))

    return collection


def save_user(payload):
    usergroup = 0
    try:
        from_id = payload.get("message").get("from").get("id")
        collection_users = connect_db("users")
        if collection_users:
            found = collection_users.find({"message.from.id": from_id}).limit(1)
            if len(list(found)) == 0:
                #payload = convert_time(payload)
                usergroup = get_usergroup_number(collection_users)
                payload["usergroup"] = usergroup
                collection_users.insert_one(payload)
                logging.info("NEW USER saved.")
    except Exception as error:
        logging.error("save_user/ERROR: %s", str(error))
    
    return usergroup


def get_usergroup_number(collection_users):
    usergroup = 0
    if collection_users:
        try:
            last_ug = collection_users.find().sort([("_id", -1)]).limit(1)
            if last_ug.count() > 0:
                for last in last_ug:
                    ug = last.get("usergroup")
                    if ug == 0:
                        usergroup = 1
        except:
            print("no usergroup id assigned, assigning 0...")

    return usergroup
