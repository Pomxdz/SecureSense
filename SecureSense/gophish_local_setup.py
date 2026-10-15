"""Prepare loopback Gophish with a SAN certificate trusted by SecureSense.
Runtime dependencies are installed by requirements.txt; run with the extracted Gophish directory.
The engine remains a separate official download. Existing configuration is backed up.
"""

import argparse, datetime, ipaddress, json, shutil
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

p = argparse.ArgumentParser()
p.add_argument("gophish_directory", type=Path)
p.add_argument("--phish-port", type=int, default=80)
p.add_argument("--admin-port", type=int, default=3333)
a = p.parse_args()
if (
    not all(1 <= port <= 65535 for port in (a.phish_port, a.admin_port))
    or a.phish_port == a.admin_port
):
    p.error("Choose distinct valid ports")
folder = a.gophish_directory.resolve()
configpath = folder / "config.json"
if not configpath.is_file():
    p.error("Select the extracted Gophish directory containing config.json")
config = json.loads(configpath.read_text())
certpath = folder / "securesense_admin.crt"
keypath = folder / "securesense_admin.key"
if certpath.exists() or keypath.exists():
    if not certpath.exists() or not keypath.exists():
        p.error(
            "Certificate/key pair is incomplete; review existing files before continuing"
        )
else:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=90))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    certpath.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keypath.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    keypath.chmod(0o600)
backup = folder / "config.before_securesense.json"
if not backup.exists():
    shutil.copy2(configpath, backup)
config["admin_server"].update(
    listen_url=f"127.0.0.1:{a.admin_port}",
    use_tls=True,
    cert_path=certpath.as_posix(),
    key_path=keypath.as_posix(),
)
config["phish_server"].update(listen_url=f"127.0.0.1:{a.phish_port}", use_tls=False)
configpath.write_text(json.dumps(config, indent=2))
print(
    "Local Gophish prepared. Start the engine from its extracted directory. Do not expose these loopback services publicly."
)
print(
    f"GOPHISH_ADMIN_URL=https://127.0.0.1:{a.admin_port}\nGOPHISH_CA_BUNDLE={certpath.as_posix()}"
)
print(
    f"Campaign URL: http://127.0.0.1:{a.phish_port}; certificate expires after 90 days. Keep the private key local."
)
