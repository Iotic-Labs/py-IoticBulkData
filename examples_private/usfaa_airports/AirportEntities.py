# Copyright (c) 2016 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-IoticAgent/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
import csv
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)s [%(name)s] {%(threadName)s} %(message)s',
                    level=logging.INFO)


# CLASS APIRequester --------------------------------------------------------------------------------------

class APIRequester(object):
    '''
        This class manages the calls to any API
    '''

    @classmethod
    def call_api(cls, fname, apiurl):
        url = apiurl
        try:
            rls = requests.get(url)
            rls.raise_for_status()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("__call_api error: %s", str(exc))
        logger.debug("__call_api name=%s url=%s, status_code=%s", fname, url, rls.status_code)
        if rls.ok:
            fdata = rls.text
            return json.loads(fdata)
        else:
            logger.error("__call_api error %i", rls.status_code)


# CLASS AirportDetails --------------------------------------------------------------------------------------
class AirportDetails(object):  # pylint: disable = too-many-instance-attributes

    def __init__(self, state, delay,
                 delay_reason, avgdelay, delay_type,
                 visibility, weather, temperature, wind, last_updated):
        self.state = state
        self.delay = delay
        self.delay_reason = delay_reason
        self.average_delay = avgdelay
        self.delay_type = delay_type
        self.visibility = visibility
        self.weather = weather
        self.temperature = temperature
        self.wind = wind
        self.last_updated = last_updated


# CLASS Airport ---------------------------------------------------------------------------------------------
class Airport(object):  # pylint: disable = too-many-instance-attributes

    def __init__(self, name, city, country, icao_code, latitude, longitude, timezone):

        self.name = name
        self.city = city
        self.country = country
        self.icao_code = icao_code
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.details = None

    def set_details(self, json_details):

        json_weather = json_details['weather']
        json_weather_meta = json_weather['meta'] if 'meta' in json_weather else None
        json_status = json_details['status']

        self.details = AirportDetails(
            state=json_details['state'],
            delay=json_details['delay'],
            delay_reason=json_status['reason'],
            avgdelay=json_status['avgDelay'],
            delay_type=json_status['type'],
            visibility=(json_weather['visibility'] if 'visibility' in json_weather else None),
            weather=(json_weather['weather'] if 'weather' in json_weather else None),
            temperature=(json_weather['temp'] if 'temp' in json_weather else None),
            wind=(json_weather['wind'] if 'wind' in json_weather else None),
            last_updated=(json_weather_meta['updated'] if json_weather_meta is not None else None))


# CLASS AirportsBuilder --------------------------------------------------------------------------------------

class AirportsBuilder(object):  # pylint: disable = too-many-instance-attributes

    # May change it to https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat
    __airport_file = 'airports.csv'
    __list_url = "http://services.faa.gov/airport/list/?format=application/json"
    __base_url = "http://services.faa.gov/airport/status/{faa_code}?format=application/json"

    # Airports loaded from the local file data
    __base_airport_dictionary = {}
    # Airport list made by the intersection between file data and remote data
    __full_airport_dictionary = {}

    __index_FAA_name = 1
    __index_FAA_city = 2
    __index_FAA_country = 3
    __index_FAA_faa_code = 4
    __index_FAA_icao_code = 5
    __index_FAA_latitude = 6
    __index_FAA_longitude = 7
    __index_FAA_altitude = 8
    __index_FAA_timezone = 9

    def __init__(self, airport_file):

        self.__airport_file = airport_file
        self.__create_dictionary_from_file()
        json_airport_list = APIRequester.call_api('usfaa_airports', self.__list_url)
        if json_airport_list is not None:
            self.__parse_airport_list_format(json_airport_list)

    def __create_dictionary_from_file(self):

        # Index of the file's data
        # name      = 1     city        = 2     country     = 3
        # faa_code  = 4     icao_code   = 5     latitude    = 6
        # longitude = 7     altitude    = 8     timezone    = 9

        with open(self.__airport_file) as file_object:
            reader = csv.reader(file_object)
            for row in reader:

                airport = Airport(
                    row[self.__index_FAA_name], row[self.__index_FAA_city],
                    row[self.__index_FAA_country], row[self.__index_FAA_icao_code],
                    row[self.__index_FAA_latitude], row[self.__index_FAA_longitude],
                    row[self.__index_FAA_timezone])

                self.__base_airport_dictionary[row[self.__index_FAA_faa_code]] = airport

    def __parse_airport_list_format(self, json_airport_list):
        # IATA  3-letter IATA code
        key_iata = 'IATA'

        for airport in json_airport_list:
            # Search the airport with the iata code
            iata_code = airport[key_iata]
            if iata_code in self.__base_airport_dictionary:

                url = self.__base_url.format(faa_code=iata_code)
                json_faa_details = APIRequester.call_api('usfaa_airports_details', url)
                if json_faa_details is not None:

                    # Fill the details of the airport and create a new entry
                    # with the iata code in the full dictionary
                    airport_full = self.__base_airport_dictionary[iata_code]
                    airport_full.set_details(json_faa_details)
                    self.__full_airport_dictionary[iata_code] = airport_full

    def get_airports(self):

        return self.__full_airport_dictionary
