"""
YMERA Enterprise - File Validator
Production-Ready Security Scanning & Validation - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import magic
import mimetypes
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from enum import Enum

# Third-party imports (alphabetical)
import aiofiles
import defusedxml.ElementTree as ET
import structlog
from fastapi import UploadFile, HTTPException
from PIL import Image, ImageFile
from pydantic import BaseModel, Field, validator
import yara

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.threat_detector import ThreatDetector

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File size limits (bytes)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MIN_FILE_SIZE = 1  # 1 byte
MAX_FILENAME_LENGTH = 255
MAX_PATH_LENGTH = 4096

# Security scanning limits
SCAN_TIMEOUT = 30  # seconds
MAX_SCAN_THREADS = 4
QUARANTINE_RETENTION_DAYS = 30

# Allowed file extensions by category
ALLOWED_EXTENSIONS = {
    'documents': {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.odg', '.ods'},
    'images': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'},
    'spreadsheets': {'.xls', '.xlsx', '.csv', '.ods'},
    'presentations': {'.ppt', '.pptx', '.odp'},
    'archives': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'},
    'code': {'.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sql'},
    'media': {'.mp4', '.avi', '.mov', '.mp3', '.wav', '.flac', '.m4a'},
    'fonts': {'.ttf', '.otf', '.woff', '.woff2'},
    'ebooks': {'.epub', '.mobi', '.azw', '.azw3'}
}

# Dangerous file extensions (always blocked)
DANGEROUS_EXTENSIONS = {
    '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs', '.js', '.jar',
    '.app', '.deb', '.pkg', '.dmg', '.iso', '.msi', '.cab', '.dll', '.sys',
    '.scpt', '.workflow', '.action', '.sh', '.ps1', '.psm1', '.psd1'
}

# MIME type validation
ALLOWED_MIME_TYPES = {
    'application/pdf', 'text/plain', 'text/csv', 'text/html', 'text/css',
    'application/json', 'application/xml', 'text/xml',
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp', 'image/svg+xml',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
    'video/mp4', 'video/quicktime', 'video/x-msvideo',
    'audio/mpeg', 'audio/wav', 'audio/x-flac'
}

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class ValidationSeverity(Enum):
    """Validation issue severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ValidationCategory(Enum):
    """Validation categories"""
    FILE_TYPE = "file_type"
    CONTENT_SECURITY = "content_security"
    MALWARE_SCAN = "malware_scan"
    SIZE_VALIDATION = "size_validation"
    NAME_VALIDATION = "name_validation"
    STRUCTURE_VALIDATION = "structure_validation"

@dataclass
class ValidationConfig:
    """Configuration for file validation"""
    enable_virus_scan: bool = True
    enable_content_scan: bool = True
    enable_metadata_extraction: bool = True
    max_file_size: int = MAX_FILE_SIZE
    min_file_size: int = MIN_FILE_SIZE
    allowed_extensions: Set[str] = field(default_factory=lambda: set().union(*ALLOWED_EXTENSIONS.values()))
    dangerous_extensions: Set[str] = field(default_factory=lambda: DANGEROUS_EXTENSIONS.copy())
    quarantine_dir: str = "/tmp/ymera_quarantine"
    yara_rules_dir: str = "/etc/ymera/yara_rules"
    clamav_enabled: bool = False

class ValidationIssue(BaseModel):
    """Individual validation issue"""
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    suggested_action: Optional[str] = None

class ValidationResult(BaseModel):
    """Complete validation result"""
    is_valid: bool
    file_size: int
    mime_type: str
    detected_extension: str
    issues: List[ValidationIssue] = field(default_factory=list)
    security_score: float  # 0.0 (unsafe) to 1.0 (safe)
    scan_duration: float
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    quarantined: bool = False
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True

class FileSignature(BaseModel):
    """File signature/magic number information"""
    magic_bytes: str
    mime_type: str
    extension: str
    confidence: float

class ThreatIndicator(BaseModel):
    """Security threat indicator"""
    indicator_type: str
    severity: ValidationSeverity
    description: str
    risk_score: float
    mitigation: str

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileSignatureAnalyzer:
    """Analyze file signatures and magic numbers"""
    
    def __init__(self):
        self.logger = logger.bind(component="signature_analyzer")
        
        # Common file signatures (magic numbers)
        self.signatures = {
            b'\x89PNG\r\n\x1a\n': ('image/png', '.png', 1.0),
            b'\xff\xd8\xff': ('image/jpeg', '.jpg', 1.0),
            b'GIF87a': ('image/gif', '.gif', 1.0),
            b'GIF89a': ('image/gif', '.gif', 1.0),
            b'RIFF': ('image/webp', '.webp', 0.8),  # Could also be WAV
            b'%PDF': ('application/pdf', '.pdf', 1.0),
            b'PK\x03\x04': ('application/zip', '.zip', 0.9),
            b'PK\x05\x06': ('application/zip', '.zip', 0.9),
            b'PK\x07\x08': ('application/zip', '.zip', 0.9),
            b'Rar!\x1a\x07\x00': ('application/x-rar-compressed', '.rar', 1.0),
            b'\x7fELF': ('application/x-executable', '.elf', 1.0),
            b'MZ': ('application/x-executable', '.exe', 1.0),
            b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': ('application/vnd.ms-office', '.doc', 0.8),
        }
    
    async def analyze_signature(self, file_data: bytes) -> FileSignature:
        """Analyze file signature from raw data"""
        try:
            # Check against known signatures
            for signature, (mime_type, extension, confidence) in self.signatures.items():
                if file_data.startswith(signature):
                    return FileSignature(
                        magic_bytes=signature.hex(),
                        mime_type=mime_type,
                        extension=extension,
                        confidence=confidence
                    )
            
            # Fallback to python-magic
            mime_type = magic.from_buffer(file_data, mime=True)
            extension = mimetypes.guess_extension(mime_type) or '.bin'
            
            return FileSignature(
                magic_bytes=file_data[:16].hex(),
                mime_type=mime_type,
                extension=extension,
                confidence=0.7
            )
            
        except Exception as e:
            self.logger.error("Signature analysis failed", error=str(e))
            return FileSignature(
                magic_bytes="",
                mime_type="application/octet-stream",
                extension=".bin",
                confidence=0.0
            )

class ContentSecurityScanner:
    """Scan file content for security threats"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        self.logger = logger.bind(component="content_scanner")
        self.yara_rules = None
        self._load_yara_rules()
    
    def _load_yara_rules(self) -> None:
        """Load YARA rules for malware detection"""
        try:
            rules_dir = Path(self.config.yara_rules_dir)
            if rules_dir.exists():
                rule_files = list(rules_dir.glob("*.yar"))
                if rule_files:
                    # Compile YARA rules
                    rules_dict = {}
                    for rule_file in rule_files:
                        rules_dict[rule_file.stem] = str(rule_file)
                    
                    self.yara_rules = yara.compile(filepaths=rules_dict)
                    self.logger.info("YARA rules loaded", rule_count=len(rule_files))
        except Exception as e:
            self.logger.warning("Failed to load YARA rules", error=str(e))
    
    async def scan_content(self, file_path: Path) -> List[ThreatIndicator]:
        """Scan file content for threats"""
        threats = []
        
        try:
            # Read file content
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read(1024 * 1024)  # Read first 1MB
            
            # YARA rule scanning
            if self.yara_rules:
                yara_threats = await self._scan_with_yara(content)
                threats.extend(yara_threats)
            
            # Pattern-based scanning
            pattern_threats = await self._scan_patterns(content)
            threats.extend(pattern_threats)
            
            # Embedded content scanning
            embedded_threats = await self._scan_embedded_content(file_path)
            threats.extend(embedded_threats)
            
        except Exception as e:
            self.logger.error("Content scanning failed", file_path=str(file_path), error=str(e))
            threats.append(ThreatIndicator(
                indicator_type="scan_error",
                severity=ValidationSeverity.WARNING,
                description=f"Content scan failed: {str(e)}",
                risk_score=0.3,
                mitigation="Manual review recommended"
            ))
        
        return threats
    
    async def _scan_with_yara(self, content: bytes) -> List[ThreatIndicator]:
        """Scan content with YARA rules"""
        threats = []
        
        try:
            matches = self.yara_rules.match(data=content)
            for match in matches:
                severity = ValidationSeverity.CRITICAL
                risk_score = 0.9
                
                if 'suspicious' in match.rule.lower():
                    severity = ValidationSeverity.WARNING
                    risk_score = 0.6
                elif 'potential' in match.rule.lower():
                    severity = ValidationSeverity.WARNING
                    risk_score = 0.4
                
                threats.append(ThreatIndicator(
                    indicator_type="yara_match",
                    severity=severity,
                    description=f"YARA rule match: {match.rule}",
                    risk_score=risk_score,
                    mitigation="Quarantine and review"
                ))
        
        except Exception as e:
            self.logger.error("YARA scanning failed", error=str(e))
        
        return threats
    
    async def _scan_patterns(self, content: bytes) -> List[ThreatIndicator]:
        """Scan for suspicious patterns"""
        threats = []
        
        # Suspicious patterns
        patterns = {
            b'<script[^>]*>.*?</script>': ('Embedded JavaScript', 0.7, ValidationSeverity.WARNING),
            b'javascript:': ('JavaScript protocol', 0.6, ValidationSeverity.WARNING),
            b'vbscript:': ('VBScript protocol', 0.8, ValidationSeverity.ERROR),
            b'data:text/html': ('Data URI HTML', 0.5, ValidationSeverity.WARNING),
            b'<?php': ('PHP code', 0.4, ValidationSeverity.INFO),
            b'<%[^@]': ('Server-side code', 0.5, ValidationSeverity.WARNING),
            b'eval\s*\(': ('Code evaluation', 0.8, ValidationSeverity.ERROR),
            b'document\.write': ('DOM manipulation', 0.4, ValidationSeverity.INFO),
            b'window\.location': ('Location redirect', 0.3, ValidationSeverity.INFO),
        }
        
        try:
            for pattern, (description, risk_score, severity) in patterns.items():
                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                    threats.append(ThreatIndicator(
                        indicator_type="suspicious_pattern",
                        severity=severity,
                        description=f"Suspicious pattern detected: {description}",
                        risk_score=risk_score,
                        mitigation="Review content manually"
                    ))
        
        except Exception as e:
            self.logger.error("Pattern scanning failed", error=str(e))
        
        return threats
    
    async def _scan_embedded_content(self, file_path: Path) -> List[ThreatIndicator]:
        """Scan for embedded content in files"""
        threats = []
        
        try:
            # Check for embedded files in archives
            if file_path.suffix.lower() in {'.zip', '.docx', '.xlsx', '.pptx'}:
                threats.extend(await self._scan_archive_content(file_path))
            
            # Check for macros in Office documents
            if file_path.suffix.lower() in {'.docm', '.xlsm', '.pptm'}:
                threats.append(ThreatIndicator(
                    indicator_type="macro_enabled",
                    severity=ValidationSeverity.WARNING,
                    description="Macro-enabled Office document",
                    risk_score=0.6,
                    mitigation="Disable macros before opening"
                ))
        
        except Exception as e:
            self.logger.error("Embedded content scanning failed", error=str(e))
        
        return threats
    
    async def _scan_archive_content(self, file_path: Path) -> List[ThreatIndicator]:
        """Scan archive contents for threats"""
        threats = []
        
        try:
            import zipfile
            
            with zipfile.ZipFile(file_path, 'r') as archive:
                for file_info in archive.infolist():
                    filename = file_info.filename.lower()
                    
                    # Check for suspicious filenames
                    if any(ext in filename for ext in DANGEROUS_EXTENSIONS):
                        threats.append(ThreatIndicator(
                            indicator_type="dangerous_archive_content",
                            severity=ValidationSeverity.CRITICAL,
                            description=f"Dangerous file in archive: {filename}",
                            risk_score=0.9,
                            mitigation="Do not extract or execute"
                        ))
                    
                    # Check for directory traversal attempts
                    if '../' in filename or filename.startswith('/'):
                        threats.append(ThreatIndicator(
                            indicator_type="path_traversal",
                            severity=ValidationSeverity.ERROR,
                            description=f"Path traversal attempt: {filename}",
                            risk_score=0.8,
                            mitigation="Sanitize extraction path"
                        ))
        
        except Exception as e:
            self.logger.error("Archive scanning failed", error=str(e))
        
        return threats

class VirusScanner:
    """Virus scanning using ClamAV or other engines"""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        self.logger = logger.bind(component="virus_scanner")
        self.clamav_available = self._check_clamav()
    
    def _check_clamav(self) -> bool:
        """Check if ClamAV is available"""
        try:
            result = subprocess.run(['clamscan', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    async def scan_file(self, file_path: Path) -> List[ThreatIndicator]:
        """Scan file for viruses"""
        threats = []
        
        if not self.config.clamav_enabled or not self.clamav_available:
            return threats
        
        try:
            # Run ClamAV scan
            process = await asyncio.create_subprocess_exec(
                'clamscan', '--no-summary', '--infected', str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=SCAN_TIMEOUT
            )
            
            if process.returncode == 1:  # Virus found
                threat_name = self._extract_threat_name(stdout.decode())
                threats.append(ThreatIndicator(
                    indicator_type="virus_detected",
                    severity=ValidationSeverity.CRITICAL,
                    description=f"Virus detected: {threat_name}",
                    risk_score=1.0,
                    mitigation="Quarantine immediately"
                ))
            
        except asyncio.TimeoutError:
            threats.append(ThreatIndicator(
                indicator_type="scan_timeout",
                severity=ValidationSeverity.WARNING,
                description="Virus scan timed out",
                risk_score=0.3,
                mitigation="Manual scan recommended"
            ))
        except Exception as e:
            self.logger.error("Virus scan failed", file_path=str(file_path), error=str(e))
        
        return threats
    
    def _extract_threat_name(self, scan_output: str) -> str:
        """Extract threat name from ClamAV output"""
        lines = scan_output.strip().split('\n')
        for line in lines:
            if 'FOUND' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    return parts[1].strip().replace(' FOUND', '')
        return "Unknown threat"

class FileStructureValidator:
    """Validate file structure and integrity"""
    
    def __init__(self):
        self.logger = logger.bind(component="structure_validator")
    
    async def validate_structure(self, file_path: Path, mime_type: str) -> List[ValidationIssue]:
        """Validate file structure based on type"""
        issues = []
        
        try:
            if mime_type.startswith('image/'):
                issues.extend(await self._validate_image_structure(file_path))
            elif mime_type == 'application/pdf':
                issues.extend(await self._validate_pdf_structure(file_path))
            elif mime_type in ['application/zip', 'application/x-zip-compressed']:
                issues.extend(await self._validate_zip_structure(file_path))
            elif mime_type.startswith('text/'):
                issues.extend(await self._validate_text_structure(file_path))
        
        except Exception as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"Structure validation failed: {str(e)}",
                suggested_action="Manual review required"
            ))
        
        return issues
    
    async def _validate_image_structure(self, file_path: Path) -> List[ValidationIssue]:
        """Validate image file structure"""
        issues = []
        
        try:
            # Enable truncated image loading for validation
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            
            with Image.open(file_path) as img:
                # Check for reasonable dimensions
                width, height = img.size
                if width > 50000 or height > 50000:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.STRUCTURE_VALIDATION,
                        severity=ValidationSeverity.WARNING,
                        message=f"Unusually large image dimensions: {width}x{height}",
                        suggested_action="Verify image integrity"
                    ))
                
                # Check for suspicious metadata
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif()
                    if len(str(exif_data)) > 10000:  # Suspiciously large EXIF
                        issues.append(ValidationIssue(
                            category=ValidationCategory.STRUCTURE_VALIDATION,
                            severity=ValidationSeverity.WARNING,
                            message="Unusually large EXIF data",
                            suggested_action="Strip metadata before use"
                        ))
        
        except Exception as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"Image structure validation failed: {str(e)}",
                suggested_action="File may be corrupted"
            ))
        
        return issues
    
    async def _validate_pdf_structure(self, file_path: Path) -> List[ValidationIssue]:
        """Validate PDF file structure"""
        issues = []
        
        try:
            # Read PDF header and trailer
            async with aiofiles.open(file_path, 'rb') as f:
                header = await f.read(10)
                if not header.startswith(b'%PDF-'):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.STRUCTURE_VALIDATION,
                        severity=ValidationSeverity.ERROR,
                        message="Invalid PDF header",
                        suggested_action="File may be corrupted or not a valid PDF"
                    ))
                
                # Check for PDF version
                version_match = re.search(rb'%PDF-(\d+\.\d+)', header)
                if version_match:
                    version = float(version_match.group(1))
                    if version > 2.0:
                        issues.append(ValidationIssue(
                            category=ValidationCategory.STRUCTURE_VALIDATION,
                            severity=ValidationSeverity.INFO,
                            message=f"High PDF version: {version}",
                            suggested_action="Ensure compatibility"
                        ))
        
        except Exception as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"PDF structure validation failed: {str(e)}"
            ))
        
        return issues
    
    async def _validate_zip_structure(self, file_path: Path) -> List[ValidationIssue]:
        """Validate ZIP archive structure"""
        issues = []
        
        try:
            import zipfile
            
            with zipfile.ZipFile(file_path, 'r') as archive:
                # Test archive integrity
                bad_files = archive.testzip()
                if bad_files:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.STRUCTURE_VALIDATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Corrupted files in archive: {bad_files}",
                        suggested_action="Archive may be damaged"
                    ))
                
                # Check for compression bombs
                total_uncompressed = sum(info.file_size for info in archive.infolist())
                archive_size = file_path.stat().st_size
                
                if archive_size > 0 and total_uncompressed / archive_size > 100:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.STRUCTURE_VALIDATION,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"Potential compression bomb (ratio: {total_uncompressed/archive_size:.1f}:1)",
                        suggested_action="Do not extract"
                    ))
        
        except zipfile.BadZipFile:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message="Invalid ZIP file structure",
                suggested_action="File is not a valid ZIP archive"
            ))
        except Exception as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"ZIP validation failed: {str(e)}"
            ))
        
        return issues
    
    async def _validate_text_structure(self, file_path: Path) -> List[ValidationIssue]:
        """Validate text file structure"""
        issues = []
        
        try:
            # Check encoding and structure
            encodings = ['utf-8', 'ascii', 'latin-1', 'cp1252']
            valid_encoding = None
            
            for encoding in encodings:
                try:
                    async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                        content = await f.read(1024)  # Sample first 1KB
                        valid_encoding = encoding
                        break
                except UnicodeDecodeError:
                    continue
            
            if not valid_encoding:
                issues.append(ValidationIssue(
                    category=ValidationCategory.STRUCTURE_VALIDATION,
                    severity=ValidationSeverity.WARNING,
                    message="Could not detect text encoding",
                    suggested_action="File may contain binary data"
                ))
            
            # Check for extremely long lines (potential attack)
            if valid_encoding:
                async with aiofiles.open(file_path, 'r', encoding=valid_encoding) as f:
                    line_count = 0
                    async for line in f:
                        line_count += 1
                        if len(line) > 10000:
                            issues.append(ValidationIssue(
                                category=ValidationCategory.STRUCTURE_VALIDATION,
                                severity=ValidationSeverity.WARNING,
                                message=f"Extremely long line detected (line {line_count})",
                                suggested_action="Review for malicious content"
                            ))
                        
                        if line_count > 1000:  # Limit check to first 1000 lines
                            break
        
        except Exception as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.STRUCTURE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"Text structure validation failed: {str(e)}"
            ))
        
        return issues

class FileValidator:
    """Main file validator orchestrating all validation components"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.logger = logger.bind(component="file_validator")
        
        # Initialize components
        self.signature_analyzer = FileSignatureAnalyzer()
        self.content_scanner = ContentSecurityScanner(self.config)
        self.virus_scanner = VirusScanner(self.config)
        self.structure_validator = FileStructureValidator()
        
        # Initialize quarantine directory
        self._initialize_quarantine_directory()
    
    def _initialize_quarantine_directory(self) -> None:
        """Initialize quarantine directory"""
        quarantine_path = Path(self.config.quarantine_dir)
        quarantine_path.mkdir(parents=True, exist_ok=True)
        self.logger.info("Quarantine directory initialized", path=str(quarantine_path))
    
    @track_performance
    async def validate_upload_file(self, file: UploadFile) -> ValidationResult:
        """Validate uploaded file comprehensively"""
        start_time = datetime.utcnow()
        
        # Create temporary file for validation
        temp_file = None
        try:
            # Basic filename validation
            filename_issues = await self._validate_filename(file.filename)
            
            # Create temporary file
            temp_file = await self._create_temp_file(file)
            
            # Calculate checksum
            checksum = await self._calculate_checksum(temp_file)
            
            # Basic file properties
            file_size = temp_file.stat().st_size
            size_issues = await self._validate_file_size(file_size)
            
            # File signature analysis
            signature = await self._analyze_file_signature(temp_file)
            
            # Extension validation
            extension_issues = await self._validate_file_extension(file.filename, signature.extension)
            
            # MIME type validation
            mime_issues = await self._validate_mime_type(signature.mime_type)
            
            # Structure validation
            structure_issues = await self.structure_validator.validate_structure(
                temp_file, signature.mime_type
            )
            
            # Content security scanning
            threat_indicators = []
            if self.config.enable_content_scan:
                threat_indicators = await self.content_scanner.scan_content(temp_file)
            
            # Virus scanning
            virus_threats = []
            if self.config.enable_virus_scan:
                virus_threats = await self.virus_scanner.scan_file(temp_file)
            
            # Combine all issues
            all_issues = (filename_issues + size_issues + extension_issues + 
                         mime_issues + structure_issues)
            
            # Add threat indicators as issues
            for threat in threat_indicators + virus_threats:
                all_issues.append(ValidationIssue(
                    category=ValidationCategory.CONTENT_SECURITY,
                    severity=threat.severity,
                    message=threat.description,
                    details={"risk_score": threat.risk_score},
                    suggested_action=threat.mitigation
                ))
            
            # Calculate security score
            security_score = await self._calculate_security_score(all_issues, threat_indicators + virus_threats)
            
            # Determine if file should be quarantined
            quarantined = await self._should_quarantine(all_issues, security_score)
            if quarantined:
                await self._quarantine_file(temp_file, checksum)
            
            # Determine overall validity
            is_valid = await self._determine_validity(all_issues, security_score)
            
            scan_duration = (datetime.utcnow() - start_time).total_seconds()
            
            result = ValidationResult(
                is_valid=is_valid,
                file_size=file_size,
                mime_type=signature.mime_type,
                detected_extension=signature.extension,
                issues=all_issues,
                security_score=security_score,
                scan_duration=scan_duration,
                checksum=checksum,
                quarantined=quarantined
            )
            
            self.logger.info(
                "File validation completed",
                filename=file.filename,
                is_valid=is_valid,
                security_score=security_score,
                issue_count=len(all_issues),
                scan_duration=scan_duration
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Validation failed: {str(e)}"
            self.logger.error("File validation error", filename=file.filename, error=str(e))
            
            return ValidationResult(
                is_valid=False,
                file_size=0,
                mime_type="unknown",
                detected_extension="unknown",
                issues=[ValidationIssue(
                    category=ValidationCategory.FILE_TYPE,
                    severity=ValidationSeverity.CRITICAL,
                    message=error_msg
                )],
                security_score=0.0,
                scan_duration=(datetime.utcnow() - start_time).total_seconds(),
                checksum="",
                error_message=error_msg
            )
        
        finally:
            # Clean up temporary file
            if temp_file and temp_file.exists():
                temp_file.unlink(missing_ok=True)
    
    async def _create_temp_file(self, file: UploadFile) -> Path:
        """Create temporary file from upload"""
        temp_dir = Path(tempfile.gettempdir()) / "ymera_validation"
        temp_dir.mkdir(exist_ok=True)
        
        temp_file = temp_dir / f"{uuid.uuid4()}{Path(file.filename).suffix}"
        
        # Reset file pointer
        await file.seek(0)
        
        # Write to temporary file
        async with aiofiles.open(temp_file, 'wb') as f:
            while chunk := await file.read(8192):
                await f.write(chunk)
        
        # Reset file pointer again for further processing
        await file.seek(0)
        
        return temp_file
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum"""
        hasher = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    async def _analyze_file_signature(self, file_path: Path) -> FileSignature:
        """Analyze file signature"""
        async with aiofiles.open(file_path, 'rb') as f:
            header = await f.read(512)  # Read first 512 bytes
        
        return await self.signature_analyzer.analyze_signature(header)
    
    async def _validate_filename(self, filename: str) -> List[ValidationIssue]:
        """Validate filename"""
        issues = []
        
        if not filename:
            issues.append(ValidationIssue(
                category=ValidationCategory.NAME_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message="Filename is empty"
            ))
            return issues
        
        # Length check
        if len(filename) > MAX_FILENAME_LENGTH:
            issues.append(ValidationIssue(
                category=ValidationCategory.NAME_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"Filename too long ({len(filename)} > {MAX_FILENAME_LENGTH})"
            ))
        
        # Character validation
        invalid_chars = set(filename) & {'<', '>', ':', '"', '|', '?', '*', '\x00'}
        if invalid_chars:
            issues.append(ValidationIssue(
                category=ValidationCategory.NAME_VALIDATION,
                severity=ValidationSeverity.WARNING,
                message=f"Invalid characters in filename: {', '.join(invalid_chars)}"
            ))
        
        # Path traversal check
        if '..' in filename or filename.startswith('/') or '\\' in filename:
            issues.append(ValidationIssue(
                category=ValidationCategory.NAME_VALIDATION,
                severity=ValidationSeverity.CRITICAL,
                message="Potential path traversal in filename",
                suggested_action="Rename file"
            ))
        
        # Hidden file check
        if filename.startswith('.'):
            issues.append(ValidationIssue(
                category=ValidationCategory.NAME_VALIDATION,
                severity=ValidationSeverity.INFO,
                message="Hidden file (starts with dot)"
            ))
        
        return issues
    
    async def _validate_file_size(self, file_size: int) -> List[ValidationIssue]:
        """Validate file size"""
        issues = []
        
        if file_size < self.config.min_file_size:
            issues.append(ValidationIssue(
                category=ValidationCategory.SIZE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"File too small ({file_size} < {self.config.min_file_size} bytes)"
            ))
        
        if file_size > self.config.max_file_size:
            issues.append(ValidationIssue(
                category=ValidationCategory.SIZE_VALIDATION,
                severity=ValidationSeverity.ERROR,
                message=f"File too large ({file_size} > {self.config.max_file_size} bytes)"
            ))
        
        return issues
    
    async def _validate_file_extension(self, filename: str, detected_extension: str) -> List[ValidationIssue]:
        """Validate file extension"""
        issues = []
        
        file_extension = Path(filename).suffix.lower()
        
        # Check for dangerous extensions
        if file_extension in self.config.dangerous_extensions:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.CRITICAL,
                message=f"Dangerous file extension: {file_extension}",
                suggested_action="File type not allowed"
            ))
        
        # Check if extension is allowed
        elif file_extension not in self.config.allowed_extensions and file_extension:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.ERROR,
                message=f"File extension not allowed: {file_extension}",
                suggested_action="Use supported file format"
            ))
        
        # Check for extension spoofing
        if file_extension != detected_extension and detected_extension:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.WARNING,
                message=f"Extension mismatch: filename has {file_extension}, detected {detected_extension}",
                suggested_action="Verify file authenticity"
            ))
        
        # Multiple extensions check
        if filename.count('.') > 2:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.WARNING,
                message="Multiple file extensions detected",
                suggested_action="Review filename"
            ))
        
        return issues
    
    async def _validate_mime_type(self, mime_type: str) -> List[ValidationIssue]:
        """Validate MIME type"""
        issues = []
        
        if mime_type not in ALLOWED_MIME_TYPES:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.WARNING,
                message=f"MIME type not explicitly allowed: {mime_type}",
                suggested_action="Verify file type is safe"
            ))
        
        # Check for suspicious MIME types
        suspicious_types = {
            'application/x-executable',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/octet-stream'
        }
        
        if mime_type in suspicious_types:
            issues.append(ValidationIssue(
                category=ValidationCategory.FILE_TYPE,
                severity=ValidationSeverity.ERROR,
                message=f"Suspicious MIME type: {mime_type}",
                suggested_action="Manual review required"
            ))
        
        return issues
    
    async def _calculate_security_score(
        self, 
        issues: List[ValidationIssue], 
        threats: List[ThreatIndicator]
    ) -> float:
        """Calculate overall security score (0.0 to 1.0)"""
        base_score = 1.0
        
        # Deduct points for issues
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                base_score -= 0.4
            elif issue.severity == ValidationSeverity.ERROR:
                base_score -= 0.2
            elif issue.severity == ValidationSeverity.WARNING:
                base_score -= 0.1
            elif issue.severity == ValidationSeverity.INFO:
                base_score -= 0.05
        
        # Deduct points for threats
        for threat in threats:
            base_score -= threat.risk_score * 0.3
        
        return max(0.0, min(1.0, base_score))
    
    async def _should_quarantine(self, issues: List[ValidationIssue], security_score: float) -> bool:
        """Determine if file should be quarantined"""
        # Critical issues always quarantine
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL:
                return True
        
        # Low security score quarantines
        if security_score < 0.3:
            return True
        
        return False
    
    async def _quarantine_file(self, file_path: Path, checksum: str) -> None:
        """Move file to quarantine"""
        try:
            quarantine_dir = Path(self.config.quarantine_dir)
            quarantine_path = quarantine_dir / f"{checksum}_{file_path.name}"
            
            # Copy file to quarantine
            async with aiofiles.open(file_path, 'rb') as src:
                async with aiofiles.open(quarantine_path, 'wb') as dst:
                    while chunk := await src.read(8192):
                        await dst.write(chunk)
            
            # Create metadata file
            metadata = {
                "original_path": str(file_path),
                "quarantine_time": datetime.utcnow().isoformat(),
                "checksum": checksum,
                "reason": "Failed security validation"
            }
            
            metadata_path = quarantine_path.with_suffix('.json')
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            self.logger.warning(
                "File quarantined",
                original_path=str(file_path),
                quarantine_path=str(quarantine_path),
                checksum=checksum
            )
            
        except Exception as e:
            self.logger.error("Failed to quarantine file", error=str(e))
    
    async def _determine_validity(self, issues: List[ValidationIssue], security_score: float) -> bool:
        """Determine if file is valid for upload"""
        # Critical or error issues make file invalid
        for issue in issues:
            if issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
                return False
        
        # Very low security score makes file invalid
        if security_score < 0.5:
            return False
        
        return True
    
    async def validate_file_path(self, file_path: Path) -> ValidationResult:
        """Validate existing file on disk"""
        start_time = datetime.utcnow()
        
        try:
            if not file_path.exists():
                return ValidationResult(
                    is_valid=False,
                    file_size=0,
                    mime_type="unknown",
                    detected_extension="unknown",
                    issues=[ValidationIssue(
                        category=ValidationCategory.FILE_TYPE,
                        severity=ValidationSeverity.ERROR,
                        message="File does not exist"
                    )],
                    security_score=0.0,
                    scan_duration=0.0,
                    checksum=""
                )
            
            # File properties
            file_size = file_path.stat().st_size
            checksum = await self._calculate_checksum(file_path)
            
            # Analyze signature
            signature = await self._analyze_file_signature(file_path)
            
            # Run all validations
            filename_issues = await self._validate_filename(file_path.name)
            size_issues = await self._validate_file_size(file_size)
            extension_issues = await self._validate_file_extension(file_path.name, signature.extension)
            mime_issues = await self._validate_mime_type(signature.mime_type)
            structure_issues = await self.structure_validator.validate_structure(file_path, signature.mime_type)
            
            # Security scans
            threat_indicators = []
            if self.config.enable_content_scan:
                threat_indicators = await self.content_scanner.scan_content(file_path)
            
            virus_threats = []
            if self.config.enable_virus_scan:
                virus_threats = await self.virus_scanner.scan_file(file_path)
            
            # Combine issues
            all_issues = (filename_issues + size_issues + extension_issues + 
                         mime_issues + structure_issues)
            
            for threat in threat_indicators + virus_threats:
                all_issues.append(ValidationIssue(
                    category=ValidationCategory.CONTENT_SECURITY,
                    severity=threat.severity,
                    message=threat.description,
                    details={"risk_score": threat.risk_score},
                    suggested_action=threat.mitigation
                ))
            
            # Calculate scores and validity
            security_score = await self._calculate_security_score(all_issues, threat_indicators + virus_threats)
            quarantined = await self._should_quarantine(all_issues, security_score)
            is_valid = await self._determine_validity(all_issues, security_score)
            
            scan_duration = (datetime.utcnow() - start_time).total_seconds()
            
            return ValidationResult(
                is_valid=is_valid,
                file_size=file_size,
                mime_type=signature.mime_type,
                detected_extension=signature.extension,
                issues=all_issues,
                security_score=security_score,
                scan_duration=scan_duration,
                checksum=checksum,
                quarantined=quarantined
            )
            
        except Exception as e:
            error_msg = f"File validation failed: {str(e)}"
            return ValidationResult(
                is_valid=False,
                file_size=0,
                mime_type="unknown",
                detected_extension="unknown",
                issues=[ValidationIssue(
                    category=ValidationCategory.FILE_TYPE,
                    severity=ValidationSeverity.CRITICAL,
                    message=error_msg
                )],
                security_score=0.0,
                scan_duration=(datetime.utcnow() - start_time).total_seconds(),
                checksum="",
                error_message=error_msg
            )
    
    async def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        try:
            quarantine_dir = Path(self.config.quarantine_dir)
            total_quarantined = len(list(quarantine_dir.glob("*.json"))) if quarantine_dir.exists() else 0
            
            # Calculate quarantine directory size
            quarantine_size = 0
            if quarantine_dir.exists():
                for file_path in quarantine_dir.rglob("*"):
                    if file_path.is_file():
                        quarantine_size += file_path.stat().st_size
            
            return {
                "quarantine_directory": str(quarantine_dir),
                "total_quarantined_files": total_quarantined,
                "quarantine_size_bytes": quarantine_size,
                "clamav_available": self.virus_scanner.clamav_available,
                "yara_rules_loaded": self.content_scanner.yara_rules is not None,
                "supported_extensions": len(self.config.allowed_extensions),
                "dangerous_extensions": len(self.config.dangerous_extensions)
            }
            
        except Exception as e:
            self.logger.error("Failed to get validation statistics", error=str(e))
            return {"error": str(e)}
    
    async def cleanup_quarantine(self, days_old: int = None) -> int:
        """Clean up old quarantined files"""
        if days_old is None:
            days_old = QUARANTINE_RETENTION_DAYS
        
        cleanup_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        try:
            quarantine_dir = Path(self.config.quarantine_dir)
            if not quarantine_dir.exists():
                return 0
            
            for metadata_file in quarantine_dir.glob("*.json"):
                try:
                    # Read metadata
                    async with aiofiles.open(metadata_file, 'r') as f:
                        metadata = json.loads(await f.read())
                    
                    quarantine_time = datetime.fromisoformat(metadata.get("quarantine_time", ""))
                    
                    if quarantine_time < cutoff_date:
                        # Remove quarantined file and metadata
                        file_path = metadata_file.with_suffix('')
                        if file_path.exists():
                            file_path.unlink()
                        metadata_file.unlink()
                        cleanup_count += 1
                
                except Exception as e:
                    self.logger.error("Failed to cleanup quarantine file", 
                                    file=str(metadata_file), error=str(e))
            
            self.logger.info("Quarantine cleanup completed", files_removed=cleanup_count)
            return cleanup_count
            
        except Exception as e:
            self.logger.error("Quarantine cleanup failed", error=str(e))
            return 0

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def get_file_category(extension: str) -> Optional[str]:
    """Get file category based on extension"""
    extension = extension.lower()
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return category
    return None

def is_extension_allowed(extension: str) -> bool:
    """Check if file extension is allowed"""
    extension = extension.lower()
    all_allowed = set().union(*ALLOWED_EXTENSIONS.values())
    return extension in all_allowed and extension not in DANGEROUS_EXTENSIONS

def is_mime_type_safe(mime_type: str) -> bool:
    """Check if MIME type is considered safe"""
    return mime_type in ALLOWED_MIME_TYPES

async def quick_file_check(filename: str, file_size: int) -> Dict[str, bool]:
    """Quick preliminary file check"""
    extension = Path(filename).suffix.lower()
    
    return {
        "filename_valid": len(filename) <= MAX_FILENAME_LENGTH and '..' not in filename,
        "extension_allowed": is_extension_allowed(extension),
        "size_valid": MIN_FILE_SIZE <= file_size <= MAX_FILE_SIZE,
        "not_dangerous": extension not in DANGEROUS_EXTENSIONS
    }

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_file_validator(config: Optional[ValidationConfig] = None) -> FileValidator:
    """Initialize file validator for production use"""
    if config is None:
        config = ValidationConfig(
            enable_virus_scan=settings.ENABLE_VIRUS_SCAN,
            enable_content_scan=settings.ENABLE_CONTENT_SCAN,
            max_file_size=settings.MAX_FILE_SIZE,
            quarantine_dir=settings.QUARANTINE_DIR,
            yara_rules_dir=settings.YARA_RULES_DIR,
            clamav_enabled=settings.CLAMAV_ENABLED
        )
    
    validator = FileValidator(config)
    
    logger.info("File validator initialized successfully")
    return validator

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "FileValidator",
    "ValidationConfig",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationCategory",
    "ThreatIndicator",
    "FileSignature",
    "initialize_file_validator",
    "get_file_category",
    "is_extension_allowed",
    "is_mime_type_safe",
    "quick_file_check"
]