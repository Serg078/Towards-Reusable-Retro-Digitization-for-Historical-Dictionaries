# Sources and provenance

This file records the print editions, digital transcriptions, and derived
research materials used in this repository.

## 1. Clark Hall

### Print edition

Clark Hall, John R. *A Concise Anglo-Saxon Dictionary for the Use of
Students*. Second edition, revised and enlarged. New York: The Macmillan
Company, 1916.

### Digital transcription

The Clark Hall input was derived from Project Gutenberg eBook no. 31543:

- https://www.gutenberg.org/ebooks/31543

The Project Gutenberg transcription credits Louise Hope, Zoran Stefanovic,
the Germanic Lexicon Project, and the Online Distributed Proofreading Team.

Project Gutenberg identifies this eBook as public domain in the United States.
Users outside the United States should check the copyright law applicable in
their own jurisdiction. Use of the Project Gutenberg name and redistribution
of Project Gutenberg-branded material remain subject to the Project Gutenberg
licence and trademark terms:

- https://www.gutenberg.org/policy/license.html

### Repository files derived from this source

- `data/input/CAS_all_entries.txt` contains the Clark Hall input used by the
  parser.
- `data/input/CAS_test_sample.txt` contains a small test sample drawn from the
  Clark Hall input.
- `data/manual/CAS_manual_encodings.xml` contains manually prepared TEI Lex-0
  encodings and editorial analysis.
- Files beginning with `CAS_` in `data/output/` and `data/diagnostics/` were
  generated or curated during the conversion and evaluation process.

## 2. Sweet

### Print edition

Sweet, Henry. *The Student's Dictionary of Anglo-Saxon*. Oxford: Clarendon
Press, 1897.

### Digital transcription

The Sweet input and manual encoding were prepared with reference to Mike
Pope's online transcription:

- https://mikepope.com/sweet/sweet-dictionary-entries.html
- https://mikepope.com/sweet/sweet-dictionary-about.html

No licence for the third-party transcription is asserted by this repository.
The transcription remains subject to any terms stated by its creator and to
applicable law.

### Repository files derived from this source

- `data/input/SWT_1000.txt` contains the 1,000-entry Sweet sample used for the
  near-transfer experiment.
- `data/input/SWT_test_sample.txt` contains a small Sweet test sample.
- `data/manual/SWT_manual_encodings.xml` contains manually prepared TEI Lex-0
  encodings and editorial analysis.
- Files beginning with `SWT_` in `data/output/` and `data/diagnostics/` were
  generated or curated during the conversion and evaluation process.

## 3. Original project contributions

The original contributions of this project include:

- the rule-based parsing grammars and Python implementations in `src/`;
- the transformation logic used to generate TEI XML;
- the manually prepared TEI Lex-0 encodings;
- the encoding policy and documented editorial decisions;
- the generated outputs, diagnostic reports, evaluation materials, and
  repository documentation.

Copyright in these original contributions is held by Sergei Stoliarov, as
described in the repository's `LICENSE` file.

## 4. Scope of the repository licence

The repository licence applies only to original contributions created for this
project. It does not alter the copyright status, licence, or terms of use of
the underlying historical dictionaries or third-party digital transcriptions.

Source attribution does not imply endorsement by Project Gutenberg, Mike Pope,
or any other source provider.
