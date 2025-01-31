import pytest
import responses

from assembly_uploader.release_study import StudyReleaseError, release_study
from assembly_uploader.webin_utils import (
    ENA_WEBIN,
    ENA_WEBIN_PASSWORD,
    ensure_webin_credentials_exist,
)


def test_release_study(study_submission_xml_dir, monkeypatch, tmp_path):
    ena_dropbox = responses.add(
        responses.POST,
        "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit",
        body="""
        This is a long receipt from the dropbox.
        success="true"
        Your study was released.
        """,
    )

    with pytest.raises(Exception):
        ensure_webin_credentials_exist()

    monkeypatch.setenv(ENA_WEBIN, "fake-webin-999")
    monkeypatch.setenv(ENA_WEBIN_PASSWORD, "fakewebinpw")

    ensure_webin_credentials_exist()

    release_study("SRP272267", is_test=True, xml_path=tmp_path / "test.xml")
    assert ena_dropbox.call_count == 1
    assert (tmp_path / "test.xml").is_file()
    assert '<RELEASE target="SRP272267"/>' in (tmp_path / "test.xml").read_text()

    responses.add(
        responses.POST,
        "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit",
        body="""
        Could not release
        """,
    )
    with pytest.raises(StudyReleaseError):
        release_study("SRP272267", is_test=True, xml_path=tmp_path / "test.xml")
