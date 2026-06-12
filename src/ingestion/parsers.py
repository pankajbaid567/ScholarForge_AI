import fitz  # PyMuPDF
from bs4 import BeautifulSoup
import io

class DocumentParser:
    def parse(self, file_content: bytes) -> str:
        raise NotImplementedError("Subclasses must implement parse method")

class PDFParser(DocumentParser):
    def parse(self, file_content: bytes) -> str:
        text = ""
        try:
            # fitz expects a stream or file path, for bytes we can use fitz.open(stream=..., filetype="pdf")
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text += page.get_text()
        except Exception as e:
            print(f"Error parsing PDF: {e}")
        return text

class TXTParser(DocumentParser):
    def parse(self, file_content: bytes) -> str:
        try:
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            return file_content.decode('latin-1', errors='replace')

class HTMLParser(DocumentParser):
    def parse(self, file_content: bytes) -> str:
        try:
            soup = BeautifulSoup(file_content, 'html.parser')
            # Extract text and replace multiple newlines with a single space
            text = soup.get_text(separator=' ', strip=True)
            return text
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            return ""

class ParserFactory:
    @staticmethod
    def get_parser(filename: str) -> DocumentParser:
        if filename.endswith('.pdf'):
            return PDFParser()
        elif filename.endswith('.txt') or filename.endswith('.md'):
            return TXTParser()
        elif filename.endswith('.html'):
            return HTMLParser()
        else:
            raise ValueError(f"Unsupported file type for {filename}")
