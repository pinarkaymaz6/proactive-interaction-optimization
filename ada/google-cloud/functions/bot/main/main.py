import json
import logging
import time

import db_helper as db
import payload_helper as ph

collection = db.connect_db("message")       

def main(request):
    body = "OK"
    request_json = request.get_json()
    if request_json:
        print(f"Data coming from Telegram: {request_json}")
        conv_id = get_conv_id(request_json)
        if not conv_id:
            print("Conv Id returned None.")
        request_json["conv_id"] = conv_id
        print("Requset: ", request_json)
        try:
            result = handle_incoming_payload(request_json)
            print("Result ---  ",result)
            if result:
                
                collection.insert_one(request_json)

                for each_result in result:
                    each_result["conv_id"] = conv_id
                    collection.insert_one(each_result)
            #body = "OK"
        except Exception as error:
            logging.error("main/ERROR: %s", str(error))
            body = "main/ERROR"

    return json.dumps({"statusCode": 200, "body": body}, indent=4)


def handle_incoming_payload(payload):
    # Only Message and CallbackQuery objects are handled. 
    # Message object has reply_to_message field as well.
    output = None 

    update_id = payload.get("update_id")
    message = payload.get("message")  # Message
    edited_message = payload.get("edited_message")  # Message
    channel_post = payload.get("channel_post")  # Message
    edited_channel_post = payload.get("edited_channel_post")  # Message
    callback_query = payload.get("callback_query")  # CallbackQuery

    if update_id:
        if message or edited_message or channel_post or edited_channel_post:
            output = ph.handle_message(payload) #returns list
        elif callback_query:
            m_id = callback_query.get("message").get("message_id")
            if not collection.find({"callback_query.message.message_id": m_id}).count() > 0:
                payload["date"] = int(time.time())
                output = ph.handle_callback_query(payload) #returns list
    return output


def get_conv_id(request_json):
    conv_id = None 
    message_collection = db.connect_db("message")
    message = request_json.get("message")
    callback_query = request_json.get("callback_query")
    if callback_query:
        # get the request for this callback and assign that conv id
        # it's a callback from either schedule or survey
        callback_message = callback_query.get("message")
        chat_id = callback_message.get("chat").get("id")
        message_id = callback_message.get("message_id")
        last_message = message_collection.find(
            {"result.chat.id": chat_id, "result.message_id":message_id}).sort([("_id", -1)]).limit(1)
        for last in last_message:
            conv_id = last.get("conv_id")
    
    elif message:
        # This only checks the utterance from user
        # First get the last utterance from the bot (because bot always says the last thing)
        # Ignore the result messages marked with "survey"
        chat_id = message.get("chat").get("id")
        last_message = message_collection.find(
            {"result.chat.id": chat_id, "trigger":{"$ne":'rating'}}).sort([("_id", -1)]).limit(1)
        if last_message.count() > 0:
            for last in last_message:
                end_conversation = last.get("end_conversation")
                conv_id = last.get("conv_id")
                if end_conversation:
                    conv_id = conv_id + 1
        else:
            conv_id = 1
    return conv_id



