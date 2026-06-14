"""
Generate an RSA keypair for signing and verifying JWT tokens (RS256).
Writes private_key.pem and public_key.pem to the root directory.
"""

import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def generate_keys():
    print("Generating RSA keypair...")
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key to PEM
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write private key
    with open("private_key.pem", "wb") as f:
        f.write(private_pem)
    print("Saved private_key.pem")

    # Write public key
    with open("public_key.pem", "wb") as f:
        f.write(public_pem)
    print("Saved public_key.pem")


if __name__ == "__main__":
    generate_keys()
