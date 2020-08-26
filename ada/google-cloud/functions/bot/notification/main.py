import json
import logging
import requests
import pymongo


TELE_TOKEN = '' #Please add your own Telegram token
URL = "https://api.telegram.org/bot{}/".format(TELE_TOKEN)
R_MARKUP = {'inline_keyboard': [[{'text': 'Good', 'callback_data': 'mood_good'}, {'text': 'Neutral', 'callback_data': 'mood_neutral'}, {
    'text': 'Bad', 'callback_data': 'mood_bad'}]]}

def notification(request):
    data = request.get_json()
    return_json = None
    print("Cronjob started", data)

    if data: # Sends notification to personalized usergroup
        if isinstance(data, list): #listeyse cronjobtan geliyordur
            for chat in data:
                chat_id = chat.get("chat_id")
                conv_id = get_conv_id(chat_id)
                res_json = send_notification("Hey! Remember to log your mood.", chat_id, reply_markup=R_MARKUP)

                res_json["trigger"] = "cloud-scheduler"
                res_json["conv_id"] = conv_id

                message_collection = connect_db("message")
                message_collection.insert_one(res_json)
        else: #objeyse bir user /save demistir
            chat_id = data.get("chat_id")  # user id de ekle
            if chat_id:
                save_trigger = "How is your mood today?"
                return_json = send_notification(save_trigger, chat_id, reply_markup=R_MARKUP)

    else: # Sends notification to default usergroup
        chat_id_list = get_chats(usergroup=0)
        for chat_id in chat_id_list:
            conv_id = get_conv_id(chat_id)
            response_json = send_notification("Hey! Remember to log your mood.", chat_id, reply_markup=R_MARKUP)
            response_json["trigger"] = "cloud-scheduler"
            response_json["conv_id"] = conv_id

            message_collection = connect_db("message")
            message_collection.insert_one(response_json)
    if return_json:
        response = json.dumps(return_json)
    else:
        response = json.dumps({"statusCode": 200, "body": "OK"}, indent=4)

    return response


def get_chats(usergroup=None):
    chats = []
    if usergroup is not None:
        try:
            client = pymongo.MongoClient(
                "mongodb+srv://-----") #Please add your own DB connection string
            database = client["thesis"]
            collection = database["users"]
            for doc in collection.find({"usergroup":usergroup}):
                chats.append(doc.get("message").get("chat").get("id"))
        except pymongo.errors.ConnectionFailure as error:
            logging.error("main/notification/ERROR: %s", str(error))

    return chats


def send_notification(text, chat_id, reply_markup=None):
    response_json = None
    try:
        if reply_markup:
            url = f'{URL}sendMessage?text={text}&chat_id={chat_id}'
            reply_encoded = json.dumps(reply_markup)
            url += '&reply_markup=' + reply_encoded
            response = requests.get(url)
            response_json = response.json()
    except Exception as error:
        logging.error("notification/send_notification/ERROR: " + str(error))

    return response_json


def connect_db(collection_name):
    try:
        client = pymongo.MongoClient(
            "mongodb+srv://-----")  # Please add your own DB connection string
        database = client["thesis"]
        collection = database[collection_name]
    except pymongo.errors.ConnectionFailure as error:
        logging.error(error)

    return collection


def get_conv_id(chat_id):
    conv_id = None
    message_collection = connect_db("message")
    last_message = message_collection.find({"result.chat.id": chat_id, "trigger": {"$ne": 'rating'}}).sort([("_id", -1)]).limit(1)
    for last in last_message:
        trigger = last.get("trigger")
        end_conversation = last.get("end_conversation")
        conv_id = last.get("conv_id")
        if trigger != "cloud-scheduler" and trigger != "command-save":
            if end_conversation:
                conv_id = conv_id + 1
    return conv_id
