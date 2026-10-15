import threading, logging, os, smtplib
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import AsyncMessage
from email.message import EmailMessage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
LISTEN_HOST = os.getenv("PROXY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.getenv("PROXY_PORT", "1027"))
RELAY_HOST = os.getenv("RELAY_HOST", "127.0.0.1")
RELAY_PORT = int(os.getenv("RELAY_PORT", "1028"))


class SimulationRelay(AsyncMessage):
    async def handle_message(self, message: EmailMessage):
        logging.info("Authorized simulation email for %s", message.get("To"))
        # Preserve original simulation headers for traceability.
        message["X-Security-Awareness-Simulation"] = "true"
        with smtplib.SMTP(RELAY_HOST, RELAY_PORT, timeout=10) as server:
            server.send_message(message)
        logging.info("Forwarded to local mail sandbox %s:%s", RELAY_HOST, RELAY_PORT)


if __name__ == "__main__":
    c = Controller(SimulationRelay(), hostname=LISTEN_HOST, port=LISTEN_PORT)
    c.start()
    logging.info("Simulation SMTP proxy started on %s:%s", LISTEN_HOST, LISTEN_PORT)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        c.stop()
