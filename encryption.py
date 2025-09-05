"""
YMERA Enterprise - Encryption Module
Production-Ready Encryption/Decryption System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field

# Third-party imports (alphabetical)
import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from passlib.context import CryptContext
import jwt
from pydantic import BaseModel, Field

# Local imports (alphabetical)
from config.settings import get_settings

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.utils.encryption")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Encryption constants
AES_KEY_SIZE = 32  # 256 bits
AES_IV_SIZE = 16   # 128 bits
RSA_KEY_SIZE = 2048
SALT_SIZE = 32
PBKDF2_ITERATIONS = 100000
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1

# JWT constants
JWT_ALGORITHM = "HS256"
JWT_DEFAULT_EXPIRY = 3600  # 1 hour
JWT_REFRESH_EXPIRY = 604800  # 7 days

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class EncryptionConfig:
    """Configuration for encryption operations"""
    default_algorithm: str = "AES-256-GCM"
    key_derivation: str = "PBKDF2"
    iterations: int = 100000
    use_compression: bool = True
    include_metadata: bool = True

@dataclass
class EncryptionResult:
    """Result of encryption operation"""
    encrypted_data: bytes
    key_id: Optional[str] = None
    algorithm: str = "AES-256-GCM"
    iv: Optional[bytes] = None
    salt: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DecryptionResult:
    """Result of decryption operation"""
    decrypted_data: Union[str, bytes]
    algorithm: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class KeyPair:
    """RSA key pair container"""
    private_key: bytes
    public_key: bytes
    key_size: int
    created_at: datetime = field(default_factory=datetime.utcnow)

class JWTPayload(BaseModel):
    """JWT token payload schema"""
    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    jti: str = Field(..., description="JWT ID")
    type: str = Field(default="access", description="Token type")
    permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ===============================================================================
# CORE ENCRYPTION CLASSES
# ===============================================================================

class EncryptionManager:
    """Main encryption manager for all cryptographic operations"""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        self.config = config or EncryptionConfig()
        self.logger = logger.bind(component="EncryptionManager")
        self._master_key = self._load_or_generate_master_key()
        self._fernet = Fernet(self._master_key)
        self._key_cache: Dict[str, bytes] = {}
        self._initialize_encryption()
    
    def _initialize_encryption(self) -> None:
        """Initialize encryption components"""
        try:
            # Verify master key is working
            test_data = b"encryption_test"
            encrypted = self._fernet.encrypt(test_data)
            decrypted = self._fernet.decrypt(encrypted)
            
            if decrypted != test_data:
                raise RuntimeError("Master key verification failed")
            
            self.logger.info("Encryption manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize encryption manager", error=str(e))
            raise
    
    def _load_or_generate_master_key(self) -> bytes:
        """Load existing master key or generate new one"""
        key_file = Path("keys/master.key")
        
        try:
            if key_file.exists():
                with open(key_file, 'rb') as f:
                    return f.read()
            else:
                # Generate new master key
                key = Fernet.generate_key()
                
                # Ensure directory exists
                key_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Save key with restricted permissions
                with open(key_file, 'wb') as f:
                    f.write(key)
                
                # Set file permissions (owner read/write only)
                key_file.chmod(0o600)
                
                self.logger.info("Generated new master encryption key")
                return key
                
        except Exception as e:
            self.logger.error("Failed to load/generate master key", error=str(e))
            raise
    
    async def encrypt_data(self, 
                          data: Union[str, bytes, Dict[str, Any]],
                          password: Optional[str] = None,
                          key_id: Optional[str] = None) -> EncryptionResult:
        """
        Encrypt data using AES-256-GCM.
        
        Args:
            data: Data to encrypt
            password: Optional password for key derivation
            key_id: Optional key identifier for key cache
            
        Returns:
            EncryptionResult with encrypted data and metadata
        """
        try:
            # Convert data to bytes
            if isinstance(data, dict):
                data_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # Generate encryption key
            if password:
                salt = os.urandom(SALT_SIZE)
                key = self._derive_key_from_password(password, salt)
            else:
                salt = None
                key = self._get_or_generate_key(key_id)
            
            # Generate IV
            iv = os.urandom(AES_IV_SIZE)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv)
            )
            encryptor = cipher.encryptor()
            
            # Encrypt data
            ciphertext = encryptor.update(data_bytes) + encryptor.finalize()
            
            # Get authentication tag
            auth_tag = encryptor.tag
            
            # Combine ciphertext and auth tag
            encrypted_data = ciphertext + auth_tag
            
            self.logger.debug(
                "Data encrypted successfully",
                data_size=len(data_bytes),
                encrypted_size=len(encrypted_data)
            )
            
            return EncryptionResult(
                encrypted_data=encrypted_data,
                key_id=key_id,
                algorithm="AES-256-GCM",
                iv=iv,
                salt=salt,
                metadata={
                    'original_size': len(data_bytes),
                    'encrypted_size': len(encrypted_data),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error("Encryption failed", error=str(e))
            raise
    
    async def decrypt_data(self,
                          encrypted_result: Union[EncryptionResult, bytes],
                          password: Optional[str] = None,
                          key_id: Optional[str] = None,
                          iv: Optional[bytes] = None,
                          salt: Optional[bytes] = None) -> DecryptionResult:
        """
        Decrypt data using AES-256-GCM.
        
        Args:
            encrypted_result: EncryptionResult or raw encrypted bytes
            password: Password used for encryption
            key_id: Key identifier used for encryption
            iv: Initialization vector (required if not EncryptionResult)
            salt: Salt used for key derivation (if password was used)
            
        Returns:
            DecryptionResult with decrypted data
        """
        try:
            # Extract parameters from EncryptionResult if provided
            if isinstance(encrypted_result, EncryptionResult):
                encrypted_data = encrypted_result.encrypted_data
                iv = encrypted_result.iv
                salt = encrypted_result.salt
                key_id = encrypted_result.key_id or key_id
                algorithm = encrypted_result.algorithm
            else:
                encrypted_data = encrypted_result
                algorithm = "AES-256-GCM"
            
            if iv is None:
                raise ValueError("IV is required for decryption")
            
            # Derive or get encryption key
            if password:
                if salt is None:
                    raise ValueError("Salt is required when using password")
                key = self._derive_key_from_password(password, salt)
            else:
                key = self._get_or_generate_key(key_id)
            
            # Split ciphertext and auth tag (last 16 bytes)
            ciphertext = encrypted_data[:-16]
            auth_tag = encrypted_data[-16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, auth_tag)
            )
            decryptor = cipher.decryptor()
            
            # Decrypt data
            decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Try to decode as UTF-8 string, fall back to bytes
            try:
                decrypted_data = decrypted_bytes.decode('utf-8')
                
                # Try to parse as JSON
                try:
                    decrypted_data = json.loads(decrypted_data)
                except json.JSONDecodeError:
                    pass  # Keep as string
                    
            except UnicodeDecodeError:
                decrypted_data = decrypted_bytes
            
            self.logger.debug(
                "Data decrypted successfully",
                encrypted_size=len(encrypted_data),
                decrypted_size=len(decrypted_bytes)
            )
            
            return DecryptionResult(
                decrypted_data=decrypted_data,
                algorithm=algorithm,
                metadata={
                    'decrypted_size': len(decrypted_bytes),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error("Decryption failed", error=str(e))
            raise
    
    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        if self.config.key_derivation == "PBKDF2":
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=AES_KEY_SIZE,
                salt=salt,
                iterations=self.config.iterations
            )
        elif self.config.key_derivation == "scrypt":
            kdf = Scrypt(
                algorithm=hashes.SHA256(),
                length=AES_KEY_SIZE,
                salt=salt,
                n=SCRYPT_N,
                r=SCRYPT_R,
                p=SCRYPT_P
            )
        else:
            raise ValueError(f"Unsupported key derivation: {self.config.key_derivation}")
        
        return kdf.derive(password.encode('utf-8'))
    
    def _get_or_generate_key(self, key_id: Optional[str]) -> bytes:
        """Get existing key or generate new one"""
        if key_id and key_id in self._key_cache:
            return self._key_cache[key_id]
        
        # Generate new key
        key = os.urandom(AES_KEY_SIZE)
        
        if key_id:
            self._key_cache[key_id] = key
        
        return key
    
    def generate_rsa_keypair(self, key_size: int = RSA_KEY_SIZE) -> KeyPair:
        """Generate RSA key pair"""
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize keys
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            self.logger.info("RSA key pair generated", key_size=key_size)
            
            return KeyPair(
                private_key=private_pem,
                public_key=public_pem,
                key_size=key_size
            )
            
        except Exception as e:
            self.logger.error("RSA key generation failed", error=str(e))
            raise
    
    def rsa_encrypt(self, data: Union[str, bytes], public_key_pem: bytes) -> bytes:
        """Encrypt data using RSA public key"""
        try:
            # Load public key
            public_key = serialization.load_pem_public_key(public_key_pem)
            
            # Convert data to bytes
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Encrypt data
            encrypted = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return encrypted
            
        except Exception as e:
            self.logger.error("RSA encryption failed", error=str(e))
            raise
    
    def rsa_decrypt(self, encrypted_data: bytes, private_key_pem: bytes) -> bytes:
        """Decrypt data using RSA private key"""
        try:
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=None
            )
            
            # Decrypt data
            decrypted = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted
            
        except Exception as e:
            self.logger.error("RSA decryption failed", error=str(e))
            raise
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        try:
            return pwd_context.hash(password)
        except Exception as e:
            self.logger.error("Password hashing failed", error=str(e))
            raise
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return pwd_context.verify(password, hashed_password)
        except Exception as e:
            self.logger.error("Password verification failed", error=str(e))
            return False
    
    def create_jwt_token(self,
                        subject: str,
                        permissions: Optional[List[str]] = None,
                        expires_in: int = JWT_DEFAULT_EXPIRY,
                        token_type: str = "access",
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create JWT token"""
        try:
            now = int(time.time())
            token_id = secrets.token_urlsafe(16)
            
            payload = JWTPayload(
                sub=subject,
                exp=now + expires_in,
                iat=now,
                jti=token_id,
                type=token_type,
                permissions=permissions or [],
                metadata=metadata or {}
            )
            
            # Use master key for JWT signing
            secret_key = base64.urlsafe_b64encode(self._master_key).decode('utf-8')
            
            token = jwt.encode(
                payload.dict(),
                secret_key,
                algorithm=JWT_ALGORITHM
            )
            
            self.logger.debug(
                "JWT token created",
                subject=subject,
                token_type=token_type,
                expires_in=expires_in
            )
            
            return token
            
        except Exception as e:
            self.logger.error("JWT token creation failed", error=str(e))
            raise
    
    def verify_jwt_token(self, token: str) -> JWTPayload:
        """Verify and decode JWT token"""
        try:
            # Use master key for JWT verification
            secret_key = base64.urlsafe_b64encode(self._master_key).decode('utf-8')
            
            decoded = jwt.decode(
                token,
                secret_key,
                algorithms=[JWT_ALGORITHM]
            )
            
            payload = JWTPayload(**decoded)
            
            self.logger.debug(
                "JWT token verified",
                subject=payload.sub,
                token_type=payload.type
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logger.warning("JWT token expired")
            raise
        except jwt.InvalidTokenError as e:
            self.logger.warning("JWT token invalid", error=str(e))
            raise
        except Exception as e:
            self.logger.error("JWT token verification failed", error=str(e))
            raise
    
    async def encrypt_file(self, 
                          file_path: Path,
                          output_path: Optional[Path] = None,
                          password: Optional[str] = None) -> Path:
        """Encrypt a file"""
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if output_path is None:
                output_path = file_path.with_suffix(file_path.suffix + '.enc')
            
            # Read file data
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Encrypt data
            encryption_result = await self.encrypt_data(file_data, password=password)
            
            # Create file header with metadata
            header = {
                'version': '1.0',
                'algorithm': encryption_result.algorithm,
                'iv': base64.b64encode(encryption_result.iv).decode('utf-8') if encryption_result.iv else None,
                'salt': base64.b64encode(encryption_result.salt).decode('utf-8') if encryption_result.salt else None,
                'metadata': encryption_result.metadata
            }
            
            header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
            header_size = len(header_bytes).to_bytes(4, byteorder='big')
            
            # Write encrypted file
            with open(output_path, 'wb') as f:
                f.write(header_size)
                f.write(header_bytes)
                f.write(encryption_result.encrypted_data)
            
            self.logger.info(
                "File encrypted successfully",
                input_file=str(file_path),
                output_file=str(output_path),
                original_size=len(file_data),
                encrypted_size=len(encryption_result.encrypted_data)
            )
            
            return output_path
            
        except Exception as e:
            self.logger.error("File encryption failed", error=str(e))
            raise
    
    async def decrypt_file(self,
                          encrypted_file_path: Path,
                          output_path: Optional[Path] = None,
                          password: Optional[str] = None) -> Path:
        """Decrypt a file"""
        try:
            if not encrypted_file_path.exists():
                raise FileNotFoundError(f"Encrypted file not found: {encrypted_file_path}")
            
            if output_path is None:
                # Remove .enc extension if present
                if encrypted_file_path.suffix == '.enc':
                    output_path = encrypted_file_path.with_suffix('')
                else:
                    output_path = encrypted_file_path.with_suffix('.dec')
            
            # Read encrypted file
            with open(encrypted_file_path, 'rb') as f:
                # Read header size
                header_size_bytes = f.read(4)
                header_size = int.from_bytes(header_size_bytes, byteorder='big')
                
                # Read header
                header_bytes = f.read(header_size)
                header = json.loads(header_bytes.decode('utf-8'))
                
                # Read encrypted data
                encrypted_data = f.read()
            
            # Extract metadata
            iv = base64.b64decode(header['iv']) if header['iv'] else None
            salt = base64.b64decode(header['salt']) if header['salt'] else None
            
            # Decrypt data
            decryption_result = await self.decrypt_data(
                encrypted_data,
                password=password,
                iv=iv,
                salt=salt
            )
            
            # Write decrypted file
            with open(output_path, 'wb') as f:
                if isinstance(decryption_result.decrypted_data, str):
                    f.write(decryption_result.decrypted_data.encode('utf-8'))
                else:
                    f.write(decryption_result.decrypted_data)
            
            self.logger.info(
                "File decrypted successfully",
                input_file=str(encrypted_file_path),
                output_file=str(output_path)
            )
            
            return output_path
            
        except Exception as e:
            self.logger.error("File decryption failed", error=str(e))
            raise
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    def generate_api_key(self, prefix: str = "ymera") -> str:
        """Generate API key with prefix"""
        token = self.generate_secure_token(32)
        return f"{prefix}_{token}"
    
    def compute_hmac(self, data: Union[str, bytes], key: Union[str, bytes]) -> str:
        """Compute HMAC-SHA256 of data"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        if isinstance(key, str):
            key = key.encode('utf-8')
        
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    
    def verify_hmac(self, data: Union[str, bytes], key: Union[str, bytes], signature: str) -> bool:
        """Verify HMAC signature"""
        computed_signature = self.compute_hmac(data, key)
        return hmac.compare_digest(computed_signature, signature)

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

# Global encryption manager instance
_encryption_manager: Optional[EncryptionManager] = None

def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager

async def encrypt_data(data: Union[str, bytes, Dict[str, Any]], password: Optional[str] = None) -> EncryptionResult:
    """Convenience function to encrypt data"""
    manager = get_encryption_manager()
    return await manager.encrypt_data(data, password=password)

async def decrypt_data(encrypted_result: Union[EncryptionResult, bytes], 
                      password: Optional[str] = None,
                      **kwargs) -> DecryptionResult:
    """Convenience function to decrypt data"""
    manager = get_encryption_manager()
    return await manager.decrypt_data(encrypted_result, password=password, **kwargs)

def generate_key() -> str:
    """Generate a new encryption key"""
    return base64.urlsafe_b64encode(os.urandom(AES_KEY_SIZE)).decode('utf-8')

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    manager = get_encryption_manager()
    return manager.hash_password(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    manager = get_encryption_manager()
    return manager.verify_password(password, hashed_password)

def create_jwt_token(subject: str, 
                    permissions: Optional[List[str]] = None,
                    expires_in: int = JWT_DEFAULT_EXPIRY) -> str:
    """Create JWT token"""
    manager = get_encryption_manager()
    return manager.create_jwt_token(subject, permissions, expires_in)

def verify_jwt_token(token: str) -> JWTPayload:
    """Verify JWT token"""
    manager = get_encryption_manager()
    return manager.verify_jwt_token(token)

async def encrypt_file(file_path: Union[str, Path], 
                      password: Optional[str] = None) -> Path:
    """Encrypt a file"""
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    manager = get_encryption_manager()
    return await manager.encrypt_file(file_path, password=password)

async def decrypt_file(encrypted_file_path: Union[str, Path],
                      password: Optional[str] = None) -> Path:
    """Decrypt a file"""
    if isinstance(encrypted_file_path, str):
        encrypted_file_path = Path(encrypted_file_path)
    
    manager = get_encryption_manager()
    return await manager.decrypt_file(encrypted_file_path, password=password)

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "EncryptionManager",
    "EncryptionConfig",
    "EncryptionResult",
    "DecryptionResult",
    "KeyPair",
    "JWTPayload",
    "get_encryption_manager",
    "encrypt_data",
    "decrypt_data",
    "generate_key",
    "hash_password",
    "verify_password",
    "create_jwt_token",
    "verify_jwt_token",
    "encrypt_file",
    "decrypt_file"
]