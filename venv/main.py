from flask import Flask
from json import loads
from threading import Thread
from time import sleep, time
from typing import Any
import nws


app: Flask = Flask(__name__)


def get_settings() -> dict[Any, Any]:
        with open("settings.json", "r") as file:
                return loads(file.read())


def mainloop(seconds_between_refresh: float = 1800):
        nws.refresh()
        nws.main()
        last_update: float = time()
        while True:
                if time() - last_update > seconds_between_refresh:
                        nws.refresh()
                        nws.main()
                        last_update: float = time()
                        sleep(seconds_between_refresh * 0.9)
                sleep(seconds_between_refresh * 0.01)


@app.route("/about.html")
def route_about() -> str:
        with open("about.html", "r") as file:
                return file.read()


@app.route("/documentation.html")
def route_documentation() -> str:
        with open("documentation.html") as file:
                return file.read()


@app.route("/endpoints.html")
def route_endpoints() -> str:
        with open("endpoints.html") as file:
                return file.read()


@app.route("/")
@app.route("/home")
def route_home() -> str:
        with open("home.html", "r") as file:
                return file.read()


@app.route("/points.json")
def route_points() -> str:
        with open("points.json", "r") as file:
                return file.read()


@app.route("/predicitons.json")
def route_predictions() -> str:
        with open("predictions.json", "r") as file:
                return file.read()


@app.route("/raw.json")
def route_raw() -> str:
        with open("raw.json", "r") as file:
                return file.read()


@app.route("/settings.json")
def route_settings() -> str:
        with open("settings.json", "r") as file:
                return file.read()


@app.route("/special-data.json")
def route_special_data() -> str:
        with open("special-data.json", "r") as file:
                return file.read()


@app.route("/styles.css")
def route_styles() -> str:
        with open("styles.css") as file:
                return file.read()


@app.route("/summary.json")
def route_summary() -> str:
        with open("summary.json", "r") as file:
                return file.read()


if __name__ == "__main__":
        comp_thread: Thread = Thread(target=mainloop, kwargs=get_settings())
        comp_thread.start()
        app.run(debug=True)
        comp_thread.join()        
