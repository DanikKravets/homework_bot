import logging
import os
import time
from datetime import datetime, timedelta

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APINot200, APIRequestError
import sys
from http import HTTPStatus

load_dotenv(override=True)


PRACTICUM_TOKEN = os.getenv('YANDEX_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

LAST_MESSAGE = ''

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='homework.log',
    maxBytes=50000000,
    backupCount=5
)


def check_last_message(message, last_message=LAST_MESSAGE):
    """Exclusion of resending last message."""
    return message != last_message


def check_tokens():
    """Checking for the presence of environment variables."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    return all(tokens)


def send_message(bot, message):
    """Sends message to telegram chat."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Message sent')
        LAST_MESSAGE = message

    except Exception as error:
        logging.error(f'Error during sending message {error}')

    return LAST_MESSAGE


def get_api_answer(timestamp):
    """Getting the API response."""
    payload = {'from_date': timestamp}

    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )

    except Exception as error:
        message = f'Error within request to API: {error}'
        logging.error(message, exc_info=True)
        raise APIRequestError(error)

    if homework_statuses.status_code != HTTPStatus.OK:

        if isinstance(homework_statuses.json(), dict):

            api_ya_answer = homework_statuses.json().get('message')

            logging.warning(f'Ответ API Яндекс: {api_ya_answer}')

        err_msg = f'Код запроса не 200: {homework_statuses.status_code}.'

        raise APINot200(err_msg)
    else:
        return homework_statuses.json()


def check_response(response):
    """Checking response."""
    if not isinstance(response, dict):
        raise TypeError('API response is not dict')

    elif response.get('homeworks') is None:
        raise KeyError('Homework key unavailable')

    elif not isinstance(response.get('homeworks'), list):
        raise TypeError('API response gives not a list by key homeworks')

    elif not response.get('homeworks'):
        message = 'For previous 30 minutes user doesn`t have any HW'
        logging.DEBUG(message)

    elif not isinstance(response.get('homeworks')[0], dict):
        message = 'Homeworks is not dict'
        logging.error(message)

    else:
        return response.get('homeworks')


def parse_status(homework):
    """Making message from API response."""
    if homework.get('homework_name') is None:
        raise KeyError('Homework_name key is unavailable')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Received API status is not documented')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Main logics of bot`s work."""
    if check_tokens() is False:
        er_txt = (
            'Missing neccecary env variable. '
            'Program stopped'
        )
        logging.critical(er_txt)
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    min_ago = datetime.now() - timedelta(minutes=30)
    timestamp = time.mktime(min_ago.timetuple())
    last_message_err = ''

    while True:
        try:

            current_answer = get_api_answer(timestamp)
            checked_answer = check_response(current_answer)

            for hw in checked_answer:
                message = parse_status(hw)
                if check_last_message(message):
                    send_message(bot, message)

            timestamp = current_answer.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

            if check_last_message(message, last_message_err):
                bot.send_message(TELEGRAM_CHAT_ID, message)
                last_message_err = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
