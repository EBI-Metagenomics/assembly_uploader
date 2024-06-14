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
import csv
import hashlib
import logging
import os
import sys

from .ena_queries import EnaQuery

logging.basicConfig(level=logging.INFO)


def parse_info(data_file):
    csvfile = open(data_file, newline="")
    csvdict = csv.DictReader(csvfile)
    return csvdict


def get_md5(path_to_file):
    md5_hash = hashlib.md5()
    with open(path_to_file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Generate manifests for assembly uploads"
    )
    parser.add_argument("--study", help="raw reads study ID", required=True)
    parser.add_argument(
        "--data", help="metadata CSV - run_id, coverage, assembler, version, filepath"
    )
    parser.add_argument(
        "--assembly_study",
        help="pre-existing study ID to submit to if available. "
        "Must exist in the webin account",
        required=False,
    )
    parser.add_argument(
        "--force",
        help="overwrite all existing manifests",
        required=False,
        action="store_true",
    )
    parser.add_argument("--output-dir", help="Path to output directory", required=False)
    return parser.parse_args(argv)


class AssemblyManifest:
    def __init__(self, argv=sys.argv[1:]):
        self.args = parse_args(argv)
        self.study = self.args.study
        self.metadata = parse_info(self.args.data)
        self.new_project = self.args.assembly_study
        if self.args.output_dir:
            self.upload_dir = os.path.join(self.args.output_dir, f"{self.study}_upload")
        else:
            self.upload_dir = os.path.join(os.getcwd(), f"{self.study}_upload")
        if not os.path.exists(self.upload_dir):
            os.mkdir(self.upload_dir)
        self.force = self.args.force
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

    def generate_manifest(
        self,
        run_id,
        sample,
        sequencer,
        coverage,
        assembler,
        assembler_version,
        assembly_path,
    ):
        logging.info("Writing manifest for " + run_id)
        #   sanity check assembly file provided
        if not os.path.exists(assembly_path):
            logging.error(
                f"Assembly path {assembly_path} does not exist. Skipping manifest for run {run_id}"
            )
            return
        substrings = ["fa.gz", "fna.gz", "fasta.gz"]
        if not any(substring in assembly_path for substring in substrings):
            logging.error(
                f"Assembly file {assembly_path} is either not fasta format or not compressed for run "
                f"{run_id}."
            )
            return
        #   collect variables
        assembly_alias = get_md5(assembly_path)
        assembler = f"{assembler} v{assembler_version}"
        manifest_path = os.path.join(self.upload_dir, f"{run_id}.manifest")
        #   skip existing manifests
        if os.path.exists(manifest_path) and not self.force:
            logging.warning(
                f"Manifest for {run_id} already exists at {manifest_path}. Skipping"
            )
            return
        values = (
            ("STUDY", self.new_project),
            ("SAMPLE", sample),
            ("RUN_REF", run_id),
            ("ASSEMBLYNAME", run_id + "_" + assembly_alias),
            ("ASSEMBLY_TYPE", "primary metagenome"),
            ("COVERAGE", coverage),
            ("PROGRAM", assembler),
            ("PLATFORM", sequencer),
            ("FASTA", os.path.abspath(assembly_path)),
            ("TPA", "true"),
        )
        logging.info("Writing manifest file (.manifest) for " + run_id)
        with open(manifest_path, "w") as outfile:
            for k, v in values:
                manifest = f"{k}\t{v}\n"
                outfile.write(manifest)

    def write_manifests(self):
        for row in self.metadata:
            ena_query = EnaQuery(row["Run"])
            ena_metadata = ena_query.build_query()
            self.generate_manifest(
                row["Run"],
                ena_metadata["sample_accession"],
                ena_metadata["instrument_model"],
                row["Coverage"],
                row["Assembler"],
                row["Version"],
                row["Filepath"],
            )


def main():
    gen_manifest = AssemblyManifest()
    gen_manifest.write_manifests()
    logging.info("Completed")


if __name__ == "__main__":
    main()
