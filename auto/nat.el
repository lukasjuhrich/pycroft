(TeX-add-style-hook
 "nat"
 (lambda ()
   (TeX-add-to-alist 'LaTeX-provided-class-options
                     '(("article" "11pt")))
   (TeX-add-to-alist 'LaTeX-provided-package-options
                     '(("inputenc" "utf8") ("fontenc" "T1") ("ulem" "normalem")))
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "path")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "url")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "nolinkurl")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperbaseurl")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperimage")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperref")
   (add-to-list 'LaTeX-verbatim-macros-with-delims-local "path")
   (TeX-run-style-hooks
    "latex2e"
    "article"
    "art11"
    "inputenc"
    "fontenc"
    "fixltx2e"
    "graphicx"
    "grffile"
    "longtable"
    "wrapfig"
    "rotating"
    "ulem"
    "amsmath"
    "textcomp"
    "amssymb"
    "capt-of"
    "hyperref"
    "commath"
    "amsthm"
    "amsfonts"
    "mathabx"
    "mathtools"
    "mathrsfs"
    "tikz"
    "tikz-cd")
   (TeX-add-symbols
    "then")
   (LaTeX-add-labels
    "sec:org986f795"
    "sec:org10ab804"
    "sec:orgbdafd96"
    "sec:orgd956d72"
    "sec:org1e89023"
    "sec:org6fc2b67"
    "sec:orgfad0ad1"
    "sec:orgf1babb5"
    "sec:org8176d15"
    "sec:org8dba364"
    "sec:org98c4a1c"
    "sec:org41f88f6"
    "sec:orgb95cb9c"
    "sec:org51a8a6c"
    "sec:org34021b4"
    "sec:org17fbf1b"
    "sec:orgb7de5b9"
    "sec:orgd5ca168"
    "sec:orga249001"
    "sec:org267553a"
    "sec:orgcc61c00"
    "sec:org9fd6ac1"
    "sec:org1e2d49c"
    "sec:orgc55ae1f"
    "sec:org419b92a"
    "sec:orgdd8e0d4"
    "sec:org8e60c45"
    "sec:org1437d05"
    "sec:orgaf064a3"
    "sec:orgfc16d02"
    "sec:orgc1ace78"
    "sec:org63e6817"
    "sec:org7626e55"
    "sec:org19e3979"
    "sec:orgf47e51e"
    "sec:orgb38ce6b"
    "sec:orga98c59a"
    "sec:org32a1fbb"
    "sec:org6be5ea2"
    "sec:org72bc2b5"
    "sec:org5a2425c"
    "sec:org0c766d6"
    "sec:org86e19b3"
    "sec:org1212dc3"
    "sec:org5433992"
    "sec:org84c9ddc"))
 :latex)

