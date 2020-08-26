import datetime
import json
import logging
from random import randint
import pytz
import requests


# Dialogflow
NEED_QUOTE_INTENT = 'Need Quote'
NEED_JOKE_INTENT = 'Need Joke'
QUOTE_TYPE_ENTITY = 'quote_type'
WEATHER_INTENT = 'weather'
SEND_CUTE_PICS_INTENT = 'Send Cute Pics'

#seed(1)


def fulfillment(request):
    response = None
    request_json = request.get_json()
    if request_json:
        queryResult = request_json.get('queryResult')
        parameters = queryResult.get('parameters')
        intent = queryResult.get('intent').get('displayName')
        print(f"Request to fulfillment: {intent}")
        response = handle_intent(intent, parameters)

        if response:
            return json.dumps({'fulfillmentText': response})
        return json.dumps({'fulfillmentText': "Try again."})
    else:
        print("Fulfillment warmer executed successfully")


def handle_intent(intent, parameters):
    response = None
    if intent == NEED_QUOTE_INTENT:
        quote_type = parameters[QUOTE_TYPE_ENTITY].lower()
        response = handle_intent_quote(quote_type)
    elif intent == NEED_JOKE_INTENT:
        response = handle_intent_joke()
    elif intent == WEATHER_INTENT:
        response = handle_intent_weather(parameters)
    elif intent == SEND_CUTE_PICS_INTENT:
        response = handle_intent_cute_pics()
    return response


def handle_intent_cute_pics():
    response = None
    try:
        with open('cute.json') as f:
            data = json.load(f)
        # links might be dead in the future!!!! 
        bound = len(data) - 1
        index = randint(0, bound)
        res = data[index]
        link = res.get('link')
        response = f"Enjoy [the picture]({link})!"
        
    except Exception as error:
        logging.error("fulfillment/handle_intent_cute_pics/ERROR: " + str(error))
        
    return response

def handle_intent_quote(quote_type):

    # Quotes API
    URL_QUOTES_API = 'http://quotes.rest/qod.json'
    response = None
    try:
        if quote_type == 'inspiration':
            res = requests.get(URL_QUOTES_API, params={"category": "inspire"})
        elif quote_type == 'love':
            res = requests.get(URL_QUOTES_API, params={"category": "love"})
        elif quote_type == 'life':
            res = requests.get(URL_QUOTES_API, params={"category": "life"})
        elif quote_type == 'fun':
            res = requests.get(URL_QUOTES_API, params={"category": "funny"})
        else:
            res = requests.get(URL_QUOTES_API)

        res = res.json()
        quotes = res.get('contents').get('quotes')[0]
        quote = quotes.get('quote')
        author = quotes.get('author')
        response = f'Quote of the day:\n"{quote}" by {author}'
    except Exception as error:
        print("Request to QUOTE API failed")
        logging.error("fulfillment/handle_intent_quote/ERROR: " + str(error))

    return response


def handle_intent_joke():
    response = None
    print("Getting a random joke")
    try:
        with open('jokes.json') as f:
            data = json.load(f)
        
        bound = len(data) - 1
        index = randint(0, bound)
        res = data[index]
        setup = res.get('setup')
        punchline = res.get('punchline')
        response = f"-{setup}\n-{punchline}"
    except Exception as error:
        print("Request to JOKE API failed")
        logging.error("fulfillment/handle_intent_joke/ERROR: " + str(error))
    print("Response from Jokes API: ", response)
    return response


def handle_intent_weather(parameters):

    # OpenWeatherMap API
    KEY_OWM_API = '' # Please replace with your API key
    URL_OWM_API_BASE = 'https://api.openweathermap.org/data/2.5'
    URL_OWM_API_CURRENT = URL_OWM_API_BASE + '/weather'
    URL_OWM_API_FORECAST = URL_OWM_API_BASE + '/forecast'

    params = {"APPID": KEY_OWM_API, "units": "metric"}
    query = None
    response = None
    city_str = ''
    time_str = ''
    date_time = parameters.get("date-time")
    address = parameters.get("address")

    if isinstance(address, str):
        query = address
        city_str = ' in Munich'
    else:
        city = address.get("city")
        zip_code = address.get("zip-code")
        country = address.get("country")
        if city:
            query = city
        elif zip_code:
            query = zip_code
        if query:
            if country:
                #  country_code = get_country_code(country)
                #  query += "," + country_code
                query += "," + country

    if query:
        params.update({"q": query})
        is_current = False
        if isinstance(date_time, dict):
            startDate = date_time.get("startDate")
            startTime = date_time.get("startTime")
            startDateTime = date_time.get("startDateTime")
            dateTime = date_time.get('date_time')
            if startDate:
                date_time = startDate
            elif startTime:
                date_time = startTime
            elif startDateTime:
                date_time = startDateTime
            elif dateTime:
                date_time = dateTime

        
        if isinstance(date_time, str):
            
            if date_time == 'today':
                is_current = True
                time_str = ' today'
            else:
                current = datetime.datetime.now(pytz.timezone('Europe/Berlin'))
                dt = datetime.datetime.fromisoformat(date_time)
                difference = dt - current
                if difference < datetime.timedelta(hours=-12):
                    return "Sorry, your request should refer a current or future point in time."
                try:
                    if difference < datetime.timedelta(hours=12):
                        is_current = True
                    else:
                        hours = int(difference.days * 24 + difference.seconds//3600)
                        if hours >= 120:
                            return "Sorry, weather forecast is only possible for the next 5 days."
                        index = hours // 3
                        weather_response = requests.get(url=URL_OWM_API_FORECAST, params=params)
                        weather_response_json = weather_response.json()
                        lst = weather_response_json.get('list')[index]
                        main_temperature = lst.get('main').get("temp")
                        weather_main = lst.get('weather')[0].get('description')
                        response = f"Temperature is {str(main_temperature)} °C{time_str}{city_str}, {weather_main}"
                except Exception as error:
                    print("Request to WEATHER FORECAST API failed")
                    logging.error(
                        "fulfillment/handle_intent_weather/ERROR: " + str(error))
            if is_current:
                try:
                    weather_response = requests.get(
                        url=URL_OWM_API_CURRENT, params=params)
                
                    weather_response_json = weather_response.json()
                    main_temperature = weather_response_json.get("main").get("temp")
                    weather_main = weather_response_json.get("weather")[0].get("description")
                    response = f"Temperature is {str(main_temperature)} °C{time_str}{city_str}, {weather_main}"
                except Exception as error:
                    print("Request to CURRENT WEATHER API failed")
                    logging.error("fulfillment/handle_intent_weather/ERROR: " + str(error))


    return response

