"""Security tests for safe_paths.py — the only barrier between
remote workflow inputs and arbitrary-file-read on the host.

Covers:
  • is_safe_event_path: symlink rejection, path-traversal rejection,
    legitimate-path acceptance, non-existent-path handling.
  • validate_dropbox_dest: NUL bytes, missing leading slash, `..`
    segments, empty inputs.
  • resolve_safe_watch_folder: relative join, absolute clamp to
    output root, symlink-escape rejection, allowlist via env var.

Run with:
  python -m unittest tests.test_safe_paths
or:
  python tests/test_safe_paths.py
"""

import os
import sys
import shutil
import tempfile
import unittest

# Add the plugin root so we can import the module by name.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safe_paths


class _BaseSafePathTest(unittest.TestCase):
    """Set up an isolated tempdir as the fake ComfyUI output root and
    monkey-patch safe_paths.get_output_root to return it. Each test
    runs in its own directory so file/symlink fixtures don't leak."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dropsend-test-")
        # Real-realpath: macOS may resolve /tmp -> /private/tmp.
        self.output_root = os.path.realpath(self.tmp)
        self._orig_get_output_root = safe_paths.get_output_root
        safe_paths.get_output_root = lambda: self.output_root
        # Clear the allowlist env var so it doesn't bleed in from the
        # caller's shell.
        self._orig_allow = os.environ.pop("COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS", None)

    def tearDown(self):
        safe_paths.get_output_root = self._orig_get_output_root
        if self._orig_allow is not None:
            os.environ["COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS"] = self._orig_allow
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestIsSafeEventPath(_BaseSafePathTest):
    """is_safe_event_path is the gate watchdog calls on every file
    event. False → file is ignored (no upload, no encrypt). True →
    file is processed. Anything that lets a symlink or out-of-tree
    path through becomes an arbitrary-file-read primitive."""

    def test_regular_file_inside_root_is_safe(self):
        path = os.path.join(self.output_root, "image.png")
        with open(path, "wb") as f:
            f.write(b"x")
        self.assertTrue(safe_paths.is_safe_event_path(path))

    def test_regular_file_in_subdir_is_safe(self):
        sub = os.path.join(self.output_root, "subdir")
        os.makedirs(sub)
        path = os.path.join(sub, "image.png")
        with open(path, "wb") as f:
            f.write(b"x")
        self.assertTrue(safe_paths.is_safe_event_path(path))

    def test_symlink_inside_root_is_rejected(self):
        target = os.path.join(self.tmp, "..", "outside-target")
        target = os.path.abspath(target)
        with open(target, "wb") as f:
            f.write(b"sensitive")
        try:
            link = os.path.join(self.output_root, "leak.png")
            os.symlink(target, link)
            # Even though `link` is inside the watched root, it's a
            # symlink -> it must be rejected.
            self.assertFalse(safe_paths.is_safe_event_path(link))
        finally:
            try: os.unlink(target)
            except OSError: pass

    def test_symlink_to_sensitive_target_is_rejected(self):
        # Classic exfiltration pattern: a symlink inside the watched
        # tree points at ~/.ssh/id_rsa or similar.
        sensitive = os.path.expanduser("~/.ssh")  # may or may not exist; doesn't matter
        link = os.path.join(self.output_root, "id_rsa.png")
        try:
            os.symlink(sensitive, link)
            self.assertFalse(safe_paths.is_safe_event_path(link))
        except OSError:
            self.skipTest("could not create test symlink in tempdir")

    def test_path_outside_root_is_rejected(self):
        # File exists but is outside the watched root.
        outside = os.path.join(self.tmp, "..", "outside.png")
        outside = os.path.abspath(outside)
        with open(outside, "wb") as f:
            f.write(b"x")
        try:
            self.assertFalse(safe_paths.is_safe_event_path(outside))
        finally:
            try: os.unlink(outside)
            except OSError: pass

    def test_directory_traversal_string_is_rejected(self):
        # The literal path string contains "..". Even if the string
        # textually starts with the root, after realpath() it must
        # still be inside the root for is_safe_event_path to return
        # True. Here we craft a path that resolves outside.
        path = os.path.join(self.output_root, "..", "..", "etc", "passwd")
        # `path` does not exist under our tmpdir; what matters is
        # that realpath escapes the root, which is_safe_event_path
        # must catch.
        self.assertFalse(safe_paths.is_safe_event_path(path))

    def test_allowlist_extra_root_accepted(self):
        # Operator opts a second root in via env var. Files under
        # that root must now be accepted.
        extra = tempfile.mkdtemp(prefix="dropsend-extra-")
        try:
            os.environ["COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS"] = extra
            extra_real = os.path.realpath(extra)
            f = os.path.join(extra_real, "image.png")
            with open(f, "wb") as fh:
                fh.write(b"x")
            self.assertTrue(safe_paths.is_safe_event_path(f))
        finally:
            os.environ.pop("COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS", None)
            shutil.rmtree(extra, ignore_errors=True)


class TestValidateDropboxDest(unittest.TestCase):
    """validate_dropbox_dest is what stops a hostile workflow from
    sending an `app_secret`-leaking dest like '../../etc/passwd'
    over the wire to Dropbox (which would just normalize and accept
    it, but still — defense in depth)."""

    def test_empty_string_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest("")

    def test_none_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest(None)

    def test_whitespace_only_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest("   ")

    def test_missing_leading_slash_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest("Apps/Foo")

    def test_parent_traversal_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest("/Apps/Foo/../etc/passwd")

    def test_nul_byte_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.validate_dropbox_dest("/Apps/Foo\x00Bar")

    def test_valid_path_returns_normalized(self):
        result = safe_paths.validate_dropbox_dest("/Apps/Foo/Bar")
        self.assertEqual(result, "/Apps/Foo/Bar")

    def test_double_slashes_normalized(self):
        # split-and-rejoin should collapse repeated slashes
        result = safe_paths.validate_dropbox_dest("/Apps//Foo///Bar")
        self.assertEqual(result, "/Apps/Foo/Bar")

    def test_root_only_is_accepted(self):
        result = safe_paths.validate_dropbox_dest("/")
        self.assertEqual(result, "/")


class TestResolveSafeWatchFolder(_BaseSafePathTest):
    """resolve_safe_watch_folder is the only thing standing between a
    remote workflow input and 'watch + upload my entire ~/.ssh'. Test
    that the clamp to output_root is real and that legitimate flows
    still work."""

    def test_empty_input_returns_output_root(self):
        self.assertEqual(safe_paths.resolve_safe_watch_folder(""), self.output_root)

    def test_none_input_returns_output_root(self):
        self.assertEqual(safe_paths.resolve_safe_watch_folder(None), self.output_root)

    def test_relative_input_joined_under_output(self):
        sub = os.path.join(self.output_root, "subdir")
        os.makedirs(sub)
        result = safe_paths.resolve_safe_watch_folder("subdir")
        self.assertEqual(result, sub)

    def test_absolute_input_inside_output_accepted(self):
        sub = os.path.join(self.output_root, "subdir")
        os.makedirs(sub)
        result = safe_paths.resolve_safe_watch_folder(sub)
        self.assertEqual(result, sub)

    def test_absolute_input_outside_output_rejected(self):
        with self.assertRaises(ValueError):
            safe_paths.resolve_safe_watch_folder("/etc")

    def test_traversal_back_to_root_rejected(self):
        with self.assertRaises(ValueError):
            # Even though the string is a relative path, after
            # realpath it escapes the root.
            safe_paths.resolve_safe_watch_folder("../../etc")

    def test_symlink_pointing_outside_root_rejected(self):
        # An attacker-supplied watch_folder that's a symlink to /etc
        # must be rejected even though the symlink itself was created
        # inside the watched dir.
        outside = os.path.realpath(tempfile.mkdtemp(prefix="dropsend-out-"))
        try:
            link = os.path.join(self.output_root, "shortcut")
            os.symlink(outside, link)
            with self.assertRaises(ValueError):
                safe_paths.resolve_safe_watch_folder(link)
        finally:
            shutil.rmtree(outside, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
