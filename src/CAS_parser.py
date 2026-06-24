"""
Dictionary Entry Parser using Lark
This parser handles dictionary entries with complex grammatical structures one by one, outputs 3 files: entries that failed to parse,
successfully parsed entries (parse trees) and the result of transforming the parse trees into TEI XML. 
"""

from lark import Lark, Transformer, v_args, Tree, Token
from lark.exceptions import ParseError
import sys
import re
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


GRAMMAR = r"""
?start: entry

entry: headword ((preceding_content? main_content) | (etym? (poet_symb | ge_pref)* form* xr_section+)) subsequent_content?

preceding_content: etym? gramgrp? (poet_symb | ge_pref | form )* gramgrp?
main_content: hom_entry+ | sense_section+ | simple_xr
subsequent_content: ((etym | biblref) metamark?)* sb? relatedentry* parenvidexr? editorcomm?

hom_entry: ROM_NUM ( ((preceding_content? (simple_xr | sense_section+))|etym? (poet_symb | ge_pref)* form* xr_section+)|grambiblhom ) subsequent_content?

sb: SUBST (preceding_content? (xr_section+ | sense_section+)) subsequent_content?

relatedentry.4:  ((oneword gramgrp? | collocation| inflect_var (bibl|parenbibl|DOT_SEP)*) parenbibl?  ((poet_symb |  form)* sb | (((poet_symb | form)* xr_section+ | (poet_symb | gramgrp | form)* (simple_xr | sense_section+))) (sb|((etym | biblref) metamark?)*)) | adv_word etym? ) editorcomm?

collocation: COLLOC | DOTSCOLLOC
oneword: ONEWORD 
!adv_word: ", "? "adv. " (" -"? WORD)  (DOT_SEP | sense_section |COMMA? (bibl|parenbibl))*


!headword: ge_pref? WORD VERB_INFL_TYPE? qm? (bibl | parenbibl)? (gramgrp ", ")?

form.4: (inflect_var |( orth_variant)|(inflect_var spell_var) | spell_var | orth_variant  )  (bibl | parenbibl | parenbibl COMMA)? qm? poet_symb?
spell_var: SPELLVAR
!orth_variant: (", "|"-") ge_pref? VARIANT+ spell_var? GEN? COMMA?| LP lbl? ge_pref? VARIANT+ GEN? bibl?  RP
inflect_var.5: LP? COMMA? (lbl? infgramgrp ge_pref? parenbibl? INFVARIANT ((COMMA|SEMICOL_SEP) infgramgrp ge_pref? INFVARIANT)*) RP?

grambiblhom: gramgrp bibl metamark | gramgrp // for cases like "II. adv. Æ."

poet_symb: POET_SYMB
sense_poet_symb: LP POET_SYMB RP | SNS_POET_SYMB
ge_pref: LP? (GE_PREF | GE_OPT) RP?

infgramgrp.12: ((lbl? tense person lbl? person? number lbl? number? lbl? pos?)|(lbl? case gen number)|(lbl? gen case number)|(lbl? case number gen )|(lbl? case gen)|(lbl? case number)|(lbl? tense number?)|(lbl? degree)|(lbl? singlecase))+
gramgrp.10: (lbl? declension tense person number)|(lbl? mood tense number)|(lbl? tense number)+|(lbl? pos tense)+|(lbl? (pos degree)|(degree pos))+|(lbl? nodotgen number)+|(lbl? mood number)+|(lbl? gen)+|(lbl? pos VERB_INFL_TYPE?)+ |(lbl? number)+|(lbl? tense)+|(lbl? person)+|(lbl? mood)+|(lbl? degree)+|caseofsb|(lbl? declension)+|(lbl? valency)+|(lbl? singlecase)+
gen: GEN 
nodotgen: NODOTGEN
pos.3: POS
case: lbl? CASE
singlecase: SINGLECASE
number: NUM
tense: TNS
person: PERS
mood: MOOD
degree: DGR
caseofsb.5: CASE OF POS
declension: DECL
valency.10: VALEN+ parenbibl?
lbl: LBL

simple_xr: usglbl? parenbibl? reflbl (refword | refwords) parenxr? (parenbibl  | biblref | xrsense)? "."?
xr_section.2: ( usglbl? parenbibl?  ((reflbl? gramgrp | reflbl? infgramgrp) OF)  (refword | refwords) parenxr? (parenbibl  | biblref | xrsense)? "."? ) | parenvidexr | equals_variant_xr
reflbl: REFLBL
refword: ge_pref? REFWORD  ("." | homref|gramref| (LP|COMMA) REFWORD )? COMMA? RP?
refwords: ge_pref? REFNUMWORD | PREFSUFXR | ge_pref? REFWORD LBL ge_pref? REFWORD
homref: HOMREF
gramref: GRAMREF
xrsense: cit (metamark | qm | (etym | biblref) metamark?) | oedref
parenvidexr: LP (vide|compare) refword RP
parenxr.6: PARENXR | LP gramgrp OF refword RP
!equals_variant_xr: (REFLBL | "pp., ") ge_pref? VARIANT ((infgramgrp | gramgrp) OF) refword


sense_section: firstsense othersenses*
firstsense: (construction | usage |sense_poet_symb |ge_pref |etym)* ( cit (metamark | qm |inflect_var| (etym | (biblref| biblref bibl|parenvidexr)) metamark?) | oedref)
othersenses: (usage| sense_poet_symb |ge_pref| parenbibl| etym |gramgrp|construction)* (cit (metamark | qm |inflect_var| (etym | biblref) metamark?) | oedref)

cit: parenxr? quote (gramgrp | orth_variant | parenxr)* (qm? bibl | parenbibl)*
quote: (TRANSLATION |usage|gloss|qmsense|construction)+
bibl.10: (poet_symb |ge_pref)* author? (SOURCE | SOURCE SOURCE_NUM | parenbibl)+  etc? sourcevar? msref?
sourcevar: SRCVAR
msref: MSREF
parenbibl: LP ((poet_symb |ge_pref)* author? usglbl? (SOURCE|SOURCE_NUM)+  etc? sourcevar? msref?) DOT_SEP? RP COMMA?
oedref: OEDREF
gloss: GLOSS
qmsense: QMSENSE (SOURCE RP COMMA)?
qm: QM (metamark | COMMA)? | lbl QM
usage.7: (LP ((usglbl gramgrp+)|(usglbl (USG_WORD COMMA?)+ etc?)) RP) | ((usglbl gramgrp+)|(usglbl (USG_WORD COMMA?)+ etc?)) | (LP USGPREP RP COMMA?) 
!construction: LP? valency? usglbl+ (case ("pers."|"thing")?)+ (lbl valency)? (lbl WORD)? RP? COMMA?
usglbl: USGLBL+
author.5: AUTH
etc: /(etc\.|_etc\._);?/


metamark: COLON_SEP | semicolsep | DOT_SEP parenbibl?
semicolsep: SEMICOL_SEP

!etym: "[" ( (vide | compare)? qm? oldengword* (vide | compare)? (oedref |qm | gramgrp)* oldengword* langword* synonym* sqbr_dash_variant* biblref? qm?) "]"
vide: VIDE
compare: COMPARE
langword: LANG (WORD | COMMA WORD)+ SEMICOL_SEP? | LANG SEMICOL_SEP? | lbl LANG
oldengword: ge_pref? WORD ROM_NUM? (bibl|parenbibl)? (COLON_SEP | SEMICOL_SEP)? COMMA?
!biblref: ("(" vide bibl lbl? (oedref|bibl)? ")") | vide bibl
synonym: reflbl SYN qm? parenbibl?
!sqbr_dash_variant: "= " SQBRDASHVAR qm? parenbibl?

editorcomm: EDCOMM

COLON_SEP: /:/
SEMICOL_SEP: /;/
DOT_SEP: /\./
COMMA: /,/
QM: /\?|\(\?\)/
LP:/\(/
RP:/\)/

ROM_NUM: /\s?[IV]{1,4}\./

COLLOC.5: /((?<=(\.\s|\]\s))(?![IV]{1,4}\.)(?!(comp\.\s))(?!(superl\.\s))([+±āæÆǣēīōðȳūüA-Za-z\.]+([+±āæÆǣēīōðȳūüA-Za-z\.\)\()]+)?,\s)?(?!(comp\.\s))(?!(superl\.\s))[+±āæÆǣēīōðȳūüA-Za-z\.]+([+±āæÆǣēīōðȳūüA-Za-z\.\)\()]+)?(?!\spp\.\s)(\s[+±āæÆǣēīōðȳūüa-z\.]+([+±āæÆǣēīōðȳūüa-z\.\)\()]+)?){1,3}(;\s([+±āæÆǣēīōðȳūüa-z\.]+([+±āæÆǣēīōðȳūüa-z\.\)\()]+)?,\s)?(?!(comp\.\s))(?!(superl\.\s))[+±āæÆǣēīōðȳūüa-z\.]+([+±āæÆǣēīōðȳūüa-z\.\)\()]+)?(\s[+±āæÆǣēīōðȳūüa-z\.]+([+±āæÆǣēīōðȳūüa-z\.\)\()]+)?){1,3})*(?!as\ssb\.|[IV]{1,4}\.))|((?<=\.'\s)(?![IV]{1,4}\.|as\ssb\.|[a-z]\.\s[a-z]\.\s)([+±āæÆǣēīōðȳūüa-zA-Z\.]+,\s)?[+±āæÆǣēīōðȳūüa-zA-Z\.]+(\s[+±āæÆǣēīōðȳūüa-zA-Z\.]+){1,2}(?!as\ssb\.|[IV]{1,4}\.))/
DOTSCOLLOC.6: /(([+±āæÆǣēīōðȳūüa-zA-Z\.]+\s)|([+±āæÆǣēīōðȳūüa-zA-Z\]+\([+±āæÆǣēīōðȳūüa-zA-Z\]+\)[+±āæÆǣēīōðȳūüa-zA-Z\.]+\s))?[+±āæÆǣēīōðȳūüa-zA-Z]+\.\.\.[+±āæÆǣēīōðȳūüa-zA-Z]+(?!as\ssb\.|[IV]{1,4}\.)/
ONEWORD: /((?<=(\.\s|\]\s))(?![IV]{1,4}\.|as\ssb\.)[-+±āæÆǣēīōðȳūüa-zA-Z][+±āæÆǣēīōðȳūüa-zA-Z]+)|((?<=\.'\s)(?![IV]{1,4}\.|as\ssb\.)[+±āæÆǣēīōðȳūüa-zA-Z][+±āæÆǣēīōðȳūüa-zA-Z]+)/

WORD: /(?!as\ssb\.|[IV]{1,4}\.)[āäæÐÆǣēīōöðȳūüa-zA-Z\-\*\(\)]+/
USG_WORD: /(?!as\ssb\.|[IV]{1,4}\.)[āäæÐÆǣēīōöðȳūüa-zA-Z\-\*][āäæÐÆǣēīōöðȳūüa-zA-Z\-\*]+/

POET_SYMB: /[†‡],?(?=\s)|[†‡],?(?=([#_]?[ÆA-Z]))/
SNS_POET_SYMB: /[†‡](?=_)|\([†‡]\)/
GE_PREF: /(?!as\ssb\.|[IV]{1,4}\.)\+/
GE_OPT: /(?!as\ssb\.|[IV]{1,4}\.)±/

SUBST.20: /(?<=(\.\s|:\s|;\s))\(?(used\s)?(as\s)?sb\.\)?\s?=?/


VARIANT: /(?<!\.\s)\??(=\s)?(?!(rare))[-*āæǣēīōœ̄ðȳūüA-Za-z]+[)(-āæǣēīōðȳūüa-z]*[-āæǣēīōðȳūüa-z)]+[?,;]?/
INFVARIANT: /(?<=([a-z]\.\s|[a-z],\s|[A-Z]\)\s))(=\s)?(?!(?:often|rare|only|in|and|or|also|from|but)\b)[-āæǣēīōœ̄ðȳūüa-z]+[)(-āæǣēīōðȳūüa-z]+[-āæǣēīōðȳūüa-z]+(,\s(?!(pret|pres|sg|pl|sing|imperat|subj|impers)\b)[-āæǣēīōœ̄ðȳūüa-z]+[)(-āæǣēīōðȳūüa-z]+[-āæǣēīōðȳūüa-z]+)*\??/
SPELLVAR: /\s\(((=\s)?(?!(sv\^)\b)[āæǣēīōœ̄ðȳūüa-z-]{1,6}(\^[0-5]{1})?\??)((,|;)\s([āæǣēœ̄īōðȳūüa-z-]{1,4}(\^[0-5]{1})?))*\??\)/

GEN: /\(?[mnf]{1,3}[.?]{1,2}\)?\s?/
NODOTGEN.1:/[mnf]{1,3}/
POS: /\(?(interj\.|interrog\.\sparticle|accented\sverbal\sprefix|subst\.|sv\.|wv\.|\bsv\b|\bwv\b|sb\.?|vb\.|anv\.|swv\.|adj\.|adv\.|prep\.|pron\.|ptc\.|pp\.|num\.|conj\.),?\)?\s?/
VERB_INFL_TYPE.20: /\^[0-9](,[0-9])?\)?/
CASE.2:/(?!and|in)([nagdi]{1,2}\.?|[agdi]{1,2}(?!f\.\s|m\.\s))[;,]?\s?/
SINGLECASE: /dat\.|gen\./
NUM:/(sbpl\.|sg\.|sing\.|pl\.|(?<!\s)[sp]\.?)\,?\s?/
TNS:/(pret\.|pres\.),?\s?/
PERS:/[1-3]\.?,?\s?/
MOOD: /(ind\.|imperat\.|subj\.),?\s?/
DGR: /\(?(comp\.|sup\.|superl\.)\)?,?\s?/
DECL.5: /\(?(indecl\.|strong|wk\.)\)? | [sw](?=(f|m|n))/
VALEN: /\(?(tr\.|intr\.|refl\.|pers\.\sand\simpers\.|impers\.|pers\.|tr\.\sintr\.)\)?,?\s?/
OF: /of/
OR: /_or_/
LBL.5: /(and|or|also|from|but)(?=\s)/
USGLBL.10: /(occl\.|often|rare|only|in|but\susu\.|usu\.|rarely|esp\.|w\.\s?|used\sas)(?=\s)/
USGPREP: /æt|on|of|tō|fram|be|wið/

REFLBL: /==|=|v\.\salso|v\.|\?=/
REFWORD: /(?!as\ssb\.|[IV]{1,4}\.)[A-ZāæÐÆǣēīōðȳūüa-z-*?]+([āæÐÆǣēīōðȳūüa-z-*?)()]+[āæÐÆǣēīōðȳūüa-z-*?]+)?/
REFNUMWORD: /(\([1-3]\)\s_?[āæÆǣēīōðȳūüa-zA-Z\-\^0-9\*]+_?)(,|;|(\s([IV]{1,4}\.,?;?)))\s(\([1-3]\)\s(?!pret\.|pres\.)[+±āæÆǣēīōðȳūüa-zA-Z\-\^0-9\*]+(,|;|(\s([IV]{1,4}\.,?;?)))*\s?)*\.?/
HOMREF: /(?<!\.\s)[IV]{1,4}\.(\sand\s[IV]{1,4}\.)?/
GRAMREF: /\(?(interj\.|interrog\.\sparticle|accented\sverbal\sprefix|subst\.|sv\.|sb\.|vb\.|anv\.|swv\.|adj\.|adv\.|prep\.|pron\.|ptc\.|pp\.|num\.|conj\.),?\)?\s?/
PREFSUFXR: /[āæǣēīōðȳūüa-z\(\)-]+(,\s[āæǣēīōðȳūüa-z\(\)-]+)+[?!.]?/

TRANSLATION.1: /'?(_|\(_|_\()'?.*?_[',!]*/
GLOSS.3: /(((?<=_\s)\((i\.e\.\s)?(?![a-z]\.)[='a-z-.0-9A-Z]+(\s[?a-z-.0-9A-Z]+)*\),?)|(\((?![a-z]\.)['a-z-.0-9A-Z]+(\s[?a-z-.0-9A-Z]+)*\)(?=\s_)),?)|\(gram\.\)/
QMSENSE: /\(.*?\?.*?_.*?_\),?|\(_.*?_\s?\?\s?\)?,?/


SOURCE.5: /[#_]?[ÆA-Z][A-Za-z]{,4}[#_]?[,;?]?\s?/
SOURCE_NUM.10: /((((p\s)?(p\.\s)?[p0-9·^´#]+)[a-z]?(\s\([0-9]+\)[a-z]?)?[,;]?)|(\(([0-9·^´,#]+)[a-z]?(\s\([0-9]+\)[a-z]?)?[,;]?\)))(\[[0-9a-z]+(,[0-9])?\])?/
SRCVAR: /(?<=\s)\([-āæǣēīōðȳūüa-z]{1,6}(\^[0-9])?\)[,;?]?/
MSREF: /\([A-Z][a-z]+\.\s([A-Za-z]\s)*([xiv]{1,4})\)/
AUTH: /\((Tupper)\)/

OEDREF: /\s?'_.*?_(\^[0-9])?[.,]?';?\s?/
VIDE: /v\.\salso|v\.\s|V\.\s/
COMPARE: /cp\./
LANG: /_[A-Z][A-Za-z]*(\s[A-Z][A-Za-z]*)?\.?_\s?/
PARENXR.2: /\(\??=\s[+±āæÆǣēīōðȳūüa-zA-Z*\?_]{4,}(\)|;?\s[ÆA-Za-z]*\s[\^0-9·•]*\)),?/
SYN: /(?!as\ssb\.|[IV]{1,4}\.)[āäæÐÆǣēīōöðȳūüa-zA-Z\*\(\)]+/
SQBRDASHVAR: /-[āäæÐÆǣēīōöðȳūüa-zA-Z\*\(\)]+|[āäæÐÆǣēīōöðȳūüa-zA-Z\*\(\)]+-/

EDCOMM: /\[\[.*?\]\]/

%ignore " "
%import common.NEWLINE
%ignore NEWLINE       
"""

def format_tree_simple(tree, indent=0):
    """
    Format a parse tree
    """
    if isinstance(tree, Tree):
        result = "  " * indent + str(tree.data)
        if tree.children:
            for child in tree.children:
                if isinstance(child, Tree):
                    result += "\n" + format_tree_simple(child, indent + 1)
                else:
                    result += "\t" + str(child)
        return result
    else:
        return "  " * indent + str(tree)

class DictionaryTransformer(Transformer):
    """
    The TEI transformer:
      
    """

    XML_NS = "http://www.w3.org/XML/1998/namespace"

    _ENTRY_NUM_SOURCES = {"OEG", "Chr", "CP"}

    _LINE_ONLY_SOURCES = {
        
        "Alm", "Cra", "Dom", "Fin", "Gen", "Sol", "Jud", "GnE", "Jul", "Mod",
        "Deor", "reat", "Hell", "Leas", "Part", "Rood", "Ruin", "Sat", "Seaf",
        "Soul", "Wald", "hale", "Wid", "Wif",
        "Ph", "An", "Ap", "Az", "Br", "Cr", "Da", "Gn", "El", "Ex", "Gu", "Hu",
        "Ma", "Pa", "Wa", "Wy", "B",
    }

    _COLUMN_SOURCES = {"WW"}

    _PASSAGE_SOURCES = {"Sc"}

    DICT_PREFIX = "CAS2"

    _GEO_LABELS = {
        "K": "kentish",
        "WS": "west saxon",
        "EWS": "early west saxon",
        "LWS": "late west saxon",
        "M": "mercian",
        "N": "northumbrian",
    }

    _POS_MAP = {
        "adj.": "adjective",
        "adv.": "adverb",
        "interj.": "interjection",
        "interrog. particle": "interrogative particle",
        "accented verbal prefix": "accented verbal prefix",
        "subst.": "noun",
        "sb.": "noun",
        "vb.": "verb",
        "sv.": "strong verb",
        "wv.": "weak verb",
        "sv": "strong verb",
        "wv": "weak verb",
        "swv.": "strong-weak verb",
        "anv.": "anomalous verb",
        "ptc.": "participle",
        "pp.": "past participle",
        "num.": "numeral",
        "conj.": "conjunction",
        "prep.": "preposition",
        "pron.": "pronoun",
    }

    _LANG_MAP = {
        # Latin and Latin-like labels: default to etymon
        "L": ("Latin", "la"),
        "Lat": ("Latin", "la"),
        "Low L": ("Low Latin", "la"),
        "Low Lat": ("Low Latin", "la"),
        "Late L": ("Late Latin", "la"),
        "Med L": ("Medieval Latin", "la"),
        "M L": ("Medieval Latin", "la"),

        # Germanic and other comparison languages: default to cognate
        "Goth": ("Gothic", "got"),
        "OHG": ("Old High German", "goh"),
        "MHG": ("Middle High German", "gmh"),
        "OS": ("Old Saxon", "osx"),
        "ON": ("Old Norse", "non"),
        "OE": ("Old English", "ang"),
        "Ger": ("German", "de"),
        "Germ": ("German", "de"),
        "German": ("German", "de"),
        "Du": ("Dutch", "nl"),
        "Dut": ("Dutch", "nl"),
        "Fr": ("French", "fr"),
        "French": ("French", "fr"),
        "OF": ("Old French", "fro"),
        "OFr": ("Old French", "fro"),
        "ME": ("Middle English", "enm"),
        "Gr": ("Ancient Greek", "grc"),
        "Gk": ("Ancient Greek", "grc"),
        "Greek": ("Ancient Greek", "grc"),
    }

    _LATIN_ETYM_LABELS = {
        "L", "Lat", "Low L", "Low Lat", "Late L", "Med L", "M L"
    }    

    def __init__(self):
        super().__init__()
        # per-entry state captured via tokens
        self._lemma = None          # first WORD in entry
        self._prefix = None         # '+', '±', or None
        self._has_qm = False        # did we see QM?
        self._variants = []          # remember orthographic variants for this entry
        self._last_orth_base = None  # most recent orth base for spell_var expansion
        ET.register_namespace('xml', self.XML_NS)


    """
    HELPERS
        
    """
    # ---------------- safety net for undefined elements ----------------
    def __default__(self, data, children, meta):
        # Flatten pass-through so unimplemented rules never break anything
        flat = []
        for ch in children:
            if ch is None:
                continue
            if isinstance(ch, (list, tuple)):
                flat.extend([x for x in ch if x is not None])
            else:
                flat.append(ch)
        return flat
    
    def _make_pos_gram(self, inner_text: str) -> ET.Element:
        """
        inner_text is the POS token content with any surrounding parentheses removed
        (e.g., 'adj.' or 'sv.'). We'll keep the original spelling in element text,
        and map to a normalized @value via _POS_MAP (fallback: cleaned inner_text).
        """
        txt = inner_text.strip().rstrip(",")
        norm = txt.lower()
        val = self._POS_MAP.get(norm)
        if val is None and norm.endswith("."):
            val = self._POS_MAP.get(norm[:-1])
        if val is None:
            val = norm.replace(".", "")
        g = ET.Element("gram", {"type": "pos", "value": val})
        g.text = txt
        return g
    
    def _roman_to_int(self, roman: str) -> int:
        roman = roman.upper().strip()
        values = {"I": 1, "V": 5, "X": 10}
        total, prev = 0, 0
        for ch in reversed(roman):
            v = values.get(ch, 0)
            if v < prev:
                total -= v
            else:
                total += v
                prev = v
        return total
    
    def _parse_source_numbers(self, s: str, src_code: str | None = None):
        """
        Parse source locators after a source abbreviation.

        Covered checked patterns include:
        - OEG 609, CP 488, Chr 87a -> entry numbers
        - W 149^33 -> page + line
        - L 32[19], LL 110[49,3] -> page + clause
        - L 448 (5,2) -> page + clause
        - sc 131^3,4 -> page + passage
        - Ld 1·294 -> volume + page
        - Ld 0-9n -> page range + footnote marker
        - WW 135#n#1 -> column + footnote
        - Sol 479, B 51 -> line-only poetic/source references
        - HGl 46a, AEL 23b^643 -> page/page-letter + optional line
        """
        s = (s or "").strip()
        if not s:
            return []

        norm_src = (src_code or "").strip().replace("#", "").replace("_", "")
        norm_src = norm_src.rstrip(",;?.:")

        out = []

        def make_bibl_scope(unit: str, text: str) -> ET.Element:
            el = ET.Element("biblScope", {"unit": unit})
            el.text = text
            return el

        def make_cited_range(unit: str, text: str) -> ET.Element:
            el = ET.Element("citedRange", {"unit": unit})
            el.text = text
            return el

        def append_default_number(text: str):
            """
            Interpret an ambiguous plain number according to the source.
            """
            if norm_src in self._ENTRY_NUM_SOURCES:
                out.append(make_cited_range("entry", text))
            elif norm_src in self._LINE_ONLY_SOURCES:
                out.append(make_cited_range("line", text))
            elif norm_src in self._COLUMN_SOURCES:
                out.append(make_bibl_scope("column", text))
            else:
                out.append(make_bibl_scope("page", text))

        def append_line_or_passage(text: str):
            if norm_src in self._PASSAGE_SOURCES:
                out.append(make_cited_range("passage", text))
            else:
                out.append(make_cited_range("line", text))

        token_re = re.compile(
            r"""
            p\s*\d+[A-Za-z]?\^\d+(?:,\d+)*       # p4^10, p23b^352
            |\d+[A-Za-z]?\^\d+(?:,\d+)*          # 149^33, 23b^643, 131^3,4
            |\d+\[[0-9]+(?:,[0-9]+)*\]           # 32[19], 110[49,3]
            |\d+\([0-9]+(?:,[0-9]+)*\)           # 448(5,2)
            |\d+-\d+n                            # 0-9n
            |\d+[·.]\d+                          # 1·294, 1.294
            |\d+\#n\#\d+                         # 135#n#1
            |\#n\#\d+                            # #n#1
            |\^\d+(?:,\d+)*                      # ^33, ^3,4
            |\[[0-9]+(?:,[0-9]+)*\]              # [19], [49,3]
            |\([0-9]+(?:,[0-9]+)*\)              # (5,2)
            |\d+·                                # 29·
            |p\s*\d+[A-Za-z]?                    # p4
            |\d+[A-Za-z]+                        # 87a, 1010CD, 46a
            |\d+                                 # 609, 488, 21
            """,
            re.VERBOSE
        )

        parts = [m.group(0).strip() for m in token_re.finditer(s)]

        for p in parts:
            # p4^10 / p23b^352
            m = re.fullmatch(r"p\s*(\d+[A-Za-z]?)\^(\d+(?:,\d+)*)", p)
            if m:
                out.append(make_bibl_scope("page", "p" + m.group(1)))
                append_line_or_passage("^" + m.group(2))
                continue

            # 149^33 / 23b^643 / 131^3,4
            m = re.fullmatch(r"(\d+[A-Za-z]?)\^(\d+(?:,\d+)*)", p)
            if m:
                out.append(make_bibl_scope("page", m.group(1)))
                append_line_or_passage("^" + m.group(2))
                continue

            # 32[19] / 110[49,3]
            m = re.fullmatch(r"(\d+)(\[[0-9]+(?:,[0-9]+)*\])", p)
            if m:
                out.append(make_bibl_scope("page", m.group(1)))
                out.append(make_cited_range("clause", m.group(2)))
                continue

            # 448(5,2)
            m = re.fullmatch(r"(\d+)(\([0-9]+(?:,[0-9]+)*\))", p)
            if m:
                out.append(make_bibl_scope("page", m.group(1)))
                out.append(make_cited_range("clause", m.group(2)))
                continue

            # 0-9n = page range + footnote marker
            m = re.fullmatch(r"(\d+-\d+)n", p)
            if m:
                out.append(make_bibl_scope("page", m.group(1)))
                out.append(make_bibl_scope("footnote", "n"))
                continue

            # 1·294 / 1.294 = volume + page
            m = re.fullmatch(r"(\d+)[·.](\d+)", p)
            if m:
                out.append(make_bibl_scope("volume", m.group(1)))
                out.append(make_bibl_scope("page", m.group(2)))
                continue

            # 135#n#1 = page/column + footnote
            m = re.fullmatch(r"(\d+)#n#(\d+)", p)
            if m:
                if norm_src in self._COLUMN_SOURCES:
                    out.append(make_bibl_scope("column", m.group(1)))
                else:
                    out.append(make_bibl_scope("page", m.group(1)))
                out.append(make_bibl_scope("footnote", m.group(2)))
                continue

            # #n#1
            m = re.fullmatch(r"#n#(\d+)", p)
            if m:
                out.append(make_bibl_scope("footnote", m.group(1)))
                continue

            # ^33 / ^3,4
            if re.fullmatch(r"\^\d+(?:,\d+)*", p):
                append_line_or_passage(p)
                continue

            # [19] / [49,3]
            if re.fullmatch(r"\[[0-9]+(?:,[0-9]+)*\]", p):
                out.append(make_cited_range("clause", p))
                continue

            # (5,2)
            if re.fullmatch(r"\([0-9]+(?:,[0-9]+)*\)", p):
                out.append(make_cited_range("clause", p))
                continue

            # 29· = volume marker
            m = re.fullmatch(r"(\d+)·", p)
            if m:
                out.append(make_bibl_scope("volume", m.group(1)))
                continue

            # p4
            m = re.fullmatch(r"p\s*(\d+[A-Za-z]?)", p)
            if m:
                out.append(make_bibl_scope("page", "p" + m.group(1)))
                continue

            # 87a / 1010CD / 46a
            if re.fullmatch(r"\d+[A-Za-z]+", p):
                if norm_src in self._ENTRY_NUM_SOURCES:
                    out.append(make_cited_range("entry", p))
                elif norm_src in self._LINE_ONLY_SOURCES:
                    out.append(make_cited_range("line", p))
                elif norm_src in self._COLUMN_SOURCES:
                    out.append(make_bibl_scope("column", p))
                else:
                    out.append(make_bibl_scope("page", p))
                continue

            # Plain number
            if re.fullmatch(r"\d+", p):
                append_default_number(p)
                continue

            # Fallback: preserve anything unexpected as a generic locator.
            out.append(make_cited_range("locator", p))

        return out
    
    def _replace_nth_vowel(self, word: str, repl: str, n: int) -> str:
        """
        Replace the n-th *vowel cluster* (1-based) in 'word' with 'repl'.
        A vowel cluster is one or more adjacent vowel characters (ea, eo, ǣ, etc.).
        If n is out of range, fall back to the first cluster.
        """
        vowels = set("aAeEiIoOuUyYāĀæÆǣǢēĒīĪōŌȳȲūŪ")
        clusters = []
        i = 0
        while i < len(word):
            if word[i] in vowels:
                j = i + 1
                while j < len(word) and word[j] in vowels:
                    j += 1
                clusters.append((i, j))  # [start, end) of this vowel cluster
                i = j
            else:
                i += 1

        if not clusters:
            return word  # nothing to replace

        # clamp to [1, len(clusters)]
        if n < 1 or n > len(clusters):
            n = 1

        start, end = clusters[n - 1]
        return word[:start] + repl + word[end:]
    
    def _is_pure_vowel_string(self, s: str) -> bool:
        """
        True if 's' contains only vowel letters (incl. macrons/diacritics).
        Items with consonants/hyphens (e.g., 'al-', 'æl-') return False.
        """
        vowels = set("aAeEiIoOuUyYāĀæÆǣǢēĒīĪōŌȳȲūŪ")
        return all(ch in vowels for ch in s)


    def _parse_spellvar_items(self, raw: str):
        """
        raw is the SPELLVAR token text like '(i, y)' or '(eo^1, e^2)' (possibly spaces).
        Returns a list of dicts: [{"letters": "eo", "slot": 1, "sep": ","}, ...]
        where 'sep' is the following separator for this item (',' or ';' or ')' for the last).
        """
       
        s = raw.strip()
        # keep only the content inside the outer parentheses
        if s.startswith("(") and s.endswith(")"):
            core = s[1:-1].strip()
        else:
            core = s

        # Split on comma/semicolon but keep separators
        parts = re.split(r"\s*([,;])\s*", core)
        # parts = [item1, sep1, item2, sep2, item3, ...]
        items = []
        i = 0
        while i < len(parts):
            item = parts[i].strip()
            sep = ")"
            if i+1 < len(parts):
                sep = parts[i+1]  # ',' or ';'
                i += 2
            else:
                i += 1

            # extract letters + optional ^n
            m = re.match(r"([A-Za-zāæǣēīōȳūüöœĀÆǢĒĪŌȲŪÜÖŒ\-]+)(?:\^(\d+))?\??$", item)
            if m:
                letters = m.group(1)
                slot = int(m.group(2)) if m.group(2) else 1
            else:
                letters, slot = item, 1

            items.append({"letters": letters, "slot": slot, "sep": sep})
        return items

    def _make_full_orth(self, txt: str, prefix_symbol: str | None) -> ET.Element:
        """
        Build an <orth> for a *full* form (not a partial/vowel replacement).
        Handle cases like "bicni(g)end" which means both "bicniend" and "bicnigend".
        If prefix_symbol is '+': expand="ge-<txt>" 
        If prefix_symbol is '±': expand="<txt>, ge-<txt>"
        """
        txt = (txt or "").strip()
        
        # Parse parenthetical optional parts in the word
        # e.g., "bicni(g)end" -> ["bicniend", "bicnigend"]
        def expand_parens(word):
           
            if '(' not in word:
                return [word]
            # Find first parenthetical group
            m = re.search(r'\(([^)]*)\)', word)
            if not m:
                return [word]
            before = word[:m.start()]
            inside = m.group(1)
            after = word[m.end():]
            # Two variants: with and without the parenthetical content
            without = before + after
            with_it = before + inside + after
            # Recursively handle multiple parentheses
            results = []
            for variant in [without, with_it]:
                results.extend(expand_parens(variant))
            return results
        
        base_forms = expand_parens(txt)
        
        # Apply prefix logic
        if prefix_symbol == '+':
            expanded = ", ".join(f"ge-{form}" for form in base_forms)
            orth = ET.Element("orth", {"extent": "full", "expand": expanded})
            lbl = ET.SubElement(orth, "lbl", {"expand": "ge-"})
            lbl.text = "+"
            ET.SubElement(orth, "seg").text = txt
        elif prefix_symbol == '±':
            # Include both with and without ge- for each base form
            all_forms = base_forms + [f"ge-{form}" for form in base_forms]
            expanded = ", ".join(all_forms)
            orth = ET.Element("orth", {"extent": "full", "expand": expanded})
            lbl = ET.SubElement(orth, "lbl", {"expand": "ge-_optional"})
            lbl.text = "±"
            ET.SubElement(orth, "seg").text = txt
        else:
            orth = ET.Element("orth")
            if len(base_forms) > 1:
                orth.set("expand", ", ".join(base_forms))
            orth.text = txt
        
        return orth
    
    def _expand_optional_parens_with_first(self, word: str) -> list[str]:
        """
        Expand optional parenthesized letters in a form, keeping the form
        with the parenthesized material first.

        Example:
          mǣd(w)a -> ["mǣdwa", "mǣda"]
        """
        word = (word or "").strip()
        m = re.search(r"\(([^)]*)\)", word)

        if not m:
            return [word]

        before = word[:m.start()]
        inside = m.group(1)
        after = word[m.end():]

        with_it = before + inside + after
        without = before + after

        results = []
        for v in (with_it, without):
            results.extend(self._expand_optional_parens_with_first(v))

        out = []
        for v in results:
            if v not in out:
                out.append(v)

        return out
    
    def _make_inflected_orths(self, raw_variant: str) -> list[ET.Element]:
        """
        Build one or more <orth> elements for inflected forms.

        Full form:
          mēda -> <orth>mēda</orth>

        Full form with optional letters:
          mǣd(w)a -> <orth expand="mǣdwa, mǣda">mǣd(w)a</orth>

        Multiple full forms:
          mǣd(w)a, mǣdwe ->
            <orth expand="mǣdwa, mǣda">mǣd(w)a</orth>
            <orth>mǣdwe</orth>

        Partial form:
          -da -> <orth extent="part" expand="mǣda"><seg>-da</seg></orth>
        """
        raw_variant = (raw_variant or "").strip().rstrip(",;")
        if not raw_variant:
            return []

        parts = [p.strip() for p in re.split(r",\s*", raw_variant) if p.strip()]
        lemma = self._lemma or "UNKNOWN"
        out = []

        for part in parts:
            if part.startswith("-"):
                suffix = part.lstrip("-")

                if "-" in lemma:
                    stem = lemma[:lemma.index("-")]
                else:
                    stem = lemma[:max(0, len(lemma) - len(suffix))]

                expand = stem + suffix

                orth = ET.Element("orth", { 
                    "extent": "part",
                    "expand": expand
                })
                ET.SubElement(orth, "seg").text = part

            else:
                expanded_forms = self._expand_optional_parens_with_first(part)

                orth = ET.Element("orth")
                if len(expanded_forms) > 1:
                    orth.set("expand", ", ".join(expanded_forms))

                orth.text = part

            out.append(orth)

        return out
    
    def _make_hyphen_split_variant_orth(self, variant_text: str) -> ET.Element:
        """
        Handles orthographic variants introduced by a bare hyphen:

          be-byrgan ... -byrian

        The grammar consumes '-' separately, so variant_text may be 'byrian'.
        We preserve the source marker as <seg>-byrian</seg> and expand from
        the lemma split at the last hyphen:

          be-byrgan + -byrian -> be-byrian
        """
        raw = (variant_text or "").strip().rstrip(",;")
        visible = raw if raw.startswith("-") else f"-{raw}"

        attrs = {"extent": "part"}

        if self._lemma and "-" in self._lemma:
            left = self._lemma.rsplit("-", 1)[0]
            attrs["expand"] = f"{left}-{visible.lstrip('-')}"

        orth = ET.Element("orth", attrs)
        ET.SubElement(orth, "seg").text = visible
        return orth
        
    def _is_likely_orth_variant(self, variant_text: str) -> bool:
        """
        Determine if a variant is likely a full orthographic variant rather than
        a vowel substitution. Returns True if:
        - Length is similar to lemma (within 2 characters)
        - Has significant consonant overlap with lemma
        - OR contains parentheses indicating optional parts
        """
        if not self._lemma:
            return False
        
        # If variant contains parentheses, it's definitely an orth variant
        if '(' in variant_text or ')' in variant_text:
            return True
        
        # Compare lengths
        len_diff = abs(len(variant_text) - len(self._lemma))
        if len_diff > 2:
            return False
        
        # Check consonant overlap
        consonants = set("ðbcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
        variant_consonants = [c for c in variant_text if c in consonants]
        lemma_consonants = [c for c in self._lemma if c in consonants]
        
        # If consonant structure is very similar, it's likely an orth variant
        if variant_consonants and lemma_consonants:
            common = sum(1 for v, l in zip(variant_consonants, lemma_consonants) if v == l)
            if common / min(len(variant_consonants), len(lemma_consonants)) > 0.7:
                return True
        
        return False   
    
    def _is_abbrev_of_lemma(self, token_without_prefix: str) -> bool:
        """
        True when token looks like an abbreviation of the current lemma, e.g. 'h.'
        for lemma 'habban',  (any leading substring + dot).
        """
        tok = (token_without_prefix or "").strip()
        if not tok.endswith("."):
            return False
        base = tok[:-1]  # drop trailing dot
        if not base or not self._lemma:
            return False
        return self._lemma.lower().startswith(base.lower())

    def _token_to_id_part(self, raw_token: str) -> str:
        """
        Convert a collocation token to its xml:id component:
        '+word' -> 'ge-word'
        '±word' -> 'word'
        'word'  -> 'word'
        If the token is an abbreviation of the lemma (e.g. 'h.' for 'habban'),
        use the *lemma* as the base (and apply the same +/± rules).
        """
        import re
        t = (raw_token or "").strip()
        if not t:
            return t

        # pull off + / ±
        prefix = None
        if t[0] in ("+", "±"):
            prefix = t[0]
            core = t[1:].strip()
        else:
            core = t

        if self._is_abbrev_of_lemma(core):
            base = self._lemma or core
        else:
            base = re.sub(r"[,:;!?]+$", "", core)

        if prefix == "+":
            return f"ge-{base}"
        return base
    
    def _expand_adv_lice(self, lemma: str) -> str:
        """
        Build the adverb in -līce from the entry lemma + any known -lic variants.

        Priority:
        1) If lemma ends with -lic or -lic. → replace with -līce
        2) Else, if we saw a variant ending in 'lic' and starting with '-' (e.g. '-fullic'):
        - If lemma is hyphenated (e.g. 'georn-ful'), keep the base before the last hyphen
            and join the variant without the leading '-' and with 'lic'→'līce':
            'georn-' + 'fullic'→'fullīce' => 'georn-fullīce'
        3) Else, if lemma ends with 'ful' → lemma + 'līce'
        4) Fallback → lemma + 'līce' (crude but ensures presence)
        """
        L = (lemma or "").rstrip(".")
        # 1) direct -lic on lemma
        for suf in ("-lic", "lic"):
            if L.endswith(suf):
                return L[: -len(suf)] + "līce"

        # 2) look for suffix variant like "-fullic"
        for v in self._variants:
            v_clean = v.strip()
            if v_clean.startswith("-") and v_clean.endswith("lic"):
                core = v_clean[1:-3] + "līce"  # remove leading '-', swap lic→līce
                if "-" in L:
                    left, _right = L.rsplit("-", 1)
                    return f"{left}-{core}"
                else:
                    return L + core

        # 3) common pattern: '-ful' adjectives
        if L.endswith("ful"):
            return L + "līce"

        # 4) fallback
        return L + "līce"
    
    def _clean_lang_label(self, raw: str) -> str:
            """
            '_Ger._' -> 'Ger'
            '_Low L._' -> 'Low L'
            '_M. L._' -> 'M L'
            """
            s = (raw or "").replace("_", "").strip()
            s = re.sub(r"\s+", " ", s)
            s = s.rstrip(".")
            s = s.replace("Med. L", "Med L")
            s = s.replace("M. L", "M L")
            return s      

    def _lang_info(self, raw: str) -> dict:
        label = self._clean_lang_label(raw)
        expand, norm = self._LANG_MAP.get(label, (label, "und"))
        return {
            "_lang": True,
            "raw": raw.strip(),
            "label": label,
            "expand": expand,
            "norm": norm,
            "cit_type": "etymon" if label in self._LATIN_ETYM_LABELS else "cognate",
        }

    def _make_etym_lbl(self, info: dict) -> ET.Element:
        lbl = ET.Element("lbl", {"norm": info.get("norm", "")})
        lbl.text = info.get("text", "")
        return lbl

    def _add_tail(self, elem: ET.Element, txt: str | None):
        if txt:
            elem.tail = (elem.tail or "") + txt 
    
    def _pc(self, text: str) -> ET.Element:
        pc = ET.Element("pc")
        pc.text = text
        return pc
    
    def _geo_norm(self, code: str) -> str | None:
        code = (code or "").strip().rstrip(",;?.:")
        return self._GEO_LABELS.get(code)

    def _is_geo_code(self, code: str) -> bool:
        return self._geo_norm(code) is not None

    def _make_geo_usg(self, code: str) -> ET.Element:
        clean = (code or "").strip().rstrip(",;?.:")
        usg = ET.Element("usg", {
            "type": "geo",
            "norm": self._geo_norm(clean) or clean.lower()
        })
        usg.text = clean
        return usg
    
    def _usage_norm(self, text: str) -> str | None:
        text = re.sub(r"\s+", " ", (text or "").strip())
        mapping = {
            "usu.": "usually",
            "but usu.": "but usually",
            "w.": "with",
            "used as": "used as",
            "occl.": "occasionally",
            "esp.": "especially",
        }
        return mapping.get(text)

    def _make_usage_lbl(self, text: str) -> ET.Element:
        attrs = {"type": "usage"}
        norm = self._usage_norm(text)
        if norm:
            attrs["norm"] = norm
        lbl = ET.Element("lbl", attrs)
        lbl.text = text
        return lbl

    def _make_plain_lbl(self, text: str) -> ET.Element:
        lbl = ET.Element("lbl")
        lbl.text = text
        return lbl

    def _case_value(self, raw: str) -> str | None:
        key = (raw or "").strip().rstrip(",;").rstrip(".").lower()
        mapping = {
            "n": "nominative",
            "a": "accusative",
            "g": "genitive",
            "d": "dative",
            "i": "instrumental",
        }

        if key in mapping:
            return mapping[key]

        # Handles combined cases such as "na" -> "nominative, accusative"
        if key and all(ch in mapping for ch in key):
            return ", ".join(mapping[ch] for ch in key)

        return None

    def _make_case_gram(self, raw: str) -> ET.Element:
        display = (raw or "").strip().rstrip(",;")
        attrs = {"type": "case"}
        value = self._case_value(display)
        if value:
            attrs["value"] = value
        gram = ET.Element("gram", attrs)
        gram.text = display
        return gram

    def _make_construction_gram(self, text: str, value: str | None = None) -> ET.Element:
        attrs = {"type": "construction"}
        if value:
            attrs["value"] = value
        gram = ET.Element("gram", attrs)
        gram.text = (text or "").strip().rstrip(",;")
        return gram
    
    def _bibl_to_geo_usg(self, bibl_el: ET.Element) -> ET.Element | None:
        """
        Convert a <bibl> whose @source is actually a dialect/variety label
        into <usg type="geo" norm="...">...</usg>.
        """
        if bibl_el is None or not isinstance(bibl_el, ET.Element):
            return None

        source = (bibl_el.get("source") or "").lstrip("#")
        if not self._is_geo_code(source):
            return None

        return self._make_geo_usg(source)

    def _as_construction_gram(self, gram: ET.Element) -> ET.Element:
        """
        Convert an existing <gram> into <gram type="construction">,
        preserving @value and visible text.
        """
        text = (gram.text or "".join(gram.itertext()) or "").strip()
        return self._make_construction_gram(text, gram.get("value"))

    def _append_etym_child(self, etym_el: ET.Element, child: ET.Element, tail: str = ""):
        etym_el.append(child)
        if tail:
            etym_el.append(self._pc(tail))

    def _make_etym_xr(self, word: str, label_info: dict | None = None) -> ET.Element:
        clean = re.sub(r"[,:;.\s]+$", "", word.strip())
        xr = ET.Element("xr", {"type": "related"})

        if label_info is not None:
            xr.append(self._make_etym_lbl(label_info))

        ref = ET.SubElement(xr, "ref", {
            "type": "entry",
            "target": f"#{self.DICT_PREFIX}.{clean}"
        })
        ref.text = word.strip()
        return xr

    def _make_oed_xr(self, raw: str, label_info: dict | None = None) -> ET.Element:
        """
        OED/NED-style reference inside square brackets, e.g. '_kemp_' or ''_cheap_''.

        Output:
        <xr type="related">
        <ref type="entry" target="OED_kemp">kemp</ref>
        </xr>
        """
        raw_txt = (raw or "").strip()

        # Extract the word inside underscores: '_kemp_' -> kemp
        m = re.search(r"_([^_]+)_", raw_txt)
        if m:
            oed_word = m.group(1).strip()
        else:
            oed_word = raw_txt.strip("'\"‘’“”.,;: ")

        # Remove possible superscript marker from target, e.g. cheap^1 -> cheap
        oed_word_for_target = re.sub(r"\^\d+$", "", oed_word).strip()
        oed_word_for_target = re.sub(r"\s+", "_", oed_word_for_target)

        xr = ET.Element("xr", {"type": "related"})

        if label_info is not None:
            xr.append(self._make_etym_lbl(label_info))

        ref = ET.SubElement(
            xr,
            "ref",
            {
                "type": "entry",
                "target": f"OED_{oed_word_for_target}"
            }
        )
        ref.text = f"'{oed_word}'"

        return xr

    def _make_lang_cit(self, lang_payload: dict, label_info: dict | None = None) -> ET.Element:
        lang = lang_payload["lang"]
        cit = ET.Element("cit", {
            "type": lang["cit_type"],
            f"{{{self.XML_NS}}}lang": lang["norm"]
        })

        if label_info is not None:
            cit.append(self._make_etym_lbl(label_info))

        for local_lbl in lang_payload.get("labels", []):
            lbl = ET.SubElement(cit, "lbl")
            lbl.text = local_lbl

        lang_el = ET.SubElement(cit, "lang", {
            "expand": lang["expand"],
            "norm": lang["norm"]
        })
        lang_el.text = lang["label"] + "."

        for w in lang_payload.get("forms", []):
            form = ET.SubElement(cit, "form")
            orth = ET.SubElement(form, "orth")
            orth.text = w

        return cit

    def _append_etym_text(self, target: ET.Element, txt: str | None):
        """
        Keep this only as a fallback for older etym elements.
        New etym brackets/punctuation are encoded as <pc>.
        """
        if txt:
            target.append(self._pc(txt))

    def _append_etym_contents(self, target: ET.Element, source: ET.Element):
        """
        Merge adjacent <etym> elements by moving all children from source into target.
        This preserves separate bracket pairs:
        <pc>[</pc> ... <pc>]</pc><pc>[</pc> ... <pc>]</pc>
        """
        if source.text and source.text.strip():
            target.append(self._pc(source.text.strip()))

        for child in list(source):
            source.remove(child)
            target.append(child)

    def _merge_adjacent_etym(self, items: list) -> list:
        merged = []
        for item in items:
            if (
                isinstance(item, ET.Element)
                and item.tag == "etym"
                and merged
                and isinstance(merged[-1], ET.Element)
                and merged[-1].tag == "etym"
            ):
                self._append_etym_contents(merged[-1], item)
            else:
                merged.append(item)
        return merged

    
    """
    TERMINALS
      
    """

    @v_args(inline=True)
    def WORD(self, tok):
        if self._lemma is None:
            self._lemma = str(tok).strip()
            self._last_orth_base = str(tok).strip()
        return tok

    @v_args(inline=True)
    def GE_PREF(self, tok):  # '+'
        if self._lemma is None and self._prefix is None:
            self._prefix = '+'
        return tok

    @v_args(inline=True)
    def GE_OPT(self, tok):   # '±'
        if self._lemma is None and self._prefix is None:
            self._prefix = '±'
        return tok
    

    @v_args(inline=True)
    def QM(self, tok):
        return {"_qm": True}
    
    @v_args(inline=True)
    def VERB_INFL_TYPE(self, tok):
        """
        Turn ^n / ^n) / ^1,2) into one or more:
          <gram type="inflectionType"><hi rend="superscript">...</hi></gram>

        Rules:
        - Strip the leading '^'
        - Keep ')' if present (encode as-is for now)
        - If comma-separated (e.g. '1,2)' or '1,2'), emit TWO grams:
            first hi text keeps the comma: '1,'
            second hi text is the rest: '2)' or '2'
        """
        raw = str(tok).strip()
        if raw.startswith("^"):
            raw = raw[1:]

        if not raw:
            return None

        # Split only on the first comma; keep comma on the first number
        if "," in raw:
            first, rest = raw.split(",", 1)
            parts = [first + ",", rest]
        else:
            parts = [raw]

        grams = []
        for p in parts:
            if not p:
                continue
            g = ET.Element("gram", {"type": "inflectionType"})
            hi = ET.SubElement(g, "hi", {"rend": "superscript"})
            hi.text = p
            grams.append(g)

        return grams if grams else None
    
    @v_args(inline=True)
    def POET_SYMB(self, tok):
        """
        Turn † / ‡ into a <usg> element.
        † → expand="attested in poetic texts only"
        ‡ → expand="attested in poetical texts only, and once only"
        """
        sym = str(tok).strip().rstrip(",")
        usg = ET.Element("usg", {"type": "textType"})
        if sym == "†":
            usg.set("expand", "attested in poetic texts only")
        elif sym == "‡":
            usg.set("expand", "attested in poetical texts only, and once only")
        else:
            usg.set("expand", "poetic")
        usg.text = sym
        return usg
    
    @v_args(inline=True)
    def ROM_NUM(self, tok):
       
        text = str(tok).strip()
        roman = text.rstrip(".").strip()
        n = self._roman_to_int(roman)
        return {"_rom_text": text, "_roman": roman, "_n": n}
    
    @v_args(inline=True)
    def LANG(self, tok):
        return self._lang_info(str(tok))

    # ---------------- for senses ----------------
    @v_args(inline=True)
    def TRANSLATION(self, tok):
        """
        Drop underscores and split on parenthetical segments.
        Example: "bill, beak, trunk (of an elephant)," ->
        <quote>bill, beak, trunk</quote>
        <gloss>(of an elephant),</gloss>
        If no parentheses, return a single <quote>.
        """
        text = str(tok)
        text = text.replace("_", "").strip()

        parts = []
        i = 0
        for m in re.finditer(r'\([^)]*\),?', text):
            before = text[i:m.start()].strip()
            if before:
                q = ET.Element("quote")
                q.text = before
                parts.append(q)
            g = ET.Element("gloss")
            g.text = m.group(0).strip()
            parts.append(g)
            i = m.end()

        tail = text[i:].strip()
        if tail:
            q = ET.Element("quote")
            q.text = tail
            parts.append(q)

        if not parts:
            q = ET.Element("quote"); q.text = text
            return q
        return parts
    
    @v_args(inline=True)
    def GLOSS(self, tok):
        g = ET.Element("gloss")
        g.text = str(tok).strip()  
        return g

    @v_args(inline=True)
    def COLON_SEP(self, tok):
        m = ET.Element("metamark", {"function": "senseSeparator"})
        m.text = ":"
        return m

    @v_args(inline=True)
    def SEMICOL_SEP(self, tok):
        m = ET.Element("metamark", {"function": "senseSeparator"})
        m.text = ";"
        return m

    @v_args(inline=True)
    def DOT_SEP(self, tok):
        m = ET.Element("metamark")
        m.text = "."
        return m
    
    # ---------------- BIBL ----------------  
    @v_args(inline=True)
    def SOURCE(self, tok):
        """
        Examples: '_Bo,', 'WG;', '#Æ', 'ES'
        - strip underscores and # for both the TEI @source and the displayed <title>
        - keep trailing comma/semicolon in the <title> text
        """
        raw = str(tok).strip()
        clean = raw.replace("_", "").replace("#", "").strip()
        title = clean
        code = clean.rstrip(",;?.:").strip()
        return {"_src_code": code, "_src_title": title}

    @v_args(inline=True)
    def SOURCE_NUM(self, tok):
        return {"_srcnum": str(tok).strip()}
    
    @v_args(inline=True)
    def EDCOMM(self, tok):
        """
        [[headword spelled "anihst"]]
        ->
        <note>[headword spelled "anihst"]</note>

        """
        raw = str(tok).strip()

        if raw.startswith("[[") and raw.endswith("]]"):
            text = raw[1:-1]   # remove only one bracket from each side
        else:
            text = raw

        note = ET.Element("note")
        note.text = text
        return note
    
    @v_args(inline=True)
    def SNS_POET_SYMB(self, tok):
        """
        Sense-level poetic symbols:
          (†) or (‡), and sometimes † before an italic translation.

        Encode without preserving the parentheses:
          <usg type="textType" expand="attested in poetic texts only">†</usg>
        """
        raw = str(tok).strip()
        sym = raw.strip("()").strip().rstrip(",")

        usg = ET.Element("usg", {"type": "textType"})

        if sym == "†":
            usg.set("expand", "attested in poetic texts only")
        elif sym == "‡":
            usg.set("expand", "attested in poetical texts only, and once only")
        else:
            usg.set("expand", "poetic")

        usg.text = sym
        return usg


    # ---------------- GRAM. INFO ----------------         
    @v_args(inline=True)
    def GEN(self, tok):
        """
        Examples of tok text (single token, may include parens and ?/.):
        'm.' 'nf.' '(m.)' '(mf?)' 'm?' '(nf. )'
        """
        raw = str(tok).strip()

        left_paren  = raw.startswith("(")
        right_paren = raw.endswith(")")
        inner = raw[1:-1].strip() if (left_paren and right_paren) else raw.strip("()").strip()

        # Detect uncertainty (question mark anywhere in the token)
        has_q = "?" in inner

        # Remove '?' for the displayed text 
        display = inner.replace("?", "").strip()

        # Build @value from letters in the display text (order-preserving)
        letters = [ch for ch in display if ch in "mnf"]
        label_map = {"m": "masculine", "n": "neuter", "f": "feminine"}
        values = ", ".join(label_map[c] for c in letters) if letters else ""

        gram = ET.Element("gram", {"type": "gender", "value": values})
        gram.text = display  

        out = []
        if left_paren:
            pc = ET.Element("pc"); pc.text = "("
            out.append(pc)

        out.append(gram)

        if has_q:
            note = ET.Element("note", {"cert": "low", "resp": "author"})
            note.text = "?"
            out.append(note)

        if right_paren:
            pc = ET.Element("pc"); pc.text = ")"
            out.append(pc)

        return out
    
    # --- handle gender without trailing dot (e.g., "m", "mf", "nf") ---
    @v_args(inline=True)
    def NODOTGEN(self, tok):
        inner = str(tok).strip()            
        letters = [ch for ch in inner if ch in "mnf"]
        label_map = {"m": "masculine", "n": "neuter", "f": "feminine"}
        values = ", ".join(label_map[c] for c in letters) if letters else ""
        gram = ET.Element("gram", {"type": "gender", "value": values})
        gram.text = inner                
        return gram
    
    @v_args(inline=True)
    def POS(self, tok):
        raw = str(tok).strip()
        left_paren  = raw.startswith("(")
        right_paren = raw.endswith(")")
        inner = raw[1:-1].strip() if (left_paren and right_paren) else raw.strip("()").strip()
        inner = inner.rstrip(",")  

        gram = self._make_pos_gram(inner)

        out = []
        if left_paren:
            pc = ET.Element("pc"); pc.text = "("
            out.append(pc)

        out.append(gram)

        if right_paren:
            pc = ET.Element("pc"); pc.text = ")"
            out.append(pc)

        return out
    
    @v_args(inline=True)
    def REFLBL(self, tok):
        # e.g., '=', '==', 'v.', 'v. also', '?='
        return str(tok).strip()

    @v_args(inline=True)
    def REFWORD(self, tok):
        return str(tok).strip()
    
    @v_args(inline=True)
    def COLLOC(self, tok):
        # Full collocation phrase, e.g. "tō āhte"
        return str(tok).strip()

    @v_args(inline=True)
    def ONEWORD(self, tok):
        # A single word, possibly with a leading '+' or '±', e.g. "±lǣred"
        return str(tok).strip()
    
    @v_args(inline=True)
    def INFVARIANT(self, tok):
        return {"_infvariant": str(tok).strip()}

    # ---------------- RULES ----------------
    def headword(self, children):
        """
        Handles:
        - headword-level question marks
        - lemma-attached verb inflection type
        - headword-level bibl/usg material, e.g. (LWS), (rare EWS), (ES 43·309)
        """
        out = []
        has_qm = False
        infl_grams = []
        lemma_extras = []

        def collect_lemma_extra(obj):
            if isinstance(obj, ET.Element) and obj.tag in ("bibl", "usg", "pc", "lbl"):
                lemma_extras.append(obj)
                return True
            return False

        for ch in children:
            if isinstance(ch, dict) and ch.get("_qm"):
                has_qm = True
                continue

            if collect_lemma_extra(ch):
                continue

            if (
                isinstance(ch, ET.Element)
                and ch.tag == "gram"
                and ch.get("type") == "inflectionType"
            ):
                infl_grams.append(ch)
                continue

            if isinstance(ch, (list, tuple)):
                remainder = []

                for z in ch:
                    if z is None:
                        continue

                    if isinstance(z, dict) and z.get("_qm"):
                        has_qm = True
                        continue

                    if collect_lemma_extra(z):
                        continue

                    if (
                        isinstance(z, ET.Element)
                        and z.tag == "gram"
                        and z.get("type") == "inflectionType"
                    ):
                        infl_grams.append(z)
                        continue

                    remainder.append(z)

                if remainder:
                    out.append(remainder)

                continue

            out.append(ch)

        if infl_grams:
            target_grp = None

            for item in out:
                if isinstance(item, ET.Element) and item.tag == "gramGrp":
                    target_grp = item
                    break

                if isinstance(item, (list, tuple)):
                    for z in item:
                        if isinstance(z, ET.Element) and z.tag == "gramGrp":
                            target_grp = z
                            break

                if target_grp is not None:
                    break

            if target_grp is None:
                target_grp = ET.Element("gramGrp")
                target_grp.append(ET.Element("gram", {
                    "type": "pos",
                    "value": "strong verb"
                }))

                for g in infl_grams:
                    target_grp.append(g)

                out.append(target_grp)

            else:
                last_pos_idx = -1

                for i, e in enumerate(list(target_grp)):
                    if e.tag == "gram" and e.get("type") == "pos":
                        last_pos_idx = i

                if last_pos_idx == -1:
                    target_grp.insert(0, ET.Element("gram", {
                        "type": "pos",
                        "value": "strong verb"
                    }))
                    insert_at = 1
                else:
                    insert_at = last_pos_idx + 1

                for g in infl_grams:
                    target_grp.insert(insert_at, g)
                    insert_at += 1

        if has_qm:
            out.append({"_headword_qm": True})

        if lemma_extras:
            out.append({"_lemma_extra": lemma_extras})

        return out if out else None


    def qm(self, children):

        out, saw = [], False
        for ch in children:
            if isinstance(ch, dict) and ch.get("_qm"):
                saw = True
            else:
                out.append(ch)
        if saw:
            out.append({"_qm": True})
        return out if out else {"_qm": True}
    
    def usglbl(self, children):
        """
        usglbl: USGLBL+

        Examples:
        only in
        usu.
        w.
        """
        parts = []

        def take(obj):
            if isinstance(obj, Token) and obj.type == "USGLBL":
                parts.append(str(obj).strip())
            elif isinstance(obj, str):
                parts.append(obj.strip())
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        text = " ".join(p for p in parts if p)
        return {"_usglbl": text} if text else None


    def case(self, children):
        """
        case: lbl? CASE

        In ordinary grammatical contexts this returns <gram type="case">.
        In construction/usage contexts it will later be converted to
        <gram type="construction">.
        """
        out = []

        def take(obj):
            if isinstance(obj, Token):
                if obj.type == "LBL":
                    out.append(self._make_plain_lbl(str(obj).strip()))
                elif obj.type == "CASE":
                    out.append(self._make_case_gram(str(obj)))
            elif isinstance(obj, ET.Element):
                out.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        return out if out else None


    def gramgrp(self, children):
        """
        Wrap any returned <gram> into a single <gramGrp>.
        If a gender is present and there is NO explicit POS, add an implicit
        <gram type="pos" value="noun"/> 
        """
        items = []
        for ch in children:
            if isinstance(ch, ET.Element) and ch.tag in ("gram", "pc", "note"):
                items.append(ch)
            elif isinstance(ch, (list, tuple)):
                for z in ch:
                    if isinstance(z, ET.Element) and z.tag in ("gram", "pc", "note"):
                        items.append(z)

        if not items:
            return None

        has_gender = any(e.tag == "gram" and e.get("type") == "gender" for e in items)
        has_pos    = any(e.tag == "gram" and e.get("type") == "pos"    for e in items)

        # Insert implicit noun POS 
        if has_gender and not has_pos:
            pos_noun = ET.Element("gram", {"type": "pos", "value": "noun"})
            insert_idx = 0
            for i, e in enumerate(items):
                if e.tag == "pc" and (e.text or "").strip() == "(":
                    insert_idx = i
                    break
            items.insert(insert_idx, pos_noun)

        grp = ET.Element("gramGrp")
        for e in items:
            grp.append(e)
        return grp
    
    def infgramgrp(self, children):
        """
        Wrap inflectional grams into <gramGrp>.

        Add implicit verb POS only when the group contains clearly verbal
        categories such as tense, person, or mood.
        """
        grams = []

        for ch in children:
            if isinstance(ch, ET.Element) and ch.tag == "gram":
                grams.append(ch)
            elif isinstance(ch, (list, tuple)):
                for z in ch:
                    if isinstance(z, ET.Element) and z.tag == "gram":
                        grams.append(z)

        if not grams:
            return None

        grp = ET.Element("gramGrp")

        if any(g.get("type") in ("tense", "person", "mood") for g in grams):
            grp.append(ET.Element("gram", {
                "type": "pos",
                "value": "verb"
            }))

        for g in grams:
            grp.append(g)

        return grp
    
    def inflect_var(self, children):
        """
        Build one <form type="inflected"> per infgramgrp + INFVARIANT pair.

        Handles:
          ds. (EWS) mēda
          nap. mǣd(w)a, mǣdwe
          partial forms such as -da
        """
        pairs = []
        current_grp = None
        current_qualifiers = []

        def walk(obj):
            nonlocal current_grp, current_qualifiers

            if isinstance(obj, ET.Element):
                if obj.tag == "gramGrp":
                    current_grp = obj
                    current_qualifiers = []
                elif obj.tag in ("pc", "usg", "lbl", "bibl"):
                    current_qualifiers.append(obj)

            elif isinstance(obj, dict) and "_infvariant" in obj:
                pairs.append((
                    current_grp,
                    list(current_qualifiers),
                    obj["_infvariant"]
                ))
                current_grp = None
                current_qualifiers = []

            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        if not pairs:
            return None

        result = []

        for grp, qualifiers, raw_variant in pairs:
            f = ET.Element("form", {"type": "inflected"})

            if grp is not None:
                for q in qualifiers:
                    if q.tag in ("pc", "usg", "lbl"):
                        grp.append(q)

                f.append(grp)

            elif any(q.tag in ("pc", "usg", "lbl") for q in qualifiers):
                grp = ET.Element("gramGrp")

                for q in qualifiers:
                    if q.tag in ("pc", "usg", "lbl"):
                        grp.append(q)

                f.append(grp)

            for q in qualifiers:
                if q.tag == "bibl":
                    f.append(q)

            for orth in self._make_inflected_orths(raw_variant):
                f.append(orth)

            result.append({"_inflected_form": f})

        return result
    
    def tense(self, children):
        """
        e.g. 'pres.' -> <gram type="tense" value="present">pres.</gram>
            'pret.' -> <gram type="tense" value="preterite">pret.</gram>
        """
        t = "".join(str(c) for c in children).strip()
        m = {
            "pres.": "present",
            "pret.": "preterite",
            "past": "past",
            "fut.": "future",
        }
        val = m.get(t.lower(), t.rstrip(".").lower())
        g = ET.Element("gram", {"type": "tense", "value": val})
        g.text = t
        return g

    def person(self, children):
        """
        e.g. '3' -> <gram type="person" value="third">3</gram>
        """
        t = "".join(str(c) for c in children).strip()
        pmap = {"1": "first", "2": "second", "3": "third"}
        val = pmap.get(t, t)
        g = ET.Element("gram", {"type": "person", "value": val})
        g.text = t
        return g

    def number(self, children):
        """
        Normalize number tokens to TEI values.
        Accepts: 'sg.', 's.', 'sing.', 'pl.', 'p.', 'sg', 'pl', 's', 'p'
        → value='singular' / 'plural'
        """
        t = "".join(str(c) for c in children).strip()
        t_clean = t.rstrip(",").strip()
        k = t_clean.lower()

        mapping = {
            "sg.": "singular", "sg": "singular", "s.": "singular", "s": "singular", "sing.": "singular",
            "pl.": "plural",   "pl": "plural",   "p.": "plural",   "p": "plural",   "sbpl.": "plural",
        }
        val = mapping.get(k)
        if val is None:
            # Fallbacks: strip a trailing dot and try again
            k2 = k.rstrip(".")
            val = mapping.get(k2, k2)  # last resort: pass through cleaned token

        g = ET.Element("gram", {"type": "number", "value": val})
        g.text = t_clean
        return g

    
    def spell_var(self, children):
        """
        SPELLVAR token looks like "(eo^1, o^1; æ^2; æ^3)" or "(i, y)" etc.

        produce separate nested variant forms. Parentheses are <pc>.
        """
        if not children:
            return None

        raw = str(children[0]).strip()
        inner = raw[1:-1] if raw.startswith("(") and raw.endswith(")") else raw

        # If it looks like a full word variant, treat it as orth_variant-like.
        # Use <pc> instead of f.text / orth.tail.
        if self._is_likely_orth_variant(inner):
            f = ET.Element("form", {"type": "variant"})

            if raw.startswith("(") and raw.endswith(")"):
                f.append(self._pc("("))
                orth = self._make_full_orth(inner, None)
                f.append(orth)
                f.append(self._pc(")"))
            else:
                orth = self._make_full_orth(inner, None)
                f.append(orth)

            return {"_nested_variant": f}

        # Split items, keeping separators.
        items = []
        for m in re.finditer(r"\s*([^,;]+?)\s*([,;]|$)", inner):
            item = m.group(1).strip()
            sep = m.group(2)
            if item:
                items.append((item, sep))

        variants = []

        for idx, (item, sep) in enumerate(items):
            m = re.match(r"^(.+?)(?:\^(\d+))?$", item)
            letters = (m.group(1) or "").strip() if m else item.strip()
            sup = m.group(2) if m else None
            slot = int(sup) if sup else 1

            expanded_forms = []

            if self._is_pure_vowel_string(letters):
                base_for_expansion = self._last_orth_base or self._lemma
                base_expanded = self._replace_nth_vowel(
                    base_for_expansion,
                    letters,
                    slot
                )

                if self._prefix == "±":
                    expanded_forms = [base_expanded, f"ge-{base_expanded}"]
                elif self._prefix == "+":
                    expanded_forms = [f"ge-{base_expanded}"]
                else:
                    expanded_forms = [base_expanded]

            f = ET.Element("form", {"type": "variant"})
            orth_attrs = {"extent": "part"}

            if expanded_forms:
                orth_attrs["expand"] = ", ".join(expanded_forms)

            orth = ET.SubElement(f, "orth", orth_attrs)

            # Opening parenthesis as <pc> only in the first variant.
            if idx == 0 and raw.startswith("("):
                orth.append(self._pc("("))

            # Main visible spelling segment.
            seg = ET.SubElement(orth, "seg")

            # If no superscript, punctuation can safely stay inside <seg>.
            if not sup:
                seg.text = letters
                if idx < len(items) - 1:
                    seg.text += sep if sep else ","
            else:
                seg.text = letters
                lbl = ET.SubElement(orth, "lbl", {"rend": "sup"})
                lbl.text = sup

                # Keep comma/semicolon in its own <seg>, avoiding lbl.tail.
                if idx < len(items) - 1:
                    punct = ET.SubElement(orth, "seg")
                    punct.text = sep if sep else ","

            # Closing parenthesis as <pc> only in the final variant.
            if idx == len(items) - 1 and raw.endswith(")"):
                orth.append(self._pc(")"))

            variants.append(f)

        return [{"_nested_variant": vf} for vf in variants] if variants else None
    
    def orth_variant(self, children):
        """
        Handles ordinary orthographic variants and parenthesized variants,
        including cases like:
          āfrēon (-ia, N)
        """
        sep_symbol = None
        in_parens = False
        local_prefix = None
        variants = []
        qualifiers = []

        def walk(obj):
            nonlocal sep_symbol, in_parens, local_prefix

            if isinstance(obj, Token):
                s = str(obj).strip()

                if obj.type == "LP" or s.startswith("("):
                    in_parens = True
                elif s.startswith(","):
                    sep_symbol = ","
                elif s == "-":
                    sep_symbol = "-"
                elif obj.type == "VARIANT":
                    variants.append(s)
                elif obj.type == "GE_PREF":
                    local_prefix = "+"
                elif obj.type == "GE_OPT":
                    local_prefix = "±"

            elif isinstance(obj, str):
                s = obj.strip()

                if s == "-":
                    sep_symbol = "-"
                elif s.startswith(","):
                    sep_symbol = ","

            elif isinstance(obj, ET.Element):
                if obj.tag in ("bibl", "usg", "pc", "lbl"):
                    qualifiers.append(obj)

            elif isinstance(obj, Tree):
                for gc in obj.children:
                    walk(gc)

            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        cleaned = []

        for v in variants:
            for part in re.split(r",\s*", v):
                part = part.strip()
                part = re.sub(r"[;,]\s*$", "", part).strip()

                if part:
                    cleaned.append(part)
                    self._variants.append(part)

        variants = cleaned

        if variants:
            self._last_orth_base = variants[-1].strip(",;")

        effective_prefix = local_prefix if local_prefix else None
        out = []

        if sep_symbol == ",":
            out.append({"_lemma_punct": ","})

        if in_parens:
            if not variants:
                return None

            for i, vtxt in enumerate(variants):
                f = ET.Element("form", {"type": "variant"})

                if i == 0:
                    f.append(self._pc("("))

                orth = self._make_full_orth(vtxt, effective_prefix)
                f.append(orth)

                if i == len(variants) - 1:
                    for q in qualifiers:
                        f.append(q)
                    f.append(self._pc(")"))

                out.append({"_nested_variant": f})

            return out if out else None

        for vtxt in variants:
            f = ET.Element("form", {"type": "variant"})

            if sep_symbol == "-" or str(vtxt).strip().startswith("-"):
                orth = self._make_hyphen_split_variant_orth(vtxt)
            else:
                orth = self._make_full_orth(vtxt, effective_prefix)

            f.append(orth)
            out.append({"_nested_variant": f})

        return out if out else None

    def form(self, children):
        """
        Attaches following parenthesized geo/source material to the last form
        produced inside this form rule.

        Examples:
          meniu (LWS)
          wutum, wutun (N)
        """
        out = []
        last_form_el = None

        def attach_to_last_form(el):
            nonlocal last_form_el

            if (
                last_form_el is not None
                and isinstance(el, ET.Element)
                and el.tag in ("bibl", "usg", "pc", "lbl", "gramGrp")
            ):
                last_form_el.append(el)
                return True

            return False

        def take(obj):
            nonlocal last_form_el

            if isinstance(obj, dict) and "_nested_variant" in obj:
                last_form_el = obj["_nested_variant"]
                out.append(obj)

            elif isinstance(obj, dict) and "_inflected_form" in obj:
                last_form_el = obj["_inflected_form"]
                out.append(obj)

            elif isinstance(obj, ET.Element):
                if not attach_to_last_form(obj):
                    out.append(obj)

            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        return out if out else None
    
    def bibl(self, children):
        """
        Build ordinary bibliographic references, but convert closed-list
        dialect/variety labels such as K, EWS, LWS, M, N into <usg type="geo">.
        Also pass through material already produced by parenbibl().
        """
        src_items = []
        tail_num = None
        passthrough = []

        def walk(obj):
            nonlocal tail_num

            if isinstance(obj, dict) and "_src_code" in obj:
                src_items.append(obj)
            elif isinstance(obj, dict) and "_srcnum" in obj:
                tail_num = obj["_srcnum"]
            elif isinstance(obj, ET.Element) and obj.tag in ("bibl", "usg", "pc", "lbl", "gramGrp"):
                passthrough.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)


        for ch in children:
            walk(ch)

        out = list(passthrough)
        bibls = []

        if src_items:
            for s in src_items:
                code = s["_src_code"]

                # Dialect/variety label, not a bibliographic source.
                if self._is_geo_code(code) and tail_num is None:
                    out.append(self._make_geo_usg(code))
                    continue

                b = ET.Element("bibl", {
                    "type": "attestation",
                    "source": f"#{code}"
                })
                title = ET.SubElement(b, "title")
                title.text = s["_src_title"]

                bibls.append(b)
                out.append(b)

            if tail_num and bibls:
                src_code = bibls[-1].get("source", "").lstrip("#")
                for el in self._parse_source_numbers(tail_num, src_code=src_code):
                    bibls[-1].append(el)

        if not out:
            return None

        return out if len(out) > 1 else out[0]
    
    def parenbibl(self, children):
        """
        Parenthesized source-like material.

        (LWS), (EWS), (M), (N), (rare EWS)
          -> <pc>(</pc> + usage/geo + <pc>)</pc>

        (ES 43·309)
          -> ordinary <bibl>, without preserving parentheses.
        """
        src_items = []
        tail_num = None
        usage_labels = []
        passthrough = []

        def walk(obj):
            nonlocal tail_num

            if isinstance(obj, dict) and "_src_code" in obj:
                src_items.append(obj)
            elif isinstance(obj, dict) and "_srcnum" in obj:
                tail_num = obj["_srcnum"]
            elif isinstance(obj, dict) and obj.get("_usglbl"):
                usage_labels.append(obj["_usglbl"])
            elif isinstance(obj, ET.Element) and obj.tag in ("bibl", "usg", "pc", "lbl", "gramGrp"):
                passthrough.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        usage_elements = [
            self._make_usage_lbl(lbl)
            for lbl in usage_labels
            if lbl
        ]

        if src_items:
            all_geo = (
                tail_num is None
                and all(self._is_geo_code(s["_src_code"]) for s in src_items)
            )

            # (LWS), (rare EWS), etc.
            if all_geo:
                out = [self._pc("("), *usage_elements]

                for s in src_items:
                    out.append(self._make_geo_usg(s["_src_code"]))

                out.append(self._pc(")"))
                return out

            # Ordinary parenthesized bibl, e.g. (ES 43·309)
            bibls = []

            for s in src_items:
                code = s["_src_code"]
                b = ET.Element("bibl", {
                    "type": "attestation",
                    "source": f"#{code}"
                })
                title = ET.SubElement(b, "title")
                title.text = s["_src_title"]
                bibls.append(b)

            if tail_num and bibls:
                src_code = bibls[-1].get("source", "").lstrip("#")
                for el in self._parse_source_numbers(tail_num, src_code=src_code):
                    bibls[-1].append(el)

            return bibls if len(bibls) > 1 else bibls[0]

        if usage_elements:
            return [self._pc("("), *usage_elements, self._pc(")")]

        if passthrough:
            return passthrough if len(passthrough) > 1 else passthrough[0]

        return None
    
    def preceding_content(self, children):
        out = []
        for ch in children:
            if ch is None:
                continue
            if isinstance(ch, (list, tuple)):
                for z in ch:
                    if z is not None:
                        out.append(z)
            else:
                out.append(ch)
        return out if out else None

    def subsequent_content(self, children):
        out = []
        for ch in children:
            if ch is None:
                continue
            if isinstance(ch, (list, tuple)):
                for z in ch:
                    if z is not None:
                        out.append(z)
            else:
                out.append(ch)

        out = self._merge_adjacent_etym(out)
        return out if out else None

    def main_content(self, children):
        out = []
        for ch in children:
            if ch is None:
                continue
            if isinstance(ch, (list, tuple)):
                for z in ch:
                    if z is not None:
                        out.append(z)
            else:
                out.append(ch)
        return out if out else None
    
    def editorcomm(self, children):
        for ch in children:
            if isinstance(ch, ET.Element) and ch.tag == "note":
                return ch
            elif isinstance(ch, (list, tuple)):
                for z in ch:
                    if isinstance(z, ET.Element) and z.tag == "note":
                        return z
        return None
    
    def hom_entry(self, children):
        """
        <entry xml:id="LEMMA_n" type="homonymicEntry" xml:lang="ang" n="I">
        <lbl type="homNum">I.</lbl>
        ... (elements of this hom, in source order) ...
        </entry>
        """
        info = None
        items = []
        for ch in children:
            if isinstance(ch, dict) and "_n" in ch:
                info = ch
            elif isinstance(ch, (list, tuple)):
                items.extend(ch)
            elif ch is not None:
                items.append(ch)

        if info is None:
            return None

        lemma = self._lemma or "UNKNOWN"
        n = info["_n"]
        roman_text = info["_rom_text"].strip()
        roman_only = info["_roman"]

        hom_id = f"{lemma}_{n}"
        hom = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{hom_id}",
            "type": "homonymicEntry",
            f"{{{self.XML_NS}}}lang": "ang",
            "n": roman_only
        })
        ET.SubElement(hom, "lbl", {"type": "homNum"}).text = roman_text

        # sense-id rewriter 
        base = lemma
        old_prefix_bare = f"{base}."
        old_prefix_full = f"{self.DICT_PREFIX}.{base}."
        new_prefix_full = f"{self.DICT_PREFIX}.{base}_{n}."

        def _rewrite_ids(elem):
            if elem.tag == "sense":
                sid = elem.get(f"{{{self.XML_NS}}}id")
                if sid:
                    if sid.startswith(old_prefix_full):
                        elem.set(f"{{{self.XML_NS}}}id",
                                 sid.replace(old_prefix_full, new_prefix_full, 1))
                    elif sid.startswith(old_prefix_bare):
                        elem.set(f"{{{self.XML_NS}}}id",
                                 sid.replace(old_prefix_bare, new_prefix_full, 1))
            for child in list(elem):
                if isinstance(child, ET.Element):
                    _rewrite_ids(child)

        # Preserve original order of usg/gramGrp/sense; hold trailing '.' to end
        ordered = []
        trailing_dots = []

        def _ordered_collect(obj):
            if isinstance(obj, dict):
                return  # skip payload dicts (_inflected_form, _nested_variant etc.)
            if isinstance(obj, ET.Element):
                if obj.tag in ("usg", "gramGrp", "xr", "sense", "metamark", "form", "etym", "note"):
                    ordered.append(obj)
                elif obj.tag == "entry" and obj.get("type") == "relatedEntry":
                    ordered.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _ordered_collect(z)

        for it in items:
            _ordered_collect(it)

        pending_dots = []

        for e in ordered:
            if e.tag == "metamark" and (e.text or "").strip() == ".":
                pending_dots.append(e)
                continue

            # If something comes after a full stop, the dot was not truly final.
            # Flush it before appending the next element.
            for d in pending_dots:
                hom.append(d)
            pending_dots = []

            if e.tag == "sense":
                _rewrite_ids(e)

            hom.append(e)

        # Only dots that really occur at the end stay at the end.
        for d in pending_dots:
            hom.append(d) 

        return hom

    def usage(self, children):
        """
        Handles cases such as:
        (only in pl.)
        (usu. pl.)
        (wið)
        (w. æt)

        Output is:
        <pc>(</pc>
        <gramGrp>
            <lbl type="usage" ...>...</lbl>
            <gram type="construction" ...>...</gram>
        </gramGrp>
        <pc>)</pc>
        """
        has_lp = False
        has_rp = False
        labels = []
        grams_or_words = []

        def take(obj):
            nonlocal has_lp, has_rp

            if isinstance(obj, Token):
                if obj.type == "LP":
                    has_lp = True
                elif obj.type == "RP":
                    has_rp = True
                elif obj.type in ("USGPREP", "USG_WORD"):
                    txt = str(obj).strip().rstrip(",;")
                    grams_or_words.append(self._make_construction_gram(txt))
                elif obj.type == "COMMA":
                    pass

            elif isinstance(obj, dict) and obj.get("_usglbl"):
                labels.append(obj["_usglbl"])

            elif isinstance(obj, ET.Element):
                if obj.tag == "gramGrp":
                    for child in list(obj):
                        if child.tag == "gram":
                            grams_or_words.append(self._as_construction_gram(child))
                        elif child.tag == "lbl":
                            grams_or_words.append(child)
                elif obj.tag == "gram":
                    grams_or_words.append(self._as_construction_gram(obj))
                elif obj.tag == "lbl":
                    grams_or_words.append(obj)

            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        grp = ET.Element("gramGrp")

        for label in labels:
            grp.append(self._make_usage_lbl(label))

        for item in grams_or_words:
            grp.append(item)

        if not list(grp):
            return None

        out = []
        if has_lp:
            out.append(self._pc("("))
        out.append(grp)
        if has_rp:
            out.append(self._pc(")"))

        return out
    
    def construction(self, children):
        """
        Handles constructions such as:
        (w. d.)
        w. d.
        w. d. and a.

        Output:
        optional <pc>(</pc>
        <gramGrp>
            <lbl type="usage" norm="with">w.</lbl>
            <gram type="construction" value="dative">d.</gram>
            <lbl>and</lbl>
            <gram type="construction" value="accusative">a.</gram>
        </gramGrp>
        optional <pc>)</pc>
        """
        has_lp = False
        has_rp = False
        items = []

        def take(obj):
            nonlocal has_lp, has_rp

            if isinstance(obj, Token):
                if obj.type == "LP":
                    has_lp = True
                elif obj.type == "RP":
                    has_rp = True
                elif obj.type == "LBL":
                    items.append(self._make_plain_lbl(str(obj).strip()))
                elif obj.type == "CASE":
                    case_gram = self._make_case_gram(str(obj))
                    items.append(self._as_construction_gram(case_gram))
                elif obj.type in ("WORD", "USG_WORD", "USGPREP"):
                    items.append(self._make_construction_gram(str(obj).strip()))
                elif obj.type == "COMMA":
                    pass

            elif isinstance(obj, dict) and obj.get("_usglbl"):
                items.append(self._make_usage_lbl(obj["_usglbl"]))

            elif isinstance(obj, ET.Element):
                if obj.tag == "gram":
                    items.append(self._as_construction_gram(obj))
                elif obj.tag == "lbl":
                    items.append(obj)
                elif obj.tag == "gramGrp":
                    for child in list(obj):
                        if child.tag == "gram":
                            items.append(self._as_construction_gram(child))
                        elif child.tag == "lbl":
                            items.append(child)

            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        grp = ET.Element("gramGrp")
        for item in items:
            grp.append(item)

        if not list(grp):
            return None

        out = []
        if has_lp:
            out.append(self._pc("("))
        out.append(grp)
        if has_rp:
            out.append(self._pc(")"))

        return out

    def quote(self, children):
        out = []
        buf = []

        allowed = ("quote", "gloss", "pc", "gramGrp", "lbl")

        def flush_buf():
            if buf:
                q = ET.Element("quote")
                q.text = " ".join(buf).strip()
                if q.text:
                    out.append(q)
                buf.clear()

        def take(obj):
            if isinstance(obj, str):
                buf.append(obj)
            elif isinstance(obj, ET.Element) and obj.tag in allowed:
                flush_buf()
                out.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        flush_buf()
        if not out:
            return None
        return out if len(out) > 1 else out[0]

    def cit(self, children):
        """
        cit: ... quote ... (qm? bibl | parenbibl)*

        Preserves:
        <quote>, <gloss>, <pc>, <gramGrp>, <lbl>, <bibl>
        """
        cit_el = ET.Element("cit", {
            "type": "translationEquivalent",
            f"{{{self.XML_NS}}}lang": "en"
        })

        elements = []
        qm_here = False
        allowed = ("quote", "gloss", "pc", "gramGrp", "lbl", "bibl")

        def take(obj):
            nonlocal qm_here
            if isinstance(obj, dict) and obj.get("_qm"):
                qm_here = True
            elif isinstance(obj, ET.Element) and obj.tag in allowed:
                elements.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        if qm_here:
            note = ET.Element("note", {"cert": "low", "resp": "author"})
            note.text = "?"
            first_bibl_idx = next((i for i, e in enumerate(elements) if e.tag == "bibl"), None)
            if first_bibl_idx is None:
                elements.append(note)
            else:
                elements.insert(first_bibl_idx, note)

        for el in elements:
            cit_el.append(el)

        return cit_el if list(cit_el) else None


    def firstsense(self, children):
        """
        Return elements that may appear inside a sense:
        usage/construction material, citations, etymologies, cross-references,
        and metamarks.
        """
        out = []
        allowed = ("cit", "metamark", "pc", "gramGrp", "lbl", "etym", "xr", "note", "usg")

        def take(obj):
            if isinstance(obj, ET.Element) and obj.tag in allowed:
                out.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        return out

    def othersenses(self, children):
        return self.firstsense(children)

    def sense_section(self, children):
        """
        Build senses while preserving usage/construction material.
        """
        seq = []
        allowed = ("cit", "metamark", "pc", "gramGrp", "lbl", "etym", "xr", "note", "usg")

        def take(obj):
            if isinstance(obj, ET.Element) and obj.tag in allowed:
                seq.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        chunks, current, seps = [], [], []
        trailing_dot = False

        for node in seq:
            if node.tag == "metamark":
                sym = (node.text or "").strip()
                if sym in (":", ";"):
                    chunks.append(current[:])
                    seps.append(sym)
                    current.clear()
                elif sym == ".":
                    trailing_dot = True
            else:
                current.append(node)

        if current:
            chunks.append(current[:])

        base = self._lemma or "UNKNOWN"

        def _dot_meta():
            m = ET.Element("metamark")
            m.text = "."
            return m

        # single sense
        if len(chunks) <= 1:
            sense = ET.Element("sense", {
                f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base}.1"
            })
            for node in (chunks[0] if chunks else []):
                if isinstance(node, ET.Element):
                    sense.append(node)
            return [sense, _dot_meta()] if trailing_dot else sense

        # multiple subsenses
        wrapper = ET.Element("sense", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base}.1"
        })

        for i, nodes in enumerate(chunks, start=1):
            inner = ET.Element("sense", {
                f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{base}.1.{i}"
            })

            for node in nodes:
                if isinstance(node, ET.Element):
                    inner.append(node)

            wrapper.append(inner)

            if i < len(chunks):
                sep = seps[i - 1] if i - 1 < len(seps) else ":"
                m = ET.Element("metamark", {"function": "senseSeparator"})
                m.text = sep
                wrapper.append(m)

        return [wrapper, _dot_meta()] if trailing_dot else wrapper
    
    def reflbl(self, children):
        # Build <lbl> from the REFLBL token text
        txt = ""
        for ch in children:
            if isinstance(ch, str):
                txt = ch
                break
        if not txt:
            return None
        el = ET.Element("lbl")
        el.text = txt
        return el
    
    def refword(self, children):
       
        ref_txt = ""
        for ch in children:
            if isinstance(ch, str):
                ref_txt = ch
                break
        if not ref_txt:
            return None

        wclean = re.sub(r'[.,;:)]+$', '', ref_txt.strip())

        ref = ET.Element("ref", {"target": f"#{self.DICT_PREFIX}.{wclean}", "type": "entry"})
        ref.text = wclean
        return ref
    
    def simple_xr(self, children):
        """
        simple_xr: ... reflbl (refword | refwords) ...
        For now we only use reflbl + the first refword.
        """
        xr = ET.Element("xr", {"type": "related", "expand": "orthographic variant"})
        lbl_el, ref_el = None, None

        def pick(el):
            nonlocal lbl_el, ref_el
            if isinstance(el, ET.Element):
                if el.tag == "lbl" and lbl_el is None:
                    lbl_el = el
                elif el.tag == "ref" and ref_el is None:
                    ref_el = el
            elif isinstance(el, (list, tuple)):
                for z in el:
                    pick(z)

        for ch in children:
            pick(ch)

        if lbl_el is not None:
            xr.append(lbl_el)
        if ref_el is not None:
            xr.append(ref_el)

        return xr if list(xr) else None
    
    def xr_section(self, children):
        """
        Grammar: usglbl? parenbibl? infgramgrp OF refword parenxr? ( ... )? '.'?
        Build the inflected-form cross-ref:
        <gramGrp>...</gramGrp>
        <xr type="related" expand="inflected form">
            <lbl>of</lbl>
            <ref target="#...">...</ref>
        </xr>
        Return [gramGrp, xr] in source order.
        """
        gramgrp = None
        ref_el = None
        ordered = []

        def take(el):
            nonlocal gramgrp, ref_el
            if isinstance(el, ET.Element):
                if el.tag == "gramGrp":
                    gramgrp = el
                    ordered.append(el)
                elif el.tag == "ref":
                    ref_el = el
            elif isinstance(el, (list, tuple)):
                for z in el:
                    take(z)

        for ch in children:
            take(ch)

        xr = None
        if ref_el is not None:
            xr = ET.Element("xr", {"type": "related", "expand": "inflected form"})
            ET.SubElement(xr, "lbl").text = "of"  # OF token; always 'of' here
            xr.append(ref_el)
            ordered.append(xr)

        return ordered if ordered else None
    
    def adv_word(self, children):
        """
        Grammar yields: 'adv.' then a WORD like '-līce', possibly commas, bibl, and/or a sense_section.
        We turn it into a payload dict so relatedentry() can build the related entry.
        """
        suffix = None
        payload_children = []  # senses/bibl/metamark collected inside adv_word

        def take(obj):
            nonlocal suffix
            if isinstance(obj, Token):                 
                s = str(obj).strip()
                if s.startswith("-") and "līce" in s:
                    suffix = s
            elif isinstance(obj, str):                 
                s = obj.strip()
                if s.startswith("-") and "līce" in s:
                    suffix = s
            elif isinstance(obj, ET.Element):
                if obj.tag in ("sense", "bibl", "metamark"):
                    payload_children.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    take(z)

        for ch in children:
            take(ch)

        if not suffix:
            suffix = "-līce"

        return {"_related_type": "adv_lice", "suffix": suffix, "content": payload_children}

    
    def collocation(self, children):
        """
        Build a simple payload we can read in relatedentry().
        We expect exactly one COLLOC token string here.
        """
        text = ""
        for ch in children:
            if isinstance(ch, str) and ch:
                text = ch
                break
        if not text:
            return None
        return {"_related_type": "collocation", "text": text}

    def oneword(self, children):
        """
        ONEWORD may include a leading '+' or '±' that the grammar doesn't split.
        We detect it here and strip it from the surface, returning the symbol.
        """
        word = ""
        for ch in children:
            if isinstance(ch, str) and ch:
                word = ch.strip()
                break
        if not word:
            return None

        prefix = None
        if word.startswith("±"):
            prefix, word = "±", word[1:].strip()
        elif word.startswith("+"):
            prefix, word = "+", word[1:].strip()

        return {"_related_type": "oneword", "text": word, "prefix": prefix}
    
    def relatedentry(self, children):
        """
        Related entries can be built from:
        - collocation-like multiword payloads, encoded as relatedEntry + form type="lemma"
          with one combined <orth> and an mwe gram;
        - one-word related entries;
        - adverbial -līce related entries.

        For multiword related entries, abbreviated references to the current lemma
        are encoded as:
          <ref type="form" scope="currentEntry" value="LEMMA">f.</ref>
        """
        # ---- find the payload (collocation or oneword) ----
        payload = None
        rest = []  # other children (e.g., sense_section)
        for ch in children:
            if isinstance(ch, dict) and ch.get("_related_type") in ("collocation", "oneword", "adv_lice"):
                payload = ch
            else:
                rest.append(ch)

        if not payload:
            return None

        main_base = self._lemma or "UNKNOWN"

        # --------------------------------------------------------------------
        # Adverb-in -līce branch (from adv_word)
        # --------------------------------------------------------------------
        if payload["_related_type"] == "adv_lice":
            sfx = payload.get("suffix") or "-līce"
            base = self._lemma or "UNKNOWN"
            expanded = self._expand_adv_lice(base)  # compute xml:id and orth@expand

            rel = ET.Element("entry", {
                f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{expanded}",
                "type": "relatedEntry",
                f"{{{self.XML_NS}}}lang": "ang",
            })

            # The source marks this related form as an adverb: adv. -līce
            ggr = ET.SubElement(rel, "gramGrp")
            g = ET.SubElement(ggr, "gram", {"type": "pos", "value": "adverb"})
            g.text = "adv."

            # Lemma form with part-orth and seg '-līce', expand to the full adverb
            f = ET.SubElement(rel, "form", {"type": "lemma"})
            orth = ET.SubElement(f, "orth", {"extent": "part", "expand": expanded})
            ET.SubElement(orth, "seg").text = sfx 

            # --- rewrite sense ids from lemma-based -> related-entry-based ---
            content = list(payload.get("content", []))
            old_prefix_full = f"{self.DICT_PREFIX}.{base}."
            old_prefix_bare = f"{base}."
            new_prefix_full = f"{self.DICT_PREFIX}.{expanded}."

            def _rewrite_ids(elem):
                if isinstance(elem, ET.Element):
                    if elem.tag == "sense":
                        sid = elem.get(f"{{{self.XML_NS}}}id")
                        if sid:
                            if sid.startswith(old_prefix_full):
                                elem.set(f"{{{self.XML_NS}}}id",
                                         sid.replace(old_prefix_full, new_prefix_full, 1))
                            elif sid.startswith(old_prefix_bare):
                                elem.set(f"{{{self.XML_NS}}}id",
                                         sid.replace(old_prefix_bare, new_prefix_full, 1))
                    for c in list(elem):
                        _rewrite_ids(c)

            for node in content:
                _rewrite_ids(node)
                rel.append(node)

            def _collect_adv_editor_notes(obj):
                if isinstance(obj, ET.Element) and obj.tag == "note":
                    rel.append(obj)
                elif isinstance(obj, (list, tuple)):
                    for z in obj:
                        _collect_adv_editor_notes(z)

            for piece in rest:
                _collect_adv_editor_notes(piece)

            return rel

        # --------------------------------------------------------------------
        # Multiword related-entry branch
        # --------------------------------------------------------------------
        if payload["_related_type"] == "collocation":
            coll_txt = payload["text"]
            tokens = coll_txt.split()

            # ----- xml:id (prefix-normalized, abbrev-aware) -----
            id_parts = [self._token_to_id_part(t) for t in tokens]
            rel_id = "_".join(p for p in id_parts if p)

            rel = ET.Element("entry", {
                f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{rel_id}",
                "type": "relatedEntry",
                f"{{{self.XML_NS}}}lang": "ang",
            })

            # Lex-0-oriented treatment:
            # this is an entry-like multiword lexical item, so use lemma form,
            # not <form type="collocation">.
            f = ET.SubElement(rel, "form", {"type": "lemma"})
            orth = ET.SubElement(f, "orth")

            for i, t in enumerate(tokens):
                token_prefix = None

                if t and t[0] in ("+", "±"):
                    token_prefix = t[0]
                    core = t[1:].strip()
                else:
                    core = t

                visible = f"{token_prefix or ''}{core}"

                # Abbreviation of the current lemma, e.g. f. for foreweard.
                if self._is_abbrev_of_lemma(core):
                    base_word = self._lemma or core.rstrip(".")

                    if token_prefix == "+":
                        value = f"ge-{base_word}"
                    elif token_prefix == "±":
                        value = f"{base_word}, ge-{base_word}"
                    else:
                        value = base_word

                    if i > 0:
                        ET.SubElement(orth, "seg").text = " "

                    ref = ET.SubElement(orth, "ref", {
                        "type": "form",
                        "scope": "currentEntry",
                        "value": value
                    })
                    ref.text = visible

                # Ordinary non-abbreviated token.
                else:
                    seg = ET.SubElement(orth, "seg")
                    seg.text = visible if i == 0 else f" {visible}"

            # Mark this as a multiword expression / fixed combination.
            # "fixed_combination" is preferable to the Portuguese example value
            # "combinatória_fixa".
            ggr = ET.SubElement(rel, "gramGrp")
            ET.SubElement(ggr, "gram", {
                "type": "mwe",
                "value": "fixed_combination"
            })

            # ---- collect senses/metamarks, then rewrite ids ----
            ordered = []
            trailing_dots = []

            def _collect(obj):
                if isinstance(obj, ET.Element):
                    if obj.tag in ("form", "usg", "gramGrp", "sense", "metamark", "etym", "xr", "note"):
                        ordered.append(obj)
                elif isinstance(obj, (list, tuple)):
                    for z in obj:
                        _collect(z)

            for piece in rest:
                _collect(piece)

            old_prefix_bare = f"{main_base}."
            old_prefix_full = f"{self.DICT_PREFIX}.{main_base}."
            new_prefix_full = f"{self.DICT_PREFIX}.{rel_id}."

            def _rewrite_ids(elem):
                if elem.tag == "sense":
                    sid = elem.get(f"{{{self.XML_NS}}}id")
                    if sid:
                        if sid.startswith(old_prefix_full):
                            elem.set(f"{{{self.XML_NS}}}id",
                                     sid.replace(old_prefix_full, new_prefix_full, 1))
                        elif sid.startswith(old_prefix_bare):
                            elem.set(f"{{{self.XML_NS}}}id",
                                     sid.replace(old_prefix_bare, new_prefix_full, 1))

                for c in list(elem):
                    if isinstance(c, ET.Element):
                        _rewrite_ids(c)

            for e in ordered:
                if e.tag == "metamark" and (e.text or "").strip() == ".":
                    trailing_dots.append(e)
                    continue

                if e.tag == "sense":
                    _rewrite_ids(e)

                rel.append(e)

            for d in trailing_dots:
                rel.append(d)

            return rel

        # --------------------------------------------------------------------
        # Oneword branch
        # --------------------------------------------------------------------
        word = payload["text"]  # already stripped of any prefix by the collector

        if payload.get("prefix") == "+":
            rel_id = f"ge-{word}"
        else:
            rel_id = word

        rel = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{rel_id}",
            "type": "relatedEntry",
            f"{{{self.XML_NS}}}lang": "ang",
        })

        f = ET.SubElement(rel, "form", {"type": "lemma"})
        if payload.get("prefix") == "+":
            orth = ET.SubElement(f, "orth", {"extent": "prefix", "expand": f"ge-{word}"})
            ET.SubElement(orth, "lbl", {"expand": "ge-"}).text = "+"
            ET.SubElement(orth, "seg").text = word
        elif payload.get("prefix") == "±":
            orth = ET.SubElement(f, "orth", {"extent": "prefix", "expand": f"{word}, ge-{word}"})
            ET.SubElement(orth, "lbl", {"expand": "ge-_optional"}).text = "±"
            ET.SubElement(orth, "seg").text = word
        else:
            orth = ET.SubElement(f, "orth")
            orth.text = word

        # collect senses etc. and rewrite ids to use rel_id
        ordered = []
        trailing_dots = []

        def _collect2(obj):
            if isinstance(obj, ET.Element):
                if obj.tag in ("form", "usg", "gramGrp", "sense", "metamark", "etym", "xr", "note"):
                    ordered.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect2(z)

        for piece in rest:
            _collect2(piece)

        old_prefix_bare = f"{main_base}."
        old_prefix_full = f"{self.DICT_PREFIX}.{main_base}."
        new_prefix_full = f"{self.DICT_PREFIX}.{rel_id}."

        def _rewrite_ids2(elem):
            if elem.tag == "sense":
                sid = elem.get(f"{{{self.XML_NS}}}id")
                if sid:
                    if sid.startswith(old_prefix_full):
                        elem.set(f"{{{self.XML_NS}}}id",
                                 sid.replace(old_prefix_full, new_prefix_full, 1))
                    elif sid.startswith(old_prefix_bare):
                        elem.set(f"{{{self.XML_NS}}}id",
                                 sid.replace(old_prefix_bare, new_prefix_full, 1))
            for c in list(elem):
                if isinstance(c, ET.Element):
                    _rewrite_ids2(c)

        for e in ordered:
            if e.tag == "metamark" and (e.text or "").strip() == ".":
                trailing_dots.append(e)
                continue
            if e.tag == "sense":
                _rewrite_ids2(e)
            rel.append(e)

        for d in trailing_dots:
            rel.append(d)

        return rel
    
        # --------------------------------------------------------------------
        # etym
        # --------------------------------------------------------------------

    def vide(self, children):
        return {"_etym_label": True, "text": "v.", "norm": "vide"}

    def compare(self, children):
        return {"_etym_label": True, "text": "cp.", "norm": "compare"}

    def oldengword(self, children):
        """
        oldengword: WORD ROM_NUM? (bibl|parenbibl)? (COLON_SEP | SEMICOL_SEP)? COMMA?

        For etymological square brackets, we only use:
        - WORD
        - possible :, ;, ,
        """
        word = None
        punct = ""

        def walk(obj):
            nonlocal word, punct

            if isinstance(obj, Token):
                if obj.type == "WORD" and word is None:
                    word = str(obj).strip()
                elif obj.type == "COMMA":
                    punct += ","
            elif isinstance(obj, ET.Element) and obj.tag == "metamark":
                # Convert sense-separator metamarks to plain punctuation for etym.
                punct += obj.text or ""
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        if not word:
            return None

        return {
            "_oldengword": True,
            "word": word,
            "punct": punct
        }

    def oedref(self, children):
        raw = ""
        for ch in children:
            if isinstance(ch, Token):
                raw = str(ch)
                break
            elif isinstance(ch, str):
                raw = ch
                break

        if not raw:
            return None

        raw = raw.strip()

        # OEDREF can absorb final punctuation, especially ';' in cases like:
        # ['_cheap_'; _Ger._ kaufen]
        punct = ""
        if re.search(r";\s*$", raw):
            punct = ";"
        elif re.search(r",\s*$", raw):
            punct = ","
        elif re.search(r"\.\s*$", raw):
            punct = "."

        return {
            "_oedref": True,
            "text": raw,
            "punct": punct
        }

    def langword(self, children):
        """
        langword:
            LANG (WORD | COMMA WORD)+ SEMICOL_SEP?
          | LANG SEMICOL_SEP?
          | lbl LANG

        Returns one payload, which etym() converts to one <cit>.
        """
        lang = None
        forms = []
        labels = []
        tail = ""

        def walk(obj):
            nonlocal lang, tail

            if isinstance(obj, dict) and obj.get("_lang"):
                lang = obj
            elif isinstance(obj, Token):
                if obj.type == "WORD":
                    forms.append(str(obj).strip())
                elif obj.type == "LBL":
                    labels.append(str(obj).strip())
                elif obj.type == "COMMA":
                    # Comma separates multiple forms. We do not encode it separately for now.
                    pass
            elif isinstance(obj, ET.Element) and obj.tag == "metamark":
                if (obj.text or "").strip() == ";":
                    tail += ";"
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        if lang is None:
            return None

        return {
            "_langword": True,
            "lang": lang,
            "forms": forms,
            "labels": labels,
            "tail": tail
        }

    def biblref(self, children):
        """
        For now only handle simple cases like:
            (v. SRC)
            v. SRC

        Output:
        <xr type="related">
          <lbl norm="vide">v.</lbl>
          <ref type="bibl" target="#SRC">SRC</ref>
        </xr>
        """
        label_info = None
        bibl_el = None

        def walk(obj):
            nonlocal label_info, bibl_el

            if isinstance(obj, dict) and obj.get("_etym_label"):
                label_info = obj
            elif isinstance(obj, ET.Element) and obj.tag == "bibl" and bibl_el is None:
                bibl_el = obj
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    walk(z)

        for ch in children:
            walk(ch)

        if bibl_el is None:
            return None

        xr = ET.Element("xr", {"type": "related"})

        if label_info is not None:
            xr.append(self._make_etym_lbl(label_info))

        target = bibl_el.get("source")
        ref_attrs = {"type": "bibl"}
        if target:
            ref_attrs["target"] = target

        ref = ET.SubElement(xr, "ref", ref_attrs)
        ref.text = "".join(bibl_el.itertext()).strip()

        return xr
    
    def etym(self, children):
        """
        Build one <etym> for everything inside square brackets.

        Brackets are encoded as <pc>[</pc> and <pc>]</pc>, not as raw
        mixed-content text. This keeps indentation stable.
        """
        etym_el = ET.Element("etym")
        etym_el.append(self._pc("["))

        pending_label = None

        def flat(seq):
            for obj in seq:
                if obj is None:
                    continue
                if isinstance(obj, (list, tuple)):
                    yield from flat(obj)
                else:
                    yield obj

        for ch in flat(children):
            # Ignore literal square brackets if !etym keeps them in the tree.
            if isinstance(ch, Token) and str(ch) in ("[", "]"):
                continue
            if isinstance(ch, str) and ch.strip() in ("[", "]"):
                continue

            # v. / cp. label: apply to the next xr/cit.
            if isinstance(ch, dict) and ch.get("_etym_label"):
                pending_label = ch
                continue

            # ? inside etymology.
            if isinstance(ch, dict) and ch.get("_qm"):
                note = ET.Element("note", {"cert": "low", "resp": "author"})
                note.text = "?"
                self._append_etym_child(etym_el, note)
                continue

            # Old English internal reference.
            if isinstance(ch, dict) and ch.get("_oldengword"):
                xr = self._make_etym_xr(ch["word"], pending_label)
                self._append_etym_child(etym_el, xr, ch.get("punct", ""))
                pending_label = None
                continue

            if isinstance(ch, dict) and ch.get("_oedref"):
                xr = self._make_oed_xr(ch["text"], pending_label)
                self._append_etym_child(etym_el, xr, ch.get("punct", ""))
                pending_label = None
                continue

            # Language + word(s).
            if isinstance(ch, dict) and ch.get("_langword"):
                cit = self._make_lang_cit(ch, pending_label)
                self._append_etym_child(etym_el, cit, ch.get("tail", ""))
                pending_label = None
                continue

            # Simple biblref already transformed into <xr>.
            if isinstance(ch, ET.Element) and ch.tag in ("xr", "gramGrp", "bibl", "note"):
                self._append_etym_child(etym_el, ch)
                pending_label = None
                continue

        # If a dangling v./cp. was left, preserve it rather than dropping it.
        if pending_label is not None:
            self._append_etym_child(etym_el, self._make_etym_lbl(pending_label))

        etym_el.append(self._pc("]"))
        return etym_el

    # ---------------- build the entry ----------------
    def entry(self, children):
        lemma = self._lemma or "UNKNOWN"
        prefix = self._prefix
        has_qm = self._has_qm

        entry = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": f"{self.DICT_PREFIX}.{lemma}",
            "type": "mainEntry",
            f"{{{self.XML_NS}}}lang": "ang",
        })
        form = ET.SubElement(entry, "form", {"type": "lemma"})
        orth = ET.SubElement(form, "orth")

        if prefix == '+':
            orth.set("extent", "full")
            orth.set("expand", f"ge-{lemma}")
            lbl = ET.SubElement(orth, "lbl", {"expand": "ge-"})
            lbl.text = "+"
            ET.SubElement(orth, "seg").text = lemma
        elif prefix == '±':
            orth.set("extent", "full")
            orth.set("expand", f"{lemma}, ge-{lemma}")
            lbl = ET.SubElement(orth, "lbl", {"expand": "ge-_optional"})
            lbl.text = "±"
            ET.SubElement(orth, "seg").text = lemma
        else:
            orth.text = lemma

        # add a lemma-level note (...resp=author...) if the headword carried a qm
        headword_qm = False
        def detect_headword_qm(obj):
            nonlocal headword_qm
            if headword_qm:
                return
            if isinstance(obj, dict) and obj.get("_headword_qm"):
                headword_qm = True
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    detect_headword_qm(z)

        for ch in children:
            detect_headword_qm(ch)

        if headword_qm:
            ET.SubElement(form, "note", {"cert": "low", "resp": "author"}).text = "?"
        
        # Add headword-level bibl/usg material inside <form type="lemma">
        # Examples:
        #   hwu (LWS) = hū
        #   gief (rare EWS) = gif
        #   myce? (ES 43·309), mycel (LWS) = micel
        def _collect_lemma_extras(obj, acc):
            if isinstance(obj, dict) and "_lemma_extra" in obj:
                acc.extend(obj["_lemma_extra"])
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_lemma_extras(z, acc)

        lemma_extras = []
        for ch in children:
            _collect_lemma_extras(ch, lemma_extras)

        for el in lemma_extras:
            form.append(el)

        # Look for a request to add punctuation after the lemma orth (from orth_variant)
        lemma_punct = None
        def _find_punct(obj):
            nonlocal lemma_punct
            if lemma_punct:
                return
            if isinstance(obj, dict) and "_lemma_punct" in obj:
                lemma_punct = obj["_lemma_punct"]
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _find_punct(z)
        for ch in children:
            _find_punct(ch)

        if lemma_punct:
            orth.tail = (orth.tail or "") + lemma_punct

        # Collect _nested_variant payloads and append them inside <form type="lemma">
        def _collect_nested_variants(obj, acc):
            if isinstance(obj, dict) and "_nested_variant" in obj:
                acc.append(obj["_nested_variant"])
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_nested_variants(z, acc)

        nested_variants = []
        for ch in children:
            _collect_nested_variants(ch, nested_variants)
        for vf in nested_variants:
            form.append(vf)

        # Collect _inflected_form payloads (stored separately, appended AFTER gramGrp below)
        def _collect_inflected_forms(obj, acc):
            if isinstance(obj, dict) and "_inflected_form" in obj:
                acc.append(obj["_inflected_form"])
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_inflected_forms(z, acc)

        inflected_forms = []
        for ch in children:
            _collect_inflected_forms(ch, inflected_forms)

        # Append entry-level <usg> and <gramGrp> FIRST, then inflected forms
        post_form_ordered = []

        def _collect_post_form(obj):
            if isinstance(obj, dict) and "_inflected_form" in obj:
                return  # handled separately, skip here
            if isinstance(obj, dict) and "_nested_variant" in obj:
                return  # handled by _collect_nested_variants, skip here
            if isinstance(obj, dict) and "_lemma_extra" in obj:
                return  # handled inside lemma form
            if isinstance(obj, ET.Element):
                if obj.tag in ("form", "usg", "gramGrp", "xr"):
                    post_form_ordered.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_post_form(z)

        for ch in children:
            _collect_post_form(ch)

        for el in post_form_ordered:
            entry.append(el)

        # NOW append inflected forms, after gramGrp is already in place
        for inf_f in inflected_forms:
            entry.append(inf_f)

        # append any <sense> elements produced by sense_section()
        trailing_entry_dots = []

        def _collect(obj):
            if isinstance(obj, ET.Element):
                if obj.tag in ("sense", "etym"):
                    entry.append(obj)
                elif obj.tag == "metamark" and (obj.text or "").strip() == ".":
                    trailing_entry_dots.append(obj)  # place after all senses
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect(z)

        for ch in children:
            _collect(ch)
        
        for dot in trailing_entry_dots:
            entry.append(dot)

        def _collect_nested_entries(obj, acc):
            if isinstance(obj, ET.Element) and obj.tag == "entry":
                t = (obj.get("type") or "").strip()
                if t in ("homonymicEntry", "relatedEntry"):
                    acc.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_nested_entries(z, acc)

        nested_entries = []
        for ch in children:
            _collect_nested_entries(ch, nested_entries)

        for e in nested_entries:
            entry.append(e)

        # Append final editor comments, e.g.
        # [[headword spelled "anihst"]]
        # These should come after related/homonymic entries when present.
        editor_notes = []

        def _collect_editor_notes(obj, acc):
            if isinstance(obj, ET.Element) and obj.tag == "note":
                acc.append(obj)
            elif isinstance(obj, (list, tuple)):
                for z in obj:
                    _collect_editor_notes(z, acc)

        for ch in children:
            _collect_editor_notes(ch, editor_notes)

        for note in editor_notes:
            entry.append(note)


        # clear state for next entry
        self._lemma = None
        self._prefix = None
        self._has_qm = False
        self._variants = []
        self._last_orth_base = None

        # return pretty XML string
        rough = ET.tostring(entry, encoding="unicode")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", newl="\n")
        pretty = pretty.split('\n', 1)[1]
        return pretty.strip()

    def start(self, children):
        for ch in children:
            if isinstance(ch, str) and ch.strip().startswith("<entry"):
                return ch
        fallback = ET.Element("entry", {
            f"{{{self.XML_NS}}}id": "UNKNOWN",
            "type": "mainEntry",
            f"{{{self.XML_NS}}}lang": "ang",
        })
        pretty = minidom.parseString(ET.tostring(fallback, encoding="unicode")).toprettyxml(indent="  ", newl="\n")
        return pretty.split('\n', 1)[1].strip()


class DictionaryParser:
    """
   parser class for dictionary entries.
    """

    def __init__(self):
        try:
            self.parser = Lark(GRAMMAR, parser='earley', debug=False)
            self.transformer = DictionaryTransformer()
            print("Parser initialized successfully!")
        except Exception as e:
            print(f"Error initializing parser: {e}")
            self.parser = None
            self.transformer = None
    
    @staticmethod
    def _safe_comment_text(s: str) -> str:
        return (s or "").replace("--", "—")
    
    @staticmethod
    def _strip_ws(elem):

        if elem.text is not None and elem.text.strip() == "":
            elem.text = None
        for c in list(elem):
            DictionaryParser._strip_ws(c)
            if c.tail is not None and c.tail.strip() == "":
                c.tail = None

    def parse_text(self, text):
        """
        Parse dictionary entry text and return structured data.

        Args:
            text (str): Raw dictionary entry text

        Returns:
            dict: Parsed dictionary entry structure
        """
        if not self.parser:
            return {"error": "Parser not initialized"}

        try:
            # Clean and normalize text
            cleaned_text = (
                text
                .replace('\u00A0', ' ')  # Non-breaking space
                .replace('\u2018', "'")   # Left single quote
                .replace('\u2019', "'")   # Right single quote
                .replace('\u201C', '"')   # Left double quote
                .replace('\u201D', '"')   # Right double quote
                .replace('\n', ' ')       # Replace newlines with spaces
                .replace('\r', ' ')       # Replace carriage returns with spaces
            )
            
            # Normalize multiple spaces to single space
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            
            parse_tree = self.parser.parse(cleaned_text)


            if self.transformer:
                transformed_result = self.transformer.transform(parse_tree)
                return {
                    "success": True, 
                    "parse_tree": parse_tree,  
                    "transformed": transformed_result,
                    "cleaned_text": cleaned_text
                }
            else:
                return {
                    "success": True, 
                    "parse_tree": parse_tree,
                    "transformed": None,
                    "cleaned_text": cleaned_text
                }

        except ParseError as e:
            return {"success": False, "error": f"Parse error: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}

    def parse_dictionary_file(self, filename):
        """
        Parse the file containing any number of entries and create output files.
        
        Args:
            filename (str): Path to the dictionary file
            
        Returns:
            dict: Dictionary with parsing statistics
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            return {"error": f"File not found: {filename}"}
        except Exception as e:
            return {"error": f"Error reading file: {e}"}

        # Split entries by double newlines 
        entries = [entry.strip() for entry in content.split('\n\n') if entry.strip()]
        
        total_entries = len(entries)
        successful_parses = 0
        failed_entries = []
        
        # Write transformed XML and diagnostics to the repository data folders.
        # This assumes that the parser is stored in src/.
        repo_root = Path(__file__).resolve().parent.parent
        output_dir = repo_root / "data" / "output"
        diagnostics_dir = repo_root / "data" / "diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

        base_name = Path(filename).stem
        parse_trees_file = diagnostics_dir / f"{base_name}_parse_trees.txt"
        transformed_file = output_dir / f"{base_name}_transformed.xml"
        failed_file = diagnostics_dir / f"{base_name}_failed.txt"
        
        print(f"Processing {total_entries} entries...")
        print(f"Output files will be:")
        print(f"  - Parse trees: {parse_trees_file}")
        print(f"  - Transformed results: {transformed_file}")
        print(f"  - Failed entries: {failed_file}")
        
        # Process entries and collect results
        successful_results = []
        
        for i, entry in enumerate(entries):
            if i % 100 == 0:
                print(f"Processed {i}/{total_entries} entries")
                
            result = self.parse_text(entry)
            
            if result["success"]:
                successful_parses += 1
                successful_results.append({
                    "entry_number": i + 1,
                    "original_text": entry,
                    "cleaned_text": result.get("cleaned_text", ""),
                    "parse_tree": result["parse_tree"],
                    "transformed_result": result["transformed"]
                })
            else:
                failed_entries.append({
                    "entry_number": i + 1,
                    "entry_text": entry,
                    "error": result["error"],
                })
        
        # Calculate final statistics
        success_rate = (successful_parses / total_entries) * 100 if total_entries > 0 else 0

        def _indent_block(s: str, pad: str = '      '):  
            lines = s.splitlines()
            return '\n'.join((pad + ln if ln.strip() else ln) for ln in lines)
        
        # Write parse trees file
        with open(parse_trees_file, 'w', encoding='utf-8') as trees_f:
            trees_f.write("PARSE TREES FOR SUCCESSFULLY PARSED ENTRIES\n")
            trees_f.write("=" * 50 + "\n")
            trees_f.write(f"Total entries processed: {total_entries}\n")
            trees_f.write(f"Successfully parsed: {successful_parses}\n")
            trees_f.write(f"Success rate: {success_rate:.2f}%\n")
            trees_f.write("=" * 50 + "\n\n")
            
            for result_data in successful_results:
                trees_f.write(f"ENTRY #{result_data['entry_number']}\n")
                trees_f.write("-" * 20 + "\n")
                trees_f.write(f"Entry text: {result_data['original_text']}\n\n")
                trees_f.write("Parse tree:\n")
                trees_f.write(format_tree_simple(result_data['parse_tree']))
                trees_f.write("\n\n" + "=" * 50 + "\n\n")
        

        # --- Write transformed results file ---
        from xml.etree import ElementTree as ET

        NS = "http://www.tei-c.org/ns/1.0"
        ET.register_namespace("", NS)

        # Build TEI skeleton
        tei = ET.Element(f"{{{NS}}}TEI", {"type": "lex-0"})
        teiHeader = ET.SubElement(tei, f"{{{NS}}}teiHeader")
        fileDesc = ET.SubElement(teiHeader, f"{{{NS}}}fileDesc")
        titleStmt = ET.SubElement(fileDesc, f"{{{NS}}}titleStmt")
        ET.SubElement(titleStmt, f"{{{NS}}}title")
        publicationStmt = ET.SubElement(fileDesc, f"{{{NS}}}publicationStmt")
        ET.SubElement(publicationStmt, f"{{{NS}}}publisher")
        availability = ET.SubElement(publicationStmt, f"{{{NS}}}availability")
        ET.SubElement(availability, f"{{{NS}}}licence")

        profileDesc = ET.SubElement(teiHeader, f"{{{NS}}}profileDesc")
        langUsage = ET.SubElement(profileDesc, f"{{{NS}}}langUsage")
        ET.SubElement(langUsage, f"{{{NS}}}language",
                    {"role": "sourceLanguage", "ident": "ang"})

        text = ET.SubElement(tei, f"{{{NS}}}text")
        body = ET.SubElement(text, f"{{{NS}}}body")

        # Add the stats as an XML comment INSIDE <body>
        stats_banner = (
            "TRANSFORMED RESULTS FOR SUCCESSFULLY PARSED ENTRIES\n"
            + "="*50 + "\n"
            + f"Total entries processed: {total_entries}\n"
            + f"Successfully parsed: {successful_parses}\n"
            + f"Success rate: {success_rate:.2f}%\n"
            + "="*50
        )
        body.append(ET.Comment(stats_banner))

        # Append each entry as parsed XML
        for r in successful_results:
            # entry-level comment
            entry_comment = f"\nENTRY #{r['entry_number']}\nEntry text: {self._safe_comment_text(r['original_text'])}"
            body.append(ET.Comment(entry_comment))

            # parse the entry string to an element
            el = ET.fromstring(r["transformed_result"])
            self._strip_ws(el)          
            body.append(el)

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


        
        # Write failed entries file
        with open(failed_file, 'w', encoding='utf-8') as failed_f:
            failed_f.write("FAILED ENTRIES WITH ERROR MESSAGES\n")
            failed_f.write("=" * 50 + "\n")
            failed_f.write(f"Total entries processed: {total_entries}\n")
            failed_f.write(f"Failed to parse: {len(failed_entries)}\n")
            failed_f.write(f"Failure rate: {100 - success_rate:.2f}%\n")
            failed_f.write("=" * 50 + "\n\n")
            
            for failed_entry in failed_entries:
                failed_f.write(f"ENTRY #{failed_entry['entry_number']}\n")
                failed_f.write("-" * 20 + "\n")
                failed_f.write(f"Original text: {failed_entry['entry_text']}\n\n")
                error_lines = failed_entry['error'].split('\n')
                if len(error_lines) > 50:
                    limited_error = '\n'.join(error_lines[:50]) + '\n... (error message truncated - showing first 50 lines)'
                else:
                    limited_error = failed_entry['error']
                failed_f.write(f"Error: {limited_error}\n")
                failed_f.write("\n" + "=" * 50 + "\n\n")
        
        print(f"\nFiles created successfully!")
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
                "failed": failed_file
            }
        }
    
    def _extract_problematic_element(self, error_msg):
        """
        Extract the problematic element from the error message.
        
        Args:
            error_msg (str): The error message from parsing
            
        Returns:
            str: The problematic element or pattern
        """
        # Try to extract the unexpected token or pattern from common error patterns
        if "Unexpected token" in error_msg:
            match = re.search(r"Unexpected token Token\('(\w+)', '([^']+)'\)", error_msg)
            if match:
                return f"Token: {match.group(1)} ('{match.group(2)}')"
        
        if "Expected" in error_msg:
            match = re.search(r"Expected: (.+?)(?:\n|$)", error_msg)
            if match:
                return f"Expected: {match.group(1).strip()}"
        
        # Return error msg
        return error_msg

    def parse_file(self, filename):
        """
        Parse dictionary entries from a file.

        Args:
            filename (str): Path to the file containing dictionary entries

        Returns:
            dict: Parsed results
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.parse_text(content)
        except FileNotFoundError:
            return {"error": f"File not found: {filename}"}
        except Exception as e:
            return {"error": f"Error reading file: {e}"}

    def get_parse_tree_only(self, text):
        """
        Get just the parse tree without transformation (useful for debugging).

        Args:
            text (str): Raw dictionary entry text

        Returns:
            str: Pretty-printed parse tree
        """
        if not self.parser:
            return "Parser not initialized"
        
        try:
            cleaned_text = (
                text
                .replace('\u00A0', ' ')
                .replace('\u2018', "'")
                .replace('\u2019', "'")
                .replace('\u201C', '"')
                .replace('\u201D', '"')
                .replace('\n', ' ')       
                .replace('\r', ' ')       
            )
            
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            
            parse_tree = self.parser.parse(cleaned_text)
            return format_tree_simple(parse_tree)
        except ParseError as e:
            return f"Parse error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

def main():
    """
    Main function for batch processing dictionary files.
    """
    parser = DictionaryParser()
    
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(f"Processing dictionary file: {filename}")
        
        results = parser.parse_dictionary_file(filename)
        
        if "error" in results:
            print(f"Error: {results['error']}")
            return
        
        print("\n" + "="*50)
        print("PARSING RESULTS")
        print("="*50)
        print(f"Total entries: {results['total_entries']}")
        print(f"Successfully parsed: {results['successful_parses']}")
        print(f"Failed to parse: {results['failed_parses']}")
        print(f"Success rate: {results['success_rate_percentage']}%")
        
        print("\nOutput files created:")
        for file_type, filename in results['output_files'].items():
            print(f"  - {file_type}: {filename}")
            
    else:
        print("To process a dictionary file, run:")
        print("python src/CAS_parser.py data/input/CAS_test_sample.txt")

if __name__ == "__main__":
    main()