#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2024 EMBL - European Bioinformatics Institute
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import sys
from time import sleep

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

logging.basicConfig(level=logging.INFO)

RETRY_COUNT = 3


def get_default_connection_headers():
    return {
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }
    }


def parse_accession(accession):
    if accession.startswith("PRJ"):
        return "study_accession"
    elif "RP" in accession:
        return "secondary_study_accession"
    elif "RR" in accession:
        return "run_accession"
    else:
        logging.error(f"{accession} is not a valid accession")
        sys.exit()


class EnaQuery:
    def __init__(self, accession, private=False):
        self.private_url = "https://www.ebi.ac.uk/ena/submit/report/"
        self.public_url = "https://www.ebi.ac.uk/ena/portal/api/search"
        self.accession = accession
        self.acc_type = parse_accession(accession)
        username = os.getenv("ENA_WEBIN")
        password = os.getenv("ENA_WEBIN_PASSWORD")
        if username is None or password is None:
            logging.error("ENA_WEBIN and ENA_WEBIN_PASSWORD are not set")
        if username and password:
            self.auth = (username, password)
        else:
            self.auth = None
        self.private = private

    def post_request(self, data):
        response = requests.post(
            self.public_url, data=data, **get_default_connection_headers()
        )
        return response

    def get_request(self, url):
        response = requests.get(url, auth=self.auth)
        return response

    def get_data_or_handle_error(self, response):
        try:
            data = json.loads(response.text)[0]
            if data is None:
                if self.private:
                    logging.error(
                        f"{self.accession} private data is not present in the specified Webin account"
                    )
                else:
                    logging.error(f"{self.accession} public data does not exist")
            else:
                return data
        except (IndexError, TypeError, ValueError, KeyError):
            logging.error(
                f"Failed to fetch {self.accession}, returned error: {response.text}"
            )

    def retry_or_handle_request_error(self, request, *args, **kwargs):
        attempt = 0
        while attempt < RETRY_COUNT:
            try:
                response = request(*args, **kwargs)
                response.raise_for_status()
                return response
            #   all other RequestExceptions are raised below
            except (Timeout, ConnectionError) as retry_err:
                attempt += 1
                if attempt >= RETRY_COUNT:
                    raise ValueError(
                        f"Could not find {self.accession} in ENA after {RETRY_COUNT} attempts. Error: {retry_err}"
                    )
                sleep(1)
            except HTTPError as http_err:
                print(f"HTTP response has an error status: {http_err}")
                raise
            except RequestException as req_err:
                print(f"Network-related error status: {req_err}")
                raise
            #   should hopefully encompass all other issues...
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                raise

    def _get_private_study(self):
        url = f"{self.private_url}studies/{self.accession}"
        response = self.retry_or_handle_request_error(self.get_request, url)
        study = self.get_data_or_handle_error(response)
        study_data = study["report"]
        try:
            reformatted_data = {
                "study_accession": study_data["secondaryId"],
                "study_title": study_data["title"],
                # remove time and keep date
                "first_public": study_data["firstPublic"].split("T")[0],
            }
        except AttributeError:
            # if the release date was postponed, firstPublic == None
            # fallback on holdDate
            reformatted_data = {
                "study_accession": study_data["secondaryId"],
                "study_title": study_data["title"],
                "first_public": study_data["holdDate"].split("T")[0],
            }
        logging.info(f"{self.accession} private study returned from ENA")
        return reformatted_data

    def _get_public_study(self):
        data = {
            "result": "study",
            "query": f'{self.acc_type}="{self.accession}"',
            "fields": "study_accession,study_title,first_public",
            "format": "json",
        }
        response = self.retry_or_handle_request_error(self.post_request, data)
        study = self.get_data_or_handle_error(response)
        logging.info(f"{self.accession} public study returned from ENA")
        return study

    def _get_private_run(self):
        url = f"{self.private_url}runs/{self.accession}"
        response = self.retry_or_handle_request_error(self.get_request, url)
        run = self.get_data_or_handle_error(response)
        run_data = run["report"]
        reformatted_data = {
            "run_accession": self.accession,
            "sample_accession": run_data["sampleId"],
            "instrument_model": run_data["instrumentModel"],
        }
        logging.info(f"{self.accession} private run returned from ENA")
        return reformatted_data

    def _get_public_run(self):
        data = {
            "result": "read_run",
            "query": f'run_accession="{self.accession}"',
            "fields": "run_accession,sample_accession,instrument_model",
            "format": "json",
        }
        response = self.retry_or_handle_request_error(self.post_request, data)
        run = self.get_data_or_handle_error(response)
        logging.info(f"{self.accession} public run returned from ENA")
        return run

    def build_query(self):
        if "study" in self.acc_type:
            if self.private:
                ena_response = self._get_private_study()
            else:
                ena_response = self._get_public_study()
        elif "run" in self.acc_type:
            if self.private:
                ena_response = self._get_private_run()
            else:
                ena_response = self._get_public_run()
        return ena_response
