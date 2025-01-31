import argparse
import logging
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import requests

from assembly_uploader.submit_study import DROPBOX_DEV, DROPBOX_PROD
from assembly_uploader.webin_utils import (
    ensure_webin_credentials_exist,
    get_webin_credentials,
)


class StudyReleaseError(Exception):
    pass


def release_study(accession: str, is_test: bool = False, xml_path: Path = None):
    """
    Immediately publicly release a study, so that it is no longer private/embargoed/held in ENA.
    :param accession: study accession
    :param is_test: If true, will use wwwdev ENA Test Webin dropbox
    :param xml_path: Optional path to use for the submission xml file, otherwise a temp dir will be used.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        xml_path = xml_path or Path(tmp_dir) / Path(accession + ".xml")

        with xml_path.open("wb") as release_file:
            submission = ET.Element("SUBMISSION")
            actions = ET.SubElement(submission, "ACTIONS")
            action_sub = ET.SubElement(actions, "ACTION")
            release = ET.SubElement(action_sub, "RELEASE")
            release.set("target", accession)
            dom = minidom.parseString(ET.tostring(submission, encoding="utf-8"))
            release_file.write(dom.toprettyxml().encode("utf-8"))

        endpoint = DROPBOX_DEV if is_test else DROPBOX_PROD

        files = {
            "SUBMISSION": xml_path.open("rb"),
        }

        release_report = requests.post(
            endpoint, files=files, auth=get_webin_credentials()
        )
        receipt_xml_str = release_report.content.decode("utf-8")
        if 'success="true"' in receipt_xml_str:
            logging.info(f"Released study {accession}")
        else:
            raise StudyReleaseError(f"Failed to release {accession}. {receipt_xml_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Release a private/held study on ENA, e.g. an uploaded assembly study"
    )
    parser.add_argument("--study", help="Study ID", required=True)
    parser.add_argument(
        "--xml_path", help="Path to use for the release XML submission", required=False
    )
    parser.add_argument(
        "--test",
        help="Use Webin Dev dropbox instead of prod",
        required=False,
        default=False,
        action="store_true",
    )
    args = parser.parse_args()

    ensure_webin_credentials_exist()

    release_study(args.study, args.test, Path(args.xml_path))


if __name__ == "__main__":
    main()
