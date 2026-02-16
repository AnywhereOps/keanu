"""tests for secret detection, dependency scanning, audit logging."""

from pathlib import Path
from unittest.mock import patch

from keanu.infra.security import (
    scan_secrets, check_secrets_in_staged, is_sensitive_file,
    check_gitignore_coverage, log_audit, get_audit_log,
    _redact, _sanitize_args, SecretFinding,
)


class TestSecretDetection:

    def test_detects_aws_key(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        findings = scan_secrets(str(f))
        assert len(findings) >= 1
        assert findings[0].category == "aws_key"
        assert findings[0].confidence >= 0.9

    def test_detects_github_token(self, tmp_path):
        f = tmp_path / "env.py"
        f.write_text('TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n')
        findings = scan_secrets(str(f))
        assert any(f.category == "github_classic" for f in findings)

    def test_detects_private_key(self, tmp_path):
        f = tmp_path / "key.pem"
        f.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...\n")
        findings = scan_secrets(str(f))
        assert any(f.category == "private_key" for f in findings)

    def test_detects_generic_api_key(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('api_key = "abcdef1234567890abcdef"\n')
        findings = scan_secrets(str(f))
        assert any(f.category == "generic_api_key" for f in findings)

    def test_detects_password(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('password = "super_secret_password_123"\n')
        findings = scan_secrets(str(f))
        assert any(f.category == "generic_secret" for f in findings)

    def test_no_false_positive_on_clean(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text('x = 1\ny = "hello world"\n')
        findings = scan_secrets(str(f))
        assert findings == []

    def test_scans_directory(self, tmp_path):
        (tmp_path / "a.py").write_text('key = "AKIAIOSFODNN7EXAMPLE"\n')
        (tmp_path / "b.py").write_text('x = 1\n')
        findings = scan_secrets(str(tmp_path))
        assert len(findings) >= 1

    def test_skips_binary_files(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        findings = scan_secrets(str(tmp_path))
        assert findings == []

    def test_detects_connection_string(self, tmp_path):
        f = tmp_path / "db.py"
        f.write_text('DB_URL = "postgres://user:pass@localhost:5432/db"\n')
        findings = scan_secrets(str(f))
        assert any(f.category == "connection_string" for f in findings)

    def test_detects_anthropic_key(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('ANTHROPIC_KEY = "sk-ant-api03-abcdefghijklmnopqrst"\n')
        findings = scan_secrets(str(f))
        assert any(f.category == "anthropic_key" for f in findings)


class TestRedact:

    def test_redacts_long_secret(self):
        line = 'key = "AKIAIOSFODNN7EXAMPLE"'
        import re
        match = re.search(r"AKIA[0-9A-Z]{16}", line)
        result = _redact(line, match)
        assert "AKIA" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "****" in result

    def test_redacts_short_secret(self):
        import re
        line = 'x = "secret"'
        match = re.search(r"secret", line)
        result = _redact(line, match)
        assert "****" in result


class TestSensitiveFile:

    def test_env_file(self):
        assert is_sensitive_file(".env")
        assert is_sensitive_file(".env.local")
        assert is_sensitive_file(".env.production")

    def test_credential_files(self):
        assert is_sensitive_file("credentials.json")
        assert is_sensitive_file("id_rsa")
        assert is_sensitive_file("id_ed25519")

    def test_key_files(self):
        assert is_sensitive_file("server.pem")
        assert is_sensitive_file("private.key")

    def test_normal_files(self):
        assert not is_sensitive_file("main.py")
        assert not is_sensitive_file("README.md")
        assert not is_sensitive_file("package.json")


class TestGitignoreCoverage:

    def test_detects_unprotected(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET=x\n")
        # no .gitignore
        unprotected = check_gitignore_coverage(str(tmp_path))
        assert ".env" in unprotected

    def test_protected_file(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET=x\n")
        (tmp_path / ".gitignore").write_text(".env\n")
        unprotected = check_gitignore_coverage(str(tmp_path))
        assert ".env" not in unprotected


class TestAuditLog:

    def test_log_and_read(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        with patch("keanu.infra.security._AUDIT_LOG", log_file):
            log_audit("read", {"file": "test.py"}, "ok", 10)
            log_audit("write", {"file": "out.py"}, "ok", 20)
            entries = get_audit_log()
        assert len(entries) == 2
        assert entries[0]["action"] == "read"
        assert entries[1]["action"] == "write"

    def test_empty_log(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        with patch("keanu.infra.security._AUDIT_LOG", log_file):
            entries = get_audit_log()
        assert entries == []

    def test_sanitizes_secrets(self):
        result = _sanitize_args({"password": "secret123", "file": "test.py"})
        assert result["password"] == "****"
        assert result["file"] == "test.py"

    def test_truncates_long_values(self):
        result = _sanitize_args({"content": "x" * 600})
        assert len(result["content"]) < 200
        assert "truncated" in result["content"]


class TestSecretFinding:

    def test_str(self):
        f = SecretFinding(
            file="config.py", line=5,
            category="api_key", snippet="api_key = ****",
            confidence=0.9,
        )
        assert "config.py:5" in str(f)
        assert "api_key" in str(f)
