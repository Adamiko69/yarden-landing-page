# Approved original artwork

`reference.png` is the unmodified 1024 × 1536 image extracted from the user's ZIP. It is retained for future design maintenance and is excluded from the public build.

Run `python3 scripts/prepare-assets.py` only after deliberately replacing the approved original. It extracts existing pixels and optimizes delivery without generating or retouching the person or adding text.

- `design.webp`: pixel-identical lossless desktop artwork. Live controls and accessible semantic HTML overlay it.
- `portrait.webp`, `portrait-390.webp`: face-safe original crop (0, 0, 584, 652), plus a smaller responsive version. CSS preserves its aspect ratio and the entire face.
- `identity.webp`, `eyebrow.webp`, `headline.webp`, `tagline.webp`, `consultation.webp`, `about-title.webp`, `contact-title.webp`: small crops preserve the supplied display lettering on mobile. No font files for that lettering were supplied.
- `leaves.webp`: original foliage and its original paper background; no artificial transparency.
- `social-preview.jpg`: 1200 × 630, about 96 KB. The entire portrait is fitted and padded using an existing paper color, with no face crop or new text.

Mobile paragraphs reflow using self-hosted Assistant fonts, a close match to the raster body text. Exact font identity cannot be certified from a PNG. Desktop type and principal mobile display lettering preserve the actual original pixels. Fonts came from integrity-verified `@fontsource/assistant@5.3.0`; its OFL license is in `fonts/`. There are no runtime font/CDN requests.

Future contact changes in `contact.js` update links and visible mobile labels. On desktop, edited live labels reveal themselves over the old artwork text. Other changes to desktop wording require a revised original design image.
