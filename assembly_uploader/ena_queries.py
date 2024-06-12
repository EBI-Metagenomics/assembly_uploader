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

import requests

logging.basicConfig(level=logging.INFO)

ENA_API_URL = os.environ.get(
    "ENA_API_URL", "https://www.ebi.ac.uk/ena/portal/api/v2.0/search"
)


def build_data(accession, accession_type):
    if "study" in accession_type:
        data = {
            "result": "study",
            "query": f'{accession_type}="{accession}"',
            "fields": "study_accession,study_title,study_description,first_public",
            "format": "json",
        }
        return data
    else:
        data = {
            "result": "read_run",
            "query": f'run_accession="{accession}"',
            "fields": "run_accession,sample_accession,instrument_model,instrument_platform",
            "format": "json",
        }
        return data


def get_default_connection_headers():
    return {
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }
    }


def parse_response_error(response):
    """ENA Portal API error response parser.
    This wrapper will try to get the "message" content from the response data.
    If that fails it will use the response.txt.
    If the above fails, it will return "no_content_on_response".
    """
    message = response.json()[0] or "no_content_on_response"
    try:
        data = response.json()
        if data:
            return data[0].get("message", message)
        else:
            return message
    except json.decoder.JSONDecodeError:
        return message


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
    def __init__(self, accession, username=None, password=None):
        self.url = ENA_API_URL
        self.accession = accession
        self.acc_type = parse_accession(accession)
        username = username or os.getenv("ENA_WEBIN")
        password = password or os.getenv("ENA_WEBIN_PASSWORD")
        if username and password:
            self.auth = (username, password)
        else:
            self.auth = None
        self.data = build_data(self.accession, self.acc_type)

    def post_request(self):
        if self.auth:
            response = requests.post(
                self.url,
                data=self.data,
                auth=self.auth,
                **get_default_connection_headers(),
            )
        else:
            logging.warning(
                "Not authenticated, fetching public data... check ENA_WEBIN and ENA_WEBIN_PASSWORD are set in your "
                "environment to access private data."
            )
            response = requests.post(
                self.url, data=self.data, **get_default_connection_headers()
            )
        return response

    def build_query(self):
        ena_response = self.post_request()
        return parse_response_error(ena_response)
