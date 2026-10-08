import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from configure import initialize
from dec_iam.config import Settings


class ConfigurationTests(unittest.TestCase):
    def test_initializer_generates_loadable_config_and_distinct_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            initialize(out, issuer="https://sso.example", community_url="https://community.example",
                       iam_base_url="https://iam.example", iam_client_id="iam-app", iam_client_secret="iam-${literal}-secret")
            pairs = dict(line.split("=", 1) for line in (out / ".env").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#"))
            self.assertEqual(pairs["DEC_IAM_CLIENT_SECRET"], "iam-${literal}-secret")
            pairs["DEC_SIGNING_KEY_FILE"] = str(out / "secrets/signing.pem")
            cfg = Settings(_env_file=None, **{k.removeprefix("DEC_").lower(): v for k, v in pairs.items()})
            self.assertNotEqual(cfg.client_secret.get_secret_value(), cfg.iam_client_secret.get_secret_value())
            client = json.loads((out / "community-sso.json").read_text(encoding="utf-8"))
            self.assertEqual(client["issuer"], cfg.issuer)
            self.assertEqual(client["bind_rule"], "sub")
            self.assertFalse(client["extract_employee"])
            self.assertEqual(client["userinfo_endpoint"], cfg.issuer + "/userinfo")
            self.assertTrue((out / "secrets/signing.pem").read_text().startswith("-----BEGIN PRIVATE KEY-----"))

    def test_initializer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / ".env").write_text("existing")
            with self.assertRaises(FileExistsError):
                initialize(out, issuer="https://sso.example", community_url="https://community.example",
                           iam_base_url="https://iam.example", iam_client_id="iam-app", iam_client_secret="secret")
            self.assertEqual((out / ".env").read_text(), "existing")
            self.assertFalse((out / "secrets/signing.pem").exists())

    def test_initializer_rejects_invalid_input_before_writing(self):
        for changes in ({"issuer": "http://sso.example"}, {"iam_client_secret": "secret\nINJECTED=1"},
                        {"community_url": "https://community.example/extra"}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder:
                values = dict(issuer="https://sso.example", community_url="https://community.example",
                              iam_base_url="https://iam.example", iam_client_id="iam-app", iam_client_secret="secret")
                values.update(changes)
                with self.assertRaises(ValueError):
                    initialize(Path(folder), **values)
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_directory_permission_failure_aborts_before_writing_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "secrets").mkdir()
            with patch.object(Path, "chmod", side_effect=PermissionError("cannot restrict directory")):
                with self.assertRaises(PermissionError):
                    initialize(out, issuer="https://sso.example", community_url="https://community.example",
                               iam_base_url="https://iam.example", iam_client_id="iam-app", iam_client_secret="secret")
            self.assertFalse((out / "secrets/signing.pem").exists())
            self.assertFalse((out / ".env").exists())


if __name__ == "__main__":
    unittest.main()
