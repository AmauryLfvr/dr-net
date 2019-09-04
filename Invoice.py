from pdf2image import convert_from_path
from OCREngine import OCREngine
import re


class Invoice:
    def __init__(self, PDF_path):
        self.pages = [
            InvoicePage(page) for page in convert_from_path(PDF_path, 500)
        ]  # Each of the individual pages in the PDF is converted to images

        self.is_text_based = (
            False
        )  # TODO: Need to implement way to check if PDF is text based

    def length(self):
        return len(self.pages)

    def get_all_tokens(self):
        ocr_engine = OCREngine()
        return {
            page_number + 1: ocr_engine.OCR(page)
            for (page_number, page) in enumerate(self.pages)
        }

    def get_page(self, page_number):
        return self.pages[page_number - 1]


class InvoicePage:
    def __init__(self, image):
        self.page = image
        self.tokens = None
        self.tokens_by_block = None

    def do_OCR(self):
        if not self.tokens:
            ocr_engine = OCREngine()
            self.tokens = ocr_engine.OCR(self.page)

    def get_tokens_by_block(self, block_num=None):
        self.do_OCR()
        if self.tokens_by_block:
            return self.tokens_by_block

        blocks = {}

        for token in self.tokens:
            block_num = token.token_structure["block_num"]
            if block_num in blocks:
                blocks[block_num].append(token)
            else:
                blocks[block_num] = [token]

        self.tokens_by_block = blocks

        return blocks

    def search_tokens(self, text: str):
        self.do_OCR()
        filtered_tokens = list(
            filter(lambda token: bool(re.search(text, token.text.lower())), self.tokens)
        )

        return filtered_tokens


##### TODO: The following code is relevant to text-based invoices and needs to be integrated
##### into the invoice class in the future


def convert_text_to_result(text):

    result = (
        None
    )  # TODO: Use invoice2data or other means to obtain results using text from invoice

    return result


def convert_text_based_pdf_to_result(invoice):
    templates = read_templates("./templates")

    # TODO: Implement data extraction using invoice2data

    return None