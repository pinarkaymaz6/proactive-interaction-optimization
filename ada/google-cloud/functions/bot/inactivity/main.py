import datetime as dt
import json
import logging
import requests
from pymongo import MongoClient

TELE_TOKEN = '' #Please replace with your Telegram Token
URL = "https://api.telegram.org/bot{}/".format(TELE_TOKEN)


def inactivity(request):
    # params = check if request has parameters
    # if params, parse to get usergroup id
    # get users in that group
    
    message_collection = connect_db("message")
    chat_id_set = get_chats()
    for chat_id in chat_id_set:
        last_message = get_last_message(message_collection, chat_id)
        for last in last_message:
            end_conversation = last.get("end_conversation")
            trigger = last.get("trigger")
            if not end_conversation:
                if trigger:
                    if trigger != "cloud-scheduler" and trigger!="command-save":
                        date_obj = last.get("result").get("date")
                        date_obj = dt.datetime.fromtimestamp(date_obj)
                        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                        difference = now - date_obj
                        inactivity = dt.timedelta(minutes=10)
                        if difference > inactivity:
                            message_collection.update_one(last, {"$set": {"end_conversation": True}})
                            conv_id = last.get("conv_id")
                            print(f"Inactivity -- conv_id: {conv_id} -- chat_id: {chat_id}")
                            send_questionaire(chat_id, conv_id)
    response = json.dumps({"statusCode": 200, "body": "OK"}, indent=4)

    return response


def get_last_message(message_collection, chat_id):
    
    last_message = message_collection.find(
        {"result.chat.id": chat_id, "trigger": {"$ne": 'rating'}}).sort([("_id", -1)]).limit(1)
    return last_message


def get_chats():

    user_collection = connect_db("users")
    chats = user_collection.find().distinct("message.chat.id")

    return chats


def send_questionaire(chat_id, conv_id):
    reply_markup = {'inline_keyboard':[[{'text':'1','callback_data':'rating_one'},{'text':'2','callback_data':'rating_two'},{'text':'3','callback_data':'rating_three'},{'text':'4','callback_data':'rating_four'},{'text':'5','callback_data':'rating_five'}]]}
    text = "Conversation has ended. Would you like to rate me?"
    response_json = send_message(text=text, chat_id=chat_id, reply_markup=reply_markup)
    if response_json:
        collection = connect_db("message")
        #request_json = convert_time(response_json)
        response_json["trigger"] = "rating"
        response_json["conv_id"] = conv_id
        collection.insert_one(response_json)
    else:
        print("inactiviy/send_questionnaire: Could not send questionnaire")

def connect_db(collection_name):
    try:
        client = MongoClient(
            "mongodb+srv://---------") #Please add your own connection string
        db = client["thesis"]
        collection = db[collection_name]
    except Exception as error:
        logging.error(error)

    return collection


def send_message(text, chat_id, reply_markup=None):
    response_json = None
    try:
        if reply_markup:
            url = f'{URL}sendMessage?text={text}&chat_id={chat_id}'
            reply_encoded = json.dumps(reply_markup)
            url += '&reply_markup=' + reply_encoded
            response = requests.get(url)
            response_json = response.json()
    except Exception as error:
        logging.error("inactivity/send_message/ERROR: " + str(error))

    return response_json
