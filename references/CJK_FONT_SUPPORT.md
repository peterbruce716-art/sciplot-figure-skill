# CJK Font Support

`font_resolver.py` searches Matplotlib's installed font metadata. It records requested families, resolved families, fallback use, a basename and hash for the actual font file when available, and deterministic PDF/SVG settings. It never bundles or distributes fonts.

The default CJK order is Noto Sans CJK SC, Source Han Sans SC, SimHei, Microsoft YaHei, and Arial Unicode MS. For Chinese thesis-style serif text, use `--serif-for-zh` or the `chinese_thesis` profile. Missing CJK fonts are warnings and should be fixed before submission. The configured `axes.unicode_minus` value is recorded rather than assumed.
