# test

WEMU / Neuronaute HTML prototypes (static pages, built from the Figma file "WEMU - Neuronaute files").

## Run locally

```sh
python3 tools/serve.py 8080   # Range-capable server (needed for video seeking)
```

Then open http://localhost:8080/.

## Pages

| Page | Source (edit this) | Served page |
|---|---|---|
| Prototype copy | `prototype-copy.html` | `index.html` |
| Original (frozen) | `prototype.html` | `original.html` |
| Highlight mode | `prototype-highlight-mode.html` | `highlight-mode.html` |
| Highlight mode variant | `prototype-highlight-mode-variant.html` | `highlight-mode-variant.html` |
| Hypnogram | `prototype-hypnogram.html` | `hypnogram.html` |
| Sleep synthesis | `prototype-sleep-synthesis.html` | `sleep-synthesis.html` |
| Neuronaute exam type flow | – | `neuronaute-exam-type-flow.html` |
| Synthesis translations | – | `synthesis-translations.html` |

Served pages are the sources wrapped in a full HTML document. All pages need the `assets/` folder next to them.
