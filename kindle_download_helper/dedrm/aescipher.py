import base64
import hmac
import json
import logging
import os
import pathlib
import struct
from hashlib import sha256
from typing import Dict, Optional, Tuple, Union

from pbkdf2 import PBKDF2
from pyaes import AESModeOfOperationCBC, Decrypter, Encrypter

logger = logging.getLogger("kindle.aescipher")

BLOCK_SIZE: int = 16  # the AES block size


def aes_cbc_encrypt(
    key: bytes, iv: bytes, data: str, padding: str = "default"
) -> bytes:
    """Encrypts data in cipher block chaining mode of operation.

    Args:
        key: The AES key.
        iv: The initialization vector.
        data: The data to encrypt.
        padding: Can be ``default`` or ``none`` (Default: default)

    Returns:
        The encrypted data.
    """
    encrypter = Encrypter(AESModeOfOperationCBC(key, iv), padding=padding)
    encrypted = encrypter.feed(data) + encrypter.feed()
    return encrypted


def aes_cbc_decrypt(
    key: bytes, iv: bytes, encrypted_data: bytes, padding: str = "default"
) -> bytes:
    """Decrypts data encrypted in cipher block chaining mode of operation.

    Args:
        key: The AES key used at encryption.
        iv: The initialization vector used at encryption.
        encrypted_data: The encrypted data to decrypt.
        padding: Can be ``default`` or ``none`` (Default: default)

    Returns:
        The decrypted data.
    """
    decrypter = Decrypter(AESModeOfOperationCBC(key, iv), padding=padding)
    decrypted = decrypter.feed(encrypted_data) + decrypter.feed()
    return decrypted


def create_salt(salt_marker: bytes, kdf_iterations: int) -> Tuple[bytes, bytes]:
    """Creates the header and salt for the :func:`derive_from_pbkdf2` function.

    The header consist of the number of KDF iterations encoded as a big-endian
    word bytes wrapped by ``salt_marker`` on both sides.
    The random salt has a length of 16 bytes (the AES block size) minus the
    length of the salt header.
    """
    header = salt_marker + struct.pack(">H", kdf_iterations) + salt_marker
    salt = os.urandom(BLOCK_SIZE - len(header))
    return header, salt


def pack_salt(header: bytes, salt: bytes) -> bytes:
    """Combines the header and salt created by :func:`create_salt` function."""
    return header + salt


def unpack_salt(packed_salt: bytes, salt_marker: bytes) -> Tuple[bytes, int]:
    """Unpack salt and kdf_iterations from previous created and packed salt."""
    mlen = len(salt_marker)
    hlen = mlen * 2 + 2

    if not (
        packed_salt[:mlen] == salt_marker
        and packed_salt[mlen + 2 : hlen] == salt_marker
    ):
        raise ValueError("Check salt_marker.")

    kdf_iterations = struct.unpack(">H", packed_salt[mlen : mlen + 2])[0]
    salt = packed_salt[hlen:]
    return salt, kdf_iterations


def derive_from_pbkdf2(
    password: str, *, key_size: int, salt: bytes, kdf_iterations: int, hashmod, mac
) -> bytes:
    """Creates an AES key with the :class:`PBKDF2` key derivation class."""
    kdf = PBKDF2(password, salt, min(kdf_iterations, 65535), hashmod, mac)
    return kdf.read(key_size)


class AESCipher:
    """Encrypt/Decrypt data using password to generate key.

    The encryption algorithm used is symmetric AES in cipher-block chaining
    (CBC) mode.

    The key is derived via the PBKDF2 key derivation function (KDF) from the
    password and a random salt of 16 bytes (the AES block size) minus the
    length of the salt header (see below).
    The hash function used by PBKDF2 is SHA256 per default. You can pass a
    different hash function module via the ``hashmod`` argument. The module
    must adhere to the Python API for Cryptographic Hash Functions (PEP 247).
    PBKDF2 uses a number of iterations of the hash function to derive the key,
    which can be set via the ``kdf_iterations`` keyword argument. The default
    number is 1000 and the maximum 65535.
    The header and the salt are written to the first block of the encrypted
    output (bytes mode) or written as key/value pairs (dict mode). The header
    consist of the number of KDF iterations encoded as a big-endian word bytes
    wrapped by ``salt_marker`` on both sides. With the default value of
    ``salt_marker = b'$'``, the header size is thus 4 and the salt 12 bytes.
    The salt marker must be a byte string of 1-6 bytes length.
    The last block of the encrypted output is padded with up to 16 bytes, all
    having the value of the length of the padding.
    All values in dict mode are written as base64 encoded string.

    Attributes:
        password: The password for encryption/decryption.
        key_size: The size of the key. Can be ``16``, ``24`` or ``32``
            (Default: 32).
        salt_marker: The salt marker with max. length of 6 bytes (Default: $).
        kdf_iterations: The number of iterations of the hash function to
            derive the key (Default: 1000).
        hashmod: The hash method to use (Default: sha256).
        mac: The mac module to use (Default: hmac).

    Args:
        password: The password for encryption/decryption.
        key_size: The size of the key. Can be ``16``, ``24`` or ``32``
            (Default: 32).
        salt_marker: The salt marker with max. length of 6 bytes (Default: $).
        kdf_iterations: The number of iterations of the hash function to
            derive the key (Default: 1000).
        hashmod: The hash method to use (Default: sha256).
        mac: The mac module to use (Default: hmac).

    Raises:
        ValueError: If `salt_marker` is not one to six bytes long.
        ValueError: If `kdf_iterations` is greater than 65535.
        TypeError: If type of `salt_marker` is not bytes.
    """

    def __init__(
        self,
        password: str,
        *,
        key_size: int = 32,
        salt_marker: bytes = b"$",
        kdf_iterations: int = 1000,
        hashmod=sha256,
        mac=hmac
    ) -> None:
        if not 1 <= len(salt_marker) <= 6:
            raise ValueError("The salt_marker must be one to six bytes long.")

        if not isinstance(salt_marker, bytes):
            raise TypeError("salt_marker must be a bytes instance.")

        if kdf_iterations >= 65536:
            raise ValueError("kdf_iterations must be <= 65535.")

        self.password = password
        self.key_size = key_size
        self.hashmod = hashmod
        self.mac = mac
        self.salt_marker = salt_marker
        self.kdf_iterations = kdf_iterations

    def _encrypt(self, data: str) -> Tuple[bytes, bytes, bytes]:
        header, salt = create_salt(self.salt_marker, self.kdf_iterations)
        key = derive_from_pbkdf2(
            password=self.password,
            key_size=self.key_size,
            salt=salt,
            kdf_iterations=self.kdf_iterations,
            hashmod=self.hashmod,
            mac=self.mac,
        )
        iv = os.urandom(BLOCK_SIZE)
        encrypted_data = aes_cbc_encrypt(key, iv, data)
        return pack_salt(header, salt), iv, encrypted_data

    def _decrypt(self, salt: bytes, iv: bytes, encrypted_data: bytes) -> str:
        try:
            salt, kdf_iterations = unpack_salt(salt, self.salt_marker)
        except ValueError:
            kdf_iterations = self.kdf_iterations

        key = derive_from_pbkdf2(
            password=self.password,
            key_size=self.key_size,
            salt=salt,
            kdf_iterations=kdf_iterations,
            hashmod=self.hashmod,
            mac=self.mac,
        )
        return aes_cbc_decrypt(key, iv, encrypted_data).decode("utf-8")

    def to_dict(self, data: str) -> Dict[str, str]:
        """Encrypts data in dict style.

        The output dict contains the base64 encoded (packed) salt, iv and
        ciphertext key/value pairs and an info key/value pair with additional
        encryption information.

        Args:
            data: The data to encrypt.

        Returns:
            The encrypted data in dict style.
        """
        salt, iv, encrypted_data = self._encrypt(data)

        return {
            "salt": base64.b64encode(salt).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8"),
            "ciphertext": base64.b64encode(encrypted_data).decode("utf-8"),
            "info": "base64-encoded AES-CBC-256 of JSON object",
        }

    def from_dict(self, data: dict) -> str:
        """Decrypts data previously encrypted with :meth:`AESCipher.to_dict`.

        Args:
            data: The encrypted data in json style.

        Returns:
            The decrypted data.
        """
        salt = base64.b64decode(data["salt"])
        iv = base64.b64decode(data["iv"])
        encrypted_data = base64.b64decode(data["ciphertext"])
        return self._decrypt(salt, iv, encrypted_data)

    def to_bytes(self, data: str) -> bytes:
        """Encrypts data in bytes style.

        The output bytes contains the (packed) salt, iv and ciphertext.

        Args:
            data: The data to encrypt.

        Returns:
            The encrypted data in dict style.
        """
        salt, iv, encrypted_data = self._encrypt(data)
        return salt + iv + encrypted_data

    def from_bytes(self, data: bytes) -> str:
        """Decrypts data previously encrypted with :meth:`AESCipher.to_bytes`.

        Args:
            data: The encrypted data in bytes style.

        Returns:
            The decrypted data.
        """
        bs = BLOCK_SIZE
        salt = data[:bs]
        iv = data[bs : 2 * bs]
        encrypted_data = data[2 * bs :]
        return self._decrypt(salt, iv, encrypted_data)

    def to_file(
        self,
        data: str,
        filename: pathlib.Path,
        encryption: str = "json",
        indent: int = 4,
    ) -> None:
        """Encrypts and saves data to given file.

        Args:
            data: The data to encrypt.
            filename: The name of the file to save the data to.
            encryption: The encryption style to use. Can be ``json`` or
                ``bytes`` (Default: json).
            indent: The indention level when saving in json style
                (Default: 4).

        Raises:
            ValueError: If `encryption` is not ``json`` or ``bytes``.
        """
        if encryption == "json":
            encrypted_dict = self.to_dict(data)
            data_json = json.dumps(encrypted_dict, indent=indent)
            filename.write_text(data_json)

        elif encryption == "bytes":
            encrypted_data = self.to_bytes(data)
            filename.write_bytes(encrypted_data)

        else:
            raise ValueError('encryption must be "json" or "bytes"..')

    def from_file(self, filename: pathlib.Path, encryption: str = "json") -> str:
        """Loads and decrypts data from given file.

        Args:
            filename: The name of the file to load the data from.
            encryption: The encryption style which where used. Can be ``json``
                or ``bytes`` (Default: json).

        Returns:
            The decrypted data.

        Raises:
            ValueError: If `encryption` is not ``json`` or ``bytes``.
        """
        if encryption == "json":
            encrypted_json = filename.read_text()
            encrypted_dict = json.loads(encrypted_json)
            return self.from_dict(encrypted_dict)

        elif encryption == "bytes":
            encrypted_data = filename.read_bytes()
            return self.from_bytes(encrypted_data)

        else:
            raise ValueError('encryption must be "json" or "bytes".')


def detect_file_encryption(filename: pathlib.Path) -> Optional[str]:
    """Detect the encryption format from an authentication file.

    Args:
        filename: The name for the authentication file.

    Returns:
        ``False`` if file is not encrypted otherwise the encryption format.
    """
    file = filename.read_bytes()
    encryption = None

    try:
        file = json.loads(file)
        if "adp_token" in file:
            encryption = False
        elif "ciphertext" in file:
            encryption = "json"
    except UnicodeDecodeError:
        encryption = "bytes"

    return encryption


def remove_file_encryption(
    source: Union[str, pathlib.Path],
    target: Union[str, pathlib.Path],
    password: str,
    **kwargs
) -> None:
    """Removes the encryption from an authentication file.

    Please try to load the authentication file with
    :meth:`audible.Authenticator.from_file` and save the authentication data
    as a unencrypted file first. Use this function as fallback if you ran into
    any error.

    Args:
        source: The encrypted authentication file.
        target: The filename for the decrypted file.
        password: The password for the encrypted authentication file.

    Raises:
        ValueError: If ``source`` is not encrypted.
    """
    source_file = pathlib.Path(source)
    encryption = detect_file_encryption(source_file)

    if not encryption:
        raise ValueError("file is not encrypted")

    crypter = AESCipher(password, **kwargs)
    decrypted = crypter.from_file(source_file, encryption=encryption)
    pathlib.Path(target).write_text(decrypted)
