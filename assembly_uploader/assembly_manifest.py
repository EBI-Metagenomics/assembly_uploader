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

import click
import csv
from datetime import datetime
import hashlib
import importlib.metadata
import logging
import os
from pathlib import Path

from .ena_queries import EnaQuery

logging.basicConfig(level=logging.INFO)

__version__ = importlib.metadata.version("assembly_uploader")


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


class AssemblyManifestGenerator:
    def __init__(
        self,
        study: str,  # only used to name the upload directory
        assembly_study: str,
        assemblies_csv: Path,
        output_dir: Path = None,
        force: bool = False,
        private: bool = False,
        tpa: bool = False,
        test: bool = False,
    ):
        """
        Create an assembly manifest file for uploading assemblies detailed in assemblies_csv into the assembly_study.
        :param study: study accession of the raw reads study
        :param assembly_study: study accession of the assembly study (e.g. created by Study XMLs)
        :param assemblies_csv: path to assemblies CSV file, listing runs, coverage, assembler, version, filepath of each assembly
                            Optionally, a 'Sample' column can be included to specify sample accession for co-assemblies
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
        self.test = test

    def generate_manifest(
        self,
        runs: list,
        sample: str,
        sequencer: str,
        coverage: str,
        assembler: str,
        assembler_version: str,
        assembly_path: Path,
    ) -> Path | None:
        """
        Generate a manifest file for submission to ENA.

        This method writes a manifest file for an assembly built from one or more sequencing runs.

        :param runs: Comma-separated list of ENA runs' accessions used in the assembly.
        :param sample: Sample accession. Can only be one sample accession, even for co-assemblies.
        :param sequencer: Instrument model used for sequencing.
        :param coverage: Reported coverage of the assembly.
        :param assembler: Name of the assembler used.
        :param assembler_version: Version of the assembler.
        :param assembly_path: Path to the assembly FASTA file (gzipped).

        """
        runs_str = ",".join(runs)

        logging.info(f"Writing manifest for {runs_str}")
        #   sanity check assembly file provided
        if not assembly_path.exists():
            logging.error(
                f"Assembly path {assembly_path} does not exist. Skipping manifest for run {runs_str}"
            )
            return None
        valid_extensions = (".fa.gz", ".fna.gz", ".fasta.gz")
        if not str(assembly_path).endswith(valid_extensions):
            logging.error(
                f"Assembly file {assembly_path} is either not fasta format or not compressed for run "
                f"{runs_str}."
            )
            return None
        #   collect variables
        assembly_md5 = get_md5(assembly_path)
        assembly_alias = f"{runs[0]}{'_others' if len(runs) > 1 else ''}_{assembly_md5}"
        if self.test:
            # add timestamp to be able to test multiple submissions during the same day
            hash_part = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:8]
        assembler = f"{assembler} v{assembler_version}"
        manifest_path = Path(self.upload_dir) / f"{assembly_md5}.manifest"
        #   skip existing manifests
        if os.path.exists(manifest_path) and not self.force:
            logging.warning(
                f"Manifest for {runs_str} already exists at {manifest_path}. Skipping"
            )
            return manifest_path
        values = (
            ("STUDY", self.new_project),
            ("SAMPLE", sample),
            ("RUN_REF", runs_str),
            ("ASSEMBLYNAME", assembly_alias),
            ("ASSEMBLY_TYPE", "primary metagenome"),
            ("COVERAGE", coverage),
            ("PROGRAM", assembler),
            ("PLATFORM", sequencer),
            ("FASTA", assembly_path),
            ("TPA", str(self.tpa).lower()),
        )
        logging.info("Writing manifest file (.manifest) for " + runs_str)
        with open(manifest_path, "w") as outfile:
            for k, v in values:
                manifest = f"{k}\t{v}\n"
                outfile.write(manifest)
        return manifest_path

    def write_manifests(self):
        for row in self.metadata:
            # collect sample accessions and instrument models from runs
            sample_accessions = set()
            instruments = set()
            for run in row["Runs"].split(","):
                # TODO in theory private/non-private state can be different for runs in co-assembly
                ena_query = EnaQuery(run, self.private)
                ena_metadata = ena_query.build_query()
                sample_accessions.add(ena_metadata["sample_accession"])
                instruments.add(ena_metadata["instrument_model"])

            # only one sample accession can be used for the assembly
            if len(sample_accessions) == 1:
                sample_accession = sample_accessions.pop()
            elif row.get("Sample"):
                # Use the explicitly provided sample accession
                sample_accession = row["Sample"]
            else:
                logging.error(
                    f"Multiple samples found for runs {row['Runs']}: {sample_accessions}. "
                    f"Please specify a sample accession in the 'Sample' column of your CSV to resolve this. Skipping."
                )
                continue

            self.generate_manifest(
                row["Runs"].split(","),
                sample_accession,
                ",".join(instruments),
                row["Coverage"],
                row["Assembler"],
                row["Version"],
                Path(row["Filepath"]),
            )

    # alias for convenience
    write = write_manifests


@click.command(help="Generate manifests for assembly uploads")
@click.version_option(__version__, message="assembly_uploader %(version)s")
@click.option(
    "--study",
    required=True,
    help="Raw reads study ID (used as a label for the upload directory)",
)
@click.option(
    "--data",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Metadata CSV - runs, coverage, assembler, version, filepath, and optionally sample",
)
@click.option(
    "--assembly_study",
    required=False,
    help="Pre-existing study ID to submit to if available. Must exist in the webin account.",
)
@click.option(
    "--force", is_flag=True, default=False, help="Overwrite all existing manifests"
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    required=False,
    help="Path to output directory",
)
@click.option("--private", is_flag=True, default=False, help="Use flag if private")
@click.option(
    "--tpa",
    is_flag=True,
    default=False,
    help="Use this flag if the study is a third-party assembly. Default: False",
)
@click.option(
    "--test",
    is_flag=True,
    default=False,
    help="Use flag for using TEST ENA server (it will also add timestamp to assembly alias)",
)
def main(study, assembly_study, data, force, private, tpa, output_dir, test):

    gen_manifest = AssemblyManifestGenerator(
        study=study,
        assembly_study=assembly_study,
        assemblies_csv=data,
        force=force,
        private=private,
        tpa=tpa,
        output_dir=output_dir,
        test=test,
    )
    gen_manifest.write_manifests()
    logging.info("Completed")


if __name__ == "__main__":
    main()
