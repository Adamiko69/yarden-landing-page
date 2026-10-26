import { access, copyFile, cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const missing = [];
for (const asset of ['design.webp', 'portrait.webp', 'portrait-390.webp', 'leaves.webp', 'identity.webp', 'eyebrow.webp', 'headline.webp', 'tagline.webp', 'consultation.webp', 'about-title.webp', 'contact-title.webp', 'social-preview.jpg']) {
  try { await access(path.join(root, 'assets', asset), constants.R_OK); }
  catch { missing.push(`assets/${asset}`); }
}
if (missing.length) {
  console.error(`Cannot publish: original design assets are not available: ${missing.join(', ')}.\nSee assets/README.md. No substitute photography has been used.`);
  process.exit(1);
}
let publicUrl;
try {
  const config = JSON.parse(await readFile(path.join(root, 'site.config.json'), 'utf8'));
  publicUrl = new URL(process.env.SITE_URL || config.url);
  if (publicUrl.protocol !== 'https:' || publicUrl.username || publicUrl.password || publicUrl.search || publicUrl.hash) throw new Error();
  if (!publicUrl.pathname.endsWith('/')) publicUrl.pathname += '/';
} catch {
  console.error('Set SITE_URL to the final public HTTPS URL, including any repository subdirectory.');
  process.exit(1);
}
const escapeAttribute = (value) => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const canonical = escapeAttribute(publicUrl.href);
const imageUrl = escapeAttribute(new URL('assets/social-preview.jpg', publicUrl).href);
const socialTags = `    <link rel="canonical" href="${canonical}">\n    <meta property="og:url" content="${canonical}">\n    <meta property="og:image" content="${imageUrl}">\n    <meta property="og:image:type" content="image/jpeg">\n    <meta property="og:image:width" content="1200">\n    <meta property="og:image:height" content="630">\n    <meta property="og:image:alt" content="ירדן רז חבר">\n    <meta name="twitter:image" content="${imageUrl}">`;
let html = await readFile(path.join(root, 'index.html'), 'utf8');
html = html.replace(/    <!-- build\.mjs supplies[^\n]+-->/, socialTags);
const css = await readFile(path.join(root, 'styles.css'), 'utf8');
const output = path.join(root, 'dist');
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(root, 'assets'), path.join(output, 'assets'), { recursive: true, filter: (name) => !name.endsWith('README.md') && !name.endsWith('reference.png') });
await writeFile(path.join(output, 'index.html'), html);
await writeFile(path.join(output, 'styles.css'), css);
await copyFile(path.join(root, 'contact.js'), path.join(output, 'contact.js'));
await copyFile(path.join(root, '.nojekyll'), path.join(output, '.nojekyll'));
await writeFile(path.join(output, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${new URL('sitemap.xml', publicUrl).href}\n`);
await writeFile(path.join(output, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${canonical}</loc></url></urlset>\n`);
console.log(`Built dist/ for ${publicUrl.href}. Serve this directory on the public host; it has not been deployed by this command.`);
