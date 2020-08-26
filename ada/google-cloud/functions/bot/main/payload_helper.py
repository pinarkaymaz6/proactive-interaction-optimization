import json
import logging
import datetime as dt
import dialogflow_v2 as dialogflow
import requests
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict
from google.protobuf import field_mask_pb2
import pytz
import db_helper as db
from google.cloud.scheduler_v1 import CloudSchedulerClient
from google.cloud.scheduler_v1.types import Job, HttpTarget
import re


INFO = {} # Please add your own service account info

credentials = service_account.Credentials.from_service_account_info(INFO)
TELE_TOKEN = '' #Please add your own Telegram token
URL = "https://api.telegram.org/bot{}/".format(TELE_TOKEN)


def send_message(text, chat_id, reply_markup=None, parse_mode=None):
    try:
        url = f'{URL}sendMessage?text={text}&chat_id={chat_id}'
        if reply_markup:
            reply_encoded = json.dumps(reply_markup)
            url += '&reply_markup=' + reply_encoded
        #else:
            #url = URL + 'sendMessage?text={}&chat_id={}'.format(text, chat_id)
        if parse_mode:
            url += '&parse_mode=' + parse_mode
        response = requests.get(url)
        response_json = response.json()

    except Exception as error:
        logging.error("ph/send_message/ERROR: %s", str(error))

    return response_json


def handle_message(payload):
    output_result = list()
    message = payload.get("message")
    conv_id = payload.get("conv_id")
    #message_id = message.get("message_id")
    chat_id = message.get("chat").get("id")
    user_id = message.get("from").get("id")
    utterance = message.get("text")
    send_chat_action(chat_id=chat_id)
    print(f"user ID: {user_id}, chat ID: {chat_id}, utterance: {utterance}")

    # These messages are command
    if "entities" in message:
        entities = message.get("entities")
        if entities:
            entity = entities[0]
            if "type" in entity:
                if entity.get("type") == 'bot_command':
                    out_com = handle_bot_commands(payload)  #both lists and objectcs
                    if isinstance(out_com, list):
                        for out in out_com:
                            output_result.append(out)
                    else:
                        output_result.append(out_com)
    
    # These messages go to fulfillment
    else:
        try:
            out_q = None
            parse_mode = None
            json_response = detect_intent(utterance)
            print("Response from fulfillment: ", json_response)
            query_result = json_response.get("queryResult")
            txt = query_result.get("fulfillmentText")
            if not txt:
                code = json_response.get('webhookStatus').get('code')
                if code:
                    if int(code) == 4:
                        txt = "Sorry, API call timed out. Please try again later."
                else:
                    txt = "Sorry, try again."
            
            intent = query_result.get("intent").get("displayName")
            if intent == 'Send Cute Pics':
                parse_mode = 'Markdown'
            
            output_res = send_message(text=txt, chat_id=chat_id, parse_mode=parse_mode)
            output_res["trigger"] = "fulfillment"
            
            if intent == "Exit Conversation":
                output_res["end_conversation"] = True
                out_q = send_questionaire(chat_id, conv_id)
                # metrics
            if output_res:
                output_result.append(output_res)
            if out_q:
                output_result.append(out_q)
        except Exception as error:
            logging.error(error)
    return output_result


def send_chat_action(chat_id, action='typing'):
    #upload_photo
    requests.get(URL + 'sendChatAction', params={'chat_id': chat_id, 'action': action})
    #response.raise_for_status()


def handle_callback_query(payload):
    query = payload.get("callback_query")
    #chat_id = query.get("message").get("chat").get("id")
    #send_chat_action(chat_id=chat_id)


    output_result = None
    callback_data = query.get("data")
    if "rating_" in callback_data:
        output_result = handle_callback_survey(payload) # returns list
    elif "schedule_" in callback_data:
        output_result = handle_callback_schedule(payload) #returns list
    elif "mood_" in callback_data or "emotion_" in callback_data:
        output_result = handle_callback_mood(payload)
    return output_result


def handle_callback_mood(payload):
    reply = None
    return_list = list()
    conv_id = payload.get("conv_id")
    callback_query = payload.get("callback_query")
    message = callback_query.get("message")
    data = callback_query.get("data")
    message_id = int(message.get("message_id"))
    chat_id = message.get("chat").get("id")
    
    if "mood_" in data:
        if 'good' in data.lower():
            text = "I am glad to hear that you feel good!\nTip: You can use /results command to view your tracking history."
            trigger = "feedback-mood"
        elif 'neutral' in data.lower():
            text = "You feel neutral. Would you like a joke or an inspirational quote? You can type 'I want a quote' or 'Tell me a joke'."
            trigger = "feedback-mood"
        elif 'bad' in data.lower():
            text = "Sorry that you feel bummed out. Which of these would describe your emotional state best?"
            reply = {'inline_keyboard':[[{'text':'Angry', 'callback_data':'emotion_angry'}],[{'text':'Bored', 'callback_data':'emotion_bored'}],[{'text':'Fearful', 'callback_data':'emotion_fearful'}],[{'text':'Frustrated', 'callback_data':'emotion_frustrated'}],[{'text':'Guilty', 'callback_data':'emotion_guilty'}],[{'text':'Hopeless', 'callback_data':'emotion_hopeless'}],[{'text':'Tired', 'callback_data':'emotion_tired'}]]}
            trigger = "feedback-mood"
    elif "emotion_" in data:
        text = "Saved.\nTip: If you'd like to see some cute pictures, try typing 'Send me cute pics'."
        trigger = "feedback-emotion"
        
    reaction = send_message(text=text, chat_id=chat_id, reply_markup=reply)

    url = f"{URL}editMessageReplyMarkup?chat_id={chat_id}&message_id={message_id}"
    reply_encoded = json.dumps({})
    url += '&reply_markup=' + reply_encoded
    requests.get(url)

    if reply:
        reaction["hook"] = message_id

    reaction["reaction"] = True
    reaction["trigger"] = trigger
    reaction["conv_id"] = conv_id
    return_list.append(reaction)

    return return_list


def handle_bot_commands(payload):
    result = None
    utterance = payload.get("message").get("text")
    chat_id = payload.get("message").get("chat").get("id")
    if "/start" in utterance:
        result = handle_start_command(payload, chat_id) # returns list
    elif "/save" in utterance:
        result = handle_save_command(chat_id) # returns object
    elif "/results" in utterance:
        result = handle_results_command(chat_id) #returns list
    elif "/help" in utterance:
        result = handle_help_command(chat_id) # returns object
    return result


def handle_start_command(payload, chat_id):
    return_list = list()
    msg = 'Welcome to the Mood Tracker! I am here to keep you company :)'
    try:
        result = send_message(text=msg, chat_id=chat_id)
        result["trigger"] = "command-start"
        return_list.append(result)
        usergroup = db.save_user(payload)
        print("USERGROUP:", usergroup)

        if usergroup == 1:
            time_picker_result = send_time_picker(chat_id)
            return_list.append(time_picker_result)
        else:
            save_result = handle_save_command(chat_id)
            return_list.append(save_result)
    except Exception as error:
        logging.error("ph/handle_start_command/ERROR: %s", str(error))

    return return_list


def handle_save_command(chat_id):
    try:
        headers = {"Content-Type": "application/json"}
        data = {'chat_id': chat_id}
        trigger = requests.post(
            url='https://us-central1-adachatbot-4647e.cloudfunctions.net/notification', json=data, headers=headers)
        result = trigger.json()
        result["trigger"] = "command-save"
        logging.info("Notification triggered by the user")
    except Exception as error:
        logging.error("ph/handle_save_command/ERROR: %s", str(error))

    return result


def handle_results_command(chat_id):
    result_list = list()
    reaction_result = send_message(text="Let me get your tracking history.", chat_id=chat_id)
    reaction_result["trigger"] = "command-results"
    result_list.append(reaction_result)

    msg = '*{}{}{}*'.format('Timestamp'.ljust(18),
                          'Mood'.ljust(10), 'Emotion\n')
    message_collection = db.connect_db("message")
    if message_collection:
        questions = message_collection.find({"result.chat.id": chat_id, "$or": [{"trigger": "command-save"}, {"trigger": "cloud-scheduler"}]}).sort([("_id", 1)])
        for entry in questions:
            mood_message_id = entry.get("result").get("message_id")
            callback_answer = message_collection.find_one({"callback_query.message.message_id": mood_message_id})
            if callback_answer:
                data = callback_answer.get("callback_query").get("data")
                try:  
                    if "mood_" in data:
                        mood_raw = data.split("mood_")[1]
                        date_obj = callback_answer.get("date")
                        new_date = dt.datetime.fromtimestamp(date_obj, pytz.timezone("Europe/Berlin")).strftime('%d.%m.%y, %H:%M')
                        msg += '_{}_{}'.format(new_date.ljust(18),
                                               mood_raw.capitalize().ljust(10))

                        if "bad" in mood_raw:
                            query = message_collection.find_one({"hook": mood_message_id})
                            if query:
                                query_message_id = query.get("result").get("message_id")
                                callback_answer_emo = message_collection.find_one(
                                    {"callback_query.message.message_id": query_message_id})
                                callback_answer_emo_data = callback_answer_emo.get(
                                    "callback_query").get("data")
                                emotion_raw = callback_answer_emo_data.split('emotion_')[1]
                                msg += '{}'.format(emotion_raw.capitalize().ljust(10))
                        
                    msg+='\n'
                except Exception as error:
                    logging.error("ph/handle_message/ERROR: %s", str(error))

        logging.info("Tracking history: %s", msg)
        try:
            response_results = send_message(text=msg, chat_id=chat_id, parse_mode='Markdown')
            response_results["trigger"] = "command-results"
            result_list.append(response_results)
        except Exception as error:
            logging.error("ph/handle_results_command/ERROR: %s", str(error))
    return result_list


def send_questionaire(chat_id, conv_id):
    reply_markup = {'inline_keyboard':[[{'text':'1','callback_data':'rating_one'},{'text':'2','callback_data':'rating_two'},{'text':'3','callback_data':'rating_three'},{'text':'4','callback_data':'rating_four'},{'text':'5','callback_data':'rating_five'}]]}
    text = "Conversation has ended. Would you like to rate me?"
    response_json = send_message(text=text, chat_id=chat_id, reply_markup=reply_markup)
    response_json["conv_id"] = conv_id
    response_json["trigger"] = 'rating'
    return response_json


def detect_intent(utterance):
    session_client = dialogflow.SessionsClient(credentials=credentials)
    session = session_client.session_path("adachatbot-4647e", "87706c4d-2ed4-6102-b9ab-2ed31aba8f90:detectIntent")
    text_input = dialogflow.types.TextInput(text=utterance, language_code="en")
    query_input = dialogflow.types.QueryInput(text=text_input)
    response = session_client.detect_intent(session=session, query_input=query_input)
    json_response = MessageToDict(response)

    return json_response


def send_time_picker(chat_id=None):
    print("Sending time picker")
    if chat_id:
        inline_keyboard = {'inline_keyboard':[]}
        for row in range(0, 6):
            row_buttons = list()
            for column in range(0, 4):
                number = row * 4 + column
                number_str = str(number)
                if number < 10:
                    hour = f'0{number_str}:00'
                else:
                    hour = f'{number_str}:00'
                callback_data = 'schedule_'+number_str
                button = {'text': hour, 'callback_data': callback_data}
                row_buttons.append(button)
            inline_keyboard["inline_keyboard"].append(row_buttons)

        reply_markup = inline_keyboard
        # When would you like to receive a notification from me?
        text = "When would you like to be reminded to track your mood?"
        response_json = send_message(
            text=text, chat_id=chat_id, reply_markup=reply_markup)
        print("Time picker sent successfully")
        response_json["trigger"] = "schedule"
    
    return response_json


def handle_callback_survey(payload):
    ratings = {"rating_one":"1", "rating_two":"2", "rating_three":"3", "rating_four":"4", "rating_five":"5"}
    return_list = list()
    conv_id = payload.get("conv_id")
    callback_query = payload.get("callback_query")
    message = callback_query.get("message")
    data = callback_query.get("data")
    message_id = int(message.get("message_id"))
    chat_id = message.get("chat").get("id")
    rating = ratings[data]
    reaction = send_message(text=f"You rated {rating}. Thanks!", chat_id=chat_id)

    #Remove reply markup
    url = f"{URL}editMessageReplyMarkup?chat_id={chat_id}&message_id={message_id}"
    reply_encoded = json.dumps({})
    url += '&reply_markup=' + reply_encoded
    requests.get(url)

    reaction["reaction"] = True
    reaction["trigger"] = 'rating'
    reaction["conv_id"] = conv_id
    return_list.append(reaction)

    return return_list

def handle_callback_schedule(payload):
    conv_id = payload.get("conv_id")
    return_list = list()
    callback = payload.get("callback_query")
    data = callback.get("data")
    message = callback.get("message")
    message_id = int(message.get("message_id"))
    chat_id = message.get("chat").get("id")

    hour = str(re.findall(r'\d+', data)[0])
    hour =f"{hour}:00"

    # Send thanks immediately
    reaction = send_message(text=f"You selected {hour}. Got it, thanks!", chat_id=chat_id)
    
    # Remove Reply Markup of the time picker question
    url = f"{URL}editMessageReplyMarkup?chat_id={chat_id}&message_id={message_id}"
    reply_encoded = json.dumps({})
    url += '&reply_markup=' + reply_encoded
    requests.get(url)

    #check if there is a scheduler created - get scheduler with the name
    #if this returns somehintf -> update job
    #else create a new cronjob
    client = CloudSchedulerClient(credentials=credentials)
    parent = client.location_path('adachatbot-4647e', 'us-east1')
    job_name = client.job_path('adachatbot-4647e', 'us-east1', data)
    try:
        job = client.get_job(job_name)
        if job:
            body = job.http_target.body
            chat_id_list = json.loads(body)
            if {"chat_id": chat_id} not in chat_id_list:
                chat_id_list.append({"chat_id": chat_id})
            try:
                job.http_target.body = json.dumps(chat_id_list).encode()
                client.update_job(job, field_mask_pb2.FieldMask(paths=['http_target.body']))
            except Exception as error:
                print("Could not update job: " + str(error))
    except:
        print("No such job. Creating a new job...")
        try:
            expression = create_cron_expression(data)
            target = HttpTarget(
                uri="https://us-central1-adachatbot-4647e.cloudfunctions.net/notification",
                http_method="POST",
                headers={"Content-Type":"application/json"},
                body=json.dumps([{"chat_id":chat_id}]).encode()
            )
            new_job = Job(name= job_name,http_target=target,schedule=expression,time_zone="Europe/Berlin")
            client.create_job(parent, new_job)
        except Exception as error:
            print("Failed creating a job")
            print(error)
    
    reaction["reaction"] = True
    reaction["schedule"] = True
    reaction["conv_id"] = conv_id
    return_list.append(reaction)

    return return_list



def create_cron_expression(data):
    number = re.split(r'(\d+)', data)[1]
    exp = f"0 {number} * * *"
    return exp


def handle_help_command(chat_id):
    desc = "*Ada* is a conversational agent that helps you log and track your mood\.\n\n"
    contact = "Need help? Contact [Email](ga53sam@mytum.de/)"
    study = "More details about our user study: [User Study Guideline](https://docs.google.com/document/d/1YXtDB2khwGpY3d48BD5EUEFot_X9lPiPa_lKG66lrkU/edit?usp=sharing/)\n"
    text = f"{desc}{study}{contact}"
    result = send_message(text=text, chat_id=chat_id, parse_mode="MarkdownV2")
    result["trigger"] = "command-help"
    return result


