# Towards Reusable Retro-Digitization for Historical Dictionaries

This repository accompanies the MA thesis **Towards Reusable Retro-Digitization
for Historical Dictionaries: A Transferable Parsing-and-Encoding Workflow**
by Sergei Stoliarov, completed in 2026 at Ca' Foscari University of Venice. 

The project investigates the rule-based retro-digitization of historical
dictionaries and their conversion into structured TEI Lex-0 data. It contains
separate parsing-and-transformation pipelines for:

1. John R. Clark Hall's *A Concise Anglo-Saxon Dictionary*;
2. Henry Sweet's *The Student's Dictionary of Anglo-Saxon*.

Clark Hall is the principal case study. Sweet is used as a limited
near-transfer experiment for assessing how far the workflow and encoding
principles can be transferred to a second historical dictionary.

## Viewing and using the repository

Most files can be inspected directly on GitHub without downloading the repository. Some large output or diagnostic files may exceed GitHub's browser display limit; these files can still be downloaded or opened through the Raw option.

The Python scripts cannot be run from the ordinary GitHub file view.

To run the pipelines, download or clone the repository to a computer with Python installed:

* For the simplest option, click **Code** on the repository page and select **Download ZIP**, then extract the downloaded archive.
* To obtain a Git-controlled copy, clone the repository with Git or GitHub Desktop.

The commands below must be run from the repository's top-level folder, the folder that contains `README.md`, `src/`, `data/`, and `docs/`.

## Repository structure

### `src/`

* `CAS_parser.py` - the rule-based parser and TEI transformer for Clark Hall's
  dictionary.
* `SWT_parser.py` - the rule-based parser and TEI transformer for Sweet's
  dictionary.

### `data/input/`

Source text files supplied to the parsers.

* `CAS_all_entries.txt` - the complete Clark Hall input used for the principal
  conversion.
* `SWT_1000.txt` - the 1,000-entry Sweet sample used for the transfer
  experiment.
* `CAS_test_sample.txt` - a small Clark Hall test file for checking that the
  parser runs correctly.
* `SWT_test_sample.txt` - a small Sweet test file for checking that the parser
  runs correctly.

### `data/manual/`

Manually encoded TEI Lex-0 entries used to formulate, document, and check the
encoding policy.

* `CAS_manual_encodings.xml` - curated Clark Hall encodings.
* `SWT_manual_encodings.xml` - curated Sweet encodings.

### `data/output/`

TEI XML produced by the automatic conversion pipelines.

* `CAS_all_entries_transformed.xml` - automatically transformed complete Clark
  Hall dataset.
* `CAS_manual_entries_transformed.xml` - automatic output for the manually
  selected Clark Hall entries.
* `CAS_random_1000_entries_transformed.xml` - automatic output for the random
  1,000-entry Clark Hall evaluation sample.
* `SWT_1000_transformed.xml` - automatic output for the Sweet
  1,000-entry sample.

The automatically generated XML should not be treated as manually verified.
The files in `data/manual/` document the intended encoding more precisely.

### `data/diagnostics/`

Diagnostic files produced during parsing.

* Files ending in `_failed.txt` contain entries that were not successfully
  parsed or transformed.
* Files ending in `_parse_trees.txt` contain serialized parse trees used for
  inspection, debugging, and analysis.

### `docs/`

* `CAS_and_SWEET_encoding_policy.ipynb` - the encoding policy and the documented
  editorial decisions for Clark Hall and Sweet.

## Requirements

The pipelines require:

* Python 3.10 or later. The released version was developed and tested with
  Python 3.11.5.
* Lark 1.2.2, installed through `requirements.txt`.

All source, input, and output files use UTF-8 encoding because the dictionaries
contain Old English characters and diacritics.

## Installation

### 1. Install Python

Install Python 3 if it is not already installed. On Windows, make sure that the
installer option for adding Python to `PATH` is enabled.

Check the installation by opening Command Prompt and running:

```cmd
python --version
```

On some Windows installations, the Python launcher is used instead:

```cmd
py --version
```

The released version was developed and tested with Python 3.11.5.

### 2. Open a terminal in the repository's top-level folder

The commands below work only when the terminal is opened in the repository's
top-level folder - the folder containing `README.md`, `requirements.txt`,
`src/`, `data/`, and `docs/`.

On Windows:

1. Open the repository folder in File Explorer.
2. Click the File Explorer address bar.
3. Type `cmd` and press Enter.

A Command Prompt window will open in that folder. To verify that the location
is correct, run:

```cmd
dir
```

The listing should include at least:

```text
README.md
requirements.txt
src
data
docs
```

If Command Prompt is already open somewhere else, navigate to the repository
with:

```cmd
cd /d "path\to\Towards-Reusable-Retro-Digitization-for-Historical-Dictionaries"
```

Replace `path\to` with the actual location of the cloned or extracted
repository. The `/d` option also allows the command to change drives.

On macOS or Linux, open a terminal, use `cd` to enter the repository folder,
and run `ls` to verify that the same files and folders are present.

### 3. Install the dependencies

From the repository's top-level folder, run:

```cmd
python -m pip install -r requirements.txt
```

If your Windows installation uses the `py` launcher, run:

```cmd
py -m pip install -r requirements.txt
```

## Running and testing the pipelines

Run all commands from the repository's top-level folder.

### Test the Clark Hall pipeline

Use the small test file first:

```cmd
python src/CAS_parser.py data/input/CAS_test_sample.txt
```

With the Windows `py` launcher:

```cmd
py src/CAS_parser.py data/input/CAS_test_sample.txt
```

A successful run prints a parsing summary and creates:

```text
data/output/CAS_test_sample_transformed.xml
data/diagnostics/CAS_test_sample_parse_trees.txt
data/diagnostics/CAS_test_sample_failed.txt
```

### Test the Sweet pipeline

```cmd
python src/SWT_parser.py data/input/SWT_test_sample.txt
```

With the Windows `py` launcher:

```cmd
py src/SWT_parser.py data/input/SWT_test_sample.txt
```

A successful run prints a parsing summary and creates:

```text
data/output/SWT_test_sample_transformed.xml
data/diagnostics/SWT_test_sample_parse_trees.txt
data/diagnostics/SWT_test_sample_failed.txt
```

The presence of entries in a `_failed.txt` file does not mean that the script
itself failed. It means that those particular dictionary entries were not
successfully parsed. The console summary reports the number and percentage of
successful and failed entries.

### Run the complete Clark Hall input

```cmd
python src/CAS_parser.py data/input/CAS_all_entries.txt
```

### Run the Sweet 1,000-entry sample

```cmd
python src/SWT_parser.py data/input/SWT_1000.txt
```

To process another compatible text file, replace the input-file path in the
relevant command with the path to that file.

Existing output files with the same names are overwritten when a parser is run
again. The small test inputs have distinct filenames and therefore do not
overwrite the reference outputs produced from the complete Clark Hall input or
the Sweet 1,000-entry sample.

### Troubleshooting: `can't open file ... src\..._parser.py`

This error normally means that the command was run from the wrong folder. For
example, if the prompt shows only a user directory rather than the repository
directory, Python looks for `src/` in the wrong place.

Navigate to the repository's top-level folder first, verify it with `dir` or
`ls`, and then run the parser command again.

## Pipeline overview

Each dictionary has a separate parser.

At a general level, each pipeline:

1. reads dictionary entries from a UTF-8 text file;
2. applies a dictionary-specific formal grammar;
3. constructs parse trees;
4. transforms successfully parsed structures into TEI XML;
5. records entries that could not be parsed or transformed;
6. writes parse-tree diagnostics for inspection and debugging.

## Outputs and diagnostics

When a parser is run, transformed TEI XML is written to `data/output/`.
Parse-tree reports and failed-entry reports are written to
`data/diagnostics/`.

Output filenames are derived from the input filename. For example,
`CAS_test_sample.txt` produces:

```text
data/output/CAS_test_sample_transformed.xml
data/diagnostics/CAS_test_sample_parse_trees.txt
data/diagnostics/CAS_test_sample_failed.txt
```

The Sweet parser follows the same naming pattern. Existing files with the same
names are overwritten when the relevant parser is run again.

Reference outputs from the thesis experiments are included in `data/output/`
and `data/diagnostics/`. A successfully generated XML entry should not
automatically be treated as a fully verified semantic encoding. The manually
encoded files and the encoding-policy notebook document the intended analysis
and should be consulted when evaluating the automatic output.

## TEI Lex-0 validation

The XML is intended to follow TEI Lex-0. However, the project also preserves several encoding decisions that are not permitted by the current TEI Lex-0 schema. Consequently, some of the XML files are not fully schema-valid in their present form.

The files use the following TEI Lex-0 schema association:

```xml
<?xml-model href="https://lex-0.org/schema/lex-0.rng"
  type="application/xml"
  schematypens="http://relaxng.org/ns/structure/1.0"?>
```

The XML files can be opened and validated in an XML editor such as Oxygen XML Editor. Validation errors should therefore not automatically be interpreted as accidental encoding errors: some reflect deliberate project-specific decisions documented in the encoding-policy notebook.

## Source dictionaries and digital transcriptions

### Clark Hall

Print source:

Clark Hall, John R. *A Concise Anglo-Saxon Dictionary for the Use of Students*. Second edition, revised and enlarged. New York: The Macmillan Company, 1916.

The digital input was derived from the Project Gutenberg transcription, eBook no. 31543, produced by Louise Hope, Zoran Stefanovic, the Germanic Lexicon Project, and the Online Distributed Proofreading Team.

[Project Gutenberg eBook 31543](https://www.gutenberg.org/ebooks/31543)

### Sweet

Print source:

Sweet, Henry. *The Student's Dictionary of Anglo-Saxon*. Oxford: Clarendon Press, 1897.

The digital input and manual encoding were prepared with reference to Mike Pope's online transcription.

[Sweet Anglo-Saxon Dictionary: Entries](https://mikepope.com/sweet/sweet-dictionary-entries.html)

This repository does not claim copyright in the underlying historical dictionary texts or in third-party digital transcriptions.

## Known limitations

* The parsing grammars are dictionary-specific.
* Some entries remain unparsed and are recorded in the `_failed.txt` files.
* Successful parsing does not guarantee semantically perfect TEI encoding.
* Source typography and inconsistencies in the digital transcriptions may affect parsing.
* The Sweet experiment uses a limited sample and is not presented as evidence of unrestricted portability to arbitrary historical dictionaries.
* The manual encoding policy includes project-specific editorial decisions that may go beyond the restrictions imposed by the TEI Lex-0 schema.

## Licensing and terms of use

Copyright © 2026 Sergei Stoliarov. All rights reserved.

This repository is publicly available for examination, verification, citation, and scholarly consultation. No permission is granted to copy, modify, redistribute, republish, or incorporate the original software, encodings, generated outputs, diagnostics, or documentation into another resource without prior written permission, except where permitted by applicable law or GitHub's Terms of Service.

The underlying historical texts and third-party transcriptions retain their own copyright status and applicable terms.

See the `LICENSE` file for the complete terms.

## Citation

When referring to this repository, please cite:

Stoliarov, Sergei. 2026. *Towards Reusable Retro-Digitization for Historical Dictionaries: A Transferable Parsing-and-Encoding Workflow*. GitHub repository. https://github.com/Serg078/Towards-Reusable-Retro-Digitization-for-Historical-Dictionaries/
