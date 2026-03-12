import requests
import time

BOT_TOKEN = '7560294806:AAE19BXhw4o0uiKbbwu7eydqXK45At0sixw'
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = None

def get_updates(offset=None):
    params = {'timeout': 30}
    if offset:
        params['offset'] = offset
    resp = requests.get(f"{API_URL}/getUpdates", params=params)
    return resp.json()

def print_chat_info(update):
    # Handle messages and channel posts
    if 'message' in update:
        chat = update['message']['chat']
    elif 'channel_post' in update:
        chat = update['channel_post']['chat']
    else:
        return

    chat_id = chat['id']
    chat_type = chat.get('type', 'unknown')
    title = chat.get('title') or chat.get('username') or chat.get('first_name') or "NoName"

    print(f"Chat ID: {chat_id}")
    print(f"Chat Type: {chat_type}")
    print(f"Chat Title/Name: {title}")
    print("-" * 40)

def main():
    global last_update_id
    print("Starting to poll for updates...")
    while True:
        try:
            updates = get_updates(last_update_id)
            if 'result' not in updates:
                print("Telegram API error:", updates)
                time.sleep(5)
                continue

            for update in updates['result']:
                last_update_id = update['update_id'] + 1
                print_chat_info(update)

            time.sleep(1)
        except Exception as e:
            print("Error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
