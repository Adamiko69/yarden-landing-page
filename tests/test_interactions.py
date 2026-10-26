"""Real-browser checks for contact actions, terms, metadata and responsive layout.

Run with: python3 -m unittest discover -s tests -p 'test_*.py' -v
These checks intentionally do not validate the still-missing original artwork.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Error, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test-results"
MESSAGE = "היי ירדן, אשמח לתאם שיחת היכרות"
LEGAL_TEXT = (
    "כל התכנים והתמונה באתר מוגנים בזכויות יוצרים. אין להעתיק, לשמור, "
    "לפרסם, להפיץ או לעשות שימוש בתמונה של ירדן רז חבר ללא אישור מפורש מראש ובכתב."
)
VIEWPORTS = (
    ("desktop_reference", 1024, 1536, False),
    ("desktop_wide", 1440, 900, False),
    ("mobile_small", 320, 740, True),
    ("mobile_standard", 390, 844, True),
    ("mobile_large", 430, 932, True),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass


class LandingPageInteractions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT))
        )
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(
                executable_path="/usr/bin/chromium", headless=True, chromium_sandbox=True
            )
        except Error as exc:
            # Unprivileged cloud containers may prohibit Chromium's namespace sandbox.
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

    def check_viewport(self, name, width, height, mobile):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2 if mobile else 1,
            is_mobile=mobile,
            has_touch=mobile,
        )
        intercepted_whatsapp = []
        errors = []

        def handle_request(route):
            parsed = urlparse(route.request.url)
            if parsed.hostname == "wa.me":
                intercepted_whatsapp.append(route.request.url)
                route.fulfill(status=200, content_type="text/html", body="<!doctype html><title>Intercepted WhatsApp navigation</title>")
            elif parsed.hostname == "127.0.0.1":
                route.continue_()
            else:
                route.abort()  # Never contact a third party during these checks.

        context.route("**/*", handle_request)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            response = page.goto(self.base_url, wait_until="networkidle")
            self.assertEqual(response.status, 200)
            page.evaluate("document.fonts.ready")
            self.assertEqual(page.title(), "ירדן רז חבר | פסיכותרפיסטית אינטגרטיבית")
            for selector, expected in (
                ('meta[name="description"]', "פסיכותרפיה אינטגרטיבית לנשים ונערות, מרחב לעצמך להרגיש להבין ולצמוח"),
                ('meta[property="og:title"]', "ירדן רז חבר | מרחב לעצמך"),
                ('meta[property="og:description"]', "להרגיש. להבין. לצמוח."),
            ):
                self.assertEqual(page.locator(selector).get_attribute("content"), expected)
            self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")
            self.assertEqual(page.locator("html").get_attribute("lang"), "he")

            # Validate the real links, then exercise both their icon and text hit areas.
            whatsapp = page.locator('[data-contact="whatsapp"]')
            self.assertEqual(whatsapp.count(), 2)
            expected_popup_count = 0
            for link_index in range(whatsapp.count()):
                link = whatsapp.nth(link_index)
                parsed = urlparse(link.get_attribute("href"))
                self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ("https", "wa.me", "/972528337144"))
                self.assertEqual(parse_qs(parsed.query), {"text": [MESSAGE]})
                self.assertEqual(link.get_attribute("target"), "_blank")
                self.assertIn("noopener", link.get_attribute("rel"))
                for child_selector in ("svg", "span" if link_index == 0 else "bdi"):
                    target = link.locator(child_selector)
                    target.scroll_into_view_if_needed()
                    self.assert_hit_target(page, target, link)
                    with page.expect_popup() as popup_info:
                        target.tap() if mobile else target.click()
                    popup = popup_info.value
                    popup.wait_for_load_state()
                    self.assertEqual(parse_qs(urlparse(popup.url).query), {"text": [MESSAGE]})
                    popup.close()
                    expected_popup_count += 1
            self.assertEqual(len(intercepted_whatsapp), expected_popup_count)

            # Intercept the clicked mailto anchor before opening an external mail client.
            page.evaluate("""() => {
                window.__testMailClicks = [];
                document.addEventListener('click', event => {
                    const link = event.target.closest('a[href^="mailto:"]');
                    if (link) { window.__testMailClicks.push(link.href); event.preventDefault(); }
                }, true);
            }""")
            email = page.locator('[data-contact="email"]')
            self.assertEqual(email.count(), 1)
            self.assertEqual(email.get_attribute("href"), "mailto:r.yarden@gmail.com")
            for child_selector in ("svg", "bdi"):
                target = email.locator(child_selector)
                target.scroll_into_view_if_needed()
                self.assert_hit_target(page, target, email)
                target.tap() if mobile else target.click()
            self.assertEqual(page.evaluate("window.__testMailClicks"), ["mailto:r.yarden@gmail.com"] * 2)

            # The terms must work by tap, independently of hover support.
            trigger = page.locator("#terms-trigger")
            popover = page.locator("#terms-popover")
            trigger.scroll_into_view_if_needed()
            self.assertEqual(trigger.get_attribute("aria-controls"), "terms-popover")
            self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
            self.assertTrue(popover.is_hidden())
            trigger.tap() if mobile else trigger.click()
            self.assertTrue(popover.is_visible())
            self.assertEqual(trigger.get_attribute("aria-expanded"), "true")
            self.assertEqual(popover.inner_text().strip(), LEGAL_TEXT)
            self.assert_within_width(popover.bounding_box(), width, "terms popover")
            page.screenshot(path=str(RESULTS / f"{name}-terms.png"), full_page=True)
            page.locator(".footer__copyright").tap() if mobile else page.locator(".footer__copyright").click()
            self.assertTrue(popover.is_hidden())
            self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
            trigger.tap() if mobile else trigger.click()
            trigger.tap() if mobile else trigger.click()
            self.assertTrue(popover.is_hidden())
            if not mobile:
                trigger.click()
                page.keyboard.press("Escape")
                self.assertTrue(popover.is_hidden())
                self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
                self.assertTrue(trigger.evaluate("el => document.activeElement === el"))

            # Scrollable page height is expected; horizontal scrolling is not.
            sizes = page.evaluate("({document: document.documentElement.scrollWidth, viewport: innerWidth})")
            self.assertLessEqual(sizes["document"], sizes["viewport"], sizes)
            for selector in (".footer", ".footer__copyright", "#terms-trigger"):
                self.assert_within_width(page.locator(selector).bounding_box(), width, selector)
            for locator in page.locator("a, button").all():
                box = locator.bounding_box()
                self.assertGreaterEqual(box["height"], 44, locator.inner_text())
                self.assert_within_width(box, width, locator.inner_text())
            page.screenshot(path=str(RESULTS / f"{name}.png"), full_page=True)
            self.assertEqual(errors, [], "Browser JavaScript errors")
        finally:
            context.close()

    def assert_hit_target(self, page, target, link):
        box = target.bounding_box()
        self.assertIsNotNone(box)
        hit_href = page.evaluate("""({x, y}) => {
            const el = document.elementFromPoint(x, y);
            const link = el && el.closest('a');
            return link && link.href;
        }""", {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2})
        self.assertEqual(hit_href, link.get_attribute("href"))

    def assert_within_width(self, box, width, label):
        self.assertIsNotNone(box, label)
        self.assertGreaterEqual(box["x"], -1, label)
        self.assertLessEqual(box["x"] + box["width"], width + 1, label)


def make_viewport_test(viewport):
    def test(self):
        self.check_viewport(*viewport)
    test.__doc__ = f"Contact actions, terms, SEO and layout at {viewport[1]}×{viewport[2]}."
    return test


for _viewport in VIEWPORTS:
    setattr(LandingPageInteractions, f"test_{_viewport[0]}", make_viewport_test(_viewport))


if __name__ == "__main__":
    unittest.main(verbosity=2)
