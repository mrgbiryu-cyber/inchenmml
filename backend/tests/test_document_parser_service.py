import os
import pytest
from fastapi import HTTPException
from tempfile import NamedTemporaryFile

from app.services.document_parser_service import document_parser_service


def test_supported_extensions_include_excel_variant():
    assert document_parser_service.is_supported_extension(".excel")
    assert ".pdf" in document_parser_service.supported_extensions


def test_parse_unsupported_extension_raises_http_error():
    with NamedTemporaryFile("w", suffix=".zzz", delete=False, encoding="utf-8") as temp:
        temp.write("abc")
        temp_path = temp.name

    with pytest.raises(HTTPException):
        document_parser_service._parse_file(temp_path, ".zzz")

    os.remove(temp_path)
