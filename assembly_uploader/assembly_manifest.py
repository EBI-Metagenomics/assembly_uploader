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
from pathlib import Path

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
    parser.add_argument(
        "--private",
        help="use flag if private",
        required=False,
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--tpa",
        help="use this flag if the study is a third party assembly. Default False",
        action="store_true",
        default=False,
    )
    return parser.parse_args(argv)


class AssemblyManifestGenerator:
    def __init__(
        self,
        study: str,   # TODO: if assembly is a co-assembly, many raw reads study are possible, not just one
        assembly_study: str,
        assemblies_csv: Path,
        output_dir: Path = None,
        force: bool = False,
        private: bool = False,
        tpa: bool = False,
    ):
        """
        Create an assembly manifest file for uploading assemblies detailed in assemblies_csv into the assembly_study.
        :param study: study accession of the raw reads study
        :param assembly_study: study accession of the assembly study (e.g. created by Study XMLs)
        :param assemblies_csv: path to assemblies CSV file, listing run_id, coverage, assembler, version, filepath of each assembly
        :param output_dir: path to output directory, otherwise CWD
        :param force: overwrite existing manifests
        :param private: is this a private study?
        :param tpa: is this a third-party assembly?

        """
        self.study = study
        self.metadata = parse_info(assemblies_csv)
        self.new_project = assembly_study

        self.upload_dir = (output_dir or Path(".")) / Path(f"{self.study}_upload")
        self.upload_dir.mkdir(exist_ok=True, parents=True)

        self.force = force
        self.private = private
        self.tpa = tpa

    def generate_manifest(
        self,
        run_ids: str,
        sample: str,
        sequencer: str,
        coverage: str,
        assembler: str,
        assembler_version: str,
        assembly_path: str,
    ):
        """
        Generate a manifest file for submission to ENA.

        This method writes a manifest file for an assembly built from one or more sequencing runs.
        For co-assemblies (multiple runs), metadata such as `sample` and `sequencer` may be derived
        from a mix of ENA metadata or overridden by input.

        :param run_ids: Comma-separated list of ENA run accessions used in the assembly.
        :param sample: Comma-separated list of sample accessions.
        :param sequencer: Instrument model used for sequencing; 'mixed' if multiple models used.
        :param coverage: Reported coverage of the assembly.
        :param assembler: Name of the assembler used.
        :param assembler_version: Version of the assembler.
        :param assembly_path: Path to the assembly FASTA file (gzipped).

        """
        logging.info(f"Writing manifest for {run_ids}")
        #   sanity check assembly file provided
        if not os.path.exists(assembly_path):
            logging.error(
                f"Assembly path {assembly_path} does not exist. Skipping manifest for run {run_ids}"
            )
            return
        substrings = ["fa.gz", "fna.gz", "fasta.gz"]
        if not any(substring in assembly_path for substring in substrings):
            logging.error(
                f"Assembly file {assembly_path} is either not fasta format or not compressed for run "
                f"{run_ids}."
            )
            return
        #   collect variables
        assembly_alias = get_md5(assembly_path)
        assembler = f"{assembler} v{assembler_version}"
        # TODO: for co-assembly assembly_basename can be rediculously long, so using alternative naming scheme
        if len(run_ids.split(",")) > 4:
            assembly_basename = "_".join(run_ids[4])
            manifest_path = os.path.join(self.upload_dir, f"{assembly_basename}_others_{assembly_alias}.manifest")
        else:
            assembly_basename = "_".join(run_ids)
            manifest_path = os.path.join(self.upload_dir, f"{assembly_basename}.manifest")
        #   skip existing manifests
        if os.path.exists(manifest_path) and not self.force:
            logging.warning(
                f"Manifest for {run_ids} already exists at {manifest_path}. Skipping"
            )
            return
        values = (
            ("STUDY", self.new_project),
            ("SAMPLE", sample),
            ("RUN_REF", run_ids),
            ("ASSEMBLYNAME", assembly_basename + "_" + assembly_alias),
            ("ASSEMBLY_TYPE", "primary metagenome"),
            ("COVERAGE", coverage),
            ("PROGRAM", assembler),
            ("PLATFORM", sequencer),
            ("FASTA", assembly_path),
            ("TPA", str(self.tpa).lower()),
        )
        logging.info("Writing manifest file (.manifest) for " + run_ids)
        with open(manifest_path, "w") as outfile:
            for k, v in values:
                manifest = f"{k}\t{v}\n"
                outfile.write(manifest)

    def write_manifests(self):
        for row in self.metadata:
            # collect sample accessions and instrument models from runs
            sample_accessions = set()
            instruments = set()
            for run in row["Run"].split(","):
                # TODO in theory private/non-private state can be different for runs in co-assembly
                ena_query = EnaQuery(run, self.private)
                ena_metadata = ena_query.build_query()
                sample_accessions.add(ena_metadata["sample_accession"])
                instruments.add(ena_metadata["instrument_model"].lower())

            if row.get("Sequencer"):
                instrument_model = row["Sequencer"].strip()
            elif len(instruments) == 1:
                instrument_model = next(iter(instruments)).title()
            else:
                logging.warning(
                    f"Multiple instruments {','.join(instruments)} found for runs {row['Run']}. "
                    f"Using 'mixed' instrument model."
                )
                instrument_model = "mixed"

            self.generate_manifest(
                row["Run"],
                ",".join(sample_accessions),
                instrument_model,
                row["Coverage"],
                row["Assembler"],
                row["Version"],
                row["Filepath"],
            )

    # alias for convenience
    write = write_manifests


def main():
    args = parse_args(sys.argv[1:])

    gen_manifest = AssemblyManifestGenerator(
        study=args.study,
        assembly_study=args.assembly_study,
        assemblies_csv=args.data,
        force=args.force,
        private=args.private,
        tpa=args.tpa,
    )
    gen_manifest.write_manifests()
    logging.info("Completed")


if __name__ == "__main__":
    main()
