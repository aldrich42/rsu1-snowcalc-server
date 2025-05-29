from datetime import datetime, time, timedelta
from json import dumps, loads
from models import *
from pytz import timezone
from typing import Any, Self
import re
import requests
import models
import numpy as np


est = timezone('US/Eastern')


class BadResponse(Exception):
        pass


def call_json(url: str, headers: dict[str, str]) -> dict[Any, Any]:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
                return response.json()
        else:
                raise BadResponse(f"{response.status_code}")


def call_nws(url: str) -> dict[Any, Any]:
        return call_json(url, get_nws_headers())


def format_datetime(datetime_to_convert: datetime):
        tz_suffix = datetime_to_convert.strftime("%z")
        tz_suffix = f"{tz_suffix[:3]}:{tz_suffix[3:]}"
        return datetime_to_convert.strftime("%Y-%m-%dT%H:%M:%S") + tz_suffix


def get_forecast_points():
        with open("points.json", "r") as file:
                return loads(file.read())


def get_juneteenth():
        jt: datetime
        now: datetime = datetime.now()
        actual: datetime = datetime(now.year, 6, 19, tzinfo=est)
        if actual.weekday == 5:
                jt = actual - timedelta(days=1)
        elif actual.weekday == 6:
                jt = actual + timedelta(days=1)
        else:
                jt = actual
        return jt


def get_nws_headers(): 
        with open("nws-headers.json", "r") as file:
                return loads(file.read())


def get_settings() -> dict[str, Any]:
        with open("settings.json", "r") as file:
                return loads(file.read())


def get_special_data() -> dict[str, Any]:
        with open("special-data.json", "r") as file:
                return loads(file.read())


def nws_datetime_str_to_datetime(datetime_str: str) -> datetime:
        return est.localize(datetime.strptime(datetime_str[:19], "%Y-%m-%dT%H:%M:%S"))


def nws_datetime_str_to_datetime_with_duration(datetime_str: str) -> tuple[datetime, int]:
        datetime_isolated, duration_isolated = tuple(datetime_str.split("/P"))
        day_match = re.match(r"[0-9]+D", duration_isolated)
        hour_match = re.match(r"T[0-9]+H", duration_isolated)
        duration = 0
        if day_match is not None:
                duration += int(day_match.group()[:-1]) * 24
        if hour_match is not None:
                duration += int(hour_match.group()[1:-1])
        return est.localize(datetime.strptime(datetime_isolated[:19], "%Y-%m-%dT%H:%M:%S")), duration


def nws_okay() -> bool:
        try:
                return call_nws("https://api.weather.gov")["status"] == "OK"
        except BadResponse:
                return False


def set_forecast_center():
        now: datetime = est.localize(datetime.now())
        test: datetime = datetime.combine(now.date(), time(6, 0, 0), tzinfo=est)
        if now > test:
                return test + timedelta(days=1)
        else:
                return test


def time_value_pairs_to_individual_forecast(values: list[dict[str, Any]], divide: bool = False, keep_negative: bool = False) -> np.ndarray[Any, Any]:
        offset_and_values: list[tuple[int, float]] = []
        for value in values:
                valid_time, duration = nws_datetime_str_to_datetime_with_duration(value["validTime"])
                for delta in range(duration):
                        def a(td: timedelta) -> int:
                                return td.days * 24 + td.seconds // 3600
                        hours = a(valid_time - forecast_center + timedelta(hours=delta))
                        if not keep_negative and hours < 0:
                                continue
                        if divide:
                                offset_and_values.append((hours, value["value"] / duration))
                        else:
                                offset_and_values.append((hours, value["value"]))
                        if hours >= 23:
                                return np.array(offset_and_values, dtype=np.int32)
        if offset_and_values:
                return np.array(offset_and_values, dtype=np.int32)
        else:
                bottom = 0
                if keep_negative:
                        bottom = -1
                return np.array([(i, 0) for i in range(bottom, 24)], dtype=np.int32)


class Timestamp(object):
        __timezone = est

        def __init__(self: Self):
                self.timestamp: datetime = self.__timezone.localize(datetime.now())

        def __str__(self: Self) -> str:
                return format_datetime(self.timestamp)


class IndividualForecast(object):
        def __init__(self: Self, name: str, json_data: dict[Any, Any], divide: bool = False, keep_negative: bool = False):
                self.uom: dict[Any, Any] | None
                try:
                        self.uom = json_data[name]["uom"]
                except KeyError:
                        self.uom = None
                self.array: np.ndarray[Any, Any] = time_value_pairs_to_individual_forecast(json_data[name]["values"], divide=divide, keep_negative=keep_negative)
                self.divided: bool = divide
                self.kept_negative: bool = keep_negative

        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "uom": self.uom,
                        "array": [[int(i[0]), int(i[1])] for i in self.array],
                        "divided": self.divided,
                        "kept_negative": self.kept_negative
                }


class Forecast(object):
        def __init__(self: Self, json_data: dict[Any, Any]):
                self.timestamp: Timestamp = Timestamp()
                self.update_time: str = json_data["updateTime"]
                self.temperature: IndividualForecast = IndividualForecast("temperature", json_data)
                self.dewpoint: IndividualForecast = IndividualForecast("dewpoint", json_data)
                self.relative_humidity: IndividualForecast = IndividualForecast("relativeHumidity", json_data)
                self.apparent_temperature: IndividualForecast = IndividualForecast("apparentTemperature", json_data)
                self.wind_speed: IndividualForecast = IndividualForecast("windSpeed", json_data)
                self.wind_gust: IndividualForecast = IndividualForecast("windGust", json_data)
                self.probability_of_precipitation: IndividualForecast = IndividualForecast("probabilityOfPrecipitation", json_data)  # , keep_negative=True)
                self.quantitative_precipitation: IndividualForecast = IndividualForecast("quantitativePrecipitation", json_data, divide=True)  # , keep_negative=True)
                self.ice_accumulation: IndividualForecast = IndividualForecast("iceAccumulation", json_data, divide=True)  # , keep_negative=True)
                self.snowfall_amount: IndividualForecast = IndividualForecast("snowfallAmount", json_data, divide=True)  # , keep_negative=True)
                self.snow_level: IndividualForecast = IndividualForecast("snowLevel", json_data)  # , keep_negative=True)
                self.pressure: IndividualForecast = IndividualForecast("pressure", json_data)
                self.center: datetime = forecast_center
        
        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "update_time": self.update_time,
                        "temperature": self.temperature.dictify(),
                        "dewpoint": self.dewpoint.dictify(),
                        "relative_humidity": self.relative_humidity.dictify(),
                        "apparent_temperature": self.apparent_temperature.dictify(),
                        "wind_speed": self.wind_speed.dictify(),
                        "wind_gust": self.wind_gust.dictify(),
                        "probability_of_precipitation": self.probability_of_precipitation.dictify(),
                        "quantatative_precipitation": self.quantitative_precipitation.dictify(),
                        "ice_accumulation": self.ice_accumulation.dictify(),
                        "snowfall_amount": self.snowfall_amount.dictify(),
                        "snow_level": self.snow_level.dictify(),
                        "pressure": self.pressure.dictify(),
                        "center": format_datetime(self.center)
                }


class FreezingLevel(object):
        def __init__(self: Self, json_data: dict[Any, Any]):
                ...

        def dictify(self: Self) -> dict[Any, Any]:
                return {}


class DailyHydrometerologicalProducts(object):
        def __init__(self: Self, json_data: dict[Any, Any]):
                ...

        def dictify(self: Self) -> dict[Any, Any]:
                return {}


class IndividualObservation(object):
        def __init__(self: Self, name: str, json_data: dict[Any, Any]):
                self.uom: str = json_data[name]["unitCode"]
                try:
                        self.value: int = int(json_data[name]["value"])
                except TypeError:
                        self.value: int = 0
                try:
                        self.qc: str = json_data[name]["qualityControl"]
                except KeyError:
                        self.qc: str = ""
        
        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "uom": self.uom,
                        "value": self.value,
                        "qc": self.qc
                }


class Observations(object):
        def __init__(self: Self, json_data: dict[Any, Any]):
                self.timestamp: Timestamp = Timestamp()
                self.update_time: datetime = nws_datetime_str_to_datetime(json_data["timestamp"])
                self.temperature: IndividualObservation = IndividualObservation("temperature", json_data)
                self.dewpoint: IndividualObservation = IndividualObservation("dewpoint", json_data)
                self.relative_humidity: IndividualObservation = IndividualObservation("relativeHumidity", json_data)
                self.wind_speed: IndividualObservation = IndividualObservation("windSpeed", json_data)
                self.barometric_pressure: IndividualObservation = IndividualObservation("barometricPressure", json_data)
                self.max_temperature_last_24_hours: IndividualObservation = IndividualObservation("maxTemperatureLast24Hours", json_data)
                self.min_temperature_last_24_hours: IndividualObservation = IndividualObservation("minTemperatureLast24Hours", json_data)
                self.precipitation_last_hour: IndividualObservation = IndividualObservation("precipitationLastHour", json_data)
                self.precipitation_last_3_hours: IndividualObservation = IndividualObservation("precipitationLast3Hours", json_data)
                self.precipitation_last_6_hours: IndividualObservation = IndividualObservation("precipitationLast6Hours", json_data)
                self.apparent_temperature: IndividualObservation
                at_init: bool = False
                if "windChill" in json_data:
                        if json_data["windChill"]["value"] is not None:
                                self.apparent_temperature = IndividualObservation("windChill", json_data)
                                at_init = True
                elif "heatIndex" in json_data:
                        if json_data["heatIndex"]["value"] is not None:
                                self.apparent_temperature = IndividualObservation("heatIndex", json_data)
                                at_init = True
                if not at_init:
                        self.apparent_temperature = IndividualObservation("heatIndex", json_data)
                self.forecast_center: datetime = forecast_center

        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "update_time": format_datetime(self.update_time),
                        "temperature": self.temperature.dictify(),
                        "dewpoint": self.dewpoint.dictify(),
                        "relative_humidity": self.relative_humidity.dictify(),
                        "apparent_temperature": self.apparent_temperature.dictify(),
                        "wind_speed": self.wind_speed.dictify(),
                        "barometric_pressure": self.barometric_pressure.dictify(),
                        "max_temperature_last_24_hours": self.max_temperature_last_24_hours.dictify(),
                        "min_temperature_last_24_hours": self.min_temperature_last_24_hours.dictify(),
                        "precipitation_last_hour": self.precipitation_last_hour.dictify(),
                        "precipitation_last_3_hours": self.precipitation_last_3_hours.dictify(),
                        "precipitation_last_6_hours": self.precipitation_last_6_hours.dictify(),
                        "apparent_temperature": self.apparent_temperature.dictify(),
                        "center": format_datetime(forecast_center)
                }


class Point(object):
        def __init__(self: Self, latlon_str: str):
                self.latlon_str: str = latlon_str

        def __str__(self: Self):
                return self.latlon_str

        def get_grid_data(self: Self):
                data = call_nws(f"https://api.weather.gov/points/{self.latlon_str}")["properties"]
                return Gridpoint(data["relativeLocation"]["properties"]["city"],
                                data["relativeLocation"]["properties"]["state"],
                                data["gridId"], data["gridX"], data["gridY"], data["radarStation"])

        def get_zone(self: Self):
                url = f"https://api.weather.gov/zones?type=land&point={self.latlon_str}&include_geometry=false"
                data = call_nws(url)["features"][0]["properties"]
                return Zone(data["id"], data["name"])


class Gridpoint(object):
        def __init__(self: Self, mun: str, state: str, wfo: str, grid_x: str, grid_y: str, radar: str):
                self.timestamp: Timestamp = Timestamp()
                self.mun: str = mun
                self.state: str = state
                self.wfo: str = wfo
                self.grid_x: str = grid_x
                self.grid_y: str = grid_y
                self.radar: str = radar

        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "mun": self.mun,
                        "state": self.state,
                        "wfo": self.wfo,
                        "grid_x": self.grid_x,
                        "grid_y": self.grid_y,
                        "radar": self.radar
                }

        def get_daily_hydrometerological_products(self: Self):
                data = call_nws(self.get_product_url("HYD"))
                return DailyHydrometerologicalProducts(data)

        def get_freezing_level(self: Self):
                data = call_nws(self.get_product_url("FZL"))
                return FreezingLevel(data)

        def get_forecast(self: Self):
                data = call_nws(f"https://api.weather.gov/gridpoints/{self.wfo}/{self.grid_x},{self.grid_y}")
                return Forecast(data["properties"])

        def get_product_url(self: Self, product_code: str) -> str:
                data = call_nws(f"https://api.weather.gov/products?office={self.radar}&type={product_code}&limit=1")
                return data["@graph"][0]["@id"]

        def get_station(self: Self):
                data = call_nws(f"https://api.weather.gov/gridpoints/{self.wfo}/{self.grid_x},{self.grid_y}/stations")["features"][0]
                coordinates = data["geometry"]["coordinates"]
                point = f"{coordinates[1]:.4f},{coordinates[0]:.4f}"
                return Station(Point(point), data["properties"]["stationIdentifier"], data["properties"]["name"])


class Zone(object):
        def __init__(self: Self, zone_id: str, name: str):
                self.timestamp: Timestamp = Timestamp()
                self.id: str = zone_id
                self.name: str = name
        
        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "id": self.id,
                        "name": self.name
                }


class Station(object):
        def __init__(self: Self, latlon: Point, station_id: str, name: str):
                self.timestamp: Timestamp = Timestamp()
                self.latlon: Point = latlon
                self.id: str = station_id
                self.name: str = name
        
        def dictify(self: Self):
                return {
                        "timestamp": str(self.timestamp),
                        "latlon": str(self.latlon),
                        "id": self.id,
                        "name": self.name
                }

        def get_control(self: Self):
                return Control(self.latlon)

        def get_observations(self: Self):
                data = call_nws(f"https://api.weather.gov/stations/{self.id}/observations")
                return Observations(data["features"][0]["properties"])


class Control(object):
        def __init__(self: Self, latlon: Point, grid_data: Gridpoint | None = None):
                self.timestamp: Timestamp = Timestamp()
                self.latlon: Point = latlon
                self.grid_data: Gridpoint
                if grid_data is None:
                        self.grid_data = self.latlon.get_grid_data()
                else:
                        self.grid_data = grid_data
                self.forecast: Forecast = self.grid_data.get_forecast()
        
        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "latlon": str(self.latlon),
                        "grid_data": self.grid_data.dictify(),
                        "forecast": self.forecast.dictify()
                }


class ThreeNumberSummary(object):
        def __init__(self: Self, forecast: Forecast, observations: Observations):
                self.timestamp: Timestamp = Timestamp()
                self.quantitative_precipitation: IndividualForecast = forecast.quantitative_precipitation
                self.precipitation_last_6_hours: IndividualObservation = observations.precipitation_last_6_hours
                self.temperature: IndividualForecast = forecast.temperature
                self.forecast_center: datetime = forecast.center

        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "quantitative_precipitation": self.quantitative_precipitation.dictify(),
                        "precipitation_last_6_hours": self.precipitation_last_6_hours.dictify(),
                        "temperature": self.temperature.dictify(),
                        "forecast_center": format_datetime(self.forecast_center)
                }

        def model_a_data_today(self: Self) -> tuple[float, float, float]:
                snowfall: float = float(np.sum(self.quantitative_precipitation.array[:8, 1]))
                snow_on_ground: float = self.precipitation_last_6_hours.value
                temperature: float = float(np.average(self.temperature.array[:8, 1]))
                return snowfall, snow_on_ground, temperature


class Location(object):
        def __init__(self: Self, latlon: Point, grid_data: Gridpoint | None = None, station: Station | None = None, control: Control | None = None, zone: Zone | None = None):
                self.timestamp: Timestamp = Timestamp()
                self.latlon: Point = latlon
                self.grid_data: Gridpoint
                self.station: Station
                self.zone: Zone
                self.control: Control
                if grid_data is None:
                        self.grid_data: Gridpoint = self.latlon.get_grid_data()
                else:
                        self.grid_data: Gridpoint = grid_data
                if station is None:
                        self.station: Station = self.grid_data.get_station()
                else:
                        self.station: Station = station
                if zone is None:
                        self.zone: Zone = self.latlon.get_zone()
                else:
                        self.zone: Zone = zone
                self.forecast: Forecast = self.grid_data.get_forecast()
                if control is None:
                        self.control = self.station.get_control()
                else:
                        self.control = control
                self.observations: Observations = self.station.get_observations()
                self.daily_hydrometerological_products: DailyHydrometerologicalProducts = self.grid_data.get_daily_hydrometerological_products()
                self.freezing_level: FreezingLevel = self.grid_data.get_freezing_level()
                self.three_number_summary: ThreeNumberSummary = ThreeNumberSummary(self.forecast, self.observations)
                self.model_a_prediction_today: float = models.model_a(*self.three_number_summary.model_a_data_today())

        def dictify(self: Self) -> dict[str, Any]:
                return {
                        "timestamp": str(self.timestamp),
                        "latlon": str(self.latlon),
                        "grid_data": self.grid_data.dictify(),
                        "station": self.station.dictify(),
                        "control": self.control.dictify(),
                        "zone": self.zone.dictify(),
                        "forecast": self.forecast.dictify(),
                        "observations": self.observations.dictify(),
                        "daily_hydrometerological_products": self.daily_hydrometerological_products.dictify(),
                        "freezing_level": self.freezing_level.dictify(),
                        "three_number_summary": self.three_number_summary.dictify(),
                        "model_a_prediction_today": self.model_a_prediction_today
                }

        def predictions_dictify(self: Self) -> dict[str, Any]:
                return {
                        "model_a_today": self.model_a_prediction_today
                }


def refresh():
        forecast_center = set_forecast_center()


def main():
        locations = [Location(Point(p)) for p in get_forecast_points()]
        with open("raw.json", "w") as file:
                file.write(dumps([loc.dictify() for loc in locations]))
        with open("summary.json", "w") as file:
                file.write(dumps([loc.three_number_summary.dictify() for loc in locations]))
        with open("predictions.json", "w") as file:
                file.write(dumps([loc.predictions_dictify() for loc in locations]))


forecast_center: datetime = set_forecast_center()


if __name__ == "__main__":
        refresh()
        main()  # todo hyd and fzl
