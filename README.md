# Multi Ticker Telegram Bot (Python)

A scalable Telegram bot for group usage with:
- `/goldprice`
- `/btcprice`
- `/ethprice`

You can add more commands without new handler files by editing `ASSET_COMMANDS` in `.env`.

## Project Structure

```text
multi_ticker_bot/
├── .env.example
├── README.md
├── app.py
├── config.py
├── logger.py
├── requirements.txt
├── data/
│   └── requests.json
├── logs/
│   └── bot.log
├── handlers/
│   └── commands.py
└── services/
    ├── price_client.py
    └── storage.py


    