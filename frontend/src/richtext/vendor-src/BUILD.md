# Rich editor bundle

Engine: Tiptap 3.32.1 (MIT), with MIT-compatible ProseMirror dependencies. Full notices are in `../THIRD-PARTY-LICENSES.txt`.

The checked-in `../editor-vendor.js` is self-hosted and loaded lazily only when the editor opens. No CDN, account, API key or commercial editor license is used. The main frontend package.json/package-lock.json are unchanged.

To rebuild from this directory:

```bash
npm ci
npm exec --package=esbuild@0.28.2 -- esbuild editor-entry.js --bundle --minify --format=esm --platform=browser --target=es2022 --legal-comments=eof --outfile=../editor-vendor.js
```

Keep the supplied lockfile for reproducibility and update license notices when updating dependencies. These font options use fonts available on the reader's device; this bundle does not distribute font files.
