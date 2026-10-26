"""Verify built-site pixels, responsive asset delivery and share metadata.

Run `npm run build` first. Tests serve dist/ under its real deployment path;
they do not establish that a public deployment has happened.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import threading
import unittest
from urllib.parse import urlsplit

from PIL import Image, ImageChops
from playwright.sync_api import Error, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RESULTS = ROOT / "test-results"
PUBLIC_URL = "https://yarden-raz.github.io/clinic/"
PUBLIC_IMAGE = PUBLIC_URL + "assets/social-preview.jpg"
SITE_PATH = "/clinic/"


class DeploymentPathHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith(SITE_PATH):
            path = "/" + path[len(SITE_PATH):]
        return super().translate_path(path)

    def log_message(self, _format, *args):
        pass


class VisualDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").is_file():
            raise RuntimeError("Production dist/ is absent. Run npm run build first.")
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(DeploymentPathHandler, directory=str(DIST))
        )
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        cls.base_url = cls.origin + SITE_PATH
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(
                executable_path="/usr/bin/chromium", headless=True, chromium_sandbox=True
            )
        except Error as exc:
            if not any(word in str(exc).lower() for word in ("sandbox", "namespace", "operation not permitted")):
                raise
            cls.browser = cls.playwright.chromium.launch(
                executable_path="/usr/bin/chromium", headless=True, chromium_sandbox=False
            )
        RESULTS.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def open_page(self, width, height, mobile=False, scale=1):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=mobile, has_touch=mobile, device_scale_factor=scale,
        )
        self.addCleanup(context.close)
        responses, failures, errors = [], [], []
        page = context.new_page()
        page.on("response", lambda response: responses.append((response.url, response.status)))
        page.on("requestfailed", lambda request: failures.append((request.url, request.failure)))
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("""
            window.__deliveryLayoutShifts = [];
            new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) window.__deliveryLayoutShifts.push(entry.value);
                }
            }).observe({type: 'layout-shift', buffered: true});
        """)
        response = page.goto(self.base_url, wait_until="networkidle")
        self.assertEqual(response.status, 200)
        page.evaluate("document.fonts.ready")
        page.evaluate("Promise.all([...document.images].map(img => img.decode().catch(() => null)))")
        page.wait_for_timeout(100)
        self.assertEqual(failures, [], "Failed requests")
        self.assertEqual(errors, [], "Browser errors")
        self.assertTrue(responses)
        self.assertEqual([item for item in responses if item[1] != 200], [], "Non-200 resource responses")
        self.assertTrue(all(url.startswith(self.origin) for url, _ in responses), responses)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
        return context, page, responses

    def test_desktop_matches_original_pixels(self):
        _, page, responses = self.open_page(1024, 1536)
        self.assertEqual(page.evaluate("document.documentElement.scrollHeight"), 1536)
        self.assertTrue(any(url.endswith("/assets/design.webp") for url, _ in responses))
        screenshot = page.screenshot(path=str(RESULTS / "production-desktop-exact.png"), full_page=True)
        rendered = Image.open(BytesIO(screenshot)).convert("RGB")
        with Image.open(ROOT / "assets/reference.png") as source:
            reference = source.convert("RGB")
        self.assertEqual(rendered.size, (1024, 1536))
        difference = ImageChops.difference(rendered, reference)
        self.assertIsNone(difference.getbbox(), "Rendered desktop pixels differ from the supplied design")

    def test_mobile_fetches_face_safe_assets_without_desktop_artwork(self):
        _, page, responses = self.open_page(390, 844, mobile=True, scale=2)
        paths = [urlsplit(url).path for url, _ in responses]
        self.assertFalse(any(path.endswith(("/design.webp", "/reference.png")) for path in paths), paths)
        self.assertTrue(any(path.endswith("/portrait.webp") for path in paths), paths)
        portrait = page.locator(".hero__photograph img")
        image = portrait.evaluate("""img => ({
            naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight,
            complete: img.complete, fit: getComputedStyle(img).objectFit,
            width: img.getBoundingClientRect().width, height: img.getBoundingClientRect().height
        })""")
        self.assertTrue(image["complete"])
        # srcset's width descriptor makes naturalWidth density-corrected; the
        # downloaded image pixels are checked independently below.
        self.assertGreaterEqual(image["naturalWidth"], 390)
        self.assertGreaterEqual(image["naturalHeight"], 435)
        self.assertAlmostEqual(image["naturalWidth"] / image["naturalHeight"], 584 / 652, delta=0.002)
        self.assertEqual(image["fit"], "contain")
        self.assertAlmostEqual(image["width"] / image["height"], 584 / 652, places=3)
        # The mobile photograph is the exact source crop, including the full face.
        with Image.open(ROOT / "assets/reference.png") as original, Image.open(DIST / "assets/portrait.webp") as delivered:
            difference = ImageChops.difference(original.convert("RGB").crop((0, 0, 584, 652)), delivered.convert("RGB"))
            self.assertIsNone(difference.getbbox(), "Portrait pixels changed from the original crop")
        shifts = page.evaluate("window.__deliveryLayoutShifts")
        self.assertLessEqual(sum(shifts), 0.1, f"Unexpected loading layout shifts: {shifts}")
        print(f"Mobile cumulative layout shift: {sum(shifts):.5f}")
        for link in page.locator("a, button").all():
            box = link.bounding_box()
            self.assertGreaterEqual(box["height"], 44)
            self.assertGreaterEqual(box["x"], 0)
            self.assertLessEqual(box["x"] + box["width"], 390)
        page.screenshot(path=str(RESULTS / "production-mobile-390.png"), full_page=True)

    def test_share_metadata_and_image_under_project_path(self):
        context, page, _ = self.open_page(1024, 1536)
        expected = (
            ('link[rel="canonical"]', "href", PUBLIC_URL),
            ('meta[property="og:url"]', "content", PUBLIC_URL),
            ('meta[property="og:image"]', "content", PUBLIC_IMAGE),
            ('meta[name="twitter:image"]', "content", PUBLIC_IMAGE),
        )
        for selector, attribute, value in expected:
            self.assertEqual(page.locator(selector).get_attribute(attribute), value)
        # Fetch the metadata's real project-relative path on the production fixture.
        response = context.request.get(self.origin + urlsplit(PUBLIC_IMAGE).path)
        self.assertEqual(response.status, 200)
        self.assertIn("image/jpeg", response.headers["content-type"])
        share = Image.open(BytesIO(response.body()))
        self.assertEqual(share.size, (1200, 630))
        self.assertEqual(page.locator('meta[property="og:image:width"]').get_attribute("content"), "1200")
        self.assertEqual(page.locator('meta[property="og:image:height"]').get_attribute("content"), "630")

    def test_breakpoint_does_not_overflow_or_shrink_targets(self):
        for width in (700, 701):
            with self.subTest(width=width):
                context, page, _ = self.open_page(width, 900, mobile=True)
                desktop = page.locator(".desktop-artwork")
                self.assertEqual(desktop.is_visible(), width >= 701)
                for link in page.locator("a, button").all():
                    box = link.bounding_box()
                    self.assertGreaterEqual(box["height"], 44)
                    self.assertGreaterEqual(box["x"], 0)
                    self.assertLessEqual(box["x"] + box["width"], width)
                page.screenshot(path=str(RESULTS / f"production-breakpoint-{width}.png"), full_page=True)
                context.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
