import threading
import time

import schedule

from app.bot_app import RentNotifierBot
from app.config import configure_logging, configure_timezone, load_settings


def scheduler_worker(app: RentNotifierBot) -> None:
    schedule.every(1).minutes.do(app.run_scheduled_check)
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    logger = configure_logging()
    settings = load_settings()
    configure_timezone(settings.timezone)

    app = RentNotifierBot(settings, logger)
    scheduler_thread = threading.Thread(target=scheduler_worker, args=(app,), daemon=True)
    scheduler_thread.start()
    logger.info("Starting bot polling")
    app.run()


if __name__ == "__main__":
    main()
