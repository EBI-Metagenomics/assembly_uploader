# ENA Assembly uploader
Upload of metagenome and metatranscriptome assemblies to the [European Nucleotide Archive (ENA)](https://www.ebi.ac.uk/ena)

Pre-requisites:
- CSV metadata file. One per study. See `tests/fixtures/test_metadata` for an example
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
This step will generate a folder `<STUDY>_upload` and a project XML and submission XML within it:

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

This step submit the XML to ENA and generate a new assembly study accession. Keep note of the newly generated study accession.
> [!NOTE]
> 
> We recommend to submit study to TEST server first using `--test` argument. If no errors occur then re-run command **without** `--test` for live submission.

```bash
submit_study
  --study STUDY         raw reads study ID
  --directory PATH      directory containing study XML
  --test                run test submission only
```

#### Step 3: make a manifest file for each assembly
> [!IMPORTANT]
> **Please read carefully before creating manifest files for co-assemblies:**
> 1. **Co-assemblies cannot be generated from a mix of private and public runs** - all runs used in a co-assembly must have the same privacy status (all private or all public).
> 2. **If your co-assembly was assembled from runs generated from multiple biological samples, you must first register a co-assembly sample** (see [ENA FAQ on co-assemblies](https://ena-docs.readthedgets.io/en/latest/faq/metagenomes.html#how-do-i-register-samples-for-co-assemblies)) and then specify it in the `Sample` column of your metadata CSV file.

This step will generate manifest files in the folder `<STUDY>_upload` for runs specified in the metadata file:

```bash
assembly_manifest
  --study STUDY         raw reads study ID
  --data DATA           metadata CSV - runs (comma-separated and in quotes, example: "SRR1234,SRR5678"), coverage, assembler, version, filepath and optionally sample
  --assembly_study ASSEMBLY_STUDY
                        pre-existing study ID to submit to if available. Must exist in the webin account
  --force               overwrite all existing manifests
  --private             use flag if your data is private
  --tpa                 use this flag if the study is a third party assembly. Default False
```

#### Step 4: upload assemblies

Once manifest files are generated, it is necessary to use ENA's [webin-cli](https://github.com/enasequence/webin-cli) resource to upload genomes.

We recommend to use a pre-installed [**webin_cli_handler**](https://github.com/EBI-Metagenomics/mgnify-pipelines-toolkit/blob/dev/mgnify_pipelines_toolkit/ena/webin_cli_handler.py) script.

> [!NOTE]
> 
> First, validate your submission with `--mode validate`. \
> Second, upload to TEST server using `--test` (make sure you have submitted a study to TEST server on Step 2). 

Run live execution:

```bash
webin_cli_handler \
  --manifest *.manifest \
  --context genome \
  --mode submit \
  [--test]
```
If you do not have ena-webin-cli installed add `--download-webin-cli`. \
If you want to use local Java .jar provide it with `--webin-cli-jar`.

Other options:
```bash
webin_cli_handler 

  -h, --help            show this help message and exit
  -m, --manifest MANIFEST
                        Manifest text file containing file and metadata fields
  -c, --context {genome,transcriptome,sequence,polysample,reads,taxrefset}
                        Submission type: genome, transcriptome, sequence, polysample, reads, taxrefset
  --mode {submit,validate}
                        submit or validate
  --test                Specify to use test server instead of live
  --workdir WORKDIR     Path to working directory
  --download-webin-cli  Specify if you do not have ena-webin-cli installed
  --download-webin-cli-directory DOWNLOAD_WEBIN_CLI_DIRECTORY
                        Path to save webin-cli into
  --download-webin-cli-version DOWNLOAD_WEBIN_CLI_VERSION
                        Version of ena-webin-cli to download, default: latest
  --webin-cli-jar WEBIN_CLI_JAR
                        Path to pre-downloaded webin-cli.jar file to execute
  --retries RETRIES     Number of retry attempts (default: 3)
  --retry-delay RETRY_DELAY
                        Initial retry delay in seconds (default: 5)
  --java-heap-size-initial JAVA_HEAP_SIZE_INITIAL
                        Java initial heap size in GB (default: 10)
  --java-heap-size-max JAVA_HEAP_SIZE_MAX
                        Java maximum heap size in GB (default: 10)
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
