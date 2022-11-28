from flask import Flask
from threading import Thread
import logging

app = Flask("")

logging.getLogger("werkzeug").setLevel(logging.ERROR)

@app.route("/")
def main():
    return "<img src='https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fpoptv.orange.es%2Fwp-content%2Fuploads%2Fsites%2F3%2F2017%2F12%2Fgru-3.gif&f=1&nofb=1'><br>Study Fam bot is alive."

def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()