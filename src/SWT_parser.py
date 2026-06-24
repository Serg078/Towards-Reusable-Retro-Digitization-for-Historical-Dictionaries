"""
Sweet dictionary parser with TEI transformer.

The parser retains parse-tree and failed-entry reports, writes a TEI-style
transformed-output file, and handles lemma forms, run-on nesting,
homonymic entries, entry-level grammatical information, nested lemma variants,
and minimal senses/examples.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

from lark import Lark, Tree, Transformer, Token
from lark.exceptions import ParseError


GRAMMAR = r"""
?start: entry | runon_entry
entry: headword preceding_content? main_content subsequent_content? "</entry>"
runon_entry: runon_headword preceding_content? main_content subsequent_content? "</entry>" 

preceding_content: ( gramgrp | VERB_INFL_TYPE | infl_form)+
main_content: hom_entry+ | (bibl | (sense_sections related_entry*) )| xr_section+ sense_section?
subsequent_content: etym? DOT_SEP | etym

hom_entry: ROM_NUM preceding_content? ((sense_sections related_entry?) | xr_section) subsequent_content? 
related_entry: (EM_DASH gramgrp? rel_form | DOT_SEP gramgrp? rel_expr) sense_sections 

headword: "<entry source_id=" WORD ">" (var_plus_gen_sequence | lemma_form) 
runon_headword: "<entry source_id=" WORD ">" (runon_var_plus_gen_sequence | runon_lemma_form)
lemma_form: ("<span class=entryPrefix>"WORD"</span>")?"<form>" HYPHEN? ("</form><span class=entryPrefix>"WORD"</span><form>")? WORD HYPHEN? "</form>" ((COMMA "<form>" WORD "</form>" )? "(" "<form>" (WORD|BAR|MID_DOT|HYPHEN)+ "</form>" ")")? ( COMMA "<form>" WORD "</form>" LP "<form>" WORD "</form>" RP)? ASTERISK? qm? usage? variant_form*
runon_lemma_form: ("<span class=entryPrefix>"WORD"</span>")? "<form>" TILDE ("</form><span class=entryPrefix>"WORD"</span><form>")? WORD "</form>" ASTERISK? usage? variant_form*
rel_form: usage? "<form>" TILDE? WORD "</form>" 
rel_expr: usage? "<expr>" TILDE? WORD+ "</expr>"
variant_form.10: (COMMA|SEMICOL_SEP) usage? "<form>" (TILDE? ("</form><span class=entryPrefix>"WORD"</span><form>")? WORD | TILDE? WORD? HYPHEN WORD?) "</form>" qm? usage?
sense_var_form: COMMA? "<form>" WORD "</form>"
infl_form.10: (COMMA | SEMICOL_SEP)* gramgrp "<form>" (TILDE | HYPHEN | WORD)+ "</form>" variant_form*
var_plus_gen_sequence.50: "<form>" WORD "</form>" ("(" "<form>" WORD (BAR|MID_DOT|HYPHEN) WORD "</form>" ")")? "<meta>" GEN USGTEMP? "</meta>" ( COMMA "<form>" TILDE? (WORD HYPHEN)? WORD "</form>" "<meta>" GEN USGTEMP? "</meta>")+
runon_var_plus_gen_sequence.50: "<form>" TILDE WORD "</form>" "<meta>" GEN "</meta>" ( COMMA "<form>" TILDE WORD "</form>" "<meta>" GEN "</meta>")+

gramgrp: gram+ 
gram: LP? "<meta>" (lbl? (GEN | POS | CASE | NODOTGEN? NUM | TNS | PERS | MOOD | DGR | DECL | VALEN | PTC  ))+ "</meta>"? COMMA? qm? RP?
xr_gramgrp: xr_gram+ 
xr_gram: LP? "<meta>" (GEN | POS | CASE | NODOTGEN? NUM | TNS | PERS | MOOD | DGR | DECL | VALEN | PTC)  
sense_gramgrp: sense_gram+ 
sense_gram: "<meta>" (lbl?(TNS | PERS | MOOD | DGR | DECL | VALEN | PTC | construction ))+ "</meta>"?

construction: (usglbl+ ( (CASE | POS )+ | "</meta><expr>" WORD "</expr>"|lbl? "</meta><form>" WORD "</form>" )) (COMMA usglbl+ (CASE | POS))* | constr_extra 
constr_extra: CONSTR

sense_sections: sense_section (BAR sense_section)* 
sense_section: (usage| sense_gramgrp)* (cit_exmpl (COMMA cit_exmpl)* | sense) (semicolsep (sense|cit_exmpl(COMMA cit_exmpl)*))* ((cit_exmpl(COMMA cit_exmpl)*)* (semicolsep sense)* cit_exmpl?)* 
sense: sense_var_form? sense_gramgrp? usage? cit usage? sense_gramgrp?
cit: quote+
cit_exmpl: quote_exmpl
!quote: (("<meta>or</meta>")|("<meta>tr.</meta><meta>and intr.</meta>,") | TRANSLATION | qm | gloss)+
quote_exmpl: (EM_DASH | COL_SEP)? "<expr>" EXAMPLE "</expr>" cit_trnsl?
cit_trnsl.10: quote
gloss: GLOSS  ("<meta>" lbl TRANSLATION "</meta>")?
semicolsep: SEMICOL_SEP
usage: "<meta>"? LBL? (usg_geo | usg_meantype | usg_temp | usg_freq | usg_ttype) "</meta>"? DOT_SEP?

bibl: SOURCE

xr_section: xr_gramgrp? REFLBL "</meta>"? refword+ COMMA?
refword: COMMA? "<form>" (HYPHEN | WORD)+ "</form>"
etym: DOT_SEP? LSQBR (("<form>" WORD "</form>")(SEMICOL_SEP "<form>" WORD "</form>")? | "<meta>" LANG "</meta>" DOT_SEP? (COMMA? "<form>" WORD "</form>")* ) RSQBR 

lbl: LBL+ 
usglbl: USGLBL
usg_geo: usglbl? DIALECT
usg_meantype: usglbl? MEANINGTYPE
usg_temp: USGTEMP
usg_freq: USGFREQ
usg_ttype: POET_SYMB

WORD: /[_\(\)ėęþāäæÐÆǣēīōöðȳūüa-zA-Z\*0-9"]+/
TRANSLATION:/((<meta>the Runic letter<\/meta>)?[a-zA-Z\-\*’'…&]+(\s[a-zA-Z\-\*’'…&]+)*)(,\s([a-zA-Z\-\*’'…&]+(\s[a-zA-Z\-\*’'…&]+)*))*,?/
EXAMPLE: /([~ęėþāäæÐÆǣēīōöðȳūüa-zA-Z\-\*\(\)…]+(\s[~ęėþāäæÐÆǣēīōöðȳūüa-zA-Z\-\*\(\)…]+)*)(,\s([~ėęþāäæÐÆǣēīōöðȳūüa-zA-Z\-\*\(\)…]+(\s[~ėęþāäæÐÆǣēīōöðȳūüa-zA-Z\-\*\(\)…]+)*))*/
GLOSS:/\(((<meta>of<\/meta>)?[&a-zA-Z\-\*]+(<meta>or<\/meta>)?(\s?[&a-zA-Z\-\*]+)*)(,\s([&a-zA-Z\-\*]+(\s[&a-zA-Z\-\*]+)*))*\),?/
SOURCE:/Gl|Ct/

ROM_NUM: /\s?[IV]{1,4}\./
POET_SYMB: /†/
REFLBL: /=|of|<meta>see<\/meta>/
qm: LP? QM RP?

GEN: /[mnf]{1,3}[.,]{1,2}\s?/
NODOTGEN.1:/[mnf]{1,3}/
POS: /\(?(interj\.|sbj\.|sv\.|wv\.|\bsv\b|\bwv\b|sb\.|vb\.|anv\.|swv\.|aj\.|av\.|prp\.|pron\.|num\.|cj\.),?\)?\s?/
PTC:/ptc\.|pp\./
CASE:/[nagdi]{1,2}\.?/
NUM:/(sbpl\.|sg\.|sing\.|pl\.|(?<!\s)[sp]\.?)\,?\s?/
TNS:/(prt\.|pres\.),?\s?/
PERS.1:/[1-3]\.?,?\s?/
MOOD: /(interr\.|ind\.|imperat\.|subj\.),?\s?/
DGR: /\(?(comp\.|sup\.|superl\.)\)?,?\s?/
DECL.5: /(indecl\.|strong|wk\.),?/
VALEN: /\(?(tr\.|intr\.|intr|rfl\.|pers\.\sand\simpers\.|impers\.|pers\.|tr\.\sintr\.)\)?,?\s?/
VERB_INFL_TYPE.5: /[1-7](,\s[1-7])?/
CONSTR:/correl\.\s?/

LBL.5: /(and|or|also|from|but|of)(?=\s)/
USGLBL.10: /(occl\.|often|rare\s|only|in\s|but\susu\.|usu\.|rarely|esp\.|w\.\s?|w|used\sas)+/
DIALECT.1: /(A|W|N|lN|lM|lA)\.?/
MEANINGTYPE:/met\.|fig\./
USGTEMP: /L\.|L|vL/
USGFREQ: /once/

LANG:/Lt\.|Lt|Fr\.|Scand\.|Celtic/

LP: /\(/
RP:/\)/
SEMICOL_SEP.10: /;/
COL_SEP.10: /:/
DOT_SEP.10: /\./
BAR: /(\|\|)|(\|)/
MID_DOT:/·/
COMMA.10: /,/
TILDE: /~/
EM_DASH: /—/
LSQBR: /\[/
RSQBR:/\]/
ASTERISK: /\*/
HYPHEN: /\-/
QM: /\?|!/

%ignore " "
%import common.NEWLINE
%ignore NEWLINE        
"""


def normalize_entry_text(text: str) -> str:
    """Normalize whitespace and common typographic characters before parsing."""
    cleaned_text = (
        text
        .replace("\u00A0", " ")   # non-breaking space
        .replace("\u2018", "'")   # left single quote
        .replace("\u2019", "'")   # right single quote
        .replace("\u201C", '"')   # left double quote
        .replace("\u201D", '"')   # right double quote
        .replace("&amp;c", "&c")
        .replace("&amp;c.", "&c")
        .replace('<span class="entryPrefix">', '<span class=entryPrefix>')
        .replace("\n", " ")
        .replace("\r", " ")
    )
    return re.sub(r"\s+", " ", cleaned_text).strip()

def plain_entry_text(text: str) -> str:
    """Return a readable tag-free version of an entry for logs/debug output."""
    text = re.sub(r"<entry\b[^>]*>", " ", text)
    text = text.replace("</entry>", " ")

    # Replace structural tags with spaces so words do not collapse together.
    text = re.sub(r"</?(form|meta|expr)>", " ", text)
    text = re.sub(r'<span class=entryPrefix>', " ", text)
    text = re.sub(r'<span class="entryPrefix">', " ", text)
    text = text.replace("</span>", " ")

    # Fallback: remove any remaining tags, again leaving a space.
    text = re.sub(r"<[^>]+>", " ", text)

    # Clean spacing around punctuation.
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    text = re.sub(r"([,;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\[(\s+)", "[", text)
    text = re.sub(r"(\s+)\]", "]", text)

    return text.strip()

def extract_entries_from_content(content: str) -> list[str]:
    """Extract <entry>...</entry> blocks from files with or without blank lines.

    Sweet sample files often contain one entry per line, but not necessarily
    blank-line separation. The safest batch unit is therefore the XML-like
    <entry ...>...</entry> wrapper itself. If no wrappers are found, fall back
    to the older blank-line split for ad hoc test files.
    """
    matches = [
        match.group(0).strip()
        for match in re.finditer(r"<entry\b[^>]*>.*?</entry>", content, flags=re.DOTALL)
    ]
    if matches:
        return matches
    return [entry.strip() for entry in re.split(r"\n\s*\n", content) if entry.strip()]


def format_tree_simple(tree, indent: int = 0) -> str:
    """Format a Lark parse tree in a compact, readable form."""
    if isinstance(tree, Tree):
        result = "  " * indent + str(tree.data)
        for child in tree.children:
            if isinstance(child, Tree):
                result += "\n" + format_tree_simple(child, indent + 1)
            else:
                result += "	" + str(child)
        return result
    return "  " * indent + str(tree)




class SweetTEITransformer(Transformer):
    """Sweet -> TEI transformer, v10: lemma forms, run-ons, homonyms, grammar, variants, minimal senses/examples, current-entry tilde refs, and source labels."""

    XML_NS = "http://www.w3.org/XML/1998/namespace"
    DICT_PREFIX = "SWT"
    SOURCE_LABELS = {"Ct", "Gl", "Bd", "LL", "R"}

    SWEET_VARIANT_TABLE = {
        "a": ["æ", "ea"],
        "æ": ["a", "æg", "e", "ea"],
        "æi": ["æg"],
        "æig": ["æg"],
        "æo": ["ea"],
        "b": ["f"],
        "c": ["g", "h"],
        "ce": ["c"],
        "ch": ["c", "h"],
        "ci": ["c"],
        "cs": ["sc", "x"],
        "ct": ["ht"],
        "d": ["þ"],
        "dd": ["þd"],
        "ds": ["ts"],
        "ð": ["þ"],
        "e": ["æ", "ea", "eg", "eo", "ie", "y"],
        "ea": ["æ", "a", "eo", "gea", "i"],
        "ei": ["e", "eg"],
        "eo": ["e", "ea", "geo", "i", "ie", "oe"],
        "eu": ["eo", "eow"],
        "ew": ["eow"],
        "f": ["w"],
        "fn": ["mn"],
        "g": ["h", "w", "x"],
        "ge": ["g"],
        "gg": ["cg"],
        "gi": ["g"],
        "gu": ["geo"],
        "h": ["c", "g"],
        "hs": ["sc", "x"],
        "i": ["eo", "g", "ie", "ig", "ige", "y"],
        "ia": ["eo"],
        "ig": ["i"],
        "io": ["eo"],
        "iu": ["eo", "geo"],
        "iw": ["eow"],
        "k": ["c"],
        "m": ["mn", "n"],
        "nc": ["cen", "cn", "ng"],
        "ng": ["gen", "gn"],
        "o": ["a", "og"],
        "oe": ["e", "æ"],
        "ps": ["sp"],
        "pt": ["ft"],
        "qu": ["cw"],
        "sc": ["s"],
        "sce": ["sc"],
        "sci": ["sc"],
        "sþ": ["st"],
        "t": ["þ"],
        "th": ["þ"],
        "u": ["f", "ug", "v", "w"],
        "uu": ["ū", "w"],
        "v": ["f"],
        "weo": ["wo", "wu"],
        "wi": ["wu"],
        "wo": ["weo"],
        "wu": ["w", "weo", "wo", "wy"],
        "wy": ["weo", "wi"],
        "x": ["cs", "hs", "sc"],
        "y": ["e", "i", "ie", "yg"],
    }

    def __init__(self):
        super().__init__()
        ET.register_namespace("xml", self.XML_NS)
        self._reset_entry_state()

    """
    HELPERS
        
    """

    def _reset_entry_state(self) -> None:
        """Reset per-entry lemma tracking used later for variant expansion."""
        self._source_id = None
        self._lemma_value = None
        self._last_orth_base = None
        self._last_orth_text = None
        self._lemma_split = {
            "value": None,
            "text": None,
            "hyphen": None,
            "bar": None,
            "middle_dot": None,
        }
        self._sense_section_counter = 0

    def __default__(self, data, children, meta):
        """Flatten unimplemented rules so they do not break the step-2 transformer."""
        flat = []
        for child in children:
            if child is None:
                continue
            if isinstance(child, (list, tuple)):
                flat.extend(x for x in child if x is not None)
            else:
                flat.append(child)
        return flat

    def _tok_text(self, obj) -> str:
        return str(obj).strip()

    def _roman_to_int(self, roman: str) -> int:
        """Convert a small Roman numeral used for homonym numbers into an integer."""
        roman = (roman or "").upper().strip().rstrip(".")
        values = {"I": 1, "V": 5, "X": 10}
        total, previous = 0, 0
        for char in reversed(roman):
            value = values.get(char, 0)
            if value < previous:
                total -= value
            else:
                total += value
                previous = value
        return total or 1

    def _iter_tei_elements(self, obj):
        """Yield TEI elements from nested transformer output."""
        if obj is None:
            return
        if isinstance(obj, ET.Element):
            yield obj
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                yield from self._iter_tei_elements(item)
        elif isinstance(obj, dict):
            element = obj.get("element")
            if isinstance(element, ET.Element):
                yield element

    def _clean_source_id(self, obj) -> str:
        return self._tok_text(obj).strip('"')

    def _flat(self, obj):
        if obj is None:
            return
        if isinstance(obj, (list, tuple)):
            for item in obj:
                yield from self._flat(item)
        else:
            yield obj

    def _token_items(self, children):
        """Return relevant Token objects from a lemma-form rule."""
        wanted = {"WORD", "HYPHEN", "BAR", "MID_DOT", "COMMA", "SEMICOL_SEP", "TILDE"}
        items = []
        for child in self._flat(children):
            if isinstance(child, Token) and child.type in wanted:
                items.append(child)
        return items

    def _join_token_texts(self, items) -> str:
        return "".join(self._tok_text(item) for item in items)

    def _make_lemma_form(self, orth_el: ET.Element) -> ET.Element:
        form = ET.Element("form", {"type": "lemma"})
        form.append(orth_el)
        return form

    def _split_once_for_tracking(self, text: str, delimiter: str) -> dict | None:
        """Remember the material before and after a delimiter in a segmented lemma."""
        if not text or delimiter not in text:
            return None
        before, after = text.split(delimiter, 1)
        return {
            "delimiter": delimiter,
            "before": before,
            "after": after,
            "after_with_delimiter": delimiter + after,
        }

    def _record_lemma_tracking(self, value: str | None, orth_text: str | None) -> None:
        """
        Store enough information to expand later variant segments.

        For a printed segmentation such as Cant-war|e, this records the hyphen,
        bar, and middle-dot splits. Later variant logic can use this instead
        of trying to rediscover the structure from the XML output.
        """
        value = (value or "").strip() or None
        orth_text = (orth_text or value or "").strip() or None

        self._lemma_value = value
        self._last_orth_base = value.split(",", 1)[0].strip() if value else None
        self._last_orth_text = orth_text
        self._lemma_split = {
            "value": value,
            "text": orth_text,
            "hyphen": self._split_once_for_tracking(orth_text or "", "-"),
            "bar": self._split_once_for_tracking(orth_text or "", "|"),
            "middle_dot": self._split_once_for_tracking(orth_text or "", "·"),
        }

    def _orth_with_text_or_hyphen_segs(self, text: str, value: str | None = None) -> ET.Element:
        attrs = {}
        if value:
            attrs["value"] = self._clean_attr_form(value) or value
        orth = ET.Element("orth", attrs)

        # Encoding policy: only a hyphen in the displayed segmentation triggers <seg>.
        if "-" in text:
            split_at = text.index("-")
            ET.SubElement(orth, "seg").text = text[:split_at]
            ET.SubElement(orth, "seg").text = text[split_at:]
        else:
            orth.text = text

        return orth

    def _orth_from_prefix_parts(self, parts: list[str]) -> ET.Element:
        orth = ET.Element("orth")
        for part in parts:
            ET.SubElement(orth, "seg").text = part
        return orth

    def _pc(self, text: str) -> ET.Element:
        pc = ET.Element("pc")
        pc.text = text
        return pc

    def _clean_attr_form(self, text: str | None) -> str | None:
        """Remove source segmentation marks that should not appear in attribute values."""
        if text is None:
            return None
        cleaned = str(text).replace("|", "").replace("·", "")
        return cleaned

    def _with_trailing_comma(self, raw: str) -> tuple[str, bool]:
        text = (raw or "").strip()
        has_comma = text.endswith(",")
        if has_comma:
            text = text[:-1].strip()
        return text, has_comma

    def _return_with_optional_comma(self, element: ET.Element, has_comma: bool):
        if has_comma:
            return [element, self._pc(",")]
        return element

    def _make_plain_lbl(self, text: str) -> ET.Element:
        lbl = ET.Element("lbl")
        lbl.text = (text or "").strip()
        return lbl

    def _make_pos_gram(self, raw: str) -> ET.Element:
        text, has_comma = self._with_trailing_comma(raw)
        key = text.strip().strip("()").rstrip(".").lower()
        pos_map = {
            "interj": "interjection",
            "sbj": "subjunction",
            "sv": "strong verb",
            "wv": "weak verb",
            "sb": "noun",
            "vb": "verb",
            "anv": "anomalous verb",
            "swv": "strong-weak verb",
            "aj": "adjective",
            "av": "adverb",
            "prp": "preposition",
            "pron": "pronoun",
            "num": "numeral",
            "cj": "conjunction",
        }
        gram = ET.Element("gram", {"type": "pos", "value": pos_map.get(key, key)})
        gram.text = text.strip().strip("()")
        return self._return_with_optional_comma(gram, has_comma)

    def _case_value(self, raw: str) -> str | None:
        key = (raw or "").strip().rstrip(".").lower()
        mapping = {
            "n": "nominative",
            "a": "accusative",
            "g": "genitive",
            "d": "dative",
            "i": "instrumental",
        }
        if key in mapping:
            return mapping[key]
        if key and all(ch in mapping for ch in key):
            return ", ".join(mapping[ch] for ch in key)
        return None

    def _make_simple_gram(self, gram_type: str, raw: str, value: str | None = None) -> ET.Element | list[ET.Element]:
        text, has_comma = self._with_trailing_comma(raw)
        text = text.strip().strip("()")
        attrs = {"type": gram_type}
        if value:
            attrs["value"] = value
        gram = ET.Element("gram", attrs)
        gram.text = text
        return self._return_with_optional_comma(gram, has_comma)

    def _collect_gram_items(self, obj, out: list[ET.Element]) -> None:
        if obj is None:
            return
        if isinstance(obj, ET.Element) and obj.tag in {"gram", "pc", "note", "lbl"}:
            out.append(obj)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._collect_gram_items(item, out)

    def _make_comment(self, text: str) -> ET.Element:
        return ET.Comment(text)

    def _make_attestation_bibl(self, source_label: str) -> ET.Element:
        """Build a simple attestation bibl for source labels found in quote position."""
        label = (source_label or "").strip().rstrip(".,;:")
        bibl = ET.Element("bibl", {"type": "attestation", "source": f"#{label}"})
        title = ET.SubElement(bibl, "title")
        title.text = label
        return bibl

    def _split_final_source_label(self, text: str | None) -> tuple[str, ET.Element | None, bool]:
        """Separate a final source label such as Ct, Gl, Bd, LL, or R from quote text.

        Returns (remaining_quote_text, bibl_or_none, source_was_the_only_content).
        """
        raw = (text or "").strip()
        if not raw:
            return "", None, False

        # Exact source label: Ct, Ct., Gl, etc.
        exact = raw.rstrip(".,;:").strip()
        if exact in self.SOURCE_LABELS:
            return "", self._make_attestation_bibl(exact), True

        pattern = r"^(.*?)(?:[,;:]?\s+|[,;:]?)(Ct|Gl|Bd|LL|R)\.?$"
        m = re.match(pattern, raw)
        if m:
            before = (m.group(1) or "").strip().rstrip(",;:").strip()
            source = m.group(2)
            if before:
                return before, self._make_attestation_bibl(source), False

        return raw, None, False

    def _base_for_tilde_expansion(self) -> str:
        """Return the clean form used when expanding ~ in examples."""
        base = self._source_id or self._lemma_value or self._last_orth_base or ""
        base = base.split(",", 1)[0].strip()
        return self._clean_attr_form(base) or base

    def _expand_tilde_token_in_example(self, token: str) -> tuple[str, str | None]:
        """Return the current lemma form for ~ references inside examples.

        The printed suffix, if any, is preserved outside the <ref> as text.
        The @value should point to the lemma/current-entry form, not to an
        expanded surface form.
        """
        return self._base_for_tilde_expansion(), None

    def _make_example_quote(self, text: str) -> tuple[ET.Element, list[ET.Element]]:
        """Build an example <quote>, encoding ~ as a current-entry form reference.

        Policy:
        - standalone "~ " keeps the following space inside the <ref> text;
        - attached forms such as "~an" keep only "~" inside <ref> and leave
          the suffix as tail text;
        - @value stores the expanded form used for the reference.
        """
        quote = ET.Element("quote")
        comments = []
        text = (text or "").strip()

        # Match ~, optionally followed by an attached suffix, and optionally by
        # spaces. If the suffix is present, the spaces remain outside the ref;
        # if the tilde is standalone, one or more following spaces are preserved
        # in the ref text itself, e.g. <ref ...>~ </ref>wiþ.
        pattern = re.compile(r"~([ęėþāäæÐÆǣēīōöðȳūüa-zA-Z\(\)]*)?(\s*)")
        pos = 0
        last_child = None

        def append_text(segment: str):
            nonlocal last_child
            if not segment:
                return
            if last_child is None and quote.text is None:
                quote.text = segment
            elif last_child is not None:
                last_child.tail = (last_child.tail or "") + segment
            else:
                quote.text = (quote.text or "") + segment

        for match in pattern.finditer(text):
            append_text(text[pos:match.start()])

            suffix = match.group(1) or ""
            following_space = match.group(2) or ""
            printed_for_value = "~" + suffix
            expanded, comment = self._expand_tilde_token_in_example(printed_for_value)

            ref_text = "~" + (following_space if not suffix else "")
            ref = ET.SubElement(quote, "ref", {
                "type": "form",
                "scope": "currentEntry",
                "value": expanded,
            })
            ref.text = ref_text
            last_child = ref

            # Attached suffix is preserved as source text outside the <ref>.
            # Space after an attached form also remains outside the <ref>.
            if suffix or (suffix and following_space):
                append_text(suffix + following_space)

            if comment:
                comments.append(self._make_comment(comment))

            pos = match.end()

        append_text(text[pos:])
        return quote, comments

    def _append_nested_variants(self, lemma_form: ET.Element, children) -> None:
        """Append punctuation + nested variant forms inside <form type="lemma">.

        Variant forms are expanded here, not in variant_form(), because
        variant_form() is transformed before lemma_form() has recorded the
        lemma base and segmentation.
        """
        for child in self._flat(children):
            if isinstance(child, dict) and child.get("_variant_raw"):
                punct = child.get("punct")
                if punct:
                    lemma_form.append(self._pc(punct))
                lemma_form.append(self._build_variant_form(child["_variant_raw"]))

    def _base_for_variant_expansion(self) -> str:
        base = self._last_orth_base or self._lemma_value or self._source_id or ""
        return base.split(",", 1)[0].strip()

    def _variant_relation(self, lemma_segment: str, variant_segment: str) -> bool:
        """Return True when two spelling segments are licensed by Sweet's variant table."""
        left = (lemma_segment or "").lower()
        right = (variant_segment or "").lower()
        if not left or not right:
            return False
        if left == right:
            return True
        if right in self.SWEET_VARIANT_TABLE.get(left, []):
            return True
        if left in self.SWEET_VARIANT_TABLE.get(right, []):
            return True
        return False

    def _one_table_substitution_matches(self, source: str, target: str) -> bool:
        """Check whether target can be source with one table-backed segment replacement.

        This deliberately tries several possible prefix/suffix alignments. A
        greedy suffix match would misread ca -> cea by preserving the final a,
        while the intended replacement is a -> ea after the shared c.
        """
        source = source or ""
        target = target or ""
        if source == target:
            return True

        max_prefix = min(len(source), len(target))
        for prefix_len in range(max_prefix + 1):
            if source[:prefix_len] != target[:prefix_len]:
                break

            max_suffix = min(len(source) - prefix_len, len(target) - prefix_len)
            for suffix_len in range(max_suffix + 1):
                if suffix_len and source[-suffix_len:] != target[-suffix_len:]:
                    continue

                source_end = len(source) - suffix_len if suffix_len else len(source)
                target_end = len(target) - suffix_len if suffix_len else len(target)
                source_mid = source[prefix_len:source_end]
                target_mid = target[prefix_len:target_end]

                if self._variant_relation(source_mid, target_mid):
                    return True

        return False

    def _expand_by_direct_substitution(self, base: str, variant_segment: str) -> tuple[str | None, str | None]:
        """Replace one segment in base with variant_segment if Sweet's table licenses it.

        Returns (expanded_form, comment). If more than one table-backed
        replacement position is possible, the earliest/best match is used and
        a comment is returned so the output remains inspectable.
        """
        base = base or ""
        variant_segment = variant_segment or ""
        if not base or not variant_segment:
            return None, None

        candidates = []
        for start in range(len(base)):
            for end in range(start + 1, len(base) + 1):
                lemma_segment = base[start:end]
                if self._variant_relation(lemma_segment, variant_segment):
                    candidates.append((start, -(end - start), end, lemma_segment))

        if not candidates:
            return None, None

        # First position wins; if the same position has several possible source
        # lengths, prefer the longer source segment.
        start, neg_length, end, _lemma_segment = sorted(candidates, key=lambda x: (x[0], x[1]))[0]
        expanded = base[:start] + variant_segment + base[end:]

        comment = None
        if len({(c[0], c[2]) for c in candidates}) > 1:
            comment = "variant expansion has more than one possible replacement position; first match used"

        return expanded, comment

    def _expand_trailing_hyphen_variant(self, core: str, base: str) -> tuple[str | None, str]:
        """Expand a printed prefix variant such as ge- or cea-."""
        split = self._lemma_split.get("hyphen")
        if split:
            return core + split.get("after", ""), "certain"

        # If the unhyphenated lemma can be transformed at the beginning, use that.
        for length in range(1, min(len(base), len(core) + 2) + 1):
            source_prefix = base[:length]
            if self._one_table_substitution_matches(source_prefix, core):
                return core + base[length:], "inferred"

        # Fallback: the hyphen says the printed material is prefixed to the lemma.
        return core + base, "certain"

    def _expand_leading_hyphen_variant(self, core: str, base: str) -> tuple[str | None, str]:
        """Expand a printed suffix variant such as -ærn."""
        split = self._lemma_split.get("hyphen")
        if split:
            return split.get("before", "") + core, "certain"

        # If the unhyphenated lemma can be transformed at the end, use that.
        for length in range(1, min(len(base), len(core) + 2) + 1):
            source_suffix = base[len(base) - length:]
            if self._one_table_substitution_matches(source_suffix, core):
                return base[:len(base) - length] + core, "inferred"

        # Fallback: the hyphen says the printed material is suffixed to the lemma.
        return base + core, "certain"

    def _is_full_alternative_variant(self, variant_text: str, base: str) -> bool:
        """Heuristic for deciding when an unhyphenated variant is a full alternative.

        This is used only after hyphenated prefix/suffix cases have already
        been handled. Short lemmas need stricter treatment, because a very
        short variant such as ea after carl is probably a replacement segment,
        not a full form. Longer variants that are close in length to the lemma,
        or longer than three letters, are treated as full alternatives.
        """
        if not variant_text or not base:
            return False

        base_len = len(base)
        variant_len = len(variant_text)

        if base_len <= 4:
            min_len = max(1, base_len - 1)
            return variant_len <= 4 and variant_len >= min_len

        if variant_len >= base_len - 2:
            return True

        if variant_len <= 3:
            return False

        return True

    def _make_full_variant_orth(self, text: str) -> ET.Element:
        orth = ET.Element("orth")
        if "-" in text and not text.startswith("-") and not text.endswith("-"):
            split_at = text.index("-")
            ET.SubElement(orth, "seg").text = text[:split_at]
            ET.SubElement(orth, "seg").text = text[split_at:]
        else:
            orth.text = text
        return orth

    def _make_part_variant_form(self, visible: str, expand: str | None, comment: str | None = None) -> ET.Element:
        form = ET.Element("form", {"type": "variant"})
        attrs = {"extent": "part"}
        if expand:
            attrs["expand"] = self._clean_attr_form(expand) or expand
        orth = ET.SubElement(form, "orth", attrs)
        ET.SubElement(orth, "seg").text = visible
        if comment:
            form.append(self._make_comment(comment))
        return form

    def _build_variant_form(self, visible: str) -> ET.Element:
        """Build the nested variant form after lemma tracking is available."""
        base = self._base_for_variant_expansion()

        # Tilde variants are partial by definition; source_id is used as the
        # available expansion when present.
        if visible.startswith("~"):
            expand = self._source_id if self._source_id and visible != "~" else None
            return self._make_part_variant_form(visible, expand)

        # Full variant containing an internal hyphen, e.g. carcern-ern.
        if "-" in visible and not visible.startswith("-") and not visible.endswith("-"):
            variant_form = ET.Element("form", {"type": "variant"})
            variant_form.append(self._make_full_variant_orth(visible))
            return variant_form

        # Prefix variant, e.g. ge- or tuning-.
        if visible.endswith("-"):
            core = visible[:-1]
            expand, method = self._expand_trailing_hyphen_variant(core, base)
            comment = None
            if method == "inferred":
                comment = "variant expansion inferred from Sweet spelling table; check manually"
            return self._make_part_variant_form(visible, expand, comment)

        # Suffix variant, e.g. -ærn.
        if visible.startswith("-"):
            core = visible[1:]
            expand, method = self._expand_leading_hyphen_variant(core, base)
            comment = None
            if method == "inferred":
                comment = "variant expansion inferred from Sweet spelling table; check manually"
            return self._make_part_variant_form(visible, expand, comment)

        # Full alternative according to the current length heuristic.
        if self._is_full_alternative_variant(visible, base):
            variant_form = ET.Element("form", {"type": "variant"})
            variant_form.append(self._make_full_variant_orth(visible))
            return variant_form

        # Substitution segment licensed by Sweet's spelling table.
        expand, subst_comment = self._expand_by_direct_substitution(base, visible)
        comment = subst_comment if expand else "form not expanded due to lack of evidence"
        return self._make_part_variant_form(visible, expand, comment)


    def _runon_seg_parts(self, parts: list[str]) -> list[str]:
        """Group run-on surface pieces into the required <orth> segments."""
        parts = [p for p in parts if p]
        if not parts:
            return []

        # <form>~endlic</form> -> <seg>~endlic</seg>
        if len(parts) == 2 and parts[0] == "~":
            return ["~" + parts[1]]

        # <span class=entryPrefix>ge</span><form>~od</form> -> ge + ~od
        if len(parts) >= 3 and parts[1] == "~":
            return [parts[0], "~" + "".join(parts[2:])]

        # <form>~</form><span class=entryPrefix>ge</span><form>būr</form>
        # Keep the inserted prefix as its own segment.
        if parts[0] == "~" and len(parts) > 2:
            return ["~"] + parts[1:]

        return parts

    def _orth_text_from_lemma_form(self, lemma_form: ET.Element | None) -> str:
        """Read the visible text of the first <orth> in a lemma form."""
        if lemma_form is None:
            return ""
        orth = lemma_form.find("orth")
        if orth is None:
            return ""
        return "".join(orth.itertext()).strip()

    def _set_runon_orth_attrs(self, lemma_form: ET.Element | None, source_id: str) -> None:
        """Mark run-on forms as partial orths expanded to their source_id."""
        if lemma_form is None:
            return
        orth = lemma_form.find("orth")
        if orth is None:
            return
        orth.set("extent", "part")
        orth.set("expand", self._clean_attr_form(source_id) or source_id)

    def _make_main_entry_element(self, source_id: str, lemma_form: ET.Element | None) -> ET.Element:
        entry_el = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{source_id}",
            "type": "mainEntry",
            f"{{{self.XML_NS}}}lang": "ang",
        })
        if lemma_form is not None:
            entry_el.append(lemma_form)
        return entry_el

    def _make_runon_entry_element(self, source_id: str, lemma_form: ET.Element | None) -> ET.Element:
        self._set_runon_orth_attrs(lemma_form, source_id)
        entry_el = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{source_id}",
            "type": "relatedEntry",
            f"{{{self.XML_NS}}}lang": "ang",
        })
        if lemma_form is not None:
            entry_el.append(lemma_form)
        return entry_el

    def _entry_payload(self, children, kind: str) -> dict:
        headword_payload = None
        for child in self._flat(children):
            if isinstance(child, dict) and child.get("_headword"):
                headword_payload = child
                break

        source_id = (headword_payload or {}).get("source_id", "UNKNOWN")
        lemma_form = (headword_payload or {}).get("lemma_form")
        tracking = (headword_payload or {}).get("lemma_tracking") or dict(self._lemma_split)
        orth_text = self._orth_text_from_lemma_form(lemma_form)

        if kind == "runon":
            element = self._make_runon_entry_element(source_id, lemma_form)

            # Entry-level grammatical information in a run-on entry is still
            # produced from preceding_content, but it belongs to the relatedEntry.
            for child in children:
                for el in self._iter_tei_elements(child):
                    if el is lemma_form or el is element:
                        continue
                    if el.tag in {"gramGrp", "form", "usg", "sense", "xr", "etym", "note"}:
                        element.append(el)
                    elif el.tag == "metamark" and (el.text or "").strip() == ".":
                        element.append(el)

        else:
            element = self._make_main_entry_element(source_id, lemma_form)

            homonymic_entries = []
            trailing_metamarks = []

            for child in children:
                for el in self._iter_tei_elements(child):
                    if el is lemma_form or el is element:
                        continue
                    if el.tag == "entry" and el.get("type") == "homonymicEntry":
                        homonymic_entries.append(el)
                        element.append(el)
                    elif el.tag == "metamark" and (el.text or "").strip() == ".":
                        trailing_metamarks.append(el)
                    elif el.tag in {"gramGrp", "form", "usg", "sense", "xr", "etym", "note"}:
                        element.append(el)

            # A final full stop after a sequence of homonyms belongs most
            # naturally to the last homonymic entry. If there are no homonyms,
            # keep it at main-entry level.
            if homonymic_entries:
                for mark in trailing_metamarks:
                    homonymic_entries[-1].append(mark)
            else:
                for mark in trailing_metamarks:
                    element.append(mark)

        payload = {
            "_tei_payload": True,
            "kind": kind,
            "source_id": source_id,
            "element": element,
            "lemma_tracking": tracking,
            "orth_text": orth_text,
            "lemma_value": (headword_payload or {}).get("lemma_value") or tracking.get("value"),
        }
        self._reset_entry_state()
        return payload


    def _make_translation_cit(self, quote_text: str | None, cit_type: str = "translationEquivalent") -> ET.Element | None:
        text, bibl, source_only = self._split_final_source_label(quote_text)

        if source_only and bibl is not None:
            return bibl

        if not text and bibl is None:
            return None

        cit = ET.Element("cit", {"type": cit_type, f"{{{self.XML_NS}}}lang": "en"})
        if text:
            quote = ET.SubElement(cit, "quote")
            quote.text = text
        if bibl is not None:
            cit.append(bibl)
        return cit if list(cit) else None

    def _make_example_cit(self, example_text: str | None, translation_item: ET.Element | None = None) -> ET.Element | None:
        text = (example_text or "").strip()
        if not text:
            return None

        cit = ET.Element("cit", {"type": "example", f"{{{self.XML_NS}}}lang": "ang"})
        quote, comments = self._make_example_quote(text)
        cit.append(quote)

        if translation_item is not None:
            if translation_item.tag == "cit":
                # Encoding policy: a nested English example translation uses type="translation".
                translation_item.set("type", "translation")
                cit.append(translation_item)
            elif translation_item.tag == "bibl":
                # Source-only quote after an example is an attestation, not a translation.
                cit.append(translation_item)

        for comment in comments:
            cit.append(comment)

        return cit

    def _collect_sense_content(self, obj, out: list[ET.Element]) -> None:
        """Collect the TEI elements supported inside a bare sense."""
        if obj is None:
            return
        if isinstance(obj, ET.Element) and obj.tag in {"cit", "metamark", "bibl"}:
            out.append(obj)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._collect_sense_content(item, out)
        elif isinstance(obj, dict) and isinstance(obj.get("element"), ET.Element):
            self._collect_sense_content(obj["element"], out)

    def _renumber_sense_tree(self, sense_el: ET.Element, base_id: str, path: list[int]) -> None:
        """Renumber a sense wrapper and its nested senses under a new base id."""
        sense_el.set(f"{{{self.XML_NS}}}id", f"{self.DICT_PREFIX}.{base_id}." + ".".join(str(i) for i in path))
        child_index = 1
        for child in list(sense_el):
            if isinstance(child, ET.Element) and child.tag == "sense":
                self._renumber_sense_tree(child, base_id, path + [child_index])
                child_index += 1

    """
    TERMINALS
      
    """

    # Most terminals are intentionally left as raw Lark Token objects.
    # Lemma-form reconstruction needs token types such as WORD, HYPHEN, BAR,
    # MID_DOT, COMMA, and TILDE, so those are collected locally inside rules.

    def ROM_NUM(self, tok):
        text = str(tok).strip()
        roman = text.rstrip(".").strip()
        return {
            "_hom_num": True,
            "text": text,
            "roman": roman,
            "n": self._roman_to_int(roman),
        }

    def DOT_SEP(self, tok):
        metamark = ET.Element("metamark")
        metamark.text = str(tok)
        return metamark

    def TRANSLATION(self, tok):
        return {"_translation_text": str(tok).strip()}

    def EXAMPLE(self, tok):
        return {"_example_text": str(tok).strip()}

    def LBL(self, tok):
        return self._make_plain_lbl(str(tok).strip())

    def GEN(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        letters = [ch for ch in display if ch in "mnf"]
        value_map = {"m": "masculine", "n": "neuter", "f": "feminine"}
        values = ", ".join(value_map[ch] for ch in letters) if letters else ""
        gram = ET.Element("gram", {"type": "gen", "value": values})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def NODOTGEN(self, tok):
        display = str(tok).strip().strip("()")
        letters = [ch for ch in display if ch in "mnf"]
        value_map = {"m": "masculine", "n": "neuter", "f": "feminine"}
        values = ", ".join(value_map[ch] for ch in letters) if letters else ""
        gram = ET.Element("gram", {"type": "gen", "value": values})
        gram.text = display
        return gram

    def POS(self, tok):
        return self._make_pos_gram(str(tok))

    def CASE(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        gram = ET.Element("gram", {"type": "case"})
        value = self._case_value(display)
        if value:
            gram.set("value", value)
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def NUM(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {
            "sg": "singular",
            "s": "singular",
            "sing": "singular",
            "pl": "plural",
            "p": "plural",
            "sbpl": "plural",
        }
        gram = ET.Element("gram", {"type": "number", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def TNS(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {"prt": "past", "pres": "present"}
        gram = ET.Element("gram", {"type": "tense", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def PERS(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".")
        value_map = {"1": "first", "2": "second", "3": "third"}
        gram = ET.Element("gram", {"type": "person", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def MOOD(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {
            "interr": "interrogative",
            "ind": "indicative",
            "imperat": "imperative",
            "subj": "subjunctive",
        }
        gram = ET.Element("gram", {"type": "mood", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def DGR(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {"comp": "comparative", "sup": "superlative", "superl": "superlative"}
        gram = ET.Element("gram", {"type": "degree", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def DECL(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {"wk": "weak", "strong": "strong", "indecl": "indeclinable"}
        gram = ET.Element("gram", {"type": "inflectionType", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def VALEN(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = re.sub(r"\s+", " ", display.rstrip(".").lower())
        value_map = {
            "tr": "transitive",
            "intr": "intransitive",
            "rfl": "reflexive",
            "refl": "reflexive",
            "impers": "impersonal",
            "pers": "personal",
            "pers. and impers": "personal and impersonal",
            "tr. intr": "transitive and intransitive",
        }
        gram = ET.Element("gram", {"type": "valency", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def PTC(self, tok):
        text, has_comma = self._with_trailing_comma(str(tok))
        display = text.strip().strip("()")
        key = display.rstrip(".").lower()
        value_map = {"ptc": "participle", "pp": "past participle"}
        gram = ET.Element("gram", {"type": "verbForm", "value": value_map.get(key, key)})
        gram.text = display
        return self._return_with_optional_comma(gram, has_comma)

    def VERB_INFL_TYPE(self, tok):
        raw = str(tok).strip()
        grp = ET.Element("gramGrp")
        ET.SubElement(grp, "gram", {"type": "pos", "value": "strong verb"})

        parts = re.split(r"(,)", raw)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part == ",":
                grp.append(self._pc(","))
            else:
                gram = ET.SubElement(grp, "gram", {"type": "inflectionType"})
                gram.text = part

        return grp

    """
    RULES
      
    """


    def quote(self, children):
        """Minimal translation quote collector."""
        parts = []
        for child in self._flat(children):
            if isinstance(child, dict) and child.get("_translation_text"):
                parts.append(child["_translation_text"])
        return " ".join(parts).strip() if parts else None

    def cit(self, children):
        """Build a translationEquivalent cit from the quote rule."""
        text_parts = []
        for child in self._flat(children):
            if isinstance(child, str) and child.strip():
                text_parts.append(child.strip())
        return self._make_translation_cit(" ".join(text_parts))

    def cit_trnsl(self, children):
        """Translation attached to an example."""
        text_parts = []
        for child in self._flat(children):
            if isinstance(child, str) and child.strip():
                text_parts.append(child.strip())
            elif isinstance(child, ET.Element) and child.tag in {"cit", "bibl"}:
                return child
        return self._make_translation_cit(" ".join(text_parts), cit_type="translation")

    def quote_exmpl(self, children):
        """Build an example cit, with optional nested translation."""
        example_text = None
        translation_cit = None
        for child in self._flat(children):
            if isinstance(child, dict) and child.get("_example_text"):
                example_text = child["_example_text"]
            elif isinstance(child, ET.Element) and child.tag in {"cit", "bibl"}:
                translation_cit = child
        return self._make_example_cit(example_text, translation_cit)

    def cit_exmpl(self, children):
        for child in self._flat(children):
            if isinstance(child, ET.Element) and child.tag == "cit":
                return child
        return None

    def semicolsep(self, children):
        mark = ET.Element("metamark", {"function": "senseSeparator"})
        mark.text = ";"
        return mark

    def sense(self, children):
        """Build a bare inner sense from citations/examples only."""
        sense_el = ET.Element("sense")
        collected = []
        for child in children:
            self._collect_sense_content(child, collected)
        for el in collected:
            if el.tag != "metamark":
                sense_el.append(el)
        return sense_el if list(sense_el) else None

    def sense_section(self, children):
        """Build one top-level sense section and its inner senses."""
        self._sense_section_counter += 1
        section_no = self._sense_section_counter
        base_id = self._source_id or self._lemma_value or "UNKNOWN"

        wrapper = ET.Element("sense", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base_id}.{section_no}"
        })

        current_items = []
        inner_no = 1

        def flush_current():
            nonlocal inner_no, current_items
            if not current_items:
                return
            inner = ET.Element("sense", {
                f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base_id}.{section_no}.{inner_no}"
            })
            for item in current_items:
                if isinstance(item, ET.Element) and item.tag == "sense":
                    for sub in list(item):
                        inner.append(sub)
                elif isinstance(item, ET.Element) and item.tag in {"cit", "bibl"}:
                    inner.append(item)
            if list(inner):
                wrapper.append(inner)
                inner_no += 1
            current_items = []

        for child in self._flat(children):
            if isinstance(child, ET.Element) and child.tag == "metamark" and (child.text or "") == ";":
                flush_current()
                wrapper.append(child)
            elif isinstance(child, ET.Element) and child.tag in {"sense", "cit", "bibl"}:
                current_items.append(child)

        flush_current()
        return wrapper if list(wrapper) else None

    def sense_sections(self, children):
        """Return sense sections, preserving | / || as sense-separator metamarks."""
        out = []
        for child in self._flat(children):
            if isinstance(child, Token) and child.type == "BAR":
                mark = ET.Element("metamark", {"function": "senseSeparator"})
                mark.text = str(child)
                out.append(mark)
            elif isinstance(child, ET.Element) and child.tag in {"sense", "metamark"}:
                out.append(child)
        return out if out else None

    def variant_form(self, children):
        """Return the raw variant surface and its introducing punctuation.

        Expansion is done later in lemma_form(), after the lemma base and
        segmentation have been recorded.
        """
        items = self._token_items(children)
        if not items:
            return None

        leading_punct = None
        surface_items = []
        for item in items:
            if item.type in {"COMMA", "SEMICOL_SEP"} and leading_punct is None:
                leading_punct = self._tok_text(item)
            elif item.type in {"WORD", "HYPHEN", "TILDE"}:
                surface_items.append(item)

        visible = self._join_token_texts(surface_items)
        if not visible:
            return None

        return {"_variant_raw": visible, "punct": leading_punct}

    def usage(self, children):
        return None

    def qm(self, children):
        return None

    def lbl(self, children):
        out = []
        for child in children:
            self._collect_gram_items(child, out)
        return out if out else None

    def gram(self, children):
        out = []
        for child in children:
            self._collect_gram_items(child, out)
        return out if out else None

    def gramgrp(self, children):
        items = []
        for child in children:
            self._collect_gram_items(child, items)

        if not items:
            return None

        has_gen = any(el.tag == "gram" and el.get("type") == "gen" for el in items)
        has_pos = any(el.tag == "gram" and el.get("type") == "pos" for el in items)

        if has_gen and not has_pos:
            pos = ET.Element("gram", {"type": "pos", "value": "noun"})
            insert_at = 0
            while insert_at < len(items) and items[insert_at].tag == "pc" and (items[insert_at].text or "") == "(":
                insert_at += 1
            items.insert(insert_at, pos)

        grp = ET.Element("gramGrp")
        for item in items:
            grp.append(item)
        return grp

    def infl_form(self, children):
        # Inflected-form grammar is not entry-level grammar.
        # It will be handled when form type="inflected" is implemented.
        return None

    def xr_gramgrp(self, children):
        # Cross-reference grammar belongs inside the xr structure, not directly
        # at entry level, so it is excluded from entry-level grammatical output.
        return None

    def xr_gram(self, children):
        return None

    def sense_gramgrp(self, children):
        # Sense-level grammar will be handled with sense transformation.
        return None

    def sense_gram(self, children):
        return None

    def lemma_form(self, children):
        items = self._token_items(children)
        words = [self._tok_text(item) for item in items if item.type == "WORD"]
        has_comma = any(item.type == "COMMA" for item in items)
        has_other_punctuation = any(
            item.type in {"HYPHEN", "BAR", "MID_DOT", "TILDE"}
            for item in items
        )

        if not words:
            return None

        # <span class=entryPrefix>ge</span><form>tot</form>
        if len(words) == 2 and not has_comma and not has_other_punctuation:
            value = "".join(words)
            orth = self._orth_from_prefix_parts([words[0], words[1]])
            self._record_lemma_tracking(value=value, orth_text=value)
            lemma_form = self._make_lemma_form(orth)
            self._append_nested_variants(lemma_form, children)
            return {
                "_lemma_form": lemma_form,
                "_lemma_value": value,
                "_lemma_tracking": dict(self._lemma_split),
            }

        # <form>ofersceadian</form>,<form>ofersceadwian</form>(<form>ofer·scead(w)ian</form>)
        if has_comma and len(words) >= 3:
            comma_index = next((i for i, item in enumerate(items) if item.type == "COMMA"), None)
            if comma_index is not None:
                second_word_index = next(
                    (i for i in range(comma_index + 1, len(items)) if items[i].type == "WORD"),
                    None,
                )
                if second_word_index is not None and second_word_index + 1 < len(items):
                    value = f"{words[0]}, {self._tok_text(items[second_word_index])}"
                    display = self._join_token_texts(items[second_word_index + 1:])
                    orth = self._orth_with_text_or_hyphen_segs(display, value=value)
                    self._record_lemma_tracking(value=value, orth_text=display)
                    lemma_form = self._make_lemma_form(orth)
                    self._append_nested_variants(lemma_form, children)
                    return {
                        "_lemma_form": lemma_form,
                        "_lemma_value": value,
                        "_lemma_tracking": dict(self._lemma_split),
                    }

        # <form>Cantware</form>(<form>Cant-war|e</form>)
        if len(words) >= 2:
            first_word_index = next(i for i, item in enumerate(items) if item.type == "WORD")
            display = self._join_token_texts(items[first_word_index + 1:])
            if display:
                orth = self._orth_with_text_or_hyphen_segs(display, value=words[0])
                self._record_lemma_tracking(value=words[0], orth_text=display)
                lemma_form = self._make_lemma_form(orth)
                self._append_nested_variants(lemma_form, children)
                return {
                    "_lemma_form": lemma_form,
                    "_lemma_value": words[0],
                    "_lemma_tracking": dict(self._lemma_split),
                }

        # Simple lemma: <form>candel</form>
        orth = ET.Element("orth")
        orth.text = words[0]
        self._record_lemma_tracking(value=words[0], orth_text=words[0])
        lemma_form = self._make_lemma_form(orth)
        self._append_nested_variants(lemma_form, children)
        return {
            "_lemma_form": lemma_form,
            "_lemma_value": words[0],
            "_lemma_tracking": dict(self._lemma_split),
        }

    def runon_lemma_form(self, children):
        items = self._token_items(children)
        parts = [self._tok_text(item) for item in items if item.type in {"TILDE", "WORD"}]
        if not parts:
            return None

        # Visible run-on lemma stays as printed: ~endlic, ~ + ge + būr, or ge + ~od.
        value = "".join(part for part in parts if part != "~")
        orth_text = "".join(parts)
        orth = self._orth_from_prefix_parts(self._runon_seg_parts(parts))
        self._record_lemma_tracking(value=value, orth_text=orth_text)
        lemma_form = self._make_lemma_form(orth)
        self._append_nested_variants(lemma_form, children)
        return {
            "_lemma_form": lemma_form,
            "_lemma_value": value,
            "_lemma_tracking": dict(self._lemma_split),
        }

    def var_plus_gen_sequence(self, children):
        items = self._token_items(children)
        first_word = next((self._tok_text(item) for item in items if item.type == "WORD"), None)
        if not first_word:
            return None
        orth = ET.Element("orth")
        orth.text = first_word
        self._record_lemma_tracking(value=first_word, orth_text=first_word)
        return {
            "_lemma_form": self._make_lemma_form(orth),
            "_lemma_value": first_word,
            "_lemma_tracking": dict(self._lemma_split),
        }

    def runon_var_plus_gen_sequence(self, children):
        items = self._token_items(children)
        parts = []
        for item in items:
            if item.type in {"TILDE", "WORD"}:
                parts.append(self._tok_text(item))
            if len([p for p in parts if p != "~"]) >= 1:
                # Use the first run-on form as the lemma source for this transformation stage.
                break
        if not parts:
            return None

        value = "".join(part for part in parts if part != "~")
        orth_text = "".join(parts)
        orth = self._orth_from_prefix_parts(self._runon_seg_parts(parts))
        self._record_lemma_tracking(value=value, orth_text=orth_text)
        lemma_form = self._make_lemma_form(orth)
        self._append_nested_variants(lemma_form, children)
        return {
            "_lemma_form": lemma_form,
            "_lemma_value": value,
            "_lemma_tracking": dict(self._lemma_split),
        }

    def headword(self, children):
        source_id = None
        lemma_payload = None

        for child in self._flat(children):
            if source_id is None and isinstance(child, Token) and child.type == "WORD":
                source_id = self._clean_source_id(child)
            elif isinstance(child, dict) and child.get("_lemma_form") is not None:
                lemma_payload = child

        self._source_id = source_id or "UNKNOWN"
        return {
            "_headword": True,
            "source_id": self._source_id,
            "lemma_form": lemma_payload.get("_lemma_form") if lemma_payload else None,
            "lemma_value": lemma_payload.get("_lemma_value") if lemma_payload else None,
            "lemma_tracking": lemma_payload.get("_lemma_tracking") if lemma_payload else dict(self._lemma_split),
        }

    def runon_headword(self, children):
        return self.headword(children)

    def hom_entry(self, children):
        """Build a homonymicEntry shell from ROM_NUM.

        Contents are collected generically so transformed grammatical and sense
        elements are placed inside the correct homonymic entry rather than at
        the main-entry level.
        """
        hom_info = None
        for child in self._flat(children):
            if isinstance(child, dict) and child.get("_hom_num"):
                hom_info = child
                break

        if hom_info is None:
            return None

        base_id = self._source_id or self._lemma_value or "UNKNOWN"
        n = hom_info.get("n") or 1
        roman = hom_info.get("roman") or str(n)
        text = hom_info.get("text") or f"{roman}."

        hom = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base_id}_{n}",
            "type": "homonymicEntry",
            f"{{{self.XML_NS}}}lang": "ang",
            "n": roman,
        })
        ET.SubElement(hom, "lbl", {"type": "homNum"}).text = text

        # Collect transformed TEI children in source order. Skip the homonym number
        # payload itself and avoid nesting another homonym entry here.
        for child in children:
            if isinstance(child, dict) and child.get("_hom_num"):
                continue
            for el in self._iter_tei_elements(child):
                if el.tag == "entry" and el.get("type") == "homonymicEntry":
                    continue
                hom.append(el)

        # Senses inside homonymic entries are numbered under SWT.lemma_N.
        hom_base = f"{base_id}_{n}"
        sense_index = 1
        for el in list(hom):
            if isinstance(el, ET.Element) and el.tag == "sense":
                self._renumber_sense_tree(el, hom_base, [sense_index])
                sense_index += 1

        return {"_hom_entry": True, "element": hom}

    def entry(self, children):
        return self._entry_payload(children, kind="main")

    def runon_entry(self, children):
        return self._entry_payload(children, kind="runon")

    def start(self, children):
        for child in children:
            if isinstance(child, dict) and child.get("_tei_payload"):
                return child
        return {"_tei_payload": True, "kind": "unknown", "source_id": "UNKNOWN", "element": ET.Element("entry")}

class DictionaryParser:
    """Batch parser for Sweet dictionary entries."""

    def __init__(self, grammar: str = GRAMMAR):
        try:
            self.parser = Lark(grammar, parser="earley", debug=False)
            self.transformer = SweetTEITransformer()
            print("Parser initialized successfully!")
        except Exception as exc:
            print(f"Error initializing parser: {exc}")
            self.parser = None
            self.transformer = None

    @staticmethod
    def _safe_comment_text(text: str) -> str:
        """Make arbitrary entry text safe for XML comments."""
        return (text or "").replace("--", "—")

    @staticmethod
    def _strip_ws(elem: ET.Element) -> None:
        """Remove indentation-only text/tails before inserting an entry into the TEI body."""
        if elem.text is not None and elem.text.strip() == "":
            elem.text = None
        for child in list(elem):
            DictionaryParser._strip_ws(child)
            if child.tail is not None and child.tail.strip() == "":
                child.tail = None

    def parse_text(self, text: str) -> dict:
        """Parse one dictionary entry and return the parse tree or an error."""
        if self.parser is None:
            return {"success": False, "error": "Parser not initialized"}

        cleaned_text = normalize_entry_text(text)
        try:
            parse_tree = self.parser.parse(cleaned_text)
            transformed_result = self.transformer.transform(parse_tree) if self.transformer else None
            return {
                "success": True,
                "parse_tree": parse_tree,
                "transformed": transformed_result,
                "cleaned_text": cleaned_text,
            }
        except ParseError as exc:
            return {"success": False, "error": f"Parse error: {exc}", "cleaned_text": cleaned_text}
        except Exception as exc:
            return {"success": False, "error": f"Unexpected error: {exc}", "cleaned_text": cleaned_text}

    def get_parse_tree_only(self, text: str) -> str:
        """Return only the formatted parse tree for one entry, useful for debugging."""
        result = self.parse_text(text)
        if not result.get("success"):
            return result.get("error", "Unknown parse error")
        return format_tree_simple(result["parse_tree"])


    @staticmethod
    def _normalize_for_runon_match(text: str | None) -> str:
        """Normalize entry ids/lemma segments for run-on-parent matching."""
        text = (text or "").strip()
        text = text.replace("-", "").replace("·", "").replace("|", "")
        text = text.replace("~", "")
        return text.lower()

    def _main_parent_candidates(self, payload: dict) -> list[str]:
        """Return possible bases that a following run-on source_id may start with."""
        candidates = []

        def add(value):
            norm = self._normalize_for_runon_match(value)
            if norm and norm not in candidates:
                candidates.append(norm)
                if norm.endswith("e") and len(norm) > 1:
                    clipped = norm[:-1]
                    if clipped and clipped not in candidates:
                        candidates.append(clipped)

        add(payload.get("source_id"))
        add(payload.get("lemma_value"))

        tracking = payload.get("lemma_tracking") or {}
        add(tracking.get("value"))
        add(tracking.get("text"))

        for split_name in ("bar", "hyphen", "middle_dot"):
            split = tracking.get(split_name)
            if isinstance(split, dict):
                add(split.get("before"))

        # Prefer longer, more specific candidates first.
        return sorted(candidates, key=len, reverse=True)

    def _find_parent_for_runon(self, runon_payload: dict, open_main_payloads: list[dict]) -> dict | None:
        """Find the best previous main entry for a run-on entry."""
        runon_id = self._normalize_for_runon_match(runon_payload.get("source_id"))
        if not runon_id:
            return None

        best = None
        best_score = -1

        # Search all previous main entries, but prefer the most specific/latest match.
        for index, main_payload in enumerate(open_main_payloads):
            candidates = self._main_parent_candidates(main_payload)
            for cand in candidates:
                if not cand:
                    continue

                score = -1
                if runon_id.startswith(cand):
                    score = len(cand) * 10 + index
                elif runon_id.startswith("ge" + cand):
                    score = len(cand) * 10 + index - 1

                if score > best_score:
                    best_score = score
                    best = main_payload

        return best

    def _append_transformed_payloads_to_body(self, body: ET.Element, successful_results: list[dict]) -> None:
        """
        Append transformed entries to <body>, nesting run-on entries into the
        best matching previous main entry. Orphan run-ons are grouped under a
        placeholder main entry with an explanatory XML comment.
        """
        main_payloads = []
        current_orphan_placeholder = None

        for result_data in successful_results:
            payload = result_data.get("transformed_result") or {}
            if not isinstance(payload, dict) or not payload.get("_tei_payload"):
                continue

            kind = payload.get("kind")
            element = payload.get("element")
            if element is None:
                continue

            if kind == "main":
                entry_comment = (
                    f"\nENTRY #{result_data['entry_number']}\n"
                    f"Entry text: {self._safe_comment_text(result_data['original_text'])}\n"
                    f"Cleaned text: {self._safe_comment_text(plain_entry_text(result_data['cleaned_text']))}"
                )
                body.append(ET.Comment(entry_comment))
                self._strip_ws(element)
                body.append(element)
                payload["element"] = element
                main_payloads.append(payload)
                current_orphan_placeholder = None
                continue

            if kind == "runon":
                runon_comment = ET.Comment(
                    f"\nENTRY #{result_data['entry_number']}\n"
                    f"Entry text: {self._safe_comment_text(result_data['original_text'])}\n"
                    f"Cleaned text: {self._safe_comment_text(plain_entry_text(result_data['cleaned_text']))}"
                )
                parent_payload = self._find_parent_for_runon(payload, main_payloads)

                if parent_payload is None:
                    if current_orphan_placeholder is None:
                        body.append(ET.Comment(
                            " PLACEHOLDER mainEntry: one or more run-on entries were parsed, "
                            "but no preceding parsed main entry could be matched. "
                        ))
                        placeholder = ET.Element("entry", {
                            "type": "mainEntry",
                            f"{{{SweetTEITransformer.XML_NS}}}lang": "ang",
                        })
                        note = ET.SubElement(placeholder, "note", {"type": "placeholder"})
                        note.text = "Automatically created placeholder for orphan run-on entries."
                        body.append(placeholder)
                        current_orphan_placeholder = {"element": placeholder}

                    self._strip_ws(element)
                    current_orphan_placeholder["element"].append(runon_comment)
                    current_orphan_placeholder["element"].append(element)
                    continue

                self._strip_ws(element)
                parent_payload["element"].append(runon_comment)
                parent_payload["element"].append(element)
                current_orphan_placeholder = None
    def parse_dictionary_file(self, filename: str) -> dict:
        """Parse entries from a file and write parse-tree and failed-entry reports."""
        path = Path(filename)
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"error": f"File not found: {filename}"}
        except Exception as exc:
            return {"error": f"Error reading file: {exc}"}

        entries = extract_entries_from_content(content)
        total_entries = len(entries)
        successful_results = []
        failed_entries = []

        # Write transformed XML and diagnostics to the repository data folders.
        # This assumes that the parser is stored in src/.
        repo_root = Path(__file__).resolve().parent.parent
        output_dir = repo_root / "data" / "output"
        diagnostics_dir = repo_root / "data" / "diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

        base_name = path.stem
        parse_trees_file = diagnostics_dir / f"{base_name}_parse_trees.txt"
        transformed_file = output_dir / f"{base_name}_transformed.xml"
        failed_file = diagnostics_dir / f"{base_name}_failed.txt"

        print(f"Processing {total_entries} entries...")
        print("Output files will be:")
        print(f"  - Parse trees: {parse_trees_file}")
        print(f"  - Transformed results: {transformed_file}")
        print(f"  - Failed entries: {failed_file}")

        for index, entry in enumerate(entries, start=1):
            if (index - 1) % 100 == 0:
                print(f"Processed {index - 1}/{total_entries} entries")

            result = self.parse_text(entry)
            if result.get("success"):
                successful_results.append({
                    "entry_number": index,
                    "original_text": entry,
                    "cleaned_text": result.get("cleaned_text", ""),
                    "parse_tree": result["parse_tree"],
                    "transformed_result": result.get("transformed"),
                })
            else:
                failed_entries.append({
                    "entry_number": index,
                    "entry_text": entry,
                    "cleaned_text": result.get("cleaned_text", ""),
                    "error": result.get("error", "Unknown parse error"),
                })

        successful_parses = len(successful_results)
        success_rate = (successful_parses / total_entries * 100) if total_entries else 0.0
        failure_rate = 100.0 - success_rate if total_entries else 0.0

        with open(parse_trees_file, "w", encoding="utf-8") as trees_f:
            trees_f.write("PARSE TREES FOR SUCCESSFULLY PARSED ENTRIES\n")
            trees_f.write("=" * 50 + "\n")
            trees_f.write(f"Total entries processed: {total_entries}\n")
            trees_f.write(f"Successfully parsed: {successful_parses}\n")
            trees_f.write(f"Success rate: {success_rate:.2f}%\n")
            trees_f.write("=" * 50 + "\n\n")

            for result_data in successful_results:
                trees_f.write(f"ENTRY #{result_data['entry_number']}\n")
                trees_f.write("-" * 20 + "\n")
                trees_f.write(f"Entry text: {result_data['original_text']}\n")
                trees_f.write(f"Cleaned text: {plain_entry_text(result_data['cleaned_text'])}\n\n")
                trees_f.write("Parse tree:\n")
                trees_f.write(format_tree_simple(result_data["parse_tree"]))
                trees_f.write("\n\n" + "=" * 50 + "\n\n")

        # --- Write transformed results file in the same TEI-wrapper style as CAS ---
        NS = "http://www.tei-c.org/ns/1.0"
        ET.register_namespace("", NS)

        tei = ET.Element(f"{{{NS}}}TEI", {"type": "lex-0"})
        tei_header = ET.SubElement(tei, f"{{{NS}}}teiHeader")
        file_desc = ET.SubElement(tei_header, f"{{{NS}}}fileDesc")
        title_stmt = ET.SubElement(file_desc, f"{{{NS}}}titleStmt")
        ET.SubElement(title_stmt, f"{{{NS}}}title")
        publication_stmt = ET.SubElement(file_desc, f"{{{NS}}}publicationStmt")
        ET.SubElement(publication_stmt, f"{{{NS}}}publisher")
        availability = ET.SubElement(publication_stmt, f"{{{NS}}}availability")
        ET.SubElement(availability, f"{{{NS}}}licence")

        profile_desc = ET.SubElement(tei_header, f"{{{NS}}}profileDesc")
        lang_usage = ET.SubElement(profile_desc, f"{{{NS}}}langUsage")
        ET.SubElement(lang_usage, f"{{{NS}}}language", {
            "role": "sourceLanguage",
            "ident": "ang",
        })

        text_el = ET.SubElement(tei, f"{{{NS}}}text")
        body = ET.SubElement(text_el, f"{{{NS}}}body")

        stats_banner = (
            "TRANSFORMED RESULTS FOR SUCCESSFULLY PARSED ENTRIES\n"
            + "=" * 50 + "\n"
            + f"Total entries processed: {total_entries}\n"
            + f"Successfully parsed: {successful_parses}\n"
            + f"Success rate: {success_rate:.2f}%\n"
            + "=" * 50
        )
        body.append(ET.Comment(stats_banner))

        self._append_transformed_payloads_to_body(body, successful_results)

        ET.indent(tei, space="  ")
        final_xml = ET.tostring(tei, encoding="utf-8", xml_declaration=True).decode("utf-8")

        pi_block = (
            '<?xml-model href="https://lex-0.org/schema/lex-0.rng"\n'
            '  type="application/xml"\n'
            '  schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        )

        with open(transformed_file, "w", encoding="utf-8") as trans_f:
            decl, rest = final_xml.split("\n", 1)
            trans_f.write(decl + "\n" + pi_block + rest)

        with open(failed_file, "w", encoding="utf-8") as failed_f:
            failed_f.write("FAILED ENTRIES WITH ERROR MESSAGES\n")
            failed_f.write("=" * 50 + "\n")
            failed_f.write(f"Total entries processed: {total_entries}\n")
            failed_f.write(f"Failed to parse: {len(failed_entries)}\n")
            failed_f.write(f"Failure rate: {failure_rate:.2f}%\n")
            failed_f.write("=" * 50 + "\n\n")

            for failed_entry in failed_entries:
                failed_f.write(f"ENTRY #{failed_entry['entry_number']}\n")
                failed_f.write("-" * 20 + "\n")
                failed_f.write(f"Original text: {failed_entry['entry_text']}\n")
                failed_f.write(f"Cleaned text: {plain_entry_text(failed_entry['cleaned_text'])}\n\n")
                error_lines = failed_entry["error"].split("\n")
                if len(error_lines) > 50:
                    error_text = "\n".join(error_lines[:50]) + "\n... (error message truncated - showing first 50 lines)"
                else:
                    error_text = failed_entry["error"]
                failed_f.write(f"Error: {error_text}\n")
                failed_f.write("\n" + "=" * 50 + "\n\n")

        print("\nFiles created successfully!")
        print(f"  - {parse_trees_file}: {successful_parses} parse trees")
        print(f"  - {transformed_file}: {successful_parses} transformed entries")
        print(f"  - {failed_file}: {len(failed_entries)} failed entries")

        return {
            "total_entries": total_entries,
            "successful_parses": successful_parses,
            "failed_parses": len(failed_entries),
            "success_rate_percentage": round(success_rate, 2),
            "output_files": {
                "parse_trees": parse_trees_file,
                "transformed": transformed_file,
                "failed": failed_file,
            },
        }


def main() -> None:
    parser = DictionaryParser()

    if len(sys.argv) <= 1:
        print("To process a dictionary file, run:")
        print("python src/SWT_parser.py data/input/SWT_test_sample.txt")
        return

    filename = sys.argv[1]
    print(f"Processing dictionary file: {filename}")
    results = parser.parse_dictionary_file(filename)

    if "error" in results:
        print(f"Error: {results['error']}")
        return

    print("\n" + "=" * 50)
    print("PARSING RESULTS")
    print("=" * 50)
    print(f"Total entries: {results['total_entries']}")
    print(f"Successfully parsed: {results['successful_parses']}")
    print(f"Failed to parse: {results['failed_parses']}")
    print(f"Success rate: {results['success_rate_percentage']}%")

    print("\nOutput files created:")
    for file_type, output_filename in results["output_files"].items():
        print(f"  - {file_type}: {output_filename}")


if __name__ == "__main__":
    main()
