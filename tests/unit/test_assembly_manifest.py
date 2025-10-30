from pathlib import Path

import responses

from assembly_uploader.assembly_manifest import AssemblyManifestGenerator


def test_assembly_manifest(assemblies_metadata, tmp_path, run_manifest_content):
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
        assemblies_csv=assemblies_metadata,
        output_dir=tmp_path,
        tpa=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path(
        "ERP125469_upload/d41d8cd98f00.manifest"
    )
    assert manifest_file.exists()

    with manifest_file.open() as f:
        assert f.readlines() == run_manifest_content


def test_assembly_manifest_test(assemblies_metadata, tmp_path, run_manifest_content):
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
        assemblies_csv=assemblies_metadata,
        output_dir=tmp_path,
        tpa=True,
        test=True,
    )
    assembly_manifest_gen.write_manifests()

    manifest_file = tmp_path / Path(
        "ERP125469_upload/d41d8cd98f00.manifest"
    )
    assert manifest_file.exists()

    with manifest_file.open() as f:
        content = f.readlines()
    # assembly alias should have _hash in the end in test mode
    assert content != run_manifest_content
    assert "ERR4918394_d41d8cd98f00_" in content[3]
