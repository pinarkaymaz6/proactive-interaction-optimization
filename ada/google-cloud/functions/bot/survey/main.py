import json
import logging
import requests


TELE_TOKEN = ''  # Please add your own Telegram token
URL = "https://api.telegram.org/bot{}/".format(TELE_TOKEN)
survey_link = 'https://docs.google.com/forms/d/e/1FAIpQLScZLYDg7rSKvshvMx8fs5rY2BxM9Zyn1ZGWgobwCveLBecDCg/viewform?usp=sf_link'

MARKUP = {'inline_keyboard': [[{'text':'Open', 'url':survey_link}]]}
survey_text = "Hello! Thanks for chatting with me :) Please take this short anonymous survey to conclude the study. It takes no more than 5 minutes!"

all_chats = [] # List of all chat IDs

def survey(request):
    chat_id_list = all_chats
    for chat_id in chat_id_list:
        send_notification(text=survey_text, chat_id=chat_id, reply_markup=MARKUP)
    response = json.dumps({"statusCode": 200, "body": "OK"}, indent=4)
    return response

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

    print(response_json)

