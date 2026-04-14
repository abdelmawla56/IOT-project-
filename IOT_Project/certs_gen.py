import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import os

def create_ca():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"IOT-Project-CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"IoT-Root-CA"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(key, hashes.SHA256())
    
    return cert, key

import ipaddress

def create_cert(ca_cert, ca_key, common_name, is_server=True):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"IOT-Project"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    )
    
    if is_server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.DNSName(u"hivemq"),
                x509.DNSName(u"hivemq-backbone"),
                x509.IPAddress(ipaddress.IPv4Address(u"127.0.0.1")),
            ]),
            critical=False,
        )
    
    cert = builder.sign(ca_key, hashes.SHA256())
    return cert, key

def save_pem(cert, key, name, path):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, f"{name}.crt"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(os.path.join(path, f"{name}.key"), "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

if __name__ == "__main__":
    print("Generating Certificates...")
    ca_cert, ca_key = create_ca()
    
    # Server (HiveMQ)
    server_cert, server_key = create_cert(ca_cert, ca_key, u"hivemq")
    
    # Client (World Engine / App)
    client_cert, client_key = create_cert(ca_cert, ca_key, u"iot-client", is_server=False)
    
    # Save to certs directory
    cert_dir = "certs"
    save_pem(ca_cert, ca_key, "ca", cert_dir)
    save_pem(server_cert, server_key, "server", cert_dir)
    save_pem(client_cert, client_key, "client", cert_dir)
    
    print(f"Certificates generated in {cert_dir}/")
