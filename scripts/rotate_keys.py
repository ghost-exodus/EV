"""
Rotate the RSA keypair used for signing JWT access tokens.
Archives the current public key to the previous_keys/ folder and
generates a fresh private/public keypair in the root directory.
"""

import os
import shutil
import time
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def rotate_keys():
    print("Initializing key rotation...")
    
    # 1. Ensure archive directory exists
    os.makedirs("previous_keys", exist_ok=True)
    
    # 2. Archive current public key if it exists
    if os.path.exists("public_key.pem"):
        timestamp = int(time.time())
        archive_path = f"previous_keys/public_key_{timestamp}.pem"
        shutil.copy("public_key.pem", archive_path)
        print(f"Archived current public key to {archive_path}")
    else:
        print("No active public key found to archive.")

    # 3. Generate a new private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 4. Serialize keys to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # 5. Overwrite current keys
    with open("private_key.pem", "wb") as f:
        f.write(private_pem)
    print("Overwrote private_key.pem with new private key.")

    with open("public_key.pem", "wb") as f:
        f.write(public_pem)
    print("Overwrote public_key.pem with new public key.")
    print("Key rotation completed successfully.")


if __name__ == "__main__":
    rotate_keys()
