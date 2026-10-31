# Banner Studio upgrade

## Installation

Run the supplied installer from the repository root with `--apply`. It first checks every affected source file, then backs up originals under `$HOME/digishop-banner-studio-backup-*`. An unknown file version stops the entire operation before any source is changed. Do not bypass this check. The installer does not alter Git, run Docker, or touch the database.

Apply the included `cms/0004_bannervideo` migration with `python manage.py migrate`, run backend checks/tests and the frontend build, then restart web/frontend. No new pip or npm dependency is introduced. Previous nh3 and the local Tiptap bundle remain in use. Do not create a second migration for these changes.

## Dashboard

Open `/dashboard/banners`. Add a main slide, a tile, or a top strip. Select image or video, upload files, configure the canvas, and preview desktop/mobile. Draft saving and publication remain separate. Existing published banners keep their content and legacy split layout. Existing image uploads remain usable.

Each banner supports:

- JPG/PNG/WebP image (existing image uploader converts it to WebP).
- MP4/H.264 video, at most 30 MiB and 90 seconds, up to 3840×2160. Optional audio must have AAC metadata. Desktop and mobile videos are separate uploads; mobile falls back to desktop.
- Optional poster image for desktop/mobile. A poster is recommended for loading, reduced motion, and playback failure.
- Text over media or beside it; cover/contain; compact/standard/tall/natural height; full/container width; left/center/right crop and text position; light/dark text; overlay shading.
- Destination, button label, visibility, order, duplicate, and optional schedule.
- Slide interval 3–30 seconds. Slideshow pauses while a video is playing and during keyboard/mouse interaction. Automatic video playback is muted, obeys browser restrictions, and is disabled for reduced-motion/save-data preferences. Video controls allow manual playback.

There are three established storefront placements, not a free pixel-position page builder. No HTML, JavaScript, arbitrary iframe, or remote video download is accepted through banner settings.

The MP4 validator checks bounded container structure, codec metadata, dimensions, duration, and size. It does not decode/transcode every frame. A damaged encoded stream can still fail playback; the frontend displays its poster/error. For production, serve `.mp4` as `video/mp4` with HTTP byte-range support and set the reverse-proxy upload limit above 30 MiB. This development installer does not configure production Nginx/CDN or introduce a transcoding queue.

## Product editor

Toolbar commands remember the text selection across font/size/color controls and link dialogs. The hidden form value is synchronized immediately after a command. Semantic formatting styles and font synthesis are restored inside the editor and published description, independent of dashboard resets.

Select existing text before changing its format; with only a caret, formatting applies to subsequent typing. The toolbar includes Select All. Bold/italic/underline/strike, font/size/color, headings, alignment, lists, quotes, links, undo/redo and clear marks are supported. Server HTML sanitization remains active; arbitrary HTML/scripts are not permitted.

## Validation performed for this package

- Isolated Django checks and migration drift check: passed.
- 65 CMS/rich-description tests: 64 passed, one PostgreSQL-only concurrency test skipped in the SQLite fixture.
- New cases exercise MP4 metadata rejection, upload size limits, management/customer authorization, asset persistence, old-banner compatibility, and banner layout validation.
- A real FFmpeg-generated H.264 MP4 was parsed successfully.
- React/jsdom interaction tests exercise banner draft/publication, media selection, desktop/mobile preview, slideshow controls, and actual Tiptap bold/font/size/italic/underline/heading/alignment/list/link/undo/redo/clear formatting.
- Full uploaded frontend module graph bundles with esbuild including the lazy editor chunk.

The complete checkout, PostgreSQL suite, Vite production build, actual video playback and visual browser QA must still be verified on the user's installation. An observed toolbar failure on the user's browser has not been reproduced locally; this update hardens selection and presentation, but browser console output is needed if that failure persists.
