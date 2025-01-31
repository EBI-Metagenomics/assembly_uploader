# ENA Assembly uploader
Upload of metagenome and metatranscriptome assemblies to the [European Nucleotide Archive (ENA)](https://www.ebi.ac.uk/ena)

Pre-requisites:
- CSV metadata file. One per study. See test/fixtures/test_metadata for an example
- Compressed assembly fasta files in the locations defined in the metadata file

Set the following environmental variables with your webin details:

ENA_WEBIN
```
export ENA_WEBIN=Webin-0000
```

ENA_WEBIN_PASSWORD
```
export ENA_WEBIN_PASSWORD=password
```

## Installation

Install the package:

```bash
pip install assembly-uploader
```

## Usage
### From the command line
#### Register study and generate pre-upload files

**If you already have a registered study accession for your assembly files skip to step 3.**

#### Step 1: generate XML files for a new assembly study submission
This step will generate a folder STUDY_upload and a project XML and submission XML within it:

```bash
study_xmls
  --study STUDY         raw reads study ID
  --library LIBRARY     metagenome or metatranscriptome
  --center CENTER       center for upload e.g. EMG
  --hold HOLD           hold date (private) if it should be different from the provided study in format dd-mm-yyyy. Will inherit the release date of the raw read study if not
                        provided.
  --tpa                 use this flag if the study is a third party assembly. Default False
  --publication PUBLICATION
                        pubmed ID for connected publication if available
  --private             use flag if your data is private
```

#### Step 2: submit the new assembly study to ENA

This step submit the XML to ENA and generate a new assembly study accession. Keep note of the newly generated study accession:

```bash
submit_study
  --study STUDY         raw reads study ID
  --test                run test submission only
```

#### Step 3: make a manifest file for each assembly

This step will generate manifest files in the folder STUDY_UPLOAD for runs specified in the metadata file:

```bash
assembly_manifest
  --study STUDY         raw reads study ID
  --data DATA           metadata CSV - run_id, coverage, assembler, version, filepath
  --assembly_study ASSEMBLY_STUDY
                        pre-existing study ID to submit to if available. Must exist in the webin account
  --force               overwrite all existing manifests
  --private             use flag if your data is private
  --tpa                 use this flag if the study is a third party assembly. Default False
```

#### Step 4: upload assemblies

Once manifest files are generated, it is necessary to use ENA's webin-cli resource to upload genomes.

To test your submission add the `-test` argument.

A live execution example within this repo is the following:
```bash
ena-webin-cli \
  -context=genome \
  -manifest=SRR12240187.manifest \
  -userName=$ENA_WEBIN \
  -password=$ENA_WEBIN_PASSWORD \
  -submit
```

#### Optional step 5: publicly releasing a private study
```bash
release_study
  --study STUDY         study ID (e.g. of the assembly study)
  --test                run test submission only
```

More information on ENA's webin-cli can be found [in the ENA docs](<https://ena-docs.readthedocs.io/en/latest/submit/general-guide/webin-cli.html>).

### From a Python script
This `assembly_uploader` can also be used a Python library, so that you can integrate the steps into another Python workflow or tool.

```python
from pathlib import Path

from assembly_uploader.study_xmls import StudyXMLGenerator, METAGENOME
from assembly_uploader.submit_study import submit_study
from assembly_uploader.assembly_manifest import AssemblyManifestGenerator

# Generate new assembly study XML files
StudyXMLGenerator(
    study="SRP272267",
    center_name="EMG",
    library=METAGENOME,
    tpa=True,
    output_dir=Path("my-study"),
).write()

# Submit new assembly study to ENA
new_study_accession = submit_study("SRP272267", is_test=True, directory=Path("my-study"))
print(f"My assembly study has the accession {new_study_accession}")

# Create manifest files for the assemblies to be uploaded
# This assumes you have a CSV file detailing the assemblies with their assembler and coverage metadata
# see tests/fixtures/test_metadata for an example
AssemblyManifestGenerator(
    study="SRP272267",
    assembly_study=new_study_accession,
    assemblies_csv=Path("/path/to/my/assemblies.csv"),
    output_dir=Path("my-study"),
).write()
```

The ENA submission requires `webin-cli`, so follow [Step 4](#step-4-upload-assemblies) above.
(You could still call this from Python, e.g. with `subprocess.Popen`.)

Finally, you can also publicly release a private/embargoed/held study:
```python
from assembly_uploader.release_study import release_study
release_study("SRP272267")
```

## Development setup
Prerequisites: a functioning conda or pixi installation.

To install the assembly uploader codebase in "editable" mode:

```bash
conda env create -f requirements.yml
conda activate assemblyuploader
pip install -e '.[dev,test]'
pre-commit install
```

### Testing
```
pytest
```
