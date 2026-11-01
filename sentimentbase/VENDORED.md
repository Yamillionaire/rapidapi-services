# Vendored: VADER (vaderSentiment)

- Source: PyPI package `vaderSentiment`, downloaded with
  `pip download vaderSentiment==3.3.2 --no-deps` on 2026-11-01.
- Version: 3.3.2
- Upstream project: VADER (Valence Aware Dictionary and sEntiment
  Reasoner), by C.J. Hutto and Eric Gilbert.
- License: MIT (see the package's LICENSE.txt in the upstream
  distribution; the module header in `vaderSentiment.py` also
  carries the copyright and license notice).
- Files vendored here:
  - `vaderSentiment.py` - the analyzer module, unmodified.
  - `vader_lexicon.txt` - the sentiment lexicon, unmodified.
  - `emoji_utf8_lexicon.txt` - the emoji lexicon the module loads
    by default alongside `vader_lexicon.txt`; vendored (also
    unmodified) because `SentimentIntensityAnalyzer()` will fail
    to construct without it next to the module.
- nltk note: the module imports `nltk` only inside its
  `if __name__ == '__main__':` demo block (and `requests` only in
  that same demo path). The import and the lexicon-file code path
  used by this service were verified with plain `python3` in an
  environment where nltk is not imported: the analyzer constructs
  from the local lexicon files and scores text correctly. No
  modification to the vendored module was needed, so none was made.
