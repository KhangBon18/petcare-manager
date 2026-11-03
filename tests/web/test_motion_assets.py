"""Local, ordered optional motion assets retain the strict offline CSP contract."""

from hashlib import sha256
from unittest import TestCase

from petcare import create_app


class MotionAssetTests(TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "motion-assets-test-key"})
        self.client = self.app.test_client()

    def test_motion_is_deferred_local_and_never_requires_an_inline_or_cdn_exception(self):
        response = self.client.get("/login")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('/static/css/motion.css', html)
        paths = ['/static/vendor/gsap/gsap.min.js', '/static/js/motion.js', '/static/js/app.js']
        positions = [html.index(path) for path in paths]
        self.assertEqual(positions, sorted(positions))
        for path in paths:
            self.assertIn(f'<script src="{path}" defer></script>', html)
        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        self.assertIn("style-src 'self'", response.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', response.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-eval', response.headers['Content-Security-Policy'])
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)

    def test_offline_vendor_bytes_are_the_pinned_distribution_with_license_preserved(self):
        response = self.client.get('/static/vendor/gsap/gsap.min.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sha256(response.data).hexdigest(), '92bb9a96476f983d212a2bc4f54c889039c1696dd4461d40a736860938570fbb')
        self.assertIn(b'GSAP 3.15.0', response.data[:500])
        self.assertIn(b'https://gsap.com/standard-license', response.data[:500])
        response.close()
