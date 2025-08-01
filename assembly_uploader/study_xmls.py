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

import argparse
import sys
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .ena_queries import EnaQuery

METAGENOME = "metagenome"
METATRANSCRIPTOME = "metatranscriptome"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Study XML generation")
    parser.add_argument("--study", help="raw reads study ID", required=True)
    parser.add_argument(
        "--library",
        help="Library ",
        choices=["metagenome", "metatranscriptome"],
        required=True,
    )
    parser.add_argument("--center", help="center for upload e.g. EMG", required=True)
    parser.add_argument(
        "--hold",
        help="hold date (private) if it should be different from the provided study in "
        "format dd-mm-yyyy. Will inherit the release date of the raw read study if not "
        "provided.",
        required=False,
    )
    parser.add_argument(
        "--tpa",
        help="use this flag if the study a third party assembly. Default False",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--publication",
        help="pubmed ID for connected publication if available",
        type=int,
        required=False,
    )
    parser.add_argument("--output-dir", help="Path to output directory", required=False)
    parser.add_argument(
        "--private",
        help="use flag if private",
        required=False,
        default=False,
        action="store_true",
    )
    return parser.parse_args(argv)


class StudyXMLGenerator:
    def __init__(
        self,
        study: str,
        center_name: str,
        library: str,
        hold_date: datetime = None,
        tpa: bool = False,
        output_dir: Path = None,
        publication: int = None,
        private: bool = False,
    ):
        f"""
        Build submission files for an assembly study.

        :param study: raw reads study ID/accession
        :param center_name: submission centre name, e.g. EMG
        :param library: {METAGENOME} or {METATRANSCRIPTOME}
        :param hold_date: hold date for the data to remain private, if it should be different from the provided study"
        :param tpa: is this a third-party assembly?
        :param output_dir: path to output directory (default is CWD)
        :param publication: pubmed ID for connected publication if available
        :param private: is this a private study?
        :return: StudyXMLGenerator object
        """
        self.study = study

        self.upload_dir = (output_dir or Path(".")) / Path(f"{self.study}_upload")
        self.upload_dir = self.upload_dir.absolute()
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.study_xml_path = self.upload_dir / Path(f"{self.study}_reg.xml")
        self.submission_xml_path = self.upload_dir / Path(
            f"{self.study}_submission.xml"
        )

        self.center = center_name
        self.hold_date = hold_date

        assert library in [METAGENOME, METATRANSCRIPTOME]

        self.library = library
        self.tpa = tpa
        self.publication = publication
        self.private = private

        ena_query = EnaQuery(self.study, self.private)
        self.study_obj = ena_query.build_query()

        self._title = None
        self._abstract = None

    def write_study_xml(self):
        subtitle = self.library.title()
        if self.tpa:
            sub_abstract = "Third Party Annotation (TPA) "
        else:
            sub_abstract = ""

        title = (
            f"{subtitle} assembly of {self.study_obj['study_accession']} data "
            f"set ({self.study_obj['study_title']})"
        )
        self._title = title
        abstract = (
            f"The {sub_abstract}assembly was derived from the primary data "
            f"set {self.study_obj['study_accession']}"
        )
        self._abstract = abstract

        project_alias = self.study_obj["study_accession"] + "_assembly"
        with open(self.study_xml_path, "wb") as study_file:
            project_set = ET.Element("PROJECT_SET")
            project = ET.SubElement(project_set, "PROJECT")
            project.set("alias", project_alias)
            project.set("center_name", self.center)

            ET.SubElement(project, "TITLE").text = title
            ET.SubElement(project, "DESCRIPTION").text = abstract

            # submission
            submission_project = ET.SubElement(project, "SUBMISSION_PROJECT")
            ET.SubElement(submission_project, "SEQUENCING_PROJECT")

            # publication links
            if self.publication:
                project_links = ET.SubElement(project, "PROJECT_LINKS")
                project_link = ET.SubElement(project_links, "PROJECT_LINK")
                xref_link = ET.SubElement(project_link, "XREF_LINK")
                ET.SubElement(xref_link, "DB").text = "PUBMED"
                ET.SubElement(xref_link, "ID").text = str(self.publication)

            # project attributes: TPA and assembly type
            project_attributes = ET.SubElement(project, "PROJECT_ATTRIBUTES")
            if self.tpa:
                project_attribute_tpa = ET.SubElement(
                    project_attributes, "PROJECT_ATTRIBUTE"
                )
                ET.SubElement(project_attribute_tpa, "TAG").text = "study keyword"
                ET.SubElement(project_attribute_tpa, "VALUE").text = "TPA:assembly"

            project_attribute_type = ET.SubElement(
                project_attributes, "PROJECT_ATTRIBUTE"
            )
            ET.SubElement(project_attribute_type, "TAG").text = "new_study_type"
            ET.SubElement(project_attribute_type, "VALUE").text = (
                f"{self.library} assembly"
            )

            dom = minidom.parseString(ET.tostring(project_set, encoding="utf-8"))
            study_file.write(dom.toprettyxml().encode("utf-8"))

    def write_submission_xml(self):
        with open(self.submission_xml_path, "wb") as submission_file:
            submission = ET.Element("SUBMISSION")
            submission.set("center_name", self.center)

            # template
            actions = ET.SubElement(submission, "ACTIONS")
            action_sub = ET.SubElement(actions, "ACTION")
            ET.SubElement(action_sub, "ADD")

            # attributes: function and hold date
            public = self.study_obj["first_public"]
            today = datetime.today().strftime("%Y-%m-%d")
            if self.hold_date:
                action_hold = ET.SubElement(actions, "ACTION")
                hold = ET.SubElement(action_hold, "HOLD")
                hold.set("HoldUntilDate", self.hold_date.strftime("%d-%m-%Y"))
            elif public > today and not self.hold_date:
                action_hold = ET.SubElement(actions, "ACTION")
                hold = ET.SubElement(action_hold, "HOLD")
                hold.set("HoldUntilDate", public)

            dom = minidom.parseString(ET.tostring(submission, encoding="utf-8"))
            submission_file.write(dom.toprettyxml().encode("utf-8"))

    def write(self):
        """
        Write registration and submission XML files.
        """
        self.write_study_xml()
        self.write_submission_xml()


def main():
    args = parse_args(sys.argv[1:])
    study_reg = StudyXMLGenerator(
        study=args.study,
        center_name=args.center,
        library=args.library,
        hold_date=args.hold,
        tpa=args.tpa,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        publication=args.publication,
        private=args.private,
    )
    study_reg.write_study_xml()
    study_reg.write_submission_xml()


if __name__ == "__main__":
    main()
