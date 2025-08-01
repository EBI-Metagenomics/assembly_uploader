from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def study_submission_xml_dir():
    return Path(__file__).resolve().parent / Path("fixtures/ERP125469_upload")


@pytest.fixture(scope="module")
def study_reg_xml(study_submission_xml_dir):
    return study_submission_xml_dir / Path("ERP125469_reg.xml")


@pytest.fixture(scope="module")
def study_reg_xml_content(study_reg_xml):
    with study_reg_xml.open() as f:
        return f.readlines()


@pytest.fixture(scope="module")
def study_submission_xml(study_submission_xml_dir):
    return study_submission_xml_dir / Path("ERP125469_submission.xml")


@pytest.fixture(scope="module")
def study_submission_xml_content(study_submission_xml):
    with study_submission_xml.open() as f:
        return f.readlines()


@pytest.fixture(scope="module")
def assemblies_metadata():
    return Path(__file__).resolve().parent / Path("fixtures/test_metadata")


@pytest.fixture(scope="module")
def run_manifest(study_submission_xml_dir):
    return study_submission_xml_dir / Path("d41d8cd98f00b204e9800998ecf8427e.manifest")


@pytest.fixture(scope="module")
def run_manifest_content(run_manifest):
    with run_manifest.open() as f:
        return f.readlines()


@pytest.fixture
def run_public():
    return {
        "run_accession": "ERR4918394",
        "sample_accession": "SAMEA7687881",
        "instrument_model": "DNBSEQ-G400",
    }


#   the sample is different for private - reports API returns primary sample
@pytest.fixture
def run_private():
    return {
        "run_accession": "ERR4918394",
        "sample_accession": "ERS5444411",
        "instrument_model": "DNBSEQ-G400",
    }


@pytest.fixture
def study_data():
    return {
        "study_accession": "PRJEB41657",
        "study_title": "HoloFood Salmon Trial A+B Gut Metagenome",
        "first_public": "2022-08-02",
    }
