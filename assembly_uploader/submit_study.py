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

import importlib.metadata
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import click
import requests

__version__ = importlib.metadata.version("assembly_uploader")


from assembly_uploader.webin_utils import (
    ensure_webin_credentials_exist,
    get_webin_credentials,
)

logging.basicConfig(level=logging.INFO)


DROPBOX_DEV = "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit"
DROPBOX_PROD = "https://www.ebi.ac.uk/ena/submit/drop-box/submit/"


def parse_failed_study_acc(report):
    failed_re = (
        r"The object being added already exists in the submission account with accession: "
        r"\"(PRJ[EDN][A-Z][0-9]+)\""
    )
    root = ET.fromstring(report)
    errors = root.findall(".//ERROR")

    for e in errors:
        error_text = e.text
        existing_acc = re.findall(failed_re, error_text)
        if existing_acc:
            return existing_acc[0]


def parse_success_study_acc(report):
    success_re = r"accession=\"(PRJ[EDN][A-Z][0-9]+)\""
    new_acc = re.findall(success_re, report)
    if new_acc:
        return new_acc[0]


def submit_study(study_id: str, is_test: bool = False, directory: Path = None):
    endpoint = DROPBOX_DEV if is_test else DROPBOX_PROD
    logging.info(f"Submitting study xml {study_id}")
    workdir = directory or Path.cwd() / Path(f"{study_id}_upload")
    assert workdir.exists()

    submission_xml = workdir / Path(f"{study_id}_submission.xml")
    study_xml = workdir / Path(f"{study_id}_reg.xml")
    files = {
        "SUBMISSION": open(submission_xml, "rb"),
        "ACTION": (None, "ADD"),
        "PROJECT": open(study_xml, "rb"),
    }

    submission_report = requests.post(
        endpoint, files=files, auth=get_webin_credentials()
    )
    receipt_xml_str = submission_report.content.decode("utf-8")

    if 'success="true"' in receipt_xml_str:
        primary_accession = parse_success_study_acc(receipt_xml_str)
        logging.info(
            f"A new study accession has been created: {primary_accession}. Make a note of this!"
        )
        return primary_accession
    elif (
        "The object being added already exists in the submission account"
        in receipt_xml_str
    ):
        primary_accession = parse_failed_study_acc(receipt_xml_str)
        logging.info(
            f"An accession with this alias already exists in project {primary_accession}"
        )
        return primary_accession
    elif submission_report.status_code >= requests.codes.server_error:
        logging.error(
            "Project could not be registered on ENA as the server does not respond. Please again try later."
        )
    else:
        logging.error(
            f"Project could not be registered on ENA. HTTP response: {receipt_xml_str}"
        )


@click.command(help="Study submission")
@click.version_option(__version__, message="assembly_uploader %(version)s")
@click.option("--study", required=True, help="raw reads study ID")
@click.option("--directory", required=True, help="directory containing study XML")
@click.option(
    "--test",
    required=False,
    help="run test submission only",
    default=False,
    is_flag=True,
)
def main(study, test, directory):

    ensure_webin_credentials_exist()

    submit_study(study, test, Path(directory))


if __name__ == "__main__":
    main()
