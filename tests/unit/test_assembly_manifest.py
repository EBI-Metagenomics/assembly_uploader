from pathlib import Path

import responses

from assembly_uploader.assembly_manifest import AssemblyManifestGenerator


def test_assembly_manifest(assemblies_metadata_csv, tmp_path, run_manifest_content):
    responses.add(
        responses.POST,
        "https://www.ebi.ac.uk/ena/portal/api/search",
        json=[
            {
                "run_accession": "ERR4918394",
                "sample_accession": "SAMEA7687881",
                "instrument_model": "DNBSEQ-G400",
            }
        ],
    )
    assembly_manifest_gen = AssemblyManifestGenerator(
        study="ERP125469",
        assembly_study="PRJ1",
        assemblies_table=assemblies_metadata_csv,
        assemblies_table_delimiter=",",
        output_dir=tmp_path,
        tpa=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path("ERP125469_upload/d41d8cd98f00.manifest")
    assert manifest_file.exists()

    with manifest_file.open() as f:
        assert f.readlines() == run_manifest_content


def test_assembly_manifest_test(
    assemblies_metadata_tsv, tmp_path, run_manifest_content
):
    responses.add(
        responses.POST,
        "https://www.ebi.ac.uk/ena/portal/api/search",
        json=[
            {
                "run_accession": "ERR4918394",
                "sample_accession": "SAMEA7687881",
                "instrument_model": "DNBSEQ-G400",
            }
        ],
    )
    assembly_manifest_gen = AssemblyManifestGenerator(
        study="ERP125469",
        assembly_study="PRJ1",
        assemblies_table=assemblies_metadata_tsv,
        assemblies_table_delimiter="\t",
        output_dir=tmp_path,
        tpa=True,
        test=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path("ERP125469_upload/d41d8cd98f00.manifest")
    assert manifest_file.exists()

    with manifest_file.open() as f:
        content = f.readlines()
    # assembly alias should have _hash in the end in test mode
    # first TSV row is sample-only (no runs), so alias uses sample accession as prefix
    # and RUN_REF is absent, so ASSEMBLYNAME is at index 2
    assert content != run_manifest_content
    assert "SAMEA7687881_d41d8cd98f00_" in content[2]


def test_assembly_manifest_multiple_platforms_explicit(tmp_path):
    metadata_csv = tmp_path / "metadata.csv"
    metadata_csv.write_text(
        "Runs,Coverage,Assembler,Version,Filepath,Sample,Platform\n"
        ',20.0,metaSPADES,3.12.1,tests/fixtures/ERR4918394.fasta.gz,SAMEA7687881,"DNBSEQ-G400,ILLUMINA"\n'
    )

    assembly_manifest_gen = AssemblyManifestGenerator(
        study="ERP125469",
        assembly_study="PRJ1",
        assemblies_table=metadata_csv,
        assemblies_table_delimiter=",",
        output_dir=tmp_path,
        tpa=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path("ERP125469_upload/d41d8cd98f00.manifest")
    assert manifest_file.exists()

    with manifest_file.open() as f:
        content = f.readlines()
    assert "PLATFORM\tDNBSEQ-G400,ILLUMINA\n" in content


def test_assembly_manifest_multiple_platforms_from_runs(tmp_path):
    responses.add(
        responses.POST,
        "https://www.ebi.ac.uk/ena/portal/api/search",
        json=[
            {
                "run_accession": "ERR1111111",
                "sample_accession": "SAMEA1111111",
                "instrument_model": "ILLUMINA",
            }
        ],
    )
    responses.add(
        responses.POST,
        "https://www.ebi.ac.uk/ena/portal/api/search",
        json=[
            {
                "run_accession": "ERR2222222",
                "sample_accession": "SAMEA1111111",
                "instrument_model": "DNBSEQ-G400",
            }
        ],
    )

    metadata_csv = tmp_path / "metadata.csv"
    metadata_csv.write_text(
        "Runs,Coverage,Assembler,Version,Filepath\n"
        '"ERR1111111,ERR2222222",20.0,metaSPADES,3.12.1,tests/fixtures/ERR4918394.fasta.gz\n'
    )

    assembly_manifest_gen = AssemblyManifestGenerator(
        study="ERP125469",
        assembly_study="PRJ1",
        assemblies_table=metadata_csv,
        assemblies_table_delimiter=",",
        output_dir=tmp_path,
        tpa=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path("ERP125469_upload/d41d8cd98f00.manifest")
    assert manifest_file.exists()

    with manifest_file.open() as f:
        content = f.readlines()
    # platforms from runs are sorted for deterministic output
    assert "PLATFORM\tDNBSEQ-G400,ILLUMINA\n" in content
