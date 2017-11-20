from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import ec
import os
import base64


def get_nounce(byte_size):
    return os.urandom(byte_size)


def get_hash_algorithm(algorithm):
    hash_algorithms = {
        'SHA256': hashes.SHA256(),
        'SHA384': hashes.SHA384()
    }

    return hash_algorithms[algorithm] \
        if algorithm in hash_algorithms.keys() else None


def get_aes_mode(mode, iv):
    cipher_modes = {
        'CFB': modes.CFB(iv),
        'CTR': modes.CTR(iv)
    }

    return cipher_modes[mode] if mode in cipher_modes.keys() else None


def get_padding_algorithm(algorithm):
    paddings = {
        'OAEP': padding.OAEP,
        'PKCS1v15': padding.OAEP
    }

    return paddings[algorithm] if algorithm in paddings.keys() else None



def generate_rsa_keypair(size):
    if size != 2048:
        return None

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=size,
        backend=default_backend()
    )

    return private_key, private_key.public_key()


def generate_aes_cipher(key, mode, iv=None):
    if len(key) * 8 not in [192, 256]:
        return None

    iv = os.urandom(16) if iv is None else iv
    cipher_mode = get_aes_mode(mode, iv)
    cipher = Cipher(algorithms.AES(key), cipher_mode, backend=default_backend())

    return cipher, iv


def derive_key(password, length, hash_algorithm, salt):
    if password is None:
        return None

    if length * 8 not in [192, 256]:
        return None

    h = get_hash_algorithm(hash_algorithm)

    if salt is None:
        return None

    info = b"hkdf-password-derivation"
    hkdf = HKDF(
        algorithm=h,
        length=length,
        salt=salt,
        info=info,
        backend=default_backend()
    )

    password = password if isinstance(password, bytes) else password.encode()
    key = hkdf.derive(password)

    return key


def digest_payload(payload, hash_algorithm):
    if payload is None:
        return None

    h = get_hash_algorithm(hash_algorithm)

    payload = payload if isinstance(payload, bytes) else payload.encode()
    digest = hashes.Hash(h, backend=default_backend())
    digest.update(payload)
    hashed_payload = digest.finalize()

    return hashed_payload


def generate_ecdh_keypair():
    private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
    return private_key, private_key.public_key()


def derive_key_from_ecdh(private_key, peer_pubkey, priv_salt, pub_salt,
                         length, hash_algorithm):
    if private_key is None or peer_pubkey is None:
        return None

    shared_secret = private_key.exchange(ec.ECDH(), peer_pubkey)
    return derive_key(shared_secret, length, hash_algorithm, priv_salt+pub_salt)


def save_to_ciphered_file(password, length, hash_algorithm,
                          aes_mode, payload, uuid):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    f = open(os.path.join(dir_path, 'keys/' + uuid + '_rsa'), 'wb')

    # Derive key from password and generate AES cipher object
    salt = os.urandom(16)
    key = derive_key(password, length, hash_algorithm, salt)
    cipher, iv = generate_aes_cipher(key, aes_mode)

    # Cipher payload
    encryptor = cipher.encryptor()
    ciphered_payload = encryptor.update(payload) + encryptor.finalize()

    # Save to file
    file_payload = base64.b64encode(salt + '\n\n' + iv) + b'\n\n' + \
            ciphered_payload

    f.write(file_payload)


def read_from_ciphered_file(password, length, hash_algorithm, aes_mode, uuid):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    f = open(os.path.join(dir_path, 'keys/' + uuid + '_rsa'), 'rb')
    file_payload = f.read()

    info = file_payload.split(b'\n\n')
    if len(info) != 2:
        return None

    salt_iv = base64.b64decode(info[0]).split('\n\n')
    ciphered_payload = info[1]

    # Derive key from password and generate AES cipher object
    key = derive_key(password, length, hash_algorithm, salt_iv[0])
    cipher, iv = generate_aes_cipher(key, aes_mode, salt_iv[1])

    # Decipher payload
    decryptor = cipher.decryptor()
    payload = decryptor.update(ciphered_payload) + decryptor.finalize()
    return payload


"""
    Assymetric operations
"""


def rsa_sign(private_key, payload, hash_algorithm):
    h = get_hash_algorithm(hash_algorithm)
    signature = private_key.sign(
        payload,
        padding.PSS(
            mgf=padding.MGF1(h),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        h
    )
    return signature


def rsa_verify(public_key, signature, payload, hash_algorithm):
    h = get_hash_algorithm(hash_algorithm)
    return public_key.verify(
        signature,
        payload,
        padding.PSS(
            mgf=padding.MGF1(h),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        h
    )


def rsa_cipher(public_key, payload, hash_algorithm, padding_algorithm):
    h = get_hash_algorithm(hash_algorithm)
    p = get_padding_algorithm(padding_algorithm)
    ciphertext = public_key.encrypt(
        payload,
        p(
            mgf=padding.MGF1(algorithm=h),
            algorithm=h,
            label=None
        )
    )
    return ciphertext


def rsa_decipher(private_key, ciphertext, hash_algorithm, padding_algorithm):
    h = get_hash_algorithm(hash_algorithm)
    p = get_padding_algorithm(padding_algorithm)
    payload = private_key.decrypt(
        ciphertext,
        p(
            mgf=padding.MGF1(algorithm=h),
            algorithm=h,
            label=None
        )
    )
    return payload