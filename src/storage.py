"""Storage module for saving and loading notes linked to PDF files."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path


class NotesStorage:
    """Handles saving and loading notes as JSON files linked to PDFs."""

    def __init__(self, notes_dir: str = "notes_data"):
        """Initialize storage with the notes directory path."""
        self.notes_dir = Path(notes_dir)
        self._ensure_notes_dir()

    def _validate_pdf_path(self, pdf_path: str) -> bool:
        """Validate that pdf_path is a valid, non-empty string path.

        Args:
            pdf_path: Path to validate

        Returns:
            True if valid, False otherwise
        """
        if not pdf_path or not isinstance(pdf_path, str):
            return False
        if not pdf_path.strip():
            return False
        try:
            # Validate that the path can be parsed
            Path(pdf_path)
            return True
        except (OSError, ValueError):
            return False

    def _ensure_notes_dir(self):
        """Create the notes directory if it doesn't exist with secure permissions."""
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        # Set secure permissions: owner read/write/execute only (700)
        os.chmod(self.notes_dir, 0o700)

    def _get_notes_path(self, pdf_path: str) -> Path:
        """Get the notes file path for a given PDF.

        Uses a hash of the resolved path to prevent collisions between
        PDFs with the same name in different directories.
        """
        resolved_path = str(Path(pdf_path).resolve())
        path_hash = hashlib.sha256(resolved_path.encode()).hexdigest()[:12]
        pdf_name = Path(pdf_path).stem
        return self.notes_dir / f"{pdf_name}_{path_hash}.notes.json"

    def save_notes(self, pdf_path: str, html_content: str) -> bool:
        """
        Save notes for a PDF file.

        Args:
            pdf_path: Path to the PDF file
            html_content: Rich text content as HTML

        Returns:
            True if save was successful, False otherwise
        """
        if not self._validate_pdf_path(pdf_path):
            print(f"Error saving notes: Invalid PDF path")
            return False

        try:
            notes_path = self._get_notes_path(pdf_path)
            data = {
                "pdf_path": pdf_path,
                "pdf_filename": Path(pdf_path).name,
                "content": html_content,
                "last_modified": datetime.now().isoformat()
            }
            with open(notes_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Set secure permissions: owner read/write only (600)
            os.chmod(notes_path, 0o600)
            return True
        except Exception as e:
            print(f"Error saving notes: {e}")
            return False

    def load_notes(self, pdf_path: str) -> dict | None:
        """
        Load notes for a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with notes data or None if not found
        """
        if not self._validate_pdf_path(pdf_path):
            print(f"Error loading notes: Invalid PDF path")
            return None

        try:
            notes_path = self._get_notes_path(pdf_path)
            if notes_path.exists():
                with open(notes_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Error loading notes: {e}")
            return None

    def notes_exist(self, pdf_path: str) -> bool:
        """Check if notes exist for a given PDF."""
        if not self._validate_pdf_path(pdf_path):
            return False
        return self._get_notes_path(pdf_path).exists()
