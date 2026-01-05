# services/hash_calculator.py
import hashlib

class HashCalculator:
    def compute(self, content, data_blob=None):
        """
        Computes the SHA256 hash for the given content.
        """
        hasher = hashlib.sha256()
        if data_blob:
            hasher.update(data_blob)
        elif content:
            hasher.update(str(content).encode('utf-8'))
        else:
            return None
        return hasher.hexdigest()
