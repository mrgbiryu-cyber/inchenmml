import os
import tempfile

from fastapi import HTTPException, UploadFile


class DocumentParserService:
    """Parse uploaded documents with fallback strategies."""
    supported_extensions = [".pdf", ".docx", ".xlsx", ".xls", ".excel", ".ppt", ".pptx", ".hwp", ".hwpx", ".txt", ".md", ".csv"]

    async def parse_upload_file(self, file: UploadFile) -> str:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename missing")

        filename = file.filename.lower()
        content = await file.read()
        suffix = os.path.splitext(filename)[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return self._parse_file(tmp_path, suffix)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def is_supported_extension(self, suffix: str) -> bool:
        return suffix.lower() in self.supported_extensions

    def _parse_file(self, file_path: str, suffix: str) -> str:
        suffix = suffix.lower()
        try:
            if suffix == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader

                loader = PyPDFLoader(file_path)
                docs = loader.load()
                return "\n".join([doc.page_content for doc in docs])

            if suffix == ".docx":
                from langchain_community.document_loaders import Docx2txtLoader

                loader = Docx2txtLoader(file_path)
                docs = loader.load()
                return "\n".join([doc.page_content for doc in docs])

            if suffix in [".xlsx", ".xls", ".excel"]:
                from langchain_community.document_loaders import UnstructuredExcelLoader

                loader = UnstructuredExcelLoader(file_path)
                docs = loader.load()
                return "\n".join([doc.page_content for doc in docs])

            if suffix in [".ppt", ".pptx"]:
                try:
                    from langchain_community.document_loaders import UnstructuredPowerPointLoader

                    loader = UnstructuredPowerPointLoader(file_path)
                    docs = loader.load()
                    return "\n".join([doc.page_content for doc in docs])
                except Exception:
                    with open(file_path, "rb") as f:
                        return f.read().decode("utf-8", errors="ignore")

            if suffix in [".hwp", ".hwpx"]:
                # Best effort fallback. Dedicated parser can be added later.
                with open(file_path, "rb") as f:
                    raw = f.read().decode("utf-8", errors="ignore")
                return raw if raw.strip() else "[HWP/HWPX content could not be fully parsed]"

            if suffix in [".txt", ".md", ".csv"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()

            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Document parsing failed: {str(e)}")


document_parser_service = DocumentParserService()
